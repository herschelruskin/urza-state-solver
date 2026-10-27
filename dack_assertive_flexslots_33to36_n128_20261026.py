#!/usr/bin/env python3
"""Independent Assertive flex-slot screen, 33/34/35/36 nominal lands, n128.

Re-tests Basalt Monolith, World Map, Lunarch Mantle, Pentad Prism, Giant's
Boulder, Voltaic / Manifold Key and Candelabra as paired permutations.

Deck construction and card-order inputs derive from the exact frozen October
26 99-card Boonweaver current and verified legal four-rainbow package.
No duplicate Command Tower; no banned Mana Crypt / Jeweled Lotus.
Every variant uses promoted Assertive for every London decision.
Screening results are exploratory and require held-out confirmation.
Outcome is an optimistic Dack cast, NOT certified full combo/multiplayer win.
"""
from __future__ import annotations
import argparse, collections, gzip, json, math, os, time
from pathlib import Path
import dack_assertive_ramp_land_key_screen_n256_20261026 as prior

sim=prior.sim
CUR=prior.CUR
FULL=prior.FULL
SAFE=prior.PACKAGE_SAFE
SCHEMA="dack_assertive_flexslots_33to36_n128_v1"
SEED_BASE=99142610262358031
N=128
PER_SHARD=2
BEAM=160
POLICY="assertive"
VARIANTS={}

def one(deck,old,new):
    seq=list(deck)
    if old=="Plains":
        assert seq.count(old)>=1,(old,new)
    else:assert seq.count(old)==1,(old,new)
    if new!="Plains":assert new not in seq,(old,new,"non-singleton")
    seq[seq.index(old)]=new
    return tuple(seq)

def replacements(deck,*changes):
    for a,b in changes:deck=one(deck,a,b)
    return tuple(deck)

def add(label,deck):
    assert label not in VARIANTS,label
    VARIANTS[label]=tuple(deck)

# Five paired anchors link this grid with the already running 20-arm screen.
add("current",CUR)
add("full_prism_voltaic_boulder",FULL)
add("full_preserve_mantle",SAFE)
add("full_double_keys",one(FULL,"Giant's Boulder","Manifold Key"))
add("full_basalt_over_boulder",one(FULL,"Giant's Boulder","Basalt Monolith"))

# 33 nominal lands: convert exactly one Plains to another acceleration slot.
for base,deck,rocks in (
    ("full33",FULL,("Manifold Key","Candelabra of Tawnos","Basalt Monolith")),
    ("safe33",SAFE,("Manifold Key","Candelabra of Tawnos")),
    ("current33",CUR,("Voltaic Key","Pentad Prism","Manifold Key")),
):
    for rock in rocks:
        add(base+"_"+rock.lower().replace(" ","_").replace("'",""),
            one(deck,"Plains",rock))

# Inverse: 35 or 36 lands by trading nonland cards for Plains.
for base,deck,outs in (
    ("full35",FULL,("Voltaic Key","Giant's Boulder","Pentad Prism","World Map")),
    ("safe35",SAFE,("Voltaic Key","Giant's Boulder")),
    ("current35",CUR,("World Map","Basalt Monolith")),
):
    for old in outs:
        add(base+"_minus_"+old.lower().replace(" ","_").replace("'",""),
            one(deck,old,"Plains"))
add("full36_no_key_boulder",replacements(FULL,("Voltaic Key","Plains"),("Giant's Boulder","Plains")))
add("safe36_no_key_boulder",replacements(SAFE,("Voltaic Key","Plains"),("Giant's Boulder","Plains")))

# World Map now joins Basalt and Mantle as an explicit flex slot.
for base,deck,choices in (
    ("full_map",FULL,("Manifold Key","Candelabra of Tawnos","Basalt Monolith")),
    ("safe_map",SAFE,("Manifold Key","Basalt Monolith")),
    ("current_map",CUR,("Voltaic Key","Pentad Prism")),
):
    for new in choices:
        add(base+"_to_"+new.lower().replace(" ","_").replace("'",""),
            one(deck,"World Map",new))

# Basalt might be better as colored burst mana or artifact untap utility.
for new in ("Pentad Prism","Voltaic Key","Candelabra of Tawnos","Manifold Key"):
    add("current_basalt_to_"+new.lower().replace(" ","_").replace("'",""),
        one(CUR,"Basalt Monolith",new))

# Preserve the Mantle combo outlet while probing how to spend other slots.
add("safe_boulder_to_basalt",one(SAFE,"Giant's Boulder","Basalt Monolith"))
add("safe_prism_to_basalt",one(SAFE,"Pentad Prism","Basalt Monolith"))
add("safe_boulder_to_manifold",one(SAFE,"Giant's Boulder","Manifold Key"))

# Two-way and three-way interactions requiring extra flex slots.
add("full_basalt_plus_candelabra",
    replacements(FULL,("Giant's Boulder","Basalt Monolith"),
                      ("Voltaic Key","Candelabra of Tawnos")))
add("full_map_to_basalt_boulder_to_manifold",
    replacements(FULL,("World Map","Basalt Monolith"),
                      ("Giant's Boulder","Manifold Key")))
add("full33_manifold_boulder_to_basalt",
    replacements(FULL,("Plains","Manifold Key"),
                      ("Giant's Boulder","Basalt Monolith")))
add("safe33_manifold_boulder_to_basalt",
    replacements(SAFE,("Plains","Manifold Key"),
                      ("Giant's Boulder","Basalt Monolith")))

EXPECTED_ARMS=41
assert len(VARIANTS)==EXPECTED_ARMS,(len(VARIANTS),list(VARIANTS))
sim.configure_variants(VARIANTS)

def diff(deck):
    a,b=collections.Counter(CUR),collections.Counter(deck)
    return {"in":sorted((b-a).elements()),"out":sorted((a-b).elements())}

def nominal(deck):
    return sum(c in sim.d.LANDS or c in ("Emeria's Call","Razorgrass Ambush") for c in deck)

def audit():
    assert sim.ACTIVE_POLICY==POLICY and sim.GAMEPLAY_BEAM==BEAM
    assert SEED_BASE not in (sim.DEFAULT_SEED_BASE,prior.SEED_BASE,20261026175233)
    assert N==PER_SHARD*64 and EXPECTED_ARMS==len(VARIANTS)
    assert CUR==sim.FROZEN_DECK and sim.deck_hash(CUR)==sim.FROZEN_DECK_HASH
    assert len({sim.deck_hash(deck) for deck in VARIANTS.values()})==EXPECTED_ARMS
    assert nominal(CUR)==34 and nominal(FULL)==34 and nominal(SAFE)==34
    assert {nominal(deck) for deck in VARIANTS.values()}=={33,34,35,36}
    assert any("World Map" not in d for d in VARIANTS.values())
    assert any("Lunarch Mantle" in d for d in VARIANTS.values())
    assert any("Basalt Monolith" in d for d in VARIANTS.values())
    assert any("Basalt Monolith" not in d for d in VARIANTS.values())
    for name,deck in VARIANTS.items():
        assert len(deck)==99,name
        assert sim.root.COMBO.issubset(deck),name
        assert not {"Mana Crypt","Jeweled Lotus"}.intersection(deck),name
        assert len([c for c in deck if c!="Plains"])==len(set(c for c in deck if c!="Plains")),name
        assert deck.count("Command Tower")<=1,name
        assert deck.count("Moonsilver Key")==1 and deck.count("Bucknard's Everfull Purse")==1,name
        assert all(c in sim.d.CARD_ID for c in deck),name
        assert nominal(deck) in (33,34,35,36),(name,nominal(deck))
    assert VARIANTS["current"]==CUR and VARIANTS["full_prism_voltaic_boulder"]==FULL
    assert VARIANTS["full_preserve_mantle"]==SAFE
    assert "Lunarch Mantle" in SAFE and "Lunarch Mantle" not in FULL
    # Same already-audited corrected Prism, artifact untaps, four-rainbow land rules.
    prior.audit_rules = getattr(prior,"audit_rules",lambda:None)
    sim.root.install("full_prism_voltaic_boulder")
    d=sim.d
    p=d.State(1,(),(),(d.Perm("Pentad Prism",False,2,1),))
    step=[x for x in d.tap_mana_actions(p) if x.any==1 and x.battlefield[0].counters==1 and not x.battlefield[0].tapped]
    assert step and any(x.any==2 and x.battlefield[0].counters==0 for x in d.tap_mana_actions(step[0]))
    sim.configure_variants(VARIANTS)
    print("FLEXSLOTS_41_ARM_AUDIT_PASS",json.dumps({
        "n":N,"arms":EXPECTED_ARMS,"policy":POLICY,"seed_base":SEED_BASE,
        "hashes":{name:sim.deck_hash(deck) for name,deck in VARIANTS.items()},
        "land_count":{name:nominal(deck) for name,deck in VARIANTS.items()},
        "swaps":{name:diff(deck) for name,deck in VARIANTS.items()}}),flush=True)

def smoke():
    audit()
    for name in ("current","full_prism_voltaic_boulder","full_preserve_mantle",
                 "full33_manifold_key","full36_no_key_boulder","safe_map_to_basalt_monolith"):
        sim.reset_caches()
        x=sim.simulate(name,50001,policy=POLICY,seed_base=SEED_BASE,beam=BEAM)
        assert x["policy"]==POLICY and x["deck_hash"]==sim.deck_hash(VARIANTS[name])
        assert x["win_turn"] in (0,1,2,3)
        print("FLEXSLOTS_SMOKE",name,x["win_turn"],x["keep_n"],flush=True)

def run(shard,games,out):
    audit()
    assert games==PER_SHARD and 0<=shard<N//PER_SHARD
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    checkpoint=Path(str(dest).replace(".json.gz",".jsonl"))
    start=shard*PER_SHARD
    rows=[]
    if checkpoint.exists():
        rows=[json.loads(x) for x in checkpoint.read_text().splitlines() if x.strip()]
        assert all(rec["gid"]==start+j and set(rec["arms"])==set(VARIANTS) for j,rec in enumerate(rows))
    if dest.exists() and len(rows)==PER_SHARD:
        print("SHARD_ALREADY_FINISHED",shard,flush=True);return
    started=time.time()
    with checkpoint.open("a",encoding="utf8") as f:
        for j in range(len(rows),PER_SHARD):
            gid=start+j;arms={}
            for name,deck in VARIANTS.items():
                sim.reset_caches()
                rec=sim.simulate(name,gid,policy=POLICY,seed_base=SEED_BASE,beam=BEAM)
                assert rec["seed"]==SEED_BASE+gid*1000003
                assert rec["deck_hash"]==sim.deck_hash(deck)
                assert rec["policy"]==POLICY
                arms[name]={"turn":rec["win_turn"],"keep_n":rec["keep_n"],
                            "seat":rec["seat"],"seed":rec["seed"]}
            assert len({v["seat"] for v in arms.values()})==1
            row={"gid":gid,"arms":arms}
            f.write(json.dumps(row,separators=(",",":"))+"\n")
            f.flush();os.fsync(f.fileno())
            rows.append(row)
            print("FLEXSLOTS_GAME_PASS",gid," ".join(f"{v}:{arms[v]['turn']}" for v in VARIANTS),
                  "elapsed",round(time.time()-started,2),flush=True)
    payload={"schema":SCHEMA,"shard":shard,"games":PER_SHARD,"seed_base":SEED_BASE,
             "beam":BEAM,"policy":POLICY,"deck_hashes":{k:sim.deck_hash(v) for k,v in VARIANTS.items()},"rows":rows}
    tmp=Path(str(dest)+".tmp")
    with tmp.open("wb") as raw:
        with gzip.GzipFile(filename="",mode="wb",fileobj=raw,mtime=0) as z:
            z.write(json.dumps(payload,separators=(",",":")).encode())
        raw.flush();os.fsync(raw.fileno())
    os.replace(tmp,dest)
    print("FLEXSLOTS_SHARD_COMPLETE",shard,len(rows),flush=True)

def paired(rows,name,turn):
    diffs=[int(0<r["arms"][name]["turn"]<=turn)-int(0<r["arms"]["current"]["turn"]<=turn) for r in rows]
    n=len(diffs);avg=sum(diffs)/n
    se=math.sqrt(sum((v-avg)**2 for v in diffs)/(n*(n-1))) if n>1 else 0
    return {"delta_pp":round(100*avg,4),"gain":diffs.count(1),"loss":diffs.count(-1),
            "paired_95_ci_pp":[round(100*(avg-1.96*se),4),round(100*(avg+1.96*se),4)]}

def pool(folder,out):
    audit()
    paths=sorted(Path(folder).rglob("flex_shard_*.json.gz"))
    hashes={name:sim.deck_hash(deck) for name,deck in VARIANTS.items()}
    data={}
    for p in paths:
        with gzip.open(p,"rt",encoding="utf8") as f:q=json.load(f)
        assert q["schema"]==SCHEMA and q["seed_base"]==SEED_BASE and q["beam"]==BEAM
        assert q["policy"]==POLICY and q["deck_hashes"]==hashes
        assert q["games"]==PER_SHARD and len(q["rows"])==PER_SHARD
        for idx,row in enumerate(q["rows"]):
            gid=q["shard"]*PER_SHARD+idx
            assert gid not in data and row["gid"]==gid and 0<=gid<N
            assert set(row["arms"])==set(VARIANTS)
            assert len({v["seat"] for v in row["arms"].values()})==1
            for v in row["arms"].values():
                assert v["seed"]==SEED_BASE+gid*1000003
                assert v["turn"] in (0,1,2,3) and v["keep_n"] in range(1,8)
            data[gid]=row
    missing=sorted(set(range(N))-set(data))
    n=len(data)
    result={"status":"PASS" if not missing else "INCOMPLETE","schema":SCHEMA,
      "planned_n":N,"validated_n":n,"missing_count":len(missing),
      "missing_game_ids_first50":missing[:50],"shards_found":len(paths),
      "expected_shards":N//PER_SHARD,"seed_base":SEED_BASE,"beam":BEAM,
      "policy":POLICY,"hashes":hashes,"arms":{},"paired_vs_current":{},
      "scope":"Exploratory small-n screen, 41 predeclared singleton-legal 33–36-land combinations under promoted Assertive. Matched full-beam optimistic Dack cast, not confirmed combo completion or multiplayer win. Multiple comparisons: shortlist then independently replicate.",
      "combo_caveat":"Removing Lunarch Mantle, World Map, Basalt, or other functional pieces may impact lines unobserved by Dack-cast proxy. Confirm complete combo functionality before considering a deck promotion."}
    if n:
        seq=[data[k] for k in sorted(data)]
        for name,deck in VARIANTS.items():
            counts=collections.Counter(r["arms"][name]["turn"] for r in seq)
            result["arms"][name]={"nominal_lands":nominal(deck),
                "retains_mantle":"Lunarch Mantle" in deck,
                "retains_world_map":"World Map" in deck,
                "retains_basalt":"Basalt Monolith" in deck,
                **diff(deck),"counts":{str(i):counts[i] for i in range(4)},
                "T1_pct":round(100*counts[1]/n,4),
                "T2_pct":round(100*(counts[1]+counts[2])/n,4),
                "T3_pct":round(100*(counts[1]+counts[2]+counts[3])/n,4),
                "weighted_T2_plus_half_exact_T3_pct":round(100*(counts[1]+counts[2]+.5*counts[3])/n,4),
                "mean_keep":round(sum(r["arms"][name]["keep_n"] for r in seq)/n,4)}
            if name!="current":
                result["paired_vs_current"][name]={f"T{t}":paired(seq,name,t) for t in (1,2,3)}
        result["rank_by_T2"]=sorted(VARIANTS,
            key=lambda k:(-result["arms"][k]["T2_pct"],-result["arms"][k]["T3_pct"],k))
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2)+"\n")
    with gzip.open(dest.with_suffix(".raw.json.gz"),"wt",encoding="utf8") as f:
        json.dump({"schema":SCHEMA,"hashes":hashes,"seed_base":SEED_BASE,
                   "rows":[data[k] for k in sorted(data)]},f,separators=(",",":"))
    print("FLEXSLOTS_POOL",result["status"],"n",n,"missing",len(missing),
          "rank",result.get("rank_by_T2",[])[:8],flush=True)
    assert not missing,("incomplete",len(missing))

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",action="store_true")
    ap.add_argument("--smoke",action="store_true")
    ap.add_argument("--pool",action="store_true")
    ap.add_argument("--path",default="shards")
    ap.add_argument("--shard",type=int,default=0)
    ap.add_argument("--games",type=int,default=PER_SHARD)
    ap.add_argument("--out",default="shards/flex_shard_0.json.gz")
    args=ap.parse_args()
    if args.smoke:smoke()
    elif args.audit:audit()
    elif args.pool:pool(args.path,args.out)
    else:run(args.shard,args.games,args.out)
