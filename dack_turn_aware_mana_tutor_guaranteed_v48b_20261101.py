#!/usr/bin/env python3
"""v48b: additionally permit *verified deterministic deck-search* actions.

This is NOT a future-draw tutor model. It only adds search-to-hand or
search-to-battlefield effects that are physically guaranteed because the
target exists in the user's known 99-card remaining multiset. Enlightened
Tutor's topdeck effect remains excluded pending explicit T2 draw tracking.

Every new successor is first produced by the real simulator and independently
checked for source, target zone and physical library-count provenance. A
negative remains bounded/unknown. No live v43 policy is installed.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import replace
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import dack_turn_aware_legal_mana_features_v48_20261101 as base
d=base.d;ref=base.ref
SCHEMA="dack_v48b_legally_searched_mana_futures_without_unseen_draws_v1"
TUTOR_SOURCES={"Expedition Map","Moonsilver Key","Urza's Cave","Tezzeret, Cruel Captain"}
def moved_from_deck(before,after,source):
    """Physical source verification independent of hidden library order."""
    lib0=Counter(before.library);lib1=Counter(after.library)
    removed=lib0-lib1;added=lib1-lib0
    if added or sum(removed.values())!=1:return None
    target=next(iter(removed))
    new_hand=Counter(after.hand)-Counter(before.hand)
    bf0=Counter(d.effective_name(p) for p in before.battlefield)
    bf1=Counter(d.effective_name(p) for p in after.battlefield)
    new_bf=bf1-bf0
    if source=="v03":
        # Exact existing d.v03_actions deck-search pathways.
        verified=(
          ("Moonsilver Key" in before.hand or any(p.name=="Moonsilver Key" for p in before.battlefield))
            and "Moonsilver Key" in (Counter(after.grave)-Counter(before.grave))
            and new_hand[target]>0
          or ("Expedition Map" in (Counter(after.grave)-Counter(before.grave))
            and any(p.name=="Expedition Map" for p in before.battlefield) and new_hand[target]>0)
          or (any(p.name=="Urza's Cave" for p in before.battlefield)
            and "Urza's Cave" in (Counter(after.grave)-Counter(before.grave)) and new_bf[target]>0)
          or (any(p.name=="Tezzeret, Cruel Captain" for p in before.battlefield)
            and any(p.name=="Tezzeret, Cruel Captain" and p.activated_turn==before.turn
                   for p in after.battlefield) and new_hand[target]>0))
    elif source=="saga":
        verified=(any(p.name=="Urza's Saga" and p.aux=="SAGA3" for p in before.battlefield)
                 and new_bf[target]>0)
    else:verified=False
    if not verified:return None
    # Checked against actual simulated outcome, never hand-constructed mana.
    assert lib0[target]>=1
    assert len(before.library)==len(after.library)+1
    return target
def augmented_actions(s):
    yield from base._actions(s)
    # In the installed rules some activations depend on the actual top card.
    # Only the specifically source-verified tutor branch enters the frontier.
    for source,fn in (("v03",d.v03_actions),("saga",d.saga_tutor_actions)):
        for q in fn(s):
            if q.library==s.library:continue
            t=moved_from_deck(s,q,source)
            if t is not None:
                # Search effects legally shuffle the remaining deck. Canonical
                # order is allowed because there are NO FUTURE DRAWS in this
                # witness; no 'known top' value may leak into mana feasibility.
                yield replace(q,library=tuple(sorted(q.library)))
def analyze(seven,unknown,seat,keep_n=7,stage=0,bottom=(),beam=32,depth=9):
    seven=tuple(seven);unknown=tuple(unknown);bottom=tuple(bottom)
    assert len(seven)==7 and len(unknown)==92 and len(bottom)==7-keep_n
    hand=tuple(sorted((Counter(seven)-Counter(bottom)).elements()))
    library=tuple(sorted(unknown))+tuple(sorted(bottom))
    assert Counter(hand)+Counter(library)==Counter(ref.SLOT_VARIANTS["one_key_34"].values())
    assert ref.sim.STAGES[stage]==keep_n
    original=base._actions
    base._actions=augmented_actions
    try:
        pre=d._pregame_states(d.State(1,hand,library),seat)
        a=base.search_main(pre,beam=beam,depth=depth)
        second=[]
        for s in a["pass_states"]:second+=base._advance_turn_no_draw(s)
        if not second:raise AssertionError("no viable turn2 states")
        b=base.search_main(second,beam=beam,depth=depth)
    finally:
        base._actions=original
    w1=a["cast_witness"];w2=b["cast_witness"]
    for w in (w1,w2):
        if w is None:continue
        assert d.can_cast_dack(w)
        # No unknown card can materialize in hand or on battlefield except
        # through a verified tutor action, and the library never increases.
        assert not (Counter(w.library)-Counter(library))
        assert len(w.library)<=len(library)
    return {"schema":SCHEMA,"seat":seat,"stage":stage,"keep_n":keep_n,
      "hand":list(hand),"no_future_draw":True,
      "T1_tutor_legal_no_draw_witness":bool(w1),
      "T2_tutor_legal_no_draw_witness":bool(w1 or w2),
      "T1_tutor_count_in_witness":len(library)-len(w1.library) if w1 else None,
      "T2_tutor_count_in_witness":len(library)-len(w2.library) if w2 else None,
      "T1":{"white_max":a["max_white"],
       "generic_after_WW_max":a["max_generic_after_WW"],
       "total_commander_usable_max":a["max_commander_usable"],
       "states":a["expanded_states"],"actions":a["considered_actions"]},
      "T2":{"white_max":b["max_white"],
       "generic_after_WW_max":b["max_generic_after_WW"],
       "total_commander_usable_max":b["max_commander_usable"],
       "states":b["expanded_states"],"actions":b["considered_actions"]},
      "witness_has_no_known_topdeck_tutor_draw":True,
      "bounded_search_negative_not_impossibility":True,"beam":beam,"depth":depth}
def smoke():
    base.v43.audit()
    deck=list(ref.SLOT_VARIANTS["one_key_34"].values())
    cases=[
     ["Plains","Ancient Tomb","Moonsilver Key","Sol Ring","Chrome Mox","Silence","Mana Vault"],
     ["Plains","Plains","City of Traitors","Expedition Map","Mox Diamond","Grim Monolith","Sol Ring"],
     ["Cavern of Souls","Mana Vault","Sol Ring","Moonsilver Key","The Mycosynth Gardens","Silence","Plains"],
     ["Gemstone Caverns","Ancient Tomb","Moonsilver Key","Mox Diamond","Plains","Plains","Sol Ring"],
    ]
    results=[]
    for seat,hand in enumerate(cases):
        assert not Counter(hand)-Counter(deck)
        unknown=deck.copy()
        for c in hand:unknown.remove(c)
        t0=time.perf_counter()
        a=analyze(hand,unknown,seat)
        b=analyze(hand,list(reversed(unknown)),seat)
        for k in ("T1_tutor_legal_no_draw_witness","T2_tutor_legal_no_draw_witness",
                  "T1_tutor_count_in_witness","T2_tutor_count_in_witness","T1","T2"):
            assert a[k]==b[k],(seat,k,a[k],b[k])
        results.append({"seat":seat,
           "T1":a["T1_tutor_legal_no_draw_witness"],
           "T2":a["T2_tutor_legal_no_draw_witness"],
           "T1_tutor_count":a["T1_tutor_count_in_witness"],
           "T2_tutor_count":a["T2_tutor_count_in_witness"],
           "seconds":round(time.perf_counter()-t0,3)})
    # Source-verified tutor to hand must be accepted; unknown-top straight
    # draw must NOT masquerade as a tutor via a changed deck size.
    rem=["Plains","Mana Vault","Sol Ring"]
    s=d.State(1,(),tuple(rem),battlefield=(d.Perm("Moonsilver Key"),),c=1)
    outs=[q for q in d.v03_actions(s) if moved_from_deck(s,q,"v03") is not None]
    assert outs,"actual key fetched a legal deck target"
    draw=d.draw(s,1)
    assert moved_from_deck(s,draw,"v03") is None
    assert moved_from_deck(s,draw,"saga") is None
    return {"status":"PASS","cases":results,
       "hidden92_reversal_invariant":True,
       "source_tutor_action_verified":True,"random_top_deck_draw_rejected":True,
       "no_model_or_policy_retrained":True}
if __name__=="__main__":
    print("DACK_V48B_TUTOR_MANA_SMOKE_PASS",json.dumps(smoke(),sort_keys=True),flush=True)
