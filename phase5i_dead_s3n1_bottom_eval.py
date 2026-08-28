#!/usr/bin/env python3
"""Exact per-bottom factorization of dead-context stage-3 sample 1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from phase5_mulligan import OpeningEnvironment, _sample_fresh_seven, unique_bottom_subsets
from phase5i_human_hand_eval import estimate_json
from phase5i_mulligan import Phase5IOpeningKeepEvaluator
from phase5i_stage_sample_eval import (
    BASE_SEED,
    BOTTOM_SHORTLIST,
    HORIZON,
    OUTER_CONFIRM,
    OUTER_SCREEN,
    Q_SEED_OFFSET,
    load_deck,
)

CONTEXT="dead"
SEAT=1
STAGE=3
SAMPLE_ID=1


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--bottom-index",type=int,required=True)
    args=p.parse_args()
    seed=BASE_SEED + STAGE*10_007 + SAMPLE_ID*100_003
    q_seed=seed+Q_SEED_OFFSET
    deck=load_deck()
    seven=_sample_fresh_seven(deck,root_seed=seed,stage=STAGE,sample_id=SAMPLE_ID)
    legal=unique_bottom_subsets(seven,STAGE)
    bottom=legal[int(args.bottom_index)]
    evaluator=Phase5IOpeningKeepEvaluator(
        deck,
        screen_rollouts=OUTER_SCREEN,
        confirm_rollouts=OUTER_CONFIRM,
        shortlist_size=BOTTOM_SHORTLIST,
        mc_root_seed=seed,
        q_mc_root_seed=q_seed,
        horizon=HORIZON,
        opening_environment=OpeningEnvironment(seat=SEAT,player_count=4),
    )
    screen=evaluator.screen_evaluator.evaluate(
        seven,stage=STAGE,candidate_bottoms=(bottom,),sample_start=0
    ).best
    confirm=evaluator.confirm_evaluator.evaluate(
        seven,stage=STAGE,candidate_bottoms=(bottom,),sample_start=1
    ).best
    payload={
        "kind":"phase5i-dead-s3n1-bottom-factor",
        "bottom_index":int(args.bottom_index),
        "legal_bottom_count":len(legal),
        "bottom":list(bottom),
        "seven":list(seven),
        "mc_root_seed":seed,
        "q_mc_root_seed":q_seed,
        "screen":estimate_json(screen),
        "confirm":estimate_json(confirm),
        "q_cache":{"hits":evaluator.cache.stats.hits,"misses":evaluator.cache.stats.misses},
    }
    Path(f"phase5i_dead_s3n1_bottom_{int(args.bottom_index):02d}.json").write_text(
        json.dumps(payload,indent=2)+"\n",encoding="utf-8"
    )
    print("PHASE5I_DEAD_S3N1_FACTOR="+json.dumps({
        "bottom_index":int(args.bottom_index),"bottom":list(bottom),
        "screen_key":screen.value.comparison_key(),"confirm_key":confirm.value.comparison_key(),
    },sort_keys=True))


if __name__=="__main__":
    main()
