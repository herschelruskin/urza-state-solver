"""V23 research-only T2-first REAL keep-vs-continuation London policy.

Exactly the same candidate bottom selection as v14-128 for every London
stage (to isolate the keep/mull decision). Predict conditional goldfish
U from the directly labeled all-stage v22 forest and compare it against
OFFLINE computed per-seat continuation expectation C_k. First free seven
compares against C_7, second seven against C_6, then C_5..C_1.

No beam search in mulligans. Actual goldfish after keep retains the same
physical 99 card slots, strict stable dice and beam160 gameplay.
"""
from __future__ import annotations
from collections import Counter
import hashlib,json
from pathlib import Path
import dack_paired_counterfactual_v13_teacher_distill_20261031 as old
import dack_mulligan_teacher_features_v13_20261031 as f
import dack_mulligan_keep_value_v22_20261101 as estimator
from dack_simulator.validation.collect_teacher_london_v13 import finalists

ref=old.ref
POLICY="dack_v23_T2_only_real_keep_london_DP_experimental"
MODEL_PATH="models/dack_v23_T2_only_real_keep_value_EXPERIMENTAL.json"
DP_PATH="models/dack_v23_T2_only_continuations_EXPERIMENTAL.json"
KEEP_BASELINE="models/v14_curve/v14_teacher_groups_128.json"
MODEL=None
DP=None
MODEL_SHA=None
DP_SHA=None
STATS=Counter()

def install(modelpath=MODEL_PATH,dppath=DP_PATH):
    global MODEL,DP,MODEL_SHA,DP_SHA
    source_sha=old.install(KEEP_BASELINE)
    a=Path(modelpath);b=Path(dppath)
    m=json.loads(a.read_text());dp=json.loads(b.read_text())
    if m["schema"]!=estimator.SCHEMA:
        raise ValueError("wrong real keep model")
    if m["feature_hash"]!=f.feature_hash():
        raise ValueError("keep value feature hash mismatch")
    if m["source_student_model_sha256"]!=source_sha:
        raise ValueError("value model based on another bottom selector")
    if m.get("T3_reward_is_exactly_zero") is not True:
        raise ValueError("v23 requires T2-only zero-T3-reward model")
    if m["deployed_policy_approved"] is not False:
        raise ValueError("cannot promote unreviewed value model")
    if dp["schema"]!="dack_v22_all_stage_london_continuation_dp":
        raise ValueError("wrong DP schema")
    if dp["model_sha256"]!=estimator.model_hash(m):
        raise ValueError("DP produced using DIFFERENT value forest")
    if dp["source_student_sha256"]!=source_sha:
        raise ValueError("DP for different bottom selection policy")
    if dp["source_manifest_sha256"]!=ref.source_sha(ref.MANIFEST_PATH):
        raise ValueError("DP for another deck manifest")
    if dp["model_approved"] is not False:
        raise ValueError("unapproved continuation model required")
    if len(dp["seat_continuations"])!=4:
        raise AssertionError("must compute all four position-specific continuations")
    MODEL=m;DP=dp
    MODEL_SHA=hashlib.sha256(a.read_bytes()).hexdigest()
    DP_SHA=hashlib.sha256(b.read_bytes()).hexdigest()
    ref.RULES_VERSION=POLICY+"_"+MODEL_SHA[:12]+"_"+DP_SHA[:12]
    ref.MULLIGAN_POLICY_NAME=POLICY
    ref.MULLIGAN_SAMPLER_NAME="real_keep_utility_vs_offline_DP_no_beam"
    ref.choose_keep=choose_keep
    return MODEL_SHA

def choose_keep(deck_slots,seat,orders):
    if MODEL is None or DP is None:raise RuntimeError("DP and model not installed")
    if deck_slots!=ref.SLOT_VARIANTS["one_key_34"]:
        raise ValueError("v23 only validated for control physical 99")
    thresholds=DP["seat_continuations"][str(seat)]["thresholds_by_london_stage"]
    hist=[]
    for stage,(kn,order) in enumerate(zip(ref.sim.STAGES,orders)):
        seven=tuple(deck_slots[s] for s in order[:7])
        unknown=tuple(deck_slots[s] for s in order[7:])
        pool=Counter(unknown)
        candidates=[]
        for idx,c in enumerate(finalists(seven,kn,unknown)):
            x=f.extract(seven,c["hand"],c["bottom"],pool,seat,kn,
                        stage,c["struct_rank"],idx)
            vote=f.score_head(old.MODEL,"choice_trees",x)
            candidates.append((vote,-idx,c,x))
        score,minus_idx,choice,x=max(candidates,key=lambda t:(t[0],t[1]))
        estimate=estimator.predict(MODEL,x)
        next_value=float(thresholds[stage])
        keep=(kn==1 or estimate>=next_value)
        old_keep_vote=f.score_head(old.MODEL,"keep_trees",x)
        STATS["stages"]+=1
        STATS["kept" if keep else "mulliganed"]+=1
        STATS["keep_differs_from_original_classifier"]+=int(
            keep!=(kn==1 or old_keep_vote>=old.MODEL["keep_cutoff"]))
        hand=tuple(choice["hand"]);bottom=tuple(choice["bottom"])
        hist.append({
            "stage":stage,"keep_n":kn,"kept":keep,
            "raw":round(estimate,7),"threshold":round(next_value,7),
            "refined":False,"sampled_t1":None,
            "value_model_sha256":MODEL_SHA,
            "continuation_dp_sha256":DP_SHA,
            "old_classifier_keep_vote":round(old_keep_vote,7),
            "candidate_index":-minus_idx,
            "candidate_count":len(candidates),
            "seven_slots":list(order[:7]),"seven":list(seven),
            "hand":list(hand),"bottom":list(bottom),
            "hand_slots":ref.selected_slots(order[:7],seven,hand),
            "bottom_slots":ref.selected_slots(order[:7],seven,bottom),
            "policy":POLICY,
        })
        if keep:
            if len(hand)!=kn or len(unknown)!=92:
                raise AssertionError("illegal London kept hand")
            return ref.d.State(1,hand,unknown+bottom),hist
    raise AssertionError("terminal London keep missing")

def audit():
    estimator.selftest()
    install()
    status=ref.audit()
    if status["status"]!="PASS" or status["mulligan_policy"]!=POLICY:
        raise AssertionError("ref rules audit failure")
    return dict(status,value_model_sha256=MODEL_SHA,
                continuation_sha256=DP_SHA,
                keep_decision="value_greater_than_expected_next_London_stage",
                unchanged_bottom_choice="frozen_v14_128",
                early_seven_free_mulligan_supported=True,
                gameplay_beam=160,mulligan_beam=0,
                model_approved_for_production=False)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--game",type=int,default=87000)
    a=p.parse_args()
    status=audit()
    if a.audit:
        print("V23_T2_ONLY_KEEP_LONDON_DP_AUDIT_PASS",json.dumps(status),flush=True)
    else:
        if not 88000<=a.game<87000:
            raise ValueError("v23 only unseen 86k full-game physical IDs")
        r=ref.game("one_key_34",a.game)
        print("V23_REAL_KEEP_GAME",json.dumps(r),flush=True)
        print("V23_POLICY_STATS",json.dumps(dict(STATS)),flush=True)
