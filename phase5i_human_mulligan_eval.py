#!/usr/bin/env python3
"""Evaluate one exact human mulligan hand against a fixed unlabeled stage model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from phase3_value_engine import WinDistributionValue
from phase5_adaptive_mulligan import AdaptiveOpeningKeepEvaluator
from phase5_mulligan import OpeningEnvironment, value_at_least
from phase5_rollout_policy_v6 import DeterministicRolloutPolicyV6, PHASE5_ROLLOUT_POLICY_V6


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


def value_from_json(row):
    return WinDistributionValue(
        horizon=int(row["horizon"]),
        exact_win=tuple(float(x) for x in row["exact_win"]),
        no_win=float(row["no_win"]),
        win_families=tuple((str(name),float(p)) for name,p in row.get("win_families",())),
    )


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


def estimate_json(estimate):
    return {
        "bottom":list(estimate.bottom),
        "kept_hand":list(estimate.kept_hand),
        "pregame_choice":{
            "use_caverns":estimate.pregame_choice.use_caverns,
            "exile_card":estimate.pregame_choice.exile_card,
        },
        "value":value_json(estimate.value),
        "rollouts":estimate.rollouts,
        "terminal_reasons":[list(x) for x in estimate.terminal_reason_counts],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--hand-id",type=int,required=True)
    p.add_argument("--stage-model",default="phase5i_stage_model.json")
    p.add_argument("--screen-rollouts-per-bottom",type=int,default=1)
    p.add_argument("--confirm-rollouts-per-bottom",type=int,default=2)
    p.add_argument("--shortlist-size",type=int,default=4)
    p.add_argument("--mc-root-seed",type=int,default=2026083001)
    p.add_argument("--q-mc-root-seed",type=int,default=2026083002)
    args=p.parse_args()

    fixture=json.loads(
        Path("benchmarks/human/human_mulligan_exact_hands.json").read_text(encoding="utf-8")
    )
    row=next(x for x in fixture["hands"] if int(x["hand_id"])==int(args.hand_id))
    if row.get("primary_benchmark_usable") is False:
        raise SystemExit(f"hand {args.hand_id} is not benchmark-usable")

    stage=int(row["mulligan_count"])
    seven=tuple(row["drawn_seven"])
    human_decision=str(row["decision"])
    human_bottom=tuple(sorted(str(x) for x in row.get("cards_bottomed") or ()))

    stage_payload=json.loads(Path(args.stage_model).read_text(encoding="utf-8"))
    stage_values={
        int(x["stage"]):value_from_json(x["value"])
        for x in stage_payload["stages"]
    }
    continuation=stage_values.get(stage+1)

    evaluator=AdaptiveOpeningKeepEvaluator(
        load_deck(),
        screen_rollouts=args.screen_rollouts_per_bottom,
        confirm_rollouts=args.confirm_rollouts_per_bottom,
        shortlist_size=args.shortlist_size,
        mc_root_seed=args.mc_root_seed,
        q_mc_root_seed=args.q_mc_root_seed,
        horizon=6,
        continuation_policy=DeterministicRolloutPolicyV6(
            policy_id=PHASE5_ROLLOUT_POLICY_V6
        ),
        max_episode_steps=512,
        strict_terminal_reasons=True,
        opening_environment=OpeningEnvironment(seat=1,player_count=4),
    )
    result=evaluator.evaluate(seven,stage=stage)
    best=result.best
    solver_decision=(
        "Keep"
        if continuation is None or value_at_least(best.value,continuation)
        else "Mulligan"
    )

    confirmation_rank={
        est.bottom:i
        for i,est in enumerate(result.confirmation.estimates,1)
    }
    human_bottom_estimate=None
    human_bottom_rank=None
    human_bottom_shortlisted=None
    bottom_exact_match=None
    delta_pwin_best_minus_human=None
    delta_cumulative_best_minus_human=None

    if human_decision=="Keep":
        bottom_exact_match=(best.bottom==human_bottom)
        human_bottom_shortlisted=(human_bottom in confirmation_rank)
        human_bottom_rank=confirmation_rank.get(human_bottom)
        if human_bottom in confirmation_rank:
            human_bottom_estimate=next(
                est for est in result.confirmation.estimates
                if est.bottom==human_bottom
            )
        else:
            # Human annotation is comparison-only: evaluate it after solver
            # selection on the same confirmation outer-world window.
            human_eval=evaluator.confirm_evaluator.evaluate(
                seven,
                stage=stage,
                candidate_bottoms=(human_bottom,),
                sample_start=evaluator.screen_rollouts,
            )
            human_bottom_estimate=human_eval.best

        delta_pwin_best_minus_human=(
            float(best.value.win_probability)
            - float(human_bottom_estimate.value.win_probability)
        )
        delta_cumulative_best_minus_human=[
            float(best.value.win_by(t)-human_bottom_estimate.value.win_by(t))
            for t in range(1,7)
        ]

    payload={
        "kind":"phase5i-heldout-human-mulligan-hand",
        "hand_id":int(args.hand_id),
        "stage":stage,
        "keep_size":int(row["keep_size"]),
        "seven":list(seven),
        "human":{
            "decision":human_decision,
            "rating_within_size":row.get("rating_within_size"),
            "bottom":list(human_bottom),
        },
        "solver":{
            "decision":solver_decision,
            "best":estimate_json(best),
            "continuation_value":(
                None if continuation is None else value_json(continuation)
            ),
            "legal_bottom_count":result.legal_bottom_count,
            "confirmed_bottom_count":result.confirmed_bottom_count,
            "shortlisted_bottoms":[list(x) for x in result.shortlisted_bottoms],
        },
        "comparison":{
            "decision_match":solver_decision==human_decision,
            "bottom_exact_match":bottom_exact_match,
            "human_bottom_shortlisted":human_bottom_shortlisted,
            "human_bottom_confirmation_rank":human_bottom_rank,
            "human_bottom_estimate":(
                None if human_bottom_estimate is None
                else estimate_json(human_bottom_estimate)
            ),
            "delta_pwin_best_minus_human":delta_pwin_best_minus_human,
            "delta_cumulative_best_minus_human":delta_cumulative_best_minus_human,
        },
        "annotations_used_for_solver_selection":False,
    }
    out=Path(f"phase5i_human_hand_{int(args.hand_id):02d}.json")
    out.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print("PHASE5I_HUMAN_HAND="+json.dumps({
        "hand_id":payload["hand_id"],
        "stage":stage,
        "human":human_decision,
        "solver":solver_decision,
        "decision_match":payload["comparison"]["decision_match"],
        "solver_bottom":payload["solver"]["best"]["bottom"],
        "human_bottom":list(human_bottom),
        "bottom_exact_match":bottom_exact_match,
        "best_pwin":payload["solver"]["best"]["value"]["win_probability"],
        "continuation_pwin":(
            None if continuation is None else continuation.win_probability
        ),
    },sort_keys=True))


if __name__=="__main__":
    main()
