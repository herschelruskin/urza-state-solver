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
PROTO="dack_v17_common_random_number_candidate_values"

def seed(*values):
    s=json.dumps([PROTO,*values],sort_keys=True,separators=(",",":"))
    return int.from_bytes(hashlib.sha256(s.encode()).digest()[:8],"big")

def read_teacher_file(path):
    with gzip.open(path,"rt",encoding="utf8") as fp:
        meta=json.loads(next(fp));rows=[json.loads(s) for s in fp]
    assert rows and meta["teacher"]=="dack_stable_dice_strict_bounded_witness_v5"
    assert meta["split"]=="train" and meta["variant"]=="one_key_34"
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

def generate(root,start,games,out,draws=8,first_k=3):
    if not (60000<=start and start+games<=60144) or games<1:
        raise ValueError("pilot uses archived training groups only, never 61k validation or heldout tests")
    teacher.audit()
    before=time.perf_counter()
    output=[];skipped=[]
    root=Path(root)
    for gid in range(start,start+games):
        source=(root/f"distill_v13_train_{gid}.jsonl.gz" if gid<60016 else
                root/f"v14_train_{gid}.jsonl.gz")
        # Support two separate already-archived teacher training folders.
        if not source.exists():
            folder=("datasets/teacher_v13_20261031" if gid<60016 else
                    "datasets/teacher_v14_expansion")
            source=Path(folder)/source.name
        if not source.exists():raise FileNotFoundError(source)
        row=evaluate_group(source,draws,first_k)
        if row is None:
            skipped.append(gid)
        else:
            output.append(row)
            print("V17_REAL_CANDIDATE_PAIRED_GROUP",gid,
                  {"keep_n":row["keep_n"],
                   "candidate_count":len(row["candidates"]),
                   "teacher_u":row["teacher_selected_empirical_u"],
                   "structural_first_u":row["structural_first_empirical_u"]},
                  flush=True)
    if not output:raise RuntimeError("no eligible bottom-choice groups")
    meta={
        "schema":"dack_v17_paired_candidate_value_pilot",
        "status":"PASS","source":"previously_archived_exact_v5_teacher_training",
        "start":start,"requested_games":games,
        "observed_groups":len(output),"ineligible_game_ids":skipped,
        "paired_draws_per_option":draws,
        "candidate_limit_structural_first_plus_teacher":first_k,
        "model_data_only":True,
        "mulligan_teacher_search_not_repeated":True,
        "gameplay_beam":160,"no_hidden_order_in_export":True
    }
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(dest,"wt",encoding="utf8") as fp:
        fp.write(json.dumps({"type":"metadata",**meta},separators=(",",":"))+"\n")
        for r in output:fp.write(json.dumps(r,separators=(",",":"))+"\n")
    print("V17_PAIRED_CANDIDATE_PILOT_PASS",json.dumps({
        "sampled_groups":len(output),
        "sampled_options":sum(len(r["candidates"]) for r in output),
        "actual_beam160_rollouts":sum(len(r["candidates"])*draws for r in output),
        "teacher_empirically_better_than_first":sum(r["teacher_minus_structural_first_u"]>0 for r in output),
        "teacher_empirically_worse_than_first":sum(r["teacher_minus_structural_first_u"]<0 for r in output),
        "seconds":round(time.perf_counter()-before,3),
    },sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--root",default="datasets/teacher_v13_20261031")
    p.add_argument("--start",type=int,default=60000)
    p.add_argument("--games",type=int,default=8)
    p.add_argument("--draws",type=int,default=8)
    p.add_argument("--first-k",type=int,default=3)
    p.add_argument("--out",default="datasets/v17_paired_candidate_pilot.jsonl.gz")
    a=p.parse_args()
    generate(a.root,a.start,a.games,a.out,a.draws,a.first_k)
