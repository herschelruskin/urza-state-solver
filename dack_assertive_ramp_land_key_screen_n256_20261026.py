#!/usr/bin/env python3
"""Independent Assertive N256 screen of singleton-legal Dack land/ramp packages.

20 predeclared variants drawn from the historical October 22 and 25 screens.
Promoted Assertive London policy for every arm. The previous Standard-policy
card rankings are NOT pooled with this trial. Compare by T1, by T2 (primary),
by T3, and the weighted T2+.5*exact-T3 diagnostic; combos are not verified.
Matched game ID/seed/seat for each variant, independent from all earlier seeds.
Every game is checkpointed and fsynced. Only complete shard zips are pooled.
"""
from __future__ import annotations
import argparse, collections, gzip, json, math, os, time
from pathlib import Path

import dack_active_mulligan_policy as sim
import dack_land_ramp_factorial12_20261022 as historical

SCHEMA="dack_assertive_ramp_land_key_screen_n256_v1"
SEED_BASE=99142610262341
N=256
PER_SHARD=4
BEAM=160
POLICY="assertive"
CUR=tuple(sim.FROZEN_DECK)
SW=historical.sw
FULL=tuple(historical.FULL)
RAINBOW_ONLY=tuple(historical.LAND_ONLY)
PACKAGE_SAFE=tuple(historical.pkg.LEGAL_COMBO_SAFE)
PACKAGE_ONLY=tuple(historical.RAMP_ONLY)
HISTORICAL_MATCH=historical.CURRENT

def change(cards,*replacements):
    deck=tuple(cards)
    for old,new in replacements:
        assert deck.count(old)==1,(old,new,"replacement source is missing/ambiguous")
        assert new=="Plains" or new not in deck,(old,new,"would violate singleton")
        deck=SW(deck,old,new)
    return tuple(deck)

RAINBOW_TWEAK=change(CUR,
    ("Urza's Cave","Mana Confluence"),
    ("Fomori Vault","City of Brass"),
    ("Emergence Zone","Gemstone Mine"))

VARIANTS={
  "current":CUR,
  "legal_four_rainbow":RAINBOW_ONLY,
  "targeted_three_rainbow":RAINBOW_TWEAK,
  "prism_only":change(CUR,("Implements of Sacrifice","Pentad Prism")),
  "ramp_package_only":PACKAGE_ONLY,
  "four_rainbow_plus_prism":tuple(historical.VARIANTS["rainbow_prism_only"]),
  "full_prism_voltaic_boulder":FULL,
  "full_prism_candelabra_boulder":tuple(historical.VARIANTS["full_candelabra"]),
  "full_basalt_instead_boulder":tuple(historical.VARIANTS["full_basalt_over_boulder"]),
  "full_basalt_instead_prism":tuple(historical.VARIANTS["full_basalt_over_prism"]),
  "full_35lands_instead_voltaic":tuple(historical.VARIANTS["full_plains35"]),
  "full_2keys_instead_boulder":change(FULL,("Giant's Boulder","Manifold Key")),
  "full_3keys_instead_tooth":change(FULL,("Tooth of Ramos","Manifold Key")),
  "full_candelabra_instead_tooth":change(FULL,("Tooth of Ramos","Candelabra of Tawnos")),
  "full_preserve_mantle":PACKAGE_SAFE,
  "full_preserve_mantle_2keys":change(PACKAGE_SAFE,("Giant's Boulder","Manifold Key")),
  "full_preserve_mantle_candelabra":change(PACKAGE_SAFE,("Voltaic Key","Candelabra of Tawnos")),
  "current_2keys":change(CUR,("Hardlight Containment","Voltaic Key"),
                              ("Lunarch Mantle","Manifold Key")),
  "current_voltaic_candelabra":change(CUR,("Hardlight Containment","Voltaic Key"),
                                         ("Lunarch Mantle","Candelabra of Tawnos")),
  "full_basalt_and_candelabra":change(FULL,("Giant's Boulder","Basalt Monolith"),
                                         ("Voltaic Key","Candelabra of Tawnos")),
}
assert len(VARIANTS)==20
sim.configure_variants(VARIANTS)

def deckdiff(cards):
    old=collections.Counter(CUR);new=collections.Counter(cards)
    return {"out":sorted((old-new).elements()),"in":sorted((new-old).elements())}

def audit():
    assert tuple(HISTORICAL_MATCH)==CUR,"historical basis differs from promoted deck"
    assert sim.ACTIVE_POLICY==POLICY
    assert SEED_BASE not in {sim.DEFAULT_SEED_BASE,20261026175233,20261025111008}
    assert sim.GAMEPLAY_BEAM==BEAM
    assert len(VARIANTS)==20 and len({sim.deck_hash(v) for v in VARIANTS.values()})==20
    assert CUR.count("Plains")==10 and CUR.count("Command Tower")==0
    assert RAINBOW_ONLY.count("Plains")==6
    assert RAINBOW_ONLY.count("Command Tower")==1
    assert RAINBOW_ONLY.count("Mana Confluence")==1
    assert RAINBOW_ONLY.count("City of Brass")==1
    assert RAINBOW_ONLY.count("Gemstone Mine")==1
    assert PACKAGE_SAFE.count("Lunarch Mantle")==1
    assert FULL.count("Lunarch Mantle")==0
    assert FULL.count("Basalt Monolith")==0
    assert FULL.count("Pentad Prism")==1 and FULL.count("Giant's Boulder")==1
    assert FULL.count("Voltaic Key")==1
    assert "Mana Crypt" not in CUR and "Jeweled Lotus" not in CUR
    for name,deck in VARIANTS.items():
        assert len(deck)==99,name
        assert sim.root.COMBO.issubset(deck),name
        assert len([x for x in deck if x!="Plains"])==len(set(x for x in deck if x!="Plains")),name
        assert not {"Mana Crypt","Jeweled Lotus"}.intersection(deck),name
        assert deck.count("Bucknard's Everfull Purse")==1,name
        assert deck.count("World Map")==1,name
        assert deck.count("Moonsilver Key")==1,name
        assert deck.count("Coalition Relic")==1,name
        assert deck.count("Command Tower")<=1,name
        assert all(x in sim.d.CARD_ID for x in deck),name
        lands=sum(x in sim.d.LANDS or x in ("Emeria's Call","Razorgrass Ambush") for x in deck)
        assert lands in (34,35),(name,lands)
    # Rules witnesses for mana-fixing, untappers, and corrected no-tap Prism:
    sim.root.install("full_prism_voltaic_boulder")
    d=sim.d
    p=d.State(1,(),(),(d.Perm("Pentad Prism",False,2,1),))
    one=[x for x in d.tap_mana_actions(p) if x.any==1 and x.battlefield[0].counters==1 and not x.battlefield[0].tapped]
    assert one and any(x.any==2 and x.battlefield[0].counters==0 for x in d.tap_mana_actions(one[0]))
    s=d.State(1,(),(),(d.Perm("Voltaic Key",False,0,1),d.Perm("Mana Vault",True,0,1)),c=1)
    assert any(x.battlefield[0].tapped and not x.battlefield[1].tapped for x in d.utility_actions(s))
    s=d.State(1,(),(),(d.Perm("Candelabra of Tawnos",False,0,1),d.Perm("Ancient Tomb",True,0,1)),c=1)
    assert any(x.battlefield[0].tapped and not x.battlefield[1].tapped for x in d.utility_actions(s))
    assert SEED_BASE+123*1000003 != sim.DEFAULT_SEED_BASE+123*1000003
    sim.configure_variants(VARIANTS)
    print("ASSERTIVE_SCREEN_AUDIT_PASS",json.dumps({
        "n":N,"shards":N//PER_SHARD,"variants":len(VARIANTS),
        "seed_base":SEED_BASE,"beam":BEAM,"policy":POLICY,
        "deck_hashes":{k:sim.deck_hash(v) for k,v in VARIANTS.items()},
        "card_diffs":{k:deckdiff(v) for k,v in VARIANTS.items()} }),flush=True)

def smoke():
    audit()
    for name in ("current","full_prism_voltaic_boulder",
                 "full_preserve_mantle","full_2keys_instead_boulder"):
        sim.reset_caches()
        x=sim.simulate(name,50000,policy=POLICY,seed_base=SEED_BASE,beam=BEAM)
        assert x["seed"]==SEED_BASE+50000*1000003 and x["policy"]==POLICY
        assert x["deck_hash"]==sim.deck_hash(VARIANTS[name])
        assert 0<=x["win_turn"]<=3
        print("ASSERTIVE_PACKAGE_SMOKE",name,x["win_turn"],x["keep_n"],flush=True)

def run(shard,games,out):
    audit()
    assert 0<=shard<N//PER_SHARD and games==PER_SHARD
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    checkpoint=Path(str(dest).replace(".json.gz",".jsonl"))
    start=shard*PER_SHARD
    rows=[]
    if checkpoint.exists():
        rows=[json.loads(x) for x in checkpoint.read_text().splitlines() if x.strip()]
        assert all(rec["gid"]==start+i for i,rec in enumerate(rows))
        assert all(set(rec["arms"])==set(VARIANTS) for rec in rows)
    if dest.exists() and len(rows)==PER_SHARD:
        print("SHARD_ALREADY_FINISHED",shard,flush=True);return
    began=time.time()
    with checkpoint.open("a",encoding="utf8") as f:
        for j in range(len(rows),PER_SHARD):
            gid=start+j
            arms={}
            for name in VARIANTS:
                sim.reset_caches()
                rec=sim.simulate(name,gid,policy=POLICY,seed_base=SEED_BASE,beam=BEAM)
                assert rec["seed"]==SEED_BASE+gid*1000003
                assert rec["deck_hash"]==sim.deck_hash(VARIANTS[name])
                assert rec["policy"]==POLICY
                arms[name]={"turn":rec["win_turn"],"keep_n":rec["keep_n"],
                            "seat":rec["seat"],"seed":rec["seed"]}
            assert len({r["seat"] for r in arms.values()})==1
            row={"gid":gid,"arms":arms}
            f.write(json.dumps(row,separators=(",",":"))+"\n")
            f.flush();os.fsync(f.fileno())
            rows.append(row)
            print("ASSERTIVE_SCREEN_GAME",gid," ".join(f"{v}={arms[v]['turn']}" for v in VARIANTS),
                  "elapsed",round(time.time()-began,2),flush=True)
    doc={"schema":SCHEMA,"shard":shard,"games":PER_SHARD,"seed_base":SEED_BASE,
         "deck_hashes":{k:sim.deck_hash(v) for k,v in VARIANTS.items()},
         "beam":BEAM,"policy":POLICY,"rows":rows}
    tmp=Path(str(dest)+".tmp")
    with tmp.open("wb") as raw:
        with gzip.GzipFile(filename="",mode="wb",fileobj=raw,mtime=0) as z:
            z.write(json.dumps(doc,separators=(",",":")).encode())
        raw.flush();os.fsync(raw.fileno())
    os.replace(tmp,dest)
    print("ASSERTIVE_SCREEN_SHARD_PASS",shard,PER_SHARD,len(rows),flush=True)

def paired(rows,name,metric):
    n=len(rows)
    a=[int(0<rec["arms"][name]["turn"]<=metric)-
       int(0<rec["arms"]["current"]["turn"]<=metric)
       for rec in rows]
    mean=sum(a)/n if n else 0
    se=math.sqrt(sum((v-mean)**2 for v in a)/((n-1)*n)) if n>1 else 0
    return {"delta_pp":round(100*mean,4),"gains":a.count(1),"losses":a.count(-1),
            "paired_95_ci_pp":[round(100*(mean-1.96*se),4),round(100*(mean+1.96*se),4)]}

def pool(path,out):
    audit()
    files=sorted(Path(path).rglob("assertive_ramp_shard_*.json.gz"))
    rows={}
    hashes={k:sim.deck_hash(v) for k,v in VARIANTS.items()}
    for fn in files:
        with gzip.open(fn,"rt",encoding="utf8") as f:doc=json.load(f)
        assert doc["schema"]==SCHEMA and doc["deck_hashes"]==hashes
        assert doc["seed_base"]==SEED_BASE and doc["policy"]==POLICY and doc["beam"]==BEAM
        assert doc["games"]==PER_SHARD and len(doc["rows"])==PER_SHARD
        for offset,r in enumerate(doc["rows"]):
            gid=doc["shard"]*PER_SHARD+offset
            assert gid not in rows and r["gid"]==gid and 0<=gid<N
            assert set(r["arms"])==set(VARIANTS)
            assert len({q["seat"] for q in r["arms"].values()})==1
            for name,q in r["arms"].items():
                assert q["seed"]==SEED_BASE+gid*1000003
                assert q["turn"] in (0,1,2,3)
                assert q["keep_n"] in (1,2,3,4,5,6,7)
            rows[gid]=r
    missing=sorted(set(range(N))-set(rows))
    n=len(rows)
    report={"schema":SCHEMA,"status":"PASS" if not missing else "INCOMPLETE",
            "planned_n":N,"validated_n":n,"shards_found":len(files),
            "expected_shards":N//PER_SHARD,"missing_count":len(missing),
            "missing_ids_first50":missing[:50],"seed_base":SEED_BASE,"beam":BEAM,
            "policy":POLICY,"deck_hashes":hashes,"arms":{},"paired_vs_current":{},
            "scope":"Exploratory, matched Assertive free-London full-beam goldfish Dack CAST T1/T2/T3 conditional on combo; not multiplayer or proven full Boonweaver sequence. Requires new held-out confirmation.",
            "caveat":"Many speed-only packages remove Lunarch Mantle or Tooth of Ramos; Dack cast benchmark does NOT validate preserved sacrifice outlet/full combo, so assess those versions separately before actual deck recommendations."}
    if n:
        ordered=[rows[k] for k in sorted(rows)]
        for name,deck in VARIANTS.items():
            c=collections.Counter(row["arms"][name]["turn"] for row in ordered)
            report["arms"][name]={"out":deckdiff(deck)["out"],"in":deckdiff(deck)["in"],
                   "retains_lunarch_mantle":"Lunarch Mantle" in deck,
                   "nominal_lands":sum(q in sim.d.LANDS or q in ("Emeria's Call","Razorgrass Ambush") for q in deck),
                   "counts":{str(k):c[k] for k in range(4)},
                   "T1_pct":round(100*c[1]/n,4),
                   "T2_pct":round(100*(c[1]+c[2])/n,4),
                   "T3_pct":round(100*(c[1]+c[2]+c[3])/n,4),
                   "T2_plus_half_exact_T3_pct":round(100*(c[1]+c[2]+.5*c[3])/n,4),
                   "mean_keep":round(sum(row["arms"][name]["keep_n"] for row in ordered)/n,4)}
            if name!="current":
                report["paired_vs_current"][name]={
                  f"T{t}":paired(ordered,name,t) for t in (1,2,3)}
        report["rank_by_T2_then_T3"] = sorted(VARIANTS,
            key=lambda v:(-report["arms"][v]["T2_pct"],
                          -report["arms"][v]["T3_pct"],v))
    output=Path(out);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+"\n")
    print("ASSERTIVE_SCREEN_POOL",report["status"],"n",n,"missing",len(missing),
          "top_T2",report.get("rank_by_T2_then_T3",[])[:8],flush=True)
    assert not missing,("incomplete data",len(missing))

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",action="store_true")
    ap.add_argument("--smoke",action="store_true")
    ap.add_argument("--pool",action="store_true")
    ap.add_argument("--shard",type=int,default=0)
    ap.add_argument("--games",type=int,default=PER_SHARD)
    ap.add_argument("--out",default="shards/assertive_ramp_shard_0.json.gz")
    ap.add_argument("--path",default="shards")
    args=ap.parse_args()
    if args.smoke:smoke()
    elif args.audit:audit()
    elif args.pool:pool(args.path,args.out)
    else:run(args.shard,args.games,args.out)
