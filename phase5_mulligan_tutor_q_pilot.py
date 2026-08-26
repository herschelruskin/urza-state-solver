#!/usr/bin/env python3
"""Small, pre-training mulligan value pilot with selective tutor-Q continuation.

This is intentionally not a fitted mulligan model. It evaluates two exact benchmark
sevens at stage 2 (keep six) under identical outer hidden-world coordinates:

  * rollout-v6 continuation;
  * selective tutor-Q continuation with rollout-v6 leaves.

The human counterfactual bottoms are reported only after evaluation and are not used
to score or constrain the solver. This gives a first check that adding Q can improve
continuation values/bottom rankings without circularly training on the annotations.

Budgets are deliberately tiny because Q is nested inside each opening rollout.
"""

from __future__ import annotations

import json
from pathlib import Path

from phase5_mulligan import OpeningKeepEvaluator
from phase5_rollout_policy_v6 import (
    DeterministicRolloutPolicyV6,
    PHASE5_ROLLOUT_POLICY_V6,
)
from phase5_selective_tutor_q import make_selective_tutor_q_episode_runner

HAND_IDS=(22,23)
STAGE=2
OUTER_ROLLOUTS=1
MC_ROOT_SEED=20260826


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
        "no_win":value.no_win,
        "win_families":[list(x) for x in value.win_families],
    }


def estimate_json(estimate):
    return {
        "bottom":list(estimate.bottom),
        "kept_hand":list(estimate.kept_hand),
        "value":value_json(estimate.value),
        "terminal_reasons":[list(x) for x in estimate.terminal_reason_counts],
    }


def human_counterfactual(row):
    cf=row.get("counterfactual_keep_at_m2") or {}
    return {
        "decision":cf.get("decision"),
        "lean":cf.get("lean"),
        "bottom":cf.get("bottom") or cf.get("bottom_if_keep") or [],
        "note":cf.get("note",""),
    }


def main():
    deck=load_deck()
    fixture=json.loads(
        Path("benchmarks/human/human_mulligan_exact_hands.json")
        .read_text(encoding="utf-8")
    )
    by_id={int(row["hand_id"]):row for row in fixture["hands"]}

    leaf=DeterministicRolloutPolicyV6(policy_id=PHASE5_ROLLOUT_POLICY_V6)
    v6_eval=OpeningKeepEvaluator(
        deck,
        rollout_count=OUTER_ROLLOUTS,
        mc_root_seed=MC_ROOT_SEED,
        horizon=6,
        continuation_policy=leaf,
        max_episode_steps=512,
        strict_terminal_reasons=True,
    )
    q_eval=OpeningKeepEvaluator(
        deck,
        rollout_count=OUTER_ROLLOUTS,
        mc_root_seed=MC_ROOT_SEED,
        horizon=6,
        continuation_policy=leaf,
        max_episode_steps=512,
        strict_terminal_reasons=True,
        episode_runner=make_selective_tutor_q_episode_runner(
            mc_root_seed=MC_ROOT_SEED,
            screen_rollouts=1,
            confirm_rollouts=1,
            shortlist_size=3,
        ),
    )

    rows=[]
    for hand_id in HAND_IDS:
        row=by_id[hand_id]
        seven=tuple(row["drawn_seven"])
        v6=v6_eval.evaluate(seven,stage=STAGE)
        q=q_eval.evaluate(seven,stage=STAGE)
        human=human_counterfactual(row)
        rows.append({
            "hand_id":hand_id,
            "seven":list(seven),
            "human_counterfactual":human,
            "v6_best":estimate_json(v6.best),
            "q_best":estimate_json(q.best),
            "v6_human_bottom_rank":next(
                (
                    rank for rank,est in enumerate(v6.estimates,1)
                    if list(est.bottom)==sorted(human["bottom"])
                ),
                None,
            ),
            "q_human_bottom_rank":next(
                (
                    rank for rank,est in enumerate(q.estimates,1)
                    if list(est.bottom)==sorted(human["bottom"])
                ),
                None,
            ),
            "v6_all":[estimate_json(x) for x in v6.estimates],
            "q_all":[estimate_json(x) for x in q.estimates],
        })

    payload={
        "kind":"phase5-mulligan-tutor-q-pilot",
        "stage":STAGE,
        "keep_size":6,
        "outer_rollouts_per_bottom":OUTER_ROLLOUTS,
        "q_screen_rollouts":1,
        "q_confirm_rollouts":1,
        "mc_root_seed":MC_ROOT_SEED,
        "human_annotations_used_for_selection_only":True,
        "rows":rows,
    }
    Path("phase5_mulligan_tutor_q_pilot.json").write_text(
        json.dumps(payload,indent=2)+"\n",encoding="utf-8"
    )
    print(json.dumps({
        row["hand_id"]:{
            "human":row["human_counterfactual"],
            "v6_best_bottom":row["v6_best"]["bottom"],
            "v6_win_probability":row["v6_best"]["value"]["win_probability"],
            "v6_human_bottom_rank":row["v6_human_bottom_rank"],
            "q_best_bottom":row["q_best"]["bottom"],
            "q_win_probability":row["q_best"]["value"]["win_probability"],
            "q_human_bottom_rank":row["q_human_bottom_rank"],
        }
        for row in rows
    },indent=2))


if __name__=="__main__":
    main()
