#!/usr/bin/env python3
"""Focused typed-runtime parity checks for Chain of Vapor and self-Offer."""

import urza_solver as solver
from non_oracle_chain_offer_runtime import (
    CHAIN_COPY_COMMIT,
    CHAIN_COPY_DECLINE,
    MAIN_CAST_CHAIN,
    PRIORITY_CAST_OFFER_SELF,
    _stage_chain_copy_choice,
)
from non_oracle_rules_adapter_v2 import apply_main_action, rules_decision_request
from non_oracle_runtime import make_runtime_state
from non_oracle_top_draw_runtime import PRIORITY_ACTIVATE_TOP_DRAW
from solver_architecture import canonical_markov_state_key
from phase5_rollout_policy_v6 import DeterministicRolloutPolicyV6


def _action(runtime, *, kind=None, label_contains=None):
    rows = list(rules_decision_request(runtime, horizon=6, policy_id="chain-offer-smoke").actions)
    if kind is not None:
        rows = [row for row in rows if row.kind == kind]
    if label_contains is not None:
        rows = [row for row in rows if label_contains in row.label]
    if not rows:
        raise AssertionError(f"no action kind={kind!r} label={label_contains!r}")
    return sorted(rows, key=lambda row: row.action_id)[0]


def _pass(runtime):
    return _action(runtime, kind="pass_priority")


def test_chain_bounce_copy_matches_oracle_public_state():
    state = solver.State(
        turn=3,
        library=(),
        hand=("Chain of Vapor",),
        battlefield=(
            solver.Perm("Island"),
            solver.Perm("Sol Ring"),
            solver.Perm("Witching Well"),
        ),
        blue=2,
        rng_root_seed=20260826,
    )
    runtime = make_runtime_state(state)
    cast = _action(runtime, kind=MAIN_CAST_CHAIN, label_contains="Sol Ring")
    runtime = apply_main_action(runtime, cast)
    runtime = apply_main_action(runtime, _pass(runtime))
    assert "Sol Ring" in runtime.true_state.hand
    assert runtime.pending is not None

    copy = _action(runtime, kind=CHAIN_COPY_COMMIT, label_contains="Witching Well")
    runtime = apply_main_action(runtime, copy)
    runtime = apply_main_action(runtime, _pass(runtime))
    assert runtime.pending is None
    assert set(runtime.true_state.hand) == {"Sol Ring", "Witching Well"}
    assert "Chain of Vapor" in runtime.true_state.graveyard
    assert "Island" in runtime.true_state.graveyard

    oracle = solver.chain_of_vapor_actions(state)
    wanted = canonical_markov_state_key(runtime.true_state)
    assert any(canonical_markov_state_key(row) == wanted for row in oracle)
    print("Chain cast -> bounce -> land-sac copy -> second bounce parity: PASS")


def test_chain_stack_allows_other_priority_action_before_resolution():
    state = solver.State(
        turn=3,
        library=("Island",),
        hand=("Chain of Vapor",),
        battlefield=(
            solver.Perm("Island"),
            solver.Perm("Sol Ring"),
            solver.Perm("Sensei's Divining Top"),
        ),
        blue=1,
        rng_root_seed=20260826,
    )
    runtime = make_runtime_state(state)
    cast = _action(runtime, kind=MAIN_CAST_CHAIN, label_contains="Sol Ring")
    runtime = apply_main_action(runtime, cast)
    assert runtime.stack.objects
    chain_id = runtime.stack.top().object_id
    stack_count = len(runtime.stack.objects)

    top_draw = _action(runtime, kind=PRIORITY_ACTIVATE_TOP_DRAW)
    runtime = apply_main_action(runtime, top_draw)
    assert len(runtime.stack.objects) == stack_count + 1
    assert any(obj.object_id == chain_id for obj in runtime.stack.objects)
    assert runtime.stack.top().object_id != chain_id
    print("Chain stack permits typed priority activation before pass/resolution: PASS")





def _copy_request(state):
    runtime = _stage_chain_copy_choice(
        make_runtime_state(state),
        source_object_id="chain-smoke",
    )
    return rules_decision_request(
        runtime, horizon=6, policy_id="chain-visible-payoff-smoke"
    )


def test_chain_copy_declines_when_no_visible_payoff():
    request = _copy_request(solver.State(
        turn=4,
        library=("Island",),
        hand=(),
        battlefield=(
            solver.Perm("Island"),
            solver.Perm("Defense Grid"),
            solver.Perm("Pithing Needle"),
        ),
        blue=1,
        rng_root_seed=20260828,
    ))
    assert tuple(action.kind for action in request.actions) == (CHAIN_COPY_DECLINE,)
    print("Chain copy with no visible replay/downstream payoff -> decline only: PASS")


def test_chain_copy_collapses_land_cross_product():
    request = _copy_request(solver.State(
        turn=4,
        library=("Island",),
        hand=(),
        battlefield=(
            solver.Perm("Flooded Strand"),
            solver.Perm("Island"),
            solver.Perm("Ancient Tomb"),
            solver.Perm("Witching Well"),
        ),
        blue=1,
        rng_root_seed=20260828,
    ))
    commits = [action for action in request.actions if action.kind == CHAIN_COPY_COMMIT]
    assert len(commits) == 1, [action.label for action in request.actions]
    params = dict(commits[0].parameters)
    assert params["target_name"] == "Witching Well"
    assert params["land_name"] == "Flooded Strand", params
    assert "replay_scry2" in tuple(params["payoff_reasons"])
    print("Chain land x target Cartesian product -> one expendable land per target: PASS")


def test_chain_copy_retains_artifact_trigger_engine():
    request = _copy_request(solver.State(
        turn=4,
        library=("Island",),
        hand=(),
        battlefield=(
            solver.Perm("Island"),
            solver.Perm("Pithing Needle"),
            solver.Perm("Forensic Gadgeteer", sick=False),
        ),
        blue=1,
        rng_root_seed=20260828,
    ))
    commits = [action for action in request.actions if action.kind == CHAIN_COPY_COMMIT]
    assert len(commits) == 1
    params = dict(commits[0].parameters)
    assert params["target_name"] == "Pithing Needle"
    assert "gadgeteer_clue" in tuple(params["payoff_reasons"])
    print("Chain keeps cheap artifact recycle with visible Gadgeteer payoff: PASS")


def test_chain_copy_retains_mana_unlock_and_policy_uses_it():
    request = _copy_request(solver.State(
        turn=4,
        library=("Island",),
        hand=("Whir of Invention",),
        battlefield=(
            solver.Perm("Ancient Tomb"),
            solver.Perm(solver.COMMANDER, sick=False),
            solver.Perm("Tormod's Crypt", tapped=True),
        ),
        blue=2,
        urza=True,
        commander_in_command_zone=False,
        rng_root_seed=20260828,
    ))
    commits = [action for action in request.actions if action.kind == CHAIN_COPY_COMMIT]
    assert len(commits) == 1
    params = dict(commits[0].parameters)
    assert "mana_unlock:Whir of Invention" in tuple(params["payoff_reasons"])
    assert int(params["payoff_margin"]) > 0
    chosen = DeterministicRolloutPolicyV6().choose(
        request.observation, request.actions, request.context
    )
    assert chosen.kind == CHAIN_COPY_COMMIT, chosen
    print("Chain mana-positive zero replay unlocks visible Whir and beats decline: PASS")


def test_chain_copy_never_targets_urza_construct_or_tokens():
    request = _copy_request(solver.State(
        turn=4,
        library=("Island",),
        hand=(),
        battlefield=(
            solver.Perm("Island"),
            solver.Perm(solver.COMMANDER, sick=False),
            solver.Perm("Construct", mode="construct"),
            solver.Perm("Treasure", mode="treasure"),
            solver.Perm("Pithing Needle"),
            solver.Perm("Forensic Gadgeteer", sick=False),
        ),
        blue=1,
        urza=True,
        commander_in_command_zone=False,
        rng_root_seed=20260828,
    ))
    commits = [action for action in request.actions if action.kind == CHAIN_COPY_COMMIT]
    assert commits
    labels = " | ".join(action.label for action in commits)
    assert "Urza, Lord High Artificer" not in labels
    assert "Construct" not in labels
    assert "Treasure" not in labels
    assert any("Pithing Needle" in action.label for action in commits)
    print("Chain hard-prunes Urza, Construct, and expendable token bounce targets: PASS")


def test_offer_self_counter_two_treasures_matches_oracle():
    state = solver.State(
        turn=2,
        library=(),
        hand=("Dramatic Reversal", "An Offer You Can't Refuse"),
        battlefield=(),
        blue=3,
        rng_root_seed=20260826,
    )
    runtime = make_runtime_state(state)
    dramatic = _action(runtime, kind="main_cast_proactive_nonartifact", label_contains="Dramatic Reversal")
    runtime = apply_main_action(runtime, dramatic)
    offer = _action(runtime, kind=PRIORITY_CAST_OFFER_SELF, label_contains="Dramatic Reversal")
    runtime = apply_main_action(runtime, offer)
    runtime = apply_main_action(runtime, _pass(runtime))

    names = [perm.name for perm in runtime.true_state.battlefield]
    assert names.count("Treasure") == 2
    assert runtime.true_state.graveyard.count("Dramatic Reversal") == 1
    assert runtime.true_state.graveyard.count("An Offer You Can't Refuse") == 1
    assert not runtime.stack.objects

    oracle = solver.offer_actions(state)
    wanted = canonical_markov_state_key(runtime.true_state)
    assert any(canonical_markov_state_key(row) == wanted for row in oracle)
    print("Offer self-counter -> two simultaneous Treasures parity: PASS")


def main():
    test_chain_bounce_copy_matches_oracle_public_state()
    test_chain_stack_allows_other_priority_action_before_resolution()
    test_chain_copy_declines_when_no_visible_payoff()
    test_chain_copy_collapses_land_cross_product()
    test_chain_copy_retains_artifact_trigger_engine()
    test_chain_copy_retains_mana_unlock_and_policy_uses_it()
    test_chain_copy_never_targets_urza_construct_or_tokens()
    test_offer_self_counter_two_treasures_matches_oracle()
    print("PHASE5 CHAIN/OFFER PARITY SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
