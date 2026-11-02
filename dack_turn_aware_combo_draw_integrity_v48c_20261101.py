#!/usr/bin/env python3
"""v48c explicit factorization of early deployment: physically reached mana,
known combo-library integrity and *unmodified natural-draw* contamination risk.

No probability is asserted for games with tutors/scry/draw/rearrangements.
These analytic features complement, never replace, strict real simulation.
Never use unknown draw ORDER, only known 92-card multiset and London bottoms.
"""
from __future__ import annotations
from collections import Counter
import json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import dack_turn_aware_legal_mana_features_v48_20261101 as base
d=base.d
SCHEMA="dack_v48c_factorized_mana_combo_integrity_unmodified_draw_risk_v1"
def expose(seven,unknown,bottom=(),keep_n=7):
    seven=tuple(seven);unknown=tuple(unknown);bottom=tuple(bottom)
    assert len(seven)==7 and len(unknown)==92 and len(bottom)==7-keep_n
    hand=Counter(seven)-Counter(bottom)
    assert sum(hand.values())==keep_n
    core=set(d.COMBO_CREATURES)
    in_hand=sum(hand[c] for c in core)
    in_bottom=sum(Counter(bottom)[c] for c in core)
    in_unknown=sum(Counter(unknown)[c] for c in core)
    assert in_hand+in_bottom+in_unknown==len(core)==3
    no_card_draw_contamination_initially=(in_hand==0)
    def survival(n):
        # Exactly n *natural and unmanipulated* draws from the first unknown92.
        # If a required creature is already in hand, the un-repaired combo
        # gate is broken at time zero even if every future natural draw is safe.
        if not no_card_draw_contamination_initially:return 0.
        v=1.
        for i in range(n):
            v*=(92-in_unknown-i)/(92-i)
        return v
    return {"schema":SCHEMA,"keep_n":keep_n,"creatures_in_initial_hand":in_hand,
       "creatures_put_on_bottom":in_bottom,"creatures_in_initial_unknown92":in_unknown,
       "no_repair_combo_gate_initially_intact":no_card_draw_contamination_initially,
       "unmodified_one_natural_draw_combo_survival":survival(1),
       "unmodified_two_natural_draw_combo_survival":survival(2),
       "unmodified_two_draw_combo_brick_risk":1-survival(2),
       "not_applicable_after_topdeck_tutoring_scry_other_draw_spells":True,
       "no_future_order_seen":True}
def smoke():
    base.v43.audit()
    deck=list(base.ref.SLOT_VARIANTS["one_key_34"].values())
    seven=["Plains","Ancient Tomb","Sol Ring","Chrome Mox","Silence","Mox Diamond","Enlightened Tutor"]
    rem=deck.copy()
    for x in seven:rem.remove(x)
    a=expose(seven,rem)
    b=expose(seven,list(reversed(rem)))
    assert a==b
    assert a["creatures_in_initial_hand"]==0 and a["creatures_in_initial_unknown92"]==3
    assert abs(a["unmodified_two_natural_draw_combo_survival"]-((89*88)/(92*91)))<1e-12
    # The previous exact discordance was a natural T2 draw of Boonweaver.
    gid=169051
    seed=int(base.ref.SPEC["seed_base"])+gid*base.ref.SEED_STRIDE
    seat,orders=base.ref.stage_slots(seed)
    cards=base.ref.SLOT_VARIANTS["one_key_34"]
    seven=tuple(cards[k] for k in orders[0][:7])
    unknown=tuple(cards[k] for k in orders[0][7:])
    risk=expose(seven,unknown)
    assert unknown[1]=="Boonweaver Giant"
    assert risk["creatures_in_initial_unknown92"]==3
    assert risk["unmodified_two_draw_combo_brick_risk"]>0
    # Legal London bottom to protected library genuinely changes probability.
    c="Boonweaver Giant"
    seven2=["Plains","Ancient Tomb","Sol Ring","Chrome Mox","Silence","Mox Diamond",c]
    rem2=deck.copy()
    for x in seven2:rem2.remove(x)
    bottomed=expose(seven2,rem2,bottom=(c,),keep_n=6)
    assert bottomed["creatures_put_on_bottom"]==1
    assert bottomed["creatures_in_initial_unknown92"]==2
    assert bottomed["no_repair_combo_gate_initially_intact"]
    assert bottomed["unmodified_two_natural_draw_combo_survival"]>((89*88)/(92*91))
    return {"status":"PASS","cases":4,
       "natural_T2_combo_brick_probability":a["unmodified_two_draw_combo_brick_risk"],
       "real_discordance_gid_169051_explained_by_T2_draw":True,
       "bottomed_combo_creature_protected_from_first_two_natural_draws":True,
       "library_order_invariance":True,
       "does_not_model_drawing_after_tutor_or_scry":True}
if __name__=="__main__":
    print("DACK_V48C_COMBO_INTEGRITY_SURVIVAL_SMOKE_PASS",
          json.dumps(smoke(),sort_keys=True),flush=True)
