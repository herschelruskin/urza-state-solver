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
from typing import Iterable, Sequence, Tuple

import urza_solver as solver
from decision_observation import ActionIntent, PolicyDecisionContext
from non_oracle_runtime_view import RuntimePolicyView

BASE_POLICY_VERSION = "urza-deterministic-base-v1"

# Transparent, intentionally coarse static priorities.  These are only rollout
# heuristics; future DP/MC replaces their judgment without changing rules.
COMBO_CORE = frozenset({
    "Power Artifact",
    "Basalt Monolith",
    "Grim Monolith",
    "Sensei's Divining Top",
    "The Reality Chip",
    "Fortune Teller's Talent",
    "Forensic Gadgeteer",
    "Grinding Station",
    "Battered Golem",
    "Sewer-veillance Cam",
    "Banishing Knack",
    "Retraction Helix",
})
TUTOR_CORE = frozenset({
    "Mystical Tutor",
    "Merchant Scroll",
    "Spellseeker",
    "Dizzy Spell",
    "Muddle the Mixture",
    "Reshape",
    "Transmute Artifact",
    "Whir of Invention",
    "Repurposing Bay",
    "Urza's Saga",
})
FAST_MANA = frozenset({
    "Mana Crypt",
    "Sol Ring",
    "Mana Vault",
    "Mox Opal",
    "Mox Amber",
    "Chrome Mox",
    "Mox Diamond",
    "Lotus Petal",
    "Grim Monolith",
    "Basalt Monolith",
    "Everflowing Chalice",
})
CARD_ADVANTAGE = frozenset({
    "Mystic Remora",
    "Rhystic Study",
    "The One Ring",
    "Faerie Mastermind",
    "Uthros Research Craft",
})


@dataclass(frozen=True)
class DeterministicBasePolicy:
    policy_id: str = BASE_POLICY_VERSION

    def visible_card_score(self, card: str, observation: RuntimePolicyView) -> float:
        """Coarse value using only the visible card identity + visible resources."""
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
            # Lands matter more before the land drop and when current floating
            # resources are low.  This is visible public state.
            score += 2.0 if not observation.base.land_played else 0.5
            if observation.base.blue + observation.base.colorless == 0:
                score += 1.0
        if card in getattr(solver, "INTERACTION_CARDS", frozenset()):
            score += 1.0
        return score

    @staticmethod
    def _ordered_kinds(action: ActionIntent) -> Tuple[str, ...]:
        label = action.label
        marker = "Resolve: "
        if marker not in label:
            return ()
        return tuple(piece.strip() for piece in label.split(marker, 1)[1].split(" -> "))

    def _stack_order_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        order = self._ordered_kinds(action)
        if not order:
            return 0.0
        score = 0.0

        # Prefer value/information triggers above pure untap triggers by default.
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
        for index, kind in enumerate(order):
            score += base_priority.get(kind, 0.0) * (n - index)

        # The only place this policy deliberately conditions Assistant/Uthros
        # order is on a LEGALLY KNOWN top card.  Unknown top => scry first.
        if "uthros_draw_and_counter" in order and "assistant_scry_1" in order:
            known = observation.base.known_top
            known_value = self.visible_card_score(known[0], observation) if known else 0.0
            u = order.index("uthros_draw_and_counter")
            a = order.index("assistant_scry_1")
            if known and known_value >= 3.0:
                score += 25.0 if u < a else -25.0
            else:
                score += 25.0 if a < u else -25.0

        # If Bauble is going to counter our zero-mana spell, resolve other value
        # triggers first when possible.
        if "vexing_bauble_counter" in order:
            score += 15.0 if order[-1] == "vexing_bauble_counter" else -15.0
        return score

    def _scry_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        params = dict(action.parameters)
        top = tuple(params.get("top", ()))
        bottom = tuple(params.get("bottom", ()))
        if not isinstance(top, tuple) or not isinstance(bottom, tuple):
            return 0.0

        # Prefer valuable cards on top, with earlier positions weighted more.
        score = 0.0
        for index, card in enumerate(top):
            value = self.visible_card_score(str(card), observation)
            score += value * (3.0 / (index + 1))
            # Neutral filler is slightly undesirable to keep when bottoming is free.
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
        # When mana-starved, imprinting a low-value visible card is useful; with
        # adequate mana, preserve cards unless later DP/MC proves otherwise.
        return (3.0 - card_cost) if mana <= 1 else (-1.0 - card_cost)

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
        if kind == "runtime_scry_choice" or kind == "scry_choose_positions":
            return self._scry_score(observation, action)
        if kind == "runtime_chrome_imprint":
            return self._chrome_imprint_score(observation, action)
        if kind == "pass_priority":
            return 0.0
        # Unknown future action families remain deterministic rather than silently
        # consulting Oracle state.  As Phase 2 adds main-phase actions, they get
        # explicit visible-feature scoring here.
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
