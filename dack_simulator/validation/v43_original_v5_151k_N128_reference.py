#!/usr/bin/env python3
"""Match real ORIGINAL v5 on N128 of the newly completed v43 151k cohort.

This cohort was already inspected in v43/v27 comparison, so adding the v5
reference is a *retrospective same-seed comparison*, NOT a pristine new
prospective acceptance test. Original v5 engine and full original keep
policy, strict gameplay beam160, canonical 99-slots, original stable dice.
"""
from __future__ import annotations
import argparse,hashlib,gzip,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v5_stable_chance_20261031 as teacher
SCHEMA="dack_v43_same_151k_original_v5_reference_N128_shard"
def run(start,out):
    if start not in range(151000,151128,16):
        raise ValueError("N128 retrospective reference = exactly eight 16-game shards")
    audit=teacher.audit()
    assert audit["status"]=="PASS"
    ref=teacher.reference
    assert ref.SPEC["beam"]==160 and len(ref.SLOTS)==99
    rows=[];t0=time.perf_counter()
    for gid in range(start,start+16):
        tt=time.perf_counter()
        r=ref.game("one_key_34",gid)
        assert r["win_turn"] in (0,1,2,3)
        rows.append({
          "game_id":gid,"seat":r["seat"],"turn":int(r["win_turn"]),
          "keep_n":r["keep_n"],"history":r["history"],
          "seconds":round(time.perf_counter()-tt,5),
        })
        print("DACK_V43_ORIGINAL_V5_REFERENCE_151K_GAME",gid,
              "turn",r["win_turn"],"keep",r["keep_n"],
              "elapsed",round(time.perf_counter()-t0,2),flush=True)
    report={
      "schema":SCHEMA,"status":"PASS","game_ids":[start,start+15],
      "physical_groups":16,"strict_99_beam160_original_rules":True,
      "original_v5_with_no_modifications":True,
      "already_inspected_151k_not_prospective":True,"rows":rows,
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(report,f,sort_keys=True)
    print("DACK_V43_ORIGINAL_V5_REFERENCE_N16_PASS",start,flush=True)
if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--start",type=int,required=True)
    a.add_argument("--out",required=True)
    z=a.parse_args();run(z.start,z.out)
