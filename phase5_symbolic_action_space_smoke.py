#!/usr/bin/env python3
"""Symbolic action-space and Whir ZDD parity regression."""

from dataclasses import replace
from math import comb

import urza_solver as solver
import non_oracle_x_artifact_tutor_runtime as xrt
from non_oracle_runtime import make_runtime_state
from symbolic_action_space import (
    ParetoFrontier,
    ParetoPoint,
    add_bit,
    bit_count,
    branch_and_bound,
    cached_cardinality_zdd,
)
from x_artifact_search_adapter import WHIR, whir_cast_intents


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
        hand=(WHIR,),
        battlefield=tuple(solver.Perm(card) for card in ARTIFACT_BOARD),
        blue=8,
        colorless=8,
        rng_root_seed=20260828,
    )


def old_useful_plans(state,x):
    rows=set()
    for action in whir_cast_intents(state):
        params=dict(action.parameters)
        if int(params["x"])!=int(x):
            continue
        if int(x)>xrt.MAX_USEFUL_ARTIFACT_X:
            continue
        rows.add((
            tuple(tuple(raw) for raw in params["improvise"]),
            int(params["floating_generic"]),
        ))
    return rows


def symbolic_terminal_plans(runtime,root):
    pending=xrt.begin_x_artifact_tutor(runtime,root)
    if pending.pending is None:
        return {((),0)}
    data=dict(pending.pending.payload)
    slot_keys=tuple(tuple(raw) for raw in data["slot_keys"])
    min_k=int(data["min_selected"])
    max_k=int(data["max_selected"])
    zdd=cached_cardinality_zdd(len(slot_keys),min_k,max_k)
    need=int(data["generic_need"])
    rows=set()
    for mask in zdd.iter_masks():
        selected=tuple(
            slot_keys[index]
            for index in range(len(slot_keys))
            if mask & (1<<index)
        )
        rows.add((selected,need-bit_count(mask)))
    return rows


def walk_runtime(runtime):
    """Walk every symbolic payment leaf through actual pending actions."""
    finals={}

    def visit(current):
        data=dict(current.pending.payload)
        mask=int(data["selected_mask"])
        request=xrt.whir_payment_request(
            current,horizon=6,objective="win_by_horizon",policy_id="symbolic-parity"
        )
        for action in request.actions:
            result=xrt.apply_whir_payment_pending(current,action)
            if result.pending is not None and result.pending.kind==xrt.RUNTIME_WHIR_PAYMENT:
                visit(result)
            else:
                key=(
                    mask,
                    action.kind,
                    tuple(action.parameters),
                )
                finals[key]=result

    visit(runtime)
    return finals


def main():
    # Standalone cardinality ZDD compression.
    zdd=cached_cardinality_zdd(20,7,7)
    stats=zdd.stats()
    assert stats.represented_sets==comb(20,7)
    assert stats.node_count<200,(stats.node_count,stats.represented_sets)
    assert stats.represented_sets>70000
    assert sum(1 for _ in zdd.iter_masks())==stats.represented_sets

    # Pareto primitive: dominated point is rejected and a new dominating point
    # removes the weaker frontier row.
    frontier=ParetoFrontier()
    assert frontier.add(ParetoPoint("a",(3.0,2.0),(5.0,)))
    assert not frontier.add(ParetoPoint("b",(2.0,2.0),(6.0,)))
    assert frontier.add(ParetoPoint("c",(4.0,2.0),(4.0,)))
    assert tuple(row.value for row in frontier.rows())==("c",)

    # Exact branch-and-bound toy: bound is the max leaf under each integer node.
    children_map={
        "root":("left","right"),
        "left":("l1","l2"),
        "right":("r1","r2"),
    }
    leaf_value={"l1":3,"l2":5,"r1":2,"r2":9}
    bound={"root":9,"left":5,"right":9,**leaf_value}
    result=branch_and_bound(
        root="root",
        is_terminal=lambda item:item in leaf_value,
        children=lambda item:children_map.get(item,()),
        upper_bound=lambda item:bound[item],
        evaluate=lambda item:leaf_value[item],
        better=lambda a,b:a>b,
        can_beat=lambda upper,incumbent:upper>incumbent,
    )
    assert result.best_item=="r2" and result.best_value==9

    state=fixture_state()
    runtime=make_runtime_state(state)
    roots=tuple(
        action for action in xrt.x_artifact_runtime_intents(runtime)
        if action.source==WHIR
    )
    assert roots
    assert len(roots)<=xrt.MAX_USEFUL_ARTIFACT_X+1

    for root in roots:
        x=int(dict(root.parameters)["x"])
        old=old_useful_plans(state,x)
        new=symbolic_terminal_plans(runtime,root)
        assert new==old,(x,len(new),len(old),list(old-new)[:2],list(new-old)[:2])

    # Pick the largest useful X and compare action-surface size to represented
    # terminal plans.
    root=max(roots,key=lambda action:int(dict(action.parameters)["x"]))
    x=int(dict(root.parameters)["x"])
    pending=xrt.begin_x_artifact_tutor(runtime,root)
    data=dict(pending.pending.payload)
    zdd=cached_cardinality_zdd(
        len(data["slot_keys"]),
        int(data["min_selected"]),
        int(data["max_selected"]),
    )
    request=xrt.whir_payment_request(
        pending,horizon=6,objective="win_by_horizon",policy_id="surface"
    )
    assert zdd.count_sets()==len(old_useful_plans(state,x))
    assert len(request.actions)<=len(data["slot_keys"])+1
    assert zdd.stats().node_count<zdd.count_sets()

    # Hidden order cannot alter root or payment DAG edges.
    hidden=make_runtime_state(replace(state,library=tuple(reversed(state.library))))
    hidden_roots=tuple(
        action for action in xrt.x_artifact_runtime_intents(hidden)
        if action.source==WHIR
    )
    assert tuple(a.strategic_key() for a in roots)==tuple(
        a.strategic_key() for a in hidden_roots
    )
    hidden_root=max(hidden_roots,key=lambda action:int(dict(action.parameters)["x"]))
    hidden_pending=xrt.begin_x_artifact_tutor(hidden,hidden_root)
    hidden_request=xrt.whir_payment_request(
        hidden_pending,horizon=6,objective="win_by_horizon",policy_id="surface"
    )
    assert tuple(a.strategic_key() for a in request.actions)==tuple(
        a.strategic_key() for a in hidden_request.actions
    )

    print(f"ZDD 20 choose 7: {stats.represented_sets} subsets in {stats.node_count} nodes")
    print(f"Whir X={x}: {zdd.count_sets()} payment subsets; {len(request.actions)} root DAG edges")
    print("bitset/ZDD Whir payment family matches legacy useful plans: PASS")
    print("hidden library order cannot affect symbolic payment DAG: PASS")
    print("Pareto frontier primitive: PASS")
    print("exact branch-and-bound primitive: PASS")


if __name__=="__main__":
    main()
