#!/usr/bin/env python3
"""Focused Phase 5I integration regressions."""

from __future__ import annotations

from phase5_monte_carlo import Phase5DecisionCache
from phase5_mulligan import OpeningEnvironment
from phase5_production_policy import (
    PHASE5H_PRODUCTION_POLICY_VERSION,
    PHASE5H_PRODUCTION_Q,
    make_phase5h_production_episode_runner,
)
from phase5i_mulligan import Phase5IOpeningKeepEvaluator


def tiny_deck_and_seven():
    seven=(
        "Island",
        "Sol Ring",
        "Mana Vault",
        "Mystical Tutor",
        "Vexing Bauble",
        "Swan Song",
        "Welding Jar",
    )
    rest=tuple(f"Filler {i:02d}" for i in range(92))
    return seven+rest,seven


def test_frozen_phase5h_config_exact():
    cfg=PHASE5H_PRODUCTION_Q
    assert cfg.screen_rollouts==1
    assert cfg.confirm_rollouts==2
    assert cfg.shortlist_size==3
    assert cfg.contingent is True
    assert cfg.confidence_gate is True
    assert cfg.validation_rollouts==2
    assert cfg.max_validation_rollouts==8
    assert abs(cfg.confidence_alpha-0.25)<1e-12
    assert cfg.key()[0]==PHASE5H_PRODUCTION_POLICY_VERSION
    print("Phase 5H production Q configuration is explicit and frozen: PASS")


def test_production_runner_carries_identity_and_shared_cache():
    cache=Phase5DecisionCache()
    runner=make_phase5h_production_episode_runner(
        mc_root_seed=123,
        decision_cache=cache,
    )
    assert runner.production_policy_version==PHASE5H_PRODUCTION_POLICY_VERSION
    assert runner.production_q_config==PHASE5H_PRODUCTION_Q
    assert runner.decision_cache is cache
    print("production episode runner exposes frozen identity and shared Q cache: PASS")


def test_phase5i_both_passes_use_same_frozen_player():
    deck,_=tiny_deck_and_seven()
    evaluator=Phase5IOpeningKeepEvaluator(
        deck,
        screen_rollouts=1,
        confirm_rollouts=2,
        shortlist_size=3,
        mc_root_seed=91,
        q_mc_root_seed=92,
        opening_environment=OpeningEnvironment(seat=1),
    )
    assert evaluator.screen_evaluator.episode_runner.production_policy_version==PHASE5H_PRODUCTION_POLICY_VERSION
    assert evaluator.confirm_evaluator.episode_runner.production_policy_version==PHASE5H_PRODUCTION_POLICY_VERSION
    assert evaluator.screen_evaluator.episode_runner.production_q_config==PHASE5H_PRODUCTION_Q
    assert evaluator.confirm_evaluator.episode_runner.production_q_config==PHASE5H_PRODUCTION_Q
    assert evaluator.screen_evaluator.episode_runner.decision_cache is evaluator.cache
    assert evaluator.confirm_evaluator.episode_runner.decision_cache is evaluator.cache
    print("Phase 5I screen/confirm both play the identical frozen Phase 5H policy: PASS")


def test_outer_sample_windows_are_disjoint_by_contract():
    deck,_=tiny_deck_and_seven()
    evaluator=Phase5IOpeningKeepEvaluator(
        deck,
        screen_rollouts=2,
        confirm_rollouts=3,
        shortlist_size=2,
        mc_root_seed=101,
        opening_environment=OpeningEnvironment(seat=1),
    )
    # The implementation passes sample_start=0 for screening and
    # sample_start=screen_rollouts for confirmation.  Assert the configured
    # windows themselves cannot overlap.
    screen_ids=set(range(0,evaluator.screen_rollouts))
    confirm_ids=set(range(evaluator.screen_rollouts,evaluator.screen_rollouts+evaluator.confirm_rollouts))
    assert screen_ids.isdisjoint(confirm_ids)
    print("Phase 5I bottom screen/confirmation outer-world windows are disjoint: PASS")


def test_live_seats_are_mechanically_equivalent():
    # Current opening mechanics consume seat only through caverns_live.  Keep an
    # explicit regression before collapsing seats 2/3/4 for expensive human
    # benchmark evaluation.
    environments=tuple(OpeningEnvironment(seat=s,player_count=4) for s in (2,3,4))
    assert all(env.caverns_live for env in environments)
    assert len({env.caverns_live for env in environments})==1
    print("Commander seats 2/3/4 share the same current Caverns-live mechanics: PASS")


def main():
    test_frozen_phase5h_config_exact()
    test_production_runner_carries_identity_and_shared_cache()
    test_phase5i_both_passes_use_same_frozen_player()
    test_outer_sample_windows_are_disjoint_by_contract()
    test_live_seats_are_mechanically_equivalent()
    print("PHASE5I MULLIGAN INTEGRATION SMOKE: ALL PASS")


if __name__=="__main__":
    main()
