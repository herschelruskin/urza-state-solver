#!/usr/bin/env python3
"""Independent predeclared N2048 Assertive mana-corrected Key + Prism slot tests.

Use exactly the Mox Diamond, Mox Opal, Mycosynth Gardens, Talon Gates,
Prismatic Lens, Coalition Relic and Giant's Boulder corrections validated
by dack_prism_color_sources_20261028.py. FOUR genuinely offcolor lands:
City of Brass, Mana Confluence, Tarnished Citadel, Gemstone Mine.

The earlier N512 study only nominated packages; this is a fresh paired-seed
confirmation with a limited set of plausible cut locations. Outcomes are
Dack CAST (optimistic), NOT full Boonweaver combo wins. Both auras remain
in all arms. Staff is preserved in all arms. Implements as an alternative
cut is exploratory: downstream combo sacrifice routes still need verification.
"""
from __future__ import annotations
import argparse, json
from collections import Counter
import dack_prism_four_true_rainbow_n512_20261028 as prior

sim=prior.sim
fix=prior.fix
N=2048
SHARD_GAMES=8
SEED_BASE=9914281028171137
SCHEMA="dack_prism_key_cuts_four_rainbow_paired_n2048_v1"
POLICY="assertive"
BEAM=160
TRUE4=tuple(prior.TRUE4)
BASE=tuple(prior.BASE)
RAINBOW=tuple(prior.RAINBOW)
LOCKED=frozenset(("Hardlight Containment","Lunarch Mantle"))
CANDIDATE_CUTS=("World Map","Tooth of Ramos","Implements of Sacrifice","Everflowing Chalice")
EXPECTED_HASH="a1c8e05dc3f9e1bcfbfbe2f7773ea4a5e62222d3440dd2f7417fd7f2f058c422"

def change(*pairs):
    return prior.mutate(TRUE4,pairs)

# A separate deck for each independent combination, preserving 99 slots.
# Source/target correspondences intentionally explicit so paired comparisons
# isolate whichever card was removed while holding the background fixed.
VARIANTS={
    "current":BASE,
    "true4":TRUE4,
    "true4_map_boulder":change(("World Map","Giant's Boulder")),
    "true4_map_basalt_boulder_key":change(
        ("World Map","Giant's Boulder"),("Basalt Monolith","Voltaic Key")),
    "true4_map_basalt_prism_key":change(
        ("World Map","Pentad Prism"),("Basalt Monolith","Voltaic Key")),
    "true4_map_basalt_boulder_prism":change(
        ("World Map","Giant's Boulder"),("Basalt Monolith","Pentad Prism")),
    "true4_basalt_prism":change(("Basalt Monolith","Pentad Prism")),
    "true4_basalt_tooth_prism_key":change(
        ("Basalt Monolith","Pentad Prism"),("Tooth of Ramos","Voltaic Key")),
    "true4_basalt_implements_prism_key":change(
        ("Basalt Monolith","Pentad Prism"),("Implements of Sacrifice","Voltaic Key")),
    "true4_basalt_everflow_prism_key":change(
        ("Basalt Monolith","Pentad Prism"),("Everflowing Chalice","Voltaic Key")),
    "true4_map_tooth_prism_key":change(
        ("World Map","Pentad Prism"),("Tooth of Ramos","Voltaic Key")),
    "true4_map_implements_prism_key":change(
        ("World Map","Pentad Prism"),("Implements of Sacrifice","Voltaic Key")),
    "true4_map_basalt_tooth_boulder_prism_key":change(
        ("World Map","Giant's Boulder"),
        ("Basalt Monolith","Pentad Prism"),("Tooth of Ramos","Voltaic Key")),
    "true4_map_basalt_implements_boulder_prism_key":change(
        ("World Map","Giant's Boulder"),
        ("Basalt Monolith","Pentad Prism"),("Implements of Sacrifice","Voltaic Key")),
}
assert len(VARIANTS)==14
PRIMARY_ARMS=(
    "true4_map_basalt_boulder_key",
    "true4_map_basalt_prism_key",
    "true4_map_basalt_boulder_prism",
)
# Predeclared matched conditional contrasts; labels always AFTER-minus-BEFORE.
PAIRS=(
    ("current","true4"),
    ("true4","true4_basalt_prism"),
    ("true4_map_basalt_prism_key","true4_map_basalt_boulder_key"),
    ("true4_map_basalt_boulder_prism","true4_map_basalt_boulder_key"),
    ("true4_map_basalt_boulder_prism","true4_map_basalt_prism_key"),
    ("true4_map_boulder","true4_map_basalt_boulder_key"),
    ("true4_basalt_prism","true4_basalt_tooth_prism_key"),
    ("true4_basalt_prism","true4_basalt_implements_prism_key"),
    ("true4_basalt_prism","true4_basalt_everflow_prism_key"),
    ("true4_map_basalt_prism_key","true4_map_basalt_tooth_boulder_prism_key"),
    ("true4_map_basalt_prism_key","true4_map_basalt_implements_boulder_prism_key"),
    ("true4_map_basalt_tooth_boulder_prism_key","true4_map_basalt_implements_boulder_prism_key"),
    ("true4_basalt_tooth_prism_key","true4_map_tooth_prism_key"),
    ("true4_basalt_implements_prism_key","true4_map_implements_prism_key"),
)

def diff_between(a,b):
    ca,cb=Counter(a),Counter(b)
    return {"out":sorted((ca-cb).elements()),"in":sorted((cb-ca).elements())}

def audit():
    assert POLICY==sim.ACTIVE_POLICY and BEAM==sim.GAMEPLAY_BEAM
    assert N==256*SHARD_GAMES and SHARD_GAMES==prior.GAMES_PER_SHARD
    assert SEED_BASE not in (prior.SEED_BASE,sim.DEFAULT_SEED_BASE,
                             99142710271850,99142710270201)
    assert sim.deck_hash(BASE)==EXPECTED_HASH
    assert len(VARIANTS)==14 and len({sim.deck_hash(x) for x in VARIANTS.values()})==14
    assert len(PAIRS)==14
    assert set(PRIMARY_ARMS).issubset(VARIANTS)
    assert len(set(RAINBOW))==4 and "Command Tower" not in RAINBOW
    assert diff_between(VARIANTS["true4_map_basalt_prism_key"],
                        VARIANTS["true4_map_basalt_boulder_key"])=={
                            "out":["Pentad Prism"],"in":["Giant's Boulder"]}
    assert diff_between(VARIANTS["true4_map_basalt_boulder_prism"],
                        VARIANTS["true4_map_basalt_boulder_key"])=={
                            "out":["Pentad Prism"],"in":["Voltaic Key"]}
    assert diff_between(VARIANTS["true4_basalt_tooth_prism_key"],
                        VARIANTS["true4_map_tooth_prism_key"])=={
                            "out":["World Map"],"in":["Basalt Monolith"]}
    for name,deck in VARIANTS.items():
        assert len(deck)==99 and LOCKED.issubset(deck),name
        assert sim.root.COMBO.issubset(deck),name
        assert all(x in sim.d.CARD_ID for x in deck),name
        assert not {"Jeweled Lotus","Mana Crypt"}.intersection(deck),name
        assert deck.count("Staff of Compleation")==1,name
        assert deck.count("Mox Diamond")==1 and deck.count("Mox Opal")==1,name
        assert deck.count("The Mycosynth Gardens")==1,name
        assert deck.count("Prismatic Lens")==1 and deck.count("Coalition Relic")==1,name
        assert prior.land_count(deck)==34,name
        nonbasics=[x for x in deck if x!="Plains"]
        assert len(nonbasics)==len(set(nonbasics)),name
        if name!="current":
            assert all(x in deck for x in RAINBOW),name
        if "prism_key" in name:
            assert "Pentad Prism" in deck and "Voltaic Key" in deck,name
        if "boulder_prism_key" in name:
            assert "Giant's Boulder" in deck,name
        if "implements" not in name:
            assert "Implements of Sacrifice" in deck,name
    fix.exact_source_witnesses()
    sim.configure_variants(VARIANTS)
    print("PRISM_KEY_SLOT_N2048_AUDIT_PASS",json.dumps({
        "n":N,"schema":SCHEMA,"beam":BEAM,"policy":POLICY,"seed_base":SEED_BASE,
        "ramp_base_hash":EXPECTED_HASH,"rainbow":RAINBOW,"locked":sorted(LOCKED),
        "source_fix":fix.FIX_VERSION,
        "hashes":{k:sim.deck_hash(v) for k,v in VARIANTS.items()},
        "diffs":{k:prior.diff(v) for k,v in VARIANTS.items()},
        "predeclared_pairs":PAIRS}),flush=True)

def smoke():
    audit()
    for gid in (999995,):
        for name in ("current","true4_map_basalt_boulder_key",
                     "true4_map_basalt_prism_key",
                     "true4_basalt_implements_prism_key",
                     "true4_map_basalt_tooth_boulder_prism_key"):
            sim.reset_caches()
            r=sim.simulate(name,gid,policy=POLICY,seed_base=SEED_BASE,beam=BEAM)
            assert r["deck_hash"]==sim.deck_hash(VARIANTS[name])
            assert r["win_turn"] in (0,1,2,3)
            print("PRISM_KEY_SLOT_SMOKE_PASS",gid,name,r["win_turn"],r["keep_n"],flush=True)

# Reuse the field-tested fsynced shard/pooling implementation. All configuration
# lives in prior module globals, set ONCE before the run. No old observations.
prior.VARIANTS=VARIANTS
prior.N=N
prior.SEED_BASE=SEED_BASE
prior.SCHEMA=SCHEMA
prior.PAIRS=PAIRS
prior.audit=audit
sim.configure_variants(VARIANTS)

def pool(folder,out):
    prior.pool(folder,out)
    p=json.load(open(out))
    assert p["status"]=="PASS" and p["n"]==N and p["missing_count"]==0
    assert p["shards_found"]==256 and len(p["arms"])==14
    assert len(p["head_to_heads"])==len(PAIRS)
    p["study_design"]="Independent N2048 direct confirmation of N512 speed finalists plus exploratory Key+Prism extra-card cut search. Predeclared, same seeds and samples across arms."
    p["primary_confirmatory_arms"]=list(PRIMARY_ARMS)
    p["exploratory_extra_slot_candidates"]=list(CANDIDATE_CUTS)
    p["interpretation_limit"]="Dack casting only, not fully verified Boonweaver combo; Implements-of-Sacrifice alternative may remove useful post-Dack lines."
    with open(out,"w") as f:json.dump(p,f,indent=2);f.write("\n")
    print("PRISM_KEY_SLOT_N2048_VERIFIED_REPORT_PASS",p["rank_by_T2"],flush=True)

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
