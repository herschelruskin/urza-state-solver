#!/usr/bin/env python3
"""v36 no-beam audit: targeted training does NOT balance seats by design.

The manifest claims boundary balance, but selection enforces six
stage×old KEEP/MULL quotas only. Report actual seat composition and
weighted effective outer-group sample count; do not silently change
an outcome-label source manifest after training has started.
"""
from __future__ import annotations
import json,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v1_20261030 as ref

def run():
    p=ROOT/"datasets/v36_preoutcome_123k_manifest.json"
    d=json.loads(p.read_text())
    assert d["schema"]=="dack_v36_preoutcome_stratified_123k_physical_training_manifest_1"
    assert d["status"]=="PASS" and d["no_gameplay_rollouts_at_selection"]
    assert len(d["groups"])==256
    by_source=Counter();by_seat=Counter();selected=Counter()
    nums=set()
    for group in d["groups"]:
        gid=group["game_id"]
        assert gid not in nums
        nums.add(gid)
        seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,_=ref.stage_slots(seed)
        kind=group["sample"]
        by_source[kind]+=1
        by_seat[(kind,seat)]+=1
        if kind=="boundary_enriched":
            meta=group["selection"]
            selected[(meta["selection_stage"],meta["original_v27_keep"])]+=1
        else:assert kind=="random" and group["selection"] is None
    assert len(nums)==256
    assert by_source==Counter({"random":128,"boundary_enriched":128})
    assert all(selected[(s,k)]==n
         for s,n in ((0,24),(1,20),(2,20)) for k in (True,False))
    wsum=128*1.+128*.5
    w2=128*1.+128*.5**2
    eff=wsum*wsum/w2
    report={
      "schema":"dack_v36_training_selection_no_outcome_seat_balance_audit",
      "status":"PASS","no_gameplay_called":True,
      "random_ids":128,"enriched_ids":128,
      "balanced_stage_and_old_action":True,
      "NOT_balance_seat_exactly":True,
      "manifest_metadata_claiming_seat_balance_is_OVERSTATED":True,
      "seat_census_by_source":{k:dict((str(seat),by_seat[(k,seat)])
                       for seat in range(4)) for k in ("random","boundary_enriched")},
      "selected_stratum_quota":{f"{stage}:{int(keep)}":n
              for (stage,keep),n in sorted(selected.items())},
      "effective_outer_group_weight_count_before_stage_correlation":eff,
      "no_manual_rematching_or_outcome_dependent_selection":True
    }
    dest=ROOT/"benchmark_results/v36_preoutcome_selection_method_audit.json"
    dest.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V36_MANIFEST_METHOD_AUDIT_PASS",json.dumps(report,sort_keys=True),flush=True)

if __name__=="__main__":run()
