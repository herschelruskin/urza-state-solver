#!/usr/bin/env python3
"""A/B probe for Hand 25 under the Whir target-frontier policy.

Runs exactly one legal bottom x one outer hidden-world coordinate under the
frozen Phase-5H production player.  This is diagnostic-only: it does not replace
or modify the authoritative homogeneous Phase-5I benchmark artifact.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import time

import non_oracle_rules_adapter_v2 as rules
import non_oracle_episode as episode_mod
import phase5_selective_tutor_q as tutor_q
import phase5_monte_carlo as phase5_mc
from phase5_mulligan import OpeningEnvironment, OpeningKeepEvaluator, unique_bottom_subsets
from phase5_production_policy import (
    PHASE5H_PRODUCTION_Q,
    make_phase5h_production_decision_cache,
    make_phase5h_production_episode_runner,
)
from phase5_rollout_policy_v6 import DeterministicRolloutPolicyV6, PHASE5_ROLLOUT_POLICY_V6
from phase5i_human_hand_eval import (
    HORIZON,
    MC_ROOT_SEED,
    Q_MC_ROOT_SEED,
    load_deck,
)


HAND_ID = 25
STAGE = 2

_original_request = rules.rules_decision_request
max_actions = 0
max_kinds = ()
request_count = 0


def traced_request(*args, **kwargs):
    global max_actions, max_kinds, request_count
    request = _original_request(*args, **kwargs)
    request_count += 1
    n = len(request.actions)
    if n > max_actions:
        max_actions = n
        kinds = Counter(str(action.kind) for action in request.actions)
        max_kinds = tuple(sorted(kinds.items()))
        print(
            "H25_FANOUT_NEW_MAX "
            f"requests={request_count} actions={n} kinds={max_kinds!r}",
            flush=True,
        )
    if request_count % 1000 == 0:
        print(
            "H25_REQUEST_HEARTBEAT "
            f"requests={request_count} max_actions={max_actions}",
            flush=True,
        )
    return request


# Cover the direct episode loop plus bounded-Q/MC subloops.
rules.rules_decision_request = traced_request
episode_mod.rules_decision_request = traced_request
tutor_q.rules_decision_request = traced_request
phase5_mc.rules_decision_request = traced_request


def fixture_row():
    fixture = json.loads(
        Path("benchmarks/human/human_mulligan_exact_hands.json").read_text(encoding="utf-8")
    )
    return next(x for x in fixture["hands"] if int(x["hand_id"]) == HAND_ID)


def step_json(step):
    return {
        "sequence": int(step.sequence),
        "turn_before": int(step.turn_before),
        "window_kind": str(step.window_kind),
        "action_id": str(step.action_id),
        "action_kind": str(step.action_kind),
        "action_label": str(step.action_label),
        "turn_after": int(step.turn_after),
        "won_after": bool(step.won_after),
        "win_family_after": str(step.win_family_after),
    }


def q_json(row):
    return {
        "sequence": int(row.sequence),
        "turn": int(row.turn),
        "decision_id": str(row.decision_id),
        "v6_action": str(row.v6_action),
        "chosen_action": str(row.chosen_action),
        "overridden": bool(row.overridden),
        "screen_candidate_count": int(row.screen_candidate_count),
        "confirm_candidate_count": int(row.confirm_candidate_count),
        "v6_value_key": list(row.v6_value_key),
        "chosen_value_key": list(row.chosen_value_key),
        "proposed_action": str(row.proposed_action),
        "proposed_value_key": list(row.proposed_value_key),
        "validation_rollouts": int(row.validation_rollouts),
        "paired_better": int(row.paired_better),
        "paired_worse": int(row.paired_worse),
        "paired_ties": int(row.paired_ties),
        "paired_sign_p": float(row.paired_sign_p),
        "gate_reason": str(row.gate_reason),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bottom-card", required=True)
    p.add_argument("--sample-id", type=int, required=True, choices=(0, 1, 2, 3))
    args = p.parse_args()

    row = fixture_row()
    seven = tuple(row["drawn_seven"])
    legal = unique_bottom_subsets(seven, STAGE)
    bottom = (str(args.bottom_card),)
    normalized = tuple(sorted(bottom))
    if normalized not in set(legal):
        raise SystemExit(f"illegal hand-25 bottom {normalized!r}; legal={legal!r}")

    cache = make_phase5h_production_decision_cache()
    production_runner = make_phase5h_production_episode_runner(
        mc_root_seed=Q_MC_ROOT_SEED,
        decision_cache=cache,
        config=PHASE5H_PRODUCTION_Q,
    )
    traces = []

    def wrapped_runner(runtime, *, horizon, policy, max_steps):
        started = time.monotonic()
        print(
            "H25_WORLD_BEGIN "
            f"bottom={args.bottom_card!r} sample={int(args.sample_id)} "
            f"turn={runtime.true_state.turn}",
            flush=True,
        )
        result = production_runner(
            runtime,
            horizon=horizon,
            policy=policy,
            max_steps=max_steps,
        )
        elapsed = time.monotonic() - started
        ep = getattr(result, "episode", result)
        qrows = tuple(getattr(result, "q_decisions", ()))
        trace = {
            "elapsed_seconds": elapsed,
            "terminal_reason": str(ep.terminal_reason),
            "win_turn": None if ep.win_turn is None else int(ep.win_turn),
            "win_family": str(ep.win_family),
            "steps": [step_json(x) for x in ep.steps],
            "q_decisions": [q_json(x) for x in qrows],
        }
        traces.append(trace)
        print(
            "H25_WORLD_END "
            f"bottom={args.bottom_card!r} sample={int(args.sample_id)} "
            f"elapsed={elapsed:.3f}s terminal={ep.terminal_reason!r} "
            f"win_turn={ep.win_turn!r} win_family={ep.win_family!r} "
            f"steps={len(ep.steps)} q_decisions={len(qrows)}",
            flush=True,
        )
        for step in ep.steps:
            print(
                "H25_PLAY "
                f"seq={step.sequence} turn={step.turn_before}->{step.turn_after} "
                f"kind={step.action_kind!r} action={step.action_label!r}",
                flush=True,
            )
        for qrow in qrows:
            print(
                "H25_Q "
                f"seq={qrow.sequence} turn={qrow.turn} decision={qrow.decision_id!r} "
                f"v6={qrow.v6_action!r} chosen={qrow.chosen_action!r} "
                f"override={qrow.overridden} gate={qrow.gate_reason!r}",
                flush=True,
            )
        return result

    evaluator = OpeningKeepEvaluator(
        load_deck(),
        rollout_count=1,
        mc_root_seed=MC_ROOT_SEED,
        horizon=HORIZON,
        continuation_policy=DeterministicRolloutPolicyV6(policy_id=PHASE5_ROLLOUT_POLICY_V6),
        max_episode_steps=512,
        strict_terminal_reasons=True,
        episode_runner=wrapped_runner,
        opening_environment=OpeningEnvironment(seat=1, player_count=4),
    )

    started = time.monotonic()
    evaluated = evaluator.evaluate(
        seven,
        stage=STAGE,
        candidate_bottoms=(normalized,),
        sample_start=int(args.sample_id),
    )
    elapsed = time.monotonic() - started
    estimate = evaluated.best
    payload = {
        "kind": "phase5i-hand25-frontier-probe",
        "hand_id": HAND_ID,
        "stage": STAGE,
        "bottom": list(normalized),
        "sample_id": int(args.sample_id),
        "coordinate_role": "screen" if int(args.sample_id) == 0 else "confirmation",
        "mc_root_seed": MC_ROOT_SEED,
        "q_mc_root_seed": Q_MC_ROOT_SEED,
        "elapsed_seconds": elapsed,
        "max_action_request": int(max_actions),
        "max_action_kinds": [[name, int(count)] for name, count in max_kinds],
        "decision_request_count": int(request_count),
        "value_key": list(estimate.value.comparison_key()),
        "win_probability": float(estimate.value.win_probability),
        "terminal_reasons": [list(x) for x in estimate.terminal_reason_counts],
        "q_cache": {"hits": cache.stats.hits, "misses": cache.stats.misses},
        "trajectory": traces[0] if traces else None,
    }
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in args.bottom_card).strip("_")
    out = Path(f"phase5i_hand25_frontier_{safe}_n{int(args.sample_id)}.json")
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("H25_DIAG=" + json.dumps({
        "bottom": payload["bottom"],
        "sample_id": payload["sample_id"],
        "role": payload["coordinate_role"],
        "elapsed_seconds": payload["elapsed_seconds"],
        "max_action_request": payload["max_action_request"],
        "requests": payload["decision_request_count"],
        "value_key": payload["value_key"],
        "terminal_reasons": payload["terminal_reasons"],
        "q_cache": payload["q_cache"],
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
