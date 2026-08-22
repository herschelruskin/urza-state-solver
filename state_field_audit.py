#!/usr/bin/env python3
"""Auditable State/Perm classification for future V(s)/Q(s,a) keys.

This module is deliberately descriptive: it does NOT change Oracle rules, State,
Perm, canonical_markov_state_key(), or search behavior.  It records the design
decision for every currently declared solver field and provides validation helpers
so future State/Perm additions cannot silently bypass the strategic-key review.

The central distinction is between three identities:

1. replay / diagnostic identity: conservative full state and provenance;
2. concrete Markov transition identity: exact sampled world, including RNG root;
3. strategic expected-value identity: seed-independent state sufficient for the
   selected objective and legal-information policy.

The third identity is NOT simply State with a few fields deleted.  In particular,
unknown library order must be replaced by a belief/information representation for
non-Oracle policy value rather than retained as clairvoyant state or discarded.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Dict, Iterable, Mapping, Tuple

from solver_architecture import PolicyView, PublicPermanent
from urza_solver import Perm, State

# Recommended treatment in the base scalar objective V_win_by_horizon(s).
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


# Every State field MUST appear exactly once here.  Conservative rule: if a
# current field can alter legality, resources, a pending trigger, a future draw,
# or a terminal decision, retain it until a dedicated proof shows equivalence.
STATE_FIELD_AUDIT: Mapping[str, FieldAudit] = {
    "turn": FieldAudit(
        "rules+horizon", "state_coordinate", PUBLIC, RETAIN,
        "Turn controls untap/upkeep/main sequencing and remaining horizon/reward.",
    ),
    "library": FieldAudit(
        "hidden-zone future", "hidden_order+chance_source", HIDDEN_TRUE, REPLACE_WITH_BELIEF,
        "Concrete/Oracle transitions need exact order, but non-Oracle expected value must use remaining composition plus InformationState known-top/bottom constraints rather than clairvoyant order.",
    ),
    "hand": FieldAudit(
        "rules+resources", "state_coordinate", PUBLIC, RETAIN,
        "Current legal casts, imprint/pitch choices, tutors, lands and protection depend on hand multiset.",
    ),
    "battlefield": FieldAudit(
        "rules+resources", "state_coordinate", PUBLIC, RETAIN,
        "Permanent identities and exact future-relevant permanent attributes determine mana, abilities, triggers, combo legality and protection.",
    ),
    "graveyard": FieldAudit(
        "rules+resources", "state_coordinate", PUBLIC, RETAIN,
        "Scour/Codex and threshold-style effects can use graveyard contents; order is not modeled as relevant.",
    ),
    "exile": FieldAudit(
        "zone accounting", "state_coordinate", PUBLIC, RETAIN,
        "Cards removed from library/hand must remain unavailable; exact ordering is not modeled as relevant.",
    ),
    "blue": FieldAudit(
        "mana resource", "state_coordinate", PUBLIC, RETAIN,
        "Colored payment legality and future protection depend on floating blue.",
    ),
    "colorless": FieldAudit(
        "mana resource", "state_coordinate", PUBLIC, RETAIN,
        "Generic payment and combo lines depend on floating colorless.",
    ),
    "land_played": FieldAudit(
        "turn legality", "state_coordinate", PUBLIC, RETAIN,
        "Controls whether another land may be played this turn, including top-access lands.",
    ),
    "drain_bank": FieldAudit(
        "delayed resource", "state_coordinate", PUBLIC, RETAIN,
        "Mana Drain's modeled delayed mana changes a future turn's resources.",
    ),
    "bauble_draws": FieldAudit(
        "delayed draw", "state_coordinate", PUBLIC, RETAIN,
        "Pending Mishra/Urza Bauble draws alter future hand/library state.",
    ),
    "remora_age": FieldAudit(
        "upkeep cost", "state_coordinate", PUBLIC, RETAIN,
        "Mystic Remora cumulative upkeep amount depends on current age.",
    ),
    "remora_upkeep_pending": FieldAudit(
        "pending trigger/phase", "state_coordinate", PUBLIC, RETAIN,
        "Blocks normal main-phase actions and enables upkeep response/choice sequencing.",
    ),
    "saga3_pending": FieldAudit(
        "pending trigger/phase", "state_coordinate", PUBLIC, RETAIN,
        "Saga III search remains resolvable even if Saga itself changes zones while the trigger is pending.",
    ),
    "ring_counters": FieldAudit(
        "draw engine state", "state_coordinate", PUBLIC, RETAIN,
        "The One Ring draw quantity depends on accumulated counters in the current model.",
    ),
    "ftt_level": FieldAudit(
        "engine level", "state_coordinate", PUBLIC, RETAIN,
        "Fortune Teller's Talent level changes top access and cost reduction.",
    ),
    "uthros_counters": FieldAudit(
        "engine counter", "state_coordinate", PUBLIC, RETAIN,
        "Uthros activation/trigger state and draw behavior depend on this counter.",
    ),
    "urza": FieldAudit(
        "ability availability", "state_coordinate", PUBLIC, RETAIN,
        "Urza's artifact mana ability and commander-dependent lines use this explicit current flag.",
    ),
    "construct": FieldAudit(
        "modeled board state", "state_coordinate", PUBLIC, RETAIN,
        "Currently participates in the solver's board/combo representation; retain until a proof establishes it is fully derivable from battlefield without behavioral change.",
    ),
    "top_access": FieldAudit(
        "engine access", "state_coordinate", PUBLIC, RETAIN,
        "Current solver state may use this access flag; retain conservatively until derivability/usage is proven redundant.",
    ),
    "chip_attached": FieldAudit(
        "engine access", "state_coordinate", PUBLIC, RETAIN,
        "Reality Chip top-cast permission depends on attachment state.",
    ),
    "chip_target": FieldAudit(
        "attachment identity", "state_coordinate", PUBLIC, RETAIN,
        "Exact attachment target matters for bounce/removal and current singleton attachment representation.",
    ),
    "spell_cast_this_turn": FieldAudit(
        "turn history sufficient statistic", "state_coordinate", PUBLIC, RETAIN,
        "FTT level 2 top access depends on whether a spell has been cast this turn; this is path history compressed into a Markov sufficient statistic.",
    ),
    "pa_target": FieldAudit(
        "attachment identity", "state_coordinate", PUBLIC, RETAIN,
        "Power Artifact's cost modification/combo legality depends on its current target.",
    ),
    "vfc_pumps": FieldAudit(
        "current-turn continuous effect", "state_coordinate", PUBLIC, RETAIN,
        "Valley Floodcaller/Assistant power within the turn depends on accumulated cast triggers.",
    ),
    "urza_cast_turn": FieldAudit(
        "analytics history", "none", ANALYTICS_ONLY, OBJECTIVE_AUGMENT,
        "Does not change future legality in the current model. Exclude from base win-by-horizon V key; preserve in episode outcome or augment state only for an objective whose future reward explicitly depends on first Urza cast turn.",
    ),
    "commander_in_command_zone": FieldAudit(
        "zone legality", "state_coordinate", PUBLIC, RETAIN,
        "Controls command-zone cast availability versus hand/battlefield/graveyard routes.",
    ),
    "commander_casts_from_zone": FieldAudit(
        "commander tax", "state_coordinate", PUBLIC, RETAIN,
        "Determines future command-zone generic tax.",
    ),
    "interaction_seen": FieldAudit(
        "analytics history", "none", ANALYTICS_ONLY, OBJECTIVE_AUGMENT,
        "Historical exposure is valuable research output but does not change base game legality. Keep outside base V key; add only the minimal objective-memory statistic for path-dependent objectives such as P(interaction seen by T3).",
    ),
    "won": FieldAudit(
        "terminal status", "none", TERMINAL_ONLY, RETAIN,
        "A scalar win objective must distinguish terminal wins from live states (or terminal-check before keying). Retaining is the conservative representation.",
    ),
    "win_family": FieldAudit(
        "terminal analytics", "none", TERMINAL_ONLY, OBJECTIVE_AUGMENT,
        "Not needed for scalar P(win by horizon); preserve terminal metadata and include/augment only for family-specific objectives or distributions.",
    ),
    "rng_root_seed": FieldAudit(
        "concrete random tape", "root_random_tape", HIDDEN_SIMULATOR, EXCLUDE,
        "Required for deterministic replay/concrete transition identity, but expected strategic value must merge identical strategic states across Monte-Carlo root seeds.",
    ),
    "trace": FieldAudit(
        "replay provenance", "none", ANALYTICS_ONLY, EXCLUDE,
        "Replay/debug text must never fragment transpositions or change expected value.",
    ),
}


PERM_FIELD_AUDIT: Mapping[str, FieldAudit] = {
    "name": FieldAudit(
        "permanent identity", "state_coordinate", PUBLIC, RETAIN,
        "Card/token identity determines types, mana, abilities, triggers and legal targets.",
    ),
    "tapped": FieldAudit(
        "activation/mana legality", "state_coordinate", PUBLIC, RETAIN,
        "Tap status changes available mana and activated abilities.",
    ),
    "sick": FieldAudit(
        "tap-symbol legality", "state_coordinate", PUBLIC, RETAIN,
        "Summoning sickness changes creature tap-ability legality.",
    ),
    "counters": FieldAudit(
        "permanent counters", "state_coordinate", PUBLIC, RETAIN,
        "Saga/loyalty/Skerry/Chalice and other modeled counter behavior depends on this value.",
    ),
    "mode": FieldAudit(
        "face/token/copy mode", "state_coordinate", PUBLIC, RETAIN,
        "Distinguishes land faces, tokens, copies, attached forms and other rules-relevant modes.",
    ),
    "knack_granted": FieldAudit(
        "temporary granted ability", "state_coordinate", PUBLIC, RETAIN,
        "Exact creature grant changes which permanent may activate Knack/Helix this turn.",
    ),
    "knack_source": FieldAudit(
        "provenance label", "none", ANALYTICS_ONLY, EXCLUDE,
        "Banishing Knack and Retraction Helix grant the same modeled ability; source label is trace/pruning provenance only.",
    ),
    "producer_urza_ready": FieldAudit(
        "compression resource", "state_coordinate", ENGINE_DERIVED, RETAIN,
        "Represents an unspent refundable +U tied to a specific producer; changes which strategically distinct native/Knack tap remains available.",
    ),
    "instance_tag": FieldAudit(
        "macro runtime identity", "none", RUNTIME_ONLY, EXCLUDE,
        "Ephemeral object identity is used only while executing multi-step macros and must not fragment canonical strategic state.",
    ),
}


# State fields that should appear directly in PolicyView.  `library` is handled
# through InformationState rather than exact-order exposure.  Terminal/analytics/
# simulator-only fields intentionally do not appear.
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
    """Return lightweight static evidence that each audited field is used.

    Attribute mentions count expressions such as ``s.blue`` or ``p.tapped``.
    Keyword mentions count constructor/``replace`` writes such as ``blue=...``.
    The scanner intentionally does not pretend to prove semantic relevance; it is
    an audit aid for human review and a useful warning when a field appears dead.
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
    """Fields with no source mentions outside declaration warrant manual review.

    This is informational rather than a failure because architecture adapters may
    access fields through getattr() or generic dataclass iteration.
    """
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


def main() -> None:
    validate_audit_tables()
    validate_policy_projection_contract()
    signals = source_usage_signals()

    print("STATE / PERM FIELD AUDIT: STRUCTURAL VALIDATION PASS")
    print("State fields:", len(STATE_FIELD_AUDIT), "Perm fields:", len(PERM_FIELD_AUDIT))
    print("Base win-value exclusions:", ", ".join(base_win_value_exclusions()))
    print("Objective-specific history/terminal fields:", ", ".join(base_win_value_objective_augments()))
    print("Library treatment: replace exact unknown order with belief/information state")

    zeros = suspicious_zero_usage_fields(signals)
    print("Static source zero-usage signals:", ", ".join(zeros) if zeros else "none")
    print("\nUsage signals (attribute, keyword):")
    for name, sig in signals.items():
        print(f"  {name:30s} {sig.attribute_mentions:4d} {sig.keyword_mentions:4d}")


if __name__ == "__main__":
    main()
