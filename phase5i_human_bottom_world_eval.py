#!/usr/bin/env python3
"""Evaluate one fixed outer world for one legal Phase-5I human-hand bottom.

For seat-invariant non-Gemstone hands, each bottom has one pregame choice.  The
monolithic value therefore factorizes exactly into screen sample 0 plus
confirmation samples 1,2,3.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from phase5_mulligan import OpeningEnvironment, unique_bottom_subsets
from phase5i_human_hand_eval import (
    BOTTOM_SHORTLIST,
    HORIZON,
    MC_ROOT_SEED,
    Q_MC_ROOT_SEED,
    estimate_json,
    load_deck,
)
from phase5i_mulligan import Phase5IOpeningKeepEvaluator


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--hand-id",type=int,required=True)
    p.add_argument("--bottom-index",type=int,required=True)
    p.add_argument("--sample-id",type=int,required=True,choices=(0,1,2,3))
    args=p.parse_args()

    fixture=json.loads(
        Path("benchmarks/human/human_mulligan_exact_hands.json").read_text(encoding="utf-8")
    )
    row=next(x for x in fixture["hands"] if int(x["hand_id"])==int(args.hand_id))
    seven=tuple(row["drawn_seven"])
    if "Gemstone Caverns" in seven:
        raise SystemExit("world factorization currently requires seat-invariant non-Gemstone hand")
    stage=int(row["mulligan_count"])
    bottoms=unique_bottom_subsets(seven,stage)
    idx=int(args.bottom_index)
    if not 0<=idx<len(bottoms):
        raise SystemExit(f"bottom-index must be in [0,{len(bottoms)-1}]")
    bottom=bottoms[idx]

    evaluator=Phase5IOpeningKeepEvaluator(
        load_deck(),
        screen_rollouts=1,
        confirm_rollouts=1,
        shortlist_size=BOTTOM_SHORTLIST,
        mc_root_seed=MC_ROOT_SEED,
        q_mc_root_seed=Q_MC_ROOT_SEED,
        horizon=HORIZON,
        opening_environment=OpeningEnvironment(seat=1,player_count=4),
    )
    sample_id=int(args.sample_id)
    if sample_id==0:
        estimate=evaluator.screen_evaluator.evaluate(
            seven,stage=stage,candidate_bottoms=(bottom,),sample_start=0
        ).best
        phase="screen"
    else:
        estimate=evaluator.confirm_evaluator.evaluate(
            seven,stage=stage,candidate_bottoms=(bottom,),sample_start=sample_id
        ).best
        phase="confirm"

    payload={
        "kind":"phase5i-human-bottom-world-factor",
        "hand_id":int(args.hand_id),
        "stage":stage,
        "bottom_index":idx,
        "bottom":list(bottom),
        "sample_id":sample_id,
        "phase":phase,
        "estimate":estimate_json(estimate),
        "q_cache":{
            "hits":evaluator.cache.stats.hits,
            "misses":evaluator.cache.stats.misses,
            "evictions":getattr(evaluator.cache.stats,"evictions",0),
        },
    }
    out=Path(
        f"phase5i_human_bottom_world_h{int(args.hand_id)}_b{idx}_n{sample_id}.json"
    )
    out.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print("PHASE5I_HUMAN_BOTTOM_WORLD="+json.dumps({
        "hand_id":int(args.hand_id),
        "bottom_index":idx,
        "sample_id":sample_id,
        "phase":phase,
        "key":payload["estimate"]["value"]["comparison_key"],
    },sort_keys=True))


if __name__=="__main__":
    main()
