#!/usr/bin/env python3
"""Reduce independent K_s(h) samples into a backward London stage model."""

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

    fitted={}
    rows=[]
    for stage in range(FLOOR_STAGE,-1,-1):
        selected=[]
        kept=mulled=0
        reasons=Counter()
        decisions=[]
        continuation=None if stage==FLOOR_STAGE else fitted[stage+1]
        for sample in sorted(by_stage[stage],key=lambda x:int(x["sample_id"])):
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
            "keep_size":int(by_stage[stage][0]["keep_size"]),
            "value":value_json(fitted[stage]),
            "sampled_hands":len(by_stage[stage]),
            "kept_count":kept,
            "mulligan_count":mulled,
            "keep_rate":kept/len(by_stage[stage]),
            "terminal_reasons":[list(x) for x in sorted(reasons.items())],
            "decisions":decisions,
        })

    payload={
        "kind":"phase5i-factorized-stage-model",
        "context":args.context,
        "representative_seat":1 if args.context=="dead" else 2,
        "sample_count_per_stage":{
            str(stage):len(by_stage[stage]) for stage in range(7)
        },
        "stages":sorted(rows,key=lambda x:int(x["stage"])),
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
    },sort_keys=True))


if __name__=="__main__":
    main()
