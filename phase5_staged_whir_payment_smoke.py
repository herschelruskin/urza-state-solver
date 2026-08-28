#!/usr/bin/env python3
"""Exact staged-Whir action-space parity and fanout regression."""

from dataclasses import replace
from pathlib import Path

import urza_solver as solver
import non_oracle_x_artifact_tutor_runtime as xrt
from non_oracle_runtime import make_runtime_state
from phase5_selective_tutor_q import contingent_depth_after_action
from x_artifact_search_adapter import (
    WHIR,
    _artifact_search_event,
    whir_cast_intents,
)


ARTIFACT_BOARD=(
    "Sol Ring",
    "Sensei's Divining Top",
    "Codex Shredder",
    "Grafdigger's Cage",
    "Defense Grid",
    "Grinding Station",
    "Mox Opal",
    "Welding Jar",
)


def fixture_state():
    return solver.State(
        turn=4,
        library=tuple(sorted(solver.ARTIFACTS)),
        hand=(WHIR,),
        battlefield=tuple(solver.Perm(card) for card in ARTIFACT_BOARD),
        blue=8,
        colorless=8,
        rng_root_seed=20260828,
    )


def legacy_plan_set(state):
    rows=set()
    for action in whir_cast_intents(state):
        params=dict(action.parameters)
        x=int(params["x"])
        if x>xrt.MAX_USEFUL_ARTIFACT_X:
            continue
        rows.add((
            x,
            tuple(tuple(raw) for raw in params["improvise"]),
            int(params["floating_generic"]),
        ))
    return rows


def walk_staged(runtime, root):
    x=int(dict(root.parameters)["x"])
    started=xrt.begin_x_artifact_tutor(runtime,root)
    if started.pending is None:
        return {(x,(),0):started}
    finals={}

    def visit(current):
        data=dict(current.pending.payload)
        selected=tuple(tuple(raw) for raw in data["selected"])
        request=xrt.whir_payment_request(
            current,
            horizon=6,
            objective="win_by_horizon",
            policy_id="staged-whir-parity",
        )
        for action in request.actions:
            params=dict(action.parameters)
            if action.kind==xrt.WHIR_PAYMENT_FINISH:
                plan=(x,selected,int(params["floating_generic"]))
                result=xrt.apply_whir_payment_pending(current,action)
                assert result.pending is None
                if plan in finals:
                    raise AssertionError(f"duplicate staged Whir path for {plan!r}")
                finals[plan]=result
                continue

            assert action.kind==xrt.WHIR_PAYMENT_ADD
            raw=tuple(params["slot"])
            updated=selected+(raw,)
            result=xrt.apply_whir_payment_pending(current,action)
            if result.pending is None:
                plan=(x,updated,0)
                if plan in finals:
                    raise AssertionError(f"duplicate staged Whir path for {plan!r}")
                finals[plan]=result
            else:
                visit(result)

    visit(started)
    return finals


def legacy_phase2_finish(runtime,plan):
    """Historical monolithic Whir commitment, retained only as a parity oracle."""
    x,selected,floating=plan
    state=runtime.true_state
    paid=solver.pay(state,0,3)
    if paid is None:
        raise AssertionError("fixture cannot pay Whir UUU")
    slots=tuple(xrt._slot_from_parameter(raw) for raw in selected)
    indices=tuple(xrt._slot_index(paid,slot) for slot in slots)
    for index in indices:
        paid=solver.update_perm(paid,index,tapped=True)
    paid=solver.pay(paid,int(floating),0)
    if paid is None:
        raise AssertionError("legacy fixture payment became illegal")
    paid=replace(
        paid,
        hand=solver.remove_one(paid.hand,WHIR),
        spell_cast_this_turn=True,
    )
    mana_spent=3+int(floating)
    paid=solver.add_trace(paid,f"legacy Whir X={x}; payment plan committed")
    out=replace(runtime,true_state=solver._ensure_oracle_instance_tags(paid))
    spell,out=xrt._allocate_spell(
        out,kind=xrt.SPELL_WHIR,source=WHIR,x=x,mana_spent=mana_spent
    )
    return xrt._finish_cast_triggers(
        out,
        source=WHIR,
        spell=spell,
        mana_spent=mana_spent,
        prized_died=False,
        cam_died=False,
    )


def normalize_trace(runtime):
    return replace(
        runtime,
        true_state=replace(runtime.true_state,trace=()),
    )


def main():
    state=fixture_state()
    runtime=make_runtime_state(state)

    legacy_all=whir_cast_intents(state)
    assert any(
        int(dict(action.parameters)["x"])>xrt.MAX_USEFUL_ARTIFACT_X
        for action in legacy_all
    ),"fixture should expose historically dominated high-X actions"

    # X beyond the maximum deck artifact MV cannot reveal another artifact.
    assert xrt.MAX_USEFUL_ARTIFACT_X==max(
        solver.mana_value(card) for card in solver.ARTIFACTS
    )
    search_at_cap=_artifact_search_event(state,WHIR,xrt.MAX_USEFUL_ARTIFACT_X)
    search_above=_artifact_search_event(state,WHIR,xrt.MAX_USEFUL_ARTIFACT_X+1)
    assert search_at_cap.legal_cards==search_above.legal_cards

    roots=tuple(
        action for action in xrt.x_artifact_runtime_intents(runtime)
        if str(action.source)==WHIR
    )
    assert roots
    assert max(int(dict(action.parameters)["x"]) for action in roots)==xrt.MAX_USEFUL_ARTIFACT_X
    assert len(roots)<=xrt.MAX_USEFUL_ARTIFACT_X+1

    legacy=legacy_plan_set(state)
    staged={}
    for root in roots:
        staged.update(walk_staged(runtime,root))

    assert set(staged)==legacy,(len(staged),len(legacy),sorted(legacy-set(staged))[:3])
    assert len(staged)==len(legacy)
    # This fixture historically materializes hundreds of payment commitments at
    # once. Staging keeps the main-phase Whir surface to one action per useful X.
    assert len(legacy)>=100,(len(legacy),len(roots))
    assert len(roots)<=5

    for plan,result in staged.items():
        old=legacy_phase2_finish(runtime,plan)
        assert normalize_trace(result)==normalize_trace(old),plan

    # No hidden library order may affect X/payment commitment choices.
    hidden=make_runtime_state(replace(state,library=tuple(reversed(state.library))))
    hidden_roots=tuple(
        action for action in xrt.x_artifact_runtime_intents(hidden)
        if str(action.source)==WHIR
    )
    assert tuple(a.strategic_key() for a in roots)==tuple(
        a.strategic_key() for a in hidden_roots
    )
    root4=next(a for a in roots if int(dict(a.parameters)["x"])==xrt.MAX_USEFUL_ARTIFACT_X)
    hidden_root4=next(
        a for a in hidden_roots
        if int(dict(a.parameters)["x"])==xrt.MAX_USEFUL_ARTIFACT_X
    )
    p1=xrt.begin_x_artifact_tutor(runtime,root4)
    p2=xrt.begin_x_artifact_tutor(hidden,hidden_root4)
    q1=xrt.whir_payment_request(
        p1,horizon=6,objective="win_by_horizon",policy_id="parity"
    )
    q2=xrt.whir_payment_request(
        p2,horizon=6,objective="win_by_horizon",policy_id="parity"
    )
    assert tuple(a.strategic_key() for a in q1.actions)==tuple(
        a.strategic_key() for a in q2.actions
    )

    need=int(dict(root4.parameters)["generic_need"])
    assert contingent_depth_after_action(root4)==need+1
    add=next(a for a in q1.actions if a.kind==xrt.WHIR_PAYMENT_ADD)
    assert contingent_depth_after_action(add)==int(dict(add.parameters)["remaining_before"])
    finish=next(a for a in q1.actions if a.kind==xrt.WHIR_PAYMENT_FINISH)
    assert contingent_depth_after_action(finish)==1

    print(f"historical useful Whir payment plans: {len(legacy)}")
    print(f"staged main-phase Whir actions: {len(roots)}")
    print("every useful historical payment plan has exactly one staged path: PASS")
    print("staged final cast state matches historical Phase-2 commitment: PASS")
    print("high-X dominated commitments removed without changing target set: PASS")
    print("hidden library order cannot affect X/improvise commitment actions: PASS")
    print("bounded Q depth covers every staged payment choice plus target: PASS")


if __name__=="__main__":
    main()
