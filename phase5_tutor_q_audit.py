#!/usr/bin/env python3
"""Offline Q audit for tutor timing/targets on held-out human-kept hands.

The played trajectory remains frozen to rollout-v6. At tutor-relevant decisions,
this diagnostic separately estimates Q(s,a) for the visible competing actions using
common hidden worlds and rollout-v6 as the leaf/continuation policy. Thus it can
identify bad tutor timing/target choices without changing the trajectory used to
locate those states.

No actual hidden-library order is supplied to the choice comparison.
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import urza_solver as solver
from information_state_propagation import validate_information_against_state
from non_oracle_episode import (
    EpisodeStep,
    NonOracleEpisodeResult,
    _checked_runtime,
    _blocked_reason,
    episode_cycle_key,
)
from non_oracle_rules_adapter_v2 import apply_main_action, rules_decision_request
from phase4_hidden_world import materialize_hidden_world
from phase5_monte_carlo import Phase5MonteCarloDecisionEvaluator
from phase5_mulligan import _opening_world, opening_runtime
from phase5_rollout_policy_v6 import (
    DeterministicRolloutPolicyV6,
    PHASE5_ROLLOUT_POLICY_V6,
)

SELECTED = (19, 20, 21, 24, 25, 27)
HORIZON = 6
MAX_STEPS = 512
ROLLOUTS = 4

MAIN_TUTOR_KINDS = frozenset({
    "main_use_simple_tutor",
    "main_use_transmute_artifact",
    "main_use_x_artifact_tutor",
    "main_activate_repurposing_bay",
    "main_cast_scour_for_scrap",
    "main_activate_tezzeret_minus3",
})
TUTOR_DECISION_KINDS = frozenset({
    "choose_tutor_target",
    "transmute_choose_sacrifice",
    "transmute_choose_target",
    "transmute_pay_difference",
    "x_artifact_search_target",
    "remaining_search_target",
})


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


def _value_json(value):
    return {
        "win_probability": value.win_probability,
        "exact_win": list(value.exact_win),
        "no_win": value.no_win,
        "cumulative": [[turn, value.win_by(turn)] for turn in range(1, value.horizon + 1)],
        "win_families": [[name, mass] for name, mass in value.win_families],
        "comparison_key": list(value.comparison_key()),
    }


def _candidate_subset(policy, request, fresh_actions):
    kinds = {action.kind for action in fresh_actions}
    if kinds & TUTOR_DECISION_KINDS:
        # A post-search/commitment choice: compare the complete visible choice set.
        return tuple(fresh_actions), "complete_tutor_decision"

    tutor_actions = tuple(action for action in fresh_actions if action.kind in MAIN_TUTOR_KINDS)
    if not tutor_actions:
        return (), ""

    chosen = policy.choose(request.observation, fresh_actions, request.context)
    by_key = {action.strategic_key(): action for action in tutor_actions}
    by_key.setdefault(chosen.strategic_key(), chosen)
    return tuple(by_key[key] for key in sorted(by_key, key=repr)), "tutor_vs_v6_choice"


def run_hand(root, *, policy, evaluator):
    runtime = _checked_runtime(root)
    attempted_by_cycle_state = {}
    steps = []
    audit = []

    for sequence in range(MAX_STEPS):
        state = runtime.true_state
        if state.won:
            return NonOracleEpisodeResult(
                runtime, tuple(steps), HORIZON, int(state.turn), state.win_family, "win"
            ), audit
        if state.turn > HORIZON:
            return NonOracleEpisodeResult(
                runtime, tuple(steps), HORIZON, None, "", "horizon"
            ), audit

        request = rules_decision_request(
            runtime,
            horizon=HORIZON,
            policy_id=policy.policy_id,
        )
        if not request.actions:
            return NonOracleEpisodeResult(
                runtime, tuple(steps), HORIZON, None, "",
                _blocked_reason(runtime, HORIZON),
            ), audit

        cycle_key = episode_cycle_key(runtime)
        attempted = attempted_by_cycle_state.setdefault(cycle_key, set())
        fresh = tuple(
            action for action in request.actions
            if action.strategic_key() not in attempted
        )
        if not fresh:
            return NonOracleEpisodeResult(
                runtime, tuple(steps), HORIZON, None, "", "strategic_cycle_exhausted"
            ), audit

        chosen = policy.choose(request.observation, fresh, request.context)
        candidates, audit_kind = _candidate_subset(policy, request, fresh)

        if candidates and len(fresh) == len(request.actions):
            q = evaluator.evaluate(runtime, candidate_actions=candidates)
            static_est = next(
                estimate for estimate in q.estimates
                if estimate.action.strategic_key() == chosen.strategic_key()
            )
            audit.append({
                "sequence": sequence,
                "turn": int(state.turn),
                "audit_kind": audit_kind,
                "decision_id": request.context.decision_id,
                "decision_stage": request.context.decision_stage,
                "hand": list(request.observation.base.hand),
                "battlefield": [perm.name for perm in request.observation.base.battlefield],
                "blue": int(request.observation.base.blue),
                "colorless": int(request.observation.base.colorless),
                "v6_chosen": chosen.label,
                "q_best": q.best_action.label,
                "q_disagrees": q.best_action.strategic_key() != chosen.strategic_key(),
                "v6_value": _value_json(static_est.value),
                "estimates": [
                    {
                        "label": estimate.action.label,
                        "kind": estimate.action.kind,
                        "value": _value_json(estimate.value),
                        "terminal_reasons": list(estimate.terminal_reason_counts),
                    }
                    for estimate in q.estimates
                ],
            })

        attempted.add(chosen.strategic_key())
        before_turn = int(state.turn)
        before_window = runtime.window.kind
        observation_key = request.observation.key()
        runtime = apply_main_action(runtime, chosen)
        runtime = _checked_runtime(runtime)
        after = runtime.true_state
        steps.append(EpisodeStep(
            sequence=sequence,
            turn_before=before_turn,
            window_kind=before_window,
            observation_key=observation_key,
            action_id=chosen.action_id,
            action_kind=chosen.kind,
            action_label=chosen.label,
            action_strategic_key=chosen.strategic_key(),
            turn_after=int(after.turn),
            won_after=bool(after.won),
            win_family_after=str(after.win_family),
        ))

    return NonOracleEpisodeResult(
        runtime,
        tuple(steps),
        HORIZON,
        int(runtime.true_state.turn) if runtime.true_state.won else None,
        runtime.true_state.win_family if runtime.true_state.won else "",
        "step_limit",
    ), audit


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

    rows = []
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
        result, q_audit = run_hand(sampled, policy=policy, evaluator=evaluator)
        rows.append({
            "hand_id": hand_id,
            "win_turn": result.win_turn,
            "win_family": result.win_family,
            "terminal_reason": result.terminal_reason,
            "q_audit": q_audit,
        })

    payload = {
        "kind": "phase5-tutor-q-audit",
        "rollouts_per_candidate": ROLLOUTS,
        "mc_root_seed": 20260826,
        "continuation_policy_id": policy.policy_id,
        "hands": rows,
    }
    Path("phase5_tutor_q_audit.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = {}
    for row in rows:
        summary[row["hand_id"]] = {
            "win_turn": row["win_turn"],
            "q_decisions": len(row["q_audit"]),
            "q_disagreements": sum(x["q_disagrees"] for x in row["q_audit"]),
        }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
