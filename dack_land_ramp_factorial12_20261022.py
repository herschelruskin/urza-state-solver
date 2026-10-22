#!/usr/bin/env python3
"""Matched 12-variant factorial-style sweep of Boonweaver Dack land/ramp slots.

Goldfish objective: earliest valid Dack deployment, combo trio in library.
Same game seed, seat, beam=160, free multiplayer London decisions; scores
are NOT cEDH win rates. Uses Prism's audited no-tap-counter ability.
All arms singleton-legal with <=34/35 nominal lands (2 MDFCs included).
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,math,time
from collections import Counter
from pathlib import Path
import dack_no_basalt_key_vs_candelabra_20261022 as prev

root=prev.root
d=prev.d
m=prev.m
pkg=prev.pkg
swap=prev.swap
CURRENT=pkg.CURRENT
FULL=pkg.LEGAL
LAND_ONLY=pkg.replace_plains(CURRENT,pkg.LEGAL_LANDS)
RAMP_ONLY=pkg.replace_nonlands(CURRENT)
def sw(cards,a,b):return swap(cards,a,b)
VARIANTS={
 "current":CURRENT,
 "lands_only":LAND_ONLY,
 "ramp_only":RAMP_ONLY,
 "rainbow_prism_only":sw(LAND_ONLY,"Hardlight Containment","Pentad Prism"),
 "full_voltaic":FULL,
 "full_candelabra":sw(FULL,"Voltaic Key","Candelabra of Tawnos"),
 "full_plains35":sw(FULL,"Voltaic Key","Plains"),
 "full_basalt_over_boulder":sw(FULL,"Giant's Boulder","Basalt Monolith"),
 "full_basalt_over_prism":sw(FULL,"Pentad Prism","Basalt Monolith"),
 "full_candelabra_over_prism":sw(FULL,"Pentad Prism","Candelabra of Tawnos"),
 "full_both_keys_candelabra":sw(FULL,"Giant's Boulder","Candelabra of Tawnos"),
 "full_basalt_extra_tooth":sw(FULL,"Tooth of Ramos","Basalt Monolith"),
}
root.VARIANTS=VARIANTS
root.batch.build_deck=lambda variant:VARIANTS[variant]

def sha(cards):return hashlib.sha256("\n".join(cards).encode()).hexdigest()
def diff(base,other):
    return {"out":sorted((Counter(base)-Counter(other)).elements()),
            "in":sorted((Counter(other)-Counter(base)).elements())}

def audit():
    assert len(VARIANTS)==12 and len(CURRENT)==len(FULL)==99
    assert CURRENT.count("Plains")==10
    assert FULL.count("Plains")==6
    assert "World Map" in CURRENT and "Bucknard's Everfull Purse" in CURRENT
    seen_hashes=set()
    for v,cards in VARIANTS.items():
        assert len(cards)==99 and root.COMBO.issubset(cards),v
        assert len(set(x for x in cards if x!="Plains")) == len([x for x in cards if x!="Plains"]),v
        assert not {"Mana Crypt","Jeweled Lotus"}.intersection(cards),v
        assert cards.count("Bucknard's Everfull Purse")==1 and cards.count("Coalition Relic")==1,v
        assert cards.count("Moonsilver Key")==1,v
        assert sum(x in d.LANDS or x in ("Emeria's Call","Razorgrass Ambush") for x in cards)==(35 if v=="full_plains35" else 34),v
        assert (cards.count("Command Tower")==0 if v=="current" or v=="ramp_only" else cards.count("Command Tower")==1),v
        assert cards.count("World Map")==1,v
        root.install(v)
        assert len(d.DECK)==99 and all(x in d.CARD_ID for x in d.DECK),v
        seen_hashes.add(sha(cards))
    assert len(seen_hashes)==12,"duplicate deck candidate"
    assert diff(CURRENT, FULL)["out"]==sorted(["Plains"]*4+["Hardlight Containment","Lunarch Mantle","Basalt Monolith"])
    assert diff(CURRENT, FULL)["in"]==sorted(list(pkg.LEGAL_LANDS)+["Pentad Prism","Voltaic Key","Giant's Boulder"])
    s=d.State(1,(),(),(d.Perm("Pentad Prism",False,2,1),))
    first=[q for q in d.tap_mana_actions(s) if q.any==1 and q.battlefield[0].counters==1 and not q.battlefield[0].tapped]
    assert first and any(q.any==2 and q.battlefield[0].counters==0 for q in d.tap_mana_actions(first[0]))
    assert root.batch.CONFIG["lambda"]==0.5
    print("DACK_FACTORIAL12_AUDIT_PASS",json.dumps({k:sha(v) for k,v in VARIANTS.items()}),flush=True)

def run(shard,games,beam,out):
    rows=[];start=time.time()
    for j in range(games):
        gid=shard*games+j
        rec={"gid":gid}
        for arm in VARIANTS:
            root.install(arm)
            d._WIN_CACHE.clear()
            rec[arm]=root.simulate(arm,gid,beam)
            print("FACTORIAL_GAME",arm,gid,rec[arm]["win_turn"],rec[arm]["keep_n"],flush=True)
        rows.append(rec)
    doc={"schema":"dack_factorial12_20261022_v1","shard":shard,"games":games,
        "beam":beam,"seed_base":root.batch.CONFIG["seed_base"],
        "deck_hashes":{k:sha(v) for k,v in VARIANTS.items()},
        "rows":rows,"elapsed_seconds":round(time.time()-start,1)}
    with gzip.open(out,"wt",encoding="utf8") as f:json.dump(doc,f,separators=(",",":"))
    print("FACTORIAL12_SHARD_PASS",shard,games,len(rows),flush=True)

def pool(path,out,expected):
    files=sorted(Path(path).rglob("*.json.gz"))
    assert files
    records={};hashes=None;beams=set()
    for path in files:
        with gzip.open(path,"rt",encoding="utf8") as f:doc=json.load(f)
        assert doc["schema"]=="dack_factorial12_20261022_v1"
        assert len(doc["rows"])==doc["games"]
        if hashes is None:hashes=doc["deck_hashes"]
        assert hashes==doc["deck_hashes"]
        beams.add(doc["beam"])
        for rec in doc["rows"]:
            gid=rec["gid"];assert gid not in records
            for v in VARIANTS:
                assert rec[v]["game_id"]==gid
                assert rec[v]["seed"]==doc["seed_base"]+gid*1000003
            records[gid]=rec
    assert len(beams)==1 and set(records)==set(range(expected)),(len(records),expected)
    n=len(records)
    report={"status":"PASS","n_paired":n,"beam":next(iter(beams)),
        "scope":"Historical full-beam Dack deployment only; no multiplayer or post-Dack combo validation; mulligan sampling plus oracle limitations remain; 12 exploratory candidates require confirmation on held-out seeds",
        "reference":"current", "hashes":hashes,
        "variants":{},"paired_vs_current":{},"paired_vs_full_voltaic":{}}
    for v,deck in VARIANTS.items():
        counts=Counter(records[i][v]["win_turn"] for i in range(n))
        report["variants"][v]={"changes_vs_current":diff(CURRENT,deck),
              "counts":{str(j):counts[j] for j in range(4)},
              "by_T1_pct":round(100*counts[1]/n,4),
              "by_T2_pct":round(100*(counts[1]+counts[2])/n,4),
              "by_T3_pct":round(100*(counts[1]+counts[2]+counts[3])/n,4),
              "weighted_T2_half_T3_pct":round(100*(counts[1]+counts[2]+0.5*counts[3])/n,4),
              "mean_keep":round(sum(records[i][v]["keep_n"] for i in range(n))/n,4)}
    def pair(v,base):
        out={}
        for t in (1,2,3):
            vals=[int(0<records[i][v]["win_turn"]<=t)-int(0<records[i][base]["win_turn"]<=t) for i in range(n)]
            wins=vals.count(1);losses=vals.count(-1);m=(wins-losses)/n
            se=math.sqrt(sum((z-m)**2 for z in vals)/(n-1)/n)
            out["T"+str(t)]={"delta_pp":round(100*m,4),"gains":wins,"losses":losses,
                "paired_95_ci_pp":[round(100*(m-1.96*se),3),round(100*(m+1.96*se),3)],
                "discordant_keep_size_changed":sum(records[i][v]["keep_n"]!=records[i][base]["keep_n"] for i in range(n) if vals[i])}
        return out
    for v in VARIANTS:
        if v!="current":report["paired_vs_current"][v]=pair(v,"current")
        if v!="full_voltaic":report["paired_vs_full_voltaic"][v]=pair(v,"full_voltaic")
    rank=sorted(VARIANTS,key=lambda v:(-report["variants"][v]["by_T2_pct"],
       -report["variants"][v]["weighted_T2_half_T3_pct"],-report["variants"][v]["by_T3_pct"],v))
    report["ranking_by_T2_then_weighted"]=rank
    Path(out).write_text(json.dumps(report,indent=2)+"\n")
    print("DACK_FACTORIAL12_POOL_PASS",json.dumps({"n":n,"ranking":rank,"top":{k:report["variants"][k] for k in rank[:5]}}),flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--audit",action="store_true")
    parser.add_argument("--shard",type=int,default=0)
    parser.add_argument("--games",type=int,default=4)
    parser.add_argument("--beam",type=int,default=160)
    parser.add_argument("--out",default="factorial12.json.gz")
    parser.add_argument("--pool",action="store_true")
    parser.add_argument("--path",default="shards")
    parser.add_argument("--expected",type=int,default=64)
    a=parser.parse_args()
    audit()
    if a.audit:pass
    elif a.pool:pool(a.path,a.out,a.expected)
    else:run(a.shard,a.games,a.beam,a.out)
