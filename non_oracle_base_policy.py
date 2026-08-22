#!/usr/bin/env python3
"""Deterministic information-constrained base policy for Phase 2.

This policy is intentionally simple. Its job is to provide one legal continuation
strategy that Monte Carlo/DP can later evaluate and improve. It is NOT intended to
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
    "Repurposing Bay","Urza's Saga","Scour for Scrap",
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

CHROME_TARGET_PRIORITY = {
    "Grinding Station": 100.0,
    "Battered Golem": 96.0,
    "Mana Vault": 93.0,
    "Grim Monolith": 91.0,
    "Basalt Monolith": 89.0,
    "Forensic Gadgeteer": 86.0,
    "Sol Ring": 82.0,
    "Prized Statue": 74.0,
    "Voltaic Key": 70.0,
    "Manifold Key": 69.0,
    "Sewer-veillance Cam": 62.0,
    "The One Ring": 58.0,
}
CAM_TARGET_PRIORITY = {
    "Battered Golem": 100.0,
    "Grinding Station": 96.0,
    "Forensic Gadgeteer": 90.0,
    "Valley Floodcaller": 82.0,
    "Artificer's Assistant": 78.0,
    "Spellseeker": 72.0,
    "The Reality Chip": 68.0,
    "Chrome Dome": 64.0,
}
KEY_TARGET_PRIORITY = {
    "Mana Vault": 100.0,
    "Grim Monolith": 96.0,
    "Basalt Monolith": 94.0,
    "Sol Ring": 76.0,
    "Grinding Station": 72.0,
    "The One Ring": 58.0,
    "Sewer-veillance Cam": 50.0,
    "Sensei's Divining Top": 45.0,
    "Uthros Research Craft": 40.0,
    "Everflowing Chalice": 38.0,
    "Mox Opal": 35.0,
    "Mox Diamond": 35.0,
    "Chrome Mox": 35.0,
    "Voltaic Key": -100.0,
    "Manifold Key": -100.0,
}
DRAW_ACTIVATION_PRIORITY = {
    "activated_one_ring_draw": 38.0,
    "activated_bauble_delayed_draw": 31.0,
    "activated_vexing_bauble_draw": 28.0,
    "activated_clue_draw": 22.0,
    "activated_aether_spellbomb_draw": 21.0,
    "activated_witching_well_draw": 18.0,
    "activated_cam_draw_two": 17.0,
}


@dataclass(frozen=True)
class DeterministicBasePolicy:
    policy_id: str = BASE_POLICY_VERSION

    def visible_card_score(self, card: str, observation: RuntimePolicyView) -> float:
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
            "etb_cam": 4.25,
            "ltb_cam": 4.25,
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

    def _top_reorder_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        order = tuple(dict(action.parameters).get("order", ()))
        if not order:
            return 0.0
        return sum(
            self.visible_card_score(str(card), observation) * (4.0 / (index + 1))
            for index, card in enumerate(order)
        )

    def _chrome_imprint_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        card = str(dict(action.parameters).get("card", ""))
        if not card:
            return 0.0
        card_cost = self.visible_card_score(card, observation)
        mana = observation.base.blue + observation.base.colorless
        return (3.0 - card_cost) if mana <= 1 else (-1.0 - card_cost)

    def _mox_diamond_entry_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        land = str(dict(action.parameters).get("land", ""))
        if not land:
            return -100.0
        return 30.0 - self.visible_card_score(land, observation)

    def _tutor_target_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        target = str(dict(action.parameters).get("target", ""))
        if not target:
            return -100.0
        return 20.0 + self.visible_card_score(target, observation)

    def _transmute_sacrifice_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        signature = tuple(dict(action.parameters).get("signature", ()))
        name = str(signature[0]) if signature else ""
        score = -self.visible_card_score(name, observation)
        if name == "Prized Statue":
            score += 4.0
        return score

    @staticmethod
    def _transmute_payment_score(action: ActionIntent) -> float:
        params = dict(action.parameters)
        if params.get("choice") == "decline":
            return -50.0
        steps = tuple(params.get("mana_steps", ()))
        return 15.0 - float(len(steps))

    @staticmethod
    def _cam_target_score(action: ActionIntent) -> float:
        signature = tuple(dict(action.parameters).get("target_signature", ()))
        name = str(signature[0]) if signature else ""
        tapped = bool(signature[1]) if len(signature) > 1 else False
        return CAM_TARGET_PRIORITY.get(name, 40.0) + (12.0 if tapped else 0.0)

    @staticmethod
    def _cam_effect_score(action: ActionIntent) -> float:
        choice = str(dict(action.parameters).get("choice", "decline"))
        return {"untap": 20.0, "decline": 2.0, "tap": 0.0}.get(choice, -10.0)

    def _chrome_endstep_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        params = dict(action.parameters)
        target = str(params.get("target_name", ""))
        if not target:
            return 0.0
        return 30.0 + CHROME_TARGET_PRIORITY.get(
            target,
            20.0 + 4.0 * self.visible_card_score(target, observation),
        ) / 10.0

    @staticmethod
    def _draw_activation_score(action: ActionIntent) -> float:
        params = dict(action.parameters)
        kind = str(params.get("ability_kind", ""))
        base = DRAW_ACTIVATION_PRIORITY.get(kind, 0.0)
        # Expensive draw engines should not outrank an available tutor simply
        # because they draw two; their base priorities already account for tempo.
        return base

    def _main_action_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        params = dict(action.parameters)
        if action.kind == "main_cast_commander":
            return 35.0
        if action.kind == "main_play_land":
            return 30.0 + self.visible_card_score(str(params.get("card", "")), observation)
        if action.kind == "main_cast_gitaxian_probe":
            return -20.0 if bool(params.get("will_be_countered_by_own_bauble", False)) else 40.0
        if action.kind == "main_draw_activation":
            return self._draw_activation_score(action)
        if action.kind == "main_use_transmute_artifact":
            return 33.0
        if action.kind == "main_activate_repurposing_bay":
            target_mv = int(params.get("target_mv", 0))
            mv_value = 4.0 - abs(target_mv - 2.5)
            sacrificed = str(params.get("sacrifice_name", ""))
            sacrifice_penalty = 0.5 * self.visible_card_score(sacrificed, observation)
            if sacrificed == "Prized Statue":
                sacrifice_penalty -= 2.0
            return 30.0 + mv_value - sacrifice_penalty
        if action.kind == "main_cast_scour_for_scrap":
            mode = str(params.get("mode", ""))
            grave = str(params.get("graveyard_target", ""))
            mode_bonus = {"both": 5.0, "library": 3.0, "graveyard": 1.0}.get(mode, 0.0)
            return 29.0 + mode_bonus + 0.25 * self.visible_card_score(grave, observation)
        if action.kind == "main_activate_tezzeret_minus3":
            return 28.0
        if action.kind == "main_use_x_artifact_tutor":
            x = int(params.get("x", 0))
            x_score = 4.5 - 1.5 * abs(x - 3)
            sacrificed = str(params.get("sacrifice_name", ""))
            sacrifice_penalty = 0.5 * self.visible_card_score(sacrificed, observation) if sacrificed else 0.0
            return 28.0 + x_score - sacrifice_penalty
        if action.kind == "main_use_simple_tutor":
            return 27.0 + self.visible_card_score(str(params.get("source", "")), observation)
        if action.kind == "main_cast_proactive_nonartifact":
            return 24.0 + self.visible_card_score(str(params.get("card", "")), observation)
        if action.kind == "main_cast_utility_artifact":
            card = str(params.get("card", ""))
            if card == "Mox Diamond":
                return 26.0
            if card == "Everflowing Chalice":
                kicks = int(params.get("kicks", 0))
                return 23.0 if kicks == 1 else (15.0 if kicks == 0 else 18.0 - 0.5 * kicks)
            return 18.0
        if action.kind == "main_activate_key":
            target = str(params.get("target_name", ""))
            return 24.0 + KEY_TARGET_PRIORITY.get(target, -100.0) / 10.0
        if action.kind == "main_activate_top":
            return 17.0
        if action.kind == "main_cast_artifact":
            return 20.0 + self.visible_card_score(str(params.get("card", "")), observation)
        if action.kind == "main_mana_action":
            gain = max(0, int(params.get("blue_delta", 0))) + max(0, int(params.get("colorless_delta", 0)))
            return 10.0 + 2.0 * gain
        if action.kind == "main_end_turn":
            return -100.0
        return 0.0

    def action_score(self, observation: RuntimePolicyView, action: ActionIntent, context: PolicyDecisionContext) -> float:
        kind = action.kind
        if kind == "runtime_stack_order":
            return self._stack_order_score(observation, action)
        if kind == "runtime_producer_untap":
            return 5.0 if dict(action.parameters).get("choice") == "untap" else 0.0
        if kind in {"runtime_scry_choice", "scry_choose_positions"}:
            return self._scry_score(observation, action)
        if kind == "top_reorder":
            return self._top_reorder_score(observation, action)
        if kind == "runtime_chrome_imprint":
            return self._chrome_imprint_score(observation, action)
        if kind == "runtime_mox_diamond_entry":
            return self._mox_diamond_entry_score(observation, action)
        if kind == "runtime_cam_target":
            return self._cam_target_score(action)
        if kind == "runtime_cam_effect":
            return self._cam_effect_score(action)
        if kind == "runtime_chrome_endstep_choice":
            return self._chrome_endstep_score(observation, action)
        if kind in {"choose_tutor_target", "x_artifact_search_target", "transmute_choose_target", "remaining_search_target"}:
            return self._tutor_target_score(observation, action)
        if kind == "transmute_choose_sacrifice":
            return self._transmute_sacrifice_score(observation, action)
        if kind == "transmute_pay_difference":
            return self._transmute_payment_score(action)
        if kind == "upkeep_pay_remora":
            return 50.0
        if kind == "upkeep_decline_remora":
            return -25.0
        if kind == "pass_priority":
            return 0.0
        if kind.startswith("main_"):
            return self._main_action_score(observation, action)
        return 0.0

    def choose(self, observation: RuntimePolicyView, actions: Sequence[ActionIntent], context: PolicyDecisionContext) -> ActionIntent:
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
