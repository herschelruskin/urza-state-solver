#!/usr/bin/env python3
"""Distill EXACT installed v5 London keep/bottom decisions; no game-label proxy.

The teacher is the unchanged v5 bounded/witness London evaluator, including
stable dice and assertive thresholds. One row per VISITED stage of a naturally
shuffled 99-slot seven; candidate rows reproduce the original structural
top-12 bottom policy and stable ties. Candidate labels identify the *actual*
teacher bottom, not a manually chosen heuristic. No future library order
enters features. Do not turn labels into claimed win probabilities.

Game ID bands 60000-60999=train; 61000-61999=validation; 62000-62999=
held-out imitation test; 63000+ entirely independent full-game policy test.
The earlier 41k/42k/43k policy outcomes never enter these labels.
"""
from __future__ import annotations
import argparse
from collections import Counter
from itertools import combinations
import gzip,json,hashlib,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import dack_paired_counterfactual_v5_stable_chance_20261031 as teacher

ref=teacher.reference
d=ref.d
SCHEMA="dack_v13_v5_london_teacher_stages_v1"
SPLITS={"train":(60000,60999),"validation":(61000,61999),
        "imitation_test":(62000,62999)}
POLICY="dack_stable_dice_strict_bounded_witness_v5"

def finalists(seven,keep_n,unknown,limit=12):
    rows=[]
    for inds in ([()] if keep_n==7 else combinations(range(7),7-keep_n)):
        used=set(inds)
        hand=d.sort_hand([card for i,card in enumerate(seven) if i not in used])
        bottom=tuple(seven[i] for i in sorted(used))
        structural=sum(d.bottom_priority(seven[i],seven) for i in used)
        contam=sum(card in d.COMBO_CREATURES for card in hand)
        aura=sum(card in d.AURAS for card in hand)
        rows.append({
            "struct_rank":[structural,-contam,-aura],
            "hand":list(hand),"bottom":list(bottom),
            "bottom_indices":list(inds),
        })
    rows.sort(key=lambda r:tuple(r["struct_rank"]),reverse=True)
    return rows[:min(int(limit),len(rows))]

def generate(start,games,out,split="train",variant="one_key_34"):
    if split not in SPLITS or variant not in ref.VARIANTS:raise ValueError("invalid split/arm")
    lo,hi=SPLITS[split]
    if games<1 or start<lo or start+games-1>hi:
        raise ValueError("teacher game IDs outside disjoint split")
    teacher.audit()
    t0=time.monotonic()
    path=Path(out);path.parent.mkdir(parents=True,exist_ok=True)
    counts=Counter()
    with gzip.open(path,"wt",encoding="utf8") as f:
        meta={
            "type":"metadata","schema":SCHEMA,"split":split,
            "start":start,"games":games,"variant":variant,
            "teacher":POLICY,
            "seed_base":int(ref.SPEC["seed_base"]),
            "seed_stride":ref.SEED_STRIDE,
            "sampling":"original_real_physical_slots_each_London_stage",
            "teacher_only_visits_reached_before_keep":True,
            "structural_top_finalists":12,
            "teacher_future_samples":"original 8 or threshold-refined 16",
            "teacher_effective_beam":"original fixed v5 mulligan model",
            "source_manifest_sha256":ref.source_sha(ref.MANIFEST_PATH),
            "source_spec_sha256":ref.source_sha(ref.SPEC_PATH),
            "no_realized_future_library_order_in_training_records":True,
            "disjoint_grouping":"outer game ID across all stages and choices",
            "model_target":"teacher candidate selected and teacher stage keep",
        }
        f.write(json.dumps(meta,separators=(",",":"))+"\n")
        for gid in range(start,start+games):
            seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
            seat,orders=ref.stage_slots(seed)
            deck=ref.SLOT_VARIANTS[variant]
            ref.sim.reset_caches()
            ref.sim.root.install(variant)
            ref.sim.m.set_trial_seed(seed)
            state,history=ref.choose_keep(deck,seat,orders)
            assert history and history[-1]["kept"]
            for stage_info in history:
                stage=int(stage_info["stage"]);keep_n=int(stage_info["keep_n"])
                order=orders[stage]
                seven=[deck[s] for s in order[:7]]
                unknown=[deck[s] for s in order[7:]]
                choices=finalists(seven,keep_n,unknown)
                selected=tuple(stage_info["hand"]),tuple(stage_info["bottom"])
                matches=[i for i,row in enumerate(choices)
                         if (tuple(row["hand"]),tuple(row["bottom"]))==selected]
                if not matches:
                    raise AssertionError(("teacher winner absent from structural finalists",
                                          gid,stage,selected))
                chosen=matches[0]
                # Reconstruct all candidate feature-visible states, no information
                # about the shuffled unknown future order. Teacher-choice labels
                # are derived from the installed ORIGINAL teacher only.
                record={
                    "type":"stage","game_id":gid,"group_id":f"{variant}:{gid}",
                    "variant":variant,"stage":stage,"seat":seat,"keep_n":keep_n,
                    "seven":list(seven),
                    "unknown_counts":dict(sorted(Counter(unknown).items())),
                    "candidate_rows":choices,
                    "teacher_chosen_candidate":chosen,
                    "teacher_keep":bool(stage_info["kept"]),
                    "teacher_raw":float(stage_info["raw"]),
                    "teacher_sampled_t1":float(stage_info["sampled_t1"]),
                    "teacher_threshold":float(stage_info["threshold"]),
                    "teacher_refined":bool(stage_info["refined"]),
                    "teacher_selected_hand":list(stage_info["hand"]),
                    "teacher_selected_bottom":list(stage_info["bottom"]),
                }
                assert len(seven)==7 and len(unknown)==92
                assert Counter(seven)+Counter(unknown)==Counter(ref.VARIANTS[variant])
                assert sum(record["unknown_counts"].values())==92
                assert all("library" not in k.lower() and "first3" not in k
                           for k in record)
                f.write(json.dumps(record,separators=(",",":"))+"\n")
                counts["stage_rows"]+=1
                counts["candidate_rows"]+=len(choices)
                counts["teacher_keeps"]+=int(stage_info["kept"])
                counts["teacher_rejects"]+=int(not stage_info["kept"])
                counts["candidate_count_"+str(len(choices))]+=1
            counts["games"]+=1
            print("DISTILL_TEACHER_GAME",gid,len(history),
                  round(time.monotonic()-t0,3),flush=True)
    print("DISTILL_TEACHER_SHARD_PASS",json.dumps({
        "schema":SCHEMA,"split":split,"start":start,"games":games,
        "counts":dict(counts),"seconds":round(time.monotonic()-t0,3)
    },sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--split",choices=tuple(SPLITS),default="train")
    p.add_argument("--start",type=int,default=60000)
    p.add_argument("--games",type=int,default=2)
    p.add_argument("--variant",choices=list(ref.VARIANTS),default="one_key_34")
    p.add_argument("--out",default="datasets/distill_teacher_60000.jsonl.gz")
    a=p.parse_args()
    generate(a.start,a.games,a.out,a.split,a.variant)
