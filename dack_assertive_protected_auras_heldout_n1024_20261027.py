#!/usr/bin/env python3
"""Independent N1024 matched held-out confirmation of aura-preserving Dack packages.

The 10 arms are predeclared before any new seed is simulated, selected from
the completed N128 protected-aura screen. No candidate here removes Hardlight
Containment or Lunarch Mantle; all are exact 99-card singleton-legal builds.
Both artifacts Mana Crypt and Jeweled Lotus remain absent. Staff is retained
except in one deliberately tested direct 33-land-versus-Staff-cut comparison.

Primary: cumulative Dack-cast-by-T2 paired delta against CURRENT.
Secondary: T1, cumulative T3, mean keep, and Staff-vs-land same-slot test.
Goldfish Dack deployment only, NOT confirmation of winning the full combo.
Fresh independent seed base; old screening games do not enter any estimates.
"""
from __future__ import annotations
import argparse, collections, gzip, hashlib, json, math, os, time
from pathlib import Path
import dack_assertive_protected_auras_cutsearch_n128_20261027 as prev

sim=prev.sim
SCHEMA="dack_assertive_auras_heldout_n1024_v1"
POLICY="assertive"
N=1024
PER_SHARD=8
BEAM=160
SEED_BASE=99142710271850
ARM_NAMES=(
    "current",
    "current_map_to_plains",
    "current_map_to_giants_boulder",
    "four_rainbow",
    "rainbow_map_to_pentad_prism",
    "rainbow_map_basalt_to_voltaic_manifold",
    "rainbow_map_basalt_to_prism_boulder",
    "rainbow_map_basalt_to_voltaic_boulder",
    "rainbow_map_basalt_tooth_to_voltaic_prism_boulder",
    "rainbow_33land_full_four_standalone_keepers",
    "rainbow_map_basalt_tooth_staff_to_voltaic_manifold_prism_boulder",
)
VARIANTS={k:tuple(prev.VARIANTS[k]) for k in ARM_NAMES}
LOCKED=frozenset(("Hardlight Containment","Lunarch Mantle"))
BASELINE="current"
PREDECLARED_COMPARISONS=(
    ("current_map_to_plains","current_map_to_giants_boulder"),
    ("rainbow_33land_full_four_standalone_keepers",
     "rainbow_map_basalt_tooth_staff_to_voltaic_manifold_prism_boulder"),
)
sim.configure_variants(VARIANTS)

def nominal(deck):
    return sum(x in sim.d.LANDS or x in ("Emeria's Call","Razorgrass Ambush") for x in deck)

def diff(deck):
    b,a=collections.Counter(prev.CURRENT),collections.Counter(deck)
    return {"out":sorted((b-a).elements()),"in":sorted((a-b).elements())}

def audit():
    assert len(VARIANTS)==11 and len(set(ARM_NAMES))==11
    assert N==128*PER_SHARD and N>=1024
    assert POLICY==sim.ACTIVE_POLICY and BEAM==sim.GAMEPLAY_BEAM==160
    assert SEED_BASE not in (
        sim.DEFAULT_SEED_BASE,prev.SEED_BASE,prev.earlier.SEED_BASE,
        prev.earlier.historical.root.batch.CONFIG["seed_base"],99142610262358031)
    assert VARIANTS[BASELINE]==tuple(sim.FROZEN_DECK)
    assert sim.deck_hash(VARIANTS[BASELINE])==sim.FROZEN_DECK_HASH
    assert len({sim.deck_hash(deck) for deck in VARIANTS.values()})==11
    for name,deck in VARIANTS.items():
        assert len(deck)==99 and LOCKED.issubset(deck),name
        assert sim.root.COMBO.issubset(deck),name
        assert not {"Mana Crypt","Jeweled Lotus"}.intersection(deck),name
        assert deck.count("Moonsilver Key")==1,name
        assert deck.count("Bucknard's Everfull Purse")==1,name
        assert deck.count("Coalition Relic")==1,name
        assert all(x in sim.d.CARD_ID for x in deck),name
        nonbasics=[x for x in deck if x!="Plains"]
        assert len(set(nonbasics))==len(nonbasics),name
        assert deck.count("Command Tower")<=1,name
        assert nominal(deck) in (33,34,35),name
        if name not in ("current","current_map_to_plains",
                        "current_map_to_giants_boulder"):
            for rainbow in ("Command Tower","Mana Confluence",
                            "City of Brass","Gemstone Mine"):
                assert deck.count(rainbow)==1,(name,rainbow)
    assert nominal(VARIANTS["current"])==34
    assert nominal(VARIANTS["current_map_to_plains"])==35
    assert nominal(VARIANTS["rainbow_33land_full_four_standalone_keepers"])==33
    assert nominal(VARIANTS["rainbow_map_basalt_tooth_staff_to_voltaic_manifold_prism_boulder"])==34
    staff_cut="rainbow_map_basalt_tooth_staff_to_voltaic_manifold_prism_boulder"
    assert "Staff of Compleation" not in VARIANTS[staff_cut]
    assert all("Staff of Compleation" in x for k,x in VARIANTS.items() if k!=staff_cut)
    # A uniquely direct Staff/Plains comparison with all other 98 cards held.
    aa=VARIANTS["rainbow_33land_full_four_standalone_keepers"]
    bb=VARIANTS[staff_cut]
    assert diff_pair(aa,bb)=={"out":["Staff of Compleation"],"in":["Plains"]}
    # World Map -> Boulder / Plains is also direct, no other changes.
    assert diff_pair(VARIANTS["current_map_to_plains"],
                     VARIANTS["current_map_to_giants_boulder"])=={
                         "out":["Plains"],"in":["Giant's Boulder"]}
    sim.root.install(BASELINE)
    d=sim.d
    prism=d.State(1,(),(),(d.Perm("Pentad Prism",False,2,1),))
    nxt=[x for x in d.tap_mana_actions(prism) if x.any==1 and
         x.battlefield[0].counters==1 and not x.battlefield[0].tapped]
    assert nxt and any(x.any==2 and x.battlefield[0].counters==0
                       for x in d.tap_mana_actions(nxt[0]))
    sim.configure_variants(VARIANTS)
    print("AURA_HELDOUT_N1024_AUDIT_PASS",json.dumps({
        "n":N,"arms":len(VARIANTS),"policy":POLICY,"beam":BEAM,
        "seed_base":SEED_BASE,"baseline_hash":sim.FROZEN_DECK_HASH,
        "locked":sorted(LOCKED),"hashes":{k:sim.deck_hash(v) for k,v in VARIANTS.items()},
        "swaps":{k:diff(v) for k,v in VARIANTS.items()}}),flush=True)

def diff_pair(before,after):
    a,b=collections.Counter(before),collections.Counter(after)
    return {"out":sorted((a-b).elements()),"in":sorted((b-a).elements())}

def smoke():
    audit()
    # Run 2 new independent games on 4 contrasting decks, BEFORE main shards.
    for gid in (99000,99001):
        for name in ("current","current_map_to_plains",
                     "rainbow_33land_full_four_standalone_keepers",
                     "rainbow_map_basalt_tooth_staff_to_voltaic_manifold_prism_boulder"):
            sim.reset_caches()
            r=sim.simulate(name,gid,policy=POLICY,seed_base=SEED_BASE,beam=BEAM)
            assert r["seed"]==SEED_BASE+gid*1000003
            assert r["deck_hash"]==sim.deck_hash(VARIANTS[name])
            assert r["win_turn"] in (0,1,2,3)
            print("AURA_HELDOUT_SMOKE_PASS",gid,name,r["win_turn"],r["keep_n"],flush=True)

def run(shard,games,out):
    audit()
    assert games==PER_SHARD and 0<=shard<N//PER_SHARD
    dest=Path(out)
    dest.parent.mkdir(parents=True,exist_ok=True)
    checkpoint=Path(str(dest).replace(".json.gz",".jsonl"))
    first=shard*PER_SHARD
    rows=[]
    if checkpoint.exists():
        rows=[json.loads(line) for line in checkpoint.read_text().splitlines() if line.strip()]
        assert all(row["gid"]==first+i and set(row["arms"])==set(VARIANTS)
                   for i,row in enumerate(rows))
    if dest.exists() and len(rows)==PER_SHARD:
        print("AURA_HELDOUT_SHARD_ALREADY_FINISHED",shard,flush=True);return
    started=time.time()
    with checkpoint.open("a",encoding="utf8") as f:
        for j in range(len(rows),PER_SHARD):
            gid=first+j;arms={}
            for name,deck in VARIANTS.items():
                sim.reset_caches()
                r=sim.simulate(name,gid,policy=POLICY,
                               seed_base=SEED_BASE,beam=BEAM)
                assert r["seed"]==SEED_BASE+gid*1000003
                assert r["deck_hash"]==sim.deck_hash(deck)
                assert r["policy"]==POLICY
                arms[name]={"turn":r["win_turn"],"keep_n":r["keep_n"],
                            "seed":r["seed"],"seat":r["seat"]}
            assert len({z["seat"] for z in arms.values()})==1
            row={"gid":gid,"arms":arms}
            f.write(json.dumps(row,separators=(",",":"))+"\n")
            f.flush();os.fsync(f.fileno())
            rows.append(row)
            print("AURA_HELDOUT_GAME_PASS",gid,
                  " ".join(f"{k}:{arms[k]['turn']}" for k in VARIANTS),
                  "elapsed",round(time.time()-started,2),flush=True)
    doc={"schema":SCHEMA,"shard":shard,"games":PER_SHARD,
         "seed_base":SEED_BASE,"beam":BEAM,"policy":POLICY,
         "hashes":{k:sim.deck_hash(v) for k,v in VARIANTS.items()},"rows":rows}
    temp=Path(str(dest)+".tmp")
    with temp.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw,mode="wb",filename="",mtime=0) as z:
            z.write(json.dumps(doc,separators=(",",":")).encode())
        raw.flush();os.fsync(raw.fileno())
    os.replace(temp,dest)
    print("AURA_HELDOUT_SHARD_PASS",shard,len(rows),flush=True)

def pair(rows,left,right,turn):
    n=len(rows)
    d=[int(0<r["arms"][right]["turn"]<=turn)-
       int(0<r["arms"][left]["turn"]<=turn) for r in rows]
    mean=sum(d)/n
    se=math.sqrt(sum((x-mean)**2 for x in d)/(n*(n-1))) if n>1 else 0
    return {"delta_pp":round(100*mean,4),
        "gains":d.count(1),"losses":d.count(-1),"ties":d.count(0),
        "paired_95_ci_pp":[round(100*(mean-1.96*se),4),
                           round(100*(mean+1.96*se),4)]}

def pool(shards,out):
    audit()
    files=sorted(Path(shards).rglob("aura_heldout_shard_*.json.gz"))
    expected={k:sim.deck_hash(v) for k,v in VARIANTS.items()}
    found={}
    for fp in files:
        with gzip.open(fp,"rt",encoding="utf8") as f:doc=json.load(f)
        assert doc["schema"]==SCHEMA and doc["policy"]==POLICY
        assert doc["beam"]==BEAM and doc["seed_base"]==SEED_BASE
        assert doc["hashes"]==expected and doc["games"]==PER_SHARD
        assert len(doc["rows"])==PER_SHARD
        for offset,row in enumerate(doc["rows"]):
            gid=doc["shard"]*PER_SHARD+offset
            assert 0<=gid<N and row["gid"]==gid and gid not in found
            assert set(row["arms"])==set(VARIANTS)
            assert len({r["seat"] for r in row["arms"].values()})==1
            for r in row["arms"].values():
                assert r["seed"]==SEED_BASE+gid*1000003
                assert r["turn"] in (0,1,2,3) and 1<=r["keep_n"]<=7
            found[gid]=row
    missing=sorted(set(range(N))-set(found))
    n=len(found)
    data={"schema":SCHEMA,"status":"PASS" if not missing else "INCOMPLETE",
          "n":n,"planned_n":N,"shards_found":len(files),
          "expected_shards":N//PER_SHARD,"missing_count":len(missing),
          "first_missing_ids":missing[:40],"seed_base":SEED_BASE,
          "beam":BEAM,"policy":POLICY,"hashes":expected,
          "locked_auras":sorted(LOCKED),"arms":{},
          "paired_vs_current":{},"head_to_heads":{},
          "scope":"Predeclared independent held-out Assertive N1024 sample, 11 singleton-legal decks with both auras retained, paired across all arms. Outcome is optimistic Dack cast by T1/T2/T3, not verified Boonweaver combo or cEDH win.",
          "caution":"Several candidates preselected from N128 exploratory results; interpret CIs as descriptive unadjusted matched intervals, with family-wise multiplicity / selection considerations."}
    if n:
        rows=[found[i] for i in sorted(found)]
        for name,deck in VARIANTS.items():
            counts=collections.Counter(r["arms"][name]["turn"] for r in rows)
            data["arms"][name]={
                "lands":nominal(deck),
                "retains_staff":"Staff of Compleation" in deck,
                "removed":diff(deck)["out"],"added":diff(deck)["in"],
                "counts":{str(t):counts[t] for t in (0,1,2,3)},
                "T1_pct":round(100*counts[1]/n,4),
                "T2_pct":round(100*(counts[1]+counts[2])/n,4),
                "T3_pct":round(100*(counts[1]+counts[2]+counts[3])/n,4),
                "T2_plus_half_exact_T3_pct":round(100*(counts[1]+counts[2]+.5*counts[3])/n,4),
                "mean_keep":round(sum(r["arms"][name]["keep_n"] for r in rows)/n,4)}
            if name!=BASELINE:
                data["paired_vs_current"][name]={
                    f"T{t}":pair(rows,BASELINE,name,t) for t in (1,2,3)}
        for before,after in PREDECLARED_COMPARISONS:
            data["head_to_heads"][after+"_minus_"+before]={
                "before":before,"after":after,
                "card_swap":diff_pair(VARIANTS[before],VARIANTS[after]),
                "T1":pair(rows,before,after,1),
                "T2":pair(rows,before,after,2),
                "T3":pair(rows,before,after,3)}
        data["rank_by_T2_then_T3"]=sorted(
            VARIANTS,key=lambda name:(-data["arms"][name]["T2_pct"],
                       -data["arms"][name]["T3_pct"],name))
    output=Path(out);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(data,indent=2)+"\n")
    with gzip.open(output.with_suffix(".raw.json.gz"),"wt",encoding="utf8") as f:
        json.dump({"schema":SCHEMA,"seed_base":SEED_BASE,"hashes":expected,
                   "rows":[found[i] for i in sorted(found)]},f,separators=(",",":"))
    print("AURA_HELDOUT_POOL",data["status"],"n",n,"missing",len(missing),
          "best",data.get("rank_by_T2_then_T3",[])[:7],flush=True)
    assert not missing,"Reject incomplete held-out sample"

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",action="store_true")
    ap.add_argument("--smoke",action="store_true")
    ap.add_argument("--pool",action="store_true")
    ap.add_argument("--shard",type=int,default=0)
    ap.add_argument("--games",type=int,default=PER_SHARD)
    ap.add_argument("--path",default="shards")
    ap.add_argument("--out",default="shards/aura_heldout_shard_0.json.gz")
    args=ap.parse_args()
    if args.audit:audit()
    elif args.smoke:smoke()
    elif args.pool:pool(args.path,args.out)
    else:run(args.shard,args.games,args.out)
