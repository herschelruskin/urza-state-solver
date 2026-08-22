#!/usr/bin/env python3
"""Focused smokes for the proactive nonartifact cast layer."""

from dataclasses import replace

import urza_solver as solver
from non_oracle_proactive_spell_adapter import MAIN_CAST_PROACTIVE_NONARTIFACT
from non_oracle_rules_adapter import apply_main_action, rules_decision_request
from non_oracle_runtime import ACTION_PASS_PRIORITY, make_runtime_state


def actions(runtime, *, card=None):
    request = rules_decision_request(runtime, horizon=6)
    rows = [a for a in request.actions if a.kind == MAIN_CAST_PROACTIVE_NONARTIFACT]
    if card is not None:
        rows = [a for a in rows if dict(a.parameters).get("card") == card]
    return rows


def pass_action(runtime):
    request = rules_decision_request(runtime, horizon=6)
    return next(a for a in request.actions if a.action_id == ACTION_PASS_PRIORITY)


def resolve_until_main(runtime, limit=20):
    for _ in range(limit):
        if runtime.pending is None and not runtime.stack.objects:
            return runtime
        request = rules_decision_request(runtime, horizon=6)
        if not request.actions:
            raise AssertionError("runtime stopped with unresolved proactive stack")
        runtime = apply_main_action(runtime, request.actions[0])
    raise AssertionError("proactive stack did not settle")


def test_action_set_is_hidden_future_invariant():
    battlefield = (solver.Perm("Basalt Monolith"), solver.Perm("Forensic Gadgeteer"))
    left = make_runtime_state(solver.State(
        turn=3, library=("SECRET_A", "SECRET_B"),
        hand=("Power Artifact", "Retraction Helix"), battlefield=battlefield,
        blue=3, colorless=2,
    ))
    right = make_runtime_state(solver.State(
        turn=3, library=("SECRET_B", "SECRET_A"),
        hand=("Power Artifact", "Retraction Helix"), battlefield=battlefield,
        blue=3, colorless=2,
    ))
    assert tuple(a.strategic_key() for a in actions(left)) == tuple(
        a.strategic_key() for a in actions(right)
    )
    assert "SECRET_A" not in repr(actions(left)) and "SECRET_B" not in repr(actions(left))


def test_engine_permanent_is_not_on_battlefield_until_spell_resolves():
    runtime = make_runtime_state(solver.State(
        turn=2, library=("Island",), hand=("Forensic Gadgeteer",), battlefield=(),
        blue=1, colorless=2,
    ))
    action = actions(runtime, card="Forensic Gadgeteer")[0]
    runtime = apply_main_action(runtime, action)
    assert "Forensic Gadgeteer" not in [p.name for p in runtime.true_state.battlefield]
    assert runtime.stack.top().kind == "proactive_engine_permanent_spell"
    runtime = apply_main_action(runtime, pass_action(runtime))
    assert "Forensic Gadgeteer" in [p.name for p in runtime.true_state.battlefield]


def test_tezzeret_cast_puts_assistant_historic_trigger_above_spell():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("GOOD", "TAIL"),
        hand=("Tezzeret, Cruel Captain",),
        battlefield=(solver.Perm("Artificer's Assistant"),),
        blue=0,
        colorless=3,
    ))
    action = actions(runtime, card="Tezzeret, Cruel Captain")[0]
    runtime = apply_main_action(runtime, action)
    assert [obj.kind for obj in runtime.stack.objects] == [
        "assistant_scry_1", "proactive_engine_permanent_spell"
    ]
    runtime = apply_main_action(runtime, pass_action(runtime))
    assert runtime.pending is not None
    assert runtime.information.known_top[0] == "GOOD"
    assert not any(p.name == "Tezzeret, Cruel Captain" for p in runtime.true_state.battlefield)


def test_power_artifact_target_is_committed_and_applied_on_resolution():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Island",),
        hand=("Power Artifact",),
        battlefield=(solver.Perm("Basalt Monolith"), solver.Perm("Sol Ring")),
        blue=2,
        colorless=0,
    ))
    pa_actions = actions(runtime, card="Power Artifact")
    basalt = next(a for a in pa_actions if "Basalt Monolith" in a.label)
    runtime = apply_main_action(runtime, basalt)
    assert runtime.true_state.pa_target == ""
    runtime = resolve_until_main(runtime)
    assert runtime.true_state.pa_target == "Basalt Monolith"
    assert any(p.name == "Power Artifact" for p in runtime.true_state.battlefield)


def test_retraction_helix_grants_exact_target_until_end_of_turn_state():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Island",),
        hand=("Retraction Helix",),
        battlefield=(solver.Perm("Forensic Gadgeteer"), solver.Perm("Artificer's Assistant")),
        blue=1,
        colorless=0,
    ))
    helix_actions = actions(runtime, card="Retraction Helix")
    gadget = next(a for a in helix_actions if "Forensic Gadgeteer" in a.label)
    runtime = resolve_until_main(apply_main_action(runtime, gadget))
    granted = [p for p in runtime.true_state.battlefield if p.knack_granted]
    assert len(granted) == 1 and granted[0].name == "Forensic Gadgeteer"
    assert "Retraction Helix" in runtime.true_state.graveyard


def test_dramatic_reversal_resolves_through_stack_and_untaps_nonlands():
    runtime = make_runtime_state(solver.State(
        turn=3,
        library=("Island",),
        hand=("Dramatic Reversal",),
        battlefield=(
            solver.Perm("Island", tapped=True),
            solver.Perm("Sol Ring", tapped=True),
            solver.Perm("Basalt Monolith", tapped=True),
        ),
        blue=1,
        colorless=1,
    ))
    action = actions(runtime, card="Dramatic Reversal")[0]
    runtime = apply_main_action(runtime, action)
    assert next(p for p in runtime.true_state.battlefield if p.name == "Sol Ring").tapped
    runtime = resolve_until_main(runtime)
    island = next(p for p in runtime.true_state.battlefield if p.name == "Island")
    ring = next(p for p in runtime.true_state.battlefield if p.name == "Sol Ring")
    basalt = next(p for p in runtime.true_state.battlefield if p.name == "Basalt Monolith")
    assert island.tapped
    assert not ring.tapped and not basalt.tapped
    assert "Dramatic Reversal" in runtime.true_state.graveyard


def main():
    tests = (
        test_action_set_is_hidden_future_invariant,
        test_engine_permanent_is_not_on_battlefield_until_spell_resolves,
        test_tezzeret_cast_puts_assistant_historic_trigger_above_spell,
        test_power_artifact_target_is_committed_and_applied_on_resolution,
        test_retraction_helix_grants_exact_target_until_end_of_turn_state,
        test_dramatic_reversal_resolves_through_stack_and_untaps_nonlands,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("PROACTIVE NONARTIFACT SPELL SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
