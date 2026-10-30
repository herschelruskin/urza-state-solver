#!/usr/bin/env python3
"""Independent one-Key 34/35/36-land and Untaidake vs Plains holdout.

Start from user's actual Boulder 99. Tooth -> Voltaic Key only;
KEEP Implements; NO second Manifold Key. Seven deck arms isolate
Untaidake at 34 and at 36 lands, plus Mind Stone and Everflowing cuts.
No unapproved rainbow swaps, no banned cards. Preserve all protected
Auras, Gleaming Splendor and legal first-Key Bucknard stack actions.
Fresh matched game seeds, 64 shards x 16 seeds = N1024 per arm.
"""
from __future__ import annotations
import argparse, json
import dack_boonweaver_aura_exile_guard_20261029 as validated
import dack_actual_current_boulder_20261028 as live
import dack_prism_four_true_rainbow_n512_20261028 as prior

sim=validated.sim
d=sim.d
SOURCE=tuple(live.ACTUAL_CURRENT_99)
N=1024
SHARD_GAMES=16
BEAM=160
POLICY="assertive"
SEED_BASE=9914301030011429
SCHEMA="dack_onekey_36lands_untaidake_n1024_20261030_v1"
LOCKED=frozenset(("Hardlight Containment","Lunarch Mantle","Gleaming Splendor"))

def change(deck,old,new):
    cards=list(deck)
    assert old in cards
    assert new=="Plains" or new not in cards
    cards[cards.index(old)]=new
    return tuple(cards)

ONE=change(SOURCE,"Tooth of Ramos","Voltaic Key")
BASE=ONE
VARIANTS={
    "current":BASE,
    "no_untaidake":change(BASE,"Untaidake, the Cloud Keeper","Plains"),
    "land35_mindstone":change(BASE,"Mind Stone","Plains"),
    "land35_everflow":change(BASE,"Everflowing Chalice","Plains"),
    "land36_both":change(change(BASE,"Mind Stone","Plains"),
                         "Everflowing Chalice","Plains"),
    "land35_everflow_no_unt":change(change(BASE,
                         "Everflowing Chalice","Plains"),
                         "Untaidake, the Cloud Keeper","Plains"),
    "land36_both_no_unt":change(change(change(BASE,
                         "Mind Stone","Plains"),"Everflowing Chalice","Plains"),
                         "Untaidake, the Cloud Keeper","Plains"),
}
PAIRS=(
    ("current","no_untaidake"),
    ("current","land35_mindstone"),
    ("current","land35_everflow"),
    ("current","land36_both"),
    ("current","land36_both_no_unt"),
    ("no_untaidake","land35_everflow_no_unt"),
    ("land35_everflow","land35_everflow_no_unt"),
    ("land36_both","land36_both_no_unt"),
    ("land35_everflow","land36_both"),
    ("land35_everflow_no_unt","land36_both_no_unt"),
)
sim.configure_variants(VARIANTS)

def audit():
    assert validated.audit()["status"]=="PASS"
    live.audit()
    assert N==64*SHARD_GAMES and POLICY==sim.ACTIVE_POLICY and BEAM==sim.GAMEPLAY_BEAM
    assert SEED_BASE not in (9914291029102331,9914291029184729,9914281028171137,sim.DEFAULT_SEED_BASE)
    assert "Giant's Boulder" in SOURCE and "World Map" not in SOURCE
    assert "Voltaic Key" in BASE and "Manifold Key" not in BASE
    assert "Tooth of Ramos" not in BASE and "Implements of Sacrifice" in BASE
    assert len(set(sim.deck_hash(v) for v in VARIANTS.values()))==len(VARIANTS)
    assert "Untaidake, the Cloud Keeper" in BASE
    assert "Mind Stone" in BASE and "Everflowing Chalice" in BASE
    assert len(VARIANTS)==7 and len(PAIRS)==10
    for k,deck in VARIANTS.items():
        assert len(deck)==99 and LOCKED.issubset(deck),k
        assert sim.root.COMBO.issubset(deck),k
        assert "Giant's Boulder" in deck and "Bucknard's Everfull Purse" in deck,k
        assert "Voltaic Key" in deck and "Manifold Key" not in deck,k
        assert "Implements of Sacrifice" in deck,k
        assert not {"Mana Crypt","Jeweled Lotus","Pentad Prism"}.intersection(deck),k
        assert not {"City of Brass","Mana Confluence"}.intersection(deck),k
        assert len([x for x in deck if x!="Plains"])==len(set(x for x in deck if x!="Plains")),k
        assert all(x in d.CARD_ID for x in deck),k
        nland=sum(x in d.LANDS or x in ("Emeria's Call","Razorgrass Ambush") for x in deck)
        assert 34<=nland<=36,(k,nland)
    sim.configure_variants(VARIANTS)
    print("PARALLEL_DECK_AUDIT_PASS",json.dumps({
        "schema":SCHEMA,"n":N,"names":list(VARIANTS),
        "hashes":{k:sim.deck_hash(v) for k,v in VARIANTS.items()},
        "seed_base":SEED_BASE,"land_counts":{
            k:sum(x in d.LANDS or x in ("Emeria's Call","Razorgrass Ambush")
                  for x in v) for k,v in VARIANTS.items()},
        "exile_guard":validated.FIX_VERSION,
        "first_key_priority":validated.priority.FIX_VERSION}),flush=True)

def smoke():
    audit()
    for name in VARIANTS:
        sim.reset_caches()
        x=sim.simulate(name,88413,policy=POLICY,seed_base=SEED_BASE,beam=BEAM)
        assert x["deck_hash"]==sim.deck_hash(VARIANTS[name])
        assert x["win_turn"] in (0,1,2,3)
        print("PARALLEL_SMOKE_PASS",name,x["win_turn"],x["keep_n"],flush=True)

prior.VARIANTS=VARIANTS
prior.N=N
prior.GAMES_PER_SHARD=SHARD_GAMES
prior.SEED_BASE=SEED_BASE
prior.SCHEMA=SCHEMA
prior.PAIRS=PAIRS
prior.BASE=BASE
prior.LOCKED=LOCKED
prior.RAINBOW=()
prior.audit=audit
sim.configure_variants(VARIANTS)

def pool(folder,out):
    prior.pool(folder,out)
    with open(out) as f: report=json.load(f)
    assert report["status"]=="PASS" and report["n"]==N
    assert report["missing_count"]==0 and report["shards_found"]==64
    assert len(report["head_to_heads"])==len(PAIRS)
    report.update({
        "study_objective":"Fresh one-Key: 34/35/36 land re-evaluation and Untaidake-vs-Plains at 34 and 36 lands. Land count changes also remove Everflowing and/or Mind Stone.",
        "actual_boulder_deck":True,
        "one_key_baseline":"Voltaic for Tooth; Implements retained, Manifold absent",
        "guard_version":validated.FIX_VERSION,
        "first_key_bucknard_version":validated.priority.FIX_VERSION,
        "original_34_land_slots":34,
        "land_counts":{k:sum(x in d.LANDS or x in ("Emeria's Call","Razorgrass Ambush") for x in v) for k,v in VARIANTS.items()},
        "fresh_seed":True,"exploratory_multiple_comparisons":True})
    with open(out,"w") as f:json.dump(report,f,indent=2);f.write("\n")
    print("PARALLEL_POOL_PASS",SCHEMA,
          json.dumps({"rank_T2":report["rank_by_T2"],
                      "T2":{k:v["T2_pct"] for k,v in report["arms"].items()},
                      "T3":{k:v["T3_pct"] for k,v in report["arms"].items()},
                      "pairs_T2":{k:v["T2"] for k,v in report["head_to_heads"].items()}}),
          flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",action="store_true")
    ap.add_argument("--smoke",action="store_true")
    ap.add_argument("--pool",action="store_true")
    ap.add_argument("--shard",type=int,default=0)
    ap.add_argument("--games",type=int,default=SHARD_GAMES)
    ap.add_argument("--path",default="shards")
    ap.add_argument("--out",default="shards/prism_true4_shard_0.json.gz")
    args=ap.parse_args()
    if args.audit:audit()
    elif args.smoke:smoke()
    elif args.pool:pool(args.path,args.out)
    else:prior.run(args.shard,args.games,args.out)
