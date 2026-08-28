#!/usr/bin/env python3
"""Reduce exact bottom factors into the original dead/stage3/sample1 K_s artifact."""

from __future__ import annotations

import json
from pathlib import Path

from phase5i_human_hand_eval import value_from_json
from phase5i_stage_sample_eval import (
    BOTTOM_SHORTLIST,
    OUTER_CONFIRM,
    OUTER_SCREEN,
)


def _rank(rows,key):
    return tuple(sorted(
        rows,
        key=lambda row:(value_from_json(row[key]["value"]).comparison_key(),repr(tuple(row["bottom"]))),
        reverse=True,
    ))


def main():
    rows=[]
    for path in Path(".").rglob("phase5i_dead_s3n1_bottom_*.json"):
        rows.append(json.loads(path.read_text(encoding="utf-8")))
    if not rows:
        raise SystemExit("no dead s3n1 bottom factors")
    rows=sorted(rows,key=lambda r:int(r["bottom_index"]))
    legal_count=int(rows[0]["legal_bottom_count"])
    if len(rows)!=legal_count:
        raise SystemExit(f"expected {legal_count} factors, found {len(rows)}")
    assert [int(r["bottom_index"]) for r in rows]==list(range(legal_count))

    screen=_rank(rows,"screen")
    cutoff_index=min(BOTTOM_SHORTLIST,len(screen))-1
    cutoff=value_from_json(screen[cutoff_index]["screen"]["value"]).comparison_key()
    shortlist=[
        row for row in screen
        if value_from_json(row["screen"]["value"]).comparison_key()>=cutoff
    ]
    confirm=_rank(shortlist,"confirm")
    best_row=confirm[0]
    best=best_row["confirm"]
    payload={
        "kind":"phase5i-stage-keep-sample",
        "context":"dead",
        "representative_seat":1,
        "stage":3,
        "keep_size":5,
        "sample_id":1,
        "mc_root_seed":int(rows[0]["mc_root_seed"]),
        "q_mc_root_seed":int(rows[0]["q_mc_root_seed"]),
        "seven":rows[0]["seven"],
        "best_bottom":best["bottom"],
        "best_pregame_choice":best["pregame_choice"],
        "keep_value":best["value"],
        "terminal_reasons":best["terminal_reasons"],
        "legal_bottom_count":legal_count,
        "confirmed_bottom_count":len(shortlist),
        "q_cache":{
            "hits":sum(int(r["q_cache"]["hits"]) for r in rows),
            "misses":sum(int(r["q_cache"]["misses"]) for r in rows),
        },
        "budgets":{
            "outer_screen":OUTER_SCREEN,
            "outer_confirm":OUTER_CONFIRM,
            "bottom_shortlist":BOTTOM_SHORTLIST,
        },
        "factorization":{
            "exact":True,
            "method":"per-bottom screen0 + confirm1to2; original shortlist reconstructed",
        },
    }
    Path("phase5i_stage_sample_dead_s3_n1.json").write_text(
        json.dumps(payload,indent=2)+"\n",encoding="utf-8"
    )
    print("PHASE5I_DEAD_S3N1_REDUCED="+json.dumps({
        "best_bottom":best["bottom"],
        "pwin":best["value"]["win_probability"],
        "shortlist_size":len(shortlist),
    },sort_keys=True))


if __name__=="__main__":
    main()
