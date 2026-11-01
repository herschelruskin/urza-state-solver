"""EXPERIMENTAL v19 London: value-rank top3, old v14-128 keep head.

All bottoming choices must be generated from the opening seven's visible
physical slots. The real v5 teacher index is NEVER known to this policy.
The v18 regressor is trained solely on real paired U for k 3..6, so for
k in (1,2,7) we use the original v14-128 imitation choice head.

V14-128 keep/reject head is unchanged. This is an isolated causal test
of replacing bottom-choice imitation with real estimated deployment utility,
not a final value-driven London continuation policy.
"""
from __future__ import annotations
from collections import Counter
import hashlib,json
from pathlib import Path
import dack_mulligan_teacher_features_v13_20261031 as features
import dack_mulligan_candidate_value_v18_20261101 as utility
from dack_simulator.validation.collect_teacher_london_v13 import finalists
import dack_paired_counterfactual_v13_teacher_distill_20261031 as original

ref=original.ref
STATS=Counter()
CHOICE_MODEL_PATH="models/dack_v18_paired_candidate_utility_EXPERIMENTAL.json"
KEEP_MODEL_PATH="models/v14_curve/v14_teacher_groups_128.json"
VALUE_MODEL=None
VALUE_SHA=None
KEEP_SHA=None
POLICY="dack_experimental_v19_paired_real_candidate_values"

def install(choice_path=CHOICE_MODEL_PATH,keep_path=KEEP_MODEL_PATH):
    global VALUE_MODEL,VALUE_SHA,KEEP_SHA
    KEEP_SHA=original.install(keep_path)
    value=Path(choice_path)
    model=json.loads(value.read_text())
    if model.get("schema")!=utility.SCHEMA:
        raise ValueError("bad value-model schema")
    if model.get("feature_hash")!=features.feature_hash():
        raise ValueError("model cannot use expected feature set")
    if model.get("selection_uses_structural_first_three_only") is not True:
        raise ValueError("model may rely on teacher-only candidate index")
    if model.get("deployed_policy_approved") is not False:
        raise ValueError("not a research-only model")
    if model.get("training_groups",0)<40:
        raise ValueError("value model lacks physical training groups")
    VALUE_MODEL=model
    VALUE_SHA=hashlib.sha256(value.read_bytes()).hexdigest()
    ref.RULES_VERSION=POLICY+"_"+KEEP_SHA[:12]+"_"+VALUE_SHA[:12]
    ref.MULLIGAN_POLICY_NAME=POLICY
    ref.MULLIGAN_SAMPLER_NAME="no_beam_real_pair_utility_student_v18"
    ref.choose_keep=choose_keep
    return VALUE_SHA

def choose_keep(deck_slots,seat,order_by_stage):
    if VALUE_MODEL is None or original.MODEL is None:
        raise RuntimeError("models not installed")
    if deck_slots!=ref.SLOT_VARIANTS["one_key_34"]:
        raise ValueError("research model only validated for one_key_34")
    history=[]
    for stage,(kn,order) in enumerate(zip(ref.sim.STAGES,order_by_stage)):
        seven=tuple(deck_slots[j] for j in order[:7])
        unknown=tuple(deck_slots[j] for j in order[7:])
        pool=Counter(unknown)
        candidate_rows=finalists(seven,kn,unknown)
        options=[]
        for idx,c in enumerate(candidate_rows):
            if 3<=kn<=6 and idx>=3:continue
            x=features.extract(seven,c["hand"],c["bottom"],pool,
                seat,kn,stage,c["struct_rank"],idx)
            if 3<=kn<=6:
                vote=utility.predict(VALUE_MODEL,x)
                score_type="actual_utility_forest"
            else:
                vote=features.score_head(original.MODEL,"choice_trees",x)
                score_type="v14_128_imitation_uncovered_stage"
            options.append((vote,-idx,c,x,idx))
        vote,negative_idx,selected,x,idx=max(options,key=lambda z:(z[0],z[1]))
        keep_vote=features.score_head(original.MODEL,"keep_trees",x)
        keep=(kn==1 or keep_vote>=original.MODEL["keep_cutoff"])
        hand=tuple(selected["hand"]);bottom=tuple(selected["bottom"])
        STATS["stages"]+=1
        STATS["value_stages" if 3<=kn<=6 else "baseline_stages"]+=1
        STATS["keeps" if keep else "mulligans"]+=1
        STATS["value_selected_structural_first" if idx==0 else "value_selected_other"]+=int(3<=kn<=6)
        history.append({
            "stage":stage,"keep_n":kn,"kept":bool(keep),
            "raw":round(keep_vote,7),"sampled_t1":None,
            "threshold":original.MODEL["keep_cutoff"],"refined":False,
            "seven_slots":list(order[:7]),"seven":list(seven),
            "hand":list(hand),"bottom":list(bottom),
            "hand_slots":ref.selected_slots(order[:7],seven,hand),
            "bottom_slots":ref.selected_slots(order[:7],seven,bottom),
            "candidate_index":idx,"candidate_count":len(candidate_rows),
            "selected_score":round(vote,7),
            "selection_head":score_type,"keep_vote":round(keep_vote,7),
            "policy":POLICY,
            "value_model_sha256":VALUE_SHA,
            "keep_model_sha256":KEEP_SHA
        })
        if keep:
            if len(hand)!=kn or len(unknown)!=92:
                raise AssertionError("illegal physical London kept state")
            return ref.d.State(1,hand,unknown+bottom),history
    raise AssertionError("failed terminal London keep")

def audit():
    utility.selftest()
    install()
    report=ref.audit()
    if report["status"]!="PASS" or report["mulligan_policy"]!=POLICY:
        raise AssertionError("incorrect gameplay audit")
    return dict(report,choice_model_sha256=VALUE_SHA,
        keep_model_sha256=KEEP_SHA,
        learned_candidate_limit=3,
        candidate_value_covered_keep_n=[3,4,5,6],
        model_approved_for_production=False,
        mulligan_beam=0,gameplay_beam=160)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--game",type=int,default=72000)
    a=p.parse_args()
    report=audit()
    if a.audit:
        print("V19_REAL_VALUE_POLICY_AUDIT_PASS",json.dumps(report),flush=True)
    else:
        if not 72000<=a.game<73000:
            raise ValueError("V19 only fresh 72k independent full-game research IDs")
        outcome=ref.game("one_key_34",a.game)
        print("V19_REAL_VALUE_GAME",json.dumps(outcome),flush=True)
        print("V19_REAL_VALUE_STATS",json.dumps(dict(STATS)),flush=True)
