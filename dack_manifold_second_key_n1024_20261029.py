#!/usr/bin/env python3
"""Fresh N1024 paired screen: should a SECOND key be added after -Tooth +Voltaic?

Real user live 34-land Boonweaver deck already has Giant's Boulder, not
World Map. Every arm uses Aura + non-Aura Gleaming Splendor exile protection
and the completed Voltaic/Manifold Bucknard priority stack mechanics.
All three required combo creatures remain in library at the winning check.

Compare live current, single Key for Tooth, and five TWO-key alternatives:
 - Implement of Sacrifice, Everflowing Chalice, Candelabra of Tawnos,
   Coalition Relic, or Basalt Monolith => Manifold Key. All still retain
   Giant's Boulder. Losing Basalt tests whether its Key synergy matters.

FRESH matched random seed, one-free multiplayer London, Assertive, beam160.
T1/T2/T3 endpoints are Dack combo-eligible deployment by that turn.
This 5-cut discovery screen is exploratory, not a proof that the top
arm is globally better. Evaluate paired 95% CIs and T3 tradeoff.
"""
from __future__ import annotations
import argparse,collections,json
import dack_manifold_second_key_stack_20261029 as second
import dack_actual_current_boulder_20261028 as live
import dack_prism_four_true_rainbow_n512_20261028 as prior

sim=second.sim;d=sim.d
BASE=tuple(live.ACTUAL_CURRENT_99)
N=1024
SHARD_GAMES=8
SEED_BASE=9914291029184729
SCHEMA="dack_second_key_manifold_fresh_n1024_v1"
BEAM=160
POLICY="assertive"
LOCKED=frozenset(("Hardlight Containment","Lunarch Mantle","Gleaming Splendor"))
CUTS=("Implements of Sacrifice","Everflowing Chalice","Candelabra of Tawnos","Coalition Relic","Basalt Monolith")

def change(deck,remove,insert):
    assert remove in deck and insert not in deck,(remove,insert)
    x=list(deck);x[x.index(remove)]=insert
    return tuple(x)

ONE_KEY=change(BASE,"Tooth of Ramos","Voltaic Key")
VARIANTS={
    "live_boulder":BASE,
    "one_key_tooth":ONE_KEY,
    "two_keys_implements":change(ONE_KEY,"Implements of Sacrifice","Manifold Key"),
    "two_keys_everflow":change(ONE_KEY,"Everflowing Chalice","Manifold Key"),
    "two_keys_candelabra":change(ONE_KEY,"Candelabra of Tawnos","Manifold Key"),
    "two_keys_coalition":change(ONE_KEY,"Coalition Relic","Manifold Key"),
    "two_keys_basalt":change(ONE_KEY,"Basalt Monolith","Manifold Key"),
}
PAIRS=(
    ("live_boulder","one_key_tooth"),
    ("one_key_tooth","two_keys_implements"),
    ("one_key_tooth","two_keys_everflow"),
    ("one_key_tooth","two_keys_candelabra"),
    ("one_key_tooth","two_keys_coalition"),
    ("one_key_tooth","two_keys_basalt"),
    ("two_keys_implements","two_keys_everflow"),
    ("two_keys_implements","two_keys_candelabra"),
    ("two_keys_implements","two_keys_coalition"),
    ("two_keys_implements","two_keys_basalt"),
)

def diff(deck):
    old,new=collections.Counter(BASE),collections.Counter(deck)
    return {"out":sorted((old-new).elements()),"in":sorted((new-old).elements())}

def audit():
    live.audit()
    assert second.witness()["status"]=="PASS"
    assert N==128*SHARD_GAMES and SHARD_GAMES==prior.GAMES_PER_SHARD
    assert POLICY==sim.ACTIVE_POLICY and BEAM==sim.GAMEPLAY_BEAM
    assert SEED_BASE not in (9914291029102331,9914281028171137,99142710271850,
                             99142710270201,sim.DEFAULT_SEED_BASE)
    assert len(VARIANTS)==7 and len({sim.deck_hash(x) for x in VARIANTS.values()})==7
    assert len(PAIRS)==10
    assert "World Map" not in BASE and "Giant's Boulder" in BASE
    assert sim.deck_hash(BASE)==live.audit()["live_deck_hash"]
    assert {"Bucknard's Everfull Purse","Basalt Monolith","Tooth of Ramos","Implements of Sacrifice",
            "Everflowing Chalice","Candelabra of Tawnos","Coalition Relic"}.issubset(BASE)
    assert not {"Voltaic Key","Manifold Key","Pentad Prism"}.intersection(BASE)
    for name,deck in VARIANTS.items():
        assert len(deck)==99,name
        assert len([x for x in deck if x!="Plains"])==len(set(x for x in deck if x!="Plains")),name
        assert all(x in d.CARD_ID for x in deck),name
        assert sim.root.COMBO.issubset(deck),name
        assert LOCKED.issubset(deck),name
        assert "Bucknard's Everfull Purse" in deck,name
        assert "Giant's Boulder" in deck and "World Map" not in deck,name
        assert "Staff of Compleation" in deck,name
        assert not {"Mana Crypt","Jeweled Lotus","Pentad Prism"}.intersection(deck),name
        assert "City of Brass" not in deck and "Mana Confluence" not in deck,name
        assert sum(x in d.LANDS or x in ("Emeria's Call","Razorgrass Ambush")
                   for x in deck)==34,name
        if name=="live_boulder":
            assert diff(deck)=={"out":[],"in":[]}
            assert "Tooth of Ramos" in deck and not {"Voltaic Key","Manifold Key"}.intersection(deck)
        elif name=="one_key_tooth":
            assert diff(deck)=={"out":["Tooth of Ramos"],"in":["Voltaic Key"]}
        else:
            expected={
                "two_keys_implements":"Implements of Sacrifice",
                "two_keys_everflow":"Everflowing Chalice",
                "two_keys_candelabra":"Candelabra of Tawnos",
                "two_keys_coalition":"Coalition Relic",
                "two_keys_basalt":"Basalt Monolith",
            }[name]
            assert diff(deck)=={"out":sorted(["Tooth of Ramos",expected]),
                                "in":["Manifold Key","Voltaic Key"]},name
            assert "Manifold Key" in deck and "Voltaic Key" in deck
    sim.configure_variants(VARIANTS)
    print("SECOND_KEY_N1024_AUDIT_PASS",json.dumps({
        "schema":SCHEMA,"n":N,"seed_base":SEED_BASE,"beam":BEAM,
        "live_boulder_hash":sim.deck_hash(BASE),
        "hashes":{k:sim.deck_hash(v) for k,v in VARIANTS.items()},
        "cuts":{k:diff(v) for k,v in VARIANTS.items()},
        "guard":second.guard.FIX_VERSION,
        "bucknard_two_key_fix":second.FIX_VERSION,
        "land_changes":0,"rainbow_swaps":0,
        "priority_stack_witness":True,
        "scope":"Dack conditional combo-eligible goldfish deployment T1/T2/T3"}),flush=True)

def smoke():
    audit()
    for name in VARIANTS:
        sim.reset_caches()
        r=sim.simulate(name,34117,policy=POLICY,seed_base=SEED_BASE,beam=BEAM)
        assert r["deck_hash"]==sim.deck_hash(VARIANTS[name])
        assert r["win_turn"] in (0,1,2,3)
        print("SECOND_KEY_SMOKE",name,r["win_turn"],r["keep_n"],flush=True)

prior.VARIANTS=VARIANTS
prior.N=N
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
    report=json.load(open(out,encoding="utf8"))
    assert report["status"]=="PASS" and report["n"]==N
    assert report["shards_found"]==128 and report["missing_count"]==0
    assert len(report["arms"])==len(VARIANTS) and len(report["head_to_heads"])==len(PAIRS)
    report["source_correction"]=[second.guard.FIX_VERSION,second.FIX_VERSION]
    report["no_rainbow_land_swaps"]=True
    report["real_user_baseline"]="Actual Boulder deck (World Map absent, 34 original lands)"
    report["first_key"]="Voltaic Key IN, Tooth of Ramos OUT"
    report["second_key"]="Manifold Key"
    report["scope"]="Fresh paired N1024 game IDs across one- and two-key Boonweaver decks, with Aura/Gleaming exile protection and both-key Bucknard pre-resolution priority interaction, one-free Assertive London mulligan; Dack combo-eligible goldfish deployment."
    report["candidate_selection"]="Exploratory screen of five possible second-key cuts, multiple comparisons apply"
    with open(out,"w",encoding="utf8") as f:json.dump(report,f,indent=2);f.write("\n")
    print("SECOND_KEY_N1024_FINAL_PASS",json.dumps({
        "rank":report["rank_by_T2"],
        "t2":{k:v["T2_pct"] for k,v in report["arms"].items()},
        "t3":{k:v["T3_pct"] for k,v in report["arms"].items()},
        "paired_one_to_two_T2":{k:v["T2"] for k,v in report["head_to_heads"].items() if "_vs_one_key_tooth" in k},
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
