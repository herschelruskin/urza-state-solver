#!/usr/bin/env python3
"""Static audit for required urza_solver.State fixture fields in Phase-1 smokes.

This catches mechanical test-construction errors before the semantic suites run.
State currently requires the first four constructor fields:
    turn, library, hand, battlefield
A fixture may provide them positionally or by keyword.
"""

from __future__ import annotations

import ast
from pathlib import Path


REQUIRED_POSITIONAL = ("turn", "library", "hand", "battlefield")

PHASE1_SMOKE_FILES = (
    "decision_observation_smoke.py",
    "top_decision_adapter_smoke.py",
    "scry_decision_adapter_smoke.py",
    "tutor_decision_adapter_smoke.py",
    "transmute_artifact_adapter_smoke.py",
    "x_artifact_search_adapter_smoke.py",
    "remaining_search_adapters_smoke.py",
    "random_observation_adapters_smoke.py",
    "urza_permission_adapter_smoke.py",
    "urza_permission_timing_smoke.py",
    "trigger_order_adapter_smoke.py",
    "continuous_top_visibility_smoke.py",
    "information_state_propagation_smoke.py",
    "opening_information_state_smoke.py",
    "strategic_value_state_smoke.py",
    "non_oracle_runtime_value_key_smoke.py",
    "non_oracle_runtime_view_smoke.py",
    "state_field_audit_smoke.py",
    "architecture_smoke.py",
)


def _is_state_constructor(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Attribute):
        return (
            func.attr == "State"
            and isinstance(func.value, ast.Name)
            and func.value.id in {"solver", "urza_solver"}
        )
    # Support smoke files that may import State directly.
    return isinstance(func, ast.Name) and func.id == "State"


def _missing_required_fields(call: ast.Call):
    # **kwargs can legitimately provide required fields; do not make a false
    # static claim when the call cannot be resolved locally.
    if any(keyword.arg is None for keyword in call.keywords):
        return ()

    keyword_names = {keyword.arg for keyword in call.keywords if keyword.arg is not None}
    supplied_positionally = min(len(call.args), len(REQUIRED_POSITIONAL))
    missing = []
    for index, field in enumerate(REQUIRED_POSITIONAL):
        if index < supplied_positionally:
            continue
        if field not in keyword_names:
            missing.append(field)
    return tuple(missing)


def audit_file(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    failures = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_state_constructor(node):
            continue
        missing = _missing_required_fields(node)
        if missing:
            failures.append((node.lineno, missing))
    return tuple(failures)


def main():
    root = Path(__file__).resolve().parent
    failures = []
    for filename in PHASE1_SMOKE_FILES:
        path = root / filename
        if not path.exists():
            failures.append((filename, 0, ("<missing smoke file>",)))
            continue
        for line, missing in audit_file(path):
            failures.append((filename, line, missing))

    if failures:
        details = "\n".join(
            f"  {filename}:{line}: missing {', '.join(missing)}"
            for filename, line, missing in failures
        )
        raise AssertionError(
            "Phase-1 State fixture audit found incomplete constructor(s):\n" + details
        )

    print(
        "PASS all Phase-1 solver.State fixtures provide turn/library/hand/battlefield"
    )
    print("PHASE 1 STATE FIXTURE AUDIT SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
