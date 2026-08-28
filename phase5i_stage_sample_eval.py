#!/usr/bin/env python3
"""Evaluate one independent K_s(h) sample for Phase-5I London DP.

The London recursion does not require stages to be simulated serially.  For each
stage s we may independently sample fresh sevens and estimate their optimal
seat-conditioned keep value K_s(h).  A later reducer performs the backward
recursion

    V_s = E_h[max(K_s(h), V_{s+1})]

with stage 6 forced to keep.  This factorization preserves the DP semantics while
letting expensive frozen-Phase5H gameplay evaluations run in parallel.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from phase5_mulligan import OpeningEnvironment, _sample_fresh_seven, keep_size_for_stage
from phase5i_mulligan import Phase5IOpeningKeepEvaluator


OUTER_SCREEN=1
OUTER_CONFIRM=2
BOTTOM_SHORTLIST=4
PARALLEL_BOTTOM_WORKERS=4
MAX_SCREEN_TIE_BREAK_ROLLOUTS=2
BASE_SEED=2026083001
Q_SEED_OFFSET=2_000_003
HORIZON=6


def load_deck():
    cards=[]
    for raw in Path("decklist.txt").read_text(encoding="utf-8").splitlines():
        line=raw.strip()
        if not line:
            continue
        count,name=line.split(" ",1)
        if name=="Urza, Lord High Artificer":
            continue
        cards.extend([name]*int(count))
    assert len(cards)==99
    return tuple(cards)


def value_json(value):
    return {
        "win_probability":value.win_probability,
        "exact_win":list(value.exact_win),
        "cumulative":[value.win_by(t) for t in range(1,value.horizon+1)],
        "comparison_key":list(value.comparison_key()),
        "no_win":value.no_win,
        "win_families":[list(x) for x in value.win_families],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--context",choices=("dead","live"),required=True)
    p.add_argument("--stage",type=int,required=True)
    p.add_argument("--sample-id",type=int,required=True)
    args=p.parse_args()
    stage=int(args.stage)
    sample_id=int(args.sample_id)
    if not 0<=stage<=6:
        raise SystemExit("stage must be in [0,6]")
    if sample_id<0:
        raise SystemExit("sample-id must be >=0")

    seat=1 if args.context=="dead" else 2
    # Keep stage/sample/context separated in the root seed so every K sample is
    # reproducible and independent without depending on matrix execution order.
    seed=(
        BASE_SEED
        + (0 if seat==1 else 1_000_003)
        + stage*10_007
        + sample_id*100_003
    )
    q_seed=seed+Q_SEED_OFFSET
    deck=load_deck()
    seven=_sample_fresh_seven(
        deck,
        root_seed=seed,
        stage=stage,
        sample_id=sample_id,
    )
    evaluator=Phase5IOpeningKeepEvaluator(
        deck,
        screen_rollouts=OUTER_SCREEN,
        confirm_rollouts=OUTER_CONFIRM,
        shortlist_size=BOTTOM_SHORTLIST,
        mc_root_seed=seed,
        q_mc_root_seed=q_seed,
        horizon=HORIZON,
        opening_environment=OpeningEnvironment(seat=seat,player_count=4),
        parallel_workers=PARALLEL_BOTTOM_WORKERS,
        max_screen_tie_break_rollouts=MAX_SCREEN_TIE_BREAK_ROLLOUTS,
    )
    result=evaluator.evaluate(seven,stage=stage)
    best=result.best
    payload={
        "kind":"phase5i-stage-keep-sample",
        "context":args.context,
        "representative_seat":seat,
        "stage":stage,
        "keep_size":keep_size_for_stage(stage),
        "sample_id":sample_id,
        "mc_root_seed":seed,
        "q_mc_root_seed":q_seed,
        "seven":list(seven),
        "best_bottom":list(best.bottom),
        "best_pregame_choice":{
            "use_caverns":bool(best.pregame_choice.use_caverns),
            "exile_card":str(best.pregame_choice.exile_card),
        },
        "keep_value":value_json(best.value),
        "terminal_reasons":[list(x) for x in best.terminal_reason_counts],
        "legal_bottom_count":result.legal_bottom_count,
        "confirmed_bottom_count":result.confirmed_bottom_count,
        "fully_confirmed_bottom_count":result.fully_confirmed_bottom_count,
        "screen_tie_break_rollouts":result.screen_tie_break_rollouts,
        "confirmation_early_eliminated_bottoms":[
            list(x) for x in result.confirmation_early_eliminated_bottoms
        ],
        "parallel_workers":result.parallel_workers,
        "confirmation_start_sample":result.confirmation_start_sample,
        "q_cache":{
            "hits":evaluator.cache.stats.hits,
            "misses":evaluator.cache.stats.misses,
        },
        "budgets":{
            "outer_screen":OUTER_SCREEN,
            "outer_confirm":OUTER_CONFIRM,
            "bottom_shortlist":BOTTOM_SHORTLIST,
            "parallel_bottom_workers":PARALLEL_BOTTOM_WORKERS,
            "max_screen_tie_break_rollouts":MAX_SCREEN_TIE_BREAK_ROLLOUTS,
        },
    }
    out=Path(
        f"phase5i_stage_sample_{args.context}_s{stage}_n{sample_id}.json"
    )
    out.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print("PHASE5I_STAGE_SAMPLE="+json.dumps({
        "context":args.context,
        "stage":stage,
        "sample_id":sample_id,
        "pwin":best.value.win_probability,
        "value_key":list(best.value.comparison_key()),
        "best_bottom":list(best.bottom),
    },sort_keys=True))


if __name__=="__main__":
    main()
