#!/usr/bin/env python3
"""Phase-5 legality normalization for source-absent Chrome Mox imprint triggers.

A Chrome Mox imprint trigger on the stack exists independently of its source.  If
Chrome Mox leaves the battlefield before that trigger resolves, the trigger still
resolves, but the Oracle correctly retains only its no-imprint branch: candidate
imprint branches cannot find the tagged Chrome Mox to mark as imprinted.

The Phase-2 pending-decision generator previously exposed hand-card imprint choices
even after the source had disappeared, and execution then raised an exception after
exiling the selected card.  This adapter mirrors the Oracle at the policy boundary:
when the exact source tag is absent/changed, only the already-supported no-imprint
action remains legal.  No hidden information is involved.
"""

from __future__ import annotations

from decision_observation import DecisionRequest
from non_oracle_runtime import DECISION_CHROME_IMPRINT, _perm_index_for_tag


def handles_chrome_imprint_request(runtime) -> bool:
    return bool(runtime.pending is not None and runtime.pending.kind == DECISION_CHROME_IMPRINT)


def chrome_source_is_live(runtime) -> bool:
    if not handles_chrome_imprint_request(runtime):
        return True
    obj = dict(runtime.pending.payload).get("object")
    if obj is None:
        return False
    tag = int(dict(obj.payload).get("source_tag", 0))
    idx = _perm_index_for_tag(runtime.true_state, tag)
    if idx is None:
        return False
    perm = runtime.true_state.battlefield[idx]
    return bool(perm.name == "Chrome Mox" and perm.mode != "imprinted")


def normalize_chrome_imprint_request(runtime, request: DecisionRequest) -> DecisionRequest:
    if not handles_chrome_imprint_request(runtime) or chrome_source_is_live(runtime):
        return request
    legal = tuple(
        action for action in request.actions
        if action.kind == DECISION_CHROME_IMPRINT
        and not str(dict(action.parameters).get("card", ""))
    )
    if len(legal) != 1:
        raise AssertionError("source-absent Chrome imprint must retain exactly one no-imprint action")
    return DecisionRequest(
        observation=request.observation,
        actions=legal,
        context=request.context,
    )
