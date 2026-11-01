"""Pure Python frozen v5 imitation policy for experimental mulligans."""
from __future__ import annotations
import json
from collections import Counter
import dack_mulligan_teacher_features_v13_20261031 as features
from dack_simulator.validation.collect_teacher_london_v13 import finalists
import dack_paired_counterfactual_v1_20261030 as ref
import dack_counterfactual_rules_v2_strict_key_20261030 as strict
import dack_mulligan_stateless_roll_v1_20261031 as dice
from pathlib import Path
import hashlib

POLICY="dack_teacher_distillation_v13"
MODEL=None
MODEL_SHA=None
STATS=Counter()

def install(path="models/dack_teacher_distill_v13_EXPERIMENTAL.json"):
    global MODEL,MODEL_SHA
    m=json.loads(Path(path).read_text())
    if m["schema"]!=features.EXPORT_SCHEMA or m["feature_hash"]!=features.feature_hash():
        raise ValueError("model incompatible with features")
    if m["source_manifest_sha256"]!=ref.source_sha(ref.MANIFEST_PATH):
        raise ValueError("physical manifest mismatch")
    if m["deployed_policy_approved"] is not False:
        raise ValueError("experiment requires unapproved model")
    MODEL=m
    MODEL_SHA=hashlib.sha256(Path(path).read_bytes()).hexdigest()
    dice.install()
    ref.rules=strict
    ref.RULES_VERSION=POLICY+"_"+MODEL_SHA[:16]
    ref.MULLIGAN_POLICY_NAME=POLICY
    ref.MULLIGAN_SAMPLER_NAME="none_frozen_v5_imitation"
    ref.choose_keep=choose_keep
    return MODEL_SHA

def choose_keep(deck_slots,seat,order_by_stage):
    if MODEL is None:raise RuntimeError("model not loaded")
    if deck_slots!=ref.SLOT_VARIANTS["one_key_34"]:
        raise ValueError("model first validated on control physical-99 only")
    history=[]
    for stage,(keep_n,order) in enumerate(zip(ref.sim.STAGES,order_by_stage)):
        seven=tuple(deck_slots[k] for k in order[:7])
        unknown=tuple(deck_slots[k] for k in order[7:])
        pool=Counter(unknown)
        candidates=[]
        for i,item in enumerate(finalists(seven,keep_n,unknown)):
            x=features.extract(seven,item["hand"],item["bottom"],pool,seat,keep_n,stage,item["struct_rank"],i)
            p=features.score_head(MODEL,"choice_trees",x)
            candidates.append((p,-i,item,x))
        selected_vote,negative_rank,selected,x=max(candidates,key=lambda a:(a[0],a[1]))
        keep_vote=features.score_head(MODEL,"keep_trees",x)
        keep=keep_n==1 or keep_vote>=MODEL["keep_cutoff"]
        hand=tuple(selected["hand"]);bottom=tuple(selected["bottom"])
        STATS["stages"]+=1
        STATS["keeps" if keep else "mulls"]+=1
        history.append({"stage":stage,"keep_n":keep_n,"kept":bool(keep),
            "raw":round(keep_vote,7),"sampled_t1":None,
            "threshold":MODEL["keep_cutoff"],"refined":False,
            "policy":POLICY,"model_sha256":MODEL_SHA,
            "teacher_choice_vote":round(selected_vote,7),
            "candidate_index":-negative_rank,
            "seven_slots":list(order[:7]),"seven":list(seven),
            "hand":list(hand),"bottom":list(bottom),
            "hand_slots":ref.selected_slots(order[:7],seven,hand),
            "bottom_slots":ref.selected_slots(order[:7],seven,bottom)})
        if keep:return ref.d.State(1,hand,unknown+bottom),history
    raise AssertionError("no terminal keep")

def audit(path="models/dack_teacher_distill_v13_EXPERIMENTAL.json"):
    assert strict.rule_smoke()["status"]=="PASS"
    install(path)
    report=ref.audit()
    assert report["mulligan_policy"]==POLICY
    return dict(report,model_sha256=MODEL_SHA,mulligan_beam=0,gameplay_beam=160,
                model_approved_for_production=False)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--model",default="models/dack_teacher_distill_v13_EXPERIMENTAL.json")
    p.add_argument("--audit",action="store_true")
    p.add_argument("--game",type=int,default=64000)
    args=p.parse_args()
    report=audit(args.model)
    if args.audit:print("TEACHER_IMITATION_AUDIT_PASS",json.dumps(report),flush=True)
    else:
        if not 64000<=args.game<65000:raise ValueError("require fresh 64k game IDs")
        print("DISTILLED_RESEARCH_GAME",json.dumps(ref.game("one_key_34",args.game)),flush=True)
        print("DISTILLED_RESEARCH_STATS",dict(STATS),flush=True)
