#!/usr/bin/env python3
"""Exact per-bottom factorization for expensive Phase-5I human hands.

Each task evaluates one legal London bottom on the exact original outer worlds:
- screen: sample 0 (1 rollout)
- confirmation: samples 1..3 (3 rollouts)

The reducer can therefore reconstruct the original shortlist and confirmation
ranking exactly. Evaluating confirmation for bottoms that would have been pruned
is extra diagnostic compute only and does not alter selection.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from phase5_mulligan import OpeningEnvironment, unique_bottom_subsets
from phase5i_human_hand_eval import (
    HORIZON,
    MC_ROOT_SEED,
    Q_MC_ROOT_SEED,
    estimate_json,
    load_deck,
)
from phase5i_mulligan import Phase5IOpeningKeepEvaluator


TASKS = (
    tuple((14, i) for i in range(35))
    + tuple((25, i) for i in range(7))
    + tuple((26, i) for i in range(35))
)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--task-id",type=int,required=True)
    args=p.parse_args()
    hand_id,bottom_index=TASKS[int(args.task_id)]

    fixture=json.loads(
        Path("benchmarks/human/human_mulligan_exact_hands.json").read_text(encoding="utf-8")
    )
    row=next(x for x in fixture["hands"] if int(x["hand_id"])==hand_id)
    seven=tuple(row["drawn_seven"])
    stage=int(row["mulligan_count"])
    legal=unique_bottom_subsets(seven,stage)
    if bottom_index>=len(legal):
        raise SystemExit((hand_id,stage,bottom_index,len(legal)))
    bottom=legal[bottom_index]

    evaluator=Phase5IOpeningKeepEvaluator(
        load_deck(),
        screen_rollouts=1,
        confirm_rollouts=3,
        shortlist_size=4,
        mc_root_seed=MC_ROOT_SEED,
        q_mc_root_seed=Q_MC_ROOT_SEED,
        horizon=HORIZON,
        opening_environment=OpeningEnvironment(seat=1,player_count=4),
    )
    screen=evaluator.screen_evaluator.evaluate(
        seven,stage=stage,candidate_bottoms=(bottom,),sample_start=0
    ).best
    confirm=evaluator.confirm_evaluator.evaluate(
        seven,stage=stage,candidate_bottoms=(bottom,),sample_start=1
    ).best

    payload={
        "kind":"phase5i-expensive-hand-bottom-factor",
        "task_id":int(args.task_id),
        "hand_id":hand_id,
        "stage":stage,
        "bottom_index":bottom_index,
        "legal_bottom_count":len(legal),
        "bottom":list(bottom),
        "screen":estimate_json(screen),
        "confirm":estimate_json(confirm),
        "q_cache":{"hits":evaluator.cache.stats.hits,"misses":evaluator.cache.stats.misses},
        "coordinates":{"screen_sample_ids":[0],"confirm_sample_ids":[1,2,3]},
    }
    out=Path(f"phase5i_expensive_hand_{hand_id}_bottom_{bottom_index:02d}.json")
    out.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print("PHASE5I_BOTTOM_FACTOR="+json.dumps({
        "hand_id":hand_id,"bottom_index":bottom_index,"bottom":list(bottom),
        "screen_key":screen.value.comparison_key(),
        "confirm_key":confirm.value.comparison_key(),
    },sort_keys=True))


if __name__=="__main__":
    main()
