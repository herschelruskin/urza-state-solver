#!/usr/bin/env python3
"""Offline London dynamic programming from REAL-OUTCOME v22 predicted hand utility.

For each seat, draw hundreds of independent physical-99 London stage sevens,
choose the same frozen v14-128 bottom candidate policy as v22 deployment,
then use the new v22 predicted keep utility at each of all eight London
stages. No beam rollouts or game outcome peeking during DP/inference.

Backward stage recursion:
C_1=E[U_1]
C_k=E[max(U_k,C_(k-1))] for k=2..7
Initial free London seven compares to C_7; second seven to C_6.
This recursion is approximate because value model's conditional predictions
may be miscalibrated; evidence comes only from fresh full-game benchmarks.
"""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
from collections import Counter,defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import dack_paired_counterfactual_v13_teacher_distill_20261031 as student
import dack_mulligan_teacher_features_v13_20261031 as features
import dack_mulligan_keep_value_v22_20261101 as values
from dack_simulator.validation.collect_teacher_london_v13 import finalists

ref=student.ref
SCHEMA="dack_v22_all_stage_london_continuation_dp"

def choose_current(seven,unknown,seat,kn,stage):
    pool=Counter(unknown)
    scored=[]
    for idx,c in enumerate(finalists(seven,kn,unknown)):
        x=features.extract(seven,c["hand"],c["bottom"],pool,
                            seat,kn,stage,c["struct_rank"],idx)
        prob=features.score_head(student.MODEL,"choice_trees",x)
        scored.append((prob,-idx,x,c))
    _,neg_idx,x,c=max(scored,key=lambda a:(a[0],a[1]))
    return x,c

def derive(modelpath,out,start=92000,games=512):
    if start<92000 or games<128 or start+games>93000:
        raise ValueError("DP needs independent physical 92k stage sevens")
    report=student.audit("models/v14_curve/v14_teacher_groups_128.json")
    assert report["status"]=="PASS"
    model=json.loads(Path(modelpath).read_text())
    if model.get("T3_reward_is_exactly_zero") is not True:
        raise ValueError("v23 requires T2-only direct utility, not v22 T3-weighted utility")
    if model["deployed_policy_approved"] is not False:
        raise AssertionError("v23 model unapproved")
    sha=hashlib.sha256(Path("models/v14_curve/v14_teacher_groups_128.json").read_bytes()).hexdigest()
    if model["source_student_model_sha256"]!=sha:
        raise ValueError("DP uses a different bottom-choice student than v22 trained on")
    seat_values=defaultdict(lambda:defaultdict(list))
    deck=ref.SLOT_VARIANTS["one_key_34"]
    for gid in range(start,start+games):
        seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,stages=ref.stage_slots(seed)
        for stage,(kn,order) in enumerate(zip(ref.sim.STAGES,stages)):
            seven=tuple(deck[s] for s in order[:7])
            unknown=tuple(deck[s] for s in order[7:])
            x,c=choose_current(seven,unknown,seat,kn,stage)
            u=values.predict(model,x)
            seat_values[str(seat)][stage].append(u)
        if (gid-start+1)%128==0:
            print("V23_T2_DP_PHYSICAL_STAGES_SAMPLED",gid-start+1,flush=True)
    table={}
    for seat,staged in sorted(seat_values.items()):
        ns=[len(staged[i]) for i in range(8)]
        if len(set(ns))!=1 or min(ns)<32:
            raise AssertionError("not enough each-stage independent physical samples for seat")
        cont={}
        c1=sum(staged[7])/len(staged[7])
        cont["1"]=c1
        for kn in range(2,8):
            stage=8-kn
            current=staged[stage]
            c1=sum(max(u,c1) for u in current)/len(current)
            cont[str(kn)]=c1
        thresholds=[cont["7"],cont["6"],cont["5"],cont["4"],
                    cont["3"],cont["2"],cont["1"],-1.]
        if not all(0<=x<=1 for x in thresholds[:7]):
            raise AssertionError("invalid continuation")
        table[seat]={
            "samples_per_stage":ns[0],
            "expected_value_if_keep_this_stage":{
                str(stage):sum(staged[stage])/len(staged[stage]) for stage in range(8)},
            "continuation_by_keep_n":cont,
            "thresholds_by_london_stage":thresholds
        }
    output={
        "schema":SCHEMA,
        "model_sha256":values.model_hash(model),
        "source_student_sha256":sha,
        "source_manifest_sha256":ref.source_sha(ref.MANIFEST_PATH),
        "physical_group_ids":[start,start+games-1],
        "independent_physical_stage_samples":games,
        "mulligan_beam_calls":0,
        "free_first_seven_compares_against_second_seven_value":True,
        "trained_on_rejected_as_well_as_accepted_london_hands":True,
        "seat_continuations":table,
        "model_approved":False,
        "utility_definition":"P(deploy_by_T2),T3_reward=0",
        "warning":"DP values are learned estimates not exact future game probabilities. Benchmarked only by independent full-game reference comparisons."
    }
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(output,sort_keys=True,indent=2)+"\n")
    print("V23_T2_ONLY_DP_REAL_VALUE_PASS",json.dumps({
        "n_seats":len(table),
        "samples":games,
        "seat_0":table.get("0",{}).get("thresholds_by_london_stage"),
        "model_approved":False},sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--model",default="models/dack_v23_T2_only_real_keep_value_EXPERIMENTAL.json")
    p.add_argument("--out",default="models/dack_v23_T2_only_continuations_EXPERIMENTAL.json")
    p.add_argument("--start",type=int,default=92000)
    p.add_argument("--games",type=int,default=512)
    a=p.parse_args()
    derive(a.model,a.out,a.start,a.games)
