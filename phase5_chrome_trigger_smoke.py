#!/usr/bin/env python3
"""Regression for a Chrome Mox imprint trigger whose source has left play."""

import urza_solver as solver
from decision_observation import DECISION_MECHANICAL, PendingDecisionSpec
from non_oracle_rules_adapter_v2 import apply_main_action, rules_decision_request
from non_oracle_runtime import (
    DECISION_CHROME_IMPRINT,
    STACK_TRIGGER,
    NonOracleRuntimeState,
    RuntimePendingDecision,
    RuntimeStack,
)
from non_oracle_runtime_value_key import RuntimeDecisionWindow, WINDOW_POST_OBSERVATION
from solver_architecture import InformationState


def test_source_absent_chrome_trigger_forces_no_imprint():
    obj, stack = RuntimeStack().allocate(
        object_type=STACK_TRIGGER,
        kind="chrome_imprint",
        source="Chrome Mox",
        card="Chrome Mox",
        payload=(("source_tag", 77),),
        public_payload=(),
        strategic_payload=(),
    )
    # The ETB trigger exists, but the exact Chrome Mox permanent tagged 77 has
    # already left the battlefield. A blue nonartifact remains in hand so the old
    # Phase-2 request would incorrectly offer an imprint choice and then crash.
    runtime = NonOracleRuntimeState(
        true_state=solver.State(
            turn=3,
            library=(),
            hand=("Power Artifact",),
            battlefield=(solver.Perm("Island", instance_tag=1),),
        ),
        information=InformationState(),
        stack=RuntimeStack((), stack.next_sequence),
        pending=RuntimePendingDecision(
            spec=PendingDecisionSpec(
                decision_id="source-absent.chrome",
                kind=DECISION_CHROME_IMPRINT,
                source="Chrome Mox",
                decision_stage=DECISION_MECHANICAL,
                contingent_on=obj.object_id,
            ),
            kind=DECISION_CHROME_IMPRINT,
            payload=(("object", obj),),
        ),
        window=RuntimeDecisionWindow(WINDOW_POST_OBSERVATION),
    )
    request = rules_decision_request(runtime, horizon=6, policy_id="chrome-source-smoke")
    assert len(request.actions) == 1
    action = request.actions[0]
    assert action.kind == DECISION_CHROME_IMPRINT
    assert dict(action.parameters).get("card") == ""

    after = apply_main_action(runtime, action)
    assert after.pending is None
    assert after.true_state.hand == ("Power Artifact",)
    assert after.true_state.exile == ()
    assert any("Chrome Mox no imprint" in line for line in after.true_state.trace)
    print("source-absent Chrome imprint trigger -> legal no-imprint: PASS")


def main():
    test_source_absent_chrome_trigger_forces_no_imprint()
    print("PHASE5 CHROME TRIGGER SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
