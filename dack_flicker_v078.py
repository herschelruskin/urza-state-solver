#!/usr/bin/env python3
"""Dack flicker current-100 T1-T3 DEPLOYMENT-only engine fork.

Forks validated v0.77 and patches the minimum new mechanics required for the
2026-10-12 creature-flicker non-Boonweaver list. Never interprets a Dack cast
as an automatically completed win. Opponent response and combo-pile resolution
are deliberately NOT modeled in this phase.

The older v0.77 calibration/mulligan source remains unmodified.
"""
from __future__ import annotations
from dataclasses import replace
from itertools import combinations
from pathlib import Path
import random

import dack_v077_full_deck_accel as engine

d = engine.d
ROOT = Path(__file__).resolve().parent
DECK_FILE = ROOT / "dack_flicker_current100_20261012.txt"
CREATURES = frozenset({
    "Abdel Adrian, Gorion's Ward", "Bronzebeak Foragers",
    "Felidar Guardian", "Fiend Hunter", "Flickerwisp",
    "Radiant Solar", "Restoration Angel", "Wispweaver Angel",
})
MDFC = frozenset({"Emeria's Call", "Razorgrass Ambush"})
# All policy-eligible white spells, including white creatures except Radiant Solar.
WHITE_IMPRINTS = frozenset({
    "Abdel Adrian, Gorion's Ward", "Abeyance", "Bilbo's Gambit",
    "Blind Obedience", "Bronzebeak Foragers", "Calamity's Wake",
    "Charitable Levy", "Deafening Silence", "Emeria's Call",
    "Enlightened Tutor", "Felidar Guardian", "Fiend Hunter",
    "Flickerwisp", "Gleaming Splendor", "March of Otherworldly Light",
    "Orim's Chant", "Paladin Class", "Path to Exile", "Razorgrass Ambush",
    "Restoration Angel", "Scout's Warning", "Seam Rip", "Silence",
    "Smothering Tithe", "Static Prison", "Sunscour", "Swords to Plowshares",
    "Touch the Spirit Realm", "Vanquish the Horde", "Wispweaver Angel",
})
assert len(WHITE_IMPRINTS) == 30
NEW_LANDS = frozenset({"Blast Zone", "Emergence Zone", "Fomori Vault", "Petrified Hamlet"})
NEW_ARTIFACTS = frozenset({
    "Mirage Mirror", "Rings of Brighthearth", "Smothering Tithe",  # Tithe removed from artifact classification below
    "Staff of Compleation", "The One Ring", "Throne of Eldraine", "Mind Stone",
})
NEW_ARTIFACTS -= {"Smothering Tithe"}
# Spells the goldfish is allowed to cast as real battlefield permanents.
PERMANENT_COSTS = {
    "Blind Obedience": (1,1,0), "Mirage Mirror": (3,0,0),
    "Rings of Brighthearth": (3,0,0), "Smothering Tithe": (3,1,0),
    "Staff of Compleation": (3,0,0), "The One Ring": (4,0,0),
    "Throne of Eldraine": (5,0,0), "Mind Stone": (2,0,0),
}
# Sorcery speed spells with modeled effects are NOT inserted into COSTS:
# legacy default would incorrectly put a sorcery onto the battlefield.
BATTLEFRONT_COST = (3,1,0)
# Oracle {X} counts as 0 when Battlefront checks mana value.
# These are the noncreature/nonland permanents with costs <=3.
ELIGIBLE_BATTLEFRONT = {
    "Arcane Signet", "Basalt Monolith", "Blind Obedience", "Chrome Mox",
    "Cursed Totem", "Deafening Silence", "Defense Grid", "Disruptor Flute",
    "Fellwar Stone", "Gleaming Splendor", "Grim Monolith", "Jeweled Amulet",
    "Lion's Eye Diamond", "Lotus Petal", "Manifold Key", "Mind Stone",
    "Mirage Mirror", "Moonsilver Key", "Mox Diamond", "Mox Opal",
    "Paladin Class", "Portable Hole", "Prismatic Lens", "Rings of Brighthearth",
    "Sol Ring", "Static Prison", "Staff of Compleation", "Tezzeret, Cruel Captain",
    "The Mind Stone", "Thorn of Amethyst", "Touch the Spirit Realm",
    "Trinisphere", "Vexing Bauble", "Void Mirror", "Voltaic Key",
}
# These two are eligible at MV0, but Battlefront puts them in with X=0.
ELIGIBLE_BATTLEFRONT.add("Everflowing Chalice")
# Verify individually against installed costs, not just a hard-coded count.

def load_deck():
    cards = []
    commander = None
    for row in DECK_FILE.read_text(encoding="utf8").splitlines():
        if not row.strip():
            continue
        n, name = row.split(" ", 1)
        if name == d.COMMANDER:
            assert int(n) == 1
            commander = name
        else:
            cards.extend([name] * int(n))
    assert commander == d.COMMANDER, commander
    assert len(cards) == 99, len(cards)
    assert len(set(cards)) == 87, len(set(cards))
    assert all(cards.count(c) == 1 for c in CREATURES)
    assert cards.count("Plains") == 13
    return tuple(cards)

BASE_DECK = load_deck()
d.DECK = list(BASE_DECK)
# Disable old Boonweaver 'all creatures in library' gate, hard-mulligan penalty,
# LED hand-contamination restriction and forced library-repair target.
# This test measures CAST availability, not whether the new flicker combo wins.
d.COMBO_CREATURES = frozenset()
d.AURAS = frozenset()
d.chrome_mox_allowed = lambda card: card in WHITE_IMPRINTS
d.LANDS = frozenset(set(d.LANDS) | NEW_LANDS)
d.COSTS.update(PERMANENT_COSTS)
# Only battlefield permanents count toward Metalcraft.
_artifact_original = d.is_artifact_perm
def is_artifact_perm(card):
    return card in NEW_ARTIFACTS or _artifact_original(card)
d.is_artifact_perm = is_artifact_perm
# Need exactly 99 cards registered in cache identities, including creature pitches.
for card in set(BASE_DECK) | {"United Battlefront"}:
    if card not in d.CARD_ID:
        idx = max(d.CARD_ID.values(), default=-1)+1
        d.CARD_ID[card] = idx
        d.ID_CARD[idx] = card

d.RAMP_PROTECTED = frozenset(set(d.RAMP_PROTECTED) | {
    "The One Ring", "Throne of Eldraine", "Staff of Compleation",
    "Rings of Brighthearth", "Mirage Mirror", "Smothering Tithe",
})
d.MOONSILVER_MANA_ARTIFACTS = frozenset(set(d.MOONSILVER_MANA_ARTIFACTS) | {"Throne of Eldraine", "Staff of Compleation"})

# Correct Thorn: Dack is a creature and is NOT taxed by Thorn of Amethyst.
# Original v0.77's can_cast_dack added one generic despite the creature type.
_previous_can_cast = d.can_cast_dack
def can_cast_dack(s):
    if any(p.name == "Thorn of Amethyst" for p in s.battlefield):
        s = replace(s, battlefield=tuple(p for p in s.battlefield if p.name != "Thorn of Amethyst"))
    return _previous_can_cast(s)
d.can_cast_dack = can_cast_dack

# Correct Thorn: every NONCREATURE spell costs one more, including artifacts.
# Legacy _cast_actions_ranked applies Thorn only when "not art".
# Temporarily add {1} to artifact cost metadata only while legacy cast runs.
_previous_cast = d.cast_actions
def _legacy_cast_thorn_correct(s):
    if not any(p.name == "Thorn of Amethyst" for p in s.battlefield):
        return _previous_cast(s)
    changed = {}
    try:
        for name, (g,w,cc) in tuple(d.COSTS.items()):
            if is_artifact_perm(name):
                changed[name] = (g,w,cc)
                d.COSTS[name] = (g+1,w,cc)
        return _previous_cast(s)
    finally:
        d.COSTS.update(changed)

# Register actual land output (these 4 lands are not in the legacy tap table).
_original_tap = d.tap_mana_actions
def tap_mana_actions(s):
    out = list(_original_tap(s))
    for i,p in enumerate(s.battlefield):
        if p.tapped:
            continue
        n = d.effective_name(p)
        if n in NEW_LANDS:
            bf = list(s.battlefield)
            bf[i] = replace(p,tapped=True)
            out.append(replace(s,battlefield=tuple(bf),c=s.c+1))
        elif n == "Throne of Eldraine":
            bf = list(s.battlefield); bf[i] = replace(p,tapped=True)
            # The four white mana is restricted to casting monowhite spells.
            # For this phase it is only used to pay for Dack.
            out.append(replace(s,battlefield=tuple(bf),
                               restricted_dack_white=s.restricted_dack_white+4))
        elif n == "Staff of Compleation":
            bf = list(s.battlefield); bf[i] = replace(p,tapped=True)
            # Pay 2 life, T: add one mana of any color. Life excluded from T1-T3.
            out.append(replace(s,battlefield=tuple(bf),w=s.w+1))
    return d._dedupe(out) if hasattr(d,"_dedupe") else engine._dedupe(out)
d.tap_mana_actions = tap_mana_actions

# Draw/untap engine actions. Card draws use the actual library order.
# Do not model the later expensive Mind Stone harness activation in T1-3.
_original_special = d.special_actions
def special_actions(s):
    out = list(_original_special(s))
    for i,p in enumerate(s.battlefield):
        if p.tapped:
            continue
        n=d.effective_name(p)
        if n=="The One Ring":
            bf=list(s.battlefield)
            burden=p.counters+1
            bf[i]=replace(p,tapped=True,counters=burden)
            out.append(d.draw(replace(s,battlefield=tuple(bf)),burden))
        elif n=="Staff of Compleation":
            bf=list(s.battlefield);bf[i]=replace(p,tapped=True)
            out.append(d.draw(replace(s,battlefield=tuple(bf)),1))
        elif n=="Throne of Eldraine":
            # Cost is 3 mana of the chosen color, NOT its own restricted 4W.
            for paid in d.pay_options(s,3,0,0):
                used=(s.w-paid.w)+(s.any-paid.any)
                if used!=3: continue
                bf=list(paid.battlefield);bf[i]=replace(bf[i],tapped=True)
                out.append(d.draw(replace(paid,battlefield=tuple(bf)),2))
    # Rings + Basalt: pay {3} to untap Basalt, copy for {2}; tap
    # Basalt between the two untap resolutions. Requires {2} external
    # resources before starting, but then produces unlimited colorless.
    if (s.c < 12 and
        any(d.effective_name(p)=="Rings of Brighthearth" for p in s.battlefield)
        and any(d.effective_name(p)=="Basalt Monolith" and not p.tapped for p in s.battlefield)):
        for paid in d.pay_options(s,2):
            # Cap the infinite-colorless representation at 12C, avoiding
            # arbitrarily many distinct mana-pool states in bounded search.
            out.append(replace(paid,c=12))
    # Mirage Mirror copying a nonlegendary mana source until end of turn.
    for i,p in enumerate(s.battlefield):
        if p.name!="Mirage Mirror" or p.aux or p.tapped:
            continue
        for ti,t in enumerate(s.battlefield):
            if i==ti:continue
            target=d.effective_name(t)
            if target not in {"Ancient Tomb","City of Traitors","Crystal Vein",
                              "Sol Ring","Mana Vault","Grim Monolith","Basalt Monolith",
                              "Arcane Signet","Fellwar Stone","Mox Diamond",
                              "Mind Stone"}:
                continue
            for paid in d.pay_options(s,2):
                bf=list(paid.battlefield)
                bf[i]=replace(bf[i],aux="COPY:"+target)
                out.append(replace(paid,battlefield=tuple(bf)))
    return engine._dedupe(out)
d.special_actions=special_actions

_old_untap = d.untap_and_begin
def untap_and_begin(s):
    s = _old_untap(s)
    # Mirror's copy effect expires at end of previous turn; don't grant
    # permanent copied mana production on the next turn.
    return replace(s,battlefield=tuple(replace(p,aux="") if p.name=="Mirage Mirror" and
        p.aux.startswith("COPY:") else p for p in s.battlefield))
d.untap_and_begin=untap_and_begin

# Tithe's opponent-tax payments cannot be inferred from a goldfish.
# Conservative early-deployment baseline: zero guaranteed Treasures from Tithe.
# The later multiplayer phase will evaluate explicit opponent-payment scenarios.

def _front_hit(s,card):
    """Resolve Battlefront putting a card onto battlefield without casting."""
    if card=="Chrome Mox":
        outputs=[]
        for imprint in sorted(set(s.hand) & WHITE_IMPRINTS):
            hand=list(s.hand);hand.remove(imprint)
            bf=d.artifact_enters_bf(s.battlefield,d.Perm(card,False,0,s.turn))
            outputs.append(replace(s,hand=d.sort_hand(hand),exile=s.exile+(imprint,),battlefield=bf))
        # Without a white imprint it is a zero-mana artifact, not a white source.
        if outputs:return outputs
    if card=="Mox Diamond":
        outputs=[]
        for land in sorted(set(s.hand)&set(d.LANDS)):
            hand=list(s.hand);hand.remove(land)
            bf=d.artifact_enters_bf(s.battlefield,d.Perm(card,False,0,s.turn))
            outputs.append(replace(s,hand=d.sort_hand(hand),grave=s.grave+(land,),battlefield=bf))
        return outputs
    bf=d.artifact_enters_bf(s.battlefield,d.Perm(card,False,0,s.turn,
                       loyalty=4 if card=="Tezzeret, Cruel Captain" else 0))
    return [replace(s,battlefield=bf)]

def battlefront_actions(s):
    if "United Battlefront" not in s.hand:
        return []
    if not d.stax_allows(s,"United Battlefront",is_artifact=False):
        return []
    cost_g,cost_w,_ = BATTLEFRONT_COST
    if any(p.name=="Thorn of Amethyst" for p in s.battlefield):
        cost_g+=1
    if any(p.name=="Trinisphere" for p in s.battlefield):
        cost_g=max(cost_g,3-cost_w)
    results=[]
    for paid in d.pay_options(s,cost_g,cost_w):
        if not d.payment_stax_ok(s,paid):continue
        hand=list(paid.hand); hand.remove("United Battlefront")
        base=replace(paid,hand=d.sort_hand(hand),grave=paid.grave+("United Battlefront",),
                     spells=paid.spells+1,nonartifact_spells=paid.nonartifact_spells+1,
                     noncreature_spells=paid.noncreature_spells+1)
        window=base.library[:7]
        tail=base.library[7:]
        hit_ids=[j for j,name in enumerate(window) if name in ELIGIBLE_BATTLEFRONT]
        # All 0/1/2 candidate choices, including putting nothing into play.
        for k in range(min(2,len(hit_ids))+1):
            for selected in combinations(hit_ids,k):
                chosen=[window[j] for j in selected]
                rest=[window[j] for j in range(len(window)) if j not in selected]
                # Opponent doesn't control bottom order; deterministic shuffle
                # is intentionally keyed from this library state.
                rng=random.Random(d._stable_seed(tuple(rest)+tuple(tail),0xB477))
                rng.shuffle(rest)
                states=[replace(base,library=tuple(tail)+tuple(rest))]
                for name in chosen:
                    states=[next_state for z in states for next_state in _front_hit(z,name)]
                results.extend(states)
    return engine._dedupe(results)

def cast_actions(s):
    return engine._dedupe(_legacy_cast_thorn_correct(s)+battlefront_actions(s))
d.cast_actions = cast_actions

def build_deck(variant="baseline"):
    cards=list(BASE_DECK)
    if variant=="baseline":
        pass
    elif variant=="battlefront_over_prismatic":
        cards[cards.index("Prismatic Lens")]="United Battlefront"
    elif variant=="battlefront_over_amulet":
        cards[cards.index("Jeweled Amulet")]="United Battlefront"
    else:
        raise ValueError(variant)
    assert len(cards)==99
    return tuple(cards)

def install(variant="baseline"):
    deck=build_deck(variant)
    engine.set_deck(deck)
    return deck

def selftest():
    assert len(BASE_DECK)==99
    assert "Radiant Solar" not in WHITE_IMPRINTS
    assert all(c in WHITE_IMPRINTS for c in CREATURES if c!="Radiant Solar")
    assert all(c in WHITE_IMPRINTS for c in MDFC)
    assert not d.chrome_mox_allowed("Ancient Den")
    assert not d.chrome_mox_allowed("The One Ring")
    assert not d.chrome_mox_allowed("Radiant Solar")
    assert all(d.chrome_mox_allowed(c) for c in WHITE_IMPRINTS)
    assert BATTLEFRONT_COST==(3,1,0)
    assert "The One Ring" not in ELIGIBLE_BATTLEFRONT
    assert "Throne of Eldraine" not in ELIGIBLE_BATTLEFRONT
    assert all(c not in ELIGIBLE_BATTLEFRONT for c in CREATURES)
    assert d.is_artifact_perm("The One Ring")
    assert not d.is_artifact_perm("Smothering Tithe")
    assert all(c in d.CARD_ID for c in BASE_DECK)
    assert all(c in d.LANDS for c in NEW_LANDS)
    # Chrome Mox can imprint flicker creatures, but not Radiant Solar.
    ss=d.State(1,("Chrome Mox","Felidar Guardian","Radiant Solar"),())
    casts=[q for q in d.cast_actions(ss) if any(x.name=="Chrome Mox" for x in q.battlefield)]
    assert any("Felidar Guardian" in q.exile for q in casts)
    assert all("Radiant Solar" not in q.exile for q in casts)
    # Thorn taxes artifact spells, including Sol Ring, by one generic mana.
    ss=d.State(1,("Sol Ring",),(),battlefield=(d.Perm("Thorn of Amethyst"),),c=1)
    assert not any(any(x.name=="Sol Ring" for x in q.battlefield) for q in d.cast_actions(ss))
    # Rings + Basalt cannot supply colorless without two extra mana.
    ss=d.State(1,(),(),battlefield=(d.Perm("Rings of Brighthearth"),d.Perm("Basalt Monolith")))
    assert not any(q.c==12 for q in d.special_actions(ss))
    ss=replace(ss,c=2)
    assert any(q.c==12 for q in d.special_actions(ss))
    # Creature commander must not be taxed by Thorn.
    s=d.State(1,(),(),battlefield=(d.Perm("Thorn of Amethyst"),),w=2,c=4)
    assert d.can_cast_dack(s)
    # Throne's mana can cast Dack but cannot be converted into ordinary W.
    s=d.State(2,(),(),battlefield=(d.Perm("Throne of Eldraine"),),c=2)
    x=[q for q in d.tap_mana_actions(s) if q.restricted_dack_white==4]
    assert x and all(q.w==0 for q in x)
    # Staff is a zero-mana activation with a life payment, not a {1} tax.
    s=d.State(2,(),(),battlefield=(d.Perm("Staff of Compleation"),))
    assert any(q.w==1 for q in d.tap_mana_actions(s))
    # The One Ring places burden counter BEFORE drawing.
    s=d.State(2,(),("Plains","Sol Ring"),battlefield=(d.Perm("The One Ring"),))
    q=[z for z in d.special_actions(s) if z.hand==("Plains",)]
    assert q and any(z.battlefield[0].counters==1 for z in q)
    # Battlefront 3W can hit two eligible permanents directly into play.
    s=d.State(2,("United Battlefront",),
        ("Sol Ring","Arcane Signet","Plains","Felidar Guardian","The One Ring","Prismatic Lens","Blind Obedience"),
        w=1,c=3)
    targets=[z for z in d.battlefront_actions(s)] if hasattr(d,"battlefront_actions") else battlefront_actions(s)
    assert targets and any({"Sol Ring","Arcane Signet"} <=
        {p.name for p in z.battlefield} for z in targets)
    assert any("Felidar Guardian" in z.library for z in targets)
    return True

if __name__=="__main__":
    import argparse
    a=argparse.ArgumentParser()
    a.add_argument("--audit",action="store_true")
    a.add_argument("--variant",default="baseline")
    opts=a.parse_args()
    install(opts.variant)
    assert selftest()
    print("DACK_FLICKER_V078_FOCUSED_AUDIT_PASS",opts.variant,flush=True)
