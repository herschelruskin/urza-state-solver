#!/usr/bin/env python3
"""Pooled Realistic v6 N128 vs frozen Full Beam, matched game IDs."""
from __future__ import annotations
import argparse,glob,gzip,json,math
from collections import Counter
from pathlib import Path
SHA={"current":"3a10a02e1aae070645129fa85ed94240f1ae9d5447e3711f7621f92064d9f129",
"buck_worldmap":"f130ff4c9c0fbc888525070877fe820caba03e836e0be66ec60ea3410e950068"}
def load(pattern,var,n,exact_schema=None):
    files=glob.glob(pattern,recursive=True);assert files,(pattern,"missing")
    data={}
    for file in files:
        with gzip.open(file,"rt") as f:q=json.load(f)
        if q["variant"]!=var:continue
        assert q["deck_sha256"]==SHA[var]
        if exact_schema:assert q["schema"]==exact_schema
        for r in q["rows"]:
            i=r["game_id"]
            if i<n:
                assert i not in data
                data[i]=r
    assert set(data)==set(range(n)),(var,n,len(data))
    return data
def summary(rows):
    n=len(rows);c=Counter(q["win_turn"] for q in rows.values())
    return {"n":n,"by_T1_pct":round(100*c[1]/n,4),
            "by_T2_pct":round(100*(c[1]+c[2])/n,4),
            "by_T3_pct":round(100*(c[1]+c[2]+c[3])/n,4),
            "mean_keep":round(sum(q["keep_n"] for q in rows.values())/n,3)}
def paired(a,b):
    n=len(a);r={}
    for t in (1,2,3):
        diff=[int(0<a[i]["win_turn"]<=t)-int(0<b[i]["win_turn"]<=t) for i in range(n)]
        mu=sum(diff)/n
        se=math.sqrt(sum((z-mu)**2 for z in diff)/(n*(n-1)))
        r[f"T{t}"]={"delta_pp":round(100*mu,4),
            "paired_normal_95pct_pp":[round(100*(mu-1.96*se),3),round(100*(mu+1.96*se),3)],
            "a_only":sum(z==1 for z in diff),"b_only":sum(z==-1 for z in diff)}
    return r
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--real",default="real")
    p.add_argument("--full-current",default="full_current")
    p.add_argument("--full-buck",default="full_buck")
    p.add_argument("--n",type=int,default=128)
    p.add_argument("--out",required=True)
    a=p.parse_args();x={}
    for v in SHA:
        real=load(f"{a.real}/**/{v}_shard_*.json.gz",v,a.n,
            "dack_realistic_v6_confirm_n128")
        full=load(f"{a.full_current if v=='current' else a.full_buck}/**/*.json.gz",v,a.n)
        x[v]={"real":real,"full":full}
    out={"status":"PASS","n_per_deck":a.n,
      "design":"Same paired game IDs, exact decks, frozen original Full Beam=240 vs Realistic v6 gameplay=120, stratified chance-aware turn planning and independent Bucknard die",
      "arms":{},"paired_swap":{}}
    for v,z in x.items():
        out["arms"][v]={"realistic_v6":summary(z["real"]),
          "full_beam_optimistic":summary(z["full"]),
          "realistic_minus_full":paired(z["real"],z["full"])}
    for engine in ("real","full"):
        out["paired_swap"][engine]=paired(x["buck_worldmap"][engine],x["current"][engine])
    out["limitations"]=[
      "Full Beam is intentionally clairvoyant and its absolute rates are not realistic match win probabilities",
      "Realistic v6 still inherits within-turn hidden-information peek in certain tutor/draw action sequences",
      "N128 is exploratory for effects of 1-3 percentage points",
      "Goldfish Dack deployment proxy, not a full multiplayer game or combo proof",
      "The two engines also differ in beam width and policy quality, so their gap is not solely hindsight"]
    Path(a.out).write_text(json.dumps(out,indent=2)+"\n")
    print("DACK_V6_CONFIRM_N128_POOLED_PASS",json.dumps(out),flush=True)
if __name__=="__main__":main()
