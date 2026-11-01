#!/usr/bin/env python3
"""V21 real beam160 counterfactual *keep* values at all London stages.

The frozen v14-128 bottoming student produces ONE candidate from every
physically independently shuffled 99-card London seven, including stages
that its current keep classifier would reject and stages it would not
reach in an actual game. Evaluating all 8 stage opportunities corrects
the v5-kept-only sample selection problem.

Each proposed kept hand gets independent unseen 92-card future shuffles.
Physical stage = 0..7 with keep_n=7,7,6,5,4,3,2,1. Bottoms remain at the
bottom in their original order, as in the strict simulator. Eight stages
share one seat; no future-order information enters model features.
Probabilities are goldfish deployment conditional on a proposed kept hand,
not the overall policy win probability. Never leak observed win label into
the keep/mull decision itself.
"""
from __future__ import annotations
import argparse,hashlib,gzip,json,random,time,sys
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import dack_paired_counterfactual_v13_teacher_distill_20261031 as student
from dack_simulator.validation.collect_teacher_london_v13 import finalists
import dack_mulligan_teacher_features_v13_20261031 as features

ref=student.ref
d=ref.d
MODEL="models/v14_curve/v14_teacher_groups_128.json"
SCHEMA="dack_v21_counterfactual_london_keep_values"
PROTO="DACK_V21_INDEPENDENT_PHYSICAL_STAGE_FUTURES"
SPLITS={"train":(82000,82999),"validation":(83000,83999),
        "test":(84000,84999)}

def stable_seed(*parts):
    data=json.dumps([PROTO,*parts],sort_keys=True,separators=(",",":"))
    return int.from_bytes(hashlib.sha256(data.encode()).digest()[:8],"big")

def sample_one(gid,draws,variant="one_key_34"):
    seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
    seat,orders=ref.stage_slots(seed)
    deck=ref.SLOT_VARIANTS[variant]
    rows=[]
    for stage,(keep_n,order) in enumerate(zip(ref.sim.STAGES,orders)):
        seven=tuple(deck[s] for s in order[:7])
        unknown=tuple(deck[s] for s in order[7:])
        unknown_counts=Counter(unknown)
        choices=finalists(seven,keep_n,unknown)
        scored=[]
        for idx,c in enumerate(choices):
            x=features.extract(seven,c["hand"],c["bottom"],
                unknown_counts,seat,keep_n,stage,c["struct_rank"],idx)
            p=features.score_head(student.MODEL,"choice_trees",x)
            scored.append((p,-idx,c,x))
        score,neg_index,chosen,x=max(scored,key=lambda t:(t[0],t[1]))
        accept_vote=features.score_head(student.MODEL,"keep_trees",x)
        student_accept=keep_n==1 or accept_vote>=student.MODEL["keep_cutoff"]
        hand=tuple(chosen["hand"]);bottom=tuple(chosen["bottom"])
        if Counter(hand)+Counter(bottom)!=Counter(seven):
            raise AssertionError("nonphysical London bottoming")
        if Counter(seven)+unknown_counts!=Counter(ref.VARIANTS[variant]):
            raise AssertionError("not exactly 99 legal physical card slots")
        for j in range(draws):
            order_names=list(unknown)
            random.Random(stable_seed(gid,stage,j,"hidden")).shuffle(order_names)
            ref.sim.reset_caches()
            ref.sim.root.install(variant)
            ref.sim.m.set_trial_seed(stable_seed(gid,stage,j,"dice"))
            turn=int(d._win_turn_from_unknown_order(
                hand,tuple(order_names)+bottom,seat,beam=160,max_turn=3) or 0)
            if turn not in (0,1,2,3):
                raise AssertionError("bad Dack deployment class")
            rows.append({
                "type":"label","schema":SCHEMA,"group_id":f"{variant}:{gid}",
                "game_id":gid,"seat":seat,"stage":stage,"keep_n":keep_n,
                "seven":list(seven),"hand":list(hand),"bottom":list(bottom),
                "unknown_counts":dict(sorted(unknown_counts.items())),
                "candidate_index":-neg_index,"candidate_count":len(choices),
                "candidate_struct_rank":chosen["struct_rank"],
                "student_choice_vote":float(score),
                "student_keep_vote":float(accept_vote),
                "student_would_keep":bool(student_accept),
                "future_index":j,"label_turn":turn,
            })
    if len(rows)!=draws*8:
        raise AssertionError("must evaluate all eight London stages")
    return rows

def generate(start,games,out,split="train",draws=4):
    if split not in SPLITS:raise ValueError("invalid split")
    lo,hi=SPLITS[split]
    if games<1 or draws<1 or not lo<=start<=start+games-1<=hi:
        raise ValueError("independent split game IDs required")
    report=student.audit(MODEL)
    assert report["status"]=="PASS"
    assert student.MODEL["deployed_policy_approved"] is False
    model_sha=hashlib.sha256(Path(MODEL).read_bytes()).hexdigest()
    target=Path(out);target.parent.mkdir(exist_ok=True,parents=True)
    count=Counter();t0=time.monotonic()
    meta={
        "type":"metadata","schema":SCHEMA,
        "sampling_protocol":PROTO,"split":split,
        "first_game":start,"games":games,"draws_per_stage":draws,
        "all_eight_stages_each_physical_game":True,
        "per_stage_seven_physical_shuffle_is_independent":True,
        "stage_keep_numbers":[7,7,6,5,4,3,2,1],
        "source_student_model_sha256":model_sha,
        "source_manifest_sha256":ref.source_sha(ref.MANIFEST_PATH),
        "actual_beam":160,
        "new_unseen_library_order_never_saved":True,
        "source_student_training_never_contains_82k_83k_84k":True,
        "not_unconditional_deck_win_probability":True,
        "future_orders_independent_per_stage_and_rollout":True,
        "source_student_may_reject_or_never_reach_stage":True,
        "model_approved":False,
    }
    with gzip.open(target,"wt",encoding="utf8") as fp:
        fp.write(json.dumps(meta,separators=(",",":"))+"\n")
        for gid in range(start,start+games):
            rows=sample_one(gid,draws)
            for x in rows:
                fp.write(json.dumps(x,separators=(",",":"))+"\n")
                count["rollouts"]+=1
                count["T"+str(x["label_turn"])]+=1
                if x["future_index"]==0:
                    count["stage_rows"]+=1
                    count["would_keep"]+=int(x["student_would_keep"])
                    count["would_reject"]+=int(not x["student_would_keep"])
            count["game_groups"]+=1
            print("V21_REAL_COUNTERFACTUAL_KEEP_GAME",gid,dict(count),
                  round(time.monotonic()-t0,2),flush=True)
    print("V21_ALL_LONDON_STAGES_REAL_LABEL_PASS",json.dumps({
        "split":split,"first_game":start,"groups":games,
        "counts":dict(count),"seconds":round(time.monotonic()-t0,3),
    },sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--split",choices=tuple(SPLITS),default="train")
    p.add_argument("--start",type=int,default=82000)
    p.add_argument("--games",type=int,default=2)
    p.add_argument("--draws",type=int,default=4)
    p.add_argument("--out",default="datasets/v21_all_stage_keep_values.jsonl.gz")
    a=p.parse_args()
    generate(a.start,a.games,a.out,a.split,a.draws)
