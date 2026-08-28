#!/usr/bin/env python3
"""Evaluate one exact outer confirmation world for Phase-5I human hand 12."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from phase5_mulligan import OpeningEnvironment
from phase5i_human_hand_eval import (
    BOTTOM_SHORTLIST,
    HORIZON,
    MC_ROOT_SEED,
    Q_MC_ROOT_SEED,
    estimate_json,
    load_deck,
)
from phase5i_mulligan import Phase5IOpeningKeepEvaluator


HAND_ID=12
STAGE=1


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--sample-id",type=int,required=True,choices=(0,1,2))
    args=p.parse_args()

    fixture=json.loads(
        Path("benchmarks/human/human_mulligan_exact_hands.json").read_text(encoding="utf-8")
    )
    row=next(x for x in fixture["hands"] if int(x["hand_id"])==HAND_ID)
    seven=tuple(row["drawn_seven"])
    deck=load_deck()
    evaluator=Phase5IOpeningKeepEvaluator(
        deck,
        screen_rollouts=1,
        confirm_rollouts=1,
        shortlist_size=BOTTOM_SHORTLIST,
        mc_root_seed=MC_ROOT_SEED,
        q_mc_root_seed=Q_MC_ROOT_SEED,
        horizon=HORIZON,
        opening_environment=OpeningEnvironment(seat=1,player_count=4),
    )
    evaluated=evaluator.confirm_evaluator.evaluate(
        seven,
        stage=STAGE,
        candidate_bottoms=((),),
        sample_start=int(args.sample_id),
    )
    payload={
        "kind":"phase5i-hand12-factorized-confirm-world",
        "hand_id":HAND_ID,
        "stage":STAGE,
        "sample_id":int(args.sample_id),
        "mc_root_seed":MC_ROOT_SEED,
        "q_mc_root_seed":Q_MC_ROOT_SEED,
        "estimate":estimate_json(evaluated.best),
        "q_cache":{
            "hits":evaluator.cache.stats.hits,
            "misses":evaluator.cache.stats.misses,
        },
    }
    out=Path(f"phase5i_hand12_world_{int(args.sample_id)}.json")
    out.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print("PHASE5I_HAND12_WORLD="+json.dumps({
        "sample_id":payload["sample_id"],
        "pwin":payload["estimate"]["value"]["win_probability"],
        "key":payload["estimate"]["value"]["comparison_key"],
    },sort_keys=True))


if __name__=="__main__":
    main()
