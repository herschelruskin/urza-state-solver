#!/usr/bin/env python3
"""N1024 matched held-out comparison of Key for Tooth/Implements with live Boulder deck.

The actual user-confirmed 99 includes Giant's Boulder instead of World Map.
Basalt Monolith, Bucknard's Everfull Purse, both critical Auras, all other
combo pieces, and original actual lands stay present except each explicit
one-card replacement. Four rainbow land swaps are NOT user-confirmed and are
NOT made here; Pentad Prism is NOT in any arm.

Two diagnostic arms use identical Key-for-X decks but intentionally disable
the NEW legal Bucknard+Key priority-stack double activation, showing whether
this precise rules repair changes simulator speed. Every result is an
optimistic goldfish Dack cast estimate, not guaranteed full combo or win.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
import dack_bucknard_voltaic_stack_20261029 as priority
import dack_actual_current_boulder_20261028 as live
import dack_prism_four_true_rainbow_n512_20261028 as prior

sim=priority.sim
d=sim.d
BASE=tuple(live.ACTUAL_CURRENT_99)
N=1024
SEED_BASE=9914291029102331
SHARD_GAMES=8
SCHEMA="dack_boulder_key_bucknard_stack_paired_n1024_v1"
BEAM=160
POLICY="assertive"
LOCKED=frozenset(("Hardlight Containment","Lunarch Mantle"))
REPAIR=priority.FIX_VERSION
ORIGINAL_512_SEED=prior.SEED_BASE

def change(old,new="Voltaic Key"):
    assert BASE.count(old)==1
    assert new not in BASE
    arr=list(BASE);arr[arr.index(old)]=new
    return tuple(arr)

VARIANTS={
    "current":BASE,
    "key_for_tooth":change("Tooth of Ramos"),
    "key_for_implements":change("Implements of Sacrifice"),
    "key_for_basalt":change("Basalt Monolith"),
    "key_for_tooth_legacy_bucknard":change("Tooth of Ramos"),
    "key_for_implements_legacy_bucknard":change("Implements of Sacrifice"),
}
PAIRS=(
    ("current","key_for_tooth"),
    ("current","key_for_implements"),
    ("current","key_for_basalt"),
    ("key_for_tooth","key_for_implements"),
    ("key_for_basalt","key_for_tooth"),
    ("key_for_tooth_legacy_bucknard","key_for_tooth"),
    ("key_for_implements_legacy_bucknard","key_for_implements"),
)
STACK_DISABLED=frozenset((
    "key_for_tooth_legacy_bucknard",
    "key_for_implements_legacy_bucknard",
))
sim.configure_variants(VARIANTS)
ORIGINAL_SIMULATE=sim.simulate

def simulate_with_priority_gate(name,*args,**kwargs):
    previous=priority.ENABLED
    try:
        priority.ENABLED=name not in STACK_DISABLED
        return ORIGINAL_SIMULATE(name,*args,**kwargs)
    finally:
        priority.ENABLED=previous

sim.simulate=simulate_with_priority_gate

def delta(a,b):
    ca,cb=Counter(a),Counter(b)
    return {"out":sorted((ca-cb).elements()),"in":sorted((cb-ca).elements())}

def audit():
    live.audit()
    priority.fix.exact_source_witnesses()
    w=priority.witness()
    assert w["status"]=="PASS"
    assert N==128*SHARD_GAMES and SHARD_GAMES==prior.GAMES_PER_SHARD
    assert BEAM==sim.GAMEPLAY_BEAM and POLICY==sim.ACTIVE_POLICY
    assert SEED_BASE not in (ORIGINAL_512_SEED,sim.DEFAULT_SEED_BASE,9914281028171137,
                             99142710271850,99142710270201)
    assert len(VARIANTS)==6
    assert set(STACK_DISABLED).issubset(VARIANTS)
    assert sim.deck_hash(BASE)==live.audit()["live_deck_hash"]
    assert "World Map" not in BASE and "Giant's Boulder" in BASE
    assert "Bucknard's Everfull Purse" in BASE and "Basalt Monolith" in BASE
    assert "Voltaic Key" not in BASE and "Pentad Prism" not in BASE
    assert "City of Brass" not in BASE and "Mana Confluence" not in BASE
    assert len(PAIRS)==7
    for name,deck in VARIANTS.items():
        assert len(deck)==99 and LOCKED.issubset(deck),name
        assert live.COMBO_CREATURES.issubset(deck),name
        assert "World Map" not in deck and "Giant's Boulder" in deck,name
        assert "Bucknard's Everfull Purse" in deck and "Pentad Prism" not in deck,name
        assert "Staff of Compleation" in deck,name
        assert "Mana Crypt" not in deck and "Jeweled Lotus" not in deck,name
        assert sum(x in d.LANDS or x in ("Emeria's Call","Razorgrass Ambush") for x in deck)==34,name
        assert len(set(x for x in deck if x!="Plains"))==len([x for x in deck if x!="Plains"]),name
        assert all(x in d.CARD_ID for x in deck),name
        if name=="current":
            assert delta(BASE,deck)=={"out":[],"in":[]}
        else:
            assert deck.count("Voltaic Key")==1,name
            assert delta(BASE,deck)=={"out":[{
                "key_for_tooth":"Tooth of Ramos",
                "key_for_implements":"Implements of Sacrifice",
                "key_for_basalt":"Basalt Monolith",
                "key_for_tooth_legacy_bucknard":"Tooth of Ramos",
                "key_for_implements_legacy_bucknard":"Implements of Sacrifice",
            }[name]],"in":["Voltaic Key"]},name
    assert VARIANTS["key_for_tooth"]==VARIANTS["key_for_tooth_legacy_bucknard"]
    assert VARIANTS["key_for_implements"]==VARIANTS["key_for_implements_legacy_bucknard"]
    sim.configure_variants(VARIANTS)
    print("BOULDER_KEY_BUCKNARD_N1024_AUDIT_PASS",json.dumps({
        "schema":SCHEMA,"N":N,"game_seed_base":SEED_BASE,
        "prior_historical_hash":sim.FROZEN_DECK_HASH,
        "true_user_current_hash":sim.deck_hash(BASE),"fix":REPAIR,
        "stack_legacy_arms":sorted(STACK_DISABLED),
        "hashes":{k:sim.deck_hash(v) for k,v in VARIANTS.items()},
        "swaps":{k:delta(BASE,v) for k,v in VARIANTS.items()},
        "auras":sorted(LOCKED),"no_rainbow_changes":True,
        "bucknard_priority_audit":w}),flush=True)

def smoke():
    audit()
    for name in VARIANTS:
        sim.reset_caches()
        r=sim.simulate(name,999947,policy=POLICY,seed_base=SEED_BASE,beam=BEAM)
        assert r["deck_hash"]==sim.deck_hash(VARIANTS[name])
        assert r["win_turn"] in (0,1,2,3)
        print("BOULDER_KEY_BUCKNARD_SMOKE",name,r["win_turn"],r["keep_n"],flush=True)

# Field-tested per-game fsync, strict pooling, SHA, seed and 1024/1024 checks.
prior.VARIANTS=VARIANTS
prior.N=N
prior.SEED_BASE=SEED_BASE
prior.SCHEMA=SCHEMA
prior.PAIRS=PAIRS
prior.audit=audit
sim.configure_variants(VARIANTS)

def pool(folder,out):
    prior.pool(folder,out)
    with open(out,encoding="utf8") as f: report=json.load(f)
    assert report["status"]=="PASS" and report["n"]==N and report["missing_count"]==0
    assert report["shards_found"]==128 and len(report["arms"])==6
    assert len(report["head_to_heads"])==len(PAIRS)
    assert report["hashes"]["current"]==sim.deck_hash(BASE)
    report["rainbow_lands"]=[]
    report["locked_auras"]=sorted(LOCKED)
    report["source_correction"]=REPAIR
    report["real_user_baseline"]="current has Boulder IN and World Map OUT; original 34 lands"
    report["study_design"]="Fresh matched 1024 game IDs across real Boulder baseline, 3 key-for-one-card alternatives and 2 rule-ablated identical-deck diagnostic controls"
    report["stack_corrected_arms"]=[k for k in VARIANTS if k not in STACK_DISABLED]
    report["stack_disabled_arms"]=sorted(STACK_DISABLED)
    report["scope"]="Optimistic goldfish commander cast by T1 T2 T3. Priority stack Bucknard+Key modeled as 3 generic mana for two independent d4 treasure activations; no opponent interactions."
    for name,deck in VARIANTS.items():
        report["arms"][name]["out"]=delta(BASE,deck)["out"]
        report["arms"][name]["in"]=delta(BASE,deck)["in"]
        report["arms"][name]["key_bucknard_priority"]=name not in STACK_DISABLED
    with open(out,"w",encoding="utf8") as f:json.dump(report,f,indent=2);f.write("\n")
    print("BOULDER_KEY_BUCKNARD_1024_FINAL_PASS",json.dumps({
        "T2_rank":report["rank_by_T2"],
        "T2":{k:v["T2_pct"] for k,v in report["arms"].items()},
        "head_to_heads":{k:v["T2"] for k,v in report["head_to_heads"].items()},
        "n":report["n"]}),flush=True)

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
