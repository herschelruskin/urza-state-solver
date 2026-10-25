#!/usr/bin/env python3
"""Broad Dack speed-lever screen: 16 singleton-legal 99-card configurations.

Tests distinct speed hypotheses rather than re-running the near-identical
Basalt/Boulder 12-arm screen: multiple untap engines, mana conversions,
colored land substitution, 35/36 land counts, and alternative cheap spells.

All variants share independent game IDs and the same free multiplayer London
solver; outcomes are Dack casts by T1/2/3 with combo creatures in library,
not cEDH wins. Historical full beam leaks future info. Protective spell
cuts (Mana Tithe) are speed-only counterfactuals, not deck recommendations.

Sunburst patch: Pentad Prism removes charge counters without tapping.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,math,time
from collections import Counter
from pathlib import Path
import dack_land_ramp_factorial12_20261022 as study

root=study.root
d=study.d
m=study.m
SW=study.sw
CURRENT=study.CURRENT
FULL_BASALT=study.VARIANTS["full_basalt_over_boulder"]

def from_current(*pairs):
    deck=CURRENT
    for old,new in pairs:deck=SW(deck,old,new)
    return deck

def white_utility(deck):
    for old,new in (("Urza's Cave","Mana Confluence"),
                    ("Emergence Zone","City of Brass"),
                    ("Fomori Vault","Gemstone Mine")):
        deck=SW(deck,old,new)
    return deck

VARIANTS={
 "current":CURRENT,
 "full_basalt_rainbow":FULL_BASALT,
 "double_key":from_current(("Hardlight Containment","Voltaic Key"),("Lunarch Mantle","Manifold Key")),
 "voltaic_candelabra":from_current(("Hardlight Containment","Voltaic Key"),("Lunarch Mantle","Candelabra of Tawnos")),
 "voltaic_prism":from_current(("Hardlight Containment","Voltaic Key"),("Lunarch Mantle","Pentad Prism")),
 "voltaic_boulder":from_current(("Hardlight Containment","Voltaic Key"),("Lunarch Mantle","Giant's Boulder")),
 "voltaic_kozilek":from_current(("Hardlight Containment","Voltaic Key"),("Lunarch Mantle","Kozilek's Command")),
 "voltaic_helm":from_current(("Hardlight Containment","Voltaic Key"),("Lunarch Mantle","Helm of Awakening")),
 "voltaic_sonic":from_current(("Hardlight Containment","Voltaic Key"),("Lunarch Mantle","Sonic Screwdriver")),
 "three_untappers":from_current(("Hardlight Containment","Voltaic Key"),("Lunarch Mantle","Manifold Key"),("Mana Tithe","Candelabra of Tawnos")),
 "triple_prism_keys":from_current(("Hardlight Containment","Voltaic Key"),("Lunarch Mantle","Manifold Key"),("Mana Tithe","Pentad Prism")),
 "white_utility_only":white_utility(CURRENT),
 "white_utility_double_key":white_utility(from_current(("Hardlight Containment","Voltaic Key"),("Lunarch Mantle","Manifold Key"))),
 "land35":from_current(("Hardlight Containment","Plains")),
 "land36":from_current(("Hardlight Containment","Plains"),("Lunarch Mantle","Plains")),
 "land35_voltaic":from_current(("Hardlight Containment","Plains"),("Lunarch Mantle","Voltaic Key")),
}

SEED_BASE=202610250122
root.batch.CONFIG["seed_base"]=SEED_BASE
root.VARIANTS=VARIANTS
root.batch.build_deck=lambda v:VARIANTS[v]
def sha(cards):return hashlib.sha256("\n".join(cards).encode()).hexdigest()

def audit():
    assert len(VARIANTS)==16 and len(set(VARIANTS))==16
    hashes=set()
    for v,cards in VARIANTS.items():
        assert len(cards)==99 and root.COMBO.issubset(cards),v
        nonbasics=[x for x in cards if x!="Plains"]
        assert len(nonbasics)==len(set(nonbasics)),v
        assert not {"Jeweled Lotus","Mana Crypt"}.intersection(cards),v
        assert cards.count("Bucknard's Everfull Purse")==1 and cards.count("Coalition Relic")==1,v
        assert cards.count("Moonsilver Key")==1 and cards.count("World Map")==1,v
        assert cards.count("Plains") in (6,10,11,12),v
        nominal=sum(c in d.LANDS or c in ("Emeria's Call","Razorgrass Ambush") for c in cards)
        assert nominal in (34,35,36),(v,nominal)
        root.install(v)
        assert len(d.DECK)==99 and all(c in d.CARD_ID for c in d.DECK),v
        hashes.add(sha(cards))
    assert len(hashes)==len(VARIANTS),"duplicate variants"
    assert root.batch.CONFIG["lambda"]==0.5
    assert d.COSTS["Kozilek's Command"]==(0,0,2)
    assert d.COSTS["Voltaic Key"]==(1,0,0)
    assert d.COSTS["Manifold Key"]==(1,0,0)
    assert d.COSTS["Giant's Boulder"]==(1,0,0)
    assert d.COSTS["Helm of Awakening"]==(2,0,0)
    s=d.State(1,(),(),(d.Perm("Pentad Prism",False,2,1),))
    q=[x for x in d.tap_mana_actions(s) if x.any==1 and x.battlefield[0].counters==1 and not x.battlefield[0].tapped]
    assert q and any(x.any==2 and x.battlefield[0].counters==0 for x in d.tap_mana_actions(q[0]))
    print("DACK_BROAD16_AUDIT_PASS",json.dumps({k:sha(v) for k,v in VARIANTS.items()}),flush=True)

def run(shard,games,beam,out):
    rows=[];start=time.time()
    for k in range(games):
        gid=shard*games+k
        row={"gid":gid}
        for name in VARIANTS:
            root.install(name);d._WIN_CACHE.clear()
            row[name]=root.simulate(name,gid,beam)
            print("BROAD_GAME",name,gid,row[name]["win_turn"],row[name]["keep_n"],flush=True)
        rows.append(row)
    report={"schema":"dack_broad_16_v1","shard":shard,"games":games,
            "beam":beam,"seed_base":SEED_BASE,
            "deck_hashes":{k:sha(v) for k,v in VARIANTS.items()},
            "rows":rows,"runtime_sec":round(time.time()-start,2)}
    with gzip.open(out,"wt",encoding="utf8") as f:json.dump(report,f,separators=(",",":"))
    print("BROAD16_SHARD_PASS",shard,games,round(time.time()-start,2),flush=True)

def pool(path,out,expected):
    files=sorted(Path(path).rglob("*.json.gz"));assert files
    rows={};hashes=None;beams=set()
    for f in files:
        with gzip.open(f,"rt",encoding="utf8") as h:q=json.load(h)
        assert q["schema"]=="dack_broad_16_v1" and q["seed_base"]==SEED_BASE
        if hashes is None:hashes=q["deck_hashes"]
        assert hashes==q["deck_hashes"]
        beams.add(q["beam"]);assert len(q["rows"])==q["games"]
        for x in q["rows"]:
            gid=x["gid"];assert gid not in rows
            for v in VARIANTS:
                assert x[v]["game_id"]==gid and x[v]["seed"]==SEED_BASE+gid*1000003
            rows[gid]=x
    assert len(beams)==1 and set(rows)==set(range(expected))
    n=len(rows)
    r={"status":"PASS","n_paired":n,"beam":next(iter(beams)),
       "seed_base":SEED_BASE,"deck_hashes":hashes,
       "scope":"16-arm exploratory full-beam T1-T3 Dack cast goldfish; not real-play game wins; chance/mulligan oracle inaccuracies; speed-only tests include protection spell cuts; screen winner requires held-out confirmation",
       "variants":{},"paired_vs_current":{}}
    for v,cards in VARIANTS.items():
        c=Counter(rows[i][v]["win_turn"] for i in range(n))
        r["variants"][v]={"in":sorted((Counter(cards)-Counter(CURRENT)).elements()),
           "out":sorted((Counter(CURRENT)-Counter(cards)).elements()),
           "counts":{str(k):c[k] for k in range(4)},
           "by_T1_pct":round(c[1]*100/n,4),
           "by_T2_pct":round((c[1]+c[2])*100/n,4),
           "by_T3_pct":round((c[1]+c[2]+c[3])*100/n,4),
           "T2_plus_half_T3_pct":round((c[1]+c[2]+.5*c[3])*100/n,4),
           "mean_keep":round(sum(rows[i][v]["keep_n"] for i in range(n))/n,4)}
        if v=="current":continue
        metrics={}
        for t in (1,2,3):
            delta=[int(0<rows[i][v]["win_turn"]<=t)-int(0<rows[i]["current"]["win_turn"]<=t) for i in range(n)]
            plus=delta.count(1);minus=delta.count(-1);mu=(plus-minus)/n
            se=math.sqrt(sum((x-mu)**2 for x in delta)/(n-1)/n)
            metrics["T"+str(t)]={"delta_pp":round(mu*100,4),"gains":plus,"losses":minus,
                "paired_95_ci_pp":[round(100*(mu-1.96*se),3),round(100*(mu+1.96*se),3)],
                "discordant_changed_keep_size":sum(rows[i][v]["keep_n"]!=rows[i]["current"]["keep_n"] for i in range(n) if delta[i])}
        r["paired_vs_current"][v]=metrics
    r["ranking_by_T2"]=sorted(VARIANTS,key=lambda v:(-r["variants"][v]["by_T2_pct"],
        -r["variants"][v]["T2_plus_half_T3_pct"],v))
    Path(out).write_text(json.dumps(r,indent=2)+"\n")
    print("DACK_BROAD16_POOL_PASS",json.dumps({"n":n,"ranking":r["ranking_by_T2"],"top":{v:r["variants"][v] for v in r["ranking_by_T2"][:6]}}),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--games",type=int,default=4)
    p.add_argument("--beam",type=int,default=160)
    p.add_argument("--out",default="broad16.json.gz")
    p.add_argument("--pool",action="store_true")
    p.add_argument("--path",default="shards")
    p.add_argument("--expected",type=int,default=64)
    a=p.parse_args()
    audit()
    if a.audit:pass
    elif a.pool:pool(a.path,a.out,a.expected)
    else:run(a.shard,a.games,a.beam,a.out)
