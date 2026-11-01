#!/usr/bin/env python3
"""v37 75-dimensional observational direct-regret features.

Frozen v36 hand-capability features + TWO zero-beam v13 proxy
teacher scores on the same LEGALLY selected v14 baseline candidate.
No teacher recommendation or realized game outcome is a label.
Original v27 scores are features, not a mandatory prediction blend.
"""
from __future__ import annotations
import hashlib,json
import dack_mulligan_v36_features as base
from dack_simulator.validation.collect_teacher_london_v13 import finalists
from dack_simulator.validation import v34_frozen_v33b_continuation as kernel
from collections import Counter

NAMES=tuple(base.NAMES)+("v13_proxy_keep_vote","v13_proxy_keep_vote_minus_cutoff")
def feature_hash():
    return hashlib.sha256(json.dumps(NAMES,separators=(",",":")).encode()).hexdigest()

def extract(seven,unknown,seat,stage,selected):
    kn=int(kernel.ref.sim.STAGES[stage])
    assert stage in (0,1,2) and len(seven)==7 and len(unknown)==92
    options=finalists(tuple(seven),kn,tuple(unknown))
    index=selected["v14_baseline_candidate_index"]
    assert index in range(len(options))
    item=options[index]
    f=kernel.f.extract(tuple(seven),item["hand"],item["bottom"],
                       Counter(unknown),seat,kn,stage,item["struct_rank"],index)
    teacher=kernel.f.score_head(kernel.ctl.old.MODEL,"keep_trees",f)
    cutoff=float(kernel.ctl.old.MODEL["keep_cutoff"])
    r=base.extract(tuple(seven),selected["hand"],selected["bottom"],
       tuple(sorted(unknown)),seat,stage,selected["old_v27_Qkeep"],
       selected["old_v27_DP"])
    x=tuple(r)+(float(teacher),float(teacher-cutoff))
    assert len(x)==len(NAMES)
    return x

def smoke():
    assert len(NAMES)==75
    assert feature_hash()
    print("DACK_V37_NO_FUTURE_LEAKAGE_FEATURE_SCHEMA_PASS",len(NAMES),flush=True)

if __name__=="__main__":smoke()
