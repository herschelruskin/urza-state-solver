#!/usr/bin/env python3
"""Isolated Oct-30 physical-deck rules extension; never mutate archived modules on disk.

Changes: Treasure Vault artifact-land recognition / {C} / 2X -> X treasures,
Moonsilver Key and land tutor coverage, Mycosynth Gardens copying Treasure Vault,
and Staff of Compleation's 1-life tap-to-destroy-owned-permanent mode.

This deliberately inherits the validated assertive/priority/exile-guard stack.
It is NOT a complete rules engine or multiplayer-combo certification.
"""
from __future__ import annotations

from dataclasses import replace

import dack_boonweaver_aura_exile_guard_20261029 as validated

sim = validated.sim
d = sim.d
newer = sim.root.newer
RULES_VERSION = "dack_physical_treasure_staff_v1"
VAULT = "Treasure Vault"
STAFF = "Staff of Compleation"
STAFF_LIFE1 = "__STAFF_PAID_LIFE_1__"

# Physical land + artifact type. This must precede variant registration.
d.LANDS = frozenset(set(d.LANDS) | {VAULT})
d.LAND_TUTOR_TARGETS = tuple(dict.fromkeys(tuple(d.LAND_TUTOR_TARGETS) + (VAULT,)))
d.MOONSILVER_MANA_ARTIFACTS = frozenset(set(d.MOONSILVER_MANA_ARTIFACTS) | {VAULT})
d.ARTIFACT_TUTOR_TARGETS = tuple(dict.fromkeys(tuple(d.ARTIFACT_TUTOR_TARGETS) + (VAULT,)))
if VAULT not in d.CARD_ID:
    _id = max(d.CARD_ID.values(), default=-1) + 1
    d.CARD_ID[VAULT] = _id
    d.ID_CARD[_id] = VAULT
_prior_artifact = d.is_artifact_perm

def is_artifact_perm(name):
    return name == VAULT or _prior_artifact(name)

d.is_artifact_perm = is_artifact_perm

_prior_tap = d.tap_mana_actions

def tap_mana_actions(s):
    out = list(_prior_tap(s))
    for i, p in enumerate(s.battlefield):
        if d.effective_name(p) != VAULT or p.tapped:
            continue
        bf = list(s.battlefield)
        bf[i] = replace(p, tapped=True)
        out.append(replace(s, battlefield=tuple(bf), c=s.c + 1))
    return out

d.tap_mana_actions = tap_mana_actions

# The inherited life ledger uses State.exile sentinels; extend the *same* ledger
# so the <40 life guard applies to all of Staff's modes collectively.
_prior_staff_life_spent = newer.staff_life_spent

def staff_life_spent(s):
    return _prior_staff_life_spent(s) + s.exile.count(STAFF_LIFE1)

newer.staff_life_spent = staff_life_spent

def vault_activation_actions(s):
    """2X unrestricted mana, tap and sacrifice Treasure Vault; create X Treasures.

    X=0 is legal but yields no deployment benefit; omit from this deployment
    search. All feasible positive X are enumerated (no heuristic X cap).
    Restricted legend and artifact-spell mana cannot pay this activated ability.
    """
    if not any(d.effective_name(p) == VAULT and not p.tapped for p in s.battlefield):
        return []
    max_x = (s.w + s.c + s.any) // 2
    out = []
    for X in range(1, max_x + 1):
        for paid in d.pay_options(s, 2 * X):
            for i, p in enumerate(paid.battlefield):
                if d.effective_name(p) != VAULT or p.tapped:
                    continue
                # Payment must not have tapped/consumed the source.
                bf = list(paid.battlefield)
                removed = bf.pop(i)
                # The source is an actual artifact land, not a Treasure token.
                out.append(replace(
                    paid, battlefield=tuple(bf),
                    grave=paid.grave + (removed.name,),
                    treasures=paid.treasures + X,
                ))
    return out

def staff_destroy_actions(s):
    """Staff's {T}, pay 1 life: destroy target permanent you own.

    The goldfish models only our own board. Abstract Treasure/Spawn tokens are
    targetable via their counters. Indestructible/regeneration/shields are not
    modeled by this restricted target implementation; add witnesses before
    permitting additional indestructible cards.
    """
    if not newer.staff_can_pay(s, 1):
        return []
    out = []
    for i, source in enumerate(s.battlefield):
        if d.effective_name(source) != STAFF or source.tapped:
            continue
        tapped = list(s.battlefield)
        tapped[i] = replace(source, tapped=True)
        paid = replace(s, battlefield=tuple(tapped),
                       exile=s.exile + (STAFF_LIFE1,))
        for j, target in enumerate(paid.battlefield):
            # No known indestructible target in the physical-99 goldfish.
            bf = list(paid.battlefield)
            victim = bf.pop(j)
            out.append(replace(paid, battlefield=tuple(bf),
                               grave=paid.grave + (victim.name,)))
        if paid.treasures:
            out.append(replace(paid, treasures=paid.treasures - 1))
        if paid.spawn:
            out.append(replace(paid, spawn=paid.spawn - 1))
    return out

_prior_utility = d.utility_actions

def utility_actions(s):
    return list(_prior_utility(s)) + vault_activation_actions(s) + staff_destroy_actions(s)

d.utility_actions = utility_actions

_prior_v03 = d.v03_actions

def v03_actions(s):
    out = list(_prior_v03(s))
    # Gardens's X=0, T copy an artifact with MV0. Treasure Vault is MV0.
    if any(p.name == "The Mycosynth Gardens" and not p.tapped and not p.aux
           for p in s.battlefield) and any(d.effective_name(p) == VAULT
                                          for p in s.battlefield):
        for i, garden in enumerate(s.battlefield):
            if garden.name != "The Mycosynth Gardens" or garden.tapped or garden.aux:
                continue
            bf = list(s.battlefield)
            bf[i] = replace(garden, tapped=True, aux="COPY:" + VAULT)
            out.append(replace(s, battlefield=tuple(bf)))
    return out

d.v03_actions = v03_actions

def rule_smoke():
    """Cheap focused rules witnesses; no expensive mulligan/beam search."""
    assert VAULT in d.LANDS and VAULT in d.LAND_TUTOR_TARGETS
    assert VAULT in d.MOONSILVER_MANA_ARTIFACTS
    assert d.is_artifact_perm(VAULT)
    assert d.CARD_ID[VAULT] != d.CARD_ID["Fomori Vault"]
    s = d.State(1, (), (), battlefield=(d.Perm(VAULT), d.Perm("Mox Opal"),
                                         d.Perm("Sol Ring")))
    assert d.metalcraft(s), "Vault must contribute to Mox Opal metalcraft"
    taps = d.tap_mana_actions(s)
    assert any(q.c == 1 and q.battlefield[0].tapped for q in taps)
    empty = d.State(1, (), (), battlefield=(d.Perm(VAULT),), c=0)
    assert not vault_activation_actions(empty)
    s = replace(empty, c=4)
    made = vault_activation_actions(s)
    assert {q.treasures for q in made} == {1, 2}, "X has a 2X activation cost"
    assert any(q.c == 0 and q.treasures == 2 and VAULT in q.grave for q in made)
    assert all(not any(p.name == VAULT for p in q.battlefield) for q in made)
    assert not any(q.treasures for q in vault_activation_actions(
        replace(empty, c=0, restricted_artifact=20, restricted_legend=20)))
    s = d.State(1, (), (), battlefield=(d.Perm("The Mycosynth Gardens"),
                                        d.Perm(VAULT)))
    copies = d.v03_actions(s)
    assert any(q.battlefield[0].aux == "COPY:" + VAULT for q in copies)
    copy = next(q for q in copies if q.battlefield[0].aux == "COPY:" + VAULT)
    copy_untapped = replace(copy, battlefield=tuple(
        replace(p, tapped=False) for p in copy.battlefield))
    assert any(q.c == 1 and q.battlefield[0].tapped
               for q in d.tap_mana_actions(copy_untapped))
    staff = d.State(1, (), (), battlefield=(d.Perm(STAFF), d.Perm("Trinisphere")))
    killed = staff_destroy_actions(staff)
    assert any(q.grave == ("Trinisphere",) and q.battlefield[0].tapped
               and STAFF_LIFE1 in q.exile for q in killed)
    assert any(q.grave == (STAFF,) for q in killed)
    spent = d.State(1, (), (), battlefield=(d.Perm(STAFF),),
                    exile=(newer.STAFF_LIFE4,) * 9 + (STAFF_LIFE1,) * 3)
    assert staff_life_spent(spent) == 39
    assert not staff_destroy_actions(spent)
    assert not newer.staff_can_pay(spent, 2)
    # The distinct printed and 2026 Mind Stone cards stay distinct.
    assert d.CARD_ID["Mind Stone"] != d.CARD_ID["The Mind Stone"]
    return {"status": "PASS", "rules_version": RULES_VERSION,
            "treasure_artifact_land": True, "treasure_mana": True,
            "treasure_2x_tokens": True, "staff_destroy": True,
            "staff_shared_life_ledger": True}

if __name__ == "__main__":
    import json
    print(json.dumps(rule_smoke(), sort_keys=True))
