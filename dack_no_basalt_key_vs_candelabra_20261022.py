#!/usr/bin/env python3
"""Basalt-free Dack: Voltaic Key vs Candelabra vs +1 Plains.

Frozen base is the Commander-legal 34-land rainbow Dack package from the
2026-10-22 four-tower matched test:
   -4 Plains + Command Tower, Mana Confluence, City of Brass, Gemstone Mine
   - Hardlight Containment, Lunarch Mantle, Basalt Monolith
   + Pentad Prism, Voltaic Key, Giant's Boulder
Moonsilver Key is retained in all three arms. Decks remain 99, singleton legal.
Use the same corrected no-tap Pentad Prism activation in every arm.
Historical full-beam paired Dack deployment, not multiplayer or full combo.
"""
from __future__ import annotations
import argparse, gzip, hashlib, json, math, time
from collections import Counter
from pathlib import Path
import dack_four_towers_key_boulder_prism_20261022 as pkg

root=pkg.root
d=pkg.d
m=pkg.m
swap=pkg.swap
BASE=pkg.LEGAL
CANDELABRA=swap(BASE,"Voltaic Key","Candelabra of Tawnos")
LAND35=swap(BASE,"Voltaic Key","Plains")
VARIANTS={"voltaic_key":BASE,
          "candelabra":CANDELABRA,
          "plains35":LAND35}
root.VARIANTS=VARIANTS
root.batch.build_deck=lambda v:VARIANTS[v]

def deck_hash(deck):return hashlib.sha256("\n".join(deck).encode()).hexdigest()

def audit():
    pkg.audit()
    assert len(VARIANTS)==3
    assert len(BASE)==len(CANDELABRA)==len(LAND35)==99
    assert Counter(CANDELABRA)-Counter(BASE)==Counter(["Candelabra of Tawnos"])
    assert Counter(BASE)-Counter(CANDELABRA)==Counter(["Voltaic Key"])
    assert Counter(LAND35)-Counter(BASE)==Counter(["Plains"])
    assert Counter(BASE)-Counter(LAND35)==Counter(["Voltaic Key"])
    for name,deck in VARIANTS.items():
        assert root.COMBO.issubset(deck)
        assert not {"Basalt Monolith","Hardlight Containment","Lunarch Mantle"}.intersection(deck)
        assert deck.count("Moonsilver Key")==1
        assert deck.count("Bucknard's Everfull Purse")==1
        assert deck.count("Coalition Relic")==1
        assert deck.count("Pentad Prism")==1
        assert deck.count("Giant's Boulder")==1
        assert deck.count("Command Tower")==1
        assert deck.count("Mana Confluence")==1
        assert deck.count("City of Brass")==1
        assert deck.count("Gemstone Mine")==1
        assert len(set(x for x in deck if x!="Plains"))==len([x for x in deck if x!="Plains"]),(name,"singleton")
        assert sum(c in d.LANDS or c in ("Emeria's Call","Razorgrass Ambush") for c in deck)==(35 if name=="plains35" else 34)
        assert not {"Mana Crypt","Jeweled Lotus"}.intersection(deck)
        root.install(name)
        assert list(d.DECK)==list(deck)
    # Legal, physical artifact vs land untap actions (same pool cost of one).
    s=d.State(1,(),(),(d.Perm("Voltaic Key",False,0,1),d.Perm("Mana Vault",True,0,1)),c=1)
    assert any(q.battlefield[0].tapped and not q.battlefield[1].tapped
               for q in d.utility_actions(s)), "Voltaic did not untap Mana Vault"
    s=d.State(1,(),(),(d.Perm("Candelabra of Tawnos",False,0,1),d.Perm("Plains",True,0,1)),c=1)
    assert any(q.battlefield[0].tapped and not q.battlefield[1].tapped
               for q in d.utility_actions(s)), "Candelabra did not untap Plains"
    s=d.State(1,(),(),(d.Perm("Candelabra of Tawnos",False,0,1),d.Perm("Ancient Tomb",True,0,1)),c=1)
    assert any(q.battlefield[0].tapped and not q.battlefield[1].tapped
               for q in d.utility_actions(s)), "Candelabra did not untap Ancient Tomb"
    # The corrected Prism remains no-tap, even without either untap artifact.
    s=d.State(1,(),(),(d.Perm("Pentad Prism",False,2,1),))
    q=[v for v in d.tap_mana_actions(s) if v.any==1 and v.battlefield[0].counters==1 and not v.battlefield[0].tapped]
    assert q and any(v.any==2 and v.battlefield[0].counters==0 for v in d.tap_mana_actions(q[0]))
    print("DACK_NO_BASALT_KEY_CANDELABRA_AUDIT_PASS",json.dumps({k:deck_hash(v) for k,v in VARIANTS.items()}),flush=True)

def run(shard,games,beam,out):
    rows=[];started=time.time()
    for i in range(games):
        gid=shard*games+i
        rec={"gid":gid}
        for v in VARIANTS:
            root.install(v);d._WIN_CACHE.clear()
            rec[v]=root.simulate(v,gid,beam)
            print("GAME",v,gid,rec[v]["win_turn"],rec[v]["keep_n"],flush=True)
        rows.append(rec)
    q={"schema":"dack_no_basalt_key_candelabra_v1",
       "shard":shard,"games":games,"beam":beam,
       "seed_base":root.batch.CONFIG["seed_base"],
       "deck_hashes":{k:deck_hash(v) for k,v in VARIANTS.items()},
       "rows":rows,"elapsed_sec":round(time.time()-started,2)}
    with gzip.open(out,"wt",encoding="utf8") as f:json.dump(q,f,separators=(",",":"))
    print("DACK_NO_BASALT_KEY_CANDELABRA_SHARD_PASS",shard,games,round(time.time()-started,2),flush=True)

def pool(path,out,expected):
    files=sorted(Path(path).rglob("*.json.gz"))
    assert files
    data={}; hashes=None; beams=set()
    for p in files:
        with gzip.open(p,"rt",encoding="utf8") as f:q=json.load(f)
        assert q["schema"]=="dack_no_basalt_key_candelabra_v1"
        assert len(q["rows"])==q["games"]
        if hashes is None:hashes=q["deck_hashes"]
        assert hashes==q["deck_hashes"]
        beams.add(q["beam"])
        for row in q["rows"]:
            gid=row["gid"];assert gid not in data
            for v in VARIANTS:
                assert row[v]["game_id"]==gid
                assert row[v]["seed"]==q["seed_base"]+gid*1000003
            data[gid]=row
    assert len(beams)==1 and set(data)==set(range(expected))
    n=len(data)
    outdoc={"status":"PASS","n_paired":n,"beam":list(beams)[0],"deck_hashes":hashes,
            "scope":"Full-beam goldfish Dack casting T1-T3; mulligan continuation sampling and oracle action selection remain potentially biased; not multiplayer win or full combo validation",
            "primary_comparison":"Candelabra of Tawnos replacing Voltaic Key in otherwise identical 34-land, Basalt-free singleton legal rainbow Dack deck; Moonsilver Key retained",
            "third_arm":"One additional Plains replacing Voltaic Key (35 nominal lands)"}
    for v in VARIANTS:
        counts=Counter(data[i][v]["win_turn"] for i in range(n))
        outdoc[v]={"counts":{str(k):counts[k] for k in range(4)},
                   **{f"by_T{t}_pct":round(100*sum(counts[k] for k in range(1,t+1))/n,4) for t in (1,2,3)},
                   "mean_keep":round(sum(data[i][v]["keep_n"] for i in range(n))/n,4)}
    paired={}
    for v in ("candelabra","plains35"):
        changes={}
        for t in (1,2,3):
            x=[int(0<data[i][v]["win_turn"]<=t)-int(0<data[i]["voltaic_key"]["win_turn"]<=t) for i in range(n)]
            wins=x.count(1);loss=x.count(-1)
            mu=(wins-loss)/n
            se=math.sqrt(sum((z-mu)**2 for z in x)/(n-1)/n) if n>1 else 0
            changes[f"by_T{t}"]={"delta_pp":round(100*mu,4),
                                 "gains":wins,"losses":loss,
                                 "paired_95pct_pp":[round(100*(mu-1.96*se),3),round(100*(mu+1.96*se),3)],
                                 "discordant_keep_diff":sum(data[i][v]["keep_n"]!=data[i]["voltaic_key"]["keep_n"] for i in range(n) if x[i]!=0)}
        paired[v+"_minus_voltaic_key"]=changes
    outdoc["paired"]=paired
    Path(out).write_text(json.dumps(outdoc,indent=2))
    print("DACK_NO_BASALT_KEY_CANDELABRA_POOLED_PASS",json.dumps(outdoc),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--games",type=int,default=8)
    p.add_argument("--beam",type=int,default=160)
    p.add_argument("--out",default="dack_key_candelabra.json.gz")
    p.add_argument("--pool",action="store_true")
    p.add_argument("--path",default="shards")
    p.add_argument("--expected",type=int,default=128)
    args=p.parse_args()
    audit()
    if args.audit:pass
    elif args.pool:pool(args.path,args.out,args.expected)
    else:run(args.shard,args.games,args.beam,args.out)
