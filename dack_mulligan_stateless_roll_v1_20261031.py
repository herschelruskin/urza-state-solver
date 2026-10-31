#!/usr/bin/env python3
"""Search-order-invariant keyed random outcomes for the Bucknard/Component dice.

The inherited model hashes repr(d.key(s)) to produce each simulated die roll.
That key contains library_token, an *ordinal counter assigned on first visit*.
A harmless change in beam exploration order can therefore alter future dice
for IDENTICAL card state, making early-win searches change sampled utility.

This patch keys chance outcomes to the complete canonical game state, not to
unstable cache intern IDs or number of prior search branches.

This is still a deterministic pseudorandom oracle per state and game seed,
NOT a hidden-information-perfect Monte Carlo policy or opponent simulation.
It changes historical seeded die sequences; always version new runs.
"""
from __future__ import annotations
from dataclasses import fields
import hashlib
import json

import dack_mulligan_terminal_witness_v1_20261031 as witness

d=witness.d
buck=witness.bounded.validated.sim.m
# The canonical Bucknard stack module and general 2026 dice use this module.
import dack_v077_full_deck_accel as original_buck

assert original_buck is buck
RULES_VERSION="dack_search_order_invariant_dice_v1"
PREVIOUS_ROLL=buck._roll
STATE_FIELDS=tuple(field.name for field in fields(d.State))

def canonical_state_for_chance(s):
    out=[]
    for name in STATE_FIELDS:
        value=getattr(s,name)
        if name=="hand":
            value=tuple(sorted(value))
        elif name=="battlefield":
            value=tuple(sorted(
                (p.name,p.tapped,p.counters,p.entered_turn,p.aux,
                 p.loyalty,p.activated_turn) for p in value))
        elif name in {"grave","exile"}:
            value=tuple(sorted(value))
        # Library sequence remains EXACT, not sorted: topdeck order matters.
        # Saga age and all resource fields remain explicitly represented.
        out.append((name,value))
    return tuple(out)

def stable_roll(s,card,sides,salt=0):
    sides=int(sides)
    if sides<1:
        raise ValueError("die requires at least one face")
    payload=json.dumps(
        (int(buck.TRIAL_SEED),str(card),sides,int(salt),
         canonical_state_for_chance(s)),
        ensure_ascii=False,separators=(",",":"),sort_keys=False
    ).encode("utf8")
    digest=hashlib.sha256(payload).digest()
    return 1+(int.from_bytes(digest[:8],"big")%sides)

def install():
    buck._roll=stable_roll
    return buck._roll

def uninstall():
    buck._roll=PREVIOUS_ROLL
    return buck._roll

def selftest():
    old_seed=buck.TRIAL_SEED
    try:
        buck.set_trial_seed(10103)
        s=d.State(1,("Sol Ring",),
                  ("Boonweaver Giant","Preston, the Vanisher","Roaming Throne"),
                  battlefield=(d.Perm("Bucknard's Everfull Purse"),
                               d.Perm("Voltaic Key")),
                  c=3)
        v=stable_roll(s,"Bucknard's Everfull Purse",4,1)
        assert 1<=v<=4
        # Intern unrelated libraries before, after, and between roll calls.
        d.library_token(("Candelabra of Tawnos","Sol Ring"))
        d.library_token(("Sol Ring","Candelabra of Tawnos"))
        assert v==stable_roll(s,"Bucknard's Everfull Purse",4,1)
        rev=type(s)(**{**{name:getattr(s,name) for name in STATE_FIELDS},
                        "battlefield":tuple(reversed(s.battlefield))})
        assert canonical_state_for_chance(s)==canonical_state_for_chance(rev)
        assert stable_roll(s,"Bucknard's Everfull Purse",4,1)==stable_roll(
            rev,"Bucknard's Everfull Purse",4,1)
        assert len({stable_roll(s,"Bucknard's Everfull Purse",4,offset)
                    for offset in range(50)})>1
        install()
        assert buck._roll is stable_roll
        uninstall()
        assert buck._roll is PREVIOUS_ROLL
    finally:
        buck.set_trial_seed(old_seed)
    return {"status":"PASS","rules_version":RULES_VERSION,
            "chance_key":"full_canonical_state_and_seed",
            "does_not_depend_on_library_intern_sequence":True,
            "historical_die_rolls_changed":True}

if __name__=="__main__":
    print(json.dumps(selftest(),indent=2))
