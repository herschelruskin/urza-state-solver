#!/usr/bin/env python3
"""Opt-in zero-beam London policy v6; exact v5 chance and beam-160 game engine.

A probabilistic hand-score proxy decides London keeps/bottoms. This is NOT an
exact replacement for assertive London v5. Never pool v5 and v6 results.

Validation objective: compare the honest, paired, realized Dack deployment
rates across the SAME independently sampled game seeds, and select a policy
only after an independent N large enough for reliable paired intervals.
"""
from __future__ import annotations
import argparse
import json

import dack_counterfactual_rules_v2_strict_key_20261030 as strict
import dack_mulligan_stateless_roll_v1_20261031 as dice
import dack_mulligan_analytic_policy_v6_20261031 as analytic
import dack_paired_counterfactual_v1_20261030 as ref

VERSION="dack_stable_dice_strict_nobeam_analytic_london_v6"
ref.rules=strict
ref.RULES_VERSION=VERSION

def install():
    dice.install()
    # Verify no future-value optimization installs hook into decision-maker.
    ref.choose_keep=analytic.choose_keep

def audit():
    assert strict.rule_smoke()["status"]=="PASS"
    assert dice.selftest()["status"]=="PASS"
    assert analytic.selftest()["status"]=="PASS"
    install()
    check=ref.audit()
    assert check["rules_version"]==VERSION
    return dict(check,
        mulligan_policy=analytic.POLICY_VERSION,
        mulligan_beam_width=0,
        approximate_keep_decision=True,
        no_future_draw_order_peek=True,
        analytic_probabilities_used_only_for_simple_draw_events=True,
        proxy_not_cast_probability=True,
        gameplay_beam=160,
        historical_beam_policy_comparable_only_as_different_policy=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--single-variant",choices=list(ref.VARIANTS))
    p.add_argument("--start",type=int,default=0)
    p.add_argument("--games",type=int,default=1)
    p.add_argument("--out",default="shards/dack_no_beam_policy_v6_shard0.json.gz")
    p.add_argument("--store",default=None)
    a=p.parse_args()
    audit()
    if a.audit:
        print(json.dumps(audit(),indent=2),flush=True)
    elif a.single_variant:
        print("ANALYTIC_POLICY_GAME",json.dumps(ref.game(a.single_variant,a.start)),flush=True)
    else:
        ref.run(a.start,a.games,a.out,a.store)
        print("ANALYTIC_POLICY_STATS",json.dumps(dict(analytic.STATS)),flush=True)
