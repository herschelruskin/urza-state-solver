#!/usr/bin/env python3
"""Pool 7 matched N512 ablations against frozen Oct16 baseline and Bucknard arm."""
import argparse,glob,gzip,json,math
from collections import Counter
from pathlib import Path
from dack_plains_battlefront_ablation_20261016 import SWAPS,VARIANTS

NAMES=tuple(SWAPS)
REFERENCE_SHA="3a10a02e1aae070645129fa85ed94240f1ae9d5447e3711f7621f92064d9f129"
BUCK_SHA="f130ff4c9c0fbc888525070877fe820caba03e836e0be66ec60ea3410e950068"

def fetch(pattern,variant,n,beam,expected_sha=None):
    files=sorted(glob.glob(pattern,recursive=True))
    assert files,("nothing matches",pattern)
    rows={}
    hashes=set()
    for path in files:
        with gzip.open(path,"rt") as f:data=json.load(f)
        assert data["variant"]==variant,(path,data["variant"],variant)
        assert data["beam"]==beam,(path,data["beam"])
        assert data["games"]==len(data["rows"])
        assert data["seed_base"]==7604096001
        assert Counter(int(x["win_turn"]) for x in data["rows"])==Counter(
            {int(k):v for k,v in data["counts"].items()}),(path,"bad count")
        hashes.add(data["deck_sha256"])
        for q in data["rows"]:
            gid=int(q["game_id"])
            assert q["seed"]==7604096001+gid*1000003
            assert q["win_turn"] in (0,1,2,3)
            assert 1<=q["keep_n"]<=7
            if gid<n:
                assert gid not in rows,(path,gid,"duplicate")
                rows[gid]=q
    assert len(hashes)==1,(variant,hashes)
    dhash=next(iter(hashes))
    if expected_sha:assert dhash==expected_sha,(variant,dhash,expected_sha)
    assert len(rows)==n,(variant,len(rows),n)
    assert set(rows)==set(range(n)),(variant,"missing ids")
    return rows,dhash

def wilson(k,n):
    z=1.9599639845;p=k/n;den=1+z*z/n
    m=(p+z*z/(2*n))/den
    r=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [round(100*(m-r),3),round(100*(m+r),3)]

def summarize(rows):
    n=len(rows)
    counts=Counter(q["win_turn"] for q in rows.values())
    return {"n":n,
            "counts":{str(k):counts[k] for k in range(4)},
            "cumulative_pct":{f"by_T{t}":round(100*sum(counts[k] for k in range(1,t+1))/n,4) for t in (1,2,3)},
            "Wilson95pct":{f"by_T{t}":wilson(sum(counts[k] for k in range(1,t+1)),n) for t in (1,2,3)},
            "mean_keep":round(sum(q["keep_n"] for q in rows.values())/n,4)}

def paired(a,b):
    assert a.keys()==b.keys()
    n=len(a)
    out={}
    for t in (1,2,3):
        dif=[int(0<a[i]["win_turn"]<=t)-int(0<b[i]["win_turn"]<=t) for i in range(n)]
        mean=sum(dif)/n
        var=sum((x-mean)**2 for x in dif)/(n-1) if n>1 else 0
        se=math.sqrt(var/n)
        out[f"by_T{t}"]={
            "delta_pp":round(100*mean,4),
            "paired_normal_95pct_pp":[round(100*(mean-1.96*se),3),
                                      round(100*(mean+1.96*se),3)],
            "two_sided_p_approx":round(math.erfc(abs(mean/se)/math.sqrt(2)),6) if se else 1.0,
            "better_only":sum(x==1 for x in dif),
            "worse_only":sum(x==-1 for x in dif)}
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--selftest",action="store_true")
    ap.add_argument("--baseline",default="baseline/**/*.json.gz")
    ap.add_argument("--buck",default="buck_reference/**/*.json.gz")
    ap.add_argument("--shards",default="shards")
    ap.add_argument("--n",type=int,default=512)
    ap.add_argument("--beam",type=int,default=240)
    ap.add_argument("--out",default="plains_battlefront_pooled_20261016.json")
    a=ap.parse_args()
    if a.selftest:
        assert wilson(0,10)[0]>=0
        assert paired({0:{"win_turn":1}},{0:{"win_turn":3}})["by_T1"]["delta_pp"]==100.0
        print("PLAINS_BATTLEFRONT_POOL_SELFTEST_PASS",flush=True)
        return
    base,sha=fetch(a.baseline,"current",a.n,a.beam,REFERENCE_SHA)
    buck,buck_sha=fetch(a.buck,"buck_worldmap",a.n,a.beam,BUCK_SHA)
    payload={"status":"PASS","n_per_arm":a.n,"beam":a.beam,"baseline_run_id":38912678782,
             "buck_reference_run_id":38931616641,
             "baseline_current":{"sha":sha,"summary":summarize(base)},
             "reference_buck_worldmap":{"sha":buck_sha,"summary":summarize(buck),
                                        "paired_delta_vs_current":paired(buck,base)},
             "variants":{}}
    pvals=[]
    for v,swaps in SWAPS.items():
        rows,dhash=fetch(f"{a.shards}/**/{v}_*.json.gz",v,a.n,a.beam)
        assert dhash not in (sha,buck_sha),(v,"unchanged deck")
        pb=paired(rows,base)
        pkg={"swaps":swaps,"sha":dhash,"summary":summarize(rows),
             "paired_vs_current":pb}
        if v.startswith("buck_"):
            pkg["paired_vs_buck_worldmap"]=paired(rows,buck)
        payload["variants"][v]=pkg
        pvals.append((v,pb["by_T2"]["two_sided_p_approx"]))
    # Treat all seven vs baseline T2 tests as one exploratory family.
    ordered=sorted(pvals,key=lambda q:q[1])
    running=0
    for i,(v,p) in enumerate(ordered):
        running=max(running,min(1,p*(len(ordered)-i)))
        payload["variants"][v]["primary_T2_Holm_p_approx"]=round(running,6)
    payload["limitations"]=[
        "Focused Dack-cast goldfish, not competitive match win rate",
        "No opponent interaction (Soul Partition and Mana Tithe excluded as protection value)",
        "All simulations inherited frozen pre-free-mulligan continuation thresholds",
        "Deterministic random seeds paired by game ID; deck changes alter shuffle ordering",
        "Approximate paired CIs conditional on solver, no guarantee of exact search completeness",
        "The World Map->Bucknard reference is archived N512 exact-corrected implementation",
        "Seven tested variants; no combo/aura pieces removed"
    ]
    Path(a.out).write_text(json.dumps(payload,indent=2)+"\n")
    print("PLAINS_BATTLEFRONT_POOLED_PASS",json.dumps(payload),flush=True)

if __name__=="__main__":main()
