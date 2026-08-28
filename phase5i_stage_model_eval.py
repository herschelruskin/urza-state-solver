#!/usr/bin/env python3
"""Fit a small independent Phase-5I London continuation model.

This is not trained on human labels.  It samples fresh sevens from the deck and
runs backward London DP under the frozen Phase-5H gameplay player.  Multiple seed
replications are run separately so continuation-threshold stability can be checked
before human keep/mull agreement is scored.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from phase5_mulligan import OpeningEnvironment
from phase5i_mulligan import Phase5IStageTrainer


HAND_SAMPLES_PER_STAGE=2
OUTER_SCREEN=1
OUTER_CONFIRM=2
BOTTOM_SHORTLIST=4
BASE_SEED=2026082901
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
    p.add_argument("--replicate",type=int,required=True)
    args=p.parse_args()

    rep=int(args.replicate)
    if rep<0:
        raise SystemExit("replicate must be >= 0")
    seat=1 if args.context=="dead" else 2
    seed=BASE_SEED + rep*10_007 + (0 if seat==1 else 1_000_003)
    q_seed=seed+2_000_003

    trainer=Phase5IStageTrainer(
        load_deck(),
        hand_samples_per_stage=HAND_SAMPLES_PER_STAGE,
        earliest_stage=0,
        screen_rollouts_per_bottom=OUTER_SCREEN,
        confirm_rollouts_per_bottom=OUTER_CONFIRM,
        shortlist_size=BOTTOM_SHORTLIST,
        mc_root_seed=seed,
        q_mc_root_seed=q_seed,
        horizon=HORIZON,
        opening_environment=OpeningEnvironment(seat=seat,player_count=4),
    )
    model=trainer.train()
    payload={
        "kind":"phase5i-stage-model-replicate",
        "context":args.context,
        "representative_seat":seat,
        "replicate":rep,
        "mc_root_seed":seed,
        "q_mc_root_seed":q_seed,
        "budgets":{
            "hand_samples_per_stage":HAND_SAMPLES_PER_STAGE,
            "outer_screen_per_bottom":OUTER_SCREEN,
            "outer_confirm_per_bottom":OUTER_CONFIRM,
            "bottom_shortlist":BOTTOM_SHORTLIST,
        },
        "stages":[{
            "stage":row.stage,
            "keep_size":row.keep_size,
            "value":value_json(row.value),
            "keep_rate":row.keep_rate,
            "kept_count":row.kept_count,
            "mulligan_count":row.mulligan_count,
            "legal_bottoms_screened":row.legal_bottoms_screened,
            "bottoms_confirmed":row.bottoms_confirmed,
            "terminal_reasons":[list(x) for x in row.terminal_reason_counts],
        } for row in model.stages],
        "q_cache":{"hits":model.q_cache_hits,"misses":model.q_cache_misses},
    }
    out=Path(f"phase5i_stage_model_{args.context}_rep{rep}.json")
    out.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print("PHASE5I_STAGE="+json.dumps({
        "context":args.context,
        "replicate":rep,
        "stages":{
            str(row.stage):{
                "pwin":row.value.win_probability,
                "key":list(row.value.comparison_key()),
                "keep_rate":row.keep_rate,
            }
            for row in model.stages
        },
        "q_cache":payload["q_cache"],
    },sort_keys=True))


if __name__=="__main__":
    main()
