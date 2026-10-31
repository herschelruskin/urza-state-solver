#!/usr/bin/env python3
"""Experimental v5, strict key + bounded London + stable rolls + win witness.

Both reference and accelerated comparisons must install stable dice first.
This is a NEW stochastic engine version: do not mix with legacy outcomes.
"""
from __future__ import annotations
import argparse
import json

import dack_counterfactual_rules_v2_strict_key_20261030 as strict
import dack_mulligan_branchbound_v1_20261031 as bounded
import dack_mulligan_terminal_witness_v1_20261031 as witness
import dack_mulligan_stateless_roll_v1_20261031 as dice
import dack_paired_counterfactual_v1_20261030 as reference

VERSION="dack_stable_dice_strict_bounded_witness_v5"
reference.rules=strict
reference.RULES_VERSION=VERSION

def install():
    dice.install()
    bounded.install()
    witness.install()

def without_witness():
    dice.install()
    bounded.install()
    witness.uninstall()

def audit():
    assert strict.rule_smoke()["status"]=="PASS"
    assert bounded.selftest()["status"]=="PASS"
    assert witness.selftest()["status"]=="PASS"
    assert dice.selftest()["status"]=="PASS"
    install()
    report=reference.audit()
    assert report["rules_version"]==VERSION
    report.update({
        "search_order_invariant_dice":True,
        "early_terminate_winning_frontier_in_keep_futures":True,
        "historical_dice_stream_changed":True,
        "parity_vs_same_dice_unbounded_witness_required":True
    })
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--single-variant",choices=list(reference.VARIANTS))
    p.add_argument("--start",type=int,default=0)
    p.add_argument("--games",type=int,default=1)
    p.add_argument("--out",default="shards/dack_stable_dice_v5_0.json.gz")
    p.add_argument("--store",default=None)
    a=p.parse_args()
    audit()
    if a.audit:
        print(json.dumps({"status":"PASS","rules_version":VERSION},indent=2))
    elif a.single_variant:
        print(json.dumps(reference.game(a.single_variant,a.start),indent=2))
    else:
        reference.run(a.start,a.games,a.out,a.store)
        print("WIN_WITNESS_STATS",json.dumps(dict(witness.counters)),flush=True)
