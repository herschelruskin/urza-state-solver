#!/usr/bin/env python3
"""Umbrella Phase-1 decision/observation acceptance gate.

This runner intentionally composes the focused adapter/architecture smokes rather
than duplicating their assertions.  It is the information-boundary gate; the
repository's existing Oracle regression plan remains a separate required gate.

Run:
    py -3 phase1_acceptance_smoke.py
"""

import architecture_smoke
import continuous_top_visibility_smoke
import decision_observation_smoke
import information_state_propagation_smoke
import non_oracle_runtime_value_key_smoke
import non_oracle_runtime_view_smoke
import opening_information_state_smoke
import phase1_state_fixture_audit_smoke
import random_observation_adapters_smoke
import remaining_search_adapters_smoke
import scry_decision_adapter_smoke
import state_field_audit_smoke
import strategic_value_state_smoke
import top_decision_adapter_smoke
import transmute_artifact_adapter_smoke
import trigger_order_adapter_smoke
import tutor_decision_adapter_smoke
import urza_permission_adapter_smoke
import urza_permission_timing_smoke
import x_artifact_search_adapter_smoke


def main():
    suites = (
        ("state_fixture_audit", phase1_state_fixture_audit_smoke.main),
        ("decision_observation", decision_observation_smoke.main),
        ("top", top_decision_adapter_smoke.main),
        ("scry", scry_decision_adapter_smoke.main),
        ("simple_tutors", tutor_decision_adapter_smoke.main),
        ("transmute_artifact", transmute_artifact_adapter_smoke.main),
        ("reshape_whir", x_artifact_search_adapter_smoke.main),
        ("remaining_searches", remaining_search_adapters_smoke.main),
        ("coliseum_random_observation", random_observation_adapters_smoke.main),
        ("urza_permissions", urza_permission_adapter_smoke.main),
        ("urza_permission_timing", urza_permission_timing_smoke.main),
        ("trigger_order", trigger_order_adapter_smoke.main),
        ("continuous_top_visibility", continuous_top_visibility_smoke.main),
        ("information_propagation", information_state_propagation_smoke.main),
        ("opening_information", opening_information_state_smoke.main),
        ("strategic_value_state", strategic_value_state_smoke.main),
        ("runtime_value_key", non_oracle_runtime_value_key_smoke.main),
        ("runtime_policy_view", non_oracle_runtime_view_smoke.main),
        ("state_field_audit", state_field_audit_smoke.main),
        ("architecture", architecture_smoke.main),
    )
    for name, run in suites:
        print(f"\n=== PHASE 1 SUITE: {name} ===")
        run()
    print("\nPHASE 1 DECISION / OBSERVATION ACCEPTANCE: ALL PASS")


if __name__ == "__main__":
    main()
