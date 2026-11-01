#!/usr/bin/env python3
"""Pool exactly N256 fresh full-game outcomes, paired bootstrap by physical game.

v32 shared C calibrated before 110k, v27 frozen, v5 retained reference.
T2 primary; report T1/T3, paired gains/losses and runtime. No tuning.
"""
from __future__ import annotations
import collections,gzip,glob,json,random,math
from pathlib import Path

POLICIES=("v5","v27_frozen","v32_shared_C")
def exact_mcnemar(g,l):
    n=g+l
    return min(1.,2*sum(math.comb(n,k) for k in range(min(g,l)+1))/(2**n)) if n else 1.

def main():
    files=sorted(glob.glob("collected/v32_110k_*.json.gz"))
    assert len(files)==64,len(files)
    rows=[];originalhash=None
    for file in files:
        with gzip.open(file,"rt") as f:doc=json.load(f)
        assert doc["schema"]=="dack_v32_prospective_110k_three_policy_strict"
        assert doc["status"]=="PASS" and doc["n_game_groups"]==4
        assert doc["actual_gameplay_beam"]==160
        assert doc["mulligan_beams_v32"]==0
        assert doc["same_physical_first_seven_and_seat"]
        assert doc["test_cohort_never_in_training_or_threshold_calibration"]
        assert tuple(doc["policies"])==POLICIES
        assert doc["v32_approved"] is False
        if originalhash is None:originalhash=doc["source_sha256"]
        assert originalhash==doc["source_sha256"]
        rows+=doc["rows"]
    rows.sort(key=lambda x:x["game_id"])
    assert [x["game_id"] for x in rows]==list(range(110000,110256))
    metric={}
    for p in POLICIES:
        data=[r[p] for r in rows]
        metric[p]={
          "N":len(data),
          "T1_count":sum(x["turn"]==1 for x in data),
          "T2_count":sum(0<x["turn"]<=2 for x in data),
          "T3_count":sum(0<x["turn"]<=3 for x in data),
          "mean_keep_n":sum(x["keep_n"] for x in data)/len(data),
          "sum_gameplay_seconds":sum(x["seconds"] for x in data),
        }
    paired={}
    rng=random.Random(321103)
    for baseline in ("v27_frozen","v5"):
        for turn in (1,2,3):
            diffs=[int(0<r["v32_shared_C"]["turn"]<=turn)-
                  int(0<r[baseline]["turn"]<=turn) for r in rows]
            boost=sorted(100*sum(diffs[rng.randrange(256)] for _ in range(256))/256
                for _ in range(10000))
            g=diffs.count(1);l=diffs.count(-1)
            paired[f"v32_minus_{baseline}_T{turn}"]={
              "delta_pp":100*sum(diffs)/256,
              "gains":g,"losses":l,
              "bootstrap_95ci_pp":[boost[249],boost[9749]],
              "exploratory_exact_mcnemar_p":exact_mcnemar(g,l),
            }
    changes={}
    for base in ("v27_frozen","v5"):
        counter=collections.Counter()
        sample=[]
        for row in rows:
            a=row[base];z=row["v32_shared_C"]
            if a["keep_n"]!=z["keep_n"]:
                counter["different_final_keep_depth"]+=1
            elif collections.Counter(a["history"][-1]["hand"])!=collections.Counter(z["history"][-1]["hand"]):
                counter["same_depth_different_hand"]+=1
            else:
                counter["same_final_hand"]+=1
            if a["keep_n"]!=z["keep_n"] or collections.Counter(a["history"][-1]["hand"])!=collections.Counter(z["history"][-1]["hand"]):
                sample.append({
                  "game_id":row["game_id"],
                  "baseline_keep_n":a["keep_n"],
                  "v32_keep_n":z["keep_n"],
                  "baseline_turn":a["turn"],
                  "v32_turn":z["turn"]
                })
        changes["relative_to_"+base]={"summary":dict(counter),"sample":sample[:30]}
    report={
       "schema":"dack_v32_prospective_110k_N256_strict_v5_v27_v32",
       "status":"PASS","test_ids":[110000,110255],
       "n_independent_physical_games":256,
       "primary_endpoint":"cumulative deployment by Turn 2",
       "no_110k_training_or_calibration":True,
       "actual_goldfish_not_interactive_cEDH":True,
       "unchanged_physical_99_seat_first_seven_beam160":True,
       "all_models_unapproved":True,
       "source_sha256":originalhash,
       "per_policy":metric,"paired":paired,
       "final_hand_changes":changes,
       "v5_to_v32_gameplay_speedup":metric["v5"]["sum_gameplay_seconds"]/max(1e-6,metric["v32_shared_C"]["sum_gameplay_seconds"]),
       "limitations":"N256 paired evidence does not establish equivalence; v32 continuation estimates are one-step deviations under frozen v27 future policy, not fixed-point DP. Goldfish ignores opponent responses.",
    }
    out=Path("benchmark_results/v32_prospective_110k_N256.json")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("DACK_V32_PROSPECTIVE_N256_PASS",json.dumps({
       "metrics":metric,"paired":paired,
       "different_final_keep_depth_vs_v27":changes["relative_to_v27_frozen"]["summary"]["different_final_keep_depth"]
    },sort_keys=True),flush=True)

if __name__=="__main__":main()
