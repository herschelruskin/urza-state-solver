#!/usr/bin/env python3
"""Exact staged-Reshape DAG parity and fanout regression."""

from dataclasses import replace

import urza_solver as solver
import non_oracle_x_artifact_tutor_runtime as xrt
from non_oracle_runtime import make_runtime_state
from phase5_selective_tutor_q import contingent_depth_after_action
from x_artifact_search_adapter import RESHAPE, reshape_cast_intents


ARTIFACT_BOARD=(
    "Sol Ring",
    "Sensei's Divining Top",
    "Codex Shredder",
    "Grafdigger's Cage",
    "Defense Grid",
    "Grinding Station",
    "Mox Opal",
    "Welding Jar",
    "The One Ring",
    "The Reality Chip",
    "Sapphire Medallion",
    "Everflowing Chalice",
)


def fixture_state():
    return solver.State(
        turn=4,
        library=tuple(sorted(solver.ARTIFACTS)),
        hand=(RESHAPE,),
        battlefield=tuple(solver.Perm(card) for card in ARTIFACT_BOARD),
        blue=8,
        colorless=8,
        rng_root_seed=20260828,
    )


def legacy_useful(runtime):
    rows={}
    for action in reshape_cast_intents(runtime.true_state):
        params=dict(action.parameters)
        x=int(params["x"])
        if x>xrt.MAX_USEFUL_ARTIFACT_X:
            continue
        key=(
            x,
            int(params["generic_paid"]),
            tuple(params["sacrifice"]),
        )
        rows[key]=action
    return rows


def staged_paths(runtime):
    rows={}
    roots=tuple(
        action for action in xrt.x_artifact_runtime_intents(runtime)
        if action.source==RESHAPE
    )
    for root in roots:
        pending=xrt.begin_x_artifact_tutor(runtime,root)
        assert pending.pending is not None
        assert pending.pending.kind==xrt.RUNTIME_RESHAPE_SACRIFICE
        request=xrt._reshape_sacrifice_request(
            pending,
            horizon=6,
            objective="win_by_horizon",
            policy_id="reshape-parity",
        )
        for sacrifice in request.actions:
            params=dict(sacrifice.parameters)
            key=(
                int(params["x"]),
                int(params["generic_paid"]),
                tuple(params["sacrifice"]),
            )
            if key in rows:
                raise AssertionError(f"duplicate staged Reshape path {key!r}")
            rows[key]=(root,sacrifice,pending)
    return roots,rows


def legacy_begin(runtime,action):
    """Historical monolithic Phase-2 Reshape commitment as parity oracle."""
    params=dict(action.parameters)
    x=int(params["x"])
    generic=int(params["generic_paid"])
    state=runtime.true_state
    slot=xrt._slot_from_parameter(tuple(params["sacrifice"]))
    index=xrt._slot_index(state,slot)

    paid=solver.pay(state,generic,2)
    if paid is None or RESHAPE not in paid.hand:
        raise AssertionError("fixture Reshape payment became illegal")
    paid=replace(
        paid,
        hand=solver.remove_one(paid.hand,RESHAPE),
        spell_cast_this_turn=True,
    )
    if not solver.is_artifact_perm(paid.battlefield[index]):
        raise AssertionError("fixture sacrifice is no longer an artifact")
    paid,sacrificed=xrt._remove_artifact_for_reshape_cost(paid,index)
    mana_spent=generic+2
    paid=solver.add_trace(
        paid,
        f"Phase2 cast Reshape X={x}; sacrifice {sacrificed.name or sacrificed.mode} as additional cost",
    )
    out=replace(
        runtime,
        true_state=solver._ensure_oracle_instance_tags(paid),
    )
    spell,out=xrt._allocate_spell(
        out,
        kind=xrt.SPELL_RESHAPE,
        source=RESHAPE,
        x=x,
        mana_spent=mana_spent,
    )
    return xrt._finish_cast_triggers(
        out,
        source=RESHAPE,
        spell=spell,
        mana_spent=mana_spent,
        prized_died=sacrificed.name=="Prized Statue",
        cam_died=sacrificed.name=="Sewer-veillance Cam",
    )


def main():
    runtime=make_runtime_state(fixture_state())
    legacy=legacy_useful(runtime)
    roots,staged=staged_paths(runtime)

    assert set(staged)==set(legacy),(
        len(staged),len(legacy),
        list(set(legacy)-set(staged))[:3],
        list(set(staged)-set(legacy))[:3],
    )
    assert len(roots)<=xrt.MAX_USEFUL_ARTIFACT_X+1
    assert len(legacy)>=40,(len(legacy),len(roots))

    for key,(root,sacrifice,pending) in staged.items():
        new=xrt._apply_reshape_sacrifice(pending,sacrifice)
        old=legacy_begin(runtime,legacy[key])
        assert new==old,key

    # X roots and sacrifice choices must be independent of hidden library order.
    hidden=make_runtime_state(replace(
        runtime.true_state,
        library=tuple(reversed(runtime.true_state.library)),
    ))
    hidden_roots=tuple(
        action for action in xrt.x_artifact_runtime_intents(hidden)
        if action.source==RESHAPE
    )
    assert tuple(a.strategic_key() for a in roots)==tuple(
        a.strategic_key() for a in hidden_roots
    )
    for root,hidden_root in zip(roots,hidden_roots):
        a=xrt.begin_x_artifact_tutor(runtime,root)
        b=xrt.begin_x_artifact_tutor(hidden,hidden_root)
        ar=xrt._reshape_sacrifice_request(
            a,horizon=6,objective="win_by_horizon",policy_id="parity"
        )
        br=xrt._reshape_sacrifice_request(
            b,horizon=6,objective="win_by_horizon",policy_id="parity"
        )
        assert tuple(x.strategic_key() for x in ar.actions)==tuple(
            x.strategic_key() for x in br.actions
        )

    assert all(contingent_depth_after_action(root)==2 for root in roots)
    sample_pending=xrt.begin_x_artifact_tutor(runtime,roots[0])
    sample_sac=xrt._reshape_sacrifice_request(
        sample_pending,horizon=6,objective="win_by_horizon",policy_id="parity"
    ).actions[0]
    assert contingent_depth_after_action(sample_sac)==1

    print(f"historical useful Reshape commitments: {len(legacy)}")
    print(f"staged main-phase Reshape X roots: {len(roots)}")
    print("every historical X+sacrifice commitment has exactly one staged path: PASS")
    print("every staged path matches historical Phase-2 cast runtime exactly: PASS")
    print("hidden library order cannot affect Reshape X/sacrifice commitments: PASS")
    print("bounded Q depth covers sacrifice plus eventual target: PASS")


if __name__=="__main__":
    main()
