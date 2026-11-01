#!/usr/bin/env python3
"""Dependency-free, line-aware v13 teacher-policy forest inference.

Two independently trained heads:
  1. candidate-choice head ranks the original v5 structural top-12;
  2. stage keep head predicts whether v5 would keep the selected candidate.

Unlike v8/v11 four-class outcome probabilities, these are TEACHER-DECISION
scores, NEVER deployment probabilities. The entire observed seven and
remaining unknown MULTISET are legal inputs; future draw order is not.
"""
from __future__ import annotations
from collections import Counter
import hashlib,json,math
import dack_mulligan_learned_features_v8_20261031 as base
from dack_paired_counterfactual_v1_20261030 import VARIANTS
from dack_mulligan_analytic_policy_v6_20261031 import TUTORS,TWO_LANDS,WHITE_LANDS
import dack_paired_counterfactual_v1_20261030 as ref

CARDS=tuple(sorted({c for v in VARIANTS.values() for c in v}))
LINE_GROUPS={
    "led":("Lion's Eye Diamond",),
    "enlightened":("Enlightened Tutor",),
    "tezzeret":("Tezzeret, Cruel Captain",),
    "gardens":("The Mycosynth Gardens",),
    "vault":("Mana Vault",),
    "sol":("Sol Ring",),
    "grim":("Grim Monolith",),
    "tomb":("Ancient Tomb",),
    "city":("City of Traitors",),
    "key":("Voltaic Key",),
    "racks":("Scroll Rack","Brainstone"),
    "gemstone":("Gemstone Caverns",),
    "mox":("Mox Diamond","Chrome Mox","Mox Opal"),
    "white":tuple(WHITE_LANDS),
    "tutor":tuple(TUTORS),
}
INTERACTIONS=(
    ("Enlightened Tutor","The Mycosynth Gardens"),
    ("Lion's Eye Diamond","The Mycosynth Gardens"),
    ("Mana Vault","Voltaic Key"),
    ("Grim Monolith","Voltaic Key"),
    ("Basalt Monolith","Voltaic Key"),
    ("Sol Ring","Lion's Eye Diamond"),
    ("Mana Vault","Lion's Eye Diamond"),
    ("Ancient Tomb","Enlightened Tutor"),
    ("City of Traitors","Enlightened Tutor"),
    ("Gemstone Caverns","Enlightened Tutor"),
    ("Mox Opal","Grim Monolith"),
    ("Bucknard's Everfull Purse","Voltaic Key"),
    ("Tezzeret, Cruel Captain","Grim Monolith"),
    ("Tezzeret, Cruel Captain","Mana Vault"),
    ("Enlightened Tutor","Sol Ring"),
    ("Ancient Den","Mox Opal"),
)
EXTRA=(
    "london_stage","structural_score",
    "structural_contamination","structural_auras",
    "structural_finalist_rank",
    "seven_lands","seven_white_sources","seven_tutor_count",
    "bottom_lands","bottom_white_sources","bottom_ramp",
    "bottom_tutors",
    "hand_key_cards","seven_key_cards",
    "enlightened_white_t1","gardens_led_t1","fast_generic_t1",
    "mana_vault_tomb","mana_vault_city",
    "sol_tomb","sol_city",
    "can_produce_white_and_two_generic",
) + tuple("seven:"+c for c in CARDS
) + tuple("bottom:"+c for c in CARDS
) + tuple("pair:"+a+"|"+b for a,b in INTERACTIONS
) + tuple("group:"+g for g in LINE_GROUPS)
FEATURES=tuple(base.FEATURES)+EXTRA
SCHEMA="dack_v13_line_aware_teacher_forest_features"
EXPORT_SCHEMA="dack_v13_teacher_forest_export_v1"

def feature_hash():
    return hashlib.sha256(json.dumps(FEATURES,separators=(",",":")).encode()).hexdigest()

def extract(seven,hand,bottom,unknown_counts,seat,keep_n,stage,
            struct_rank,finalist_rank):
    seven=tuple(seven);hand=tuple(hand);bottom=tuple(bottom)
    if len(seven)!=7 or len(hand)!=int(keep_n) or len(hand)+len(bottom)!=7:
        raise ValueError("invalid London visible hand")
    if Counter(hand)+Counter(bottom)!=Counter(seven):
        raise ValueError("London physical card multiset differs from opening seven")
    if sum(unknown_counts.values())!=92:
        raise ValueError("hidden deck must contain 92 cards")
    base_features=base.extract(hand,bottom,unknown_counts,seat,keep_n)
    h=Counter(hand);s=Counter(seven);b=Counter(bottom)
    hr=set(hand)
    doubles=sum(c in TWO_LANDS for c in hand)
    whites=sum(c in WHITE_LANDS for c in hand)
    ramp=ref.d.RAMP_PROTECTED
    def count(pool,items):return float(sum(pool[x] for x in items))
    extras={
        "london_stage":float(stage),
        "structural_score":float(struct_rank[0]),
        "structural_contamination":float(struct_rank[1]),
        "structural_auras":float(struct_rank[2]),
        "structural_finalist_rank":float(finalist_rank),
        "seven_lands":float(sum(base.analytic.is_land(c) for c in seven)),
        "seven_white_sources":count(s,WHITE_LANDS),
        "seven_tutor_count":count(s,TUTORS),
        "bottom_lands":float(sum(base.analytic.is_land(c) for c in bottom)),
        "bottom_white_sources":count(b,WHITE_LANDS),
        "bottom_ramp":count(b,ramp),
        "bottom_tutors":count(b,TUTORS),
        "hand_key_cards":count(h,{"Voltaic Key","Moonsilver Key"}),
        "seven_key_cards":count(s,{"Voltaic Key","Moonsilver Key"}),
        "enlightened_white_t1":float("Enlightened Tutor" in hr and whites>0),
        "gardens_led_t1":float("The Mycosynth Gardens" in hr and "Lion's Eye Diamond" in hr),
        "fast_generic_t1":float(any(x in hr for x in ("Sol Ring","Mana Vault","Ancient Tomb","City of Traitors"))),
        "mana_vault_tomb":float("Mana Vault" in hr and "Ancient Tomb" in hr),
        "mana_vault_city":float("Mana Vault" in hr and "City of Traitors" in hr),
        "sol_tomb":float("Sol Ring" in hr and "Ancient Tomb" in hr),
        "sol_city":float("Sol Ring" in hr and "City of Traitors" in hr),
        "can_produce_white_and_two_generic":float(whites>0 and
            (doubles>0 or "Sol Ring" in hr or "Mana Vault" in hr)),
    }
    for card in CARDS:
        extras["seven:"+card]=float(s[card])
        extras["bottom:"+card]=float(b[card])
    for a,c in INTERACTIONS:
        extras["pair:"+a+"|"+c]=float(a in hr and c in hr)
    for g,names in LINE_GROUPS.items():
        extras["group:"+g]=float(any(x in hr for x in names))
    result=base_features+[extras[name] for name in EXTRA]
    if len(result)!=len(FEATURES) or any(not math.isfinite(float(x)) for x in result):
        raise AssertionError("invalid feature vector")
    return result

def score_head(model,head,features):
    if model.get("schema")!=EXPORT_SCHEMA or model.get("feature_hash")!=feature_hash():
        raise ValueError("model or feature schema mismatch")
    trees=model.get(head)
    if not isinstance(trees,list) or not trees:
        raise ValueError("missing trained forest head: "+head)
    if len(features)!=len(FEATURES):
        raise ValueError("feature vector mismatch")
    total=0.0
    for tree in trees:
        children_left=tree["left"];children_right=tree["right"]
        feat=tree["feature"];threshold=tree["threshold"];value=tree["positive"]
        i=0;depth=0
        while children_left[i]>=0:
            j=int(feat[i])
            if j<0 or j>=len(features):raise ValueError("invalid split feature")
            i=children_left[i] if features[j]<=threshold[i] else children_right[i]
            depth+=1
            if depth>30:raise ValueError("invalid depth")
        total+=float(value[i])
    answer=total/len(trees)
    return max(0.0,min(1.0,answer))

def selftest():
    from dack_simulator.validation.collect_teacher_london_v13 import finalists
    seven=["Plains","Ancient Tomb","Enlightened Tutor","The Mycosynth Gardens",
           "Mana Vault","Voltaic Key","Mind Stone"]
    unknown=Counter(ref.VARIANTS["one_key_34"])
    for c in seven:unknown[c]-=1
    unknown={k:v for k,v in unknown.items() if v>0}
    choices=finalists(seven,6,unknown)
    for i,c in enumerate(choices):
        x=extract(seven,c["hand"],c["bottom"],unknown,2,6,2,
                  c["struct_rank"],i)
        assert len(x)==len(FEATURES)
    assert choices
    return {"status":"PASS","feature_count":len(FEATURES),
            "feature_hash":feature_hash(),"pure_python_inference":True}

if __name__=="__main__":
    print(json.dumps(selftest(),indent=2))
