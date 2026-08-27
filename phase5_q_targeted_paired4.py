#!/usr/bin/env python3
"""Four-world paired v6 vs one-step vs bounded-two-step Q evaluation per hand."""

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
from phase5_rollout_policy_v6 import DeterministicRolloutPolicyV6, PHASE5_ROLLOUT_POLICY_V6
from phase5_selective_tutor_q import SelectiveTutorQController, run_selective_tutor_q_episode

TARGETED=(12,13,19,20,21,24,25,27,29,33)
OUTER_WORLD_COUNT=4
OUTER_SEED=2026082801
Q_SEED=2026082802
HORIZON=6
MAX_STEPS=512
SCREEN=1
CONFIRM=2
SHORTLIST=3


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


def value_json(v):
    return {
        "win_probability":v.win_probability,
        "exact_win":list(v.exact_win),
        "cumulative":[v.win_by(t) for t in range(1,v.horizon+1)],
        "comparison_key":list(v.comparison_key()),
        "no_win":v.no_win,
        "win_families":[list(x) for x in v.win_families],
    }


def quality(out):
    if not out.won:
        return (0,0)
    return (1,-int(out.win_turn))


def compare(a,b):
    qa,qb=quality(a),quality(b)
    return 1 if qa>qb else -1 if qa<qb else 0


def qrun(runtime,leaf,*,contingent,cache):
    controller=SelectiveTutorQController(
        continuation_policy=leaf,
        horizon=HORIZON,
        mc_root_seed=Q_SEED,
        screen_rollouts=SCREEN,
        confirm_rollouts=CONFIRM,
        shortlist_size=SHORTLIST,
        max_episode_steps=MAX_STEPS,
        decision_cache=cache,
        contingent=contingent,
    )
    return run_selective_tutor_q_episode(
        runtime,controller=controller,horizon=HORIZON,max_steps=MAX_STEPS
    )


def compact_decisions(result):
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
        if x.overridden or x.v6_action!=x.chosen_action
    ]


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--hand-id",type=int,required=True)
    args=p.parse_args()
    hand_id=int(args.hand_id)
    if hand_id not in TARGETED:
        raise SystemExit(f"hand {hand_id} is not in targeted set")

    deck=load_deck()
    fixture=json.loads(Path("benchmarks/human/human_mulligan_exact_hands.json").read_text())
    row=next(x for x in fixture["hands"] if int(x["hand_id"])==hand_id)
    if not row.get("primary_benchmark_usable",True):
        raise SystemExit(f"hand {hand_id} is not exact-state usable")

    seven=tuple(row["drawn_seven"])
    bottom=tuple(row["cards_bottomed"])
    root=opening_runtime(deck,seven,bottom)
    leaf=DeterministicRolloutPolicyV6(policy_id=PHASE5_ROLLOUT_POLICY_V6)
    one_cache=Phase5DecisionCache()
    two_cache=Phase5DecisionCache()

    v6_outcomes=[]
    one_outcomes=[]
    two_outcomes=[]
    pairs=[]
    reasons={"v6":Counter(),"one":Counter(),"two":Counter()}

    for sample_id in range(OUTER_WORLD_COUNT):
        world=_opening_world(
            deck=deck,seven=seven,bottom=bottom,
            mc_root_seed=OUTER_SEED,sample_id=sample_id,
        )

        vr=materialize_hidden_world(root,world)
        validate_information_against_state(vr.information,vr.true_state)
        v6=run_deterministic_episode(vr,horizon=HORIZON,max_steps=MAX_STEPS,policy=leaf)
        vo=_episode_outcome(v6,horizon=HORIZON)
        v6_outcomes.append(vo)
        reasons["v6"][v6.terminal_reason]+=1

        one=qrun(materialize_hidden_world(root,world),leaf,contingent=False,cache=one_cache)
        oo=_episode_outcome(one.episode,horizon=HORIZON)
        one_outcomes.append(oo)
        reasons["one"][one.episode.terminal_reason]+=1

        two=qrun(materialize_hidden_world(root,world),leaf,contingent=True,cache=two_cache)
        to=_episode_outcome(two.episode,horizon=HORIZON)
        two_outcomes.append(to)
        reasons["two"][two.episode.terminal_reason]+=1

        pairs.append({
            "sample_id":sample_id,
            "v6":{"win_turn":v6.win_turn,"family":v6.win_family,"reason":v6.terminal_reason},
            "one":{"win_turn":one.win_turn,"family":one.win_family,"reason":one.episode.terminal_reason},
            "two":{"win_turn":two.win_turn,"family":two.win_family,"reason":two.episode.terminal_reason},
            "one_vs_v6":compare(oo,vo),
            "two_vs_v6":compare(to,vo),
            "two_vs_one":compare(to,oo),
            "one_overrides":compact_decisions(one),
            "two_overrides":compact_decisions(two),
        })

    vv=_value_from_outcomes(tuple(v6_outcomes),horizon=HORIZON)
    ov=_value_from_outcomes(tuple(one_outcomes),horizon=HORIZON)
    tv=_value_from_outcomes(tuple(two_outcomes),horizon=HORIZON)
    result={
        "hand_id":hand_id,
        "outer_worlds":OUTER_WORLD_COUNT,
        "outer_seed":OUTER_SEED,
        "q_seed":Q_SEED,
        "budgets":{"screen":SCREEN,"confirm":CONFIRM,"shortlist":SHORTLIST},
        "seven":list(seven),
        "bottom":list(bottom),
        "v6":value_json(vv),
        "one":value_json(ov),
        "two":value_json(tv),
        "delta_two_vs_one":tv.win_probability-ov.win_probability,
        "delta_one_vs_v6":ov.win_probability-vv.win_probability,
        "delta_two_vs_v6":tv.win_probability-vv.win_probability,
        "value_comparison":{
            "two_vs_one":"two_better" if tv.comparison_key()>ov.comparison_key() else "one_better" if tv.comparison_key()<ov.comparison_key() else "tie",
            "one_vs_v6":"one_better" if ov.comparison_key()>vv.comparison_key() else "v6_better" if ov.comparison_key()<vv.comparison_key() else "tie",
            "two_vs_v6":"two_better" if tv.comparison_key()>vv.comparison_key() else "v6_better" if tv.comparison_key()<vv.comparison_key() else "tie",
        },
        "world_comparison":{
            "two_vs_one":{
                "better":sum(p["two_vs_one"]==1 for p in pairs),
                "tie":sum(p["two_vs_one"]==0 for p in pairs),
                "worse":sum(p["two_vs_one"]==-1 for p in pairs),
            },
            "one_vs_v6":{
                "better":sum(p["one_vs_v6"]==1 for p in pairs),
                "tie":sum(p["one_vs_v6"]==0 for p in pairs),
                "worse":sum(p["one_vs_v6"]==-1 for p in pairs),
            },
            "two_vs_v6":{
                "better":sum(p["two_vs_v6"]==1 for p in pairs),
                "tie":sum(p["two_vs_v6"]==0 for p in pairs),
                "worse":sum(p["two_vs_v6"]==-1 for p in pairs),
            },
        },
        "terminal_reasons":{k:dict(v) for k,v in reasons.items()},
        "cache":{
            "one":{"hits":one_cache.stats.hits,"misses":one_cache.stats.misses},
            "two":{"hits":two_cache.stats.hits,"misses":two_cache.stats.misses},
        },
        "paired_worlds":pairs,
    }
    out=Path(f"phase5_q_targeted_paired4_hand{hand_id}.json")
    out.write_text(json.dumps(result,indent=2)+"\n")
    print("PAIRED4="+json.dumps({
        "hand_id":hand_id,
        "pwin":{"v6":vv.win_probability,"one":ov.win_probability,"two":tv.win_probability},
        "comparison":result["value_comparison"],
        "world_comparison":result["world_comparison"],
        "cache":result["cache"],
    },sort_keys=True))


if __name__=="__main__":
    main()
