#!/usr/bin/env python3
"""Deterministic information-constrained base policy for Phase 2.

This policy is intentionally simple.  Its job is to provide one legal continuation
strategy that Monte Carlo/DP can later evaluate and improve.  It is NOT intended to
encode an Oracle search in heuristics.

Hard boundary: ``choose`` accepts RuntimePolicyView + ActionIntent objects only.
There is no raw State parameter, no concrete library, and no root game RNG seed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

import urza_solver as solver
from decision_observation import ActionIntent, PolicyDecisionContext
from non_oracle_runtime_view import RuntimePolicyView

BASE_POLICY_VERSION = "urza-deterministic-base-v1"

COMBO_CORE = frozenset({
    "Power Artifact","Basalt Monolith","Grim Monolith","Sensei's Divining Top",
    "The Reality Chip","Fortune Teller's Talent","Forensic Gadgeteer",
    "Grinding Station","Battered Golem","Sewer-veillance Cam",
    "Banishing Knack","Retraction Helix",
})
TUTOR_CORE = frozenset({
    "Mystical Tutor","Merchant Scroll","Spellseeker","Dizzy Spell",
    "Muddle the Mixture","Reshape","Transmute Artifact","Whir of Invention",
    "Repurposing Bay","Urza's Saga",
})
FAST_MANA = frozenset({
    "Mana Crypt","Sol Ring","Mana Vault","Mox Opal","Mox Amber","Chrome Mox",
    "Mox Diamond","Lotus Petal","Grim Monolith","Basalt Monolith",
    "Everflowing Chalice",
})
CARD_ADVANTAGE = frozenset({
    "Mystic Remora","Rhystic Study","The One Ring","Faerie Mastermind",
    "Uthros Research Craft",
})


@dataclass(frozen=True)
class DeterministicBasePolicy:
    policy_id: str = BASE_POLICY_VERSION

    def visible_card_score(self, card: str, observation: RuntimePolicyView) -> float:
        """Coarse value using only visible card identity + visible resources."""
        score = 0.0
        if card in COMBO_CORE:
            score += 5.0
        if card in TUTOR_CORE:
            score += 4.0
        if card in FAST_MANA:
            score += 3.0
        if card in CARD_ADVANTAGE:
            score += 2.0
        if card in getattr(solver, "ALL_LANDS", frozenset()):
            score += 2.0 if not observation.base.land_played else 0.5
            if observation.base.blue + observation.base.colorless == 0:
                score += 1.0
        if card in getattr(solver, "INTERACTION_CARDS", frozenset()):
            score += 1.0
        return score

    @staticmethod
    def _ordered_kinds(action: ActionIntent) -> Tuple[str, ...]:
        marker = "Resolve: "
        if marker not in action.label:
            return ()
        return tuple(piece.strip() for piece in action.label.split(marker, 1)[1].split(" -> "))

    def _stack_order_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        order = self._ordered_kinds(action)
        if not order:
            return 0.0
        base_priority = {
            "uthros_draw_and_counter": 7.0,
            "assistant_scry_1": 6.0,
            "gadgeteer_investigate": 5.5,
            "prized_entry_treasure": 5.0,
            "prized_dies_treasure": 5.0,
            "etb_scry_2": 4.5,
            "vfc_noncreature_cast": 4.0,
            "etb_tezz": 3.0,
            "etb_producer": 2.0,
            "chrome_imprint": 1.5,
            "vexing_bauble_counter": -10.0,
        }
        n = len(order)
        score = sum(base_priority.get(kind, 0.0) * (n - i) for i, kind in enumerate(order))

        if "uthros_draw_and_counter" in order and "assistant_scry_1" in order:
            known = observation.base.known_top
            known_value = self.visible_card_score(known[0], observation) if known else 0.0
            u = order.index("uthros_draw_and_counter")
            a = order.index("assistant_scry_1")
            if known and known_value >= 3.0:
                score += 25.0 if u < a else -25.0
            else:
                score += 25.0 if a < u else -25.0

        if "vexing_bauble_counter" in order:
            score += 15.0 if order[-1] == "vexing_bauble_counter" else -15.0
        return score

    def _scry_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        params = dict(action.parameters)
        top = tuple(params.get("top", ()))
        bottom = tuple(params.get("bottom", ()))
        if not isinstance(top, tuple) or not isinstance(bottom, tuple):
            return 0.0
        score = 0.0
        for index, card in enumerate(top):
            value = self.visible_card_score(str(card), observation)
            score += value * (3.0 / (index + 1))
            if value == 0.0:
                score -= 0.25
        for card in bottom:
            value = self.visible_card_score(str(card), observation)
            score += 0.5 if value == 0.0 else -1.5 * value
        return score

    def _chrome_imprint_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        card = str(dict(action.parameters).get("card", ""))
        if not card:
            return 0.0
        card_cost = self.visible_card_score(card, observation)
        mana = observation.base.blue + observation.base.colorless
        return (3.0 - card_cost) if mana <= 1 else (-1.0 - card_cost)

    def _main_action_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        params = dict(action.parameters)
        if action.kind == "main_cast_commander":
            # Urza is the engine enabling artifact mana, Construct lines, and the
            # eventual win recognizers.  Once legally payable, prioritize him over
            # discretionary development spells without needing hidden information.
            return 35.0
        if action.kind == "main_play_land":
            return 30.0 + self.visible_card_score(str(params.get("card", "")), observation)
        if action.kind == "main_cast_artifact":
            return 20.0 + self.visible_card_score(str(params.get("card", "")), observation)
        if action.kind == "main_mana_action":
            gain = max(0, int(params.get("blue_delta", 0))) + max(
                0, int(params.get("colorless_delta", 0))
            )
            return 10.0 + 2.0 * gain
        if action.kind == "main_end_turn":
            return -100.0
        return 0.0

    def action_score(
        self,
        observation: RuntimePolicyView,
        action: ActionIntent,
        context: PolicyDecisionContext,
    ) -> float:
        kind = action.kind
        if kind == "runtime_stack_order":
            return self._stack_order_score(observation, action)
        if kind == "runtime_producer_untap":
            return 5.0 if dict(action.parameters).get("choice") == "untap" else 0.0
        if kind in {"runtime_scry_choice", "scry_choose_positions"}:
            return self._scry_score(observation, action)
        if kind == "runtime_chrome_imprint":
            return self._chrome_imprint_score(observation, action)
        if kind == "pass_priority":
            return 0.0
        if kind.startswith("main_"):
            return self._main_action_score(observation, action)
        return 0.0

    def choose(
        self,
        observation: RuntimePolicyView,
        actions: Sequence[ActionIntent],
        context: PolicyDecisionContext,
    ) -> ActionIntent:
        if not actions:
            raise ValueError("base policy cannot choose from an empty action set")
        ranked = sorted(
            actions,
            key=lambda action: (
                -self.action_score(observation, action, context),
                repr(action.strategic_key()),
                action.action_id,
            ),
        )
        return ranked[0]

    def choose_request(self, request) -> ActionIntent:
        return self.choose(request.observation, request.actions, request.context)
