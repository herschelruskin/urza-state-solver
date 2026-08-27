#!/usr/bin/env python3
"""Train an unlabeled Phase-5I London continuation model under frozen Phase-5H Q.

Human annotations are never read here.  Fresh sevens are sampled from decklist.txt,
evaluated backward from the forced keep-2 floor, and saved as stage continuation
values for later held-out human comparison.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from phase5_adaptive_mulligan import AdaptiveMulliganStageTrainer
from phase5_mulligan import OpeningEnvironment
from phase5_selective_tutor_q import (
    PHASE5H_PRODUCTION_TUTOR_Q_CONFIG,
    PHASE5_SELECTIVE_TUTOR_Q_VERSION,
)


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
    assert len(cards)==99,len(cards)
    return tuple(cards)


def value_json(value):
    return {
        "horizon":int(value.horizon),
        "win_probability":float(value.win_probability),
        "exact_win":[float(x) for x in value.exact_win],
        "cumulative":[float(value.win_by(t)) for t in range(1,value.horizon+1)],
        "no_win":float(value.no_win),
        "win_families":[[name,float(p)] for name,p in value.win_families],
        "comparison_key":[float(x) for x in value.comparison_key()],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--hand-samples-per-stage",type=int,default=3)
    p.add_argument("--screen-rollouts-per-bottom",type=int,default=1)
    p.add_argument("--confirm-rollouts-per-bottom",type=int,default=2)
    p.add_argument("--shortlist-size",type=int,default=4)
    p.add_argument("--mc-root-seed",type=int,default=2026082901)
    p.add_argument("--q-mc-root-seed",type=int,default=2026082902)
    p.add_argument("--output",default="phase5i_stage_model.json")
    args=p.parse_args()

    deck=load_deck()
    environment=OpeningEnvironment(seat=1,player_count=4)
    trainer=AdaptiveMulliganStageTrainer(
        deck,
        hand_samples_per_stage=args.hand_samples_per_stage,
        earliest_stage=0,
        screen_rollouts_per_bottom=args.screen_rollouts_per_bottom,
        confirm_rollouts_per_bottom=args.confirm_rollouts_per_bottom,
        shortlist_size=args.shortlist_size,
        mc_root_seed=args.mc_root_seed,
        q_mc_root_seed=args.q_mc_root_seed,
        horizon=6,
        max_episode_steps=512,
        strict_terminal_reasons=True,
        opening_environment=environment,
    )
    model=trainer.train()

    payload={
        "kind":"phase5i-unlabeled-stage-continuation-model",
        "human_labels_used":False,
        "deck_size":len(deck),
        "opening_environment":{
            "seat":environment.seat,
            "player_count":environment.player_count,
            "caverns_live":environment.caverns_live,
        },
        "phase5h_q_version":PHASE5_SELECTIVE_TUTOR_Q_VERSION,
        "phase5h_q_config":{
            "screen_rollouts":PHASE5H_PRODUCTION_TUTOR_Q_CONFIG.screen_rollouts,
            "confirm_rollouts":PHASE5H_PRODUCTION_TUTOR_Q_CONFIG.confirm_rollouts,
            "shortlist_size":PHASE5H_PRODUCTION_TUTOR_Q_CONFIG.shortlist_size,
            "contingent":PHASE5H_PRODUCTION_TUTOR_Q_CONFIG.contingent,
            "confidence_gate":PHASE5H_PRODUCTION_TUTOR_Q_CONFIG.confidence_gate,
            "validation_rollouts":PHASE5H_PRODUCTION_TUTOR_Q_CONFIG.validation_rollouts,
            "max_validation_rollouts":PHASE5H_PRODUCTION_TUTOR_Q_CONFIG.max_validation_rollouts,
            "confidence_alpha":PHASE5H_PRODUCTION_TUTOR_Q_CONFIG.confidence_alpha,
        },
        "training":{
            "hand_samples_per_stage":model.hand_samples_per_stage,
            "screen_rollouts_per_bottom":model.screen_rollouts_per_bottom,
            "confirm_rollouts_per_bottom":model.confirm_rollouts_per_bottom,
            "shortlist_size":model.shortlist_size,
            "mc_root_seed":model.mc_root_seed,
            "q_mc_root_seed":model.q_mc_root_seed,
            "horizon":model.horizon,
            "q_cache_hits":model.q_cache_hits,
            "q_cache_misses":model.q_cache_misses,
        },
        "stages":[
            {
                "stage":row.stage,
                "keep_size":row.keep_size,
                "value":value_json(row.value),
                "sampled_hands":row.sampled_hands,
                "kept_count":row.kept_count,
                "mulligan_count":row.mulligan_count,
                "keep_rate":row.keep_rate,
                "legal_bottoms_screened":row.legal_bottoms_screened,
                "bottoms_confirmed":row.bottoms_confirmed,
                "terminal_reasons":[list(x) for x in row.evaluated_keep_terminal_reason_counts],
            }
            for row in model.stages
        ],
        "sampled_decisions":[
            {
                "stage":row.stage,
                "sample_id":row.sample_id,
                "seven":list(row.seven),
                "decision":row.decision,
                "best_bottom":list(row.best_bottom),
                "pregame_choice":{
                    "use_caverns":row.best_pregame_choice.use_caverns,
                    "exile_card":row.best_pregame_choice.exile_card,
                },
                "keep_value_key":list(row.keep_value_key),
                "continuation_value_key":(
                    None if row.continuation_value_key is None
                    else list(row.continuation_value_key)
                ),
                "legal_bottom_count":row.legal_bottom_count,
                "confirmed_bottom_count":row.confirmed_bottom_count,
            }
            for row in model.hand_decisions
        ],
    }
    Path(args.output).write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print("PHASE5I_STAGE_MODEL="+json.dumps({
        "stages":{
            str(row["stage"]):{
                "keep_size":row["keep_size"],
                "pwin":row["value"]["win_probability"],
                "keep_rate":row["keep_rate"],
            }
            for row in payload["stages"]
        },
        "q_cache":{
            "hits":model.q_cache_hits,
            "misses":model.q_cache_misses,
        },
    },sort_keys=True))


if __name__=="__main__":
    main()
