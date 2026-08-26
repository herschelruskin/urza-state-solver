#!/usr/bin/env python3
"""Held-out comparison of rollout-v6 versus selective tutor-Q improvement."""

from __future__ import annotations

import json
from pathlib import Path

from information_state_propagation import validate_information_against_state
from non_oracle_episode import run_deterministic_episode
from phase4_hidden_world import materialize_hidden_world
from phase5_mulligan import _opening_world, opening_runtime
from phase5_rollout_policy_v6 import (
    DeterministicRolloutPolicyV6,
    PHASE5_ROLLOUT_POLICY_V6,
)
from phase5_tutor_q_controller import (
    Phase5TutorQController,
    run_tutor_q_episode,
)

SELECTED=(12,13,19,20,21,24,25,27,29,33)


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


def opening(deck,row):
    seven=tuple(row["drawn_seven"])
    bottom=tuple(row["cards_bottomed"])
    root=opening_runtime(deck,seven,bottom)
    world=_opening_world(
        deck=deck,
        seven=seven,
        bottom=bottom,
        mc_root_seed=20260826,
        sample_id=0,
    )
    sampled=materialize_hidden_world(root,world)
    validate_information_against_state(sampled.information,sampled.true_state)
    return sampled


def main():
    deck=load_deck()
    fixture=json.loads(
        Path("benchmarks/human/human_mulligan_exact_hands.json").read_text(
            encoding="utf-8"
        )
    )
    by_id={int(row["hand_id"]):row for row in fixture["hands"]}
    v6=DeterministicRolloutPolicyV6(policy_id=PHASE5_ROLLOUT_POLICY_V6)
    rows=[]

    for hand_id in SELECTED:
        row=by_id[hand_id]

        base_result=run_deterministic_episode(
            opening(deck,row),
            horizon=6,
            max_steps=512,
            policy=v6,
        )

        controller=Phase5TutorQController(
            screen_rollouts=1,
            confirm_rollouts=2,
            shortlist=4,
            mc_root_seed=20260826,
            horizon=6,
            continuation_policy=v6,
            max_episode_steps=512,
        )
        q_result=run_tutor_q_episode(
            opening(deck,row),
            controller=controller,
            horizon=6,
            max_steps=512,
        )
        q_used=[decision for decision in controller.decisions if decision.used_q]
        q_overrides=[
            decision for decision in q_used
            if decision.chosen_action!=decision.v6_action
        ]
        rows.append({
            "hand_id":hand_id,
            "v6":{
                "win_turn":base_result.win_turn,
                "win_family":base_result.win_family,
                "terminal_reason":base_result.terminal_reason,
            },
            "tutor_q":{
                "win_turn":q_result.win_turn,
                "win_family":q_result.win_family,
                "terminal_reason":q_result.terminal_reason,
                "q_decisions":len(q_used),
                "q_overrides":len(q_overrides),
                "overrides":[
                    {
                        "turn":d.turn,
                        "stage":d.decision_stage,
                        "v6":d.v6_action,
                        "chosen":d.chosen_action,
                        "reason":d.reason,
                        "screen_best":d.screen_best,
                        "q_best":d.q_best,
                        "candidates":d.candidate_count,
                        "confirmed":d.confirmed_count,
                    }
                    for d in q_overrides
                ],
            },
        })

    payload={
        "kind":"phase5-selective-tutor-q-heldout",
        "horizon":6,
        "mc_root_seed":20260826,
        "screen_rollouts":1,
        "confirm_rollouts":2,
        "selected_hands":list(SELECTED),
        "v6_wins":sum(row["v6"]["win_turn"] is not None for row in rows),
        "tutor_q_wins":sum(
            row["tutor_q"]["win_turn"] is not None for row in rows
        ),
        "rows":rows,
    }
    Path("phase5_tutor_q_policy_diagnostic.json").write_text(
        json.dumps(payload,indent=2)+"\n",encoding="utf-8"
    )
    print(json.dumps({
        "v6_wins":payload["v6_wins"],
        "tutor_q_wins":payload["tutor_q_wins"],
        "hands":{
            row["hand_id"]:{
                "v6":row["v6"]["win_turn"],
                "q":row["tutor_q"]["win_turn"],
                "overrides":row["tutor_q"]["q_overrides"],
            }
            for row in rows
        },
    },indent=2))


if __name__=="__main__":
    main()
