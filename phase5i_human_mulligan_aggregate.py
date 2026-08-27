#!/usr/bin/env python3
"""Aggregate held-out Phase-5I human mulligan hand results."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path


def main():
    files=sorted(Path(".").rglob("phase5i_human_hand_*.json"))
    if not files:
        raise SystemExit("no phase5i_human_hand_*.json files found")

    rows=[json.loads(path.read_text(encoding="utf-8")) for path in files]
    by_id={}
    for row in rows:
        hand_id=int(row["hand_id"])
        if hand_id in by_id:
            raise ValueError(f"duplicate hand result {hand_id}")
        by_id[hand_id]=row
    rows=[by_id[k] for k in sorted(by_id)]

    decisions=Counter()
    stage_rows=defaultdict(list)
    kept=[]
    kept_with_bottom=[]
    for row in rows:
        human=row["human"]["decision"]
        solver=row["solver"]["decision"]
        decisions[(human,solver)]+=1
        stage_rows[int(row["stage"])].append(row)
        if human=="Keep":
            kept.append(row)
            if row["human"]["bottom"]:
                kept_with_bottom.append(row)

    def agreement(group):
        return (
            sum(bool(r["comparison"]["decision_match"]) for r in group)/len(group)
            if group else None
        )

    bottom_exact=[
        r for r in kept_with_bottom
        if r["comparison"]["bottom_exact_match"] is not None
    ]
    shortlisted=[
        r for r in kept_with_bottom
        if r["comparison"]["human_bottom_shortlisted"] is not None
    ]
    deltas=[
        float(r["comparison"]["delta_pwin_best_minus_human"])
        for r in kept
        if r["comparison"]["delta_pwin_best_minus_human"] is not None
    ]

    stage_summary=[]
    for stage in sorted(stage_rows):
        group=stage_rows[stage]
        stage_summary.append({
            "stage":stage,
            "n":len(group),
            "decision_agreement":agreement(group),
            "human_keep":sum(r["human"]["decision"]=="Keep" for r in group),
            "human_mulligan":sum(r["human"]["decision"]=="Mulligan" for r in group),
            "solver_keep":sum(r["solver"]["decision"]=="Keep" for r in group),
            "solver_mulligan":sum(r["solver"]["decision"]=="Mulligan" for r in group),
            "disagreement_hand_ids":[
                r["hand_id"] for r in group
                if not r["comparison"]["decision_match"]
            ],
        })

    disagreement_rows=[
        {
            "hand_id":r["hand_id"],
            "stage":r["stage"],
            "human":r["human"]["decision"],
            "solver":r["solver"]["decision"],
            "best_bottom":r["solver"]["best"]["bottom"],
            "human_bottom":r["human"]["bottom"],
            "best_pwin":r["solver"]["best"]["value"]["win_probability"],
            "continuation_pwin":(
                None
                if r["solver"]["continuation_value"] is None
                else r["solver"]["continuation_value"]["win_probability"]
            ),
            "rating_within_size":r["human"].get("rating_within_size"),
        }
        for r in rows if not r["comparison"]["decision_match"]
    ]

    bottom_rows=[
        {
            "hand_id":r["hand_id"],
            "stage":r["stage"],
            "solver_bottom":r["solver"]["best"]["bottom"],
            "human_bottom":r["human"]["bottom"],
            "exact_match":r["comparison"]["bottom_exact_match"],
            "human_bottom_shortlisted":r["comparison"]["human_bottom_shortlisted"],
            "human_bottom_confirmation_rank":r["comparison"]["human_bottom_confirmation_rank"],
            "delta_pwin_best_minus_human":r["comparison"]["delta_pwin_best_minus_human"],
            "delta_cumulative_best_minus_human":r["comparison"]["delta_cumulative_best_minus_human"],
        }
        for r in kept_with_bottom
    ]

    payload={
        "kind":"phase5i-heldout-human-mulligan-aggregate",
        "n_hands":len(rows),
        "hand_ids":[r["hand_id"] for r in rows],
        "annotations_used_for_solver_selection":False,
        "decision":{
            "agreement_count":sum(r["comparison"]["decision_match"] for r in rows),
            "agreement_rate":agreement(rows),
            "confusion":{
                f"human_{human.lower()}__solver_{solver.lower()}":count
                for (human,solver),count in sorted(decisions.items())
            },
            "by_stage":stage_summary,
            "disagreements":disagreement_rows,
        },
        "bottom":{
            "human_kept_hands":len(kept),
            "human_kept_hands_with_bottom":len(kept_with_bottom),
            "exact_match_count":sum(bool(r["comparison"]["bottom_exact_match"]) for r in bottom_exact),
            "exact_match_rate":(
                sum(bool(r["comparison"]["bottom_exact_match"]) for r in bottom_exact)/len(bottom_exact)
                if bottom_exact else None
            ),
            "human_bottom_shortlisted_count":sum(
                bool(r["comparison"]["human_bottom_shortlisted"]) for r in shortlisted
            ),
            "human_bottom_shortlisted_rate":(
                sum(bool(r["comparison"]["human_bottom_shortlisted"]) for r in shortlisted)/len(shortlisted)
                if shortlisted else None
            ),
            "mean_delta_pwin_best_minus_human":(
                sum(deltas)/len(deltas) if deltas else None
            ),
            "rows":bottom_rows,
        },
        "per_hand":rows,
    }
    Path("phase5i_human_mulligan_aggregate.json").write_text(
        json.dumps(payload,indent=2)+"\n",encoding="utf-8"
    )
    print("PHASE5I_HUMAN_AGG="+json.dumps({
        "n":payload["n_hands"],
        "decision_agreement":payload["decision"]["agreement_rate"],
        "decision_matches":payload["decision"]["agreement_count"],
        "bottom_exact_match_rate":payload["bottom"]["exact_match_rate"],
        "bottom_shortlist_rate":payload["bottom"]["human_bottom_shortlisted_rate"],
        "disagreement_ids":[x["hand_id"] for x in disagreement_rows],
    },sort_keys=True))


if __name__=="__main__":
    main()
