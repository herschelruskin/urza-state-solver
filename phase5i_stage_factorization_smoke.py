#!/usr/bin/env python3
"""Regression checks for factorized Phase-5I London DP reduction."""

from __future__ import annotations

from collections import defaultdict

from phase3_value_engine import WinDistributionValue
from phase5i_stage_sample_reduce import reduce_stage_model


def value(p,turn=6):
    exact=[0.0]*6
    exact[int(turn)-1]=float(p)
    return WinDistributionValue(
        horizon=6,
        exact_win=tuple(exact),
        no_win=1.0-float(p),
        win_families=(),
    )


def payload(value_obj,sample_id,stage):
    return {
        "sample_id":int(sample_id),
        "stage":int(stage),
        "keep_size":7 if stage<2 else 8-stage,
        "seven":[f"stage{stage}-sample{sample_id}"],
        "best_bottom":[],
        "keep_value":{
            "win_probability":value_obj.win_probability,
            "exact_win":list(value_obj.exact_win),
            "no_win":value_obj.no_win,
            "win_families":[],
        },
        "terminal_reasons":[],
    }


def test_floor_is_forced_keep_and_stage5_uses_floor_continuation():
    rows=defaultdict(list)
    # Fill irrelevant earlier stages with deterministic zeros so reduction can
    # traverse the complete model.
    for stage in range(0,5):
        rows[stage]=[
            payload(value(0.0),0,stage),
            payload(value(0.0),1,stage),
        ]

    # Keep-two floor: V6 = average(0.25, 0.75) = 0.50; no mulligan option.
    rows[6]=[
        payload(value(0.25),0,6),
        payload(value(0.75),1,6),
    ]
    # Stage5: first hand 0.25 should mull to V6=0.50; second hand 1.0 keeps.
    # Therefore V5 = average(0.50,1.00)=0.75.
    rows[5]=[
        payload(value(0.25),0,5),
        payload(value(1.0),1,5),
    ]

    reduced={row["stage"]:row for row in reduce_stage_model(rows)}
    assert abs(reduced[6]["value"]["win_probability"]-0.50)<1e-12,reduced[6]
    assert reduced[6]["kept_count"]==2 and reduced[6]["mulligan_count"]==0
    assert abs(reduced[5]["value"]["win_probability"]-0.75)<1e-12,reduced[5]
    assert reduced[5]["kept_count"]==1 and reduced[5]["mulligan_count"]==1
    assert [x["decision"] for x in reduced[5]["decisions"]]==["Mulligan","Keep"]
    print("factorized reducer preserves keep-two floor and backward max recursion: PASS")


def test_earlier_win_breaks_equal_pwin_tie():
    rows=defaultdict(list)
    # V6 = 0.5 probability winning on T6.
    for stage in range(7):
        rows[stage]=[
            payload(value(0.5,turn=6),0,stage),
            payload(value(0.5,turn=6),1,stage),
        ]
    # At stage5, sample 0 has same pwin but all wins T4, so the full
    # distribution-valued objective must keep it over V6's T6 wins.
    rows[5][0]=payload(value(0.5,turn=4),0,5)

    reduced={row["stage"]:row for row in reduce_stage_model(rows)}
    decisions=[x["decision"] for x in reduced[5]["decisions"]]
    assert decisions[0]=="Keep",decisions
    print("factorized reducer preserves full T1..T6 distribution ordering: PASS")


def main():
    test_floor_is_forced_keep_and_stage5_uses_floor_continuation()
    test_earlier_win_breaks_equal_pwin_tie()
    print("PHASE5I STAGE FACTORIZATION SMOKE: ALL PASS")


if __name__=="__main__":
    main()
