#!/usr/bin/env python3
"""Focused Phase-1 smoke for Cephalid Coliseum draw/discard staging."""

from dataclasses import replace

import urza_solver as solver
from solver_architecture import InformationState
from decision_observation import DrawObservation
from random_observation_adapters import (
    COLISEUM,
    coliseum_discard_request,
    coliseum_threshold_request,
    information_after_coliseum_draw,
    resolve_coliseum_discard,
    resolve_coliseum_threshold,
)


def seven_card_graveyard():
    return tuple(f"G{i}" for i in range(7))


def choose(request, **params):
    for action in request.actions:
        values = dict(action.parameters)
        if all(values.get(k) == v for k, v in params.items()):
            return action
    raise AssertionError(f"no action matching {params!r}")


def test_coliseum_commit_is_hidden_future_invariant():
    cards = ("A", "B", "C", "D")
    base = solver.State(
        turn=3,
        library=cards,
        hand=("Keep",),
        battlefield=(solver.Perm(COLISEUM),),
        graveyard=seven_card_graveyard(),
        blue=1,
        rng_root_seed=20260822,
    )
    other = replace(base, library=tuple(reversed(cards)))
    info = InformationState()
    req_a = coliseum_threshold_request(base, info, horizon=6)
    req_b = coliseum_threshold_request(other, info, horizon=6)
    assert req_a.observation == req_b.observation
    assert tuple(a.canonical_key() for a in req_a.actions) == tuple(
        a.canonical_key() for a in req_b.actions
    )
    assert len(req_a.actions) == 1
    assert "A" not in repr(req_a.actions[0].parameters)


def test_coliseum_draw_observation_occurs_after_costs_and_before_discard_choice():
    state = solver.State(
        turn=3,
        library=("Draw1", "Draw2", "Draw3", "Tail"),
        hand=("Keep",),
        battlefield=(solver.Perm(COLISEUM),),
        graveyard=seven_card_graveyard(),
        blue=1,
        rng_root_seed=20260822,
    )
    prior = InformationState(known_top=("Draw1", "Draw2", "Draw3"))
    action = coliseum_threshold_request(state, prior, horizon=6).actions[0]
    env = resolve_coliseum_threshold(state, action)
    assert not any(p.name == COLISEUM for p in env.true_state.battlefield)
    assert COLISEUM in env.true_state.graveyard
    assert env.true_state.blue == 0
    assert tuple(e.card for e in env.observations.events if isinstance(e, DrawObservation)) == (
        "Draw1", "Draw2", "Draw3"
    )
    assert env.pending_decision is not None
    assert env.pending_decision.kind == "coliseum_discard"
    updated = information_after_coliseum_draw(prior, env)
    assert updated.known_top == ()


def test_coliseum_discard_choices_can_depend_on_observed_draws():
    state = solver.State(
        turn=3,
        library=("Tail",),
        hand=("Keep", "Draw1", "Draw2", "Draw3"),
        battlefield=(),
        graveyard=seven_card_graveyard() + (COLISEUM,),
    )
    req = coliseum_discard_request(state, InformationState(), horizon=6)
    packages = tuple(dict(a.parameters)["cards"] for a in req.actions)
    assert ("Draw1", "Draw2", "Draw3") in packages
    assert ("Draw1", "Draw2", "Keep") in packages
    chosen = choose(req, cards=("Draw1", "Draw2", "Draw3"))
    final = resolve_coliseum_discard(state, chosen)
    assert final.true_state.hand == ("Keep",)
    assert final.true_state.graveyard[-3:] == ("Draw1", "Draw2", "Draw3")


def main():
    tests = [
        test_coliseum_commit_is_hidden_future_invariant,
        test_coliseum_draw_observation_occurs_after_costs_and_before_discard_choice,
        test_coliseum_discard_choices_can_depend_on_observed_draws,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("RANDOM OBSERVATION ADAPTERS SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
