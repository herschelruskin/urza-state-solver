#!/usr/bin/env python3
"""Prospective independent physical 97k performance of frozen experimental v26."""
from __future__ import annotations
import gzip,glob,json,math,random
from pathlib import Path
N=256
POL=("v5","v22_real_keep_DP","v26_expanded_keep_DP")
FILES="collected/v26_97k_*.json.gz"

def measure(rows,pol):
    z=[r[pol] for r in rows]
    return {
       "n":len(z),
       "T1":sum(x["turn"]==1 for x in z),
       "T2":sum(x["turn"] in (1,2) for x in z),
       "T3":sum(x["turn"] in (1,2,3) for x in z),
       "mean_keep_n":sum(x["keep_n"] for x in z)/len(z),
       "simulation_seconds":round(sum(x["seconds"] for x in z),4),
    }

def compare(rows,a,b,t):
    diff=[int(0<r[a]["turn"]<=t)-int(0<r[b]["turn"]<=t) for r in rows]
    gains=diff.count(1);losses=diff.count(-1)
    n=len(diff);rng=random.Random(260000+len(a)*17+len(b)*13+t)
    sims=sorted(100*sum(diff[rng.randrange(n)] for _ in range(n))/n for _ in range(8000))
    q=gains+losses
    exact=min(1.,2*sum(math.comb(q,k) for k in range(min(gains,losses)+1))/(2**q)) if q else 1.
    return {
       "difference_pp":100*sum(diff)/n,
       "gains":gains,"losses":losses,
       "paired_bootstrap_95ci_pp":[sims[199],sims[7799]],
       "exploratory_exact_mcnemar_two_sided_p":exact,
    }

def main():
    files=sorted(glob.glob(FILES))
    assert len(files)==64,("expected all 64 fresh 97k shards",len(files))
    rows=[];hashes=None
    for f in files:
        with gzip.open(f,"rt") as stream:
            packet=json.load(stream)
        assert packet["schema"]=="dack_v26_frozen_physical_97k_test"
        assert packet["status"]=="PASS" and packet["actual_gameplay_beam"]==160
        assert packet["v26_unapproved"] is True
        assert packet["same_first_physical_seven_verified"]
        if hashes is None:hashes=packet["models_sha256"]
        else:assert hashes==packet["models_sha256"],("inconsistent model weights",f)
        assert len(packet["rows"])==4
        rows+=packet["rows"]
    rows.sort(key=lambda r:r["game_id"])
    assert [r["game_id"] for r in rows]==list(range(97000,97256))
    assert all(len({r[p]["seat"] for p in POL})==1 for r in rows)
    assert all(len({tuple(r[p]["history"][0]["seven_slots"]) for p in POL})==1 for r in rows)
    same_hands=[r["game_id"] for r in rows if
        sorted(r["v5"]["history"][-1]["hand"])==
        sorted(r["v26_expanded_keep_DP"]["history"][-1]["hand"]) and
        r["v5"]["turn"]!=r["v26_expanded_keep_DP"]["turn"]]
    assert not same_hands,("identical final hands, different outcome",same_hands)
    metrics={p:measure(rows,p) for p in POL}
    pairs={
      a+"_minus_"+b:{
        "T"+str(t):compare(rows,a,b,t) for t in (1,2,3)
      } for a,b in [
        ("v26_expanded_keep_DP","v5"),
        ("v26_expanded_keep_DP","v22_real_keep_DP"),
        ("v22_real_keep_DP","v5"),
      ]
    }
    report={
       "schema":"dack_v26_prospective_real_value_N256_97k",
       "status":"PASS",
       "game_ids":[97000,97255],
       "independent_physical_groups":256,
       "models_frozen_before_97k_test":True,
       "v25_96k_evaluation_not_training":True,
       "actual_beam160_goldfish_gameplay":True,
       "experimental_model_approved":False,
       "sha256":hashes,
       "metrics":metrics,
       "paired":pairs,
       "identical_final_hand_different_outcome_cases":0,
       "speedup_v5_over_v26":metrics["v5"]["simulation_seconds"]/
          max(1e-6,metrics["v26_expanded_keep_DP"]["simulation_seconds"]),
       "primary_endpoint":"Cumulative Turn 2: v26 vs v5; compare against frozen v22 as mechanism check",
       "warning":"No four-player multiplayer win rates. N256 confidence interval does not prove equivalence unless precision meets a predefined noninferiority margin.",
    }
    out=Path("benchmark_results/v26_prospective_97k_vs_v5_v22_N256.json")
    out.parent.mkdir(exist_ok=True,parents=True)
    out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("DACK_V26_PROSPECTIVE_97K_PAIRED_N256_PASS",json.dumps(report,sort_keys=True),flush=True)

if __name__=="__main__":
    main()
