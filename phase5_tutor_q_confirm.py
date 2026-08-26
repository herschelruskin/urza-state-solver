#!/usr/bin/env python3
"""Targeted confirmation of tutor-Q disagreements from the one-world screen.

The first-pass Q audit is deliberately cheap and is only a screening device.  This
script revisits the reproduced states with eight common hidden worlds per candidate,
comparing only the strategically meaningful alternatives identified by the screen.
The underlying played trajectory remains rollout-v6 so every state coordinate stays
fixed and reproducible.
"""

from __future__ import annotations

import json
from pathlib import Path

from information_state_propagation import validate_information_against_state
from non_oracle_episode import _checked_runtime, episode_cycle_key
from non_oracle_rules_adapter_v2 import apply_main_action, rules_decision_request
from phase4_hidden_world import materialize_hidden_world
from phase5_monte_carlo import Phase5MonteCarloDecisionEvaluator
from phase5_mulligan import _opening_world, opening_runtime
from phase5_rollout_policy_v6 import (
    DeterministicRolloutPolicyV6,
    PHASE5_ROLLOUT_POLICY_V6,
)

HORIZON = 6
MAX_STEPS = 512
ROLLOUTS = 8

# Exact labels are intentional: these are audited, reproduced decisions rather than
# a new heuristic action filter. "End turn" is included where the question is tutor
# timing, not merely tutor target choice.
CONFIRM = {
    (19, 17): ("Use Mystical Tutor", "End turn 4"),
    (19, 19): (
        "Mystical Tutor -> Transmute Artifact",
        "Mystical Tutor -> Sea Gate Restoration",
        "Mystical Tutor -> Reshape",
        "Mystical Tutor -> Whir of Invention",
    ),
    (20, 59): (
        "Use Spellseeker",
        "Cast Reshape X=1; sacrifice The Reality Chip",
        "Cast Reshape X=1; sacrifice Grinding Station",
        "Cast Reshape X=0; sacrifice Construct",
    ),
    (20, 62): (
        "Spellseeker -> Banishing Knack",
        "Spellseeker -> Transmute Artifact",
        "Spellseeker -> Chain of Vapor",
    ),
    (21, 34): ("Cast Transmute Artifact", "End turn 4"),
    (21, 37): (
        "Find Grinding Station",
        "Find Uthros Research Craft",
        "Find Grim Monolith",
    ),
    (21, 87): (
        "Cast Whir X=0",
        "Cast Whir X=2; improvise Chrome Mox, Mox Diamond",
        "Cast Whir X=2; improvise Chrome Mox, Construct",
        "Cast Whir X=3; improvise Chrome Mox, Construct, Mox Diamond",
    ),
    (21, 89): ("Find Everflowing Chalice", "Find Jeweled Amulet"),
    (24, 6): ("Use Mystical Tutor", "End turn 1"),
    (24, 8): (
        "Mystical Tutor -> Transmute Artifact",
        "Mystical Tutor -> Sea Gate Restoration",
        "Mystical Tutor -> Reshape",
        "Mystical Tutor -> Whir of Invention",
    ),
    (25, 30): ("Cast Transmute Artifact", "End turn 4"),
    (25, 33): (
        "Find The Reality Chip",
        "Find Sewer-veillance Cam",
        "Find Grim Monolith",
        "Find Mox Opal",
    ),
    (25, 55): ("Find Chrome Mox", "Find Everflowing Chalice"),
    (27, 43): ("Cast Transmute Artifact", "End turn 5"),
    (27, 46): ("Find Grim Monolith", "Find Basalt Monolith"),
    (27, 47): (
        "Pay 1 via Urza taps Construct: +U",
        "Pay 1 via tap Island: +U",
        "Decline 1; target to graveyard",
    ),
}
SELECTED = tuple(sorted({hand for hand, _ in CONFIRM}))


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


def value_json(value):
    return {
        "win_probability": value.win_probability,
        "exact_win": list(value.exact_win),
        "no_win": value.no_win,
        "win_families": [[name, mass] for name, mass in value.win_families],
        "comparison_key": list(value.comparison_key()),
    }


def run_hand(root, *, hand_id, policy, evaluator):
    runtime = _checked_runtime(root)
    attempted_by_cycle_state = {}
    rows = []

    for sequence in range(MAX_STEPS):
        state = runtime.true_state
        if state.won or state.turn > HORIZON:
            break

        request = rules_decision_request(
            runtime,
            horizon=HORIZON,
            policy_id=policy.policy_id,
        )
        if not request.actions:
            break

        cycle_key = episode_cycle_key(runtime)
        attempted = attempted_by_cycle_state.setdefault(cycle_key, set())
        fresh = tuple(
            action for action in request.actions
            if action.strategic_key() not in attempted
        )
        if not fresh:
            break

        chosen = policy.choose(request.observation, fresh, request.context)
        wanted = CONFIRM.get((int(hand_id), sequence))
        if wanted and len(fresh) == len(request.actions):
            by_label = {action.label: action for action in fresh}
            missing = [label for label in wanted if label not in by_label]
            present = [label for label in wanted if label in by_label]
            if len(present) < 2:
                rows.append({
                    "sequence": sequence,
                    "turn": int(state.turn),
                    "v6_chosen": chosen.label,
                    "q_best": None,
                    "q_disagrees": None,
                    "rollouts_per_candidate": 0,
                    "missing_candidates": missing,
                    "available_candidates": sorted(by_label),
                    "estimates": [],
                })
                candidates = ()
            else:
                candidates = tuple(by_label[label] for label in present)
            if candidates:
                q = evaluator.evaluate(runtime, candidate_actions=candidates)
                rows.append({
                    "sequence": sequence,
                    "turn": int(state.turn),
                    "v6_chosen": chosen.label,
                    "q_best": q.best_action.label,
                    "q_disagrees": q.best_action.strategic_key() != chosen.strategic_key(),
                    "rollouts_per_candidate": q.rollout_count_per_action,
                    "missing_candidates": missing,
                    "available_candidates": sorted(by_label),
                    "estimates": [
                    {
                        "label": estimate.action.label,
                        "value": value_json(estimate.value),
                        "terminal_reasons": list(estimate.terminal_reason_counts),
                        "wilson95": list(estimate.win_probability_wilson95),
                    }
                        for estimate in q.estimates
                    ],
                })

        attempted.add(chosen.strategic_key())
        runtime = _checked_runtime(apply_main_action(runtime, chosen))

    return rows


def main():
    deck = load_deck()
    fixture = json.loads(
        Path("benchmarks/human/human_mulligan_exact_hands.json").read_text(
            encoding="utf-8"
        )
    )
    by_id = {int(row["hand_id"]): row for row in fixture["hands"]}
    policy = DeterministicRolloutPolicyV6(policy_id=PHASE5_ROLLOUT_POLICY_V6)
    evaluator = Phase5MonteCarloDecisionEvaluator(
        rollout_count=ROLLOUTS,
        mc_root_seed=20260826,
        horizon=HORIZON,
        continuation_policy=policy,
        strict_terminal_reasons=True,
    )

    hands = []
    for hand_id in SELECTED:
        row = by_id[hand_id]
        seven = tuple(row["drawn_seven"])
        bottom = tuple(row["cards_bottomed"])
        root = opening_runtime(deck, seven, bottom)
        world = _opening_world(
            deck=deck,
            seven=seven,
            bottom=bottom,
            mc_root_seed=20260826,
            sample_id=0,
        )
        sampled = materialize_hidden_world(root, world)
        validate_information_against_state(sampled.information, sampled.true_state)
        confirmations = run_hand(
            sampled,
            hand_id=hand_id,
            policy=policy,
            evaluator=evaluator,
        )
        hands.append({"hand_id": hand_id, "confirmations": confirmations})

    # These coordinates are diagnostic reproductions, not correctness gates.
    # New terminal recognizers or earlier draws can legitimately end a trajectory
    # before an old coordinate or remove a candidate from the library. Preserve
    # those changes in the artifact instead of failing CI on historical path drift.
    expected = set(CONFIRM)
    seen = {
        (row["hand_id"], confirmation["sequence"])
        for row in hands for confirmation in row["confirmations"]
    }
    path_drift = sorted(expected-seen)

    payload = {
        "kind": "phase5-tutor-q-confirmation",
        "rollouts_per_candidate": ROLLOUTS,
        "mc_root_seed": 20260826,
        "continuation_policy_id": policy.policy_id,
        "hands": hands,
        "path_drift": path_drift,
    }
    Path("phase5_tutor_q_confirm.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        row["hand_id"]: [
            {
                "sequence": x["sequence"],
                "v6": x["v6_chosen"],
                "q": x["q_best"],
                "disagrees": x["q_disagrees"],
            }
            for x in row["confirmations"]
        ]
        for row in hands
    }, indent=2))


if __name__ == "__main__":
    main()
