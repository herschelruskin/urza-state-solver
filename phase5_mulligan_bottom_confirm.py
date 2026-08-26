#!/usr/bin/env python3
"""Adaptive keep-six bottom confirmation on human-annotated benchmark sevens.

Protocol:
1. Screen all seven legal single-card bottoms with one hidden world using
   selective tutor-Q.
2. Shortlist the top three solver bottoms plus the human counterfactual bottom.
3. Confirm only that shortlist on three *fresh* common hidden worlds.
4. Run rollout-v6 on the identical confirmation candidates/world coordinates.

Human annotations are never used to alter values or action choice; the human bottom
is included only as an externally nominated candidate so its confirmed rank is
reported even if it missed the one-world solver shortlist.
"""

from __future__ import annotations

import json
from pathlib import Path

from phase5_mulligan import OpeningKeepEvaluator
from phase5_rollout_policy_v6 import (
    DeterministicRolloutPolicyV6,
    PHASE5_ROLLOUT_POLICY_V6,
)
from phase5_selective_tutor_q import make_selective_tutor_q_episode_runner

HAND_IDS=(22,23,32)
STAGE=2
SCREEN_OUTER_ROLLOUTS=1
CONFIRM_OUTER_ROLLOUTS=3
MC_ROOT_SEED=20260826


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


def human_bottom(row):
    cf=row.get("counterfactual_keep_at_m2") or {}
    return tuple(sorted(
        cf.get("bottom") or cf.get("bottom_if_keep") or ()
    ))


def estimate_json(estimate):
    return {
        "bottom":list(estimate.bottom),
        "kept_hand":list(estimate.kept_hand),
        "win_probability":estimate.value.win_probability,
        "exact_win":list(estimate.value.exact_win),
        "no_win":estimate.value.no_win,
        "win_families":[list(x) for x in estimate.value.win_families],
        "wilson95":list(estimate.win_probability_wilson95),
        "terminal_reasons":[list(x) for x in estimate.terminal_reason_counts],
    }


def rank_of(evaluation,bottom):
    for rank,estimate in enumerate(evaluation.estimates,1):
        if estimate.bottom==bottom:
            return rank
    return None


def main():
    deck=load_deck()
    fixture=json.loads(
        Path("benchmarks/human/human_mulligan_exact_hands.json")
        .read_text(encoding="utf-8")
    )
    by_id={int(row["hand_id"]):row for row in fixture["hands"]}
    leaf=DeterministicRolloutPolicyV6(policy_id=PHASE5_ROLLOUT_POLICY_V6)

    q_screen=OpeningKeepEvaluator(
        deck,
        rollout_count=SCREEN_OUTER_ROLLOUTS,
        mc_root_seed=MC_ROOT_SEED,
        horizon=6,
        continuation_policy=leaf,
        max_episode_steps=512,
        strict_terminal_reasons=True,
        episode_runner=make_selective_tutor_q_episode_runner(
            mc_root_seed=MC_ROOT_SEED,
            screen_rollouts=1,
            confirm_rollouts=1,
            shortlist_size=3,
        ),
    )
    q_confirm=OpeningKeepEvaluator(
        deck,
        rollout_count=CONFIRM_OUTER_ROLLOUTS,
        mc_root_seed=MC_ROOT_SEED,
        horizon=6,
        continuation_policy=leaf,
        max_episode_steps=512,
        strict_terminal_reasons=True,
        episode_runner=make_selective_tutor_q_episode_runner(
            mc_root_seed=MC_ROOT_SEED,
            screen_rollouts=1,
            confirm_rollouts=2,
            shortlist_size=3,
        ),
    )
    v6_confirm=OpeningKeepEvaluator(
        deck,
        rollout_count=CONFIRM_OUTER_ROLLOUTS,
        mc_root_seed=MC_ROOT_SEED,
        horizon=6,
        continuation_policy=leaf,
        max_episode_steps=512,
        strict_terminal_reasons=True,
    )

    rows=[]
    for hand_id in HAND_IDS:
        row=by_id[hand_id]
        seven=tuple(row["drawn_seven"])
        human=human_bottom(row)
        assert len(human)==1

        screen=q_screen.evaluate(seven,stage=STAGE,sample_start=0)
        shortlist={estimate.bottom for estimate in screen.estimates[:3]}
        shortlist.add(human)
        candidates=tuple(sorted(shortlist))

        q=q_confirm.evaluate(
            seven,
            stage=STAGE,
            candidate_bottoms=candidates,
            sample_start=1,
        )
        v6=v6_confirm.evaluate(
            seven,
            stage=STAGE,
            candidate_bottoms=candidates,
            sample_start=1,
        )
        cf=row.get("counterfactual_keep_at_m2") or {}
        rows.append({
            "hand_id":hand_id,
            "seven":list(seven),
            "human":{
                "decision":cf.get("decision"),
                "lean":cf.get("lean"),
                "bottom":list(human),
                "note":cf.get("note",""),
            },
            "screen":{
                "best":list(screen.best.bottom),
                "top3":[estimate_json(x) for x in screen.estimates[:3]],
                "human_rank":rank_of(screen,human),
            },
            "confirmed_candidates":[list(x) for x in candidates],
            "q":{
                "best":estimate_json(q.best),
                "human_rank":rank_of(q,human),
                "all":[estimate_json(x) for x in q.estimates],
            },
            "v6":{
                "best":estimate_json(v6.best),
                "human_rank":rank_of(v6,human),
                "all":[estimate_json(x) for x in v6.estimates],
            },
        })

    payload={
        "kind":"phase5-adaptive-keep6-bottom-confirmation",
        "stage":STAGE,
        "screen_outer_rollouts":SCREEN_OUTER_ROLLOUTS,
        "confirmation_outer_rollouts":CONFIRM_OUTER_ROLLOUTS,
        "confirmation_sample_start":1,
        "q_screen_inner_rollouts":1,
        "q_confirm_inner_rollouts":2,
        "mc_root_seed":MC_ROOT_SEED,
        "rows":rows,
    }
    Path("phase5_mulligan_bottom_confirm.json").write_text(
        json.dumps(payload,indent=2)+"\n",encoding="utf-8"
    )

    print(json.dumps({
        row["hand_id"]:{
            "human":row["human"],
            "screen_best":row["screen"]["best"],
            "q_confirm_best":row["q"]["best"]["bottom"],
            "q_confirm_pwin":row["q"]["best"]["win_probability"],
            "q_human_rank":row["q"]["human_rank"],
            "v6_confirm_best":row["v6"]["best"]["bottom"],
            "v6_confirm_pwin":row["v6"]["best"]["win_probability"],
            "v6_human_rank":row["v6"]["human_rank"],
        }
        for row in rows
    },indent=2))


if __name__=="__main__":
    main()
