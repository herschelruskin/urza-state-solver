#!/usr/bin/env python3
"""Phase-5 policy-safe metadata for Transmute Artifact target commitment.

The Phase-2 Transmute runtime correctly separates target selection from the later
optional difference payment.  A deterministic policy, however, was scoring the
revealed target without knowing the public payment consequence of that choice.  It
could therefore choose The One Ring after sacrificing a zero-MV Construct and then
immediately decline {4}, intentionally sending the tutored card to the graveyard.

After Transmute's search has resolved, all artifact targets are legally revealed and
the sacrificed permanent/MV plus current mana sources are public.  The rules layer
may therefore derive, for each target action:

* target mana value;
* required difference;
* whether at least one legal payment plan exists;
* the shortest currently modeled payment plan.

These are deterministic public consequences, not hidden-world information.  The
extra fields are policy annotations only: before execution they are stripped back
to the original Phase-2 target ActionIntent so the frozen runtime remains the rules
authority and its canonical legality checks stay unchanged.
"""

from __future__ import annotations

from dataclasses import replace

import urza_solver as solver
from decision_observation import ActionIntent, DecisionRequest
from non_oracle_transmute_runtime import RUNTIME_TRANSMUTE_TARGET
from transmute_artifact_adapter import transmute_difference_payment_options

ANNOTATION_FIELDS = frozenset({
    "sacrificed_mv",
    "target_mv",
    "difference",
    "can_pay_difference",
    "min_payment_steps",
})


def handles_transmute_target_request(runtime) -> bool:
    return bool(runtime.pending is not None and runtime.pending.kind == RUNTIME_TRANSMUTE_TARGET)


def _annotate_action(runtime, action: ActionIntent) -> ActionIntent:
    if action.kind != "transmute_choose_target":
        return action
    params = dict(action.parameters)
    target = str(params.get("target", ""))
    sacrificed_mv = int(dict(runtime.pending.payload).get("sacrificed_mv", 0))

    if not target:
        extras = (
            ("can_pay_difference", True),
            ("difference", 0),
            ("min_payment_steps", 0),
            ("sacrificed_mv", sacrificed_mv),
            ("target_mv", -1),
        )
        return replace(action, parameters=tuple(action.parameters) + extras)

    if target not in runtime.true_state.library:
        raise ValueError("revealed Transmute target disappeared before annotation")
    target_mv = int(solver.mana_value(target))
    difference = max(0, target_mv - sacrificed_mv)

    if difference <= 0:
        can_pay = True
        min_steps = 0
    else:
        # Transmute removes the chosen card from the library before the payment
        # window.  Reproduce that physical state while deriving public payment
        # feasibility; the target itself cannot become a mana source for its cost.
        library = list(runtime.true_state.library)
        library.remove(target)
        state_without_target = replace(runtime.true_state, library=tuple(library))
        options = transmute_difference_payment_options(state_without_target, difference)
        can_pay = bool(options)
        min_steps = min(
            (len(tuple(dict(candidate.parameters).get("mana_steps", ()))) for candidate, _ in options),
            default=-1,
        )

    extras = (
        ("can_pay_difference", bool(can_pay)),
        ("difference", int(difference)),
        ("min_payment_steps", int(min_steps)),
        ("sacrificed_mv", int(sacrificed_mv)),
        ("target_mv", int(target_mv)),
    )
    return replace(action, parameters=tuple(action.parameters) + extras)


def annotate_transmute_target_request(runtime, request: DecisionRequest) -> DecisionRequest:
    if not handles_transmute_target_request(runtime):
        return request
    return DecisionRequest(
        observation=request.observation,
        actions=tuple(_annotate_action(runtime, action) for action in request.actions),
        context=request.context,
    )


def strip_transmute_target_annotations(action: ActionIntent) -> ActionIntent:
    if action.kind != "transmute_choose_target":
        return action
    params = tuple((key, value) for key, value in action.parameters if key not in ANNOTATION_FIELDS)
    if params == action.parameters:
        return action
    return replace(action, parameters=params)
