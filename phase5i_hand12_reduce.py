#!/usr/bin/env python3
"""Reduce hand-12 outer worlds into the exact original Phase-5I hand schema."""

from __future__ import annotations

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


HAND_ID=12
STAGE=1


def main():
    rows=[]
    for sample_id in range(3):
        matches=list(Path(".").rglob(f"phase5i_hand12_world_{sample_id}.json"))
        if len(matches)!=1:
            raise SystemExit(f"expected one hand12 world {sample_id}, found {len(matches)}")
        rows.append(json.loads(matches[0].read_text(encoding="utf-8")))

    assert [int(x["sample_id"]) for x in rows]==[0,1,2]
    assert all(int(x["hand_id"])==HAND_ID for x in rows)
    assert all(int(x["stage"])==STAGE for x in rows)
    estimates=[x["estimate"] for x in rows]
    assert all(tuple(x["bottom"])==() for x in estimates)

    values=[value_from_json(x["value"]) for x in estimates]
    mixed=WinDistributionValue.mixture(
        tuple((1.0/3.0,value) for value in values),
        horizon=HORIZON,
    )
    reasons=Counter()
    for estimate in estimates:
        reasons.update(dict(estimate["terminal_reasons"]))

    fixture=json.loads(
        Path("benchmarks/human/human_mulligan_exact_hands.json").read_text(encoding="utf-8")
    )
    row=next(x for x in fixture["hands"] if int(x["hand_id"])==HAND_ID)
    seven=list(row["drawn_seven"])
    best={
        "bottom":[],
        "kept_hand":seven,
        "pregame_choice":{"use_caverns":False,"exile_card":""},
        "value":value_json(mixed),
        "rollouts":3,
        "terminal_reasons":[list(x) for x in sorted(reasons.items())],
    }
    context={
        "label":"seat_invariant",
        "weight":1.0,
        "seat":1,
        "caverns_live":False,
        "stage":STAGE,
        "keep_size":keep_size_for_stage(STAGE),
        "solver":{
            "best":best,
            "legal_bottom_count":1,
            "confirmed_bottom_count":1,
            "shortlisted_bottoms":[[]],
        },
        "human_bottom_diagnostic":{
            "applicable":False,
            "bottom":[],
            "screen_rank":None,
            "confirmed_rank_among_shortlist_plus_human":None,
            "exact_match":None,
            "estimate":None,
            "regret":None,
        },
        "q_cache":{
            "hits":sum(int(x["q_cache"]["hits"]) for x in rows),
            "misses":sum(int(x["q_cache"]["misses"]) for x in rows),
        },
    }
    payload={
        "kind":"phase5i-human-hand-evaluation",
        "hand_id":HAND_ID,
        "human":{
            "decision":row.get("decision"),
            "mulligan_count":int(row["mulligan_count"]),
            "keep_size":int(row["keep_size"]),
            "rating_within_size":row.get("rating_within_size"),
            "drawn_seven":seven,
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
            "solver_best_value":value_json(mixed),
            "human_bottom_value":None,
        },
        "factorization":{
            "exact":True,
            "outer_world_sample_ids":[0,1,2],
            "reason":"stage-1 has one empty-bottom candidate; mixture equals original 3-rollout confirmation",
        },
    }
    out=Path("phase5i_human_hand_12.json")
    out.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print("PHASE5I_HAND12_REDUCED="+json.dumps({
        "pwin":mixed.win_probability,
        "key":list(mixed.comparison_key()),
        "terminal_reasons":best["terminal_reasons"],
    },sort_keys=True))


if __name__=="__main__":
    main()
