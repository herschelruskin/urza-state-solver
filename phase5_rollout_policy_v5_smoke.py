#!/usr/bin/env python3
"""Focused regression smokes for Phase-5 commitment-aware rollout V5."""

import urza_solver as solver
from non_oracle_chain_offer_runtime import CHAIN_COPY_DECLINE, MAIN_CAST_CHAIN
from non_oracle_rules_adapter_v2 import apply_main_action, rules_decision_request
from non_oracle_runtime import make_runtime_state
from phase5_rollout_policy_v5 import DeterministicRolloutPolicyV5

POLICY = DeterministicRolloutPolicyV5()


def _request(runtime):
    return rules_decision_request(runtime, horizon=6, policy_id=POLICY.policy_id)


def _choose(runtime):
    request = _request(runtime)
    return POLICY.choose(request.observation, request.actions, request.context)


def _action(runtime, *, kind, label_contains=""):
    rows = [a for a in _request(runtime).actions if a.kind == kind]
    if label_contains:
        rows = [a for a in rows if label_contains in a.label]
    if not rows:
        raise AssertionError(f"no action kind={kind!r} label={label_contains!r}")
    return sorted(rows, key=lambda a: a.action_id)[0]


def test_transmute_target_avoids_unpayable_bin():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("The One Ring", "Tormod's Crypt", "Island"),
        hand=("Transmute Artifact",),
        battlefield=(solver.Perm("Construct", mode="construct"),),
        blue=2,
    ))
    runtime = apply_main_action(runtime, _action(runtime, kind="main_use_transmute_artifact"))
    runtime = apply_main_action(runtime, _action(runtime, kind="pass_priority"))
    runtime = apply_main_action(runtime, _action(runtime, kind="transmute_choose_sacrifice", label_contains="Construct"))
    request = _request(runtime)
    ring = next(a for a in request.actions if dict(a.parameters).get("target") == "The One Ring")
    crypt = next(a for a in request.actions if dict(a.parameters).get("target") == "Tormod's Crypt")
    assert dict(ring.parameters)["difference"] == 4
    assert dict(ring.parameters)["can_pay_difference"] is False
    assert dict(crypt.parameters)["difference"] == 0
    assert dict(crypt.parameters)["can_pay_difference"] is True
    chosen = POLICY.choose(request.observation, request.actions, request.context)
    assert dict(chosen.parameters).get("target") == "Tormod's Crypt"
    runtime = apply_main_action(runtime, chosen)
    assert any(p.name == "Tormod's Crypt" for p in runtime.true_state.battlefield)
    assert "The One Ring" not in runtime.true_state.graveyard
    print("V5 Transmute target commitment feasibility: PASS")


def test_transmute_pays_difference_when_payment_is_available():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("The One Ring", "Island"),
        hand=("Transmute Artifact",),
        battlefield=(solver.Perm("Sapphire Medallion"),),
        blue=4,
    ))
    runtime = apply_main_action(runtime, _action(runtime, kind="main_use_transmute_artifact"))
    runtime = apply_main_action(runtime, _action(runtime, kind="pass_priority"))
    runtime = apply_main_action(
        runtime,
        _action(runtime, kind="transmute_choose_sacrifice", label_contains="Sapphire Medallion"),
    )
    runtime = apply_main_action(
        runtime,
        _action(runtime, kind="transmute_choose_target", label_contains="The One Ring"),
    )
    request = _request(runtime)
    rows = [a for a in request.actions if a.kind == "transmute_pay_difference"]
    assert any(a.label.startswith("Pay ") for a in rows)
    assert any("Decline" in a.label for a in rows)
    chosen = POLICY.choose(request.observation, request.actions, request.context)
    assert chosen.kind == "transmute_pay_difference"
    assert chosen.label.startswith("Pay "), chosen.label
    runtime = apply_main_action(runtime, chosen)
    assert any(p.name == "The One Ring" for p in runtime.true_state.battlefield)
    assert "The One Ring" not in runtime.true_state.graveyard
    print("V5 Transmute payable difference is never voluntarily binned: PASS")


def test_transmute_sacrifice_prefers_real_mv_over_construct():
    runtime = make_runtime_state(solver.State(
        turn=2,
        library=("Grim Monolith", "Island"),
        hand=("Transmute Artifact",),
        battlefield=(
            solver.Perm("Construct", mode="construct"),
            solver.Perm("Sapphire Medallion"),
        ),
        blue=2,
    ))
    runtime = apply_main_action(runtime, _action(runtime, kind="main_use_transmute_artifact"))
    runtime = apply_main_action(runtime, _action(runtime, kind="pass_priority"))
    chosen = _choose(runtime)
    assert chosen.kind == "transmute_choose_sacrifice"
    assert "Sapphire Medallion" in chosen.label
    print("V5 Transmute sacrifice MV discipline: PASS")


def test_chain_declines_suicidal_copy_without_producer():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=(),
        hand=("Chain of Vapor",),
        battlefield=(
            solver.Perm("Island"),
            solver.Perm("Sol Ring"),
            solver.Perm("Witching Well"),
        ),
        blue=1,
    ))
    runtime = apply_main_action(runtime, _action(runtime, kind=MAIN_CAST_CHAIN, label_contains="Sol Ring"))
    runtime = apply_main_action(runtime, _action(runtime, kind="pass_priority"))
    chosen = _choose(runtime)
    assert chosen.kind == CHAIN_COPY_DECLINE
    runtime = apply_main_action(runtime, chosen)
    assert any(p.name == "Island" for p in runtime.true_state.battlefield)
    assert any(p.name == "Witching Well" for p in runtime.true_state.battlefield)
    print("V5 Chain optional-copy discipline: PASS")


def test_colorless_mana_enables_visible_artifact():
    runtime = make_runtime_state(solver.State(
        turn=1,
        library=("Island",),
        hand=("Sensei's Divining Top", "Rhystic Study"),
        battlefield=(solver.Perm("Ancient Tomb"),),
    ))
    chosen = _choose(runtime)
    assert chosen.kind == "main_mana_action"
    assert "Ancient Tomb" in chosen.label
    runtime = apply_main_action(runtime, chosen)
    chosen = _choose(runtime)
    assert chosen.kind == "main_cast_artifact"
    assert "Sensei's Divining Top" in chosen.label
    print("V5 colorless development despite blue long-term goal: PASS")


def main():
    test_transmute_target_avoids_unpayable_bin()
    test_transmute_pays_difference_when_payment_is_available()
    test_transmute_sacrifice_prefers_real_mv_over_construct()
    test_chain_declines_suicidal_copy_without_producer()
    test_colorless_mana_enables_visible_artifact()
    print("PHASE5 ROLLOUT V5 SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
