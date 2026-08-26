#!/usr/bin/env python3
"""Phase-5 rollout policy V6: protect only visibly established strategic synergies.

V6 is a narrow continuation-policy correction after the action-parity and exact-cycle
work.  It deliberately does NOT protect combo cards because of hidden future draws.
A piece is protected only when the current RuntimePolicyView already shows why
sacrificing/consuming it would dismantle an established or near-established route.

Changes relative to V5:
- do not Reshape/Bay away a visibly live Top/Chip/FTT, PA/Monolith, or Knack/producer
  piece merely because a tutor activation has a high generic score;
- an Urza-exiled Power Artifact is cast only onto a target with a modeled visible
  payoff, with Grim/Basalt overwhelmingly preferred;
- do not cast Mox Diamond with no discardable land unless its spell cast itself has
  a visible trigger payoff (Assistant/Uthros/Gadgeteer/Floodcaller).

The policy still sees only RuntimePolicyView + ActionIntent.  In particular, Chrome
Mox is NOT told to preserve Power Artifact just because a hidden Monolith may be
coming later; that would overfit the sampled world and violate the intended boundary.
"""

from __future__ import annotations

import urza_solver as solver
from decision_observation import ActionIntent, PolicyDecisionContext
from non_oracle_runtime_view import RuntimePolicyView
from phase5_rollout_policy import KNUCKS, POWER_MANA, PRODUCER_PIECES
from phase5_rollout_policy_v5 import DeterministicRolloutPolicyV5

PHASE5_ROLLOUT_POLICY_V6 = "urza-deterministic-rollout-v6-visible-synergy-protection"


class DeterministicRolloutPolicyV6(DeterministicRolloutPolicyV5):
    policy_id = PHASE5_ROLLOUT_POLICY_V6

    @staticmethod
    def _has_knack_grant(observation: RuntimePolicyView) -> bool:
        return any(bool(perm.knack_granted) for perm in observation.base.battlefield)

    def _sacrifice_is_protected(self, observation: RuntimePolicyView, name: str) -> bool:
        if not name:
            return False
        board = set(self._battlefield_names(observation))
        visible = set(self._visible_names(observation))

        # PA + Monolith is an explicit terminal route once Urza is available; even
        # pre-Urza, consuming the visible half destroys that assembled relationship.
        if name in POWER_MANA and "Power Artifact" in visible:
            return True

        # A granted Knack/Helix ability belongs to the exact creature object.  Do
        # not sacrifice the producer carrying/participating in that visible loop.
        knack_live = self._has_knack_grant(observation) or bool(visible & KNUCKS)
        if name in PRODUCER_PIECES and knack_live:
            return True

        # Top becomes a strategic engine piece only when the observation already
        # shows one of its relevant support structures.
        if name == "Sensei's Divining Top":
            if observation.base.chip_attached or int(observation.base.ftt_level) >= 2:
                return True
            if "Forensic Gadgeteer" in board and board & {"Grinding Station", "Battered Golem"}:
                return True

        if name == "The Reality Chip" and observation.base.chip_attached:
            return True
        if name == "Uthros Research Craft" and int(observation.base.uthros_counters) >= 3:
            return True
        return False

    def _power_artifact_permission_score(
        self,
        observation: RuntimePolicyView,
        action: ActionIntent,
    ) -> float:
        params = dict(action.parameters)
        signature = tuple(params.get("target_signature", ()))
        target = str(signature[0]) if signature else ""
        board = set(self._battlefield_names(observation))

        if target in POWER_MANA:
            return 245.0
        if target == "Chrome Dome":
            return 158.0 if board & {"Grinding Station", "Battered Golem"} else 96.0
        if target == "Codex Shredder":
            return 62.0
        if target == "The Reality Chip":
            return 54.0
        # Consuming the permission on Giant's Boulder/Sol Ring/etc. is worse than
        # allowing the permission to expire; it removes the unique PA card from
        # future recursion with no meaningful modeled payoff.
        return -180.0

    def _mox_diamond_cast_has_trigger_payoff(self, observation: RuntimePolicyView) -> bool:
        board = set(self._battlefield_names(observation))
        if "Artificer's Assistant" in board:
            return True
        if "Forensic Gadgeteer" in board:
            return True
        if "Valley Floodcaller" in board:
            return True
        if "Uthros Research Craft" in board and int(observation.base.uthros_counters) >= 3:
            return True
        return False

    def _main_action_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        params = dict(action.parameters)
        kind = action.kind

        if kind in {"main_use_x_artifact_tutor", "main_activate_repurposing_bay"}:
            sacrificed = str(params.get("sacrifice_name", ""))
            if self._sacrifice_is_protected(observation, sacrificed):
                return -220.0

        if kind == "main_use_urza_permission":
            card = str(params.get("card", ""))
            use = str(params.get("use", ""))
            if card == "Power Artifact" and use == "cast_proactive_nonartifact":
                return self._power_artifact_permission_score(observation, action)

        if kind == "main_cast_utility_artifact" and str(params.get("card", "")) == "Mox Diamond":
            discardable = any(
                card in solver.TRUE_LAND_CARDS
                for card in observation.base.hand
                if card != "Mox Diamond"
            )
            if not discardable and not self._mox_diamond_cast_has_trigger_payoff(observation):
                return -130.0

        return super()._main_action_score(observation, action)

    def action_score(
        self,
        observation: RuntimePolicyView,
        action: ActionIntent,
        context: PolicyDecisionContext,
    ) -> float:
        return super().action_score(observation, action, context)
