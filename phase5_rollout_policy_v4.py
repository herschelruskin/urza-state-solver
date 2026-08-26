#!/usr/bin/env python3
"""Phase-5 rollout policy V4: V3 plus restored mechanical-action awareness.

This is intentionally a narrow delta.  It does not learn from human labels and it
does not add new strategic families.  It only assigns sensible continuation scores
to public actions that were mechanically absent before the line-parity patch:

* fetchland activation, so a played fetch can become a blue source;
* Knack/Helix granted bounce, so an already-established bounce engine can actually
  recycle artifacts instead of ending the turn.
"""

from __future__ import annotations

import urza_solver as solver
from decision_observation import ActionIntent, PolicyDecisionContext
from non_oracle_runtime_view import RuntimePolicyView
from non_oracle_public_parity_runtime import (
    MAIN_ACTIVATE_FETCH,
    MAIN_ACTIVATE_KNACK_BOUNCE,
    PRIORITY_ACTIVATE_FETCH,
    PRIORITY_ACTIVATE_KNACK_BOUNCE,
)
from phase5_rollout_policy_v3 import DeterministicRolloutPolicyV3

PHASE5_ROLLOUT_POLICY_V4 = "urza-deterministic-rollout-v4-line-parity"

CHEAP_RECAST_TARGETS = frozenset({
    "Tormod's Crypt", "Mishra's Bauble", "Urza's Bauble", "Welding Jar",
    "Mox Opal", "Chrome Mox", "Mox Diamond", "Lotus Petal", "Jeweled Amulet",
    "Everflowing Chalice", "Aether Spellbomb", "Codex Shredder", "Giant's Boulder",
    "Grafdigger's Cage", "Hope of Ghirapur", "Mana Vault", "Manifold Key",
    "Moonsnare Prototype", "Pithing Needle", "Sensei's Divining Top", "Sol Ring",
    "Vexing Bauble", "Voltaic Key", "Witching Well", "Sewer-veillance Cam",
})
PROTECT_FROM_BOUNCE = frozenset({
    "Battered Golem", "Grinding Station", "Forensic Gadgeteer",
    "Uthros Research Craft", "The Reality Chip", "The One Ring",
})


class DeterministicRolloutPolicyV4(DeterministicRolloutPolicyV3):
    policy_id = PHASE5_ROLLOUT_POLICY_V4

    def _fetch_score(self, observation: RuntimePolicyView, action: ActionIntent, *, priority: bool) -> float:
        # A fetch on the battlefield is otherwise not a mana source.  Make the
        # normal main-phase activation strongly preferred while still leaving
        # unusual priority-time shuffles to future Q evaluation.
        known_top = tuple(observation.base.known_top)
        top_penalty = 0.0
        if known_top:
            top_penalty = 6.0 * self.visible_card_score(str(known_top[0]), observation)
        base = 142.0 if not priority else 18.0
        if int(observation.base.blue) == 0:
            base += 8.0
        return base - top_penalty

    def _knack_bounce_score(self, observation: RuntimePolicyView, action: ActionIntent, *, priority: bool) -> float:
        params = dict(action.parameters)
        target = str(params.get("target_name", ""))
        if target in PROTECT_FROM_BOUNCE:
            return -120.0
        if target in CHEAP_RECAST_TARGETS:
            # Recasting an artifact is exactly what wakes Station/Golem and feeds
            # the established Urza/Uthros/Top engines.  Zero/one-mana objects are
            # the cleanest deterministic continuation.
            try:
                mv = int(solver.mana_value(target))
            except Exception:
                mv = 2
            score = 178.0 - 8.0 * max(0, mv)
            if target == "Sol Ring":
                score += 8.0
            if target in {"Tormod's Crypt", "Mishra's Bauble", "Urza's Bauble", "Welding Jar"}:
                score += 7.0
            return score - (4.0 if priority else 0.0)
        return 95.0 - (4.0 if priority else 0.0)

    def action_score(
        self,
        observation: RuntimePolicyView,
        action: ActionIntent,
        context: PolicyDecisionContext,
    ) -> float:
        if action.kind == MAIN_ACTIVATE_FETCH:
            return self._fetch_score(observation, action, priority=False)
        if action.kind == PRIORITY_ACTIVATE_FETCH:
            return self._fetch_score(observation, action, priority=True)
        if action.kind == MAIN_ACTIVATE_KNACK_BOUNCE:
            return self._knack_bounce_score(observation, action, priority=False)
        if action.kind == PRIORITY_ACTIVATE_KNACK_BOUNCE:
            return self._knack_bounce_score(observation, action, priority=True)
        return super().action_score(observation, action, context)
