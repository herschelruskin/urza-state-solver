#!/usr/bin/env python3
"""Adversarial physical audit of fresh 169051 no-draw witness / actual turn0.
Do not assert whether the discrepancy is search failure or an unavoidable
drawn combo creature; print physical deck positions and demonstrate cause.
"""
from __future__ import annotations
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as v43
import dack_turn_aware_legal_mana_features_v48_20261101 as feat
ref=v43.ref
def main():
    v43.audit()
    gid=169051;deck=ref.SLOT_VARIANTS["one_key_34"]
    seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
    seat,orders=ref.stage_slots(seed)
    seven=tuple(deck[i] for i in orders[0][:7])
    unknown=tuple(deck[i] for i in orders[0][7:])
    combos=tuple(sorted(ref.d.COMBO_CREATURES))
    print("V48_DISCORDANT_PHYSICAL_OPENING",json.dumps({
       "gid":gid,"seat":seat,"seven":seven,"first_seven_unknown_top10":unknown[:10],
       "first2_combo_draw_flags":[x in combos for x in unknown[:2]],
       "combo_creatures":combos},sort_keys=True),flush=True)
    t0=time.perf_counter()
    x=feat.analyze(seven,unknown,seat,beam=32,depth=9)
    print("V48_DISCORDANT_NODRAW_WITNESS",json.dumps({
       "T1":x["mana_witness_T1_no_draw"],"T2":x["mana_witness_T2_no_draw"],
       "T2_witness":x.get("T2_witness"),
       "witness_seconds":time.perf_counter()-t0},sort_keys=True),flush=True)
    outcomes={}
    for beam in (160,384):
        ref.sim.reset_caches()
        ref.sim.root.install("one_key_34")
        ref.sim.m.set_trial_seed(seed)
        ref.d._WIN_CACHE.clear()
        orig=ref.d.search_turn_frontier_many
        trace=[]
        def wrapper(states,beam=160,depth=24):
            wins,rest=orig(states,beam=beam,depth=depth)
            trace.append({"turn":states[0].turn if states else None,
              "state_n":len(states),"wins":len(wins),"survivors":len(rest),
              "score_best":max((ref.d.score(s) for s in rest),default=None),
              "can_cast_survivors":sum(ref.d.can_cast_dack(s) for s in rest)})
            return wins,rest
        ref.d.search_turn_frontier_many=wrapper
        t1=time.perf_counter()
        try:turn=ref.d._win_turn_from_unknown_order(
            tuple(sorted(seven)),unknown,seat,beam=beam,max_turn=3)
        finally:ref.d.search_turn_frontier_many=orig
        outcomes[str(beam)]={"turn":turn,"trace":trace,"seconds":time.perf_counter()-t1}
        print("V48_DISCORDANT_PHYSICAL_BEAM",json.dumps({
             "beam":beam,**outcomes[str(beam)]},sort_keys=True),flush=True)
        if turn in (1,2):break
    print("DACK_V48_DISCORDANCE_CAUSE_AUDIT_DONE",json.dumps({
      "gid":gid,"first2_combo_draw_flags":[x in combos for x in unknown[:2]],
      "beams_tested":list(outcomes),
      "byT2_in_any_beam":any(0<int(v["turn"])<=2 for v in outcomes.values())},sort_keys=True),flush=True)
if __name__=="__main__":main()
