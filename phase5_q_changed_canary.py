#!/usr/bin/env python3
"""Single-world changed-hand canary for independent Q confirmation."""

import argparse
import json
from pathlib import Path

from information_state_propagation import validate_information_against_state
from non_oracle_episode import run_deterministic_episode
from phase4_hidden_world import materialize_hidden_world
from phase5_monte_carlo import Phase5DecisionCache
from phase5_mulligan import _opening_world, opening_runtime
from phase5_rollout_policy_v6 import DeterministicRolloutPolicyV6, PHASE5_ROLLOUT_POLICY_V6
from phase5_selective_tutor_q import SelectiveTutorQController, run_selective_tutor_q_episode

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


def qrun(runtime,leaf,contingent):
    cache=Phase5DecisionCache()
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
    result=run_selective_tutor_q_episode(
        runtime,controller=controller,horizon=HORIZON,max_steps=512
    )
    return result,cache


def decisions(result):
    return [{
        "sequence":x.sequence,
        "turn":x.turn,
        "decision_id":x.decision_id,
        "v6_action":x.v6_action,
        "chosen_action":x.chosen_action,
        "overridden":x.overridden,
        "v6_value_key":list(x.v6_value_key),
        "chosen_value_key":list(x.chosen_value_key),
    } for x in result.q_decisions]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--hand-id",type=int,required=True)
    args=parser.parse_args()
    hand_id=int(args.hand_id)

    deck=load_deck()
    fixture=json.loads(Path("benchmarks/human/human_mulligan_exact_hands.json").read_text())
    row=next(x for x in fixture["hands"] if int(x["hand_id"])==hand_id)
    if not row.get("primary_benchmark_usable",True):
        raise SystemExit(f"hand {hand_id} is not an exact-state benchmark")

    seven=tuple(row["drawn_seven"])
    bottom=tuple(row["cards_bottomed"])
    root=opening_runtime(deck,seven,bottom)
    world=_opening_world(
        deck=deck,seven=seven,bottom=bottom,
        mc_root_seed=OUTER_SEED,sample_id=0,
    )
    leaf=DeterministicRolloutPolicyV6(policy_id=PHASE5_ROLLOUT_POLICY_V6)

    vr=materialize_hidden_world(root,world)
    validate_information_against_state(vr.information,vr.true_state)
    v6=run_deterministic_episode(vr,horizon=HORIZON,max_steps=512,policy=leaf)

    one,one_cache=qrun(materialize_hidden_world(root,world),leaf,False)
    two,two_cache=qrun(materialize_hidden_world(root,world),leaf,True)

    payload={
        "hand_id":hand_id,
        "v6":{"win_turn":v6.win_turn,"family":v6.win_family,"reason":v6.terminal_reason},
        "one":{"win_turn":one.win_turn,"family":one.win_family,"reason":one.episode.terminal_reason,"decisions":decisions(one)},
        "two":{"win_turn":two.win_turn,"family":two.win_family,"reason":two.episode.terminal_reason,"decisions":decisions(two)},
        "cache":{"one":vars(one_cache.stats),"two":vars(two_cache.stats)},
    }
    out=Path(f"phase5_q_changed_canary_hand{hand_id}.json")
    out.write_text(json.dumps(payload,indent=2)+"\n")
    print("CHANGED_CANARY="+json.dumps(payload,sort_keys=True))


if __name__=="__main__":
    main()
