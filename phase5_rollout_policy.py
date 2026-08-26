#!/usr/bin/env python3
"""Human-informed but outcome-independent rollout policy for Phase 5.

This is a deterministic continuation policy, not a learned hand classifier.  It
uses only RuntimePolicyView + visible ActionIntent data and encodes broad pilot
principles needed for plausible goldfish continuations:

- develop mana only when it serves a visible development goal;
- cast Urza promptly once enabled, except high-value engines may precede it;
- prioritize value engines before generic combo fishing;
- tutors seek a missing engine/mana/combo role rather than a globally fixed card;
- Power Artifact / Knack are valuable only with a meaningful visible target;
- avoid blind self-mill and non-combo Sensei's Top draw loops.

The 36 human keep/mull labels and numerical hand ratings are deliberately NOT read
by this module.  They remain held-out calibration data.
"""

from __future__ import annotations

from typing import Tuple

import urza_solver as solver
from decision_observation import ActionIntent, PolicyDecisionContext
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_runtime_view import RuntimePolicyView

PHASE5_ROLLOUT_POLICY_VERSION = "urza-deterministic-rollout-v2"

VALUE_ENGINES = frozenset({
    "Mystic Remora", "Rhystic Study", "The One Ring", "Uthros Research Craft",
    "The Reality Chip", "Fortune Teller's Talent", "Faerie Mastermind",
    "Forensic Gadgeteer",
})
ONLINE_VALUE_ENGINES = VALUE_ENGINES
FAST_MANA = frozenset({
    "Sol Ring", "Mana Vault", "Grim Monolith", "Basalt Monolith", "Mox Opal",
    "Mox Diamond", "Chrome Mox", "Lotus Petal", "Jeweled Amulet",
    "Everflowing Chalice",
})
POWER_MANA = frozenset({"Basalt Monolith", "Grim Monolith"})
PRODUCER_PIECES = frozenset({"Grinding Station", "Battered Golem", "Forensic Gadgeteer"})
KNUCKS = frozenset({"Banishing Knack", "Retraction Helix"})

ENGINE_PRIORITY = {
    "Mystic Remora": 126.0,
    "Rhystic Study": 121.0,
    "The One Ring": 118.0,
    "Uthros Research Craft": 112.0,
    "The Reality Chip": 108.0,
    "Fortune Teller's Talent": 104.0,
    "Forensic Gadgeteer": 101.0,
    "Faerie Mastermind": 96.0,
    "Artificer's Assistant": 78.0,
    "Tezzeret, Cruel Captain": 82.0,
    "Valley Floodcaller": 74.0,
}
FAST_MANA_PRIORITY = {
    "Mana Vault": 103.0,
    "Sol Ring": 101.0,
    "Mox Opal": 99.0,
    "Mox Diamond": 98.0,
    "Chrome Mox": 97.0,
    "Grim Monolith": 96.0,
    "Lotus Petal": 94.0,
    "Jeweled Amulet": 91.0,
    "Everflowing Chalice": 90.0,
    "Basalt Monolith": 88.0,
}
LAND_PRIORITY = {
    "Ancient Tomb": 111.0,
    "City of Traitors": 108.0,
    "Crystal Vein": 105.0,
    "Seat of the Synod": 103.0,
    "Island": 102.0,
    "Minamo, School at Water's Edge": 102.0,
    "Oboro, Palace in the Clouds": 102.0,
    "Otawara, Soaring City": 101.0,
    "Cephalid Coliseum": 100.0,
    "Ipnu Rivulet": 100.0,
    "Flooded Strand": 100.0,
    "Misty Rainforest": 100.0,
    "Polluted Delta": 100.0,
    "Prismatic Vista": 100.0,
    "Scalding Tarn": 100.0,
    "Saprazzan Skerry": 96.0,
    "Urza's Saga": 94.0,
}


class DeterministicRolloutPolicyV2(DeterministicBasePolicy):
    policy_id = PHASE5_ROLLOUT_POLICY_VERSION

    @staticmethod
    def _battlefield_names(observation: RuntimePolicyView) -> Tuple[str, ...]:
        return tuple(perm.name for perm in observation.base.battlefield)

    @staticmethod
    def _hand_names(observation: RuntimePolicyView) -> Tuple[str, ...]:
        return tuple(observation.base.hand)

    def _visible_names(self, observation: RuntimePolicyView) -> frozenset[str]:
        return frozenset(self._hand_names(observation) + self._battlefield_names(observation))

    def _has_online_engine(self, observation: RuntimePolicyView) -> bool:
        return bool(set(self._battlefield_names(observation)) & ONLINE_VALUE_ENGINES)

    def _has_visible_engine(self, observation: RuntimePolicyView) -> bool:
        return bool(set(self._visible_names(observation)) & VALUE_ENGINES)

    def _mana_goal(self, observation: RuntimePolicyView) -> int:
        """Smallest visible high-value mana threshold worth building toward."""
        hand = set(self._hand_names(observation))
        goals = []
        if observation.base.commander_in_command_zone and not observation.base.urza:
            goals.append(4 + 2 * int(observation.base.commander_casts_from_zone))
        printed = {
            "Mystic Remora": 1,
            "Fortune Teller's Talent": 1,
            "The Reality Chip": 2,
            "Faerie Mastermind": 2,
            "Rhystic Study": 3,
            "Forensic Gadgeteer": 3,
            "Uthros Research Craft": 3,
            "The One Ring": 4,
            "Spellseeker": 3,
            "Transmute Artifact": 2,
            "Reshape": 2,
            "Whir of Invention": 3,
        }
        goals.extend(cost for card, cost in printed.items() if card in hand)
        return min(goals) if goals else 0

    def _tutor_target_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        target = str(dict(action.parameters).get("target", ""))
        if not target:
            return -200.0
        visible = self._visible_names(observation)
        board = set(self._battlefield_names(observation))

        # Deterministic visible combo completion gets first priority.
        if target == "Power Artifact" and visible & POWER_MANA:
            return 180.0
        if target in POWER_MANA and "Power Artifact" in visible:
            return 178.0
        if target in KNUCKS and board & PRODUCER_PIECES:
            return 165.0
        if target in PRODUCER_PIECES and visible & KNUCKS:
            return 160.0

        # Without an existing engine, use tutors to create a value route. Simple
        # instant/sorcery tutors often need to find an artifact tutor rather than
        # the final engine directly.
        if not self._has_visible_engine(observation):
            engine_routes = {
                "Transmute Artifact": 154.0,
                "Reshape": 151.0,
                "Whir of Invention": 149.0,
                "Scour for Scrap": 138.0,
                "Spellseeker": 134.0,
                "Mystical Tutor": 126.0,
                "Merchant Scroll": 120.0,
            }
            if target in engine_routes:
                return engine_routes[target]
            if target in VALUE_ENGINES:
                return 155.0 + ENGINE_PRIORITY.get(target, 90.0) / 20.0

        target_base = {
            "The One Ring": 146.0,
            "Uthros Research Craft": 143.0,
            "The Reality Chip": 141.0,
            "Forensic Gadgeteer": 137.0,
            "Fortune Teller's Talent": 135.0,
            "Grinding Station": 129.0,
            "Grim Monolith": 127.0,
            "Basalt Monolith": 125.0,
            "Sewer-veillance Cam": 118.0,
            "Sensei's Divining Top": 108.0,
            "Transmute Artifact": 125.0,
            "Reshape": 122.0,
            "Whir of Invention": 120.0,
            "Scour for Scrap": 111.0,
            "Dramatic Reversal": 80.0,
            "Banishing Knack": 45.0,
            "Retraction Helix": 44.0,
        }
        return target_base.get(target, 70.0 + self.visible_card_score(target, observation))

    def _proactive_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        params = dict(action.parameters)
        card = str(params.get("card", ""))
        target_signature = tuple(params.get("target_signature", ()))
        target_name = str(target_signature[0]) if target_signature else ""
        board = set(self._battlefield_names(observation))

        if card in ENGINE_PRIORITY:
            return ENGINE_PRIORITY[card]
        if card == "Power Artifact":
            return 185.0 if target_name in POWER_MANA else -120.0
        if card in KNUCKS:
            if target_name in {"Battered Golem", "Forensic Gadgeteer", "Valley Floodcaller"} and board & PRODUCER_PIECES:
                return 165.0
            return -80.0
        if card == "Dramatic Reversal":
            tapped_nonlands = sum(
                bool(perm.tapped) and perm.name not in solver.ALL_LANDS
                for perm in observation.base.battlefield
            )
            return 115.0 if tapped_nonlands >= 2 else -35.0
        return super()._main_action_score(observation, action)

    def _artifact_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        card = str(dict(action.parameters).get("card", ""))
        if card in ENGINE_PRIORITY:
            return ENGINE_PRIORITY[card]
        if card in FAST_MANA_PRIORITY:
            return FAST_MANA_PRIORITY[card]
        special = {
            "Grinding Station": 86.0,
            "Battered Golem": 88.0,
            "Sewer-veillance Cam": 84.0,
            "Chrome Dome": 80.0,
            "Prized Statue": 76.0,
            "Moonsnare Prototype": 82.0,
            "Sensei's Divining Top": 58.0,
            "Voltaic Key": 72.0,
            "Manifold Key": 70.0,
        }
        return special.get(card, 64.0 + self.visible_card_score(card, observation))

    def _mill_action_score(self, observation: RuntimePolicyView, action: ActionIntent, *, priority: bool) -> float:
        known = tuple(observation.base.known_top)
        if len(known) < 2:
            return -120.0
        top_value = self.visible_card_score(str(known[0]), observation)
        next_value = self.visible_card_score(str(known[1]), observation)
        if next_value <= top_value:
            return -100.0
        score = 35.0 + 8.0 * (next_value - top_value)
        sacrificed = str(dict(action.parameters).get("sacrifice_name", ""))
        if sacrificed in {"Grinding Station", "Forensic Gadgeteer", "Battered Golem"}:
            score -= 90.0
        elif sacrificed == "Prized Statue":
            score += 8.0
        elif sacrificed:
            score -= 3.0 * self.visible_card_score(sacrificed, observation)
        return score - (2.0 if priority else 0.0)

    def _main_action_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        params = dict(action.parameters)
        kind = action.kind

        if kind == "main_play_land":
            card = str(params.get("card", ""))
            return LAND_PRIORITY.get(card, 99.0)
        if kind == "main_cast_commander":
            return 116.0
        if kind == "main_mana_action":
            floating = int(observation.base.blue) + int(observation.base.colorless)
            goal = self._mana_goal(observation)
            gain = max(0, int(params.get("blue_delta", 0))) + max(0, int(params.get("colorless_delta", 0)))
            return 109.0 + 2.0 * gain if goal and floating < goal else 8.0 + gain
        if kind == "main_cast_artifact":
            return self._artifact_score(observation, action)
        if kind == "main_cast_utility_artifact":
            card = str(params.get("card", ""))
            return FAST_MANA_PRIORITY.get(card, self._artifact_score(observation, action))
        if kind == "main_cast_proactive_nonartifact":
            return self._proactive_score(observation, action)
        if kind in {"main_use_simple_tutor", "main_use_transmute_artifact", "main_use_x_artifact_tutor"}:
            return 102.0 if not self._has_visible_engine(observation) else 88.0
        if kind in {"main_cast_scour_for_scrap", "main_activate_repurposing_bay", "main_activate_tezzeret_minus3"}:
            return 92.0
        if kind == "main_activate_top_draw":
            ready_keys = int(params.get("ready_key_count", 0))
            return 78.0 if ready_keys > 0 else -90.0
        if kind == "main_activate_top":
            return 12.0
        if kind == "main_draw_activation":
            ability = str(params.get("ability_kind", ""))
            return {
                "activated_one_ring_draw": 112.0,
                "activated_bauble_delayed_draw": 63.0,
                "activated_cam_draw_two": 60.0,
                "activated_vexing_bauble_draw": 48.0,
                "activated_clue_draw": 45.0,
                "activated_aether_spellbomb_draw": 42.0,
                "activated_witching_well_draw": 38.0,
            }.get(ability, 30.0)
        if kind in {"main_activate_station_mill", "main_activate_codex_mill"}:
            return self._mill_action_score(observation, action, priority=False)
        if kind == "main_activate_urza_spin":
            return 55.0
        if kind == "main_use_urza_permission":
            return 82.0 + self.visible_card_score(str(params.get("card", "")), observation)
        if kind == "main_activate_chip_reconfigure":
            return 96.0 if str(params.get("choice", "")) == "attach" else 5.0
        if kind == "main_activate_uthros_station":
            return 88.0
        if kind == "main_activate_key":
            return 75.0 + super()._main_action_score(observation, action) / 10.0
        if kind == "main_cast_gitaxian_probe":
            return 66.0
        if kind == "main_end_turn":
            return 0.0
        return super()._main_action_score(observation, action)

    def action_score(self, observation: RuntimePolicyView, action: ActionIntent, context: PolicyDecisionContext) -> float:
        kind = action.kind
        if kind in {"choose_tutor_target", "x_artifact_search_target", "transmute_choose_target", "remaining_search_target"}:
            return self._tutor_target_score(observation, action)
        if kind in {"priority_activate_station_mill", "priority_activate_codex_mill"}:
            return self._mill_action_score(observation, action, priority=True)
        return super().action_score(observation, action, context) if not kind.startswith("main_") else self._main_action_score(observation, action)
