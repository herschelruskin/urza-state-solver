#!/usr/bin/env python3
"""Focused structural smoke tests for the strategic/value-state field audit."""

from state_field_audit import (
    ANALYTICS_ONLY,
    ENGINE_DERIVED,
    EXCLUDE,
    HIDDEN_SIMULATOR,
    HIDDEN_TRUE,
    OBJECTIVE_AUGMENT,
    PERM_FIELD_AUDIT,
    REPLACE_WITH_BELIEF,
    RETAIN,
    STATE_FIELD_AUDIT,
    source_usage_signals,
    suspicious_zero_usage_fields,
    validate_audit_tables,
    validate_policy_projection_contract,
)


def test_every_declared_field_is_classified():
    validate_audit_tables()


def test_policy_projection_matches_audit():
    validate_policy_projection_contract()


def test_base_win_value_history_is_not_accidentally_keyed():
    assert STATE_FIELD_AUDIT["trace"].win_by_horizon_value_key == EXCLUDE
    assert STATE_FIELD_AUDIT["rng_root_seed"].win_by_horizon_value_key == EXCLUDE
    assert STATE_FIELD_AUDIT["rng_root_seed"].policy_visibility == HIDDEN_SIMULATOR

    # Valuable analytics are preserved, but not allowed to fragment base V(s).
    for name in ("urza_cast_turn", "interaction_seen", "win_family"):
        assert STATE_FIELD_AUDIT[name].win_by_horizon_value_key == OBJECTIVE_AUGMENT

    assert STATE_FIELD_AUDIT["urza_cast_turn"].policy_visibility == ANALYTICS_ONLY
    assert STATE_FIELD_AUDIT["interaction_seen"].policy_visibility == ANALYTICS_ONLY


def test_nonoracle_library_requires_belief_projection():
    audit = STATE_FIELD_AUDIT["library"]
    assert audit.policy_visibility == HIDDEN_TRUE
    assert audit.win_by_horizon_value_key == REPLACE_WITH_BELIEF
    assert "InformationState" in audit.reason


def test_critical_future_legality_fields_are_retained():
    critical = {
        "turn",
        "hand",
        "battlefield",
        "graveyard",
        "exile",
        "blue",
        "colorless",
        "land_played",
        "drain_bank",
        "bauble_draws",
        "remora_age",
        "remora_upkeep_pending",
        "saga3_pending",
        "ring_counters",
        "ftt_level",
        "uthros_counters",
        "urza",
        "construct",
        "top_access",
        "chip_attached",
        "chip_target",
        "spell_cast_this_turn",
        "pa_target",
        "vfc_pumps",
        "commander_in_command_zone",
        "commander_casts_from_zone",
        "won",
    }
    for name in critical:
        assert STATE_FIELD_AUDIT[name].win_by_horizon_value_key == RETAIN, name


def test_perm_identity_keeps_real_resources_not_provenance():
    for name in (
        "name",
        "tapped",
        "sick",
        "counters",
        "mode",
        "knack_granted",
        "producer_urza_ready",
    ):
        assert PERM_FIELD_AUDIT[name].win_by_horizon_value_key == RETAIN, name

    assert PERM_FIELD_AUDIT["producer_urza_ready"].policy_visibility == ENGINE_DERIVED
    assert PERM_FIELD_AUDIT["knack_source"].win_by_horizon_value_key == EXCLUDE
    assert PERM_FIELD_AUDIT["instance_tag"].win_by_horizon_value_key == EXCLUDE


def test_static_usage_scan_runs_and_surfaces_review_signal():
    signals = source_usage_signals()
    # These are unquestionably active in the current rules implementation.
    for name in ("library", "hand", "battlefield", "blue", "turn", "tapped", "mode"):
        assert signals[name].total > 0, name

    # Zero-use fields are allowed only as an informational signal: generic getattr
    # adapters and dataclass iteration are not fully visible to this AST scanner.
    zeros = suspicious_zero_usage_fields(signals)
    assert isinstance(zeros, tuple)


def main():
    tests = [
        test_every_declared_field_is_classified,
        test_policy_projection_matches_audit,
        test_base_win_value_history_is_not_accidentally_keyed,
        test_nonoracle_library_requires_belief_projection,
        test_critical_future_legality_fields_are_retained,
        test_perm_identity_keeps_real_resources_not_provenance,
        test_static_usage_scan_runs_and_surfaces_review_signal,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("STATE FIELD AUDIT SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
