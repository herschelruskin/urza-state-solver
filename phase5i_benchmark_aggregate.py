#!/usr/bin/env python3
"""Aggregate Phase-5I human-hand values with independent London thresholds.

Inputs are intentionally separated:
- phase5i_human_hand_*.json: held-out exact human sevens scored by the solver;
- factorized or replicated continuation-stage models fit only from fresh random
  deck sevens, never from the human labels.

For a human hand observed at London stage s, the model decision compares its
seat-conditioned K_s(hand) with independently estimated V_{s+1}. Stage 6 remains
the forced keep-two floor. Because human Commander seat is unknown, decision
agreement is reported separately for seat 1 (25%) and Caverns-live seats 2-4
(75%) before an ex-ante agreement probability is formed.
"""

from __future__ import annotations

import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path

from phase3_value_engine import WinDistributionValue
from phase5_mulligan import MULLIGAN_FLOOR_STAGE


HORIZON=6
CONTEXT_WEIGHTS={"dead":0.25,"live":0.75}


def value_from_json(payload):
    return WinDistributionValue(
        horizon=HORIZON,
        exact_win=tuple(float(x) for x in payload["exact_win"]),
        no_win=float(payload["no_win"]),
        win_families=tuple(
            (str(name),float(probability))
            for name,probability in payload.get("win_families",())
        ),
    )


def value_json(value):
    return {
        "win_probability":value.win_probability,
        "exact_win":list(value.exact_win),
        "cumulative":[value.win_by(t) for t in range(1,value.horizon+1)],
        "comparison_key":list(value.comparison_key()),
        "no_win":value.no_win,
        "win_families":[list(x) for x in value.win_families],
    }


def mean_values(values):
    values=tuple(values)
    if not values:
        raise ValueError("cannot average zero values")
    weight=1.0/len(values)
    return WinDistributionValue.mixture(
        tuple((weight,value) for value in values),
        horizon=HORIZON,
    )


def _factorized_stage_model(directory,context):
    path=Path(directory)/f"phase5i_stage_model_{context}_factorized.json"
    if not path.exists():
        return None
    payload=json.loads(path.read_text(encoding="utf-8"))
    values={
        int(stage["stage"]):value_from_json(stage["value"])
        for stage in payload["stages"]
    }
    replicate_values=defaultdict(list)
    for replicate in payload.get("stability_replicates",()):
        for stage in replicate["stages"]:
            replicate_values[int(stage["stage"])].append(
                value_from_json(stage["value"])
            )
    return {
        "source":"factorized",
        "replicate_count":len(payload.get("stability_replicates",())),
        "values":values,
        "replicate_values":{
            stage:tuple(replicate_values.get(stage,()))
            for stage in values
        },
        "sample_count_per_stage":payload.get("sample_count_per_stage",{}),
    }


def load_stage_models(directory):
    # Prefer the factorized model: it has more independent K_s samples and its
    # stability replicates are derived from disjoint sample-ID groups. The older
    # serial replicates remain supported as a fallback/provenance path.
    factorized={
        context:_factorized_stage_model(directory,context)
        for context in ("dead","live")
    }
    if all(factorized.values()):
        return factorized

    grouped=defaultdict(list)
    for path in sorted(Path(directory).glob("phase5i_stage_model_*_rep*.json")):
        payload=json.loads(path.read_text(encoding="utf-8"))
        grouped[str(payload["context"])].append(payload)
    missing={"dead","live"}-set(grouped)
    if missing:
        raise SystemExit(f"missing stage-model contexts: {sorted(missing)}")

    result={}
    for context,models in grouped.items():
        by_stage=defaultdict(list)
        for model in models:
            for stage in model["stages"]:
                by_stage[int(stage["stage"])].append(value_from_json(stage["value"]))
        result[context]={
            "source":"serial-replicates",
            "replicate_count":len(models),
            "values":{
                stage:mean_values(values)
                for stage,values in by_stage.items()
            },
            "replicate_values":{
                stage:tuple(values)
                for stage,values in by_stage.items()
            },
            "sample_count_per_stage":{},
        }
    return result


def hand_context(hand,context):
    contexts=hand["contexts"]
    invariant=next((x for x in contexts if x["label"]=="seat_invariant"),None)
    if invariant is not None:
        return invariant
    wanted=("seat1_caverns_dead" if context=="dead" else "seats2to4_caverns_live")
    return next(x for x in contexts if x["label"]==wanted)


def keep_value(hand,context):
    row=hand_context(hand,context)
    return value_from_json(row["solver"]["best"]["value"])


def model_decision(keep,continuation):
    if continuation is None:
        return "Keep"
    return "Keep" if keep.comparison_key()>=continuation.comparison_key() else "Mulligan"


def weighted_bottom_metric(hand,key,default=None):
    total=0.0
    seen=False
    for context,weight in CONTEXT_WEIGHTS.items():
        row=hand_context(hand,context)
        diag=row["human_bottom_diagnostic"]
        if not diag["applicable"]:
            continue
        value=key(diag)
        if value is None:
            continue
        total+=weight*float(value)
        seen=True
    return total if seen else default


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--human-dir",default=".")
    p.add_argument("--stage-dir",default=".")
    p.add_argument("--output",default="phase5i_human_benchmark_summary.json")
    args=p.parse_args()

    hands=[]
    for path in sorted(Path(args.human_dir).glob("phase5i_human_hand_*.json")):
        hands.append(json.loads(path.read_text(encoding="utf-8")))
    if len(hands)!=35:
        raise SystemExit(f"expected 35 exact human hand files, found {len(hands)}")
    hands=sorted(hands,key=lambda row:int(row["hand_id"]))
    stage_models=load_stage_models(args.stage_dir)

    rows=[]
    agreement_weighted=0.0
    seat_consensus=0
    seat_consensus_correct=0
    by_stage=defaultdict(lambda:{"n":0,"agreement_weight":0.0})
    bottom_n=0
    bottom_exact_weight=0.0
    bottom_rank_weight=0.0
    bottom_regret_weight=0.0
    decision_counts=Counter()
    replicate_unstable_context_decisions=0
    replicate_context_decisions=0

    for hand in hands:
        stage=int(hand["human"]["mulligan_count"])
        human_decision=str(hand["human"]["decision"])
        context_rows={}
        decisions=[]
        for context,weight in CONTEXT_WEIGHTS.items():
            keep=keep_value(hand,context)
            continuation=(
                None
                if stage>=MULLIGAN_FLOOR_STAGE
                else stage_models[context]["values"][stage+1]
            )
            decision=model_decision(keep,continuation)
            decisions.append(decision)
            correct=(decision==human_decision)
            agreement_weighted+=weight*float(correct)
            by_stage[stage]["agreement_weight"]+=weight*float(correct)
            replicate_decisions=[
                model_decision(keep,rep_value)
                for rep_value in (
                    () if continuation is None
                    else stage_models[context]["replicate_values"].get(stage+1,())
                )
            ]
            if replicate_decisions:
                replicate_context_decisions+=1
                replicate_unstable_context_decisions+=int(
                    len(set(replicate_decisions))>1
                )
            context_rows[context]={
                "weight":weight,
                "solver_decision":decision,
                "matches_human":correct,
                "keep_value":value_json(keep),
                "continuation_value":None if continuation is None else value_json(continuation),
                "replicate_decisions":replicate_decisions,
                "replicate_stable":(
                    None if not replicate_decisions
                    else len(set(replicate_decisions))==1
                ),
            }
            decision_counts[(context,decision)]+=1

        if len(set(decisions))==1:
            seat_consensus+=1
            seat_consensus_correct+=int(decisions[0]==human_decision)
        by_stage[stage]["n"]+=1

        bottom_applicable=any(
            hand_context(hand,context)["human_bottom_diagnostic"]["applicable"]
            for context in CONTEXT_WEIGHTS
        )
        bottom_summary=None
        if bottom_applicable:
            bottom_n+=1
            exact=weighted_bottom_metric(
                hand,
                lambda d:1.0 if d["exact_match"] else 0.0,
                0.0,
            )
            rank=weighted_bottom_metric(
                hand,
                lambda d:d["confirmed_rank_among_shortlist_plus_human"],
                None,
            )
            regret=weighted_bottom_metric(
                hand,
                lambda d:d["regret"]["delta_pwin_best_minus_human"],
                None,
            )
            bottom_exact_weight+=float(exact or 0.0)
            if rank is not None:
                bottom_rank_weight+=float(rank)
            if regret is not None:
                bottom_regret_weight+=float(regret)
            bottom_summary={
                "ex_ante_exact_match_probability":exact,
                "ex_ante_confirmed_rank":rank,
                "ex_ante_delta_pwin_regret":regret,
                "contexts":{
                    context:hand_context(hand,context)["human_bottom_diagnostic"]
                    for context in CONTEXT_WEIGHTS
                },
            }

        rows.append({
            "hand_id":int(hand["hand_id"]),
            "stage":stage,
            "keep_size":int(hand["human"]["keep_size"]),
            "human_decision":human_decision,
            "rating_within_size":hand["human"].get("rating_within_size"),
            "seat_contexts":context_rows,
            "seat_consensus":len(set(decisions))==1,
            "ex_ante_decision_agreement_probability":sum(
                CONTEXT_WEIGHTS[c]*float(context_rows[c]["matches_human"])
                for c in CONTEXT_WEIGHTS
            ),
            "bottom":bottom_summary,
        })

    payload={
        "kind":"phase5i-human-benchmark-summary",
        "human_hand_count":len(hands),
        "stage_model":{
            context:{
                "source":row["source"],
                "replicate_count":row["replicate_count"],
                "sample_count_per_stage":row.get("sample_count_per_stage",{}),
                "mean_values":{
                    str(stage):value_json(value)
                    for stage,value in sorted(row["values"].items())
                },
            }
            for context,row in stage_models.items()
        },
        "decision":{
            "weighted_agreement":agreement_weighted/len(hands),
            "weighted_correct_equivalent_hands":agreement_weighted,
            "seat_consensus_count":seat_consensus,
            "seat_consensus_correct":seat_consensus_correct,
            "replicate_context_decisions":replicate_context_decisions,
            "replicate_unstable_context_decisions":replicate_unstable_context_decisions,
            "replicate_instability_rate":(
                replicate_unstable_context_decisions/replicate_context_decisions
                if replicate_context_decisions else None
            ),
            "by_stage":{
                str(stage):{
                    "n":row["n"],
                    "weighted_agreement":row["agreement_weight"]/row["n"],
                }
                for stage,row in sorted(by_stage.items())
            },
            "solver_counts":{
                f"{context}:{decision}":count
                for (context,decision),count in sorted(decision_counts.items())
            },
        },
        "bottom":{
            "applicable_hand_count":bottom_n,
            "weighted_exact_match_rate":(
                bottom_exact_weight/bottom_n if bottom_n else None
            ),
            "mean_ex_ante_confirmed_rank":(
                bottom_rank_weight/bottom_n if bottom_n else None
            ),
            "mean_delta_pwin_regret":(
                bottom_regret_weight/bottom_n if bottom_n else None
            ),
        },
        "rows":rows,
    }
    Path(args.output).write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print("PHASE5I_SUMMARY="+json.dumps({
        "decision":payload["decision"],
        "bottom":payload["bottom"],
    },sort_keys=True))


if __name__=="__main__":
    main()
