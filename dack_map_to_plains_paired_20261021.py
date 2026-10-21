#!/usr/bin/env python3
"""Paired exact current 34-land Dack list vs only World Map -> Plains (35 lands).

Identical cards otherwise (including Bucknard and Coalition Relic).
Uses the same beam and free multiplayer London mulligan policy in both arms.
"""
from __future__ import annotations
import argparse, gzip, hashlib, json, math, time
from pathlib import Path
from collections import Counter
import dack_plains_voltaic_paired_20261021 as prev

root=prev.root
d=prev.d
m=prev.m
CURRENT=prev.CURRENT
PROPOSED=prev.swap(CURRENT,"World Map","Plains")
VARIANTS={"current34":CURRENT,"plains35":PROPOSED}
root.VARIANTS=VARIANTS
root.batch.build_deck=lambda variant:VARIANTS[variant]

def sha(deck): return hashlib.sha256("\n".join(deck).encode()).hexdigest()

def audit():
    assert len(CURRENT)==len(PROPOSED)==99
    assert CURRENT.count("Plains")==10 and PROPOSED.count("Plains")==11
    assert CURRENT.count("World Map")==1 and PROPOSED.count("World Map")==0
    assert Counter(PROPOSED)-Counter(CURRENT)==Counter(["Plains"])
    assert Counter(CURRENT)-Counter(PROPOSED)==Counter(["World Map"])
    assert all(deck.count("Bucknard's Everfull Purse")==1 for deck in VARIANTS.values())
    assert all(deck.count("Coalition Relic")==1 for deck in VARIANTS.values())
    assert all(root.COMBO.issubset(deck) for deck in VARIANTS.values())
    assert not any(c in CURRENT for c in ("Mana Crypt","Jeweled Lotus"))
    assert root.batch.CONFIG["lambda"]==0.5
    for variant,deck in VARIANTS.items():
        root.install(variant)
        assert len(d.DECK)==99
        assert all(x in d.CARD_ID for x in d.DECK)
        assert d.COSTS["World Map"]==(1,0,0)
    print("MAP_TO_PLAINS_EXACT99_AUDIT_PASS",sha(CURRENT),sha(PROPOSED),flush=True)

def run(shard,games,beam,out):
    records=[]
    start=time.time()
    for i in range(games):
        gid=shard*games+i
        rows={}
        for variant in VARIANTS:
            root.install(variant)
            d._WIN_CACHE.clear()
            rows[variant]=root.simulate(variant,gid,beam)
            print("GAME",variant,gid,rows[variant]["win_turn"],rows[variant]["keep_n"],flush=True)
        records.append({"game_id":gid,**rows})
    payload={"schema":"dack_map_to_plains_paired_v1","games":games,"shard":shard,
      "beam":beam,"deck_sha":{k:sha(v) for k,v in VARIANTS.items()},
      "seed_base":root.batch.CONFIG["seed_base"],"records":records,
      "elapsed_sec":round(time.time()-start,2)}
    with gzip.open(out,"wt",encoding="utf8") as f:json.dump(payload,f,separators=(",",":"))
    print("MAP_PLAINS_SHARD_PASS",games,shard,round(time.time()-start,2),flush=True)

def pool(path,out,expected):
    files=sorted(Path(path).glob("*.json.gz"))
    assert files,("missing shards",path)
    records={}; hashes=None; beams=set()
    for p in files:
        with gzip.open(p,"rt",encoding="utf8") as f:q=json.load(f)
        assert q["schema"]=="dack_map_to_plains_paired_v1"
        if hashes is None: hashes=q["deck_sha"]
        assert q["deck_sha"]==hashes and q["games"]==len(q["records"])
        beams.add(q["beam"])
        for rec in q["records"]:
            gid=rec["game_id"];assert gid not in records
            for v in VARIANTS:
                assert rec[v]["game_id"]==gid
                assert rec[v]["seed"]==q["seed_base"]+gid*1000003
            records[gid]=rec
    assert len(beams)==1 and len(records)==expected
    assert set(records)==set(range(expected))
    result={"status":"PASS","n_paired":len(records),"beam":list(beams)[0],
        "deck_sha":hashes,
        "scope":"historical full-beam Dack cast goldfish, all 3 combo creatures required in library; no opponents",
        "change":["World Map","Plains"]}
    n=len(records)
    for v in VARIANTS:
        counts=Counter(records[i][v]["win_turn"] for i in records)
        result[v]={"counts":{str(i):counts[i] for i in range(4)},
          "by_T1_pct":round(100*counts[1]/n,4),
          "by_T2_pct":round(100*(counts[1]+counts[2])/n,4),
          "by_T3_pct":round(100*(counts[1]+counts[2]+counts[3])/n,4),
          "mean_keep":round(sum(records[i][v]["keep_n"] for i in records)/n,4)}
    paired={}
    for t in (1,2,3):
        x=[int(0<records[i]["plains35"]["win_turn"]<=t)-
           int(0<records[i]["current34"]["win_turn"]<=t) for i in range(n)]
        gain=x.count(1);loss=x.count(-1);delta=sum(x)/n
        se=math.sqrt(sum((a-delta)**2 for a in x)/(n-1)/n) if n>1 else 0.
        paired["by_T"+str(t)]={"delta_pp":round(100*delta,4),
             "paired_95pct_pp":[round(100*(delta-1.96*se),3),round(100*(delta+1.96*se),3)],
             "gain_only":gain,"loss_only":loss}
    result["paired_plains35_minus_current34"]=paired
    Path(out).write_text(json.dumps(result,indent=2))
    print("DACK_MAP_TO_PLAINS_POOLED_PASS",json.dumps(result),flush=True)

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--audit",action="store_true")
    a.add_argument("--shard",type=int,default=0)
    a.add_argument("--games",type=int,default=16)
    a.add_argument("--beam",type=int,default=160)
    a.add_argument("--out",default="paired.json.gz")
    a.add_argument("--pool",action="store_true")
    a.add_argument("--path",default="shards")
    a.add_argument("--expected",type=int,default=256)
    args=a.parse_args()
    audit()
    if args.audit: pass
    elif args.pool:pool(args.path,args.out,args.expected)
    else:run(args.shard,args.games,args.beam,args.out)
