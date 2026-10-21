#!/usr/bin/env python3
"""Exact current99 vs three Plains + Voltaic Key paired Dack deployment test.

Current list is Oct 16 original minus Smothering Tithe/United Battlefront,
plus Bucknard's Everfull Purse/Coalition Relic.
Four swaps: Urza's Cave, Emergence Zone, Fomori Vault -> 3 Plains;
World Map -> Voltaic Key. No other card changes.
"""
from __future__ import annotations
import argparse, gzip, hashlib, json, math, time
from pathlib import Path
from collections import Counter
import dack_bucknard_minimal_swaps_20261016 as buck
root=buck.root
d=root.d
m=root.m

def swap(deck, old, new):
    a=list(deck)
    assert a.count(old)==1,(old,a.count(old))
    a[a.index(old)]=new
    return tuple(a)

CURRENT=swap(swap(root.CURRENT,"Smothering Tithe","Bucknard's Everfull Purse"),
             "United Battlefront","Coalition Relic")
PROPOSED=CURRENT
for old in ("Urza's Cave","Emergence Zone","Fomori Vault"):
    PROPOSED=swap(PROPOSED,old,"Plains")
PROPOSED=swap(PROPOSED,"World Map","Voltaic Key")
VARIANTS={"current":CURRENT,"three_plains_voltaic":PROPOSED}
root.VARIANTS=VARIANTS
root.batch.build_deck=lambda variant:VARIANTS[variant]

def sha(deck):return hashlib.sha256("\n".join(deck).encode()).hexdigest()

def audit():
    assert len(CURRENT)==len(PROPOSED)==99
    assert CURRENT.count("Plains")==10 and PROPOSED.count("Plains")==13
    assert CURRENT.count("Bucknard's Everfull Purse")==PROPOSED.count("Bucknard's Everfull Purse")==1
    assert CURRENT.count("Coalition Relic")==PROPOSED.count("Coalition Relic")==1
    assert CURRENT.count("World Map")==1 and not PROPOSED.count("World Map")
    assert PROPOSED.count("Voltaic Key")==1 and not CURRENT.count("Voltaic Key")
    assert Counter(PROPOSED)-Counter(CURRENT)==Counter({"Plains":3,"Voltaic Key":1})
    assert Counter(CURRENT)-Counter(PROPOSED)==Counter({"Urza's Cave":1,"Emergence Zone":1,"Fomori Vault":1,"World Map":1})
    assert root.COMBO.issubset(CURRENT) and root.COMBO.issubset(PROPOSED)
    assert not {"Mana Crypt","Jeweled Lotus"}.intersection(CURRENT)
    for variant in VARIANTS:
        m.set_deck(VARIANTS[variant])
        assert len(d.DECK)==99
        assert all(x in d.CARD_ID for x in d.DECK),(variant,[x for x in d.DECK if x not in d.CARD_ID])
    assert d.COSTS["Voltaic Key"]==(1,0,0)
    assert d.is_artifact_perm("Voltaic Key")
    assert d.COSTS["Bucknard's Everfull Purse"]==(2,0,0)
    assert root.batch.CONFIG["lambda"]==0.5
    print("DACK_EXACT99_PLAINS_KEY_AUDIT_PASS",sha(CURRENT),sha(PROPOSED),flush=True)

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
            print("PAIRED_GAME",variant,gid,rows[variant]["win_turn"],rows[variant]["keep_n"],flush=True)
        records.append({"game_id":gid,"current":rows["current"],"three_plains_voltaic":rows["three_plains_voltaic"]})
    payload={"schema":"dack_three_plains_voltaic_paired_v1","games":games,"shard":shard,"beam":beam,
             "deck_sha":{x:sha(v) for x,v in VARIANTS.items()},
             "seed_base":root.batch.CONFIG["seed_base"],"records":records,"elapsed_sec":round(time.time()-start,2)}
    with gzip.open(out,"wt",encoding="utf8") as f:json.dump(payload,f,separators=(",",":"))
    print("PAIRED_SHARD_PASS",games,shard,round(time.time()-start,2),flush=True)

def pool(path,out,expected):
    files=sorted(Path(path).glob("*.json.gz")); assert files,("no files",path)
    records={}; hashes=None; beams=set()
    for p in files:
        with gzip.open(p,"rt",encoding="utf8") as f:q=json.load(f)
        assert q["schema"]=="dack_three_plains_voltaic_paired_v1"
        if hashes is None:hashes=q["deck_sha"]
        assert q["deck_sha"]==hashes and q["games"]==len(q["records"])
        beams.add(q["beam"])
        for rec in q["records"]:
            gid=rec["game_id"];assert gid not in records
            for v in VARIANTS:
                assert rec[v]["game_id"]==gid
                assert rec[v]["seed"]==q["seed_base"]+gid*1000003
            records[gid]=rec
    assert len(beams)==1 and len(records)==expected
    assert set(records)==set(range(expected)),(sorted(records)[:10],len(records))
    result={"status":"PASS","n_paired":len(records),"beam":list(beams)[0],
            "deck_sha":hashes,"scope":"historical full-beam Dack cast with all combo creatures in library, not live game winrate"}
    for v in VARIANTS:
        times=Counter(records[i][v]["win_turn"] for i in records)
        n=len(records)
        result[v]={"counts":dict(sorted(times.items())),
                   "by_T1_pct":100*times[1]/n,
                   "by_T2_pct":100*(times[1]+times[2])/n,
                   "by_T3_pct":100*(times[1]+times[2]+times[3])/n,
                   "mean_keep":sum(records[i][v]["keep_n"] for i in records)/n}
    paired={}
    n=len(records)
    for t in (1,2,3):
        differences=[int(0<records[i]["three_plains_voltaic"]["win_turn"]<=t)-
                     int(0<records[i]["current"]["win_turn"]<=t) for i in range(n)]
        gain=differences.count(1);loss=differences.count(-1);delta=sum(differences)/n
        se=math.sqrt(sum((x-delta)**2 for x in differences)/(n-1)/n) if n>1 else 0
        paired[f"by_T{t}"]={"delta_pp":round(100*delta,4),
            "paired_95pct_pp":[round(100*(delta-1.96*se),3),round(100*(delta+1.96*se),3)],
            "gain_only":gain,"loss_only":loss}
    result["paired"]=paired
    Path(out).write_text(json.dumps(result,indent=2))
    print("DACK_THREE_PLAINS_VOLTAIC_POOLED_PASS",json.dumps(result),flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",action="store_true")
    ap.add_argument("--shard",type=int,default=0)
    ap.add_argument("--games",type=int,default=8)
    ap.add_argument("--beam",type=int,default=160)
    ap.add_argument("--out",default="paired.json.gz")
    ap.add_argument("--pool",action="store_true")
    ap.add_argument("--path",default="shards")
    ap.add_argument("--expected",type=int,default=64)
    a=ap.parse_args()
    audit()
    if a.audit:pass
    elif a.pool:pool(a.path,a.out,a.expected)
    else:run(a.shard,a.games,a.beam,a.out)
