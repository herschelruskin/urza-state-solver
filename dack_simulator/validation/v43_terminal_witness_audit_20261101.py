#!/usr/bin/env python3
"""Read-only frozen-v43 physical goldfish witness and colored-mana legality audit.

Use new development-only 162700..162723 physical source deals. Capture actual
terminal beam states; never infer a line from predicted values alone. Recording
winning states is not a proof that beam finds all feasible unsuccessful lines.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import json,sys,time
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as v43
import dack_boonweaver_aura_exile_guard_20261029 as guard
ref=v43.ref
def state_summary(s):
    return {"turn":s.turn,"white":s.w,"colorless":s.c,"any":s.any,
        "restricted_legend":s.restricted_legend,
        "restricted_artifact":s.restricted_artifact,
        "restricted_dack_white":s.restricted_dack_white,
        "hand":list(s.hand),"library_combo":[x for x in ref.d.COMBO_CREATURES if x in s.library],
        "battlefield":[{"card":p.name,"tapped":p.tapped,"copy":p.aux} for p in s.battlefield],
        "exiled_protected":[x for x in s.exile if x in guard.PROTECTED_EXILE],
        "available_library_cards":len(s.library),
        "valid_dack_cast":bool(ref.d.can_cast_dack(s))}
def main():
    v43.audit()
    d=ref.d
    lib=tuple(sorted(guard.CORE_CREATURES))
    assert d.can_cast_dack(d.State(1,(),lib,w=2,c=4))
    assert not d.can_cast_dack(d.State(1,(),lib,w=1,c=5))
    assert not d.can_cast_dack(d.State(1,(),lib,w=0,c=6,restricted_legend=2))
    assert d.can_cast_dack(d.State(1,(),lib,w=0,c=4,any=2))
    assert not d.can_cast_dack(d.State(1,(),lib[:-1],w=2,c=4))
    assert not d.can_cast_dack(d.State(1,(),lib,w=2,c=4,exile=("Gleaming Splendor",)))
    assert not d.can_cast_dack(d.State(1,(),lib,w=2,c=4,exile=("Lunarch Mantle",)))
    assert d.can_cast_dack(d.State(1,("Lunarch Mantle",),lib,w=2,c=4))
    print("FROZEN_ENGINE_WHITE_AND_COMBO_GATE_REGRESSION_PASS",flush=True)
    orig=d.search_turn_frontier_many
    rows=[];t0=time.monotonic()
    for gid in range(162700,162724):
        witnesses=[]
        def recorder(states,beam=160,depth=24):
            wins,survivors=orig(states,beam=beam,depth=depth)
            for w in wins[:2]:
                assert d.can_cast_dack(w),(gid,w)
                assert guard.CORE_CREATURES.issubset(set(w.library)),(gid,"missing creature")
                assert not guard.PROTECTED_EXILE.intersection(w.exile),(gid,"exiled protected")
                witnesses.append(state_summary(w))
            return wins,survivors
        d.search_turn_frontier_many=recorder
        try:
            out=ref.game("one_key_34",gid)
        finally:
            d.search_turn_frontier_many=orig
        assert int(out["win_turn"] or 0) in (0,1,2,3)
        assert (len(witnesses)>0)==bool(out["win_turn"]),(gid,"terminal witness discrepancy")
        hist=out["history"]
        rows.append({"gid":gid,"seat":out["seat"],"win_turn":out["win_turn"],
            "first_seven":hist[0]["seven"],"first_seven_predictedQ":hist[0]["raw"],
            "first_seven_kept":hist[0]["kept"],"first_seven_threshold":hist[0]["threshold"],
            "final_keep_n":out["keep_n"],"final_hand":out["hand"],
            "first3":out["first3"],"witness_states":witnesses[:3],
            "frontier_events":out["frontier_events"]})
        if (gid-162700+1)%8==0:
            print("FROZEN_ENGINE_WITNESS_PROGRESS",gid,"T1",sum(r["win_turn"]==1 for r in rows),
              "byT2",sum(r["win_turn"] in (1,2) for r in rows),flush=True)
    result={"schema":"dack_v43_readonly_physical_winning_state_witness_audit_v1",
       "status":"PASS","development_ids":[162700,162723],
       "N_independent_source_deals":len(rows),
       "no_engine_changes":True,"not_a_full_game_policy_comparison":True,
       "not_acceptance":True,"strict_beam160":True,
       "terminal_witness_resource_and_combo_gate_rechecked":True,
       "wins":{"T1":sum(r["win_turn"]==1 for r in rows),
         "by_T2":sum(r["win_turn"] in (1,2) for r in rows),
         "by_T3":sum(r["win_turn"] in (1,2,3) for r in rows)},
       "elapsed":time.monotonic()-t0,"rows":rows}
    dest=ROOT/"benchmark_results/v43_readonly_real_terminal_state_witness_dev_162700_N24.json"
    dest.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("DACK_V43_TERMINAL_PHYSICAL_WITNESS_AUDIT_PASS",json.dumps(result["wins"]),flush=True)
if __name__=="__main__":main()
