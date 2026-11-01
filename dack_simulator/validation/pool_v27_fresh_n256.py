#!/usr/bin/env python3
"""Read-only completed 98k v27 prospective T2 optimization comparison."""
import glob,gzip,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from dack_simulator.validation.pool_v26_fresh_n256 import measure,compare
POLICIES=("v5","v26_expanded_keep_DP","v27_T2_only_DP")
def main():
    files=sorted(glob.glob("collected/v27_98k_*.json.gz"))
    assert len(files)==64,("incomplete 98k test",len(files))
    rows=[];sha=None
    for path in files:
        with gzip.open(path,"rt") as f:
            doc=json.load(f)
        assert doc["schema"]=="dack_v27_fresh_98k_physical_beam160_shard"
        assert doc["status"]=="PASS" and doc["experimental_policies_unapproved"]
        assert doc["actual_gameplay_beam"]==160 and doc["same_seat_and_physical_first_seven"]
        if sha is None:sha=doc["models_sha256"]
        else:assert sha==doc["models_sha256"]
        assert len(doc["rows"])==4
        rows+=doc["rows"]
    rows.sort(key=lambda x:x["game_id"])
    assert [r["game_id"] for r in rows]==list(range(98000,98256))
    assert all(len({r[p]["seat"] for p in POLICIES})==1 for r in rows)
    assert all(len({tuple(r[p]["history"][0]["seven_slots"]) for p in POLICIES})==1 for r in rows)
    same_hand_diff=[
      r["game_id"] for r in rows
      if sorted(r["v5"]["history"][-1]["hand"])==
         sorted(r["v27_T2_only_DP"]["history"][-1]["hand"])
         and r["v5"]["turn"]!=r["v27_T2_only_DP"]["turn"]
    ]
    assert not same_hand_diff,("physical parity anomaly",same_hand_diff)
    metrics={p:measure(rows,p) for p in POLICIES}
    pairs={
      a+"_minus_"+b:{
        "T"+str(t):compare(rows,a,b,t) for t in (1,2,3)
      } for a,b in [
        ("v27_T2_only_DP","v5"),
        ("v27_T2_only_DP","v26_expanded_keep_DP"),
        ("v26_expanded_keep_DP","v5"),
      ]
    }
    report={
      "schema":"dack_v27_T2_only_prospective_98k_N256",
      "status":"PASS",
      "n_independent_physical_game_ids":256,
      "physical_ids":[98000,98255],
      "T2_primary_endpoint":"Cumulative by T2, v27 against v5 and previous frozen v26",
      "T1_and_T3_secondary":True,
      "goldfish_not_multiplayer_winrate":True,
      "original_v5_rule_reference_unchanged":True,
      "no_previous_96k_97k_outcome_training":True,
      "model_and_dp_sha256":sha,
      "metrics":metrics,"paired":pairs,
      "same_final_hand_different_outcome":0,
      "speedup_v5_over_v27":metrics["v5"]["simulation_seconds"]/
             max(1e-6,metrics["v27_T2_only_DP"]["simulation_seconds"]),
      "model_approved":False,
      "warning":"Prospective exploratory N256; no equivalence claim. Different policies can trade by-T3 reach for by-T2 speed.",
    }
    out=Path("benchmark_results/v27_prospective_T2_98k_N256.json")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V27_PROSPECTIVE_98K_N256_PASS",json.dumps(report,sort_keys=True),flush=True)

if __name__=="__main__":
    main()
