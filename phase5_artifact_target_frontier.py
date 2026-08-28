#!/usr/bin/env python3
"""Objective-aware artifact tutor target frontier for bounded Phase-5 Q.

Rules still expose every legal search target.  This module is policy-side only:
for the goldfish `win_by_horizon` objective it cheaply removes targets whose
currently modeled strategic feature vector is dominated by another revealed
target.  It never reads concrete hidden library order.

This is intentionally versioned as an objective-specific approximation, not as
rules-level action equivalence.  Exact card identity can still affect later
shuffle/draw outcomes in a singleton deck, so promotion requires benchmark
validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

import urza_solver as solver
from decision_observation import ActionIntent
from non_oracle_runtime_view import RuntimePolicyView


ARTIFACT_TARGET_FRONTIER_VERSION = "urza-artifact-target-frontier-v1"

ROLE_COMBO = 1 << 0
ROLE_PRODUCER = 1 << 1
ROLE_MANA = 1 << 2
ROLE_VALUE = 1 << 3
ROLE_UNTAP = 1 << 4
ROLE_TUTOR = 1 << 5
ROLE_PROTECTION = 1 << 6
ROLE_DRAW = 1 << 7
ROLE_OPPONENT_ONLY = 1 << 8
ROLE_GENERIC_BODY = 1 << 9

COMBO_TARGETS = frozenset({
    "Grinding Station",
    "Battered Golem",
    "Forensic Gadgeteer",
    "Grim Monolith",
    "Basalt Monolith",
    "Sensei's Divining Top",
    "The Reality Chip",
    "Sewer-veillance Cam",
    "Repurposing Bay",
})
PRODUCER_TARGETS = frozenset(getattr(solver, "PRODUCERS", ()))
VALUE_TARGETS = frozenset({
    "The One Ring",
    "Uthros Research Craft",
    "The Reality Chip",
    "Sensei's Divining Top",
    "Sewer-veillance Cam",
    "Witching Well",
    "Aether Spellbomb",
    "Vexing Bauble",
    "Mishra's Bauble",
    "Urza's Bauble",
})
UNTAP_TARGETS = frozenset({"Voltaic Key", "Manifold Key"})
TUTOR_TARGETS = frozenset({"Repurposing Bay", "Codex Shredder"})
PROTECTION_TARGETS = frozenset({
    "Defense Grid",
    "Spellskite",
    "Welding Jar",
    "Hope of Ghirapur",
    "Vexing Bauble",
})
# These are primarily opponent-facing under the current goldfish objective.
# They remain fully legal rules actions and are retained if they are the base
# policy choice or if no strategically richer revealed target dominates them.
OPPONENT_ONLY_TARGETS = frozenset({
    "Pithing Needle",
    "Grafdigger's Cage",
    "Tormod's Crypt",
    "Disruptor Flute",
})

MANA_NOW = {
    "Mana Vault": 3,
    "Grim Monolith": 3,
    "Basalt Monolith": 3,
    "Sol Ring": 2,
    "Lotus Petal": 1,
    "Seat of the Synod": 1,
    "Moonsnare Prototype": 1,
}
CARD_ACCESS = {
    "The One Ring": 4,
    "Uthros Research Craft": 3,
    "The Reality Chip": 3,
    "Sensei's Divining Top": 2,
    "Sewer-veillance Cam": 2,
    "Witching Well": 1,
    "Aether Spellbomb": 1,
    "Vexing Bauble": 1,
    "Mishra's Bauble": 1,
    "Urza's Bauble": 1,
}
PROTECTION_VALUE = {
    # Deliberately strongest: if Grid can be deployed before a win attempt,
    # that is one of the best modeled "protected line" signals available even
    # while the current benchmark is otherwise a goldfish.
    "Defense Grid": 4,
    "Spellskite": 2,
    "Hope of Ghirapur": 2,
    "Welding Jar": 1,
    "Vexing Bauble": 1,
}


@dataclass(frozen=True)
class ArtifactTargetFeature:
    target: str
    role_mask: int
    combo_progress: int
    producer_value: int
    mana_now: int
    card_access: int
    untap_value: int
    tutor_value: int
    protection_value: int
    urza_body_mana: int
    sacrifice_value: int
    goldfish_relevance: int

    def vector(self) -> Tuple[int, ...]:
        return (
            int(self.combo_progress),
            int(self.producer_value),
            int(self.mana_now),
            int(self.card_access),
            int(self.untap_value),
            int(self.tutor_value),
            int(self.protection_value),
            int(self.urza_body_mana),
            int(self.sacrifice_value),
            int(self.goldfish_relevance),
        )


@dataclass(frozen=True)
class ArtifactTargetFrontierResult:
    actions: Tuple[ActionIntent, ...]
    legal_target_count: int
    retained_target_count: int
    dominated_target_count: int
    collapsed_signature_count: int
    retained_targets: Tuple[str, ...]
    dominated_targets: Tuple[str, ...]
    version: str = ARTIFACT_TARGET_FRONTIER_VERSION


def _target_name(action: ActionIntent) -> str:
    return str(dict(action.parameters).get("target", ""))


def _public_names(observation: RuntimePolicyView) -> Tuple[str, ...]:
    return tuple(str(p.name) for p in observation.base.battlefield)


def _artifact_count(observation: RuntimePolicyView) -> int:
    return sum(
        1 for p in observation.base.battlefield
        if str(p.name) in getattr(solver, "ARTIFACTS", frozenset())
        or str(getattr(p, "mode", "")) in {
            "clue", "treasure", "construct", "chrome_copy", "chrome_copy_preturn"
        }
    )


def _has_visible(observation: RuntimePolicyView, card: str) -> bool:
    return bool(
        card in observation.base.hand
        or card in observation.base.graveyard
        or any(str(p.name) == card for p in observation.base.battlefield)
    )


def _has_untap_payoff(observation: RuntimePolicyView) -> bool:
    useful = {
        "Mana Vault",
        "Grim Monolith",
        "Basalt Monolith",
        "The One Ring",
        "Sensei's Divining Top",
        "Sewer-veillance Cam",
        "Uthros Research Craft",
    }
    return any(
        bool(p.tapped) and str(p.name) in useful
        for p in observation.base.battlefield
    )


def _combo_progress(target: str, observation: RuntimePolicyView) -> int:
    score = 1 if target in COMBO_TARGETS else 0
    hand = set(observation.base.hand)
    board = set(_public_names(observation))
    visible = hand | board

    if target in {"Grim Monolith", "Basalt Monolith"} and "Power Artifact" in visible:
        score += 4
    if target == "Sensei's Divining Top" and (
        "The Reality Chip" in visible or observation.base.chip_attached
    ):
        score += 4
    if target == "The Reality Chip" and "Sensei's Divining Top" in visible:
        score += 4
    if target == "Battered Golem" and (
        "Banishing Knack" in hand or "Retraction Helix" in hand
    ):
        score += 4
    if target in {"Grinding Station", "Forensic Gadgeteer"} and (
        "Sensei's Divining Top" in visible
        or "Battered Golem" in visible
        or observation.base.top_access
    ):
        score += 2
    if target == "Sewer-veillance Cam" and any(
        name in visible for name in PRODUCER_TARGETS
    ):
        score += 2
    return score


def _mana_now(target: str, observation: RuntimePolicyView) -> int:
    if target == "Mox Opal":
        # The tutored Opal itself counts toward metalcraft.
        return 1 if _artifact_count(observation) + 1 >= 3 else 0
    if target == "Chrome Mox":
        blue_nonartifact = getattr(solver, "BLUE_NONARTIFACT_FRONT", frozenset())
        return 1 if any(card in blue_nonartifact for card in observation.base.hand) else 0
    if target == "Mox Diamond":
        lands = getattr(solver, "ALL_LANDS", frozenset())
        return 1 if any(card in lands for card in observation.base.hand) else 0
    if target == "Sapphire Medallion":
        # Effective future blue-spell mana, not literal floating mana.
        return 1
    if target == "Prized Statue":
        return 1
    return int(MANA_NOW.get(target, 0))


def _role_mask(target: str) -> int:
    mask = ROLE_GENERIC_BODY
    if target in COMBO_TARGETS:
        mask |= ROLE_COMBO
    if target in PRODUCER_TARGETS:
        mask |= ROLE_PRODUCER
    if target in MANA_NOW or target in {
        "Mox Opal", "Chrome Mox", "Mox Diamond", "Sapphire Medallion", "Prized Statue"
    }:
        mask |= ROLE_MANA
    if target in VALUE_TARGETS:
        mask |= ROLE_VALUE
    if target in UNTAP_TARGETS:
        mask |= ROLE_UNTAP
    if target in TUTOR_TARGETS:
        mask |= ROLE_TUTOR
    if target in PROTECTION_TARGETS:
        mask |= ROLE_PROTECTION
    if CARD_ACCESS.get(target, 0):
        mask |= ROLE_DRAW
    if target in OPPONENT_ONLY_TARGETS:
        mask |= ROLE_OPPONENT_ONLY
    return mask


def target_feature(
    target: str,
    observation: RuntimePolicyView,
) -> ArtifactTargetFeature:
    board = set(_public_names(observation))
    hand = set(observation.base.hand)
    transmute_or_bay = bool(
        "Transmute Artifact" in hand
        or "Repurposing Bay" in hand
        or "Repurposing Bay" in board
    )
    untap = 0
    if target in UNTAP_TARGETS:
        untap = 2 if _has_untap_payoff(observation) else 0

    return ArtifactTargetFeature(
        target=target,
        role_mask=_role_mask(target),
        combo_progress=_combo_progress(target, observation),
        producer_value=1 if target in PRODUCER_TARGETS else 0,
        mana_now=_mana_now(target, observation),
        card_access=int(CARD_ACCESS.get(target, 0)),
        untap_value=int(untap),
        tutor_value=2 if target == "Repurposing Bay" else (1 if target in TUTOR_TARGETS else 0),
        protection_value=int(PROTECTION_VALUE.get(target, 0)),
        urza_body_mana=1 if observation.base.urza else 0,
        sacrifice_value=(
            int(solver.mana_value(target))
            if transmute_or_bay
            else 0
        ),
        goldfish_relevance=0 if target in OPPONENT_ONLY_TARGETS else 1,
    )


def dominates(a: ArtifactTargetFeature, b: ArtifactTargetFeature) -> bool:
    av = a.vector()
    bv = b.vector()
    return all(x >= y for x, y in zip(av, bv)) and any(
        x > y for x, y in zip(av, bv)
    )


def whir_target_frontier(
    observation: RuntimePolicyView,
    actions: Iterable[ActionIntent],
    *,
    objective: str = "win_by_horizon",
    must_retain: Iterable[ActionIntent] = (),
) -> ArtifactTargetFrontierResult:
    actions = tuple(actions)
    if str(objective) != "win_by_horizon":
        targets = tuple(sorted(_target_name(a) for a in actions if _target_name(a)))
        return ArtifactTargetFrontierResult(
            actions=actions,
            legal_target_count=len(targets),
            retained_target_count=len(targets),
            dominated_target_count=0,
            collapsed_signature_count=0,
            retained_targets=targets,
            dominated_targets=(),
        )

    target_actions = tuple(
        a for a in actions
        if str(a.kind) == "x_artifact_search_target"
        and str(getattr(a, "source", "")) == "Whir of Invention"
    )
    if len(target_actions) < 2:
        targets = tuple(sorted(_target_name(a) for a in target_actions if _target_name(a)))
        return ArtifactTargetFrontierResult(
            actions=actions,
            legal_target_count=len(targets),
            retained_target_count=len(targets),
            dominated_target_count=0,
            collapsed_signature_count=0,
            retained_targets=targets,
            dominated_targets=(),
        )

    keep_keys = {a.strategic_key() for a in must_retain}
    fail_actions = tuple(a for a in target_actions if not _target_name(a))
    card_actions = tuple(a for a in target_actions if _target_name(a))
    features = {a.strategic_key(): target_feature(_target_name(a), observation) for a in card_actions}

    dominated = set()
    for candidate in card_actions:
        ckey = candidate.strategic_key()
        if ckey in keep_keys or _target_name(candidate) == "Defense Grid":
            continue
        cf = features[ckey]
        for other in card_actions:
            okey = other.strategic_key()
            if okey == ckey:
                continue
            if dominates(features[okey], cf):
                dominated.add(ckey)
                break

    survivors = [
        a for a in card_actions
        if a.strategic_key() not in dominated
        or a.strategic_key() in keep_keys
        or _target_name(a) == "Defense Grid"
    ]

    # Collapse identical modeled feature signatures to one deterministic
    # representative, while retaining the rollout-v6/base action.  This is the
    # second, explicitly objective-specific compression layer.
    by_signature = {}
    collapsed = 0
    for action in sorted(survivors, key=lambda a: a.action_id):
        key = action.strategic_key()
        if key in keep_keys:
            continue
        sig = features[key].vector()
        if sig in by_signature:
            collapsed += 1
            continue
        by_signature[sig] = action

    retained_keys = set(keep_keys)
    retained_keys.update(a.strategic_key() for a in by_signature.values())
    # Defense Grid is always a protected-line representative when revealed.
    retained_keys.update(
        a.strategic_key() for a in survivors
        if _target_name(a) == "Defense Grid"
    )

    retained_target_actions = tuple(
        a for a in target_actions
        if not _target_name(a) or a.strategic_key() in retained_keys
    )
    other_actions = tuple(a for a in actions if a not in target_actions)
    final = tuple(sorted(other_actions + retained_target_actions, key=lambda a: a.action_id))

    # Never collapse the request to zero actions.
    if not final:
        final = actions

    retained_targets = tuple(sorted(
        _target_name(a) for a in retained_target_actions if _target_name(a)
    ))
    dominated_targets = tuple(sorted(
        _target_name(a) for a in card_actions
        if a.strategic_key() not in {x.strategic_key() for x in retained_target_actions}
    ))
    return ArtifactTargetFrontierResult(
        actions=final,
        legal_target_count=len(card_actions),
        retained_target_count=len(retained_targets),
        dominated_target_count=len(dominated),
        collapsed_signature_count=int(collapsed),
        retained_targets=retained_targets,
        dominated_targets=dominated_targets,
    )
