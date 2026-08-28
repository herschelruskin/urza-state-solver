#!/usr/bin/env python3
"""Reduce four fixed outer-world factors into one exact Phase-5I bottom factor."""

from __future__ import annotations

from collections import Counter
import argparse
import json
from pathlib import Path

from phase3_value_engine import WinDistributionValue
from phase5_mulligan import unique_bottom_subsets
from phase5i_human_hand_eval import (
    BOTTOM_SHORTLIST,
    HORIZON,
    MC_ROOT_SEED,
    OUTER_CONFIRM,
    OUTER_SCREEN,
    Q_MC_ROOT_SEED,
    value_from_json,
    value_json,
)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--hand-id",type=int,required=True)
    p.add_argument("--bottom-index",type=int,required=True)
    p.add_argument("--input-dir",default=".")
    p.add_argument("--output",default=None)
    args=p.parse_args()

    fixture=json.loads(
        Path("benchmarks/human/human_mulligan_exact_hands.json").read_text(encoding="utf-8")
    )
    hand=next(x for x in fixture["hands"] if int(x["hand_id"])==int(args.hand_id))
    seven=tuple(hand["drawn_seven"])
    stage=int(hand["mulligan_count"])
    bottoms=unique_bottom_subsets(seven,stage)
    idx=int(args.bottom_index)
    bottom=bottoms[idx]

    rows=[]
    for sample_id in range(4):
        matches=list(
            Path(args.input_dir).glob(
                f"phase5i_human_bottom_world_h{int(args.hand_id)}_b{idx}_n{sample_id}.json"
            )
        )
        if len(matches)!=1:
            raise SystemExit(
                f"expected one world factor for sample {sample_id}, found {len(matches)}"
            )
        rows.append(json.loads(matches[0].read_text(encoding="utf-8")))

    assert [int(x["sample_id"]) for x in rows]==[0,1,2,3]
    assert all(tuple(x["bottom"])==tuple(bottom) for x in rows)
    screen=rows[0]["estimate"]
    confirms=[x["estimate"] for x in rows[1:]]
    assert all(tuple(x["bottom"])==tuple(screen["bottom"]) for x in confirms)
    assert all(x["kept_hand"]==screen["kept_hand"] for x in confirms)
    assert all(x["pregame_choice"]==screen["pregame_choice"] for x in confirms)

    values=[value_from_json(x["value"]) for x in confirms]
    mixed=WinDistributionValue.mixture(
        tuple((1.0/3.0,value) for value in values),
        horizon=HORIZON,
    )
    reasons=Counter()
    for estimate in confirms:
        reasons.update(dict(estimate["terminal_reasons"]))
    confirm={
        "bottom":list(screen["bottom"]),
        "kept_hand":list(screen["kept_hand"]),
        "pregame_choice":screen["pregame_choice"],
        "value":value_json(mixed),
        "rollouts":3,
        "terminal_reasons":[list(x) for x in sorted(reasons.items())],
    }

    payload={
        "kind":"phase5i-human-bottom-factor",
        "hand_id":int(args.hand_id),
        "stage":stage,
        "bottom_index":idx,
        "bottom":list(bottom),
        "screen":screen,
        "confirm":confirm,
        "q_cache":{
            "hits":sum(int(x["q_cache"]["hits"]) for x in rows),
            "misses":sum(int(x["q_cache"]["misses"]) for x in rows),
            "evictions":sum(int(x["q_cache"].get("evictions",0)) for x in rows),
            "world_factorized":True,
        },
        "budgets":{
            "outer_screen":OUTER_SCREEN,
            "outer_confirm":OUTER_CONFIRM,
            "bottom_shortlist":BOTTOM_SHORTLIST,
            "mc_root_seed":MC_ROOT_SEED,
            "q_mc_root_seed":Q_MC_ROOT_SEED,
        },
        "factorization":{
            "exact":True,
            "sample_ids":[0,1,2,3],
            "reason":"one seat-invariant pregame variant; screen0 and confirm1-3 preserve original outer coordinates",
        },
    }
    out=args.output or f"phase5i_human_bottom_h{int(args.hand_id)}_b{idx}.json"
    Path(out).write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print("PHASE5I_HUMAN_BOTTOM_WORLD_REDUCED="+json.dumps({
        "hand_id":int(args.hand_id),
        "bottom_index":idx,
        "screen_key":screen["value"]["comparison_key"],
        "confirm_key":confirm["value"]["comparison_key"],
    },sort_keys=True))


if __name__=="__main__":
    main()
