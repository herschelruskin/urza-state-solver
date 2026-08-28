#!/usr/bin/env python3
"""Reduce exact per-bottom Phase-5I factors into the original human-hand schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from phase5_mulligan import keep_size_for_stage, unique_bottom_subsets
from phase5i_human_hand_eval import (
    BOTTOM_SHORTLIST,
    MC_ROOT_SEED,
    OUTER_CONFIRM,
    OUTER_SCREEN,
    Q_MC_ROOT_SEED,
    diagnostic_rank,
    objective_gap,
    value_from_json,
    value_json,
)


def key(estimate):
    return tuple(float(x) for x in estimate["value"]["comparison_key"])


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--hand-id",type=int,required=True)
    p.add_argument("--input-dir",default=".")
    p.add_argument("--output",default=None)
    args=p.parse_args()

    fixture=json.loads(
        Path("benchmarks/human/human_mulligan_exact_hands.json").read_text(encoding="utf-8")
    )
    row=next(x for x in fixture["hands"] if int(x["hand_id"])==int(args.hand_id))
    seven=tuple(row["drawn_seven"])
    stage=int(row["mulligan_count"])
    legal=unique_bottom_subsets(seven,stage)

    factors=[]
    for path in sorted(Path(args.input_dir).glob(f"phase5i_human_bottom_h{int(args.hand_id)}_b*.json")):
        factors.append(json.loads(path.read_text(encoding="utf-8")))
    if len(factors)!=len(legal):
        raise SystemExit(
            f"expected {len(legal)} bottom factors for hand {args.hand_id}, found {len(factors)}"
        )

    by_index={int(x["bottom_index"]):x for x in factors}
    if sorted(by_index)!=list(range(len(legal))):
        raise SystemExit(f"bottom factor indices incomplete: {sorted(by_index)}")
    for idx,bottom in enumerate(legal):
        if tuple(by_index[idx]["bottom"])!=tuple(bottom):
            raise SystemExit(
                f"bottom factor identity mismatch at {idx}: "
                f"{by_index[idx]['bottom']!r} != {bottom!r}"
            )

    # Reconstruct the exact monolithic screen ranking and tie-preserving cutoff.
    screen_rows=[x["screen"] for x in factors]
    screen_ranked=sorted(
        screen_rows,
        key=lambda est:(key(est),repr(tuple(est["bottom"]))),
        reverse=True,
    )
    cutoff_index=min(BOTTOM_SHORTLIST,len(screen_ranked))-1
    cutoff_key=key(screen_ranked[cutoff_index])
    shortlist=tuple(
        tuple(est["bottom"])
        for est in screen_ranked
        if key(est)>=cutoff_key
    )
    shortlist_set=set(shortlist)

    confirm_rows=[
        x["confirm"] for x in factors
        if tuple(x["bottom"]) in shortlist_set
    ]
    confirm_ranked=sorted(
        confirm_rows,
        key=lambda est:(key(est),repr(tuple(est["bottom"]))),
        reverse=True,
    )
    best=confirm_ranked[0]

    human_bottom=tuple(sorted(row.get("cards_bottomed") or ()))
    has_human_bottom=(
        str(row.get("decision"))=="Keep"
        and stage>=2
        and len(human_bottom)>0
    )
    human_screen_rank=None
    human_confirmed_rank=None
    bottom_exact=None
    human_estimate=None
    regret=None
    if has_human_bottom:
        for rank,est in enumerate(screen_ranked,1):
            if tuple(est["bottom"])==human_bottom:
                human_screen_rank=rank
                break
        human_factor=next(
            x for x in factors if tuple(x["bottom"])==human_bottom
        )
        human_estimate=human_factor["confirm"]
        diagnostic_rows=list(confirm_ranked)
        if human_bottom not in shortlist_set:
            diagnostic_rows.append(human_estimate)
        ranked_diag=sorted(
            diagnostic_rows,
            key=lambda est:(key(est),repr(tuple(est["bottom"]))),
            reverse=True,
        )
        for rank,est in enumerate(ranked_diag,1):
            if tuple(est["bottom"])==human_bottom:
                human_confirmed_rank=rank
                break
        bottom_exact=(tuple(best["bottom"])==human_bottom)
        best_value=value_from_json(best["value"])
        human_value=value_from_json(human_estimate["value"])
        regret={
            "delta_pwin_best_minus_human":float(
                best_value.win_probability-human_value.win_probability
            ),
            "objective_key_gap_best_minus_human":objective_gap(
                type("E",(),{"value":best_value})(),
                type("E",(),{"value":human_value})(),
            ),
        }

    context={
        "label":"seat_invariant",
        "weight":1.0,
        "seat":1,
        "caverns_live":False,
        "stage":stage,
        "keep_size":keep_size_for_stage(stage),
        "solver":{
            "best":best,
            "legal_bottom_count":len(legal),
            "confirmed_bottom_count":len(shortlist),
            "shortlisted_bottoms":[list(x) for x in sorted(shortlist)],
        },
        "human_bottom_diagnostic":{
            "applicable":has_human_bottom,
            "bottom":list(human_bottom),
            "screen_rank":human_screen_rank,
            "confirmed_rank_among_shortlist_plus_human":human_confirmed_rank,
            "exact_match":bottom_exact,
            "estimate":human_estimate,
            "regret":regret,
        },
        "q_cache":{
            "hits":sum(int(x["q_cache"]["hits"]) for x in factors),
            "misses":sum(int(x["q_cache"]["misses"]) for x in factors),
            "evictions":sum(int(x["q_cache"].get("evictions",0)) for x in factors),
            "factorized":True,
        },
    }
    best_value=value_from_json(best["value"])
    human_value=(
        None if human_estimate is None
        else value_from_json(human_estimate["value"])
    )
    payload={
        "kind":"phase5i-human-hand-evaluation",
        "hand_id":int(row["hand_id"]),
        "human":{
            "decision":row.get("decision"),
            "mulligan_count":stage,
            "keep_size":int(row["keep_size"]),
            "rating_within_size":row.get("rating_within_size"),
            "drawn_seven":list(row["drawn_seven"]),
            "cards_bottomed":list(row.get("cards_bottomed") or []),
        },
        "budgets":{
            "outer_screen":OUTER_SCREEN,
            "outer_confirm":OUTER_CONFIRM,
            "bottom_shortlist":BOTTOM_SHORTLIST,
            "mc_root_seed":MC_ROOT_SEED,
            "q_mc_root_seed":Q_MC_ROOT_SEED,
        },
        "seat_missing_in_human_source":True,
        "contexts":[context],
        "ex_ante_after_seat_conditioned_optimization":{
            "solver_best_value":value_json(best_value),
            "human_bottom_value":None if human_value is None else value_json(human_value),
        },
        "factorization":{
            "exact":True,
            "legal_bottoms":len(legal),
            "reason":"per-bottom screen/confirmation use identical outer-world coordinates; reducer reproduces original tie-preserving shortlist",
        },
    }
    output=args.output or f"phase5i_human_hand_{int(row['hand_id']):02d}.json"
    Path(output).write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print("PHASE5I_HUMAN_BOTTOM_REDUCED="+json.dumps({
        "hand_id":int(row["hand_id"]),
        "best_bottom":best["bottom"],
        "best_key":best["value"]["comparison_key"],
        "shortlist_count":len(shortlist),
        "human_bottom_rank":human_confirmed_rank,
        "bottom_exact":bottom_exact,
    },sort_keys=True))


if __name__=="__main__":
    main()
