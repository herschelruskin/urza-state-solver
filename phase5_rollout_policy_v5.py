#!/usr/bin/env python3
"""Phase-5 rollout policy V5: commitment consistency before broader training.

V5 addresses deterministic failures exposed after restoring Oracle/non-Oracle
mechanical parity.  It remains information-faithful and does not read human outcome
labels.

Changes relative to V4:
- Transmute target selection respects the public sacrificed-MV / payment-feasibility
  annotation.  A target that cannot pay its required difference is dominated by an
  affordable target or failing to find rather than being knowingly sent to graveyard.
- Transmute sacrifice choices prefer expendable higher-MV artifacts over a zero-MV
  Construct while protecting active engines/combo pieces.
- mana generation may pursue a colorless artifact that becomes castable immediately,
  even when the highest long-term goal still has an unmet blue requirement.  This
  fixes states such as Ancient Tomb + Top/Codex/Prized Statue ending the turn unused.
- Chain of Vapor copies default to declining in goldfish play unless a producer is
  already online and the bounce target is a cheap artifact worth recycling.  This
  prevents deterministic policies from sacrificing every land simply because copy
  and decline previously tied at score zero.
"""

from __future__ import annotations

import urza_solver as solver
from decision_observation import ActionIntent, PolicyDecisionContext
from non_oracle_chain_offer_runtime import (
    CHAIN_COPY_COMMIT,
    CHAIN_COPY_DECLINE,
    MAIN_CAST_CHAIN,
    PRIORITY_CAST_CHAIN,
)
from non_oracle_runtime_view import RuntimePolicyView
from phase5_rollout_policy import POWER_MANA, PRODUCER_PIECES, VALUE_ENGINES
from phase5_rollout_policy_v4 import DeterministicRolloutPolicyV4

PHASE5_ROLLOUT_POLICY_V5 = "urza-deterministic-rollout-v5-commitment-aware"

PROTECTED_TRANSMUTE_SACRIFICES = frozenset({
    "Basalt Monolith", "Grim Monolith", "Grinding Station", "Battered Golem",
    "Forensic Gadgeteer", "The Reality Chip", "The One Ring", "Uthros Research Craft",
    "Sensei's Divining Top",
})

CHEAP_CHAIN_RECYCLES = frozenset({
    "Tormod's Crypt", "Mishra's Bauble", "Urza's Bauble", "Welding Jar",
    "Mox Opal", "Chrome Mox", "Mox Diamond", "Lotus Petal", "Jeweled Amulet",
    "Everflowing Chalice", "Aether Spellbomb", "Codex Shredder", "Giant's Boulder",
    "Grafdigger's Cage", "Hope of Ghirapur", "Mana Vault", "Manifold Key",
    "Moonsnare Prototype", "Pithing Needle", "Sensei's Divining Top", "Sol Ring",
    "Vexing Bauble", "Voltaic Key", "Witching Well",
})


class DeterministicRolloutPolicyV5(DeterministicRolloutPolicyV4):
    policy_id = PHASE5_ROLLOUT_POLICY_V5

    def _artifact_enabled_by_mana_action(
        self,
        observation: RuntimePolicyView,
        action: ActionIntent,
    ) -> bool:
        params = dict(action.parameters)
        blue_after = int(observation.base.blue) + int(params.get("blue_delta", 0))
        colorless_after = int(observation.base.colorless) + int(params.get("colorless_delta", 0))
        if blue_after < 0 or colorless_after < 0:
            return False
        total_after = blue_after + colorless_after
        board = set(self._battlefield_names(observation))
        gadgeteer = "Forensic Gadgeteer" in board

        for card in observation.base.hand:
            if card not in solver.ARTIFACTS or card in solver.ALL_LANDS:
                continue
            if card in {"Mox Diamond", "Chrome Mox"}:
                # Entry commitments dominate whether these are actually useful;
                # V3 already handles their casting prerequisites separately.
                continue
            generic, blue = solver.COST.get(card, (999, 999))
            generic = int(generic)
            blue = int(blue)
            if gadgeteer:
                generic = max(0, generic - 1)
            required_total = generic + blue
            currently_payable = (
                int(observation.base.blue) >= blue
                and int(observation.base.blue) + int(observation.base.colorless) >= required_total
            )
            payable_after = blue_after >= blue and total_after >= required_total
            if payable_after and not currently_payable:
                return True
        return False

    def _transmute_target_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        params = dict(action.parameters)
        target = str(params.get("target", ""))
        if not target:
            # Failing to find is preferable to intentionally binning a valuable
            # searched card when no legal difference payment exists.
            return -35.0

        base = super()._tutor_target_score(observation, action)
        difference = int(params.get("difference", 0))
        payable = bool(params.get("can_pay_difference", True))
        min_steps = int(params.get("min_payment_steps", 0))
        if difference > 0 and not payable:
            return -500.0
        if difference <= 0:
            return base + 24.0
        return base + 12.0 - 5.0 * difference - 2.0 * max(0, min_steps)

    def _transmute_sacrifice_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        params = dict(action.parameters)
        signature = tuple(params.get("signature", ()))
        name = str(signature[0]) if signature else ""
        mv = int(params.get("mana_value", 0))

        if name in PROTECTED_TRANSMUTE_SACRIFICES:
            return -180.0 + 3.0 * mv
        if name == "Construct":
            return -55.0
        if name == "Prized Statue":
            return 145.0 + 8.0 * mv
        if name in {"Treasure", "Clue"}:
            return 125.0 + 8.0 * mv
        if name == "Sapphire Medallion":
            return 112.0 + 8.0 * mv

        # Higher-MV expendable artifacts buy a wider Transmute target window.  Card
        # value remains a penalty so we do not blindly eat real engines.
        return 78.0 + 11.0 * mv - 4.0 * self.visible_card_score(name, observation)

    def _chain_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        params = dict(action.parameters)
        target = str(params.get("target_name", ""))
        board = set(self._battlefield_names(observation))
        producer_online = bool(board & PRODUCER_PIECES)
        if not producer_online:
            return -90.0
        if target not in CHEAP_CHAIN_RECYCLES:
            return -45.0
        try:
            mv = int(solver.mana_value(target))
        except Exception:
            mv = 2
        return 108.0 - 8.0 * max(0, mv)

    def _chain_copy_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        if action.kind == CHAIN_COPY_DECLINE:
            return 35.0
        params = dict(action.parameters)
        target = str(params.get("target_name", ""))
        board = set(self._battlefield_names(observation))
        if not (board & PRODUCER_PIECES) or target not in CHEAP_CHAIN_RECYCLES:
            return -120.0
        try:
            mv = int(solver.mana_value(target))
        except Exception:
            mv = 2
        # A land is a meaningful cost.  Only an already-online producer plus a
        # cheap artifact recycle can outrank declining the optional copy.
        return 74.0 - 8.0 * max(0, mv)

    def _main_action_score(self, observation: RuntimePolicyView, action: ActionIntent) -> float:
        if action.kind == "main_mana_action":
            inherited = super()._main_action_score(observation, action)
            if self._artifact_enabled_by_mana_action(observation, action):
                return max(inherited, 133.0)
            return inherited
        if action.kind == MAIN_CAST_CHAIN:
            return self._chain_score(observation, action)
        return super()._main_action_score(observation, action)

    def action_score(
        self,
        observation: RuntimePolicyView,
        action: ActionIntent,
        context: PolicyDecisionContext,
    ) -> float:
        if action.kind == "transmute_choose_target":
            return self._transmute_target_score(observation, action)
        if action.kind == "transmute_choose_sacrifice":
            return self._transmute_sacrifice_score(observation, action)
        if action.kind in {MAIN_CAST_CHAIN, PRIORITY_CAST_CHAIN}:
            return self._chain_score(observation, action)
        if action.kind in {CHAIN_COPY_DECLINE, CHAIN_COPY_COMMIT}:
            return self._chain_copy_score(observation, action)
        return super().action_score(observation, action, context)
