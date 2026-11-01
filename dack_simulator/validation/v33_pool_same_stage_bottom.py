#!/usr/bin/env python3
"""Pool all eight v33 conditional bottom replays; resample physical groups.

All 56 disagreements are selected ONLY on keep-stage agreement and different
kept cards, not the realized outcome. Original cohort is NOT prospective.
Independent fresh 92-card physical shuffles and blind dice in each split.
No policy training or post-selection tuning of two-arm contrast.
"""
from __future__ import annotations
import argparse
import gzip
import glob
import json
import random
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCHEMA="dack_v33_same_stage_bottom_fresh_futures"
SPLITS=("calibration","untouched_validation")


def score(groups,split,t):
    data=[]
    for g in groups:
        pairs=(g["splits"][split] if split else
               g["splits"]["calibration"]+g["splits"]["untouched_validation"])
        diffs=[int(0<x["v5"]<=t)-int(0<x["v27_frozen"]<=t) for x in pairs]
        data.append(sum(diffs)/len(diffs))
    avg=sum(data)/len(data)
    rng=random.Random(330011+t+(len(split) if split else 1000))
    boots=sorted(sum(data[rng.randrange(len(data))] for _ in data)/len(data)
                 for _ in range(10000))
    return {
      "n_independent_selected_physical_groups":len(groups),
      "fresh_futures_per_arm_per_group":len(groups[0]["splits"]["calibration"])*
                 (2 if split is None else 1),
      "mean_difference_probability":avg,
      "difference_percentage_points":100*avg,
      "paired_group_bootstrap_95ci_pp":[100*boots[249],100*boots[9749]],
      "positive_group_estimates":sum(v>0 for v in data),
      "negative_group_estimates":sum(v<0 for v in data),
      "zero_group_estimates":sum(v==0 for v in data),
    }


def main(source,out):
    files=sorted(glob.glob(source))
    if len(files)!=8:
        raise ValueError("v33 replay requires exactly 8 independent blocks, found "+str(len(files)))
    rows=[]; source_sha=None
    for file in files:
        with gzip.open(file,"rt") as f:
            d=json.load(f)
        assert d["schema"]==SCHEMA and d["status"]=="PASS"
        assert d["actual_beam"]==160 and d["futures_per_split"]==8
        assert d["same_unknown_shuffle_and_dice_seed_between_arms"]
        assert d["independent_split_futures"] and d["mulligan_policy_not_run"]
        assert d["selection_uses_original_win_turn"] is False
        assert d["no_engine_or_model_changes"] and not d["policy_approved"]
        assert d["block"] in range(8)
        if source_sha is None:
            source_sha=d["source_shas"]
        assert d["source_shas"]==source_sha
        assert len(d["rows"])==7
        rows+=d["rows"]
    rows.sort(key=lambda g:g["game_id"])
    assert len(rows)==56 and len({g["game_id"] for g in rows})==56
    for g in rows:
        assert g["stage"] in range(1,8) or g["stage"]==0
        for split in SPLITS:
            a=g["splits"][split]
            assert len(a)==8 and all(all(x[k] in (0,1,2,3)
                for k in ("v5","v27_frozen")) for x in a)
    by={}
    for split in (*SPLITS,"both_splits_pooled_no_fitting"):
        selector=None if split.startswith("both") else split
        by[split]={f"T{t}":score(rows,selector,t) for t in (1,2,3)}
    result={
        "schema":"dack_v33_bottom_replay_N56_x16_results",
        "status":"PASS","source_full_game_select_cohort":[110000,110255],
        "source_model_shas":source_sha,
        "n_selected_physical_groups":56,
        "total_new_gameplay_beam160_evaluations":56*2*8*2,
        "evaluation":"conditional same-stage actual v5/v27 bottom choices, physical future shuffles",
        "no_110k_game_outcomes_used_to_select_groups":True,
        "not_prospective_end_to_end_policy_performance":True,
        "no_candidate_training_or_model_promotion":True,
        "paired_group_CI_not_1792_independent_group_CI":True,
        "chance_coupling_limitations":"Common unknown order and stable dice seeds do not guarantee identical event-level chance draws across different action paths.",
        "by_split":by,
        "selection_by_stage":{str(s):sum(g["stage"]==s for g in rows) for s in range(8)},
        "policy_approved":False
    }
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("DACK_V33_BOTTOM_REPLAY_POOL_PASS",
          json.dumps({"n":56,"T2_calibration":by["calibration"]["T2"],
            "T2_untouched_validation":by["untouched_validation"]["T2"],
            "T2_pooled":by["both_splits_pooled_no_fitting"]["T2"],
            "T3_pooled":by["both_splits_pooled_no_fitting"]["T3"]},
            sort_keys=True),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",default="collected/v33_bottom_*.json.gz")
    p.add_argument("--out",default="benchmark_results/v33_bottom_replay_N56_x16.json")
    a=p.parse_args()
    main(a.source,a.out)
