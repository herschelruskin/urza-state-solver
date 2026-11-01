#!/usr/bin/env python3
"""V17 research-only paired candidate-value labels for v5 London bottoms.

Reuses *already collected* exact-v5 teacher-stage data. At one visited
stage with an actual choice of bottom cards, evaluate the structural
top-three AND the true v5-selected choice with identical unseen 92-card
physical library shuffles and identical stateless dice seeds. Different
candidate bottom orders remain at the bottom of the library.

No teacher is re-run; each candidate gets the same real future samples,
making paired utility differences much less noisy than independent rolls.
True labels are beam-160 goldfish deployment, not true multiplayer wins.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,time,sys,math
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import dack_paired_counterfactual_v5_stable_chance_20261031 as teacher
ref=teacher.reference
d=ref.d
PROTO="dack_v18_common_random_number_candidate_values"

def seed(*values):
    s=json.dumps([PROTO,*values],sort_keys=True,separators=(",",":"))
    return int.from_bytes(hashlib.sha256(s.encode()).digest()[:8],"big")

def read_teacher_file(path):
    with gzip.open(path,"rt",encoding="utf8") as fp:
        meta=json.loads(next(fp));rows=[json.loads(s) for s in fp]
    assert rows and meta["teacher"]=="dack_stable_dice_strict_bounded_witness_v5"
    assert meta["split"] in ("train","validation") and meta["variant"]=="one_key_34"
    assert meta["source_manifest_sha256"]==ref.source_sha(ref.MANIFEST_PATH)
    assert rows[-1]["teacher_keep"] and sum(x["teacher_keep"] for x in rows)==1
    return meta,rows

def evaluate_group(path,draws=8,first_k=3):
    if draws<2 or first_k<1:raise ValueError("need actual paired rollouts and candidates")
    meta,rows=read_teacher_file(path)
    gid=int(rows[0]["game_id"])
    # Latest visited stage offering real bottom alternatives. Do not select
    # a stage based on its eventual outcome, which would bias candidate labels.
    eligible=[r for r in rows if len(r["candidate_rows"])>1 and 3<=r["keep_n"]<=6]
    if not eligible:return None
    stage=eligible[-1]
    teacher_idx=int(stage["teacher_chosen_candidate"])
    chosen=sorted(set(range(min(first_k,len(stage["candidate_rows"]))))|{teacher_idx})
    unknown=stage["unknown_counts"]
    unknown_names=[card for card,n in sorted(unknown.items()) for _ in range(n)]
    assert len(unknown_names)==92
    seat=stage["seat"];variant=stage["variant"]
    future_orders=[]
    for j in range(draws):
        arr=list(unknown_names)
        random.Random(seed(gid,stage["stage"],j,"hidden_cards")).shuffle(arr)
        future_orders.append(tuple(arr))
    records=[];totals={}
    for idx in chosen:
        option=stage["candidate_rows"][idx]
        hand=tuple(option["hand"]);bottom=tuple(option["bottom"])
        assert Counter(hand)+Counter(bottom)==Counter(stage["seven"])
        assert Counter(hand)+Counter(bottom)+Counter(unknown)==Counter(ref.VARIANTS[variant])
        outcomes=[]
        for j,lib in enumerate(future_orders):
            ref.sim.reset_caches()
            ref.sim.root.install(variant)
            ref.sim.m.set_trial_seed(seed(gid,stage["stage"],j,"dice"))
            turn=int(d._win_turn_from_unknown_order(
                hand,lib+bottom,seat,beam=160,max_turn=3) or 0)
            assert turn in (0,1,2,3)
            outcomes.append(turn)
        cls=Counter(outcomes)
        # Exact goldfish utility from v8 objective; unsmoothed empirical
        # estimates for diagnostics only. Smooth/calibrate before ranking.
        u=(cls[1]+cls[2]+.5*cls[3])/draws
        totals[idx]=u
        records.append({
            "candidate_index":idx,"struct_rank":option["struct_rank"],
            "hand":option["hand"],"bottom":option["bottom"],
            "teacher_selected":idx==teacher_idx,
            "outcomes":outcomes,
            "counts":{str(k):cls[k] for k in range(4)},
            "empirical_P_T1":cls[1]/draws,
            "empirical_P_by_T2":(cls[1]+cls[2])/draws,
            "empirical_P_by_T3":(cls[1]+cls[2]+cls[3])/draws,
            "empirical_U":u,
        })
    teacher_u=totals[teacher_idx]
    empirical_best=max(totals,key=lambda k:(totals[k],-k))
    delta_to_first=teacher_u-totals[0]
    return {
        "type":"paired_candidate_group","protocol":PROTO,
        "source_teacher_game_id":gid,"stage":stage["stage"],
        "keep_n":stage["keep_n"],"seat":seat,"variant":variant,
        "seven":stage["seven"],"unknown_counts":unknown,
        "teacher_chosen_index":teacher_idx,
        "candidate_indices":chosen,"draws_per_candidate":draws,
        "future_order_shared_across_candidates":True,
        "stable_dice_seed_shared_across_candidates":True,
        "candidate_bottoms_appended_after_unknown_library":True,
        "hidden_future_order_never_saved":True,
        "outcomes_are_conditional_not_unconditional":True,
        "teacher_selected_empirical_u":teacher_u,
        "structural_first_empirical_u":totals[0],
        "teacher_minus_structural_first_u":delta_to_first,
        "empirical_best_index":empirical_best,
        "empirical_teacher_best_among_choices":teacher_idx==empirical_best,
        "candidates":records,
    }

def locate_teacher(gid,split):
    if split=="train":
        assert 60000<=gid<60144
        root=Path("datasets/teacher_v13_20261031") if gid<60016 else Path("datasets/teacher_v14_expansion")
        prefix="distill_v13_train_" if gid<60016 else "v14_train_"
    elif split=="validation":
        assert 61000<=gid<61040
        root=Path("datasets/teacher_v13_20261031") if gid<61008 else Path("datasets/teacher_v14_expansion")
        prefix="distill_v13_validation_" if gid<61008 else "v14_validation_"
    else:raise ValueError("invalid split; test 62k group sealed")
    source=root/(prefix+str(gid)+".jsonl.gz")
    if not source.exists():raise FileNotFoundError(source)
    return source

def generate(start,games,out,split="train",draws=8,first_k=3):
    if games<1 or draws<2 or first_k<1:
        raise ValueError("invalid sampling parameters")
    if split=="train":
        assert 60000<=start and start+games<=60144
    elif split=="validation":
        assert 61000<=start and start+games<=61040
    else:raise ValueError("only disjoint train and validation; tests sealed")
    teacher.audit()
    before=time.perf_counter();rows=[];skipped=[]
    for gid in range(start,start+games):
        source=locate_teacher(gid,split)
        item=evaluate_group(source,draws,first_k)
        if item is None:
            skipped.append(gid)
        else:
            item["source_teacher_split"]=split
            rows.append(item)
            print("V18_REAL_PAIR",gid,
                  {"stage":item["stage"],"keep":item["keep_n"],
                   "choices":len(item["candidates"]),
                   "u_teacher":item["teacher_selected_empirical_u"],
                   "u_structural":item["structural_first_empirical_u"]},flush=True)
    meta={
        "type":"metadata","schema":"dack_v18_paired_candidate_values",
        "status":"PASS","source":"archived_v5_beam_teacher_decisions",
        "split":split,"start":start,"requested_groups":games,
        "observed_groups":len(rows),"ineligible_game_ids":skipped,
        "candidate_limit_structural_first_plus_teacher":first_k,
        "paired_draws_per_option":draws,
        "no_future_order_in_features":True,
        "shared_physical_future_and_stateless_dice_by_group":True,
        "teacher_only_on_preselected_decision_states":True,
        "never_use_validation_for_training":True,
        "model_approved":False,
        "actual_gameplay_beam":160,
    }
    target=Path(out);target.parent.mkdir(exist_ok=True,parents=True)
    with gzip.open(target,"wt",encoding="utf8") as f:
        f.write(json.dumps(meta,separators=(",",":"))+"\n")
        for x in rows:f.write(json.dumps(x,separators=(",",":"))+"\n")
    print("V18_PAIRED_CANDIDATE_SHARD_PASS",json.dumps({
        "split":split,"start":start,"requested_groups":games,
        "observed_groups":len(rows),"skipped":len(skipped),
        "candidate_options":sum(len(x["candidates"]) for x in rows),
        "actual_beam160_rollouts":draws*sum(len(x["candidates"]) for x in rows),
        "seconds":round(time.perf_counter()-before,3)
    },sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--split",choices=("train","validation"),default="train")
    p.add_argument("--start",type=int,default=60000)
    p.add_argument("--games",type=int,default=8)
    p.add_argument("--draws",type=int,default=8)
    p.add_argument("--first-k",type=int,default=3)
    p.add_argument("--out",default="datasets/v18_paired_candidate_batch.jsonl.gz")
    a=p.parse_args()
    generate(a.start,a.games,a.out,a.split,a.draws,a.first_k)
