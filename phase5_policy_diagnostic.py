#!/usr/bin/env python3
"""Compare deterministic rollout policies on held-out human-kept hands."""

from __future__ import annotations

import json
from pathlib import Path

from information_state_propagation import validate_information_against_state
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_episode import run_deterministic_episode
from phase4_hidden_world import materialize_hidden_world
from phase5_mulligan import _opening_world, opening_runtime
from phase5_rollout_policy import DeterministicRolloutPolicyV2, PHASE5_ROLLOUT_POLICY_VERSION
from phase5_rollout_policy_v3 import DeterministicRolloutPolicyV3, PHASE5_ROLLOUT_POLICY_V3
from phase5_rollout_policy_v4 import DeterministicRolloutPolicyV4, PHASE5_ROLLOUT_POLICY_V4

SELECTED = (12, 13, 19, 20, 21, 24, 25, 27, 29, 33)


def load_deck():
    cards = []
    for raw in Path("decklist.txt").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        count, name = line.split(" ", 1)
        if name == "Urza, Lord High Artificer":
            continue
        cards.extend([name] * int(count))
    assert len(cards) == 99
    return tuple(cards)


def run_policy(policy, deck, by_id):
    rows = []
    for hand_id in SELECTED:
        row = by_id[hand_id]
        seven = tuple(row["drawn_seven"])
        bottom = tuple(row["cards_bottomed"])
        root = opening_runtime(deck, seven, bottom)
        world = _opening_world(deck=deck, seven=seven, bottom=bottom, mc_root_seed=20260826, sample_id=0)
        sampled = materialize_hidden_world(root, world)
        validate_information_against_state(sampled.information, sampled.true_state)
        result = run_deterministic_episode(sampled, horizon=6, max_steps=512, policy=policy)
        rows.append({
            "hand_id": hand_id,
            "human_decision": row["decision"],
            "mulligan_count": row["mulligan_count"],
            "keep_size": row["keep_size"],
            "rating_within_size": row.get("rating_within_size"),
            "seven": list(seven),
            "bottom": list(bottom),
            "terminal_reason": result.terminal_reason,
            "win_turn": result.win_turn,
            "win_family": result.win_family,
            "steps": [
                {"n": step.sequence, "turn": step.turn_before, "kind": step.action_kind, "label": step.action_label}
                for step in result.steps
            ],
            "final_turn": result.runtime.true_state.turn,
            "final_hand": list(result.runtime.true_state.hand),
            "final_battlefield": [p.name for p in result.runtime.true_state.battlefield],
            "final_blue": result.runtime.true_state.blue,
            "final_colorless": result.runtime.true_state.colorless,
        })
    return rows


def main():
    deck = load_deck()
    fixture = json.loads(Path("benchmarks/human/human_mulligan_exact_hands.json").read_text(encoding="utf-8"))
    by_id = {int(row["hand_id"]): row for row in fixture["hands"]}
    policies = {
        "base_v1": DeterministicBasePolicy(),
        "rollout_v2": DeterministicRolloutPolicyV2(policy_id=PHASE5_ROLLOUT_POLICY_VERSION),
        "rollout_v3": DeterministicRolloutPolicyV3(policy_id=PHASE5_ROLLOUT_POLICY_V3),
        "rollout_v4_line_parity": DeterministicRolloutPolicyV4(policy_id=PHASE5_ROLLOUT_POLICY_V4),
    }
    results = {}
    for name, policy in policies.items():
        rows = run_policy(policy, deck, by_id)
        results[name] = {
            "policy_id": policy.policy_id,
            "wins": sum(row["win_turn"] is not None for row in rows),
            "win_turns": [row["win_turn"] for row in rows],
            "hands": rows,
        }
    payload = {
        "kind": "rollout-policy-human-hand-diagnostic",
        "mc_root_seed": 20260826,
        "sample_id": 0,
        "horizon": 6,
        "selected_hands": list(SELECTED),
        "results": results,
    }
    Path("phase5_policy_diagnostic.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: {"wins": data["wins"], "win_turns": data["win_turns"]} for name, data in results.items()}, indent=2))


if __name__ == "__main__":
    main()
