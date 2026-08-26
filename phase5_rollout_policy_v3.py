#!/usr/bin/env python3
"""Goal-directed refinement of the Phase-5 deterministic rollout policy.

V3 fixes structural sequencing failures exposed by held-out human-hand traces:
- mana generation pursues the highest-priority visible goal and respects blue
  requirements instead of merely chasing the cheapest cast;
- zero/cheap fast mana is deployed before consuming additional mana resources;
- Mox Diamond is cast before the land it needs to discard;
- Chrome Mox is encouraged to imprint an expendable visible blue card when mana
  development matters;
- repeated Top activation and repeated Reality Chip reconfigure are suppressed;
- Uthros counter accumulation is subordinate to casting/development mana.

Like V2, this module never reads the human benchmark labels/ratings and receives
only RuntimePolicyView + visible ActionIntent objects.
"""

from __future__ import annotations

from typing import Tuple

import urza_solver as solver
from decision_observation import ActionIntent, PolicyDecisionContext
from non_oracle_runtime_view import RuntimePolicyView
from phase5_rollout_policy import (
    DeterministicRolloutPolicyV2,
    ENGINE_PRIORITY,
    FAST_MANA_PRIORITY,
    KNUCKS,
    POWER_MANA,
    PRODUCER_PIECES,
)

PHASE5_ROLLOUT_POLICY_V3 = "urza-deterministic-rollout-v3"

V3_ENGINE_PRIORITY = dict(ENGINE_PRIORITY)
V3_ENGINE_PRIORITY.update({
    "Mystic Remora": 151.0,
    "Rhystic Study": 147.0,
    "The One Ring": 144.0,
    "Uthros Research Craft": 132.0,
    "The Reality Chip": 129.0,
    "Fortune Teller's Talent": 126.0,
    "Forensic Gadgeteer": 124.0,
    "Faerie Mastermind": 119.0,
})
V3_COMMANDER_PRIORITY = 140.0

FAST_MANA_COST = {
    "Mox Opal": (0, 0),
    "Mox Diamond": (0, 0),
    "Chrome Mox": (0, 0),
    "Lotus Petal": (0, 0),
    "Jeweled Amulet": (0, 0),
    "Everflowing Chalice": (0, 0),
    "Mana Vault": (1, 0),
    "Sol Ring": (1, 0),
    "Moonsnare Prototype": (1, 1),
    "Grim Monolith": (2, 0),
    "Basalt Monolith": (3, 0),
}

GOAL_COSTS = {
    "Mystic Remora": (1, 1),
    "Rhystic Study": (3, 1),
    "The One Ring": (4, 0),
    "Uthros Research Craft": (3, 1),
    "The Reality Chip": (2, 1),
    "Fortune Teller's Talent": (1, 1),
    "Forensic Gadgeteer": (3, 1),
    "Faerie Mastermind": (2, 1),
    "Spellseeker": (3, 1),
    "Transmute Artifact": (2, 2),
    "Reshape": (2, 2),
    "Whir of Invention": (3, 3),
}


class DeterministicRolloutPolicyV3(DeterministicRolloutPolicyV2):
    def _highest_goal(self, observation: RuntimePolicyView) -> Tuple[int, int]:
        """Return (total mana, blue mana) for the highest-priority visible goal."""
        hand = set(observation.base.hand)
        candidates = []

        # Only the three strongest generic value engines intentionally precede an
        # available commander. This mirrors the broad human policy rather than
        # choosing the cheapest spell in hand.
        for card in ("Mystic Remora", "Rhystic Study", "The One Ring"):
            if card in hand:
                total, blue = GOAL_COSTS[card]
                candidates.append((V3_ENGINE_PRIORITY[card], total, blue))

        if observation.base.commander_in_command_zone and not observation.base.urza:
            tax = 2 * int(observation.base.commander_casts_from_zone)
            candidates.append((V3_COMMANDER_PRIORITY, 4 + tax, 2))

        # Once Urza is already available, continue into the best visible engine.
        if observation.base.urza or not observation.base.commander_in_command_zone:
            for card, priority in V3_ENGINE_PRIORITY.items():
                if card in hand and card in GOAL_COSTS:
                    total, blue = GOAL_COSTS[card]
                    candidates.append((priority, total, blue))
            for card in ("Spellseeker", "Transmute Artifact", "Reshape", "Whir of Invention"):
                if card in hand:
                    total, blue = GOAL_COSTS[card]
                    candidates.append((105.0, total, blue))

        if not candidates:
            return (0, 0)
        _, total, blue = max(candidates)
        return int(total), int(blue)

    @staticmethod
    def _fast_mana_castable_now(observation: RuntimePolicyView) -> bool:
        floating_total = int(observation.base.blue) + int(observation.base.colorless)
        floating_blue = int(observation.base.blue)
        for card in observation.base.hand:
            cost = FAST_MANA_COST.get(card)
            if cost is None:
                continue
            total, blue = cost
            if floating_total >= total and floating_blue >= blue:
                if card == "Mox Diamond":
                    # The discard must still be in hand before the normal land play.
                    if not any(c in solver.TRUE_LAND_CARDS for c in observation.base.hand if c != "Mox Diamond"):
                        continue
                if card == "Chrome Mox":
                    if not any(c in solver.BLUE_NONARTIFACT_FRONT for c in observation.base.hand if c != "Chrome Mox"):
                        continue
                return True
        return False

    def _artifact_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        card = str(dict(action.parameters).get("card", ""))
        if card in V3_ENGINE_PRIORITY:
            return V3_ENGINE_PRIORITY[card]
        if card == "Mox Diamond":
            discardable = any(c in solver.TRUE_LAND_CARDS for c in observation.base.hand if c != "Mox Diamond")
            return 149.0 if discardable else 5.0
        if card == "Chrome Mox":
            imprintable = any(c in solver.BLUE_NONARTIFACT_FRONT for c in observation.base.hand if c != "Chrome Mox")
            return 137.0 if imprintable else 18.0
        if card in FAST_MANA_PRIORITY:
            return max(126.0, FAST_MANA_PRIORITY[card])
        return super()._artifact_score(observation, action)

    def _main_action_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        params = dict(action.parameters)
        kind = action.kind

        if kind == "main_cast_commander":
            return V3_COMMANDER_PRIORITY

        if kind == "main_play_land":
            # Preserve a discardable land long enough to resolve Mox Diamond.
            if "Mox Diamond" in observation.base.hand:
                discardable = [c for c in observation.base.hand if c in solver.TRUE_LAND_CARDS]
                if discardable:
                    return 86.0
            return super()._main_action_score(observation, action)

        if kind == "main_mana_action":
            if self._fast_mana_castable_now(observation):
                return 70.0
            total_goal, blue_goal = self._highest_goal(observation)
            if not total_goal:
                return 5.0
            floating_total = int(observation.base.blue) + int(observation.base.colorless)
            floating_blue = int(observation.base.blue)
            blue_delta = int(params.get("blue_delta", 0))
            colorless_delta = int(params.get("colorless_delta", 0))
            gain = max(0, blue_delta) + max(0, colorless_delta)
            blue_deficit = max(0, blue_goal - floating_blue)
            total_deficit = max(0, total_goal - floating_total)
            if blue_deficit > 0:
                if blue_delta > 0:
                    return 135.0 + 4.0 * blue_delta
                # Do not burn colorless-only resources while the visible goal is
                # still impossible for lack of blue. Ending the turn is better.
                return -25.0
            if total_deficit > 0 and gain > 0:
                label = action.label.lower()
                sacrifice_penalty = 0.0
                if "sac crystal vein" in label:
                    sacrifice_penalty = 18.0
                return 127.0 + 3.0 * gain - sacrifice_penalty
            return 4.0

        if kind == "main_cast_artifact":
            return self._artifact_score(observation, action)
        if kind == "main_cast_utility_artifact":
            return self._artifact_score(observation, action)

        if kind == "main_cast_proactive_nonartifact":
            card = str(params.get("card", ""))
            if card in V3_ENGINE_PRIORITY:
                return V3_ENGINE_PRIORITY[card]
            return super()._main_action_score(observation, action)

        if kind == "main_activate_top":
            return 24.0 if not observation.base.known_top else -35.0
        if kind == "main_activate_top_draw":
            return 82.0 if int(params.get("ready_key_count", 0)) > 0 else -100.0

        if kind == "main_activate_chip_reconfigure":
            if observation.base.chip_attached:
                return -100.0
            return 104.0 if str(params.get("choice", "")) == "attach" else 0.0

        if kind == "main_activate_uthros_station":
            # Counter thresholds matter, but never outrank casting/development mana.
            return self._uthros_station_score(action)

        return super()._main_action_score(observation, action)

    def action_score(self, observation: RuntimePolicyView, action: ActionIntent, context: PolicyDecisionContext) -> float:
        params = dict(action.parameters)
        if action.kind == "runtime_mox_diamond_entry":
            land = str(params.get("land", ""))
            return 130.0 - self.visible_card_score(land, observation) if land else -120.0
        if action.kind == "runtime_chrome_imprint":
            card = str(params.get("card", ""))
            if not card:
                return -90.0
            # Prefer exiling interaction/redundancy over engines/combo pieces.
            penalty = self.visible_card_score(card, observation)
            if card in KNUCKS and not (set(self._battlefield_names(observation)) & PRODUCER_PIECES):
                penalty -= 8.0
            if card == "Power Artifact" and not (set(self._visible_names(observation)) & POWER_MANA):
                penalty -= 7.0
            return 95.0 - 5.0 * penalty
        return super().action_score(observation, action, context)
