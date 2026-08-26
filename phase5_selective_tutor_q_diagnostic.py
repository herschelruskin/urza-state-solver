#!/usr/bin/env python3
"""Pilot selective tutor-Q control on the same held-out human-kept worlds.

This is a directionality diagnostic, not a calibrated win-rate estimate:
* actual held-out world coordinate stays fixed for comparability with v6;
* each Q decision samples only worlds consistent with current information;
* screen budget=1, confirm budget=2, shortlist=3 to keep the pilot bounded;
* v6 remains the continuation/leaf policy and retains exact ties.
"""

from __future__ import annotations

import json
from pathlib import Path

from information_state_propagation import validate_information_against_state
from non_oracle_episode import run_deterministic_episode
from phase4_hidden_world import materialize_hidden_world
from phase5_mulligan import _opening_world,opening_runtime
from phase5_rollout_policy_v6 import (
    DeterministicRolloutPolicyV6,PHASE5_ROLLOUT_POLICY_V6,
)
from phase5_selective_tutor_q import (
    SelectiveTutorQController,run_selective_tutor_q_episode,
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


def sampled_opening(deck,row):
    seven=tuple(row["drawn_seven"])
    bottom=tuple(row["cards_bottomed"])
    root=opening_runtime(deck,seven,bottom)
    world=_opening_world(
        deck=deck,seven=seven,bottom=bottom,
        mc_root_seed=20260826,sample_id=0,
    )
    sampled=materialize_hidden_world(root,world)
    validate_information_against_state(
        sampled.information,sampled.true_state
    )
    return sampled


def main():
    deck=load_deck()
    fixture=json.loads(
        Path("benchmarks/human/human_mulligan_exact_hands.json")
        .read_text(encoding="utf-8")
    )
    by_id={int(row["hand_id"]):row for row in fixture["hands"]}
    leaf=DeterministicRolloutPolicyV6(policy_id=PHASE5_ROLLOUT_POLICY_V6)

    rows=[]
    for hand_id in SELECTED:
        row=by_id[hand_id]

        base_root=sampled_opening(deck,row)
        base=run_deterministic_episode(
            base_root,horizon=6,max_steps=512,policy=leaf
        )

        q_root=sampled_opening(deck,row)
        controller=SelectiveTutorQController(
            continuation_policy=leaf,
            horizon=6,
            mc_root_seed=20260826,
            screen_rollouts=1,
            confirm_rollouts=2,
            shortlist_size=3,
            max_episode_steps=512,
        )
        improved=run_selective_tutor_q_episode(
            q_root,controller=controller,horizon=6,max_steps=512
        )

        rows.append({
            "hand_id":hand_id,
            "v6_win_turn":base.win_turn,
            "v6_win_family":base.win_family,
            "q_win_turn":improved.win_turn,
            "q_win_family":improved.win_family,
            "q_terminal_reason":improved.episode.terminal_reason,
            "q_decision_count":len(improved.q_decisions),
            "q_override_count":sum(x.overridden for x in improved.q_decisions),
            "q_decisions":[
                {
                    "sequence":x.sequence,
                    "turn":x.turn,
                    "decision_id":x.decision_id,
                    "v6_action":x.v6_action,
                    "chosen_action":x.chosen_action,
                    "overridden":x.overridden,
                    "screen_candidate_count":x.screen_candidate_count,
                    "confirm_candidate_count":x.confirm_candidate_count,
                    "v6_value_key":list(x.v6_value_key),
                    "chosen_value_key":list(x.chosen_value_key),
                }
                for x in improved.q_decisions
            ],
            "q_steps":[
                {
                    "n":step.sequence,
                    "turn":step.turn_before,
                    "kind":step.action_kind,
                    "label":step.action_label,
                }
                for step in improved.episode.steps
            ],
        })

    payload={
        "kind":"phase5-selective-tutor-q-heldout-pilot",
        "mc_root_seed":20260826,
        "actual_world_sample_id":0,
        "horizon":6,
        "screen_rollouts":1,
        "confirm_rollouts":2,
        "shortlist_size":3,
        "selected_hands":list(SELECTED),
        "v6_wins":sum(row["v6_win_turn"] is not None for row in rows),
        "q_wins":sum(row["q_win_turn"] is not None for row in rows),
        "rows":rows,
    }
    Path("phase5_selective_tutor_q_diagnostic.json").write_text(
        json.dumps(payload,indent=2)+"\n",encoding="utf-8"
    )
    print(json.dumps({
        "v6_wins":payload["v6_wins"],
        "q_wins":payload["q_wins"],
        "hands":{
            row["hand_id"]:{
                "v6":row["v6_win_turn"],
                "q":row["q_win_turn"],
                "q_family":row["q_win_family"],
                "q_decisions":row["q_decision_count"],
                "q_overrides":row["q_override_count"],
            }
            for row in rows
        },
    },indent=2))


if __name__=="__main__":
    main()
