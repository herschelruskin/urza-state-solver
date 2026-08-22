#!/usr/bin/env python3
"""Auditable State/Perm classification for future V(s)/Q(s,a) keys.

This module changes no Magic rules or Oracle search behavior.  It is the executable
field-by-field contract for three distinct identities:

1. replay/diagnostic identity: conservative full state plus provenance;
2. concrete Markov transition identity: exact sampled world, including RNG root;
3. strategic expected-value identity: seed-independent sufficient state for the
   selected objective and a legal-information policy.

The strategic identity is not obtained by merely deleting history fields.  In
particular, exact unknown library order must be replaced by a belief/information
projection rather than retained as clairvoyant state or simply discarded.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Dict, Mapping, Tuple

from solver_architecture import PolicyView, PublicPermanent
from urza_solver import Perm, State

# Base scalar objective treatment: V_win_by_horizon(s).
RETAIN = "retain"
EXCLUDE = "exclude"
REPLACE_WITH_BELIEF = "replace_with_belief"
OBJECTIVE_AUGMENT = "objective_augment"

# Policy visibility labels.
PUBLIC = "public"
ENGINE_DERIVED = "engine_derived"
HIDDEN_TRUE = "hidden_true"
HIDDEN_SIMULATOR = "hidden_simulator"
TERMINAL_ONLY = "terminal_only"
ANALYTICS_ONLY = "analytics_only"
RUNTIME_ONLY = "runtime_only"


@dataclass(frozen=True)
class FieldAudit:
    transition_role: str
    randomness_role: str
    policy_visibility: str
    win_by_horizon_value_key: str
    reason: str


# Every State field MUST appear exactly once here.  If a field can alter legality,
# resources, a pending trigger, a future observation/chance distribution, or
# terminal reward, the default is RETAIN until equivalence is demonstrated.
STATE_FIELD_AUDIT: Mapping[str, FieldAudit] = {
    "turn": FieldAudit("rules+horizon", "state_coordinate", PUBLIC, RETAIN,
        "Controls turn sequencing and remaining horizon/reward."),
    "library": FieldAudit("hidden-zone future", "hidden_order+chance_source", HIDDEN_TRUE, REPLACE_WITH_BELIEF,
        "Concrete/Oracle state needs exact order; non-Oracle expected value must use remaining composition plus InformationState known-top/bottom constraints."),
    "hand": FieldAudit("rules+resources", "state_coordinate", PUBLIC, RETAIN,
        "Current casts, lands, imprint/pitch choices, tutors and protection depend on the hand multiset."),
    "battlefield": FieldAudit("rules+resources", "state_coordinate", PUBLIC, RETAIN,
        "Permanent identities and future-relevant attributes determine mana, abilities, triggers, combo legality and protection."),
    "graveyard": FieldAudit("rules+resources", "state_coordinate", PUBLIC, RETAIN,
        "Scour/Codex and threshold effects depend on graveyard contents; order is not modeled as relevant."),
    "exile": FieldAudit("zone accounting", "state_coordinate", PUBLIC, RETAIN,
        "Exiled cards remain unavailable; order is not modeled as relevant."),
    "urza_exile_permissions": FieldAudit("temporary play permission", "state_coordinate", PUBLIC, RETAIN,
        "Urza's {5} ability grants until-end-of-turn permission to play specific exiled card(s); multiplicity changes future legal actions."),
    "blue": FieldAudit("mana resource", "state_coordinate", PUBLIC, RETAIN,
        "Colored payment legality and protection depend on floating blue."),
    "colorless": FieldAudit("mana resource", "state_coordinate", PUBLIC, RETAIN,
        "Generic payment and combo lines depend on floating colorless."),
    "land_played": FieldAudit("turn legality", "state_coordinate", PUBLIC, RETAIN,
        "Controls whether another land may be played this turn."),
    "drain_bank": FieldAudit("delayed resource", "state_coordinate", PUBLIC, RETAIN,
        "Modeled Mana Drain delayed mana changes a future turn's resources."),
    "bauble_draws": FieldAudit("delayed draw", "state_coordinate", PUBLIC, RETAIN,
        "Pending Bauble draws alter future hand/library state."),
    "remora_age": FieldAudit("upkeep cost", "state_coordinate", PUBLIC, RETAIN,
        "Mystic Remora cumulative upkeep depends on current age."),
    "remora_upkeep_pending": FieldAudit("pending trigger/phase", "state_coordinate", PUBLIC, RETAIN,
        "Changes which actions/choices are legal before the normal main phase."),
    "saga3_pending": FieldAudit("pending trigger/phase", "state_coordinate", PUBLIC, RETAIN,
        "Saga III remains resolvable independently of the Saga permanent once triggered."),
    "ring_counters": FieldAudit("draw engine state", "state_coordinate", PUBLIC, RETAIN,
        "The One Ring draw quantity depends on its accumulated modeled counter state."),
    "ftt_level": FieldAudit("engine level", "state_coordinate", PUBLIC, RETAIN,
        "Fortune Teller's Talent level changes top access and cost reduction."),
    "uthros_counters": FieldAudit("engine counter", "state_coordinate", PUBLIC, RETAIN,
        "Uthros trigger/activation behavior depends on this counter."),
    "urza": FieldAudit("ability availability", "state_coordinate", PUBLIC, RETAIN,
        "The artifact-mana ability and commander-dependent lines read this current flag."),
    "construct": FieldAudit("legacy redundant board flag", "none", PUBLIC, EXCLUDE,
        "Usage audit found writes on Urza casts but no rule/legality reads. The actual Construct token is represented in battlefield, so this compatibility flag must not fragment base V(s). Keep the State field for now; do not use it as strategic identity."),
    "top_access": FieldAudit("legacy unused access flag", "none", PUBLIC, EXCLUDE,
        "Usage audit found no runtime rule reads and no runtime writes beyond state/key machinery. Actual top access is derived from Chip/FTT state, so this compatibility field must not fragment base V(s)."),
    "chip_attached": FieldAudit("engine access", "state_coordinate", PUBLIC, RETAIN,
        "Reality Chip top-cast permission depends on attachment state."),
    "chip_target": FieldAudit("attachment identity", "state_coordinate", PUBLIC, RETAIN,
        "Exact attachment target matters for bounce/removal in the current singleton attachment representation."),
    "spell_cast_this_turn": FieldAudit("turn-history sufficient statistic", "state_coordinate", PUBLIC, RETAIN,
        "FTT level 2 depends on whether a spell has been cast this turn; this is path history compressed into Markov state."),
    "pa_target": FieldAudit("attachment identity", "state_coordinate", PUBLIC, RETAIN,
        "Power Artifact cost modification/combo legality depends on its current target."),
    "vfc_pumps": FieldAudit("current-turn continuous effect", "state_coordinate", PUBLIC, RETAIN,
        "Valley Floodcaller/Assistant power this turn depends on accumulated triggers."),
    "urza_cast_turn": FieldAudit("analytics history", "none", ANALYTICS_ONLY, OBJECTIVE_AUGMENT,
        "Does not change future legality. Preserve as episode output; add only minimal objective memory for Urza-timing objectives."),
    "commander_in_command_zone": FieldAudit("zone legality", "state_coordinate", PUBLIC, RETAIN,
        "Controls command-zone cast availability."),
    "commander_casts_from_zone": FieldAudit("commander tax", "state_coordinate", PUBLIC, RETAIN,
        "Determines future command-zone generic tax."),
    "interaction_seen": FieldAudit("analytics history", "none", ANALYTICS_ONLY, OBJECTIVE_AUGMENT,
        "Historical exposure is valuable research output but does not alter base game legality. Path-dependent interaction objectives should add only a sufficient summary."),
    "won": FieldAudit("terminal status", "none", TERMINAL_ONLY, RETAIN,
        "Terminal wins must remain distinguishable from live states unless callers always short-circuit before key construction."),
    "win_family": FieldAudit("terminal analytics", "none", TERMINAL_ONLY, OBJECTIVE_AUGMENT,
        "Not required for scalar P(win by horizon); preserve as outcome/category for family-specific objectives."),
    "rng_root_seed": FieldAudit("concrete random tape", "root_random_tape", HIDDEN_SIMULATOR, EXCLUDE,
        "Required for deterministic concrete replay/transitions, but expected value must merge identical strategic states across Monte-Carlo seeds."),
    "trace": FieldAudit("replay provenance", "none", ANALYTICS_ONLY, EXCLUDE,
        "Replay/debug text must never fragment transpositions or expected value."),
}


PERM_FIELD_AUDIT: Mapping[str, FieldAudit] = {
    "name": FieldAudit("permanent identity", "state_coordinate", PUBLIC, RETAIN,
        "Card/token identity determines types, mana, abilities, triggers and targets."),
    "tapped": FieldAudit("activation/mana legality", "state_coordinate", PUBLIC, RETAIN,
        "Tap status changes available mana and activated abilities."),
    "sick": FieldAudit("tap-symbol legality", "state_coordinate", PUBLIC, RETAIN,
        "Summoning sickness changes creature tap-ability legality."),
    "counters": FieldAudit("permanent counters", "state_coordinate", PUBLIC, RETAIN,
        "Saga/loyalty/Skerry/Chalice and other modeled behavior depends on counters."),
    "mode": FieldAudit("face/token/copy mode", "state_coordinate", PUBLIC, RETAIN,
        "Distinguishes land faces, tokens, copies, attached forms and other rules-relevant modes."),
    "knack_granted": FieldAudit("temporary granted ability", "state_coordinate", PUBLIC, RETAIN,
        "Exact creature grant changes which permanent may activate Knack/Helix."),
    "knack_source": FieldAudit("provenance label", "none", ANALYTICS_ONLY, EXCLUDE,
        "Knack and Helix grant the same modeled ability; source identity is provenance only."),
    "producer_urza_ready": FieldAudit("compression resource", "state_coordinate", ENGINE_DERIVED, RETAIN,
        "Represents still-refundable producer +U and changes which strategically distinct native/Knack tap remains available."),
    "instance_tag": FieldAudit("macro runtime identity", "none", RUNTIME_ONLY, EXCLUDE,
        "Ephemeral object identity is only for multi-step macro execution."),
}


POLICY_DIRECT_VISIBILITY = frozenset(
    name for name, audit in STATE_FIELD_AUDIT.items()
    if audit.policy_visibility in {PUBLIC, ENGINE_DERIVED}
)
PERM_PUBLIC_VISIBILITY = frozenset(
    name for name, audit in PERM_FIELD_AUDIT.items()
    if audit.policy_visibility in {PUBLIC, ENGINE_DERIVED}
)


@dataclass(frozen=True)
class UsageSignal:
    attribute_mentions: int = 0
    keyword_mentions: int = 0

    @property
    def total(self) -> int:
        return self.attribute_mentions + self.keyword_mentions


def declared_field_names(cls) -> Tuple[str, ...]:
    return tuple(f.name for f in fields(cls))


def validate_audit_tables() -> None:
    state_declared = set(declared_field_names(State))
    state_audited = set(STATE_FIELD_AUDIT)
    if state_declared != state_audited:
        raise AssertionError(
            "State audit mismatch missing=" + str(sorted(state_declared - state_audited))
            + " extra=" + str(sorted(state_audited - state_declared))
        )
    perm_declared = set(declared_field_names(Perm))
    perm_audited = set(PERM_FIELD_AUDIT)
    if perm_declared != perm_audited:
        raise AssertionError(
            "Perm audit mismatch missing=" + str(sorted(perm_declared - perm_audited))
            + " extra=" + str(sorted(perm_audited - perm_declared))
        )


def validate_policy_projection_contract() -> None:
    policy_fields = set(declared_field_names(PolicyView))
    information_only = {"known_top", "known_bottom", "known_library_counts", "caverns_live"}
    direct = policy_fields - information_only
    if direct != set(POLICY_DIRECT_VISIBILITY):
        raise AssertionError(
            "PolicyView projection mismatch missing=" + str(sorted(set(POLICY_DIRECT_VISIBILITY) - direct))
            + " extra=" + str(sorted(direct - set(POLICY_DIRECT_VISIBILITY)))
        )
    public_perm_fields = set(declared_field_names(PublicPermanent))
    if public_perm_fields != set(PERM_PUBLIC_VISIBILITY):
        raise AssertionError(
            "PublicPermanent projection mismatch missing=" + str(sorted(set(PERM_PUBLIC_VISIBILITY) - public_perm_fields))
            + " extra=" + str(sorted(public_perm_fields - set(PERM_PUBLIC_VISIBILITY)))
        )


def source_usage_signals(path: Path | None = None) -> Dict[str, UsageSignal]:
    """Lightweight AST evidence for human semantic review.

    Attribute mentions include reads in rules code and reads inside state/key helper
    code; keyword mentions include constructor/replace writes.  Counts are evidence,
    not proof.  The focused post-report audit established the two base-value
    redundancies (`construct`, `top_access`) by tracing their actual occurrences.
    """
    if path is None:
        path = Path(__file__).resolve().with_name("urza_solver.py")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = set(STATE_FIELD_AUDIT) | set(PERM_FIELD_AUDIT)
    attr: Dict[str, int] = {name: 0 for name in names}
    kw: Dict[str, int] = {name: 0 for name in names}
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in attr:
            attr[node.attr] += 1
        elif isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg in kw:
                    kw[keyword.arg] += 1
    return {name: UsageSignal(attr[name], kw[name]) for name in sorted(names)}


def suspicious_zero_usage_fields(signals: Mapping[str, UsageSignal]) -> Tuple[str, ...]:
    return tuple(sorted(name for name, sig in signals.items() if sig.total == 0))


def base_win_value_exclusions() -> Tuple[str, ...]:
    return tuple(sorted(
        name for name, audit in STATE_FIELD_AUDIT.items()
        if audit.win_by_horizon_value_key == EXCLUDE
    ))


def base_win_value_objective_augments() -> Tuple[str, ...]:
    return tuple(sorted(
        name for name, audit in STATE_FIELD_AUDIT.items()
        if audit.win_by_horizon_value_key == OBJECTIVE_AUGMENT
    ))


def base_win_value_retained() -> Tuple[str, ...]:
    return tuple(sorted(
        name for name, audit in STATE_FIELD_AUDIT.items()
        if audit.win_by_horizon_value_key == RETAIN
    ))


def main() -> None:
    validate_audit_tables()
    validate_policy_projection_contract()
    signals = source_usage_signals()
    print("STATE / PERM FIELD AUDIT: STRUCTURAL VALIDATION PASS")
    print(f"State fields: {len(STATE_FIELD_AUDIT)} Perm fields: {len(PERM_FIELD_AUDIT)}")
    print("Base win-value exclusions:", ", ".join(base_win_value_exclusions()))
    print("Objective-specific history/terminal fields:", ", ".join(base_win_value_objective_augments()))
    print("Library treatment: replace exact unknown order with belief/information state")
    print("Static source zero-usage signals:", ", ".join(suspicious_zero_usage_fields(signals)) or "none")
    print("\nUsage signals (attribute, keyword):")
    for name, sig in signals.items():
        print(f"  {name:30s} {sig.attribute_mentions:4d} {sig.keyword_mentions:4d}")


if __name__ == "__main__":
    main()
