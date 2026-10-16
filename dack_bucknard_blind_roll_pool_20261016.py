#!/usr/bin/env python3
"""Compare outcome-blind Bucknard T2 policy and neutral-two stress test to baseline."""
import argparse,glob,gzip,json,math
from collections import Counter
from pathlib import Path

BASE_SHA="3a10a02e1aae070645129fa85ed94240f1ae9d5447e3711f7621f92064d9f129"
BUCK_SHA="f130ff4c9c0fbc888525070877fe820caba03e836e0be66ec60ea3410e950068"
SEED_BASE=7604096001

def collect(globexpr,mode,expected_n,expected_beam):
    files=sorted(glob.glob(globexpr,recursive=True))
    assert files,(globexpr,"missing")
    rows={}
    for path in files:
        with gzip.open(path,"rt") as f:d=json.load(f)
        assert d["mode"]==mode,(path,mode,d["mode"])
        assert d["beam"]==expected_beam,(path,d["beam"])
        assert d["deck_sha256"]==BUCK_SHA,(path,"deck hash mismatch")
        assert d["seed_base"]==SEED_BASE
        assert len(d["rows"])==d["games"]
        for i,rec in enumerate(d["rows"]):
            gid=int(rec["gid"])
            assert gid==d["shard"]*d["games"]+i
            assert gid not in rows,(gid,"duplicate")
            rows[gid]=rec
    assert set(rows)==set(range(expected_n)),("gaps",len(rows),expected_n)
    return rows,len(files)

def baseline(expr,expected):
    files=sorted(glob.glob(expr,recursive=True))
    assert files
    rows={}
    for path in files:
        with gzip.open(path,"rt") as f:d=json.load(f)
        assert d["variant"]=="current" and d["deck_sha256"]==BASE_SHA
        for r in d["rows"]:
            gid=r["game_id"]
            if gid<expected:
                assert gid not in rows
                rows[gid]=r
    assert set(rows)==set(range(expected))
    return rows

def summarize(records,mode,base):
    n=len(records)
    vals=[]
    for gid in range(n):
        p=(float(records[gid]["prob_T2"]) if mode=="blind_T2"
           else float(records[gid]["success_T2"]))
        assert 0<=p<=1.
        vals.append((p,float(0<base[gid]["win_turn"]<=2)))
    diffs=[p-b for p,b in vals]
    mean=sum(diffs)/n
    se=math.sqrt(sum((d-mean)**2 for d in diffs)/(n-1)/n)
    result={"games":n,"baseline_T2_pct":round(100*sum(b for p,b in vals)/n,4),
            "bucknard_T2_pct":round(100*sum(p for p,b in vals)/n,4),
            "delta_pp":round(100*mean,4),
            "paired_95pct_pp":[round(100*(mean-1.96*se),3),round(100*(mean+1.96*se),3)],
            "baseline_success_count":int(sum(b for p,b in vals))}
    if mode=="blind_T2":
        result.update({
            "expected_success_games":round(sum(p for p,b in vals),3),
            "probability_1_count":sum(p==1 for p,b in vals),
            "probability_partial_count":sum(0<p<1 for p,b in vals),
            "probability_0_count":sum(p==0 for p,b in vals),
            "mean_candidate_evaluated":round(sum(x["evaluated"] for x in records.values())/n,3),
            "chosen_activation_turn_counts":dict(Counter(str(x["chosen"]) for x in records.values()))})
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--baseline",default="baseline/**/*.json.gz")
    p.add_argument("--blind",default="blind/*.json.gz")
    p.add_argument("--neutral",default="neutral/*.json.gz")
    p.add_argument("--blind-n",type=int,default=128)
    p.add_argument("--neutral-n",type=int,default=512)
    p.add_argument("--out",default="bucknard_blind_roll_audit_results_20261016.json")
    a=p.parse_args()
    bl=baseline(a.baseline,max(a.blind_n,a.neutral_n))
    bb,ns1=collect(a.blind,"blind_T2",a.blind_n,80)
    nn,ns2=collect(a.neutral,"neutral_fixed2",a.neutral_n,240)
    result={
      "status":"PASS","design":"Bucknard pre-roll commitment uses expectation across 1-4 outcomes rather than realized die; limited candidate beam-policy search",
      "original_baseline_run":38912678782,
      "original_oracle_bucknard_n1024_run":38961531770,
      "original_oracle_T2_pct":47.9492,
      "original_baseline_T2_pct":44.4336,
      "original_oracle_delta_pp":3.5156,
      "methods":{
        "blind_T2":"Search T1-T2 with Bucknard activations withheld; collect highest ranked eligible states (max 4 per turn); choose a single state maximizing mean success over rolls 1,2,3,4; only after roll permit adaptations. Mulligans evaluated assuming neutral 2 Treasures.",
        "neutral_fixed2":"Full original T1-T3 solver and mulligan policy with Bucknard deterministically creating 2 Treasures (no random-state roll fishing). This is a stress test, not d4 expected value.",
        "baseline":"Original Oct 16 World Map deck, exact matching game IDs and initial shuffle seeds."
      },
      "blind_T2_n"+str(a.blind_n):summarize(bb,"blind_T2",bl),
      "neutral_fixed2_n"+str(a.neutral_n):summarize(nn,"neutral_fixed2",bl),
      "audited_shards":{"blind":ns1,"neutral_fixed2":ns2},
      "limitations":[
        "Blind policy is approximate top-K chance-aware candidate search, not exact full imperfect-information solver",
        "Candidate selection uses known library order already present in old goldfish; does not separately blind future draws",
        "After first activation of Bucknard, postroll beam search is adaptive as it should be",
        "Additional copied Bucknard activations after the first use the same forced outcome, a rare approximation",
        "No opponent interaction or post-Dack win-line proof",
        "Partial expected-success outcomes are averaged over four die faces and paired with original binary baseline"
      ]
    }
    Path(a.out).write_text(json.dumps(result,indent=2)+"\n")
    print("BUCKNARD_OUTCOME_BLIND_RESULT_PASS",json.dumps(result),flush=True)

if __name__=="__main__":main()
