#!/usr/bin/env python3
"""v33b compact, outcome-regret bottom features (not a rules-equivalence key).

All features depend ONLY on proposed retained cards, the known multiset of
92 unseen cards (not its realized order), and seat. They approximate
candidate *capabilities*, including mana, color and chance interactions.
Never use this descriptor to merge actual gameplay/beam states.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import json
import math
import dack_mulligan_analytic_policy_v6_20261031 as a

d=a.d
NAMES=(
 "lands","white_lands","two_mana_lands",
 "proxy_mana_T2","proxy_white_T2","proxy_T2_probability",
 "ramp","zero_mana","n_artifacts","tutors",
 "enlightened_with_white","led_with_fast_mana",
 "led_with_gardens","vault_key","monolith_key",
 "sol_plus_land","bucknards_key","saga_plus_map",
 "chrome_mox_white_imprints","opal_metalcraft_support",
 "diamond_extra_land","gemstone_exile_fuel",
 "combo_creature_brick","auras_in_hand","rack_or_brainstone",
 "lands_at_least_two","colored_source_and_generic_pair"
)

def feature_hash():
    return hashlib.sha256(json.dumps(NAMES,separators=(",",":")).encode()).hexdigest()

def extract(hand,unknown,seat):
    h=Counter(hand)
    assert sum(h.values())<=7
    assert sum(Counter(unknown).values())==92
    p=a.proxy_features(tuple(hand),tuple(unknown),seat)
    lands=sum(n for c,n in h.items() if a.is_land(c))
    white=sum(n for c,n in h.items() if c in a.WHITE_LANDS)
    two=sum(n for c,n in h.items() if c in a.TWO_LANDS)
    artifacts=sum(int(d.is_artifact_perm(c))*n for c,n in h.items())
    tutors=sum(n for c,n in h.items() if c in a.TUTORS)
    ramp=sum(n for c,n in h.items() if c in d.RAMP_PROTECTED)
    small=sum(h[c] for c in ("Lotus Petal","Lion's Eye Diamond","Chrome Mox","Mox Diamond","Mox Opal"))
    fast=sum(h[c] for c in ("Sol Ring","Mana Vault","Grim Monolith","Ancient Tomb","City of Traitors"))
    monolith=sum(h[c] for c in ("Grim Monolith","Basalt Monolith"))
    keyed=h["Voltaic Key"]+h["Manifold Key"]
    fuel=sum(n for c,n in h.items() if c!="Chrome Mox" and d.chrome_mox_allowed(c))
    racks=h["Scroll Rack"]+h["Brainstone"]
    gemfuel=sum(n for c,n in h.items() if c!="Gemstone Caverns"
            and c not in d.COMBO_CREATURES and c not in d.AURAS
            and c!="Gleaming Splendor")
    vals=(
       lands,white,two,
       min(12.,p["expected_mana_t2_proxy"]),
       min(7.,p["white_t2_proxy"]),
       p["proxy_t2_index"],
       ramp,small,artifacts,tutors,
       int(bool(h["Enlightened Tutor"] and white)),
       int(bool(h["Lion's Eye Diamond"] and fast)),
       int(bool(h["Lion's Eye Diamond"] and h["The Mycosynth Gardens"])),
       int(bool(h["Mana Vault"] and keyed)),
       int(bool(monolith and keyed)),
       int(bool(h["Sol Ring"] and lands)),
       int(bool(h["Bucknard's Everfull Purse"] and keyed)),
       int(bool(h["Urza's Saga"] and (h["Expedition Map"] or h["Moonsilver Key"]))),
       min(3,fuel) if h["Chrome Mox"] else 0,
       min(4,artifacts) if h["Mox Opal"] else 0,
       max(0,lands-1) if h["Mox Diamond"] else 0,
       min(4,gemfuel) if seat!=0 and h["Gemstone Caverns"] else 0,
       int(any(x in d.COMBO_CREATURES for x in h) and not racks),
       sum(n for c,n in h.items() if c in d.AURAS),
       int(bool(racks)),
       int(lands>=2),
       int(bool(white and (two or h["Sol Ring"] or h["Mana Vault"])))
    )
    assert len(vals)==len(NAMES) and all(math.isfinite(float(v)) for v in vals)
    return tuple(float(v) for v in vals)

def difference(base_hand,alt_hand,unknown,seat):
    x=extract(base_hand,unknown,seat)
    z=extract(alt_hand,unknown,seat)
    return tuple(a-b for a,b in zip(z,x))

def selftest():
    import dack_paired_counterfactual_v27_T2_only_DP_20261101 as v27
    assert v27.audit()["status"]=="PASS"
    ref=v27.ref
    seven=["Plains","Ancient Tomb","Chrome Mox","Void Mirror",
           "Lion's Eye Diamond","Boonweaver Giant","Mox Opal"]
    deck=Counter(ref.VARIANTS["one_key_34"])
    for card in seven:assert deck[card];deck[card]-=1
    unknown=tuple(c for c,n in deck.items() for _ in range(n))
    x=extract(seven[:5],unknown,seat=2)
    assert len(x)==len(NAMES)
    assert all(z==0 for z in difference(seven[:5],seven[:5],unknown,2))
    a_hand=["Plains","Ancient Tomb","Chrome Mox","Void Mirror","Lion's Eye Diamond"]
    b_hand=["Plains","Ancient Tomb","Chrome Mox","Mox Opal","Lion's Eye Diamond"]
    assert difference(a_hand,b_hand,unknown,seat=2)!=tuple([0.]*len(NAMES))
    print("DACK_V33B_CAPABILITY_REGRET_FEATURE_SELFTEST_PASS",len(NAMES),flush=True)

if __name__=="__main__":
    selftest()
