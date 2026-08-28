#!/usr/bin/env python3
"""Reduce exact per-bottom factors into Phase-5I human-hand artifacts."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from phase3_value_engine import WinDistributionValue
from phase5_mulligan import keep_size_for_stage
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


def _rank(rows,key):
    return tuple(sorted(
        rows,
        key=lambda row:(value_from_json(row[key]["value"]).comparison_key(),repr(tuple(row["bottom"]))),
        reverse=True,
    ))


def _gap(best,human):
    a=value_from_json(best["value"]).comparison_key()
    b=value_from_json(human["value"]).comparison_key()
    return [float(x-y) for x,y in zip(a,b)]


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--hand-id",type=int,required=True,choices=(14,25,26))
    p.add_argument("--input-dir",default=".")
    args=p.parse_args()
    hand_id=int(args.hand_id)

    rows=[]
    for path in Path(args.input_dir).rglob(f"phase5i_expensive_hand_{hand_id}_bottom_*.json"):
        rows.append(json.loads(path.read_text(encoding="utf-8")))
    if not rows:
        raise SystemExit(f"no bottom factors for hand {hand_id}")
    rows=sorted(rows,key=lambda r:int(r["bottom_index"]))
    legal_count=int(rows[0]["legal_bottom_count"])
    if len(rows)!=legal_count:
        raise SystemExit(f"hand {hand_id}: expected {legal_count} factors, found {len(rows)}")
    assert [int(r["bottom_index"]) for r in rows]==list(range(legal_count))
    assert all(int(r["hand_id"])==hand_id for r in rows)

    screen_ranked=_rank(rows,"screen")
    cutoff_index=min(BOTTOM_SHORTLIST,len(screen_ranked))-1
    cutoff=value_from_json(screen_ranked[cutoff_index]["screen"]["value"]).comparison_key()
    shortlist=[
        row for row in screen_ranked
        if value_from_json(row["screen"]["value"]).comparison_key()>=cutoff
    ]
    shortlisted_bottoms={tuple(row["bottom"]) for row in shortlist}
    confirm_ranked=_rank(shortlist,"confirm")
    best_row=confirm_ranked[0]
    best=best_row["confirm"]

    fixture=json.loads(
        Path("benchmarks/human/human_mulligan_exact_hands.json").read_text(encoding="utf-8")
    )
    human=next(x for x in fixture["hands"] if int(x["hand_id"])==hand_id)
    seven=list(human["drawn_seven"])
    stage=int(human["mulligan_count"])
    human_bottom=tuple(sorted(human.get("cards_bottomed") or ()))
    human_row=next((r for r in rows if tuple(r["bottom"])==human_bottom),None)
    has_human_bottom=(str(human.get("decision"))=="Keep" and stage>=2 and bool(human_bottom))

    human_diag={
        "applicable":has_human_bottom,
        "bottom":list(human_bottom),
        "screen_rank":None,
        "confirmed_rank_among_shortlist_plus_human":None,
        "exact_match":None,
        "estimate":None,
        "regret":None,
    }
    if has_human_bottom:
        if human_row is None:
            raise SystemExit(f"human bottom not legal/found for hand {hand_id}: {human_bottom}")
        human_diag["screen_rank"]=next(
            i for i,row in enumerate(screen_ranked,1) if tuple(row["bottom"])==human_bottom
        )
        diagnostic=list(shortlist)
        if tuple(human_row["bottom"]) not in shortlisted_bottoms:
            diagnostic.append(human_row)
        diagnostic_ranked=_rank(diagnostic,"confirm")
        human_diag["confirmed_rank_among_shortlist_plus_human"]=next(
            i for i,row in enumerate(diagnostic_ranked,1) if tuple(row["bottom"])==human_bottom
        )
        human_diag["exact_match"]=(tuple(best_row["bottom"])==human_bottom)
        human_diag["estimate"]=human_row["confirm"]
        human_diag["regret"]={
            "delta_pwin_best_minus_human":float(
                value_from_json(best["value"]).win_probability
                - value_from_json(human_row["confirm"]["value"]).win_probability
            ),
            "objective_key_gap_best_minus_human":_gap(best,human_row["confirm"]),
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
            "legal_bottom_count":legal_count,
            "confirmed_bottom_count":len(shortlist),
            "shortlisted_bottoms":[list(x) for x in sorted(shortlisted_bottoms)],
        },
        "human_bottom_diagnostic":human_diag,
        "q_cache":{
            "hits":sum(int(r["q_cache"]["hits"]) for r in rows),
            "misses":sum(int(r["q_cache"]["misses"]) for r in rows),
        },
    }
    best_value=value_from_json(best["value"])
    human_value=(
        None if human_diag["estimate"] is None
        else value_from_json(human_diag["estimate"]["value"])
    )
    payload={
        "kind":"phase5i-human-hand-evaluation",
        "hand_id":hand_id,
        "human":{
            "decision":human.get("decision"),
            "mulligan_count":stage,
            "keep_size":int(human["keep_size"]),
            "rating_within_size":human.get("rating_within_size"),
            "drawn_seven":seven,
            "cards_bottomed":list(human.get("cards_bottomed") or []),
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
            "method":"per-bottom screen0 + confirm1to3; original shortlist reconstructed",
            "all_legal_bottoms_confirmed_for_diagnostics":True,
        },
    }
    out=Path(f"phase5i_human_hand_{hand_id:02d}.json")
    out.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print("PHASE5I_EXPENSIVE_HAND_REDUCED="+json.dumps({
        "hand_id":hand_id,
        "best_bottom":best["bottom"],
        "pwin":best_value.win_probability,
        "shortlist_size":len(shortlist),
        "human_bottom_rank":human_diag["confirmed_rank_among_shortlist_plus_human"],
    },sort_keys=True))


if __name__=="__main__":
    main()
