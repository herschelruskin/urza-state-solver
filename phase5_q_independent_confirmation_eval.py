#!/usr/bin/env python3
"""Focused paired regression on hands changed by the preliminary Q sweep."""

from __future__ import annotations

import json
from pathlib import Path

from information_state_propagation import validate_information_against_state
from non_oracle_episode import run_deterministic_episode
from phase4_hidden_world import materialize_hidden_world
from phase5_monte_carlo import Phase5DecisionCache
from phase5_mulligan import _opening_world, opening_runtime
from phase5_rollout_policy_v6 import DeterministicRolloutPolicyV6, PHASE5_ROLLOUT_POLICY_V6
from phase5_selective_tutor_q import SelectiveTutorQController, run_selective_tutor_q_episode

HAND_IDS=(1,12,20,21,30,33)
OUTER_SEED=2026082801
Q_SEED=2026082802
HORIZON=6


def load_deck():
    cards=[]
    for raw in Path("decklist.txt").read_text(encoding="utf-8").splitlines():
        line=raw.strip()
        if not line:
            continue
        count,name=line.split(" ",1)
        if name=="Urza, Lord High Artificer":
            continue
        cards.extend([name]*int(count))
    assert len(cards)==99
    return tuple(cards)


def decision_rows(result):
    return [
        {
            "sequence":x.sequence,
            "turn":x.turn,
            "decision_id":x.decision_id,
            "v6_action":x.v6_action,
            "chosen_action":x.chosen_action,
            "overridden":bool(x.overridden),
            "v6_value_key":list(x.v6_value_key),
            "chosen_value_key":list(x.chosen_value_key),
        }
        for x in result.q_decisions
    ]


def run_q(runtime,leaf,*,contingent,cache):
    controller=SelectiveTutorQController(
        continuation_policy=leaf,
        horizon=HORIZON,
        mc_root_seed=Q_SEED,
        screen_rollouts=1,
        confirm_rollouts=2,
        shortlist_size=3,
        max_episode_steps=512,
        decision_cache=cache,
        contingent=contingent,
    )
    return run_selective_tutor_q_episode(
        runtime,controller=controller,horizon=HORIZON,max_steps=512
    )


def main():
    deck=load_deck()
    fixture=json.loads(
        Path("benchmarks/human/human_mulligan_exact_hands.json").read_text(encoding="utf-8")
    )
    by_id={int(row["hand_id"]):row for row in fixture["hands"]}
    leaf=DeterministicRolloutPolicyV6(policy_id=PHASE5_ROLLOUT_POLICY_V6)
    one_cache=Phase5DecisionCache()
    two_cache=Phase5DecisionCache()
    rows=[]

    for hand_id in HAND_IDS:
        row=by_id[hand_id]
        seven=tuple(row["drawn_seven"])
        bottom=tuple(row["cards_bottomed"])
        root=opening_runtime(deck,seven,bottom)
        world=_opening_world(
            deck=deck,seven=seven,bottom=bottom,
            mc_root_seed=OUTER_SEED,sample_id=0,
        )

        v6_runtime=materialize_hidden_world(root,world)
        validate_information_against_state(v6_runtime.information,v6_runtime.true_state)
        v6=run_deterministic_episode(v6_runtime,horizon=HORIZON,max_steps=512,policy=leaf)

        one_runtime=materialize_hidden_world(root,world)
        one=run_q(one_runtime,leaf,contingent=False,cache=one_cache)

        two_runtime=materialize_hidden_world(root,world)
        two=run_q(two_runtime,leaf,contingent=True,cache=two_cache)

        rows.append({
            "hand_id":hand_id,
            "v6":{"win_turn":v6.win_turn,"family":v6.win_family,"reason":v6.terminal_reason},
            "one_step":{"win_turn":one.win_turn,"family":one.win_family,"reason":one.episode.terminal_reason},
            "two_step":{"win_turn":two.win_turn,"family":two.win_family,"reason":two.episode.terminal_reason},
            "one_decisions":decision_rows(one),
            "two_decisions":decision_rows(two),
        })

    payload={
        "kind":"phase5-independent-confirmation-changed-hand-eval",
        "hand_ids":list(HAND_IDS),
        "outer_seed":OUTER_SEED,
        "q_seed":Q_SEED,
        "screen_rollouts":1,
        "confirm_rollouts":2,
        "rows":rows,
        "wins":{
            "v6":sum(r["v6"]["win_turn"] is not None for r in rows),
            "one_step":sum(r["one_step"]["win_turn"] is not None for r in rows),
            "two_step":sum(r["two_step"]["win_turn"] is not None for r in rows),
        },
        "cache":{
            "one":{"hits":one_cache.stats.hits,"misses":one_cache.stats.misses},
            "two":{"hits":two_cache.stats.hits,"misses":two_cache.stats.misses},
        },
    }
    Path("phase5_q_independent_confirmation_eval.json").write_text(
        json.dumps(payload,indent=2)+"\n",encoding="utf-8"
    )
    print("CONFIRM_EVAL="+json.dumps({
        "wins":payload["wins"],
        "hands":{
            r["hand_id"]:{
                "v6":r["v6"]["win_turn"],
                "one":r["one_step"]["win_turn"],
                "two":r["two_step"]["win_turn"],
                "v6_family":r["v6"]["family"],
                "one_family":r["one_step"]["family"],
                "two_family":r["two_step"]["family"],
                "one_overrides":sum(x["overridden"] for x in r["one_decisions"]),
                "two_overrides":sum(x["overridden"] for x in r["two_decisions"]),
            }
            for r in rows
        },
        "cache":payload["cache"],
    },sort_keys=True))


if __name__=="__main__":
    main()
