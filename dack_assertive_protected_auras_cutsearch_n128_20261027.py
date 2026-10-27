#!/usr/bin/env python3
"""Assertive locked-aura World Map / Staff / Basalt / Tooth / Plains cut search.

32 predeclared singleton-legal 99-card variants; both Hardlight Containment
and Lunarch Mantle remain in ALL arms. 128 independently seeded matched games
per arm, beam 160, free multiplayer London, Assertive keep thresholds.

Primary outcome is Dack CAST by T2, not proof of full Boonweaver ETB combo.
The cut search explicitly tests Staff of Compleation rather than assuming
its versatile role is negligible. Multiple comparisons: all results exploratory.
Every *complete* matched game is fsynced, shard artifacts archived, strict pool.
"""
from __future__ import annotations
import argparse, collections, gzip, json, math, os, time
from pathlib import Path
import dack_active_mulligan_policy as sim
import dack_assertive_ramp_land_key_screen_n256_20261026 as earlier

SCHEMA="dack_assertive_protected_auras_cutsearch_n128_v1"
SEED_BASE=99142710270201
POLICY="assertive"
BEAM=160
N=128
PER_SHARD=4
CURRENT=tuple(sim.FROZEN_DECK)
RAINBOW=tuple(earlier.RAINBOW_ONLY)
LOCKED=frozenset(("Hardlight Containment","Lunarch Mantle"))
CUTS=("World Map","Basalt Monolith","Tooth of Ramos","Staff of Compleation")
ACCEL=("Voltaic Key","Manifold Key","Pentad Prism","Giant's Boulder")

def replace(deck,pairs):
    a=list(deck)
    for old,new in pairs:
        assert old in a,(old,new)
        if old!="Plains":assert a.count(old)==1,(old,new)
        if new!="Plains":assert new not in a,(old,new,"illegal extra copy")
        a[a.index(old)]=new
    return tuple(a)

def set_cards(base,label,outs=(),ins=()):
    assert len(outs)==len(ins),(label,outs,ins)
    assert label not in VARIANTS,label
    VARIANTS[label]=replace(base,tuple(zip(outs,ins)))

VARIANTS={}
set_cards(CURRENT,"current")
set_cards(RAINBOW,"four_rainbow")
for base_name,deck in (("current",CURRENT),("rainbow",RAINBOW)):
    for into in ("Voltaic Key","Manifold Key","Pentad Prism","Giant's Boulder","Plains"):
        nm=into.lower().replace(" ","_").replace("'","")
        set_cards(deck,base_name+"_map_to_"+nm,("World Map",),(into,))
for source in ("Basalt Monolith","Tooth of Ramos","Staff of Compleation"):
    for dest in ("Voltaic Key","Pentad Prism"):
        nm=source.lower().replace(" ","_")
        dnm=dest.lower().replace(" ","_")
        set_cards(RAINBOW,"rainbow_"+nm+"_to_"+dnm,(source,),(dest,))
for label,outs,ins in (
    ("rainbow_map_basalt_to_voltaic_prism",
      ("World Map","Basalt Monolith"),("Voltaic Key","Pentad Prism")),
    ("rainbow_map_basalt_to_voltaic_boulder",
      ("World Map","Basalt Monolith"),("Voltaic Key","Giant's Boulder")),
    ("rainbow_map_tooth_to_voltaic_prism",
      ("World Map","Tooth of Ramos"),("Voltaic Key","Pentad Prism")),
    ("rainbow_map_staff_to_voltaic_prism",
      ("World Map","Staff of Compleation"),("Voltaic Key","Pentad Prism")),
    ("rainbow_map_basalt_to_voltaic_manifold",
      ("World Map","Basalt Monolith"),("Voltaic Key","Manifold Key")),
    ("rainbow_map_basalt_to_prism_boulder",
      ("World Map","Basalt Monolith"),("Pentad Prism","Giant's Boulder")),
    ("rainbow_map_basalt_tooth_to_voltaic_prism_boulder",
      ("World Map","Basalt Monolith","Tooth of Ramos"),
      ("Voltaic Key","Pentad Prism","Giant's Boulder")),
    ("rainbow_map_tooth_staff_to_voltaic_prism_boulder",
      ("World Map","Tooth of Ramos","Staff of Compleation"),
      ("Voltaic Key","Pentad Prism","Giant's Boulder")),
    ("rainbow_map_basalt_staff_to_voltaic_prism_boulder",
      ("World Map","Basalt Monolith","Staff of Compleation"),
      ("Voltaic Key","Pentad Prism","Giant's Boulder")),
    ("rainbow_map_basalt_tooth_to_voltaic_manifold_boulder",
      ("World Map","Basalt Monolith","Tooth of Ramos"),
      ("Voltaic Key","Manifold Key","Giant's Boulder")),
    ("rainbow_map_basalt_tooth_to_voltaic_manifold_prism",
      ("World Map","Basalt Monolith","Tooth of Ramos"),
      ("Voltaic Key","Manifold Key","Pentad Prism")),
    ("rainbow_map_basalt_tooth_staff_to_voltaic_manifold_prism_boulder",
      ("World Map","Basalt Monolith","Tooth of Ramos","Staff of Compleation"),
      ("Voltaic Key","Manifold Key","Pentad Prism","Giant's Boulder")),
    ("rainbow_33land_full_four_standalone_keepers",
      ("World Map","Basalt Monolith","Tooth of Ramos","Plains"),
      ("Voltaic Key","Manifold Key","Pentad Prism","Giant's Boulder")),
    ("rainbow_35land_voltaic_manifold_prism",
      ("World Map","Basalt Monolith","Tooth of Ramos","Staff of Compleation"),
      ("Voltaic Key","Manifold Key","Pentad Prism","Plains")),
):
    set_cards(RAINBOW,label,outs,ins)

EXPECTED_ARMS=32
assert len(VARIANTS)==EXPECTED_ARMS,(len(VARIANTS),list(VARIANTS))
sim.configure_variants(VARIANTS)

def nominal(deck):
    return sum(x in sim.d.LANDS or x in ("Emeria's Call","Razorgrass Ambush") for x in deck)

def diff(deck):
    a,b=collections.Counter(CURRENT),collections.Counter(deck)
    return {"removed":sorted((a-b).elements()),"added":sorted((b-a).elements())}

def audit():
    assert POLICY==sim.ACTIVE_POLICY and sim.GAMEPLAY_BEAM==BEAM
    assert CURRENT==sim.FROZEN_DECK and CURRENT==earlier.CUR
    assert LOCKED.issubset(CURRENT) and LOCKED.issubset(RAINBOW)
    assert SEED_BASE not in (sim.DEFAULT_SEED_BASE,earlier.SEED_BASE)
    assert N==PER_SHARD*32 and len(VARIANTS)==EXPECTED_ARMS
    assert len({sim.deck_hash(x) for x in VARIANTS.values()})==EXPECTED_ARMS
    assert nominal(CURRENT)==34 and nominal(RAINBOW)==34
    assert {nominal(v) for v in VARIANTS.values()}=={33,34,35}
    for name,deck in VARIANTS.items():
        assert len(deck)==99 and LOCKED.issubset(deck),name
        assert sim.root.COMBO.issubset(deck),name
        assert not {"Mana Crypt","Jeweled Lotus"}.intersection(deck),name
        nonbasics=[x for x in deck if x!="Plains"]
        assert len(nonbasics)==len(set(nonbasics)),name
        assert deck.count("Command Tower")<=1,name
        assert all(x in sim.d.CARD_ID for x in deck),name
        assert deck.count("Bucknard's Everfull Purse")==1,name
        assert deck.count("Moonsilver Key")==1,name
        assert deck.count("Coalition Relic")==1,name
        assert nominal(deck) in (33,34,35),name
    assert CURRENT.count("World Map")==1 and CURRENT.count("Staff of Compleation")==1
    assert "Staff of Compleation" in VARIANTS["rainbow_33land_full_four_standalone_keepers"]
    assert "Staff of Compleation" not in VARIANTS["rainbow_map_basalt_tooth_staff_to_voltaic_manifold_prism_boulder"]
    for x in ("Command Tower","Mana Confluence","City of Brass","Gemstone Mine"):
        assert RAINBOW.count(x)==1
    # Critical corrected artifact mana activation and untap availability.
    sim.root.install("rainbow_map_basalt_to_voltaic_prism")
    d=sim.d
    p=d.State(1,(),(),(d.Perm("Pentad Prism",False,2,1),))
    once=[s for s in d.tap_mana_actions(p) if s.any==1 and s.battlefield[0].counters==1 and not s.battlefield[0].tapped]
    assert once and any(s.any==2 and s.battlefield[0].counters==0 for s in d.tap_mana_actions(once[0]))
    key=d.State(1,(),(),(d.Perm("Voltaic Key",False,0,1),d.Perm("Mana Vault",True,0,1)),c=1)
    assert any(s.battlefield[0].tapped and not s.battlefield[1].tapped for s in d.utility_actions(key))
    sim.configure_variants(VARIANTS)
    print("PROTECTED_AURAS_32_CUTSEARCH_AUDIT_PASS",json.dumps({
      "n":N,"arms":EXPECTED_ARMS,"policy":POLICY,"seed_base":SEED_BASE,
      "locked":sorted(LOCKED),"hashes":{name:sim.deck_hash(deck) for name,deck in VARIANTS.items()},
      "swaps":{name:diff(deck) for name,deck in VARIANTS.items()},
      "lands":{name:nominal(deck) for name,deck in VARIANTS.items()}}),flush=True)

def smoke():
    audit()
    for name in ("current","four_rainbow","rainbow_map_staff_to_voltaic_prism",
        "rainbow_map_basalt_tooth_staff_to_voltaic_manifold_prism_boulder",
        "rainbow_33land_full_four_standalone_keepers"):
        sim.reset_caches()
        q=sim.simulate(name,99199,policy=POLICY,seed_base=SEED_BASE,beam=BEAM)
        assert q["policy"]==POLICY and q["deck_hash"]==sim.deck_hash(VARIANTS[name])
        assert 0<=q["win_turn"]<=3
        print("PROTECTED_AURAS_SMOKE",name,q["win_turn"],q["keep_n"],flush=True)

def run(shard,games,out):
    audit()
    assert games==PER_SHARD and 0<=shard<N//PER_SHARD
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    cp=Path(str(out).replace(".json.gz",".jsonl"))
    first=shard*PER_SHARD
    records=[]
    if cp.exists():
        records=[json.loads(line) for line in cp.read_text().splitlines() if line.strip()]
        assert all(x["gid"]==first+k and set(x["arms"])==set(VARIANTS)
                   for k,x in enumerate(records))
    if out.exists() and len(records)==PER_SHARD:
        print("PROTECTED_SHARD_ALREADY_COMPLETE",shard);return
    with cp.open("a",encoding="utf8") as f:
        for k in range(len(records),PER_SHARD):
            gid=first+k;arms={}
            for name,deck in VARIANTS.items():
                sim.reset_caches()
                rec=sim.simulate(name,gid,policy=POLICY,seed_base=SEED_BASE,beam=BEAM)
                assert rec["seed"]==SEED_BASE+gid*1000003
                assert rec["deck_hash"]==sim.deck_hash(deck)
                assert rec["policy"]==POLICY
                arms[name]={"turn":rec["win_turn"],"keep_n":rec["keep_n"],
                            "seed":rec["seed"],"seat":rec["seat"]}
            assert len({v["seat"] for v in arms.values()})==1
            row={"gid":gid,"arms":arms}
            f.write(json.dumps(row,separators=(",",":"))+"\n")
            f.flush();os.fsync(f.fileno())
            records.append(row)
            print("PROTECTED_AURAS_GAME_COMPLETE",gid," ".join(f"{x}={arms[x]['turn']}" for x in VARIANTS),flush=True)
    payload={"schema":SCHEMA,"policy":POLICY,"shard":shard,"games":PER_SHARD,
        "seed_base":SEED_BASE,"beam":BEAM,"locked":sorted(LOCKED),
        "hashes":{k:sim.deck_hash(v) for k,v in VARIANTS.items()},"rows":records}
    tmp=Path(str(out)+".tmp")
    with tmp.open("wb") as file:
        with gzip.GzipFile(filename="",mode="wb",fileobj=file,mtime=0) as z:
            z.write(json.dumps(payload,separators=(",",":")).encode())
        file.flush();os.fsync(file.fileno())
    os.replace(tmp,out)
    print("PROTECTED_AURAS_SHARD_PASS",shard,len(records),flush=True)

def pair(a,b,rows,turn):
    delta=[int(0<r["arms"][b]["turn"]<=turn)-int(0<r["arms"][a]["turn"]<=turn) for r in rows]
    n=len(delta);mean=sum(delta)/n
    se=math.sqrt(sum((x-mean)**2 for x in delta)/((n-1)*n)) if n>1 else 0
    return {"delta_pp":round(mean*100,4),"gains":delta.count(1),"losses":delta.count(-1),
        "paired_95_ci_pp":[round(100*(mean-1.96*se),3),round(100*(mean+1.96*se),3)]}

def pool(path,out):
    audit()
    found={}
    files=sorted(Path(path).rglob("protected_shard_*.json.gz"))
    hashes={name:sim.deck_hash(deck) for name,deck in VARIANTS.items()}
    for fp in files:
        with gzip.open(fp,"rt",encoding="utf8") as f:doc=json.load(f)
        assert doc["schema"]==SCHEMA and doc["seed_base"]==SEED_BASE
        assert doc["policy"]==POLICY and doc["beam"]==BEAM
        assert doc["locked"]==sorted(LOCKED) and doc["hashes"]==hashes
        assert doc["games"]==PER_SHARD and len(doc["rows"])==PER_SHARD
        for offset,row in enumerate(doc["rows"]):
            gid=doc["shard"]*PER_SHARD+offset
            assert gid not in found and gid==row["gid"] and 0<=gid<N
            assert set(row["arms"])==set(VARIANTS)
            assert len({r["seat"] for r in row["arms"].values()})==1
            for r in row["arms"].values():
                assert r["seed"]==SEED_BASE+gid*1000003
                assert r["turn"] in range(4) and r["keep_n"] in range(1,8)
            found[gid]=row
    missing=sorted(set(range(N))-set(found))
    n=len(found)
    report={"schema":SCHEMA,"status":"PASS" if not missing else "INCOMPLETE",
        "n":n,"planned_n":N,"missing_count":len(missing),
        "missing_ids_first50":missing[:50],"shards_found":len(files),
        "policy":POLICY,"beam":BEAM,"seed_base":SEED_BASE,
        "locked_auras":sorted(LOCKED),"hashes":hashes,
        "arms":{},"paired_vs_current":{},
        "scope":"Experimental optimistic beam160 Dack-casting proxy, 32 fixed 99-card decks, both Hardlight Containment and Lunarch Mantle always retained; no post-Dack combo validation. Multiple comparisons / n128 require independent followup."}
    if n:
        seq=[found[i] for i in sorted(found)]
        for name,deck in VARIANTS.items():
            counts=collections.Counter(r["arms"][name]["turn"] for r in seq)
            report["arms"][name]={"counts":{str(k):counts[k] for k in range(4)},
                "T1_pct":round(100*counts[1]/n,4),
                "T2_pct":round(100*(counts[1]+counts[2])/n,4),
                "T3_pct":round(100*(counts[1]+counts[2]+counts[3])/n,4),
                "mean_keep":round(sum(r["arms"][name]["keep_n"] for r in seq)/n,4),
                "lands":nominal(deck),"staff_retained":"Staff of Compleation" in deck,
                "worldmap_retained":"World Map" in deck,**diff(deck)}
            if name!="current":
                report["paired_vs_current"][name]={f"T{k}":pair("current",name,seq,k) for k in (1,2,3)}
        report["rank_by_T2_then_T3"]=sorted(VARIANTS,
            key=lambda name:(-report["arms"][name]["T2_pct"],-report["arms"][name]["T3_pct"],name))
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2)+"\n")
    with gzip.open(out.with_suffix(".raw.json.gz"),"wt",encoding="utf8") as f:
        json.dump({"schema":SCHEMA,"seed_base":SEED_BASE,"hashes":hashes,
                   "rows":[found[k] for k in sorted(found)]},f,separators=(",",":"))
    print("PROTECTED_AURAS_POOL",report["status"],"n",n,
          "rank",report.get("rank_by_T2_then_T3",[])[:8],flush=True)
    assert not missing

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",action="store_true")
    ap.add_argument("--smoke",action="store_true")
    ap.add_argument("--pool",action="store_true")
    ap.add_argument("--path",default="shards")
    ap.add_argument("--shard",type=int,default=0)
    ap.add_argument("--games",type=int,default=PER_SHARD)
    ap.add_argument("--out",default="shards/protected_shard_0.json.gz")
    args=ap.parse_args()
    if args.audit:audit()
    elif args.smoke:smoke()
    elif args.pool:pool(args.path,args.out)
    else:run(args.shard,args.games,args.out)
