#!/usr/bin/env python3
"""Focused Phase-1 regressions for staged Transmute Artifact resolution."""

from dataclasses import replace

import urza_solver as solver
from solver_architecture import InformationState
from decision_observation import SearchZoneObservation, ShuffleObservation
from transmute_artifact_adapter import (
    CARD,
    information_after_transmute_transition,
    resolve_transmute_cast,
    resolve_transmute_payment,
    resolve_transmute_sacrifice,
    resolve_transmute_target,
    transmute_cast_request,
    transmute_difference_payment_options,
    transmute_payment_intents,
    transmute_sacrifice_request,
    transmute_target_request,
)


def clue():
    return solver.Perm("Clue", mode="clue")


def base_state(library, *, battlefield=None, blue=2, colorless=0):
    if battlefield is None:
        battlefield=(clue(), solver.Perm("Mana Vault"))
    return solver.State(
        turn=2,
        library=tuple(library),
        hand=(CARD, "Island"),
        battlefield=tuple(battlefield),
        blue=blue,
        colorless=colorless,
        rng_root_seed=20260822,
    )


def choose_sacrifice(request, name):
    for action in request.actions:
        signature = tuple(dict(action.parameters)["signature"])
        if signature[0] == name:
            return action
    raise AssertionError(f"no sacrifice action for {name}")


def choose_target(request, target):
    return next(
        action for action in request.actions
        if dict(action.parameters).get("target") == target
    )


def stage_to_search(state, *, sacrifice_name="Clue"):
    info=InformationState()
    cast_req=transmute_cast_request(state,info,horizon=6,policy_id="smoke")
    cast=cast_req.actions[0]
    cast_env=resolve_transmute_cast(state,cast)
    sac_req=transmute_sacrifice_request(cast_env.true_state,info,horizon=6,policy_id="smoke")
    sac=choose_sacrifice(sac_req,sacrifice_name)
    sac_env,context,search=resolve_transmute_sacrifice(cast_env.true_state,sac)
    info2=information_after_transmute_transition(info,sac_env)
    target_req=transmute_target_request(sac_env.true_state,info2,search,horizon=6,policy_id="smoke")
    return cast_env,sac_env,context,search,target_req,info2


def test_cast_commit_is_hidden_future_invariant():
    cards=("Basalt Monolith","Sensei's Divining Top","Sol Ring","Tail")
    a=base_state(cards)
    b=base_state(tuple(reversed(cards)))
    info=InformationState()
    req_a=transmute_cast_request(a,info,horizon=6,policy_id="smoke")
    req_b=transmute_cast_request(b,info,horizon=6,policy_id="smoke")
    assert req_a.observation == req_b.observation
    assert tuple(x.canonical_key() for x in req_a.actions)==tuple(
        x.canonical_key() for x in req_b.actions
    )
    assert len(req_a.actions)==1
    assert "Basalt Monolith" not in repr(req_a.actions[0].parameters)


def test_uu_is_paid_before_resolution_but_sacrifice_is_not():
    state=base_state(("Basalt Monolith","Sol Ring","Tail"))
    info=InformationState()
    action=transmute_cast_request(state,info,horizon=6).actions[0]
    env=resolve_transmute_cast(state,action)
    assert env.true_state.blue==0
    assert CARD not in env.true_state.hand
    assert CARD in env.true_state.graveyard
    assert any(p.mode=="clue" for p in env.true_state.battlefield), (
        "Transmute incorrectly sacrificed an artifact as a casting cost"
    )
    assert env.pending_decision is not None
    assert env.pending_decision.kind=="transmute_choose_sacrifice"


def test_sacrifice_choice_occurs_before_search_observation():
    state=base_state(("Basalt Monolith","Sol Ring","Tail"))
    cast_env,sac_env,context,search,target_req,_=stage_to_search(state)
    assert context.sacrificed_mv==0
    assert context.sacrificed_mode=="clue"
    assert not any(p.mode=="clue" for p in sac_env.true_state.battlefield)
    assert isinstance(search,SearchZoneObservation)
    assert search.may_fail_to_find is True
    assert search.legal_cards==tuple(sorted(set(search.legal_cards)))
    assert "Basalt Monolith" in search.legal_cards
    assert "Basalt Monolith" in tuple(
        dict(action.parameters)["target"] for action in target_req.actions
    )


def test_search_target_set_is_permutation_invariant_after_commit_and_sacrifice():
    cards=("Basalt Monolith","Sensei's Divining Top","Sol Ring","Tail")
    a=base_state(cards)
    b=base_state(("Tail","Sol Ring","Basalt Monolith","Sensei's Divining Top"))
    _,_,_,search_a,target_a,_=stage_to_search(a)
    _,_,_,search_b,target_b,_=stage_to_search(b)
    assert search_a.legal_cards==search_b.legal_cards
    assert tuple((x.kind,x.parameters,x.equivalence_key) for x in target_a.actions)==tuple(
        (x.kind,x.parameters,x.equivalence_key) for x in target_b.actions
    )


def test_difference_can_use_mana_ability_during_resolution_not_only_floating_mana():
    # UU is fully spent to cast Transmute.  Sacrificing a Clue (MV 0) then finding
    # Basalt Monolith (MV 3) asks for 3.  Mana Vault is still untapped and its
    # mana ability may be activated during resolution to make CCC for that payment.
    state=base_state(
        ("Basalt Monolith","Sensei's Divining Top","Tail"),
        battlefield=(clue(),solver.Perm("Mana Vault")),
        blue=2,
        colorless=0,
    )
    _,sac_env,context,search,target_req,_=stage_to_search(state)
    target=choose_target(target_req,"Basalt Monolith")
    target_env,target_context,payment_options=resolve_transmute_target(
        sac_env.true_state,context,search,target
    )
    assert target_context.difference==3
    assert target_env.true_state.blue==0 and target_env.true_state.colorless==0
    assert payment_options, "no during-resolution mana payment plan was generated"
    plans=[dict(action.parameters)["mana_steps"] for action,_ in payment_options]
    assert any(any("Mana Vault" in step for step in plan) for plan in plans), plans
    intents=transmute_payment_intents(payment_options,target_context.difference)
    assert any(dict(action.parameters).get("choice")=="pay" for action in intents)
    assert any(dict(action.parameters).get("choice")=="decline" for action in intents)


def test_searched_target_cannot_pay_its_own_difference():
    # The found Mana Vault has MV 1.  Sacrificing a Clue (MV 0) therefore asks
    # for a difference payment of 1.  The found Vault is still the searched card,
    # not a battlefield permanent, so with no other mana sources there must be no
    # pay option: it cannot fund even its own {1} difference.
    state=base_state(
        ("Mana Vault","Sensei's Divining Top","Tail"),
        battlefield=(clue(),),
        blue=2,
        colorless=0,
    )
    _,sac_env,context,search,target_req,_=stage_to_search(state)
    target=choose_target(target_req,"Mana Vault")
    target_env,target_context,payment_options=resolve_transmute_target(
        sac_env.true_state,context,search,target
    )
    assert target_context.difference==1
    assert "Mana Vault" not in target_env.true_state.library
    assert not any(p.name=="Mana Vault" for p in target_env.true_state.battlefield)
    assert payment_options==(), "searched Mana Vault illegally funded its own payment"
    intents=transmute_payment_intents(payment_options,target_context.difference)
    assert len(intents)==1
    assert dict(intents[0].parameters)["choice"]=="decline"


def test_paid_target_enters_then_shuffle_clears_old_position_knowledge():
    state=base_state(
        ("Basalt Monolith","Sensei's Divining Top","Sol Ring","Tail"),
        battlefield=(clue(),solver.Perm("Mana Vault")),
        blue=2,
        colorless=0,
    )
    prior=InformationState(
        known_top=("Basalt Monolith",),
        known_bottom=("Tail",),
        shuffle_epoch=4,
    )
    # The root policy may know the top in this test; stage manually while preserving it.
    cast=transmute_cast_request(state,prior,horizon=6).actions[0]
    cast_env=resolve_transmute_cast(state,cast)
    sac_req=transmute_sacrifice_request(cast_env.true_state,prior,horizon=6)
    sac=choose_sacrifice(sac_req,"Clue")
    sac_env,context,search=resolve_transmute_sacrifice(cast_env.true_state,sac)
    target_req=transmute_target_request(sac_env.true_state,prior,search,horizon=6)
    target=choose_target(target_req,"Basalt Monolith")
    target_env,target_context,payment_options=resolve_transmute_target(
        sac_env.true_state,context,search,target
    )
    pay_action,pay_state=next(
        (a,s) for a,s in payment_options
        if any("Mana Vault" in step for step in dict(a.parameters)["mana_steps"])
    )
    final=resolve_transmute_payment(target_env.true_state,target_context,pay_action)
    assert any(p.name=="Basalt Monolith" for p in final.true_state.battlefield)
    assert final.pending_decision is not None
    assert final.pending_decision.kind=="resolve_entered_artifact_triggers"
    assert any(isinstance(event,ShuffleObservation) for event in final.observations.events)
    updated=information_after_transmute_transition(prior,final)
    assert updated.known_top==()
    assert updated.known_bottom==()
    assert updated.shuffle_epoch==5


def test_decline_moves_target_to_graveyard_then_shuffles():
    state=base_state(
        ("Mana Vault","Sensei's Divining Top","Tail"),
        battlefield=(clue(),),
        blue=2,
        colorless=0,
    )
    _,sac_env,context,search,target_req,_=stage_to_search(state)
    target=choose_target(target_req,"Mana Vault")
    target_env,target_context,payment_options=resolve_transmute_target(
        sac_env.true_state,context,search,target
    )
    decline=transmute_payment_intents(payment_options,target_context.difference)[0]
    final=resolve_transmute_payment(target_env.true_state,target_context,decline)
    assert "Mana Vault" in final.true_state.graveyard
    assert "Mana Vault" not in final.true_state.library
    assert not any(p.name=="Mana Vault" for p in final.true_state.battlefield)
    assert final.pending_decision is None
    assert any(isinstance(event,ShuffleObservation) for event in final.observations.events)


def test_existing_floating_mana_remains_a_legal_difference_payment_plan():
    # Unit-level check: if resolution already has X floating, paying it requires no
    # mana-ability step and must remain an option.
    state=solver.State(
        turn=2,
        library=("Tail",),
        hand=(),
        battlefield=(),
        colorless=3,
        rng_root_seed=20260822,
    )
    options=transmute_difference_payment_options(state,3)
    assert options
    action,paid=options[0]
    assert dict(action.parameters)["mana_steps"]==()
    assert paid.colorless==0


def main():
    tests=[
        test_cast_commit_is_hidden_future_invariant,
        test_uu_is_paid_before_resolution_but_sacrifice_is_not,
        test_sacrifice_choice_occurs_before_search_observation,
        test_search_target_set_is_permutation_invariant_after_commit_and_sacrifice,
        test_difference_can_use_mana_ability_during_resolution_not_only_floating_mana,
        test_searched_target_cannot_pay_its_own_difference,
        test_paid_target_enters_then_shuffle_clears_old_position_knowledge,
        test_decline_moves_target_to_graveyard_then_shuffles,
        test_existing_floating_mana_remains_a_legal_difference_payment_plan,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("TRANSMUTE ARTIFACT ADAPTER SMOKE: ALL PASS")


if __name__=="__main__":
    main()
