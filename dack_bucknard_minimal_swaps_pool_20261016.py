#!/usr/bin/env python3
"""Integrity-check four Bucknard 1-for-1 arms against completed Oct 16 baseline."""
import argparse,glob,gzip,json,math
from collections import Counter
from pathlib import Path

VARIANTS=("buck_tooth","buck_implements","buck_battlefront","buck_worldmap")
CUTS={
    "buck_tooth":"Tooth of Ramos",
    "buck_implements":"Implements of Sacrifice",
    "buck_battlefront":"United Battlefront",
    "buck_worldmap":"World Map",
}
BASELINE_SHA="3a10a02e1aae070645129fa85ed94240f1ae9d5447e3711f7621f92064d9f129"

def load_jsons(pattern,variant,expected,beam):
    paths=glob.glob(pattern,recursive=True)
    assert paths,(pattern,"missing")
    rows=[]
    hashes=set()
    for path in sorted(paths):
        with gzip.open(path,"rt",encoding="utf8") as f:x=json.load(f)
        assert x["variant"]==variant,(path,x["variant"],variant)
        assert x["beam"]==beam,(path,x["beam"],beam)
        assert x["games"]==len(x["rows"])
        assert x["seed_base"]==7604096001
        hashes.add(x["deck_sha256"])
        assert Counter(int(r["win_turn"]) for r in x["rows"])==Counter(
            {int(k):v for k,v in x["counts"].items()})
        for r in x["rows"]:
            gid=int(r["game_id"])
            assert r["seed"]==7604096001+gid*1000003,(path,gid)
            assert 0<=r["win_turn"]<=3
            assert 1<=r["keep_n"]<=7
        rows.extend(x["rows"])
    assert len(hashes)==1,(variant,hashes)
    assert len(rows)==expected,(variant,len(rows),expected)
    ids=[int(x["game_id"]) for x in rows]
    assert len(set(ids))==expected,(variant,"duplicate")
    assert sorted(ids)==list(range(expected)),(variant,"missing game")
    return {int(r["game_id"]):r for r in rows},next(iter(hashes))

def ci_wilson(count,n):
    z=1.9599639845; p=count/n
    den=1+z*z/n
    mid=(p+z*z/(2*n))/den
    radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [round(100*(mid-radius),3),round(100*(mid+radius),3)]

def summary(rows):
    n=len(rows)
    c=Counter(int(r["win_turn"]) for r in rows.values())
    pct={}
    ci={}
    for t in (1,2,3):
        k=sum(c[i] for i in range(1,t+1))
        pct[f"by_T{t}"]=round(100*k/n,4)
        ci[f"by_T{t}"]=ci_wilson(k,n)
    return {"n":n,"counts":{str(k):c[k] for k in range(4)},
            "cumulative_pct":pct,"Wilson95pct":ci,
            "mean_keep":round(sum(r["keep_n"] for r in rows.values())/n,4)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--baseline-glob",default="baseline/**/*.json.gz")
    p.add_argument("--arms-dir",default="shards")
    p.add_argument("--expected",type=int,default=512)
    p.add_argument("--beam",type=int,default=240)
    p.add_argument("--out",default="bucknard_minimal_swaps_pooled_20261016.json")
    p.add_argument("--selftest",action="store_true")
    a=p.parse_args()
    if a.selftest:
        assert ci_wilson(0,10)[0]>=0
        assert ci_wilson(10,10)[1]<100.00001
        print("BUCKNARD_POOL_SELFTEST_PASS",flush=True);return
    base,bhash=load_jsons(a.baseline_glob,"current",a.expected,a.beam)
    assert bhash==BASELINE_SHA,(bhash,BASELINE_SHA)
    arms={}
    n=a.expected
    for v in VARIANTS:
        rows,dhash=load_jsons(f"{a.arms_dir}/**/{v}_*.json.gz",v,n,a.beam)
        assert dhash!=bhash,(v,"unchanged deck hash")
        arms[v]={"rows":rows,"sha":dhash}
    output={"status":"PASS","design":"Matched N=512 independent per-game random draws under original exact99 engine; one card replaced",
            "baseline_run":38912678782,
            "n_per_arm":n,"beam":a.beam,"baseline_deck_sha":bhash,
            "baseline":summary(base),"variants":{}}
    pvals=[]
    for v in VARIANTS:
        rows=arms[v]["rows"]
        deltas={}
        for t in (1,2,3):
            dx=[int(0<rows[i]["win_turn"]<=t)-int(0<base[i]["win_turn"]<=t)
                for i in range(n)]
            mean=sum(dx)/n
            var=sum((d-mean)**2 for d in dx)/(n-1) if n>1 else 0
            se=math.sqrt(var/n)
            z=mean/se if se>0 else 0.0
            pval=math.erfc(abs(z)/math.sqrt(2)) if se>0 else 1.0
            deltas[f"by_T{t}"]={
                "delta_pp":round(100*mean,4),
                "paired_95pct_pp":[round(100*(mean-1.96*se),3),
                                   round(100*(mean+1.96*se),3)],
                "p_approx":round(pval,6),
                "improved_only":sum(d==1 for d in dx),
                "baseline_only":sum(d==-1 for d in dx)}
            if t==2:pvals.append((v,pval))
        output["variants"][v]={
            "cut":CUTS[v],"add":"Bucknard's Everfull Purse",
            "deck_sha256":arms[v]["sha"],"summary":summary(rows),
            "paired_delta_vs_current":deltas}
    # Holm correction for the four primary T2 comparisons; secondary T1/T3
    # intervals are descriptive, not confirmatory.
    ordered=sorted(pvals,key=lambda x:x[1])
    holm={}
    running=0.0
    for j,(v,pval) in enumerate(ordered):
        running=max(running,min(1.0,pval*(len(ordered)-j)))
        holm[v]=round(running,6)
    for v in VARIANTS:
        output["variants"][v]["primary_T2_Holm_p_approx"]=holm[v]
    output["limitations"]=[
        "Goldfish: successful Dack cast with all three Boonweaver combo creatures in library",
        "Staff proliferate corrected, life costs included",
        "One free multiplayer London mulligan, provisional inherited continuation thresholds",
        "Bucknard d4 sampled deterministically per complete state and game seed",
        "Bucknard control passed away after activation; with KCI, sacrifice in response modeled",
        "Opponent interaction, protection and post-Dack combo resolution not simulated",
        "Four separate single swaps, no two-card/land-count package tested here",
    ]
    Path(a.out).write_text(json.dumps(output,indent=2)+"\n",encoding="utf8")
    print("BUCKNARD_MINIMAL_SWAPS_POOLED_PASS",json.dumps(output),flush=True)

if __name__=="__main__":main()
