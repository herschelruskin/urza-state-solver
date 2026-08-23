#!/usr/bin/env python3
"""Focused Phase-2 smokes for known-top access and FTT leveling."""

import urza_solver as solver
import non_oracle_rules_adapter as rules
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_runtime import ACTION_PASS_PRIORITY, make_runtime_state
from non_oracle_top_access_runtime import TOP_ZONE
from solver_architecture import InformationState


def _request(runtime):
    return rules.rules_decision_request(runtime, horizon=6)


def _top_actions(runtime):
    return [
        action for action in _request(runtime).actions
        if dict(action.parameters).get("from_zone") == TOP_ZONE
    ]


def _ftt_level_action(runtime):
    return next(
        action for action in _request(runtime).actions
        if action.kind == "main_level_fortune_tellers_talent"
    )


def _pass(runtime):
    return next(
        action for action in _request(runtime).actions
        if action.action_id == ACTION_PASS_PRIORITY
    )


def _chip_board(*extras):
    return (
        solver.Perm("The Reality Chip", mode="chip_attached"),
        solver.Perm("Faerie Mastermind"),
    ) + tuple(extras)


def _chip_runtime(*, library, hand=(), battlefield=(), blue=0, colorless=0, information=()):
    info = InformationState(known_top=tuple(information)) if information else InformationState()
    return make_runtime_state(
        solver.State(
            turn=2,
            library=tuple(library),
            hand=tuple(hand),
            battlefield=_chip_board(*battlefield),
            chip_attached=True,
            chip_target="Faerie Mastermind",
            blue=int(blue),
            colorless=int(colorless),
        ),
        info,
    )


def test_known_top_action_set_is_hidden_future_invariant():
    left = _chip_runtime(
        library=("Sol Ring", "SECRET_A", "TAIL"),
        colorless=1,
        information=("Sol Ring",),
    )
    right = _chip_runtime(
        library=("Sol Ring", "SECRET_B", "TAIL"),
        colorless=1,
        information=("Sol Ring",),
    )
    la = tuple(action.strategic_key() for action in _top_actions(left))
    ra = tuple(action.strategic_key() for action in _top_actions(right))
    assert la == ra and la
    assert "SECRET_A" not in repr(la) and "SECRET_B" not in repr(la)


def test_top_land_play_consumes_known_top_then_refreshes_continuous_look():
    runtime = _chip_runtime(
        library=("Island", "Basalt Monolith", "TAIL"),
        information=("Island",),
    )
    action = next(a for a in _top_actions(runtime) if a.kind == "main_play_land")
    runtime = rules.apply_main_action(runtime, action)
    assert runtime.true_state.land_played
    assert runtime.true_state.library == ("Basalt Monolith", "TAIL")
    assert solver.has(runtime.true_state, "Island")
    assert runtime.information.known_top[0] == "Basalt Monolith"


def test_top_seat_land_play_uses_typed_artifact_entry_stack():
    runtime = _chip_runtime(
        library=("Seat of the Synod", "Island"),
        battlefield=(solver.Perm("Grinding Station"),),
        information=("Seat of the Synod",),
    )
    action = next(a for a in _top_actions(runtime) if a.kind == "main_play_land")
    runtime = rules.apply_main_action(runtime, action)
    assert solver.has(runtime.true_state, "Seat of the Synod")
    assert runtime.information.known_top[0] == "Island"
    assert runtime.stack.top() is not None
    assert runtime.stack.top().kind == "etb_producer"


def test_top_artifact_cast_exposes_new_top_before_trigger_order_choice():
    runtime = make_runtime_state(
        solver.State(
            turn=2,
            library=("Tormod's Crypt", "Basalt Monolith", "TAIL"),
            hand=(),
            battlefield=(
                solver.Perm("The Reality Chip", mode="chip_attached"),
                solver.Perm("Artificer's Assistant"),
                solver.Perm("Uthros Research Craft"),
            ),
            chip_attached=True,
            chip_target="Artificer's Assistant",
            uthros_counters=3,
        ),
        InformationState(known_top=("Tormod's Crypt",)),
    )
    action = next(a for a in _top_actions(runtime) if dict(a.parameters)["card"] == "Tormod's Crypt")
    runtime = rules.apply_main_action(runtime, action)
    assert runtime.true_state.library == ("Basalt Monolith", "TAIL")
    assert runtime.information.known_top[0] == "Basalt Monolith"
    assert runtime.pending is not None
    assert runtime.pending.kind == "runtime_stack_order"
    kinds = {obj.kind for obj in dict(runtime.pending.payload)["objects"]}
    assert kinds == {"assistant_scry_1", "uthros_draw_and_counter"}


def test_cage_blocks_top_artifact_cast_but_not_top_land_play():
    artifact = _chip_runtime(
        library=("Sol Ring", "TAIL"),
        battlefield=(solver.Perm("Grafdigger's Cage"),),
        colorless=1,
        information=("Sol Ring",),
    )
    assert not _top_actions(artifact)

    land = _chip_runtime(
        library=("Island", "TAIL"),
        battlefield=(solver.Perm("Grafdigger's Cage"),),
        information=("Island",),
    )
    assert any(a.kind == "main_play_land" for a in _top_actions(land))


def test_top_chalice_commits_multikicker_then_resolves_with_exact_counters():
    runtime = _chip_runtime(
        library=("Everflowing Chalice", "TAIL"),
        colorless=2,
        information=("Everflowing Chalice",),
    )
    action = next(
        a for a in _top_actions(runtime)
        if dict(a.parameters).get("kicks") == 1
    )
    runtime = rules.apply_main_action(runtime, action)
    assert runtime.true_state.colorless == 0
    assert runtime.true_state.library == ("TAIL",)
    assert runtime.stack.top().card == "Everflowing Chalice"
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    chalice = next(p for p in runtime.true_state.battlefield if p.name == "Everflowing Chalice")
    assert chalice.counters == 1


def test_top_mox_diamond_preserves_entry_replacement_decision():
    runtime = _chip_runtime(
        library=("Mox Diamond", "TAIL"),
        hand=("Island",),
        information=("Mox Diamond",),
    )
    action = next(a for a in _top_actions(runtime) if dict(a.parameters)["card"] == "Mox Diamond")
    runtime = rules.apply_main_action(runtime, action)
    assert runtime.true_state.library == ("TAIL",)
    assert not solver.has(runtime.true_state, "Mox Diamond")
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.pending is not None
    assert runtime.pending.kind == "runtime_mox_diamond_entry"
    discard = next(
        a for a in _request(runtime).actions
        if dict(a.parameters).get("land") == "Island"
    )
    runtime = rules.apply_main_action(runtime, discard)
    assert solver.has(runtime.true_state, "Mox Diamond")
    assert "Island" in runtime.true_state.graveyard


def test_ftt_level_two_requires_a_spell_cast_this_turn_for_top_access():
    def build(cast):
        return make_runtime_state(
            solver.State(
                turn=2,
                library=("Sol Ring", "TAIL"),
                hand=(),
                battlefield=(solver.Perm("Fortune Teller's Talent"),),
                ftt_level=2,
                spell_cast_this_turn=bool(cast),
                colorless=1,
            ),
            InformationState(known_top=("Sol Ring",)),
        )
    assert not _top_actions(build(False))
    assert _top_actions(build(True))


def test_ftt_resolution_immediately_refreshes_continuous_top_look():
    runtime = make_runtime_state(
        solver.State(
            turn=2,
            library=("Basalt Monolith", "TAIL"),
            hand=("Fortune Teller's Talent",),
            battlefield=(),
            colorless=3,
            blue=1,
        )
    )
    cast = next(
        a for a in _request(runtime).actions
        if a.kind == "main_cast_proactive_nonartifact"
        and dict(a.parameters).get("card") == "Fortune Teller's Talent"
    )
    runtime = rules.apply_main_action(runtime, cast)
    assert not runtime.information.known_top
    runtime = rules.apply_main_action(runtime, _pass(runtime))
    assert runtime.true_state.ftt_level == 1
    assert runtime.information.known_top[0] == "Basalt Monolith"


def test_ftt_level_one_to_two_pays_cost_and_enables_live_top_access():
    runtime = make_runtime_state(
        solver.State(
            turn=2,
            library=("Sol Ring", "TAIL"),
            hand=(),
            battlefield=(solver.Perm("Fortune Teller's Talent"),),
            ftt_level=1,
            spell_cast_this_turn=True,
            colorless=3,
            blue=1,
        ),
        InformationState(known_top=("Sol Ring",)),
    )
    action = _ftt_level_action(runtime)
    assert dict(action.parameters)["to_level"] == 2
    runtime = rules.apply_main_action(runtime, action)
    assert runtime.true_state.ftt_level == 2
    assert runtime.true_state.colorless == 0 and runtime.true_state.blue == 0
    assert not runtime.stack.objects and runtime.pending is None
    assert any(
        dict(a.parameters).get("from_zone") == TOP_ZONE
        and dict(a.parameters).get("card") == "Sol Ring"
        for a in _request(runtime).actions
    )


def test_ftt_level_two_to_three_unlocks_outside_cost_reduction():
    runtime = make_runtime_state(
        solver.State(
            turn=2,
            library=("Basalt Monolith", "TAIL"),
            hand=(),
            battlefield=(solver.Perm("Fortune Teller's Talent"),),
            ftt_level=2,
            spell_cast_this_turn=True,
            colorless=3,
            blue=1,
        ),
        InformationState(known_top=("Basalt Monolith",)),
    )
    action = _ftt_level_action(runtime)
    assert dict(action.parameters)["to_level"] == 3
    runtime = rules.apply_main_action(runtime, action)
    assert runtime.true_state.ftt_level == 3
    assert runtime.true_state.colorless == 1 and runtime.true_state.blue == 0
    top = [
        a for a in _top_actions(runtime)
        if dict(a.parameters).get("card") == "Basalt Monolith"
    ]
    assert top
    assert dict(top[0].parameters)["generic_cost"] == 1


def test_ftt_level_action_is_hidden_future_invariant():
    def build(hidden):
        return make_runtime_state(
            solver.State(
                turn=2,
                library=("Sol Ring", hidden),
                hand=(),
                battlefield=(solver.Perm("Fortune Teller's Talent"),),
                ftt_level=1,
                spell_cast_this_turn=True,
                colorless=3,
                blue=1,
            ),
            InformationState(known_top=("Sol Ring",)),
        )
    left = _ftt_level_action(build("SECRET_A"))
    right = _ftt_level_action(build("SECRET_B"))
    assert left.strategic_key() == right.strategic_key()
    assert "SECRET_A" not in repr(left) and "SECRET_B" not in repr(right)


def test_base_policy_prefers_live_level_two_access_over_ending_turn():
    runtime = make_runtime_state(
        solver.State(
            turn=2,
            library=("Sol Ring", "TAIL"),
            hand=(),
            battlefield=(solver.Perm("Fortune Teller's Talent"),),
            ftt_level=1,
            spell_cast_this_turn=True,
            colorless=3,
            blue=1,
        ),
        InformationState(known_top=("Sol Ring",)),
    )
    policy = DeterministicBasePolicy()
    request = rules.rules_decision_request(runtime, horizon=6, policy_id=policy.policy_id)
    choice = policy.choose_request(request)
    assert choice.kind == "main_level_fortune_tellers_talent"


def test_base_policy_uses_known_top_fast_mana_before_ending_turn():
    runtime = _chip_runtime(
        library=("Sol Ring", "TAIL"),
        colorless=1,
        information=("Sol Ring",),
    )
    policy = DeterministicBasePolicy()
    request = rules.rules_decision_request(runtime, horizon=6, policy_id=policy.policy_id)
    choice = policy.choose_request(request)
    assert dict(choice.parameters).get("from_zone") == TOP_ZONE
    assert dict(choice.parameters).get("card") == "Sol Ring"


def main():
    tests = (
        test_known_top_action_set_is_hidden_future_invariant,
        test_top_land_play_consumes_known_top_then_refreshes_continuous_look,
        test_top_seat_land_play_uses_typed_artifact_entry_stack,
        test_top_artifact_cast_exposes_new_top_before_trigger_order_choice,
        test_cage_blocks_top_artifact_cast_but_not_top_land_play,
        test_top_chalice_commits_multikicker_then_resolves_with_exact_counters,
        test_top_mox_diamond_preserves_entry_replacement_decision,
        test_ftt_level_two_requires_a_spell_cast_this_turn_for_top_access,
        test_ftt_resolution_immediately_refreshes_continuous_top_look,
        test_ftt_level_one_to_two_pays_cost_and_enables_live_top_access,
        test_ftt_level_two_to_three_unlocks_outside_cost_reduction,
        test_ftt_level_action_is_hidden_future_invariant,
        test_base_policy_prefers_live_level_two_access_over_ending_turn,
        test_base_policy_uses_known_top_fast_mana_before_ending_turn,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("TOP ACCESS / FTT RUNTIME SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
