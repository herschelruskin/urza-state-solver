#!/usr/bin/env python3
"""Frozen production gameplay-policy configuration after Phase 5H validation.

This module is deliberately small.  Downstream layers should import the named
configuration/factory instead of relying on the current defaults of
SelectiveTutorQController.  That makes mulligan valuation, deck-level Monte Carlo,
interaction analysis, and card-swap experiments refer to one reproducible player.
"""

from __future__ import annotations

from dataclasses import dataclass

from phase5_monte_carlo import Phase5DecisionCache
from phase5_selective_tutor_q import make_selective_tutor_q_episode_runner


PHASE5H_PRODUCTION_POLICY_VERSION = "urza-phase5h-production-policy-v1"
PHASE5H_PRODUCTION_CACHE_MAX_ENTRIES = 64


@dataclass(frozen=True)
class FrozenTutorQConfig:
    screen_rollouts: int = 1
    confirm_rollouts: int = 2
    shortlist_size: int = 3
    contingent: bool = True
    confidence_gate: bool = True
    validation_rollouts: int = 2
    max_validation_rollouts: int = 8
    confidence_alpha: float = 0.25

    def __post_init__(self) -> None:
        if int(self.screen_rollouts) < 1:
            raise ValueError("screen_rollouts must be >= 1")
        if int(self.confirm_rollouts) < 1:
            raise ValueError("confirm_rollouts must be >= 1")
        if int(self.shortlist_size) < 1:
            raise ValueError("shortlist_size must be >= 1")
        if int(self.validation_rollouts) < 1:
            raise ValueError("validation_rollouts must be >= 1")
        if int(self.max_validation_rollouts) < int(self.validation_rollouts):
            raise ValueError("max_validation_rollouts must be >= validation_rollouts")
        if not (0.0 < float(self.confidence_alpha) <= 0.5):
            raise ValueError("confidence_alpha must be in (0, 0.5]")

    def key(self):
        return (
            PHASE5H_PRODUCTION_POLICY_VERSION,
            int(self.screen_rollouts),
            int(self.confirm_rollouts),
            int(self.shortlist_size),
            bool(self.contingent),
            bool(self.confidence_gate),
            int(self.validation_rollouts),
            int(self.max_validation_rollouts),
            float(self.confidence_alpha),
        )


# Frozen from the Phase 5H 10-hand x 4-world paired held-out evaluation:
# rollout-v6 5/40; one-step confidence-Q 12/40; bounded contingent confidence-Q 14/40.
PHASE5H_PRODUCTION_Q = FrozenTutorQConfig(
    screen_rollouts=1,
    confirm_rollouts=2,
    shortlist_size=3,
    contingent=True,
    confidence_gate=True,
    validation_rollouts=2,
    max_validation_rollouts=8,
    confidence_alpha=0.25,
)


def make_phase5h_production_decision_cache() -> Phase5DecisionCache:
    """Return the bounded runtime cache for the frozen Phase-5H player.

    The bound is execution-only: evicted entries are recomputed from the same
    explicit seeds, so policy values and action choices are unchanged.
    """

    return Phase5DecisionCache(max_entries=PHASE5H_PRODUCTION_CACHE_MAX_ENTRIES)


def make_phase5h_production_episode_runner(
    *,
    mc_root_seed: int,
    decision_cache: Phase5DecisionCache | None = None,
    config: FrozenTutorQConfig = PHASE5H_PRODUCTION_Q,
):
    """Return the frozen Phase-5H OpeningKeepEvaluator-compatible player."""

    cache = (
        decision_cache
        if decision_cache is not None
        else make_phase5h_production_decision_cache()
    )
    runner = make_selective_tutor_q_episode_runner(
        mc_root_seed=int(mc_root_seed),
        screen_rollouts=int(config.screen_rollouts),
        confirm_rollouts=int(config.confirm_rollouts),
        shortlist_size=int(config.shortlist_size),
        decision_cache=cache,
        contingent=bool(config.contingent),
        confidence_gate=bool(config.confidence_gate),
        validation_rollouts=int(config.validation_rollouts),
        max_validation_rollouts=int(config.max_validation_rollouts),
        confidence_alpha=float(config.confidence_alpha),
    )
    runner.production_policy_version = PHASE5H_PRODUCTION_POLICY_VERSION
    runner.production_q_config = config
    return runner
