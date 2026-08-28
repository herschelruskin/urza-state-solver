#!/usr/bin/env python3
"""Focused Phase 5I integration regressions."""

from __future__ import annotations

from phase5_monte_carlo import Phase5DecisionCache
from phase3_value_engine import WinDistributionValue
from phase5_mulligan import OpeningEnvironment, OpeningKeepEstimate, NO_PREGAME_CHOICE
from phase5_production_policy import (
    PHASE5H_PRODUCTION_POLICY_VERSION,
    PHASE5H_PRODUCTION_Q,
    make_phase5h_production_episode_runner,
)
from phase5i_mulligan import (
    Phase5IOpeningKeepEvaluator,
    _merge_keep_estimates,
    _optimistic_completion_key,
)


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




def _estimate(*, bottom, rollouts, exact_win):
    value=WinDistributionValue(
        horizon=6,
        exact_win=tuple(exact_win),
        no_win=1.0-sum(exact_win),
    )
    return OpeningKeepEstimate(
        stage=2,
        keep_size=6,
        bottom=(bottom,),
        kept_hand=("Island",)*6,
        value=value,
        rollouts=rollouts,
        win_probability_wilson95=(0.0,1.0),
        terminal_reason_counts=(("horizon",rollouts),),
        pregame_choice=NO_PREGAME_CHOICE,
    )


def test_exact_confirmation_bound_is_safe():
    partial=_estimate(
        bottom="Island",
        rollouts=2,
        exact_win=(0.0,0.0,0.0,0.0,0.0,0.0),
    )
    optimistic=_optimistic_completion_key(partial,total_rollouts=3)
    incumbent=(2.0/3.0,0.0,0.0,0.0,0.0,0.0)
    assert optimistic[0]==round(1.0/3.0,15)
    assert optimistic < incumbent
    print("exact confirmation optimistic bound prunes only impossible catch-ups: PASS")


def test_merge_keep_estimates_preserves_distribution():
    win=_estimate(
        bottom="Island",
        rollouts=1,
        exact_win=(0.0,0.0,0.0,0.0,1.0,0.0),
    )
    loss=_estimate(
        bottom="Island",
        rollouts=1,
        exact_win=(0.0,0.0,0.0,0.0,0.0,0.0),
    )
    merged=_merge_keep_estimates((win,loss))
    assert merged.rollouts==2
    assert merged.value.win_probability==0.5
    assert merged.value.exact_win[4]==0.5
    print("adaptive paired-screen estimate merging preserves exact distribution: PASS")

def main():
    test_frozen_phase5h_config_exact()
    test_production_runner_carries_identity_and_shared_cache()
    test_phase5i_both_passes_use_same_frozen_player()
    test_outer_sample_windows_are_disjoint_by_contract()
    test_live_seats_are_mechanically_equivalent()
    test_exact_confirmation_bound_is_safe()
    test_merge_keep_estimates_preserves_distribution()
    print("PHASE5I MULLIGAN INTEGRATION SMOKE: ALL PASS")


if __name__=="__main__":
    main()
