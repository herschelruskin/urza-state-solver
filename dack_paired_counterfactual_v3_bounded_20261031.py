#!/usr/bin/env python3
"""Opt-in faster STRICT engine: certified London branch-and-bound.

The original reference runner, archived rules and original mulligan policy
remain untouched. This variant applies both (1) exact grave/exile-aware beam
state key and (2) future-rollout suffix pruning only when no possible winning
completion can change the selected bottom. No cross-arm outcome shortcuts.

DO NOT combine result blocks or pool different rules versions.
"""
from __future__ import annotations
import argparse
import json

import dack_counterfactual_rules_v2_strict_key_20261030 as strict
import dack_mulligan_branchbound_v1_20261031 as bounded
import dack_paired_counterfactual_v1_20261030 as reference

RULES_VERSION="dack_strict_state_key_bounded_mulligan_v3"

assert reference.d is strict.d is bounded.d
assert reference.sim is strict.sim is bounded.sim
reference.rules=strict
reference.RULES_VERSION=RULES_VERSION
bounded.install()

def audit():
    assert strict.rule_smoke()["status"]=="PASS"
    assert bounded.selftest()["status"]=="PASS"
    assert bounded.install() is bounded.bounded_bottom_weighted_ev_seat
    report=reference.audit()
    assert report["status"]=="PASS"
    assert report["rules_version"]==RULES_VERSION
    report.update({
        "mode":"exact_bounded_mulligan_with_strict_key",
        "original_policy_unchanged":True,
        "cross_variant_result_shortcuts":False,
        "parity_seed_tests_required":True,
    })
    return report

def one_game(variant,game_id):
    audit()
    bounded.reset_statistics()
    r=reference.game(variant,game_id)
    return {"result":r,"bound_pruning":bounded.get_statistics()}

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit",action="store_true")
    parser.add_argument("--single-variant",choices=list(reference.VARIANTS),default=None)
    parser.add_argument("--start",type=int,default=0)
    parser.add_argument("--games",type=int,default=1)
    parser.add_argument("--out",default="shards/counterfactual_strict_bounded_v3_shard0.json.gz")
    parser.add_argument("--store",default=None)
    args=parser.parse_args()
    if args.audit:
        print(json.dumps(audit(),indent=2))
    elif args.single_variant:
        print(json.dumps(one_game(args.single_variant,args.start),indent=2))
    else:
        audit()
        bounded.reset_statistics()
        reference.run(args.start,args.games,args.out,args.store)
        print("BOUNDING_STATS",json.dumps(bounded.get_statistics(),sort_keys=True),
              flush=True)
