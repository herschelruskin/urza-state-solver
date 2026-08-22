#!/usr/bin/env python3
"""Measure concrete-to-strategic state collapse without changing Oracle search.

This is a diagnostic harness, not a production policy. It reuses the validated
Oracle action generation, exact-state merging, dominance pruning, beam selection,
and end-turn transitions while observing every generated candidate with
``StrategicKeyProfiler``.

IMPORTANT INFORMATION-STATE LIMITATION
--------------------------------------
The current Oracle engine does not yet propagate a legal ``InformationState``.
This first profiler therefore projects every candidate with an empty
``InformationState``. That deliberately forgets exact hidden order, but it also
forgets legally known top/bottom constraints acquired through tutors/scry/top
inspection. Its collapse numbers are therefore an *upper-bound potential* for
state merging, not a final non-Oracle cache-hit estimate.

The harness profiles the Oracle 7A opening candidate for each requested seed. It
does not branch across mulligan stages. This keeps the measurement focused and
cheap while preserving the same in-game transition/search machinery.
"""

from __future__ import annotations

import argparse
import heapq
import json
import os
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import urza_solver as solver
from solver_architecture import InformationState
from strategic_value_state import StrategicKeyProfiler


EMPTY_INFORMATION = InformationState()


def _observe(profilers: Iterable[StrategicKeyProfiler], state: solver.State, depth: int) -> None:
    for profiler in profilers:
        profiler.observe(state, EMPTY_INFORMATION, depth=depth)


def oracle_7a_deal(seed: int, deck: List[str]) -> tuple[bool, List[str]]:
    """Return the exact Oracle 7A deal and fixed Caverns seating result."""
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

    # Match search_hand's pregame Gemstone Caverns handling exactly.
    if "Gemstone Caverns" in state.hand and caverns_live and len(state.hand) > 1:
        choices = [card for card in state.hand if card != "Gemstone Caverns"]
        exiled = min(choices, key=lambda card: solver.card_priority(state, card))
        state = replace(
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


def profile_candidate(
    deck_order: List[str],
    *,
    caverns_live: bool,
    seed: int,
    max_turn: int,
    beam: int,
    max_actions_per_turn: int,
    profilers: Sequence[StrategicKeyProfiler],
) -> Dict[str, Any]:
    """Replay search_hand's core loop with observation hooks only."""
    state = _initial_state(deck_order, caverns_live, seed)
    states = [state]
    searched = 0
    max_depth_reached = 0
    graph_stats = solver.new_graph_stats()
    _observe(profilers, state, 0)

    for turn in range(1, max_turn + 1):
        frontier = states
        expanded_this_turn = set()
        best_by: Dict[Any, solver.State] = {}

        for depth in range(max_actions_per_turn):
            max_depth_reached = max(max_depth_reached, depth + 1)
            for current in frontier:
                exact = current.key()
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
                        "graph": solver.finalize_graph_stats(graph_stats),
                    }

                actions = solver.legal_actions(current)
                graph_stats["edges_generated"] += len(actions)
                graph_stats["max_raw_successors"] = max(
                    graph_stats["max_raw_successors"], len(actions)
                )

                for successor in actions:
                    successor = solver.check_win(successor)
                    # Observe each generated candidate before exact-state merging.
                    _observe(profilers, successor, depth + 1)
                    if successor.won:
                        return {
                            "seed": seed,
                            "win_turn": successor.turn,
                            "family": successor.win_family,
                            "searched": searched,
                            "max_depth_reached": max_depth_reached,
                            "graph": solver.finalize_graph_stats(graph_stats),
                        }
                    key = successor.key()
                    old = best_by.get(key)
                    if old is not None:
                        graph_stats["exact_key_merges"] += 1
                    if old is None or solver.score(successor) > solver.score(old):
                        best_by[key] = successor

            if not best_by:
                break

            pre_dominance = list(best_by.values())
            post_dominance = solver.dominance_prune(pre_dominance)
            graph_stats["dominance_pruned"] += max(
                0, len(pre_dominance) - len(post_dominance)
            )
            graph_stats["beam_pruned"] += max(0, len(post_dominance) - beam)
            frontier = heapq.nlargest(beam, post_dominance, key=solver.score)
            graph_stats["layers"] += 1
            graph_stats["max_frontier"] = max(
                graph_stats["max_frontier"], len(frontier)
            )
            best_by = {}

        states = solver.end_turn_frontier(
            frontier,
            beam,
            resolve_remora_upkeep=(turn < max_turn),
            graph_stats=graph_stats,
        )
        # End-turn/upkeep closure can create states that were not direct legal-action
        # successors. Record them as depth zero of their resulting turn.
        for transitioned in states:
            _observe(profilers, transitioned, 0)

    return {
        "seed": seed,
        "win_turn": None,
        "family": "",
        "searched": searched,
        "max_depth_reached": max_depth_reached,
        "graph": solver.finalize_graph_stats(graph_stats),
    }


def _pct(value: float) -> str:
    return f"{100.0 * value:6.2f}%"


def print_summary(label: str, summary: Dict[str, Any]) -> None:
    print(f"\n=== {label} ===", flush=True)
    print(f"observations:       {summary['observations']:,}", flush=True)
    print(f"concrete unique:    {summary['concrete_unique']:,}", flush=True)
    print(f"strategic unique:   {summary['strategic_unique']:,}", flush=True)
    print(
        "collapse potential: "
        + _pct(summary["concrete_to_strategic_collapse_fraction"]),
        flush=True,
    )
    print(
        "candidate cache-hit: "
        + _pct(summary["estimated_strategic_cache_hit_fraction"]),
        flush=True,
    )
    if summary.get("by_turn"):
        print("by turn:", flush=True)
        for turn, metrics in summary["by_turn"].items():
            print(
                f"  T{turn}: obs={metrics['observations']:,} "
                f"concrete={metrics['concrete_unique']:,} "
                f"strategic={metrics['strategic_unique']:,} "
                f"collapse={_pct(metrics['concrete_to_strategic_collapse_fraction'])} "
                f"hit={_pct(metrics['estimated_strategic_cache_hit_fraction'])}",
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
    global_profiler = StrategicKeyProfiler()
    rows = []
    started = time.time()

    try:
        for index in range(count):
            seed = base_seed + index * step
            caverns_live, deck_order = oracle_7a_deal(seed, deck)
            local_profiler = StrategicKeyProfiler()
            print(
                f"[strategic-profile] seed={seed} 7A start "
                f"turns={max_turn} beam={beam} depth={depth} action_cap={action_cap}",
                flush=True,
            )
            row = profile_candidate(
                deck_order,
                caverns_live=caverns_live,
                seed=seed,
                max_turn=max_turn,
                beam=beam,
                max_actions_per_turn=depth,
                profilers=(global_profiler, local_profiler),
            )
            row["strategic"] = local_profiler.summary()
            rows.append(row)
            print(
                f"[strategic-profile] seed={seed} "
                f"win={row['win_turn'] or '-'} family={row['family'] or '-'} "
                f"searched={row['searched']:,} "
                f"collapse={_pct(row['strategic']['concrete_to_strategic_collapse_fraction'])} "
                f"candidate_hit={_pct(row['strategic']['estimated_strategic_cache_hit_fraction'])}",
                flush=True,
            )
    finally:
        solver.ACTION_CAP = old_action_cap

    overall = global_profiler.summary()
    return {
        "measurement_kind": "strategic-collapse-potential",
        "decision_neutral": True,
        "search_scope": "Oracle 7A opening candidate only; no mulligan branching",
        "information_assumption": (
            "EMPTY InformationState at every observation. This is an upper-bound "
            "collapse-potential measurement and may over-collapse states after "
            "legal top/bottom/count information is acquired."
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
        "overall": overall,
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
    parser.add_argument("--out", default="strategic_collapse_profile.json")
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
    print_summary("OVERALL STRATEGIC COLLAPSE POTENTIAL", payload["overall"])
    out = Path(args.out)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWrote {out}", flush=True)
    print(
        "Interpretation warning: this is NOT yet a final DP cache-hit estimate; "
        "legal InformationState propagation comes next.",
        flush=True,
    )


if __name__ == "__main__":
    main()
