#!/usr/bin/env python3
"""N1024 EXACT matched-seed replay after Boonweaver Aura + Gleaming exile repair.

Uses the prior VALIDATED Bucknard-priority study's actual Boulder deck,
the identical assertive mulligan policy, exact game IDs/seat/draw RNG, and
identical four 99-card lists. Recomputes four arms ONLY WITH THE CORRECTED
rules and compares per-game results to frozen old raw n1024 data. Since
all old games are already archived, rerunning the unsafe arms isn't needed.

This is the real user's deck: -World Map +Giant's Boulder, no unapproved
four-rainbow-land swaps, no Pentad Prism. The new guard disallows exiling
required Auras and Gleaming Splendor through both Chrome Mox and Gemstone
Caverns, including Battlefront Chrome. Important: lost Dack lines are NOT
treated as complete combo wins.

Paired outputs quantify exact old/new differences per game, and net Key
swap gain with and without protection. P-values are NOT used to
overinterpret exploratory differences; 95% CI is paired descriptive only.
"""
from __future__ import annotations
import argparse,collections,gzip,json,math
from pathlib import Path
import dack_boonweaver_aura_exile_guard_20261029 as guard
import dack_prism_four_true_rainbow_n512_20261028 as prior
import dack_actual_current_boulder_20261028 as live

sim=guard.sim
d=sim.d
N=1024
SHARD_GAMES=8
SCHEMA="dack_exile_guard_old_seed_matched_n1024_v1"
POLICY="assertive"
BEAM=160
SEED_BASE=9914291029102331 # EXACT already published N1024 seed, deliberately
HISTORIC_RAW=Path("benchmark_results/dack_boulder_key_bucknard_n1024_report.raw.json.gz")
BASE=tuple(live.ACTUAL_CURRENT_99)
OLD_NAMES=("current","key_for_tooth","key_for_implements","key_for_basalt")

def swap_one(old):
    assert old in BASE and "Voltaic Key" not in BASE
    x=list(BASE);x[x.index(old)]="Voltaic Key"
    return tuple(x)

VARIANTS={
    "current":BASE,
    "key_for_tooth":swap_one("Tooth of Ramos"),
    "key_for_implements":swap_one("Implements of Sacrifice"),
    "key_for_basalt":swap_one("Basalt Monolith"),
}
PAIRS=(
    ("current","key_for_tooth"),
    ("current","key_for_implements"),
    ("current","key_for_basalt"),
    ("key_for_tooth","key_for_implements"),
)
OLD_REPORT=Path("benchmark_results/dack_boulder_key_bucknard_n1024_report.json")

def diff(a,b):
    ca,cb=collections.Counter(a),collections.Counter(b)
    return {"out":sorted((ca-cb).elements()),"in":sorted((cb-ca).elements())}

def audit():
    report=guard.audit()
    assert report["status"]=="PASS"
    assert N==SHARD_GAMES*128==1024
    assert sim.ACTIVE_POLICY==POLICY and sim.GAMEPLAY_BEAM==BEAM
    assert SEED_BASE==9914291029102331
    assert len(VARIANTS)==4
    assert "Giant's Boulder" in BASE and "World Map" not in BASE
    assert "Gleaming Splendor" in BASE and "Gemstone Caverns" in BASE
    assert guard.PROTECTED_NON_AURA=={"Gleaming Splendor"}
    assert "Bucknard's Everfull Purse" in BASE
    for name,cards in VARIANTS.items():
        assert len(cards)==99 and sim.root.COMBO.issubset(cards),name
        assert {"Hardlight Containment","Lunarch Mantle","Gleaming Splendor"}.issubset(cards),name
        assert not {"Mana Crypt","Jeweled Lotus"}.intersection(cards),name
        assert len([x for x in cards if x!="Plains"])==len(set(x for x in cards if x!="Plains"))
        assert all(x in d.CARD_ID for x in cards)
        assert sum(x in d.LANDS or x in ("Emeria's Call","Razorgrass Ambush") for x in cards)==34
    assert OLD_REPORT.exists() and HISTORIC_RAW.exists()
    old=json.loads(OLD_REPORT.read_text())
    assert old["n"]==N and old["seed_base"]==SEED_BASE and old["status"]=="PASS"
    assert all(old["hashes"][k]==sim.deck_hash(v) for k,v in VARIANTS.items())
    sim.configure_variants(VARIANTS)
    print("DACK_GUARD_REPLAY_AUDIT_PASS",json.dumps({
        "n":N,"seed_base":SEED_BASE,"schema":SCHEMA,
        "old_report_schema":old["schema"],
        "old_hashes":{k:old["hashes"][k] for k in VARIANTS},
        "new_hashes":{k:sim.deck_hash(v) for k,v in VARIANTS.items()},
        "guard":guard.FIX_VERSION,"locked_auras":sorted(guard.PROTECTED_AURAS),
        "protected_splendor":True,"already_corrected_bucknard":True,
        "land_changes":"none; original user Boulder 34-land deck",
        "same_london_and_goldfish_beam":True}),flush=True)

def smoke():
    audit()
    for name in VARIANTS:
        sim.reset_caches()
        r=sim.simulate(name,10123,policy=POLICY,seed_base=SEED_BASE,beam=BEAM)
        assert r["deck_hash"]==sim.deck_hash(VARIANTS[name])
        assert r["win_turn"] in (0,1,2,3)
        print("GUARD_REPLAY_SMOKE",name,r["win_turn"],r["keep_n"],flush=True)

def paired(old,new,t):
    vals=[int(0<x<=t) for x in old]
    vals2=[int(0<x<=t) for x in new]
    diffs=[b-a for a,b in zip(vals,vals2)]
    n=len(diffs);assert n==N
    mu=sum(diffs)/n
    se=math.sqrt(sum((z-mu)**2 for z in diffs)/(n*(n-1)))
    return {
        "delta_pp":round(100*mu,4),
        "gains":diffs.count(1),"losses":diffs.count(-1),"ties":diffs.count(0),
        "paired_95_ci_pp":[round(100*(mu-1.96*se),4),round(100*(mu+1.96*se),4)],
    }

def pool(folder,out):
    prior.pool(folder,out)
    out=Path(out)
    new=json.loads(out.read_text())
    old=json.loads(OLD_REPORT.read_text())
    with gzip.open(HISTORIC_RAW,"rt",encoding="utf8") as f:
        hist=json.load(f)
    with gzip.open(out.with_suffix(".raw.json.gz"),"rt",encoding="utf8") as f:
        now=json.load(f)
    assert new["n"]==old["n"]==N
    assert new["seed_base"]==old["seed_base"]==SEED_BASE
    assert len(now["rows"])==len(hist["rows"])==N
    assert hist["seed_base"]==now["seed_base"]==SEED_BASE
    assert all(hist["hashes"][k]==now["hashes"][k] for k in VARIANTS)
    actual={x["gid"]:x for x in now["rows"]}
    previous={x["gid"]:x for x in hist["rows"]}
    assert set(actual)==set(previous)==set(range(N))
    old_t={k:[] for k in VARIANTS}
    new_t={k:[] for k in VARIANTS}
    for gid in range(N):
        ra,rb=previous[gid],actual[gid]
        assert set(VARIANTS).issubset(ra["arms"]) and set(VARIANTS)==set(rb["arms"])
        for name in VARIANTS:
            a,b=ra["arms"][name],rb["arms"][name]
            assert a["seed"]==b["seed"]==SEED_BASE+gid*1000003
            assert a["seat"]==b["seat"]
            assert a["turn"] in (0,1,2,3) and b["turn"] in (0,1,2,3)
            old_t[name].append(a["turn"]);new_t[name].append(b["turn"])
    new["replay_comparison"]={
        "original_report":"benchmark_results/dack_boulder_key_bucknard_n1024_report.json",
        "old_mechanics":"Previous Bucknard priority fix, no protected Aura/Splendor Gemstone guard; Splendor Chrome imprint allowed",
        "new_mechanics":guard.FIX_VERSION,
        "paired_n":N,"old_and_new_same_seeds_and_decks":True,
        "by_arm":{k:{
            "old_T2_pct":round(100*sum(0<t<=2 for t in old_t[k])/N,4),
            "new_T2_pct":round(100*sum(0<t<=2 for t in new_t[k])/N,4),
            "T1":paired(old_t[k],new_t[k],1),
            "T2":paired(old_t[k],new_t[k],2),
            "T3":paired(old_t[k],new_t[k],3),
            "keep_n_change_count":sum(previous[i]["arms"][k]["keep_n"]!=actual[i]["arms"][k]["keep_n"] for i in range(N))
        } for k in VARIANTS},
        "old_swaps_vs_current":{
            k:{f"T{t}":paired(old_t["current"],old_t[k],t) for t in (1,2,3)}
            for k in VARIANTS if k!="current"
        },
        "new_swaps_vs_current":{
            k:{f"T{t}":paired(new_t["current"],new_t[k],t) for t in (1,2,3)}
            for k in VARIANTS if k!="current"
        },
    }
    new["real_user_baseline"]="User's live 34-land deck: World Map removed, Giant's Boulder kept; NO rainbow land proposals"
    new["protected_splendor"]=True
    new["rainbow_lands"]=[]
    new["scope"]="Exact same 1024 paired old game IDs replayed with Aura+Gleaming Splendor exile guard, including Chrome Mox, Battlefront and Gemstone Caverns. Not full multiplayer win odds."
    out.write_text(json.dumps(new,indent=2)+"\n")
    print("GUARD_REPLAY_N1024_COMPLETE",json.dumps({
        "old_to_new_T2":{k:v["T2"] for k,v in new["replay_comparison"]["by_arm"].items()},
        "old_swaps_T2":{k:v["T2"] for k,v in new["replay_comparison"]["old_swaps_vs_current"].items()},
        "new_swaps_T2":{k:v["T2"] for k,v in new["replay_comparison"]["new_swaps_vs_current"].items()}
    }),flush=True)

prior.VARIANTS=VARIANTS
prior.N=N
prior.SEED_BASE=SEED_BASE
prior.SCHEMA=SCHEMA
prior.PAIRS=PAIRS
prior.audit=audit
sim.configure_variants(VARIANTS)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",action="store_true")
    ap.add_argument("--smoke",action="store_true")
    ap.add_argument("--pool",action="store_true")
    ap.add_argument("--shard",type=int,default=0)
    ap.add_argument("--games",type=int,default=SHARD_GAMES)
    ap.add_argument("--path",default="shards")
    ap.add_argument("--out",default="shards/prism_true4_shard_0.json.gz")
    a=ap.parse_args()
    if a.audit:audit()
    elif a.smoke:smoke()
    elif a.pool:pool(a.path,a.out)
    else:prior.run(a.shard,a.games,a.out)
