#!/usr/bin/env python3
"""Audit deterministic Phase-2 policy opportunities on real deck episodes.

This remains a diagnostic, not a policy optimizer. It distinguishes a card/action
that is stranded because the typed rules layer never made it legal from an action
that WAS legally offered to the policy and was skipped. In addition to hand tutors,
the audit explicitly tracks three high-value engine actions whose reachability is
important for the Urza deck model:

* casting Urza from the command zone;
* attaching The Reality Chip with reconfigure;
* stationing a creature with Uthros Research Craft.

That separation lets later heuristic work target sequencing mistakes without hiding
rules gaps behind an aggregate win rate.
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

ENGINE_ACTIONS = {
    "urza_cast": "main_cast_commander",
    "chip_reconfigure_attach": "main_activate_chip_reconfigure",
    "uthros_station": "main_activate_uthros_station",
}


def _engine_match(label, action):
    if action.kind != ENGINE_ACTIONS[label]:
        return False
    if label == "chip_reconfigure_attach":
        return str(dict(action.parameters).get("choice", "")) == "attach"
    return True


class AuditedPolicy:
    def __init__(self):
        self.base = DeterministicBasePolicy()
        self.policy_id = self.base.policy_id
        self.offered_sources = set()
        self.skipped_sources = set()
        self.chosen_sources = set()
        self.offer_decisions = 0
        self.engine_offered = Counter()
        self.engine_chosen = Counter()
        self.engine_skipped = Counter()
        self.engine_offer_decisions = Counter()

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

        for label in ENGINE_ACTIONS:
            candidates = tuple(action for action in request.actions if _engine_match(label, action))
            if not candidates:
                continue
            self.engine_offered[label] += len(candidates)
            self.engine_offer_decisions[label] += 1
            if any(chosen.canonical_key() == action.canonical_key() for action in candidates):
                self.engine_chosen[label] += 1
            else:
                self.engine_skipped[label] += 1
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

    engine_seed_offered = Counter()
    engine_seed_chosen = Counter()
    engine_seed_skipped = Counter()
    engine_offer_decisions = Counter()
    engine_chosen_decisions = Counter()
    engine_skipped_decisions = Counter()
    engine_examples = {}

    horizon_urza_live = 0
    horizon_urza_left_command_zone = 0
    horizon_chip_present = 0
    horizon_chip_attached = 0
    horizon_uthros_present = 0
    horizon_uthros_with_counters = 0

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

        for label in ENGINE_ACTIONS:
            if policy.engine_offered[label]:
                engine_seed_offered[label] += 1
                engine_offer_decisions[label] += policy.engine_offer_decisions[label]
            if policy.engine_chosen[label]:
                engine_seed_chosen[label] += 1
                engine_chosen_decisions[label] += policy.engine_chosen[label]
            if policy.engine_skipped[label]:
                engine_seed_skipped[label] += 1
                engine_skipped_decisions[label] += policy.engine_skipped[label]
                engine_examples.setdefault(
                    label,
                    (seed, result.terminal_reason, int(result.runtime.true_state.turn)),
                )

        if result.terminal_reason != "horizon":
            continue
        horizon_count += 1
        state = result.runtime.true_state
        final_hand = set(state.hand)
        for tutor in sorted(final_hand & TUTOR_CARDS):
            stranded[tutor] += 1
            if tutor in policy.offered_sources:
                stranded_ever_offered[tutor] += 1
            else:
                stranded_never_offered[tutor] += 1
            if tutor in policy.skipped_sources:
                stranded_skipped[tutor] += 1

        names = {perm.name for perm in state.battlefield}
        if state.urza:
            horizon_urza_live += 1
        if state.commander_in_command_zone:
            horizon_urza_left_command_zone += 1
        if "The Reality Chip" in names:
            horizon_chip_present += 1
        if state.chip_attached:
            horizon_chip_attached += 1
        if "Uthros Research Craft" in names:
            horizon_uthros_present += 1
            if int(state.uthros_counters) > 0:
                horizon_uthros_with_counters += 1

    print(f"PHASE2 POLICY AUDIT: seeds={base_seed}..{base_seed+count-1} horizon=T{horizon}")
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

    print("engine reachability: seeds offered | seeds chosen | seeds with a skipped offer | offer decisions | chosen decisions | skipped decisions")
    for label in ENGINE_ACTIONS:
        print(
            f"  {label:28s} "
            f"{engine_seed_offered[label]:4d} | "
            f"{engine_seed_chosen[label]:4d} | "
            f"{engine_seed_skipped[label]:4d} | "
            f"{engine_offer_decisions[label]:4d} | "
            f"{engine_chosen_decisions[label]:4d} | "
            f"{engine_skipped_decisions[label]:4d}"
        )
        if label in engine_examples:
            seed, terminal, turn = engine_examples[label]
            print(f"    first skipped example: seed={seed} terminal={terminal} final_turn={turn}")

    print("horizon engine state:")
    print(f"  Urza on battlefield:              {horizon_urza_live}/{horizon_count}")
    print(f"  Urza still in command zone:       {horizon_urza_left_command_zone}/{horizon_count}")
    print(f"  Reality Chip present:             {horizon_chip_present}/{horizon_count}")
    print(f"  Reality Chip attached:            {horizon_chip_attached}/{horizon_count}")
    print(f"  Uthros present:                    {horizon_uthros_present}/{horizon_count}")
    print(f"  Uthros with station counters > 0: {horizon_uthros_with_counters}/{horizon_count}")


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
