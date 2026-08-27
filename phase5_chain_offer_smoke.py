#!/usr/bin/env python3
"""Focused typed-runtime parity checks for Chain of Vapor and self-Offer."""

import urza_solver as solver
from non_oracle_chain_offer_runtime import (
    CHAIN_COPY_COMMIT,
    MAIN_CAST_CHAIN,
    PRIORITY_CAST_OFFER_SELF,
)
from non_oracle_rules_adapter_v2 import apply_main_action, rules_decision_request
from non_oracle_runtime import make_runtime_state
from non_oracle_top_draw_runtime import PRIORITY_ACTIVATE_TOP_DRAW
from solver_architecture import canonical_markov_state_key


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
        blue=1,
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
    test_offer_self_counter_two_treasures_matches_oracle()
    print("PHASE5 CHAIN/OFFER PARITY SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
