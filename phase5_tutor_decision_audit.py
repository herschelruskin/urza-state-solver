#!/usr/bin/env python3
"""Policy-safe audit of tutor timing and target selection on held-out hands.

The audit sees exactly what the deterministic policy sees: RuntimePolicyView,
ActionIntent, and PolicyDecisionContext. It never reads the concrete hidden library
or root RNG when recording/scoring a decision.
"""

from __future__ import annotations

import json
from pathlib import Path

from decision_observation import PolicyDecisionContext
from information_state_propagation import validate_information_against_state
from non_oracle_episode import run_deterministic_episode
from phase4_hidden_world import materialize_hidden_world
from phase5_mulligan import _opening_world, opening_runtime
from phase5_rollout_policy_v6 import (
    DeterministicRolloutPolicyV6,
    PHASE5_ROLLOUT_POLICY_V6,
)

SELECTED = (12, 13, 19, 20, 21, 24, 25, 27, 29, 33)

TUTOR_CARDS = frozenset({
    "Mystical Tutor", "Merchant Scroll", "Spellseeker", "Dizzy Spell",
    "Muddle the Mixture", "Reshape", "Transmute Artifact", "Whir of Invention",
    "Repurposing Bay", "Scour for Scrap", "Tezzeret, Cruel Captain",
})

TUTOR_DECISION_KINDS = frozenset({
    "main_use_simple_tutor",
    "main_use_transmute_artifact",
    "main_use_x_artifact_tutor",
    "main_activate_repurposing_bay",
    "main_cast_scour_for_scrap",
    "main_activate_tezzeret_minus3",
    "choose_tutor_target",
    "transmute_choose_sacrifice",
    "transmute_choose_target",
    "transmute_pay_difference",
    "x_artifact_search_target",
    "remaining_search_target",
})


def _jsonable(value):
    if isinstance(value, tuple):
        return [_jsonable(x) for x in value]
    if isinstance(value, list):
        return [_jsonable(x) for x in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


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


class TutorAuditPolicy(DeterministicRolloutPolicyV6):
    def __init__(self):
        super().__init__(policy_id=PHASE5_ROLLOUT_POLICY_V6)
        object.__setattr__(self, "audit_rows", [])

    def choose(self, observation, actions, context: PolicyDecisionContext):
        chosen = super().choose(observation, actions, context)
        hand = tuple(observation.base.hand)
        tutor_in_hand = tuple(sorted(card for card in hand if card in TUTOR_CARDS))
        relevant = bool(tutor_in_hand) or any(
            action.kind in TUTOR_DECISION_KINDS for action in actions
        )
        if relevant:
            ranked = sorted(
                actions,
                key=lambda action: (
                    -self.action_score(observation, action, context),
                    repr(action.strategic_key()),
                    action.action_id,
                ),
            )
            rows = []
            for action in ranked:
                rows.append({
                    "action_id": action.action_id,
                    "kind": action.kind,
                    "label": action.label,
                    "score": self.action_score(observation, action, context),
                    "parameters": _jsonable(dict(action.parameters)),
                    "chosen": action.canonical_key() == chosen.canonical_key(),
                })
            self.audit_rows.append({
                "turn": int(observation.base.turn),
                "decision_id": context.decision_id,
                "decision_stage": context.decision_stage,
                "hand": list(hand),
                "battlefield": [
                    {
                        "name": perm.name,
                        "tapped": bool(perm.tapped),
                        "counters": int(perm.counters),
                        "mode": perm.mode,
                        "knack_granted": bool(perm.knack_granted),
                    }
                    for perm in observation.base.battlefield
                ],
                "blue": int(observation.base.blue),
                "colorless": int(observation.base.colorless),
                "known_top": list(observation.base.known_top),
                "tutors_in_hand": list(tutor_in_hand),
                "chosen": {
                    "action_id": chosen.action_id,
                    "kind": chosen.kind,
                    "label": chosen.label,
                    "score": self.action_score(observation, chosen, context),
                    "parameters": _jsonable(dict(chosen.parameters)),
                },
                "actions": rows,
            })
        return chosen


def main():
    deck = load_deck()
    fixture = json.loads(
        Path("benchmarks/human/human_mulligan_exact_hands.json").read_text(
            encoding="utf-8"
        )
    )
    by_id = {int(row["hand_id"]): row for row in fixture["hands"]}
    output = []

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

        policy = TutorAuditPolicy()
        result = run_deterministic_episode(
            sampled,
            horizon=6,
            max_steps=512,
            policy=policy,
        )
        output.append({
            "hand_id": hand_id,
            "win_turn": result.win_turn,
            "win_family": result.win_family,
            "terminal_reason": result.terminal_reason,
            "final_tutors_in_hand": sorted(
                card for card in result.runtime.true_state.hand if card in TUTOR_CARDS
            ),
            "audit": policy.audit_rows,
        })

    payload = {
        "kind": "phase5-tutor-decision-audit",
        "policy_id": PHASE5_ROLLOUT_POLICY_V6,
        "selected_hands": list(SELECTED),
        "horizon": 6,
        "hands": output,
    }
    Path("phase5_tutor_decision_audit.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        row["hand_id"]: {
            "win_turn": row["win_turn"],
            "audit_decisions": len(row["audit"]),
            "final_tutors_in_hand": row["final_tutors_in_hand"],
        }
        for row in output
    }, indent=2))


if __name__ == "__main__":
    main()
