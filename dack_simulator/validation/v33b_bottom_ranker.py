#!/usr/bin/env python3
"""v33b: compare *existing* zero-beam bottom rankers on the same legal finalists.

No training here and no realized future order. Only seven, unknown 92-card
MULTISET, seat and London stage enter bottom selection. v27's Qkeep and
v18's candidate utility are not calibrated across arbitrary alternatives.
This is a screening experiment, not a deployable policy.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import json
import dack_mulligan_teacher_features_v13_20261031 as features
import dack_mulligan_keep_value_v22_20261101 as keep
import dack_mulligan_candidate_value_v18_20261101 as candidate_value
import dack_mulligan_analytic_policy_v6_20261031 as analytic
from dack_simulator.validation.collect_teacher_london_v13 import finalists

V18_PATH="models/dack_v18_paired_candidate_utility_EXPERIMENTAL.json"
METHODS=("v14_frozen","v27_Qkeep","v18_top3","analytic_t2")
V18=None

def load_v18():
    global V18
    if V18 is None:
        model=json.loads(Path(V18_PATH).read_text())
        assert model["schema"]==candidate_value.SCHEMA
        assert model["feature_hash"]==features.feature_hash()
        assert model["deployed_policy_approved"] is False
        assert model["selection_uses_structural_first_three_only"]
        V18=model
    return V18

def rank(seven,kn,unknown,seat,stage,student_model,keep_model):
    assert len(seven)==7 and len(unknown)==92
    assert kn in (7,6,5,4,3,2,1)
    assert sum(Counter(seven).values())==7
    pool=Counter(unknown)
    options=finalists(seven,kn,unknown)
    assert options and len(options)<=12
    vm=load_v18() if kn in (3,4,5,6) else None
    scores=[]
    for i,c in enumerate(options):
        h=tuple(c["hand"]);bottom=tuple(c["bottom"])
        assert Counter(h)+Counter(bottom)==Counter(seven)
        x=features.extract(seven,h,bottom,pool,seat,kn,stage,c["struct_rank"],i)
        f14=features.score_head(student_model,"choice_trees",x)
        q27=keep.predict(keep_model,x)
        v18=(candidate_value.predict(vm,x) if vm is not None and i<3 else None)
        p=analytic.proxy_features(h,unknown,seat)
        scores.append({"index":i,"v14_vote":f14,"Qkeep_T2":q27,
                       "v18_U":v18,"analytic_T2":p["proxy_t2_index"]})
    baseline=max(range(len(scores)),key=lambda i:(scores[i]["v14_vote"],-i))
    q=max(range(len(scores)),key=lambda i:(scores[i]["Qkeep_T2"],-i))
    approx=max(range(len(scores)),key=lambda i:(scores[i]["analytic_T2"],-i))
    vv=max(range(min(len(scores),3)),key=lambda i:(scores[i]["v18_U"]
           if scores[i]["v18_U"] is not None else -1.,-i))
    chosen=dict(zip(METHODS,(baseline,q,vv,approx)))
    return options,scores,chosen

def selftest():
    import dack_paired_counterfactual_v27_T2_only_DP_20261101 as v27
    report=v27.audit()
    assert report["status"]=="PASS"
    import dack_paired_counterfactual_v22_all_stage_real_keep_DP_20261101 as ctl
    ref=ctl.ref
    seven=("Plains","Mana Vault","Chrome Mox","Void Mirror",
           "Lion's Eye Diamond","Mox Opal","Boonweaver Giant")
    cards=Counter(ref.VARIANTS["one_key_34"])
    for c in seven:
        assert cards[c];cards[c]-=1
    unknown=tuple(c for c,n in cards.items() for _ in range(n))
    assert len(unknown)==92
    for stage,kn in enumerate((7,7,6,5,4,3,2,1)):
        opts,sc,selected=rank(seven,kn,unknown,2,stage,ctl.old.MODEL,ctl.MODEL)
        assert set(selected)==set(METHODS)
        assert all(0<=i<len(opts) for i in selected.values())
        assert all(Counter(c["hand"])+Counter(c["bottom"])==Counter(seven)
                   for c in opts)
        assert len(sc)==len(opts)
    assert stage==7
    print("DACK_V33B_BOTTOM_RANKER_SELFTEST_PASS",flush=True)

if __name__=="__main__":
    selftest()
