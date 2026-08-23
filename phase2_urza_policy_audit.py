#!/usr/bin/env python3
"""Audit Urza permission offer/use/expiry behavior under the deterministic policy.

This diagnostic answers a narrower question than the general Phase-2 policy audit:
once a card has been publicly exiled by Urza and a typed permission action is legal,
does the base policy actually use it?  Counts are grouped by public card/use/timing
family and never inspect hidden library order.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import urza_solver as solver
from non_oracle_base_policy import DeterministicBasePolicy
from non_oracle_episode import run_deterministic_episode
from phase2_coverage_profile import opening_runtime

PERMISSION_KIND = "main_use_urza_permission"
SPIN_KIND = "main_activate_urza_spin"
END_KIND = "main_end_turn"


def _permission_family(action):
    params = dict(action.parameters)
    return (
        str(params.get("card", "")),
        str(params.get("use", "")),
        "priority" if bool(params.get("priority", False)) else "main",
    )


def _family_label(family):
    card, use, timing = family
    return f"{card} | {use} | {timing}"


class UrzaPermissionAuditedPolicy:
    def __init__(self):
        self.base = DeterministicBasePolicy()
        self.policy_id = self.base.policy_id
        self.offered_families = set()
        self.chosen_families = set()
        self.skipped_families = set()
        self.offer_decisions = Counter()
        self.chosen_decisions = Counter()
        self.skipped_decisions = Counter()
        self.expired_unused = Counter()
        self.expired_after_offer = Counter()
        self.offered_cards = set()
        self.priority_spin_offers = 0
        self.priority_spin_chosen = 0
        self.priority_spin_skipped = 0

    def choose_request(self, request):
        permission_actions = tuple(a for a in request.actions if a.kind == PERMISSION_KIND)
        families = {_permission_family(a) for a in permission_actions}
        for family in families:
            self.offered_families.add(family)
            self.offered_cards.add(family[0])
            self.offer_decisions[family] += 1

        priority_spins = tuple(
            a for a in request.actions
            if a.kind == SPIN_KIND and bool(dict(a.parameters).get("priority", False))
        )
        if priority_spins:
            self.priority_spin_offers += 1

        chosen = self.base.choose_request(request)

        chosen_family = None
        if chosen.kind == PERMISSION_KIND:
            chosen_family = _permission_family(chosen)
            self.chosen_families.add(chosen_family)
            self.chosen_decisions[chosen_family] += 1
        for family in families:
            if family != chosen_family:
                self.skipped_families.add(family)
                self.skipped_decisions[family] += 1

        if priority_spins:
            if any(chosen.canonical_key() == spin.canonical_key() for spin in priority_spins):
                self.priority_spin_chosen += 1
            else:
                self.priority_spin_skipped += 1

        # Urza permissions expire at end of turn. RuntimePolicyView intentionally
        # hides execution IDs, but card/multiplicity is public and sufficient for
        # this diagnostic.
        if chosen.kind == END_KIND:
            for permission in request.observation.play_permissions:
                card = str(permission.card)
                self.expired_unused[card] += 1
                if card in self.offered_cards:
                    self.expired_after_offer[card] += 1

        return chosen


def audit(*, base_seed: int, count: int, horizon: int) -> None:
    deck = solver.load_deck(Path("decklist.txt"))
    family_seed_offered = Counter()
    family_seed_chosen = Counter()
    family_seed_skipped = Counter()
    family_offer_decisions = Counter()
    family_chosen_decisions = Counter()
    family_skipped_decisions = Counter()
    expired_unused = Counter()
    expired_after_offer = Counter()
    spin_seed_offered = 0
    spin_seed_chosen = 0
    spin_offer_decisions = 0
    spin_chosen_decisions = 0
    spin_skipped_decisions = 0
    terminal = Counter()

    for seed in range(int(base_seed), int(base_seed) + int(count)):
        policy = UrzaPermissionAuditedPolicy()
        result = run_deterministic_episode(
            opening_runtime(seed, deck),
            horizon=horizon,
            policy=policy,
        )
        terminal[result.terminal_reason] += 1

        for family in policy.offered_families:
            family_seed_offered[family] += 1
        for family in policy.chosen_families:
            family_seed_chosen[family] += 1
        for family in policy.skipped_families:
            family_seed_skipped[family] += 1
        family_offer_decisions.update(policy.offer_decisions)
        family_chosen_decisions.update(policy.chosen_decisions)
        family_skipped_decisions.update(policy.skipped_decisions)
        expired_unused.update(policy.expired_unused)
        expired_after_offer.update(policy.expired_after_offer)

        if policy.priority_spin_offers:
            spin_seed_offered += 1
            spin_offer_decisions += policy.priority_spin_offers
        if policy.priority_spin_chosen:
            spin_seed_chosen += 1
            spin_chosen_decisions += policy.priority_spin_chosen
        spin_skipped_decisions += policy.priority_spin_skipped

    print(f"PHASE2 URZA PERMISSION POLICY AUDIT: seeds={base_seed}..{base_seed+count-1} horizon=T{horizon}")
    print(f"terminal reasons: {dict(sorted(terminal.items()))}")
    print("permission families: seed offered | seed chosen | seed skipped | offer decisions | chosen decisions | skipped decisions")
    families = sorted(
        family_seed_offered,
        key=lambda family: (-family_seed_offered[family], _family_label(family)),
    )
    if not families:
        print("  none")
    for family in families:
        print(
            f"  {_family_label(family):64s} "
            f"{family_seed_offered[family]:4d} | "
            f"{family_seed_chosen[family]:4d} | "
            f"{family_seed_skipped[family]:4d} | "
            f"{family_offer_decisions[family]:4d} | "
            f"{family_chosen_decisions[family]:4d} | "
            f"{family_skipped_decisions[family]:4d}"
        )

    print("permissions expired unused: total | after at least one legal offer for same card")
    cards = sorted(expired_unused, key=lambda card: (-expired_unused[card], card))
    if not cards:
        print("  none")
    for card in cards:
        print(f"  {card:32s} {expired_unused[card]:4d} | {expired_after_offer[card]:4d}")

    print("priority Urza spin: seeds offered | seeds chosen | offer decisions | chosen decisions | skipped decisions")
    print(
        f"  {spin_seed_offered:4d} | {spin_seed_chosen:4d} | "
        f"{spin_offer_decisions:4d} | {spin_chosen_decisions:4d} | {spin_skipped_decisions:4d}"
    )


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
