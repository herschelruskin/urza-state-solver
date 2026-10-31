#!/usr/bin/env python3
"""Pure-Python deployable features and calibrated four-way softmax value head.

The model is TRAINED OFFLINE, then exported as canonical JSON.
Scoring a London hand requires no sklearn, NumPy, beam, or revealed draw order.

Class indices: 0=no Dack by T3, 1=Dack on T1, 2=Dack on T2, 3=Dack on T3.
Utility = P(T1)+P(T2)+0.5*P(T3). These are model conditional probabilities,
not proof of legal win or actual cEDH multiplayer outcomes.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import json
import math

import dack_mulligan_analytic_policy_v6_20261031 as analytic
from dack_paired_counterfactual_v1_20261030 import VARIANTS

SCHEMA="dack_multiclass_london_value_features_v8"
CARD_NAMES=tuple(sorted({x for deck in VARIANTS.values() for x in deck}))
FEATURES=(
    "keep_n","seat_is_first","seat_is_not_first",
    "land_in_hand","white_land_in_hand","white_sources_in_hand",
    "unknown_land_count","unknown_white_count",
    "proxy_hand_score","proxy_mana_t2","proxy_white_t2",
    "proxy_land_draw_t2","proxy_white_draw_t2","bricked",
    "n_artifacts","n_ramp","n_tutors",
    "n_two_mana_lands","n_free_mana",
    "has_led_white","has_led_fast","has_key_monolith",
    "has_saga_map","has_bucknard_key",
) + tuple("hand:"+x for x in CARD_NAMES)

def extract(hand,bottom,unknown_counts,seat,keep_n):
    """No future-order field exists. The unseen library is only a multiset."""
    h=tuple(sorted(hand));b=tuple(bottom)
    assert len(h)==int(keep_n)
    unseen=Counter(unknown_counts)
    assert all(n>=0 for n in unseen.values())
    assert len(h)+len(b)==7
    assert sum(unseen.values())==92,("London unknown length",sum(unseen.values()))
    # Compose only the plain card multiset for an existing proxy helper.
    unknown=tuple(card for card,n in sorted(unseen.items()) for _ in range(n))
    p=analytic.proxy_features(h,unknown,seat)
    hs=Counter(h)
    lands=sum(analytic.is_land(c) for c in h)
    white_land=sum(c in analytic.WHITE_LANDS for c in h)
    values={
        "keep_n":float(keep_n),
        "seat_is_first":float(int(seat)==0),
        "seat_is_not_first":float(int(seat)!=0),
        "land_in_hand":float(lands),
        "white_land_in_hand":float(white_land),
        "white_sources_in_hand":float(white_land+sum(c in analytic.REPEAT_WHITE for c in h)),
        "unknown_land_count":float(sum(n for c,n in unseen.items() if analytic.is_land(c))),
        "unknown_white_count":float(sum(n for c,n in unseen.items() if c in analytic.WHITE_LANDS)),
        "proxy_hand_score":float(p["proxy_utility"]),
        "proxy_mana_t2":float(p["expected_mana_t2_proxy"]),
        "proxy_white_t2":float(p["white_t2_proxy"]),
        "proxy_land_draw_t2":float(p["p_draw_land_by_t2"]),
        "proxy_white_draw_t2":float(p["p_draw_white_by_t2"]),
        "bricked":float(p["bricked"]),
        "n_artifacts":float(sum(analytic.d.is_artifact_perm(x) for x in h)),
        "n_ramp":float(sum(x in analytic.d.RAMP_PROTECTED for x in h)),
        "n_tutors":float(sum(x in analytic.TUTORS for x in h)),
        "n_two_mana_lands":float(sum(x in analytic.TWO_LANDS for x in h)),
        "n_free_mana":float(sum(x in {
            "Lion's Eye Diamond","Lotus Petal","Chrome Mox","Mox Diamond",
            "Mox Opal"} for x in h)),
        "has_led_white":float("Lion's Eye Diamond" in h and white_land>0),
        "has_led_fast":float("Lion's Eye Diamond" in h and
                             any(c in h for c in ("Sol Ring","Mana Vault","Grim Monolith"))),
        "has_key_monolith":float("Voltaic Key" in h and
                                any(c in h for c in ("Mana Vault","Grim Monolith","Basalt Monolith"))),
        "has_saga_map":float("Urza's Saga" in h and
                             any(c in h for c in ("Expedition Map","Moonsilver Key"))),
        "has_bucknard_key":float("Bucknard's Everfull Purse" in h and
                                "Voltaic Key" in h)
    }
    return [values.get(name,float(hs[name.split(":",1)[1]])
                       if name.startswith("hand:") else 0.)
            for name in FEATURES]

def feature_hash():
    return hashlib.sha256(json.dumps(FEATURES,separators=(",",":")).encode()).hexdigest()

def softmax(logits):
    m=max(logits)
    e=[math.exp(max(-700.,float(v)-m)) for v in logits]
    total=sum(e)
    return [x/total for x in e]

def probability_from_export(export,features):
    if export.get("schema")!="dack_london_multiclass_softmax_v8":
        raise ValueError("unsupported model export")
    if export.get("feature_sha256")!=feature_hash():
        raise ValueError("feature manifest does not match model")
    if export.get("classes")!=[0,1,2,3]:
        raise ValueError("model is not the full four-outcome distribution")
    if len(features)!=len(FEATURES):
        raise ValueError("feature count mismatch")
    temperature=float(export["temperature"])
    if not 0.<temperature<100.:
        raise ValueError("invalid softmax temperature")
    logits=[(sum(a*b for a,b in zip(row,features))+intercept)/temperature
            for row,intercept in zip(export["coef"],export["intercept"])]
    if len(logits)!=4 or any(not math.isfinite(x) for x in logits):
        raise ValueError("invalid logits")
    result=softmax(logits)
    assert abs(sum(result)-1.)<1e-10
    return result

def expected_utility(probs):
    return probs[1]+probs[2]+0.5*probs[3]

def selftest():
    seen=("Plains","Sol Ring","Boonweaver Giant","Mana Vault","Arcane Signet",
          "Voltaic Key","Gemstone Caverns")
    u=Counter(VARIANTS["one_key_34"])
    for c in seen:u[c]-=1
    u={k:v for k,v in u.items() if v>0}
    a=extract(seen[:-1],seen[-1:],u,seat=2,keep_n=6)
    assert len(a)==len(FEATURES)
    assert all(math.isfinite(x) for x in a)
    base={
        "schema":"dack_london_multiclass_softmax_v8",
        "feature_sha256":feature_hash(),"classes":[0,1,2,3],
        "coef":[[0.]*len(FEATURES) for _ in range(4)],
        "intercept":[0.,0.,0.,0.],"temperature":1.}
    p=probability_from_export(base,a)
    assert p==[.25]*4
    assert expected_utility(p)==.625
    assert abs(sum(probability_from_export(base,a))-1.)<1e-12
    return {"status":"PASS","feature_count":len(FEATURES),
            "feature_sha256":feature_hash(),"no_beam_at_inference":True}

if __name__=="__main__":
    print(json.dumps(selftest(),indent=2))
