#!/usr/bin/env python3
"""Reduce independent K_s(h) samples into a backward London stage model.

The full model uses every available independent K_s(h) sample at each stage.
When at least four matched sample IDs exist at every stage, two disjoint
stability replicates (first half vs second half by sample ID) are also reduced
through the complete backward DP.  These replicate stage values are diagnostics,
not human-label tuning inputs.
"""

from __future__ import annotations

import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path

from phase3_value_engine import WinDistributionValue


HORIZON=6
FLOOR_STAGE=6


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
    rows=tuple(values)
    if not rows:
        raise ValueError("cannot average zero values")
    w=1.0/len(rows)
    return WinDistributionValue.mixture(tuple((w,v) for v in rows),horizon=HORIZON)


def reduce_stage_model(by_stage, *, allowed_sample_ids=None):
    fitted={}
    rows=[]
    for stage in range(FLOOR_STAGE,-1,-1):
        samples=sorted(by_stage[stage],key=lambda x:int(x["sample_id"]))
        if allowed_sample_ids is not None:
            samples=[
                sample for sample in samples
                if int(sample["sample_id"]) in allowed_sample_ids
            ]
        if not samples:
            raise ValueError(f"no samples remain at stage {stage}")

        selected=[]
        kept=mulled=0
        reasons=Counter()
        decisions=[]
        continuation=None if stage==FLOOR_STAGE else fitted[stage+1]
        for sample in samples:
            keep=value_from_json(sample["keep_value"])
            if continuation is None or keep.comparison_key()>=continuation.comparison_key():
                chosen=keep
                decision="Keep"
                kept+=1
            else:
                chosen=continuation
                decision="Mulligan"
                mulled+=1
            selected.append(chosen)
            reasons.update(dict(sample.get("terminal_reasons",())))
            decisions.append({
                "sample_id":int(sample["sample_id"]),
                "seven":sample["seven"],
                "best_bottom":sample["best_bottom"],
                "keep_value":sample["keep_value"],
                "continuation_value":None if continuation is None else value_json(continuation),
                "decision":decision,
            })
        fitted[stage]=mean_values(selected)
        rows.append({
            "stage":stage,
            "keep_size":int(samples[0]["keep_size"]),
            "value":value_json(fitted[stage]),
            "sampled_hands":len(samples),
            "kept_count":kept,
            "mulligan_count":mulled,
            "keep_rate":kept/len(samples),
            "terminal_reasons":[list(x) for x in sorted(reasons.items())],
            "decisions":decisions,
        })
    return tuple(sorted(rows,key=lambda x:int(x["stage"])))


def stability_groups(by_stage):
    common=None
    for stage in range(7):
        ids={int(sample["sample_id"]) for sample in by_stage[stage]}
        common=ids if common is None else common & ids
    ids=sorted(common or ())
    if len(ids)<4:
        return ()
    midpoint=len(ids)//2
    if midpoint<2 or len(ids)-midpoint<2:
        return ()
    return (
        ("replicate_0",frozenset(ids[:midpoint])),
        ("replicate_1",frozenset(ids[midpoint:])),
    )


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input-dir",default=".")
    p.add_argument("--context",choices=("dead","live"),required=True)
    p.add_argument("--output",default=None)
    args=p.parse_args()

    by_stage=defaultdict(list)
    for path in sorted(Path(args.input_dir).glob(f"phase5i_stage_sample_{args.context}_s*_n*.json")):
        payload=json.loads(path.read_text(encoding="utf-8"))
        by_stage[int(payload["stage"])].append(payload)
    missing=[stage for stage in range(7) if not by_stage.get(stage)]
    if missing:
        raise SystemExit(f"missing stage samples for {args.context}: {missing}")

    rows=reduce_stage_model(by_stage)
    replicate_models=[]
    for label,sample_ids in stability_groups(by_stage):
        replicate_models.append({
            "label":label,
            "sample_ids":sorted(sample_ids),
            "stages":list(reduce_stage_model(by_stage,allowed_sample_ids=sample_ids)),
        })

    outer_confirm_values={
        int(sample["budgets"]["outer_confirm"])
        for stage in range(7)
        for sample in by_stage[stage]
    }
    if len(outer_confirm_values)!=1:
        raise SystemExit(
            f"inconsistent outer-confirm budgets for {args.context}: "
            f"{sorted(outer_confirm_values)}"
        )
    payload={
        "kind":"phase5i-factorized-stage-model",
        "context":args.context,
        "representative_seat":1 if args.context=="dead" else 2,
        "outer_confirm_rollouts":next(iter(outer_confirm_values)),
        "sample_count_per_stage":{
            str(stage):len(by_stage[stage]) for stage in range(7)
        },
        "stages":list(rows),
        "stability_replicates":replicate_models,
    }
    output=args.output or f"phase5i_stage_model_{args.context}_factorized.json"
    Path(output).write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print("PHASE5I_STAGE_REDUCED="+json.dumps({
        "context":args.context,
        "stages":{
            str(row["stage"]):{
                "pwin":row["value"]["win_probability"],
                "keep_rate":row["keep_rate"],
                "key":row["value"]["comparison_key"],
            }
            for row in payload["stages"]
        },
        "stability_replicates":[{
            "label":rep["label"],
            "sample_ids":rep["sample_ids"],
            "stage_pwin":{
                str(row["stage"]):row["value"]["win_probability"]
                for row in rep["stages"]
            },
        } for rep in replicate_models],
    },sort_keys=True))


if __name__=="__main__":
    main()
