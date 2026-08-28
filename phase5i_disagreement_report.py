#!/usr/bin/env python3
"""Classify Phase-5I human benchmark disagreements by meaning/severity.

Exact-match rates are intentionally not treated as sufficient.  For keep/mull
calls we distinguish stable, seat-dependent, and continuation-threshold-unstable
states.  For London bottoms we distinguish exact matches from timing-only
differences (same sampled T6 win probability) and differences that actually move
sampled win probability.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


EPS=1e-12


def bottom_class(row):
    bottom=row.get("bottom")
    if bottom is None:
        return "not_applicable"
    exact=float(bottom.get("ex_ante_exact_match_probability") or 0.0)
    regret=bottom.get("ex_ante_delta_pwin_regret")
    if exact>=1.0-EPS:
        return "exact_match"
    if regret is None:
        return "different_unscored"
    regret=float(regret)
    if abs(regret)<=EPS:
        return "different_timing_or_family_only"
    if regret>0:
        return "solver_sampled_pwin_advantage"
    return "human_sampled_pwin_advantage"


def decision_class(row):
    human=str(row["human_decision"])
    contexts=row["seat_contexts"]
    dead=contexts["dead"]
    live=contexts["live"]
    dead_decision=str(dead["solver_decision"])
    live_decision=str(live["solver_decision"])
    dead_stable=dead.get("replicate_stable")
    live_stable=live.get("replicate_stable")

    if dead_stable is False or live_stable is False:
        return "threshold_unstable"
    if dead_decision!=live_decision:
        dead_match=(dead_decision==human)
        live_match=(live_decision==human)
        if dead_match and not live_match:
            return "seat_dependent_human_matches_seat1_only"
        if live_match and not dead_match:
            return "seat_dependent_human_matches_live_seats_only"
        return "seat_dependent_neither_or_both"
    if dead_decision==human:
        return "stable_agreement"
    return "stable_disagreement"


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--summary",default="phase5i_human_benchmark_summary.json")
    p.add_argument("--output",default="phase5i_disagreement_report.json")
    args=p.parse_args()

    summary=json.loads(Path(args.summary).read_text(encoding="utf-8"))
    decision_counts=Counter()
    bottom_counts=Counter()
    rows=[]

    for row in summary["rows"]:
        dclass=decision_class(row)
        bclass=bottom_class(row)
        decision_counts[dclass]+=1
        bottom_counts[bclass]+=1
        rows.append({
            "hand_id":int(row["hand_id"]),
            "stage":int(row["stage"]),
            "keep_size":int(row["keep_size"]),
            "human_decision":row["human_decision"],
            "decision_class":dclass,
            "ex_ante_decision_agreement_probability":row["ex_ante_decision_agreement_probability"],
            "bottom_class":bclass,
            "bottom_exact_match_probability":(
                None if row.get("bottom") is None
                else row["bottom"].get("ex_ante_exact_match_probability")
            ),
            "bottom_pwin_regret":(
                None if row.get("bottom") is None
                else row["bottom"].get("ex_ante_delta_pwin_regret")
            ),
            "bottom_confirmed_rank":(
                None if row.get("bottom") is None
                else row["bottom"].get("ex_ante_confirmed_rank")
            ),
            "dead_decision":row["seat_contexts"]["dead"]["solver_decision"],
            "live_decision":row["seat_contexts"]["live"]["solver_decision"],
            "dead_replicate_decisions":row["seat_contexts"]["dead"].get("replicate_decisions",[]),
            "live_replicate_decisions":row["seat_contexts"]["live"].get("replicate_decisions",[]),
            "dead_bootstrap_keep_probability":row["seat_contexts"]["dead"].get("bootstrap_keep_probability"),
            "live_bootstrap_keep_probability":row["seat_contexts"]["live"].get("bootstrap_keep_probability"),
            "dead_bootstrap_decision_confidence":row["seat_contexts"]["dead"].get("bootstrap_decision_confidence"),
            "live_bootstrap_decision_confidence":row["seat_contexts"]["live"].get("bootstrap_decision_confidence"),
            "dead_joint_bootstrap_keep_probability":row["seat_contexts"]["dead"].get("joint_bootstrap_keep_probability"),
            "live_joint_bootstrap_keep_probability":row["seat_contexts"]["live"].get("joint_bootstrap_keep_probability"),
            "dead_joint_bootstrap_decision_confidence":row["seat_contexts"]["dead"].get("joint_bootstrap_decision_confidence"),
            "live_joint_bootstrap_decision_confidence":row["seat_contexts"]["live"].get("joint_bootstrap_decision_confidence"),
            "ex_ante_joint_bootstrap_human_agreement_probability":sum(
                float(row["seat_contexts"][context]["weight"])
                * float(row["seat_contexts"][context].get("joint_bootstrap_human_agreement_probability") or 0.0)
                for context in ("dead","live")
            ),
            "ex_ante_bootstrap_human_agreement_probability":sum(
                float(row["seat_contexts"][context]["weight"])
                * float(row["seat_contexts"][context].get("bootstrap_human_agreement_probability") or 0.0)
                for context in ("dead","live")
            ),
        })

    material_bottom=[
        row for row in rows
        if row["bottom_class"] in {
            "solver_sampled_pwin_advantage",
            "human_sampled_pwin_advantage",
        }
    ]
    stable_decision_disagreements=[
        row for row in rows if row["decision_class"]=="stable_disagreement"
    ]
    unstable=[
        row for row in rows if row["decision_class"]=="threshold_unstable"
    ]
    seat_dependent=[
        row for row in rows if row["decision_class"].startswith("seat_dependent_")
    ]

    payload={
        "kind":"phase5i-disagreement-report",
        "human_hand_count":len(rows),
        "decision_class_counts":dict(sorted(decision_counts.items())),
        "bottom_class_counts":dict(sorted(bottom_counts.items())),
        "stable_decision_disagreement_hand_ids":[x["hand_id"] for x in stable_decision_disagreements],
        "threshold_unstable_hand_ids":[x["hand_id"] for x in unstable],
        "seat_dependent_hand_ids":[x["hand_id"] for x in seat_dependent],
        "material_bottom_difference_hand_ids":[x["hand_id"] for x in material_bottom],
        "lowest_joint_bootstrap_confidence":[
            {
                "hand_id":row["hand_id"],
                "dead":row["dead_joint_bootstrap_decision_confidence"],
                "live":row["live_joint_bootstrap_decision_confidence"],
            }
            for row in sorted(
                rows,
                key=lambda x:(
                    min(
                        1.0 if x["dead_joint_bootstrap_decision_confidence"] is None else x["dead_joint_bootstrap_decision_confidence"],
                        1.0 if x["live_joint_bootstrap_decision_confidence"] is None else x["live_joint_bootstrap_decision_confidence"],
                    ),
                    x["hand_id"],
                ),
            )[:10]
        ],
        "lowest_bootstrap_confidence":[
            {
                "hand_id":row["hand_id"],
                "dead":row["dead_bootstrap_decision_confidence"],
                "live":row["live_bootstrap_decision_confidence"],
            }
            for row in sorted(
                rows,
                key=lambda x:(
                    min(
                        1.0 if x["dead_bootstrap_decision_confidence"] is None else x["dead_bootstrap_decision_confidence"],
                        1.0 if x["live_bootstrap_decision_confidence"] is None else x["live_bootstrap_decision_confidence"],
                    ),
                    x["hand_id"],
                ),
            )[:10]
        ],
        "rows":rows,
    }
    Path(args.output).write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print("PHASE5I_DISAGREEMENTS="+json.dumps({
        "decision_class_counts":payload["decision_class_counts"],
        "bottom_class_counts":payload["bottom_class_counts"],
        "stable_decision_disagreement_hand_ids":payload["stable_decision_disagreement_hand_ids"],
        "threshold_unstable_hand_ids":payload["threshold_unstable_hand_ids"],
        "seat_dependent_hand_ids":payload["seat_dependent_hand_ids"],
        "material_bottom_difference_hand_ids":payload["material_bottom_difference_hand_ids"],
    },sort_keys=True))


if __name__=="__main__":
    main()
