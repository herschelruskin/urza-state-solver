#!/usr/bin/env python3
"""Paired evaluation of rollout-v6 vs one-step Q vs bounded two-step Q.

This is an evaluation-only harness.  All three modes receive the same held-out
opening and the same outer hidden world.  Q uses a separate fixed internal RNG
namespace, so changing contingent depth cannot change the physical test world.

Profiles:
- targeted: 10 tutor-rich/previously-audited kept hands, 4 outer worlds each;
- broad: all 27 human-kept hands, 2 outer worlds each.

The comparison isolates the new feature:
- one_step: selective tutor-Q with contingent=False;
- two_step: the same controller with contingent=True.

No human labels are used to choose actions or tune Q.
"""

from __future__ import annotations

import argparse
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

TARGETED_IDS=(12,13,19,20,21,24,25,27,29,33)
OUTER_SEED=2026082801
Q_SEED=2026082802
HORIZON=6
MAX_STEPS=512
SCREEN_ROLLOUTS=1
CONFIRM_ROLLOUTS=2
SHORTLIST_SIZE=3


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


def load_fixture():
    return json.loads(
        Path("benchmarks/human/human_mulligan_exact_hands.json")
        .read_text(encoding="utf-8")
    )


def value_json(value):
    return {
        "win_probability":value.win_probability,
        "exact_win":list(value.exact_win),
        "cumulative":[value.win_by(t) for t in range(1,value.horizon+1)],
        "no_win":value.no_win,
        "comparison_key":list(value.comparison_key()),
        "win_families":[list(x) for x in value.win_families],
    }


def individual_compare(a,b):
    """Compare two single-world outcomes: +1 means a better than b."""
    aw=a.won
    bw=b.won
    if aw!=bw:
        return 1 if aw else -1
    if aw and bw:
        if a.win_turn<b.win_turn:
            return 1
        if a.win_turn>b.win_turn:
            return -1
    return 0


def decision_rows(result):
    return [
        {
            "sequence":x.sequence,
            "turn":x.turn,
            "decision_id":x.decision_id,
            "v6_action":x.v6_action,
            "chosen_action":x.chosen_action,
            "overridden":bool(x.overridden),
            "screen_candidates":x.screen_candidate_count,
            "confirm_candidates":x.confirm_candidate_count,
            "v6_value_key":list(x.v6_value_key),
            "chosen_value_key":list(x.chosen_value_key),
        }
        for x in result.q_decisions
    ]


def first_decision_difference(one,two):
    one_rows=decision_rows(one)
    two_rows=decision_rows(two)
    by_one={(x["turn"],x["decision_id"]):x for x in one_rows}
    by_two={(x["turn"],x["decision_id"]):x for x in two_rows}
    for key in sorted(set(by_one)|set(by_two),key=repr):
        a=by_one.get(key)
        b=by_two.get(key)
        if a is None or b is None:
            return {"key":list(key),"one_step":a,"two_step":b}
        if a["chosen_action"]!=b["chosen_action"]:
            return {"key":list(key),"one_step":a,"two_step":b}
    return None


def run_q(sampled,leaf,*,contingent,cache):
    controller=SelectiveTutorQController(
        continuation_policy=leaf,
        horizon=HORIZON,
        mc_root_seed=Q_SEED,
        screen_rollouts=SCREEN_ROLLOUTS,
        confirm_rollouts=CONFIRM_ROLLOUTS,
        shortlist_size=SHORTLIST_SIZE,
        max_episode_steps=MAX_STEPS,
        decision_cache=cache,
        contingent=contingent,
    )
    return run_selective_tutor_q_episode(
        sampled,
        controller=controller,
        horizon=HORIZON,
        max_steps=MAX_STEPS,
    )


def profile_config(profile,fixture):
    if profile=="targeted":
        return TARGETED_IDS,4
    kept=tuple(
        int(row["hand_id"]) for row in fixture["hands"]
        if row.get("decision")=="Keep"
    )
    if profile=="broad":
        return kept,2
    raise ValueError(profile)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--profile",choices=("targeted","broad"),required=True)
    args=parser.parse_args()

    deck=load_deck()
    fixture=load_fixture()
    by_id={int(row["hand_id"]):row for row in fixture["hands"]}
    hand_ids,outer_world_count=profile_config(args.profile,fixture)
    leaf=DeterministicRolloutPolicyV6(policy_id=PHASE5_ROLLOUT_POLICY_V6)

    one_cache=Phase5DecisionCache()
    two_cache=Phase5DecisionCache()

    all_v6=[]
    all_one=[]
    all_two=[]
    terminal_counts={
        "v6":Counter(),
        "one_step":Counter(),
        "two_step":Counter(),
    }
    rows=[]

    for hand_id in hand_ids:
        row=by_id[hand_id]
        seven=tuple(row["drawn_seven"])
        bottom=tuple(row["cards_bottomed"])
        root=opening_runtime(deck,seven,bottom)

        hand_v6=[]
        hand_one=[]
        hand_two=[]
        paired=[]
        q1_decisions=q1_overrides=q2_decisions=q2_overrides=0
        q1_steps=q2_steps=v6_steps=0

        for sample_id in range(outer_world_count):
            world=_opening_world(
                deck=deck,
                seven=seven,
                bottom=bottom,
                mc_root_seed=OUTER_SEED,
                sample_id=sample_id,
            )

            v6_runtime=materialize_hidden_world(root,world)
            validate_information_against_state(
                v6_runtime.information,v6_runtime.true_state
            )
            v6=run_deterministic_episode(
                v6_runtime,horizon=HORIZON,max_steps=MAX_STEPS,policy=leaf
            )
            v6_out=_episode_outcome(v6,horizon=HORIZON)
            hand_v6.append(v6_out)
            all_v6.append(v6_out)
            terminal_counts["v6"][v6.terminal_reason]+=1
            v6_steps+=len(v6.steps)

            one_runtime=materialize_hidden_world(root,world)
            one=run_q(
                one_runtime,leaf,contingent=False,cache=one_cache
            )
            one_out=_episode_outcome(one.episode,horizon=HORIZON)
            hand_one.append(one_out)
            all_one.append(one_out)
            terminal_counts["one_step"][one.episode.terminal_reason]+=1
            q1_decisions+=len(one.q_decisions)
            q1_overrides+=sum(x.overridden for x in one.q_decisions)
            q1_steps+=len(one.episode.steps)

            two_runtime=materialize_hidden_world(root,world)
            two=run_q(
                two_runtime,leaf,contingent=True,cache=two_cache
            )
            two_out=_episode_outcome(two.episode,horizon=HORIZON)
            hand_two.append(two_out)
            all_two.append(two_out)
            terminal_counts["two_step"][two.episode.terminal_reason]+=1
            q2_decisions+=len(two.q_decisions)
            q2_overrides+=sum(x.overridden for x in two.q_decisions)
            q2_steps+=len(two.episode.steps)

            paired.append({
                "sample_id":sample_id,
                "v6":{"win_turn":v6.win_turn,"family":v6.win_family,"reason":v6.terminal_reason},
                "one_step":{"win_turn":one.win_turn,"family":one.win_family,"reason":one.episode.terminal_reason},
                "two_step":{"win_turn":two.win_turn,"family":two.win_family,"reason":two.episode.terminal_reason},
                "two_vs_one":individual_compare(two_out,one_out),
                "one_vs_v6":individual_compare(one_out,v6_out),
                "two_vs_v6":individual_compare(two_out,v6_out),
                "one_q_decisions":decision_rows(one),
                "two_q_decisions":decision_rows(two),
                "first_q_difference":first_decision_difference(one,two),
            })

        v6_value=_value_from_outcomes(tuple(hand_v6),horizon=HORIZON)
        one_value=_value_from_outcomes(tuple(hand_one),horizon=HORIZON)
        two_value=_value_from_outcomes(tuple(hand_two),horizon=HORIZON)

        rows.append({
            "hand_id":hand_id,
            "mulligan_count":row.get("mulligan_count"),
            "keep_size":row.get("keep_size"),
            "seven":list(seven),
            "bottom":list(bottom),
            "v6":value_json(v6_value),
            "one_step":value_json(one_value),
            "two_step":value_json(two_value),
            "delta_two_vs_one":two_value.win_probability-one_value.win_probability,
            "delta_one_vs_v6":one_value.win_probability-v6_value.win_probability,
            "delta_two_vs_v6":two_value.win_probability-v6_value.win_probability,
            "two_vs_one_value_comparison":(
                "two_better" if two_value.comparison_key()>one_value.comparison_key()
                else "one_better" if two_value.comparison_key()<one_value.comparison_key()
                else "tie"
            ),
            "one_vs_v6_value_comparison":(
                "one_better" if one_value.comparison_key()>v6_value.comparison_key()
                else "v6_better" if one_value.comparison_key()<v6_value.comparison_key()
                else "tie"
            ),
            "two_vs_v6_value_comparison":(
                "two_better" if two_value.comparison_key()>v6_value.comparison_key()
                else "v6_better" if two_value.comparison_key()<v6_value.comparison_key()
                else "tie"
            ),
            "one_q_decisions":q1_decisions,
            "one_q_overrides":q1_overrides,
            "two_q_decisions":q2_decisions,
            "two_q_overrides":q2_overrides,
            "mean_steps":{
                "v6":v6_steps/outer_world_count,
                "one_step":q1_steps/outer_world_count,
                "two_step":q2_steps/outer_world_count,
            },
            "paired_worlds":paired,
        })

    overall_v6=_value_from_outcomes(tuple(all_v6),horizon=HORIZON)
    overall_one=_value_from_outcomes(tuple(all_one),horizon=HORIZON)
    overall_two=_value_from_outcomes(tuple(all_two),horizon=HORIZON)

    world_two_vs_one=Counter()
    world_one_vs_v6=Counter()
    world_two_vs_v6=Counter()
    changed_decision_worlds=0
    for row in rows:
        for pair in row["paired_worlds"]:
            world_two_vs_one[pair["two_vs_one"]]+=1
            world_one_vs_v6[pair["one_vs_v6"]]+=1
            world_two_vs_v6[pair["two_vs_v6"]]+=1
            if pair["first_q_difference"] is not None:
                changed_decision_worlds+=1

    hand_two_vs_one=Counter(row["two_vs_one_value_comparison"] for row in rows)
    hand_one_vs_v6=Counter(row["one_vs_v6_value_comparison"] for row in rows)
    hand_two_vs_v6=Counter(row["two_vs_v6_value_comparison"] for row in rows)

    payload={
        "kind":"phase5-bounded-two-step-q-evaluation",
        "profile":args.profile,
        "hand_ids":list(hand_ids),
        "hand_count":len(hand_ids),
        "outer_worlds_per_hand":outer_world_count,
        "total_paired_worlds":len(all_v6),
        "outer_seed":OUTER_SEED,
        "q_seed":Q_SEED,
        "horizon":HORIZON,
        "q_budgets":{
            "screen":SCREEN_ROLLOUTS,
            "confirm":CONFIRM_ROLLOUTS,
            "shortlist":SHORTLIST_SIZE,
        },
        "overall":{
            "v6":value_json(overall_v6),
            "one_step":value_json(overall_one),
            "two_step":value_json(overall_two),
            "delta_two_vs_one":overall_two.win_probability-overall_one.win_probability,
            "delta_one_vs_v6":overall_one.win_probability-overall_v6.win_probability,
            "delta_two_vs_v6":overall_two.win_probability-overall_v6.win_probability,
        },
        "hand_comparisons":{
            "two_vs_one":dict(hand_two_vs_one),
            "one_vs_v6":dict(hand_one_vs_v6),
            "two_vs_v6":dict(hand_two_vs_v6),
        },
        "world_comparisons":{
            "two_vs_one":{"better":world_two_vs_one[1],"tie":world_two_vs_one[0],"worse":world_two_vs_one[-1]},
            "one_vs_v6":{"better":world_one_vs_v6[1],"tie":world_one_vs_v6[0],"worse":world_one_vs_v6[-1]},
            "two_vs_v6":{"better":world_two_vs_v6[1],"tie":world_two_vs_v6[0],"worse":world_two_vs_v6[-1]},
        },
        "changed_q_decision_worlds":changed_decision_worlds,
        "terminal_reasons":{k:dict(v) for k,v in terminal_counts.items()},
        "cache":{
            "one_step":{"hits":one_cache.stats.hits,"misses":one_cache.stats.misses},
            "two_step":{"hits":two_cache.stats.hits,"misses":two_cache.stats.misses},
        },
        "rows":rows,
    }

    out=Path(f"phase5_two_step_q_eval_{args.profile}.json")
    out.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")

    changed=[
        {
            "hand_id":row["hand_id"],
            "v6":row["v6"]["win_probability"],
            "one":row["one_step"]["win_probability"],
            "two":row["two_step"]["win_probability"],
            "two_vs_one":row["two_vs_one_value_comparison"],
            "two_delta":row["delta_two_vs_one"],
            "one_overrides":row["one_q_overrides"],
            "two_overrides":row["two_q_overrides"],
        }
        for row in rows
        if row["two_vs_one_value_comparison"]!="tie"
        or row["one_vs_v6_value_comparison"]!="tie"
    ]

    print("EVAL_SUMMARY="+json.dumps({
        "profile":args.profile,
        "hands":len(hand_ids),
        "paired_worlds":len(all_v6),
        "overall_pwin":{
            "v6":overall_v6.win_probability,
            "one_step":overall_one.win_probability,
            "two_step":overall_two.win_probability,
        },
        "overall_exact_win":{
            "v6":list(overall_v6.exact_win),
            "one_step":list(overall_one.exact_win),
            "two_step":list(overall_two.exact_win),
        },
        "delta_two_vs_one":payload["overall"]["delta_two_vs_one"],
        "hand_comparisons":payload["hand_comparisons"],
        "world_comparisons":payload["world_comparisons"],
        "changed_q_decision_worlds":changed_decision_worlds,
        "terminal_reasons":payload["terminal_reasons"],
        "cache":payload["cache"],
        "changed_hands":changed,
    },sort_keys=True))


if __name__=="__main__":
    main()
