#!/usr/bin/env python3
"""Paired N512 color-corrected Assertive Pentad Prism benchmark, exact 99 decks.

Fresh seeds distinct from 10k/n128/n256/n1024 studies; every arm locks
Hardlight Containment, Lunarch Mantle, and three required Boonweaver creatures.
No Mana Crypt/Jeweled Lotus. Primary endpoint is Dack cast by T2, with
paired T1 and T3, not full-combo completion. All 4 new rainbow lands actually
produce a nonwhite color (unlike previously used mono-W Command Tower).
"""
from __future__ import annotations
import argparse, collections, gzip, json, math, os
from pathlib import Path
import dack_prism_color_sources_20261028 as fix

sim=fix.sim
d=sim.d
SCHEMA="dack_prism_4true_rainbow_mox_gardens_n512_v1"
N=512
GAMES_PER_SHARD=8
SEED_BASE=99142810280603
POLICY="assertive"
BEAM=160
LOCKED=frozenset(("Hardlight Containment","Lunarch Mantle"))
BASE=tuple(sim.FROZEN_DECK)
RAINBOW=("City of Brass","Mana Confluence","Tarnished Citadel","Gemstone Mine")

def mutate(deck,changes):
    a=list(deck)
    for rem,add in changes:
        assert rem in a and (rem=="Plains" or a.count(rem)==1),(rem,add)
        assert add=="Plains" or add not in a,(rem,add)
        a[a.index(rem)]=add
    return tuple(a)

TRUE4=mutate(BASE,[("Plains",x) for x in RAINBOW])
VARIANTS={
    "current":BASE,
    "current_basalt_to_prism":mutate(BASE,[("Basalt Monolith","Pentad Prism")]),
    "four_true_rainbow":TRUE4,
    "true4_basalt_to_prism":mutate(TRUE4,[("Basalt Monolith","Pentad Prism")]),
    "true4_map_to_prism":mutate(TRUE4,[("World Map","Pentad Prism")]),
    "true4_map_to_boulder":mutate(TRUE4,[("World Map","Giant's Boulder")]),
    "true4_map_basalt_to_boulder_prism":mutate(TRUE4,[
        ("World Map","Giant's Boulder"),("Basalt Monolith","Pentad Prism")]),
    "true4_map_basalt_to_boulder_voltaic":mutate(TRUE4,[
        ("World Map","Giant's Boulder"),("Basalt Monolith","Voltaic Key")]),
    "true4_map_basalt_to_prism_voltaic":mutate(TRUE4,[
        ("World Map","Pentad Prism"),("Basalt Monolith","Voltaic Key")]),
    "true4_map_basalt_to_manifold_voltaic":mutate(TRUE4,[
        ("World Map","Manifold Key"),("Basalt Monolith","Voltaic Key")]),
    "true4_map_basalt_tooth_to_prism_boulder_voltaic":mutate(TRUE4,[
        ("World Map","Pentad Prism"),("Basalt Monolith","Giant's Boulder"),
        ("Tooth of Ramos","Voltaic Key")]),
}
sim.configure_variants(VARIANTS)
PAIRS=(
    ("current","current_basalt_to_prism"),
    ("four_true_rainbow","true4_basalt_to_prism"),
    ("four_true_rainbow","true4_map_to_prism"),
    ("true4_map_to_boulder","true4_map_basalt_to_boulder_prism"),
    ("true4_map_to_boulder","true4_map_basalt_to_boulder_voltaic"),
    ("true4_map_basalt_to_boulder_prism","true4_map_basalt_to_boulder_voltaic"),
    ("four_true_rainbow","true4_map_to_boulder"),
)
EXPECTED_HASH="a1c8e05dc3f9e1bcfbfbe2f7773ea4a5e62222d3440dd2f7417fd7f2f058c422"

def land_count(deck):
    return sum(c in d.LANDS or c in ("Emeria's Call","Razorgrass Ambush") for c in deck)

def diff(deck):
    b,n=collections.Counter(BASE),collections.Counter(deck)
    return {"out":sorted((b-n).elements()),"in":sorted((n-b).elements())}

def audit():
    assert N==64*GAMES_PER_SHARD and POLICY==sim.ACTIVE_POLICY and BEAM==sim.GAMEPLAY_BEAM
    assert len(VARIANTS)==11 and len({sim.deck_hash(a) for a in VARIANTS.values()})==11
    assert sim.deck_hash(BASE)==EXPECTED_HASH==sim.FROZEN_DECK_HASH
    assert SEED_BASE not in (fix.sim.DEFAULT_SEED_BASE,99142710271850,99142710270201)
    assert len(RAINBOW)==len(set(RAINBOW))==4
    assert "Command Tower" not in RAINBOW
    assert TRUE4.count("Plains")==BASE.count("Plains")-4
    for name,deck in VARIANTS.items():
        assert len(deck)==99 and LOCKED.issubset(deck),name
        assert sim.root.COMBO.issubset(deck),name
        assert len([x for x in deck if x!="Plains"])==len(set(x for x in deck if x!="Plains")),name
        assert not {"Jeweled Lotus","Mana Crypt"}.intersection(deck),name
        assert all(x in d.CARD_ID for x in deck),name
        assert land_count(deck)==34,name
        assert deck.count("Staff of Compleation")==1,name
        assert deck.count("Mox Diamond")==1 and deck.count("Mox Opal")==1,name
        assert deck.count("The Mycosynth Gardens")==1 and deck.count("Talon Gates of Madara")==1,name
        assert deck.count("Prismatic Lens")==1 and deck.count("Coalition Relic")==1,name
        if name not in ("current","current_basalt_to_prism"):
            for land in RAINBOW: assert land in deck,(name,land)
    fix.exact_source_witnesses()
    sim.configure_variants(VARIANTS)
    print("FOUR_TRUE_RAINBOW_PRISM_AUDIT_PASS",json.dumps({
        "schema":SCHEMA,"n":N,"arms":len(VARIANTS),"seed_base":SEED_BASE,
        "hashes":{k:sim.deck_hash(v) for k,v in VARIANTS.items()},
        "diffs":{k:diff(v) for k,v in VARIANTS.items()},
        "policy":POLICY,"beam":BEAM,"rainbow":RAINBOW,"locked":sorted(LOCKED)}),flush=True)

def smoke():
    audit()
    for name in ("current","current_basalt_to_prism","true4_basalt_to_prism",
                 "true4_map_basalt_to_boulder_prism"):
        sim.reset_caches()
        trial=sim.simulate(name,991999,policy=POLICY,seed_base=SEED_BASE,beam=BEAM)
        assert trial["deck_hash"]==sim.deck_hash(VARIANTS[name])
        assert trial["win_turn"] in (0,1,2,3)
        print("FOUR_TRUE_RAINBOW_PRISM_SMOKE",name,trial["win_turn"],trial["keep_n"],flush=True)

def run(shard,games,out):
    audit()
    assert 0<=shard<N//GAMES_PER_SHARD and games==GAMES_PER_SHARD
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    checkpoint=Path(str(dest).replace(".json.gz",".jsonl"))
    start=shard*GAMES_PER_SHARD
    rows=[]
    if checkpoint.exists():
        rows=[json.loads(x) for x in checkpoint.read_text().splitlines() if x.strip()]
        assert all(x["gid"]==start+i and set(x["arms"])==set(VARIANTS) for i,x in enumerate(rows))
    if dest.exists() and len(rows)==GAMES_PER_SHARD:
        print("RAINBOW_PRISM_SHARD_ALREADY_COMPLETE",shard,flush=True);return
    with checkpoint.open("a",encoding="utf8") as f:
        for i in range(len(rows),GAMES_PER_SHARD):
            gid=start+i;arms={}
            for name,deck in VARIANTS.items():
                sim.reset_caches()
                x=sim.simulate(name,gid,policy=POLICY,seed_base=SEED_BASE,beam=BEAM)
                assert x["policy"]==POLICY and x["deck_hash"]==sim.deck_hash(deck)
                assert x["seed"]==SEED_BASE+gid*1000003
                arms[name]={"turn":x["win_turn"],"keep_n":x["keep_n"],
                            "seat":x["seat"],"seed":x["seed"]}
            assert len({z["seat"] for z in arms.values()})==1
            row={"gid":gid,"arms":arms};rows.append(row)
            f.write(json.dumps(row,separators=(",",":"))+"\n")
            f.flush();os.fsync(f.fileno())
            print("RAINBOW_PRISM_GAME",gid," ".join(f"{k}:{arms[k]['turn']}" for k in VARIANTS),flush=True)
    payload={"schema":SCHEMA,"shard":shard,"games":games,"policy":POLICY,
             "beam":BEAM,"seed_base":SEED_BASE,
             "hashes":{k:sim.deck_hash(v) for k,v in VARIANTS.items()},"rows":rows}
    tmp=Path(str(dest)+".tmp")
    with tmp.open("wb") as raw:
        with gzip.GzipFile(filename="",fileobj=raw,mode="wb",mtime=0) as z:
            z.write(json.dumps(payload,separators=(",",":")).encode())
        raw.flush();os.fsync(raw.fileno())
    os.replace(tmp,dest)
    print("RAINBOW_PRISM_SHARD_PASS",shard,len(rows),flush=True)

def compare(rows,aa,bb,t):
    diffs=[int(0<r["arms"][bb]["turn"]<=t)-int(0<r["arms"][aa]["turn"]<=t)
           for r in rows]
    n=len(diffs)
    mean=sum(diffs)/n
    se=math.sqrt(sum((x-mean)**2 for x in diffs)/(n*(n-1))) if n>1 else 0
    return {"delta_pp":round(mean*100,4),
            "gains":diffs.count(1),"losses":diffs.count(-1),"ties":diffs.count(0),
            "paired_95_ci_pp":[round((mean-1.96*se)*100,4),round((mean+1.96*se)*100,4)]}

def pool(folder,out):
    audit()
    found={};files=sorted(Path(folder).rglob("prism_true4_shard_*.json.gz"))
    hashes={k:sim.deck_hash(v) for k,v in VARIANTS.items()}
    for f in files:
        with gzip.open(f,"rt",encoding="utf8") as fp:p=json.load(fp)
        assert p["schema"]==SCHEMA and p["policy"]==POLICY and p["beam"]==BEAM
        assert p["seed_base"]==SEED_BASE and p["hashes"]==hashes
        assert p["games"]==GAMES_PER_SHARD and len(p["rows"])==GAMES_PER_SHARD
        for index,row in enumerate(p["rows"]):
            gid=p["shard"]*GAMES_PER_SHARD+index
            assert 0<=gid<N and gid not in found and row["gid"]==gid
            assert set(row["arms"])==set(VARIANTS)
            assert len({a["seat"] for a in row["arms"].values()})==1
            assert all(a["seed"]==SEED_BASE+gid*1000003 and a["turn"] in range(4)
                       for a in row["arms"].values())
            found[gid]=row
    missing=sorted(set(range(N))-set(found))
    rows=[found[i] for i in sorted(found)]
    n=len(rows)
    report={"schema":SCHEMA,"status":"PASS" if not missing else "INCOMPLETE",
            "n":n,"planned":N,"missing":missing[:100],"missing_count":len(missing),
            "shards_found":len(files),"expected_shards":N//GAMES_PER_SHARD,
            "seed_base":SEED_BASE,"policy":POLICY,"beam":BEAM,
            "locked_auras":sorted(LOCKED),"hashes":hashes,
            "rainbow_lands":RAINBOW,"source_correction":fix.FIX_VERSION,
            "arms":{},"paired_vs_current":{},"head_to_heads":{},
            "scope":"Matched independent Assertive free London goldfish Dack cast T1/T2/T3 (NOT verified post-Dack combo), with Mox Diamond any-color and Mycosynth Gardens {1},T any-color corrected. 4 true rainbow lands. 2-class sunburst simplification remains."}
    if n:
        for name,deck in VARIANTS.items():
            c=collections.Counter(row["arms"][name]["turn"] for row in rows)
            report["arms"][name]={"out":diff(deck)["out"],"in":diff(deck)["in"],
                "T1_pct":round(100*c[1]/n,4),
                "T2_pct":round(100*(c[1]+c[2])/n,4),
                "T3_pct":round(100*(c[1]+c[2]+c[3])/n,4),
                "counts":{str(t):c[t] for t in range(4)},
                "mean_keep":round(sum(row["arms"][name]["keep_n"] for row in rows)/n,4)}
            if name!="current":
                report["paired_vs_current"][name]={f"T{t}":compare(rows,"current",name,t) for t in (1,2,3)}
        for a,b in PAIRS:
            report["head_to_heads"][b+"_vs_"+a]={f"T{t}":compare(rows,a,b,t) for t in (1,2,3)}
        report["rank_by_T2"]=sorted(VARIANTS,
            key=lambda k:(-report["arms"][k]["T2_pct"],-report["arms"][k]["T3_pct"],k))
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2)+"\n")
    with gzip.open(out.with_suffix(".raw.json.gz"),"wt",encoding="utf8") as fp:
        json.dump({"schema":SCHEMA,"hashes":hashes,"seed_base":SEED_BASE,
                   "rows":rows},fp,separators=(",",":"))
    print("FOUR_TRUE_RAINBOW_PRISM_POOL",report["status"],"n",n,
          report.get("rank_by_T2",[])[:8],flush=True)
    assert not missing,"Never publish incomplete study as validated"

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",action="store_true")
    ap.add_argument("--smoke",action="store_true")
    ap.add_argument("--pool",action="store_true")
    ap.add_argument("--shard",type=int,default=0)
    ap.add_argument("--games",type=int,default=GAMES_PER_SHARD)
    ap.add_argument("--path",default="shards")
    ap.add_argument("--out",default="shards/prism_true4_shard_0.json.gz")
    a=ap.parse_args()
    if a.audit:audit()
    elif a.smoke:smoke()
    elif a.pool:pool(a.path,a.out)
    else:run(a.shard,a.games,a.out)
