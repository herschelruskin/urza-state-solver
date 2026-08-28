#!/usr/bin/env python3
"""Evaluate one legal London bottom independently for a held-out Phase-5I hand.

This is an exact execution factorization of phase5i_human_hand_eval.py.  Each
legal bottom receives the same screen world (sample 0) and confirmation worlds
(samples 1..3) as the monolithic evaluator.  Cache state is execution-only, so
separating bottoms cannot change their seeded values.
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
    OUTER_CONFIRM,
    OUTER_SCREEN,
    Q_MC_ROOT_SEED,
    estimate_json,
    load_deck,
)
from phase5i_mulligan import Phase5IOpeningKeepEvaluator


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--hand-id",type=int,required=True)
    p.add_argument("--bottom-index",type=int,required=True)
    args=p.parse_args()

    fixture=json.loads(
        Path("benchmarks/human/human_mulligan_exact_hands.json").read_text(encoding="utf-8")
    )
    row=next(x for x in fixture["hands"] if int(x["hand_id"])==int(args.hand_id))
    if not row.get("primary_benchmark_usable",False):
        raise SystemExit(f"hand {args.hand_id} is not an exact-state benchmark")

    seven=tuple(row["drawn_seven"])
    if "Gemstone Caverns" in seven:
        raise SystemExit("factorized helper currently expects seat-invariant hands")
    stage=int(row["mulligan_count"])
    bottoms=unique_bottom_subsets(seven,stage)
    idx=int(args.bottom_index)
    if not 0<=idx<len(bottoms):
        raise SystemExit(f"bottom-index must be in [0,{len(bottoms)-1}]")
    bottom=bottoms[idx]

    evaluator=Phase5IOpeningKeepEvaluator(
        load_deck(),
        screen_rollouts=OUTER_SCREEN,
        confirm_rollouts=OUTER_CONFIRM,
        shortlist_size=BOTTOM_SHORTLIST,
        mc_root_seed=MC_ROOT_SEED,
        q_mc_root_seed=Q_MC_ROOT_SEED,
        horizon=HORIZON,
        opening_environment=OpeningEnvironment(seat=1,player_count=4),
    )
    screen=evaluator.screen_evaluator.evaluate(
        seven,
        stage=stage,
        candidate_bottoms=(bottom,),
        sample_start=0,
    ).best
    confirm=evaluator.confirm_evaluator.evaluate(
        seven,
        stage=stage,
        candidate_bottoms=(bottom,),
        sample_start=OUTER_SCREEN,
    ).best

    payload={
        "kind":"phase5i-human-bottom-factor",
        "hand_id":int(args.hand_id),
        "stage":stage,
        "bottom_index":idx,
        "bottom":list(bottom),
        "screen":estimate_json(screen),
        "confirm":estimate_json(confirm),
        "q_cache":{
            "hits":evaluator.cache.stats.hits,
            "misses":evaluator.cache.stats.misses,
            "evictions":getattr(evaluator.cache.stats,"evictions",0),
            "max_entries":getattr(evaluator.cache,"max_entries",None),
        },
        "budgets":{
            "outer_screen":OUTER_SCREEN,
            "outer_confirm":OUTER_CONFIRM,
            "bottom_shortlist":BOTTOM_SHORTLIST,
            "mc_root_seed":MC_ROOT_SEED,
            "q_mc_root_seed":Q_MC_ROOT_SEED,
        },
    }
    out=Path(f"phase5i_human_bottom_h{int(args.hand_id)}_b{idx}.json")
    out.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print("PHASE5I_HUMAN_BOTTOM="+json.dumps({
        "hand_id":int(args.hand_id),
        "bottom_index":idx,
        "bottom":list(bottom),
        "screen_key":payload["screen"]["value"]["comparison_key"],
        "confirm_key":payload["confirm"]["value"]["comparison_key"],
    },sort_keys=True))


if __name__=="__main__":
    main()
