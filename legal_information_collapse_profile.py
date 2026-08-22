#!/usr/bin/env python3
"""Measure strategic value-state collapse with propagated legal InformationState.

This remains decision-neutral: Oracle legal actions, exact state merging,
dominance pruning, beam selection, and win detection are unchanged.  A sidecar
maps each retained concrete state to every legal InformationState observed on the
same Oracle search graph.  The sidecar never changes which concrete state survives.

Two profilers are recorded simultaneously:
1. empty-information baseline, matching the earlier upper-bound experiment;
2. legal-information value identity using propagated scry/top/tutor knowledge.

For the second measurement, the correct denominator is
``concrete_information_unique`` rather than concrete state alone: identical true
states reached with different remembered information can support different policy
choices and therefore must remain distinct before strategic projection.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import heapq
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence, Set, Tuple

import urza_solver as solver
from information_state_propagation import initial_information, propagate_information
from solver_architecture import InformationState
from strategic_value_state import StrategicKeyProfiler


EMPTY_INFORMATION = InformationState()
InfoMap = MutableMapping[Any, Set[InformationState]]


def _state_key(state: solver.State):
    return state.key()


def _add_infos(target: InfoMap, key, infos: Iterable[InformationState]) -> None:
    target.setdefault(key, set()).update(infos)


def _infos_for(state: solver.State, mapping: Mapping[Any, Set[InformationState]]) -> Set[InformationState]:
    infos = mapping.get(_state_key(state))
    if not infos:
        raise RuntimeError("missing InformationState sidecar for retained concrete state")
    return set(infos)


def _observe(
    baseline: StrategicKeyProfiler,
    legal: StrategicKeyProfiler,
    state: solver.State,
    infos: Iterable[InformationState],
    *,
    depth: int,
) -> None:
    baseline.observe(state, EMPTY_INFORMATION, depth=depth)
    for info in set(infos):
        legal.observe(state, info, depth=depth)


def oracle_7a_deal(seed: int, deck: List[str]) -> tuple[bool, List[str]]:
    caverns_live, deals = solver.oracle_mulligan_deals(seed, deck, min_keep=4)
    if not deals or deals[0][0] != "7A":
        raise AssertionError("unexpected Oracle mulligan stage specification")
    return caverns_live, list(deals[0][2])


def _initial_state(deck_order: List[str], caverns_live: bool, seed: int) -> solver.State:
    hand, lib = solver.london_opening_zones(deck_order, 7, [])
    state = solver.State(
        turn=1,
        library=lib,
        hand=tuple(hand),
        battlefield=(),
        rng_root_seed=seed,
        trace=("--- Turn 1 ---",),
    )
    if "Gemstone Caverns" in state.hand and caverns_live and len(state.hand) > 1:
        choices = [card for card in state.hand if card != "Gemstone Caverns"]
        exiled = min(choices, key=lambda card: solver.card_priority(state, card))
        state = solver.replace(
            state,
            hand=solver.remove_one(
                solver.remove_one(state.hand, "Gemstone Caverns"), exiled
            ),
            exile=state.exile + (exiled,),
        )
        state = solver.add_perm(state, "Gemstone Caverns", mode="luck")
        state = solver.add_trace(state, f"pregame Caverns exiles {exiled}")
    state, drawn = solver.draw_from_library(state, 1)
    if drawn:
        state = solver.append_trace_detail(state, f"normal draw for turn 1: {drawn[0]}")
    return solver.refresh_observability(state)


def _resolve_remora_upkeep_with_information(
    states: Sequence[solver.State],
    infos_by_key: Mapping[Any, Set[InformationState]],
    *,
    beam: int,
    graph_stats: Dict[str, Any],
    baseline: StrategicKeyProfiler,
    legal: StrategicKeyProfiler,
) -> tuple[List[solver.State], Dict[Any, Set[InformationState]]]:
    """Mirror the validated upkeep closure while carrying information sidecars."""
    complete: Dict[Any, solver.State] = {}
    complete_infos: Dict[Any, Set[InformationState]] = defaultdict(set)
    pending = list(states)
    pending_infos: Dict[Any, Set[InformationState]] = {
        key: set(values) for key, values in infos_by_key.items()
    }
    expanded = set()

    while pending:
        next_pending: Dict[Any, solver.State] = {}
        next_pending_infos: Dict[Any, Set[InformationState]] = defaultdict(set)
        for state in pending:
            state_infos = _infos_for(state, pending_infos)
            if not state.remora_upkeep_pending:
                checked = solver.check_win(state)
                key = _state_key(checked)
                old = complete.get(key)
                if old is not None:
                    graph_stats["upkeep_exact_key_merges"] += 1
                if old is None or solver.score(checked) > solver.score(old):
                    complete[key] = checked
                _add_infos(complete_infos, key, state_infos)
                continue

            key = _state_key(state)
            if key in expanded:
                continue
            expanded.add(key)
            actions = solver.remora_upkeep_actions(state)
            graph_stats["upkeep_nodes_expanded"] += 1
            graph_stats["upkeep_edges_generated"] += len(actions)
            graph_stats["upkeep_max_raw_successors"] = max(
                graph_stats["upkeep_max_raw_successors"], len(actions)
            )

            for successor in actions:
                successor_infos = {
                    propagate_information(state, successor, info)
                    for info in state_infos
                }
                _observe(baseline, legal, successor, successor_infos, depth=-1)
                if not successor.remora_upkeep_pending:
                    successor = solver.check_win(successor)
                    family = solver._remora_resolution_family(successor)
                    if family in {"pay", "decline", "bounce"}:
                        graph_stats[f"remora_{family}_results_generated"] += 1
                successor_key = _state_key(successor)
                target_states = next_pending if successor.remora_upkeep_pending else complete
                target_infos = next_pending_infos if successor.remora_upkeep_pending else complete_infos
                old = target_states.get(successor_key)
                if old is not None:
                    graph_stats["upkeep_exact_key_merges"] += 1
                if old is None or solver.score(successor) > solver.score(old):
                    target_states[successor_key] = successor
                _add_infos(target_infos, successor_key, successor_infos)

        graph_stats["upkeep_layers"] += 1
        if not next_pending:
            break
        raw_candidates = list(next_pending.values())
        candidates = solver.dominance_prune(raw_candidates)
        graph_stats["upkeep_dominance_pruned"] += max(
            0, len(raw_candidates) - len(candidates)
        )
        graph_stats["upkeep_beam_pruned"] += max(0, len(candidates) - beam)
        pending = heapq.nlargest(min(beam, len(candidates)), candidates, key=solver.score)
        pending_infos = {
            _state_key(state): set(next_pending_infos[_state_key(state)])
            for state in pending
        }
        graph_stats["upkeep_max_frontier"] = max(
            graph_stats["upkeep_max_frontier"], len(pending)
        )

    raw_complete = list(complete.values())
    candidates = solver.dominance_prune(raw_complete)
    graph_stats["upkeep_dominance_pruned"] += max(0, len(raw_complete) - len(candidates))
    keep_n = min(beam, len(candidates))
    if keep_n <= 0:
        return [], {}

    ranked = heapq.nlargest(len(candidates), candidates, key=solver.score)
    best_family: Dict[str, solver.State] = {}
    for state in ranked:
        family = solver._remora_resolution_family(state)
        if family in {"pay", "decline", "bounce"} and family not in best_family:
            best_family[family] = state
    required = list(best_family.values())
    if len(required) > keep_n:
        required = heapq.nlargest(keep_n, required, key=solver.score)
    graph_stats["upkeep_beam_pruned"] += max(0, len(candidates) - keep_n)

    selected: List[solver.State] = []
    selected_keys = set()
    for state in required + ranked:
        key = _state_key(state)
        if key in selected_keys:
            continue
        selected.append(state)
        selected_keys.add(key)
        if len(selected) >= keep_n:
            break
    selected_infos = {key: set(complete_infos[key]) for key in selected_keys}
    return selected, selected_infos


def _end_turn_frontier_with_information(
    frontier: Sequence[solver.State],
    infos_by_key: Mapping[Any, Set[InformationState]],
    *,
    beam: int,
    resolve_remora_upkeep: bool,
    graph_stats: Dict[str, Any],
    baseline: StrategicKeyProfiler,
    legal: StrategicKeyProfiler,
    max_turn: int,
) -> tuple[List[solver.State], Dict[Any, Set[InformationState]], int]:
    resolved = [state for state in frontier if solver.can_end_turn_state(state)]
    selected_sources = heapq.nlargest(min(beam, len(resolved)), resolved, key=solver.score)
    transitioned: List[solver.State] = []
    transitioned_infos: Dict[Any, Set[InformationState]] = defaultdict(set)
    post_horizon = 0

    for source in selected_sources:
        after = solver.end_turn(
            source, schedule_remora_upkeep=resolve_remora_upkeep
        )
        source_infos = _infos_for(source, infos_by_key)
        after_infos = {
            propagate_information(source, after, info)
            for info in source_infos
        }
        transitioned.append(after)
        _add_infos(transitioned_infos, _state_key(after), after_infos)
        if after.turn <= max_turn:
            _observe(baseline, legal, after, after_infos, depth=0)
        else:
            post_horizon += 1

    if not resolve_remora_upkeep:
        return transitioned, dict(transitioned_infos), post_horizon

    states, infos = _resolve_remora_upkeep_with_information(
        transitioned,
        transitioned_infos,
        beam=beam,
        graph_stats=graph_stats,
        baseline=baseline,
        legal=legal,
    )
    return states, infos, post_horizon


def profile_candidate(
    deck_order: List[str],
    *,
    caverns_live: bool,
    seed: int,
    max_turn: int,
    beam: int,
    max_actions_per_turn: int,
    baseline: StrategicKeyProfiler,
    legal: StrategicKeyProfiler,
) -> Dict[str, Any]:
    state = _initial_state(deck_order, caverns_live, seed)
    initial_info = initial_information(state)
    states = [state]
    infos_by_key: Dict[Any, Set[InformationState]] = {
        _state_key(state): {initial_info}
    }
    _observe(baseline, legal, state, {initial_info}, depth=0)

    searched = 0
    max_depth_reached = 0
    graph_stats = solver.new_graph_stats()
    post_horizon_snapshots = 0
    max_info_variants = 1

    for turn in range(1, max_turn + 1):
        frontier = states
        frontier_infos = infos_by_key
        expanded_this_turn = set()
        best_by: Dict[Any, solver.State] = {}

        for depth in range(max_actions_per_turn):
            max_depth_reached = max(max_depth_reached, depth + 1)
            next_infos: Dict[Any, Set[InformationState]] = defaultdict(set)
            for current in frontier:
                exact = _state_key(current)
                if exact in expanded_this_turn:
                    graph_stats["cycle_skips"] += 1
                    continue
                expanded_this_turn.add(exact)
                searched += 1
                graph_stats["nodes_expanded"] += 1

                if current.won:
                    return {
                        "seed": seed,
                        "win_turn": current.turn,
                        "family": current.win_family,
                        "searched": searched,
                        "max_depth_reached": max_depth_reached,
                        "max_information_variants_per_concrete_state": max_info_variants,
                        "post_horizon_snapshots": post_horizon_snapshots,
                        "graph": solver.finalize_graph_stats(graph_stats),
                    }

                current_infos = _infos_for(current, frontier_infos)
                max_info_variants = max(max_info_variants, len(current_infos))
                actions = solver.legal_actions(current)
                graph_stats["edges_generated"] += len(actions)
                graph_stats["max_raw_successors"] = max(
                    graph_stats["max_raw_successors"], len(actions)
                )

                for successor in actions:
                    successor = solver.check_win(successor)
                    successor_infos = {
                        propagate_information(current, successor, info)
                        for info in current_infos
                    }
                    max_info_variants = max(max_info_variants, len(successor_infos))
                    _observe(
                        baseline, legal, successor, successor_infos, depth=depth + 1
                    )
                    if successor.won:
                        return {
                            "seed": seed,
                            "win_turn": successor.turn,
                            "family": successor.win_family,
                            "searched": searched,
                            "max_depth_reached": max_depth_reached,
                            "max_information_variants_per_concrete_state": max_info_variants,
                            "post_horizon_snapshots": post_horizon_snapshots,
                            "graph": solver.finalize_graph_stats(graph_stats),
                        }
                    key = _state_key(successor)
                    old = best_by.get(key)
                    if old is not None:
                        graph_stats["exact_key_merges"] += 1
                    if old is None or solver.score(successor) > solver.score(old):
                        best_by[key] = successor
                    _add_infos(next_infos, key, successor_infos)

            if not best_by:
                break

            pre_dominance = list(best_by.values())
            post_dominance = solver.dominance_prune(pre_dominance)
            graph_stats["dominance_pruned"] += max(
                0, len(pre_dominance) - len(post_dominance)
            )
            graph_stats["beam_pruned"] += max(0, len(post_dominance) - beam)
            frontier = heapq.nlargest(beam, post_dominance, key=solver.score)
            frontier_infos = {
                _state_key(state): set(next_infos[_state_key(state)])
                for state in frontier
            }
            graph_stats["layers"] += 1
            graph_stats["max_frontier"] = max(
                graph_stats["max_frontier"], len(frontier)
            )
            best_by = {}

        states, infos_by_key, post = _end_turn_frontier_with_information(
            frontier,
            frontier_infos,
            beam=beam,
            resolve_remora_upkeep=(turn < max_turn),
            graph_stats=graph_stats,
            baseline=baseline,
            legal=legal,
            max_turn=max_turn,
        )
        post_horizon_snapshots += post

    return {
        "seed": seed,
        "win_turn": None,
        "family": "",
        "searched": searched,
        "max_depth_reached": max_depth_reached,
        "max_information_variants_per_concrete_state": max_info_variants,
        "post_horizon_snapshots": post_horizon_snapshots,
        "graph": solver.finalize_graph_stats(graph_stats),
    }


def _pct(value: float) -> str:
    return f"{100.0 * value:6.2f}%"


def _print_measurement(label: str, summary: Dict[str, Any]) -> None:
    print(f"\n=== {label} ===", flush=True)
    print(f"observations:                 {summary['observations']:,}", flush=True)
    print(f"concrete unique:              {summary['concrete_unique']:,}", flush=True)
    print(
        f"concrete+information unique:  {summary['concrete_information_unique']:,}",
        flush=True,
    )
    print(f"strategic unique:             {summary['strategic_unique']:,}", flush=True)
    print(
        "info-aware collapse:            "
        + _pct(summary["concrete_information_to_strategic_collapse_fraction"]),
        flush=True,
    )
    print(
        "candidate cache-hit:             "
        + _pct(summary["estimated_strategic_cache_hit_fraction"]),
        flush=True,
    )


def run_profile(
    deck: List[str],
    *,
    base_seed: int,
    count: int,
    step: int,
    max_turn: int,
    beam: int,
    depth: int,
    action_cap: int,
) -> Dict[str, Any]:
    old_action_cap = solver.ACTION_CAP
    solver.ACTION_CAP = action_cap
    global_baseline = StrategicKeyProfiler()
    global_legal = StrategicKeyProfiler()
    rows = []
    started = time.time()

    try:
        for index in range(count):
            seed = base_seed + index * step
            caverns_live, deck_order = oracle_7a_deal(seed, deck)
            local_baseline = StrategicKeyProfiler()
            local_legal = StrategicKeyProfiler()
            print(
                f"[legal-info-profile] seed={seed} start turns={max_turn} "
                f"beam={beam} depth={depth} action_cap={action_cap}",
                flush=True,
            )
            # Observe into local profilers during the search, then replay their
            # observations into globals is not possible from summaries alone. Use
            # a small multiplex wrapper by passing paired aggregate+local objects.
            class MultiplexProfiler:
                def __init__(self, *targets):
                    self.targets = targets
                def observe(self, *args, **kwargs):
                    for target in self.targets:
                        target.observe(*args, **kwargs)

            baseline_mux = MultiplexProfiler(global_baseline, local_baseline)
            legal_mux = MultiplexProfiler(global_legal, local_legal)
            row = profile_candidate(
                deck_order,
                caverns_live=caverns_live,
                seed=seed,
                max_turn=max_turn,
                beam=beam,
                max_actions_per_turn=depth,
                baseline=baseline_mux,
                legal=legal_mux,
            )
            row["empty_information_baseline"] = local_baseline.summary()
            row["legal_information"] = local_legal.summary()
            rows.append(row)
            legal_summary = row["legal_information"]
            print(
                f"[legal-info-profile] seed={seed} win={row['win_turn'] or '-'} "
                f"family={row['family'] or '-'} searched={row['searched']:,} "
                f"info_collapse={_pct(legal_summary['concrete_information_to_strategic_collapse_fraction'])} "
                f"hit={_pct(legal_summary['estimated_strategic_cache_hit_fraction'])} "
                f"max_info_variants={row['max_information_variants_per_concrete_state']}",
                flush=True,
            )
    finally:
        solver.ACTION_CAP = old_action_cap

    baseline = global_baseline.summary()
    legal = global_legal.summary()
    return {
        "measurement_kind": "legal-information-strategic-collapse",
        "decision_neutral": True,
        "search_scope": "Oracle 7A concrete search graph; InformationState carried in a non-decision sidecar",
        "denominator_note": (
            "Use concrete_information_to_strategic_collapse_fraction for the legal-information result. "
            "Concrete state alone is insufficient when remembered knowledge differs."
        ),
        "config": {
            "base_seed": base_seed,
            "count": count,
            "step": step,
            "turns": max_turn,
            "beam": beam,
            "depth": depth,
            "action_cap": action_cap,
            "python_hash_seed": os.environ.get("PYTHONHASHSEED"),
        },
        "empty_information_baseline": baseline,
        "legal_information": legal,
        "comparison": {
            "empty_strategic_unique": baseline["strategic_unique"],
            "legal_strategic_unique": legal["strategic_unique"],
            "legal_concrete_information_unique": legal["concrete_information_unique"],
            "empty_candidate_cache_hit_fraction": baseline["estimated_strategic_cache_hit_fraction"],
            "legal_candidate_cache_hit_fraction": legal["estimated_strategic_cache_hit_fraction"],
            "legal_information_collapse_fraction": legal[
                "concrete_information_to_strategic_collapse_fraction"
            ],
        },
        "seeds": rows,
        "wall_seconds": time.time() - started,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deck", default="decklist.txt")
    parser.add_argument("--seed", type=int, default=20260821)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--step", type=int, default=1)
    parser.add_argument("--turns", type=int, default=4)
    parser.add_argument("--beam", type=int, default=500)
    parser.add_argument("--depth", type=int, default=40)
    parser.add_argument("--action-cap", type=int, default=80)
    parser.add_argument("--out", default="legal_information_collapse_profile.json")
    args = parser.parse_args()

    solver.warn_if_unset_python_hash_seed()
    deck = solver.load_deck(Path(args.deck))
    payload = run_profile(
        deck,
        base_seed=args.seed,
        count=args.count,
        step=args.step,
        max_turn=args.turns,
        beam=args.beam,
        depth=args.depth,
        action_cap=args.action_cap,
    )
    _print_measurement("EMPTY-INFORMATION BASELINE", payload["empty_information_baseline"])
    _print_measurement("LEGAL-INFORMATION STRATEGIC VALUE", payload["legal_information"])
    out = Path(args.out)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWrote {out}", flush=True)


if __name__ == "__main__":
    main()
