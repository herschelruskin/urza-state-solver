#!/usr/bin/env python3
"""Paired multi-world expected-value diagnostic for selective tutor-Q.

The previous held-out diagnostic used one concrete hidden world per opening. That is
excellent for tracing mechanics, but a belief-based non-Oracle policy can choose an
action with higher expected value and still lose that particular world.

This pilot therefore evaluates v6 and selective tutor-Q on the *same set* of outer
hidden worlds for each fixed observed opening. Q uses a separate RNG namespace for
its internal counterfactual worlds. The output is diagnostic only; it does not train
or tune the policy and does not assert that four outer worlds are a calibrated
estimate.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from information_state_propagation import validate_information_against_state
from non_oracle_episode import run_deterministic_episode
from phase4_hidden_world import materialize_hidden_world
from phase4_monte_carlo import _episode_outcome, _value_from_outcomes
from phase5_monte_carlo import Phase5DecisionCache
from phase5_mulligan import _opening_world, opening_runtime
from phase5_rollout_policy_v6 import (
    DeterministicRolloutPolicyV6,
    PHASE5_ROLLOUT_POLICY_V6,
)
from phase5_selective_tutor_q import (
    SelectiveTutorQController,
    run_selective_tutor_q_episode,
)

SELECTED=(19,20,21,24,27)
OUTER_WORLD_COUNT=4
OUTER_MC_ROOT_SEED=2026082601
Q_MC_ROOT_SEED=2026082602
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


def value_json(value):
    return {
        "win_probability":value.win_probability,
        "exact_win":list(value.exact_win),
        "cumulative":[value.win_by(t) for t in range(1,value.horizon+1)],
        "no_win":value.no_win,
        "comparison_key":list(value.comparison_key()),
        "win_families":[list(x) for x in value.win_families],
    }


def main():
    deck=load_deck()
    fixture=json.loads(
        Path("benchmarks/human/human_mulligan_exact_hands.json")
        .read_text(encoding="utf-8")
    )
    by_id={int(row["hand_id"]):row for row in fixture["hands"]}
    leaf=DeterministicRolloutPolicyV6(policy_id=PHASE5_ROLLOUT_POLICY_V6)
    q_cache=Phase5DecisionCache()
    rows=[]

    for hand_id in SELECTED:
        row=by_id[hand_id]
        seven=tuple(row["drawn_seven"])
        bottom=tuple(row["cards_bottomed"])
        root=opening_runtime(deck,seven,bottom)

        v6_outcomes=[]
        q_outcomes=[]
        v6_reasons=Counter()
        q_reasons=Counter()
        paired=[]

        for sample_id in range(OUTER_WORLD_COUNT):
            world=_opening_world(
                deck=deck,
                seven=seven,
                bottom=bottom,
                mc_root_seed=OUTER_MC_ROOT_SEED,
                sample_id=sample_id,
            )

            v6_runtime=materialize_hidden_world(root,world)
            validate_information_against_state(
                v6_runtime.information,v6_runtime.true_state
            )
            v6=run_deterministic_episode(
                v6_runtime,horizon=HORIZON,max_steps=512,policy=leaf
            )
            v6_reasons[v6.terminal_reason]+=1
            v6_outcomes.append(_episode_outcome(v6,horizon=HORIZON))

            q_runtime=materialize_hidden_world(root,world)
            controller=SelectiveTutorQController(
                continuation_policy=leaf,
                horizon=HORIZON,
                mc_root_seed=Q_MC_ROOT_SEED,
                screen_rollouts=1,
                confirm_rollouts=2,
                shortlist_size=3,
                max_episode_steps=512,
                decision_cache=q_cache,
            )
            q=run_selective_tutor_q_episode(
                q_runtime,
                controller=controller,
                horizon=HORIZON,
                max_steps=512,
            )
            q_reasons[q.episode.terminal_reason]+=1
            q_outcomes.append(_episode_outcome(q.episode,horizon=HORIZON))

            paired.append({
                "sample_id":sample_id,
                "v6_win_turn":v6.win_turn,
                "v6_win_family":v6.win_family,
                "v6_terminal_reason":v6.terminal_reason,
                "q_win_turn":q.win_turn,
                "q_win_family":q.win_family,
                "q_terminal_reason":q.episode.terminal_reason,
                "q_decisions":len(q.q_decisions),
                "q_overrides":sum(x.overridden for x in q.q_decisions),
            })

        v6_value=_value_from_outcomes(tuple(v6_outcomes),horizon=HORIZON)
        q_value=_value_from_outcomes(tuple(q_outcomes),horizon=HORIZON)
        rows.append({
            "hand_id":hand_id,
            "observed_seven":list(seven),
            "bottom":list(bottom),
            "v6":value_json(v6_value),
            "q":value_json(q_value),
            "delta_win_probability":q_value.win_probability-v6_value.win_probability,
            "value_comparison":(
                "q_better" if q_value.comparison_key()>v6_value.comparison_key()
                else "v6_better" if q_value.comparison_key()<v6_value.comparison_key()
                else "tie"
            ),
            "v6_terminal_reasons":sorted(v6_reasons.items()),
            "q_terminal_reasons":sorted(q_reasons.items()),
            "paired_worlds":paired,
        })

    payload={
        "kind":"phase5-tutor-q-paired-expected-value-pilot",
        "selected_hands":list(SELECTED),
        "outer_world_count":OUTER_WORLD_COUNT,
        "outer_mc_root_seed":OUTER_MC_ROOT_SEED,
        "q_mc_root_seed":Q_MC_ROOT_SEED,
        "q_screen_rollouts":1,
        "q_confirm_rollouts":2,
        "horizon":HORIZON,
        "q_cache_hits":q_cache.stats.hits,
        "q_cache_misses":q_cache.stats.misses,
        "rows":rows,
    }
    Path("phase5_tutor_q_expected_value_pilot.json").write_text(
        json.dumps(payload,indent=2)+"\n",encoding="utf-8"
    )
    print(json.dumps({
        "q_cache":{"hits":q_cache.stats.hits,"misses":q_cache.stats.misses},
        "hands":{
            row["hand_id"]:{
                "v6_pwin":row["v6"]["win_probability"],
                "q_pwin":row["q"]["win_probability"],
                "delta":row["delta_win_probability"],
                "comparison":row["value_comparison"],
            }
            for row in rows
        },
    },indent=2))


if __name__=="__main__":
    main()
