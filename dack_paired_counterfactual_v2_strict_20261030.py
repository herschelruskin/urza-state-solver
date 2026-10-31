#!/usr/bin/env python3
"""Opt-in strict-state-key paired runner, isolated from the v1 reference.

Same scenario seeds, deck variants and outcome schema as v1, but stricter
state deduplication. Its outcomes MUST NOT be pooled with v1; engine/rules
version and source fingerprints are different. Compare wall time and traces
before selecting the strict runner for an exploratory screen.
"""
from __future__ import annotations
import argparse
import json

# Critical import order: apply strict key before importing the reference
# runner, while retaining the unchanged v1 entrypoint for parity controls.
import dack_counterfactual_rules_v2_strict_key_20261030 as strict
import dack_paired_counterfactual_v1_20261030 as reference

assert reference.d is strict.d and reference.sim is strict.sim
reference.rules = strict
reference.RULES_VERSION = strict.RULES_VERSION

def audit():
    report = reference.audit()
    assert report["rules_version"] == strict.RULES_VERSION
    assert strict.rule_smoke()["status"] == "PASS"
    report["mode"] = "strict_state_key_opt_in_v2"
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--games", type=int, default=1)
    parser.add_argument("--out", default="shards/strict_v2_shard0.json.gz")
    parser.add_argument("--store", default=None)
    parser.add_argument("--single-variant", choices=list(reference.VARIANTS), default=None)
    opt = parser.parse_args()
    if opt.audit:
        print(json.dumps(audit(), indent=2))
    elif opt.single_variant:
        audit()
        print(json.dumps(reference.game(opt.single_variant, opt.start), indent=2))
    else:
        audit()
        reference.run(opt.start, opt.games, opt.out, opt.store)

if __name__ == "__main__":
    main()
