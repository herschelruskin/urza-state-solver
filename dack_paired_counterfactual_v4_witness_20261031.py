#!/usr/bin/env python3
"""Opt-in v4: exact bounded London + immediate reachable winning-line collapse.

Only hypothetical mulligan searches use the modified existential frontier
search. Final kept-hand gameplay and diagnostics remain original.

No change to original random sampling, bottoming policy, or beam width.
"""
from __future__ import annotations
import argparse
import json

import dack_counterfactual_rules_v2_strict_key_20261030 as strict
import dack_mulligan_branchbound_v1_20261031 as bounded
import dack_mulligan_terminal_witness_v1_20261031 as witness
import dack_paired_counterfactual_v1_20261030 as reference

RULES_VERSION="dack_strict_bounded_terminal_witness_v4"

assert reference.d is strict.d is bounded.d is witness.d
reference.rules=strict
reference.RULES_VERSION=RULES_VERSION

def install():
    bounded.install()
    witness.install()

def uninstall():
    witness.uninstall()
    bounded.uninstall()

def audit():
    install()
    assert strict.rule_smoke()["status"]=="PASS"
    assert bounded.selftest()["status"]=="PASS"
    assert witness.selftest()["status"]=="PASS"
    install()
    report=reference.audit()
    assert report["rules_version"]==RULES_VERSION
    report["win_only_search_scoped_to_london"]=True
    report["requires_same_seed_policy_parity"]=True
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--single-variant",choices=list(reference.VARIANTS))
    p.add_argument("--start",type=int,default=0)
    p.add_argument("--games",type=int,default=1)
    p.add_argument("--out",default="shards/dack_strict_bounded_v4_0.json.gz")
    p.add_argument("--store",default=None)
    x=p.parse_args()
    audit()
    if x.audit:
        print(json.dumps({"status":"PASS","rules_version":RULES_VERSION,
                          "mulligan_witness_scope":True},indent=2))
    elif x.single_variant:
        print(json.dumps(reference.game(x.single_variant,x.start),indent=2))
    else:
        reference.run(x.start,x.games,x.out,x.store)
        print("TERMINAL_WITNESS_STATS",json.dumps(dict(witness.counters)),flush=True)
