#!/usr/bin/env python3
"""Audit tutor opportunities under the deterministic Phase-2 base policy.

This is intentionally diagnostic, not a policy optimizer.  It distinguishes tutors
that remain in a T6 horizon hand because the runtime never offered a legal tutor
action from tutors that WERE legally offered and the base policy chose something
else.  That lets policy work target actual sequencing mistakes instead of guessing
from a final hand snapshot.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import urza_solver as solver
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_episode import run_deterministic_episode
from phase2_coverage_profile import opening_runtime

TUTOR_CARDS = frozenset({
    "Dizzy Spell", "Muddle the Mixture", "Merchant Scroll", "Mystical Tutor",
    "Spellseeker", "Reshape", "Transmute Artifact", "Whir of Invention",
    "Scour for Scrap",
})
TUTOR_ACTION_KINDS = frozenset({
    "main_use_simple_tutor",
    "main_use_x_artifact_tutor",
    "main_use_transmute_artifact",
    "main_cast_scour_for_scrap",
})


class AuditedPolicy:
    def __init__(self):
        self.base = DeterministicBasePolicy()
        self.policy_id = self.base.policy_id
        self.offered_sources = set()
        self.skipped_sources = set()
        self.chosen_sources = set()
        self.offer_decisions = 0

    def choose_request(self, request):
        tutor_actions = tuple(
            action for action in request.actions
            if action.kind in TUTOR_ACTION_KINDS and action.source in TUTOR_CARDS
        )
        chosen = self.base.choose_request(request)
        if tutor_actions:
            self.offer_decisions += 1
            offered = {str(action.source) for action in tutor_actions}
            self.offered_sources.update(offered)
            if chosen.kind in TUTOR_ACTION_KINDS and chosen.source in TUTOR_CARDS:
                self.chosen_sources.add(str(chosen.source))
            else:
                self.skipped_sources.update(offered)
        return chosen


def audit(*, base_seed: int, count: int, horizon: int) -> None:
    deck = solver.load_deck(Path("decklist.txt"))
    horizon_count = 0
    stranded = Counter()
    stranded_ever_offered = Counter()
    stranded_never_offered = Counter()
    stranded_skipped = Counter()
    chosen_anywhere = Counter()
    seeds_with_offer = 0
    seeds_with_skipped_offer = 0

    for seed in range(int(base_seed), int(base_seed) + int(count)):
        policy = AuditedPolicy()
        result = run_deterministic_episode(
            opening_runtime(seed, deck),
            horizon=horizon,
            policy=policy,
        )
        for source in policy.chosen_sources:
            chosen_anywhere[source] += 1
        if policy.offered_sources:
            seeds_with_offer += 1
        if policy.skipped_sources:
            seeds_with_skipped_offer += 1
        if result.terminal_reason != "horizon":
            continue
        horizon_count += 1
        final_hand = set(result.runtime.true_state.hand)
        for tutor in sorted(final_hand & TUTOR_CARDS):
            stranded[tutor] += 1
            if tutor in policy.offered_sources:
                stranded_ever_offered[tutor] += 1
            else:
                stranded_never_offered[tutor] += 1
            if tutor in policy.skipped_sources:
                stranded_skipped[tutor] += 1

    print(f"PHASE2 TUTOR POLICY AUDIT: seeds={base_seed}..{base_seed+count-1} horizon=T{horizon}")
    print(f"horizon trajectories: {horizon_count}/{count}")
    print(f"seeds where a hand-tutor action was legally offered: {seeds_with_offer}/{count}")
    print(f"seeds where policy skipped at least one offered hand tutor: {seeds_with_skipped_offer}/{count}")
    print("stranded tutor cards at horizon: total | ever legally offered | never offered | offered then skipped")
    for tutor, total in stranded.most_common():
        print(
            f"  {tutor:24s} {total:4d} | "
            f"{stranded_ever_offered[tutor]:4d} | "
            f"{stranded_never_offered[tutor]:4d} | "
            f"{stranded_skipped[tutor]:4d}"
        )
    print("seeds where each tutor source was actually chosen at least once:")
    for tutor, total in chosen_anywhere.most_common():
        print(f"  {tutor:24s} {total:4d}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260821)
    ap.add_argument("--count", type=int, default=250)
    ap.add_argument("--horizon", type=int, default=6)
    args = ap.parse_args()
    if args.count <= 0:
        raise SystemExit("--count must be positive")
    audit(base_seed=args.seed, count=args.count, horizon=args.horizon)


if __name__ == "__main__":
    main()
