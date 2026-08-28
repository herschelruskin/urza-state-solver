#!/usr/bin/env python3
"""Diagnostic Hand-12 action-fanout trace for symbolic action-space validation."""

from __future__ import annotations

from collections import Counter

import non_oracle_rules_adapter_v2 as rules
import non_oracle_episode as episode
import phase5_selective_tutor_q as tutor_q
import phase5_monte_carlo as mc

_original_request=rules.rules_decision_request
max_actions=0
max_kinds=()


def traced_request(*args,**kwargs):
    global max_actions,max_kinds
    request=_original_request(*args,**kwargs)
    n=len(request.actions)
    if n>max_actions:
        max_actions=n
        kinds=Counter(str(action.kind) for action in request.actions)
        max_kinds=tuple(sorted(kinds.items()))
        print(
            "FANOUT_NEW_MAX "
            f"actions={n} kinds={max_kinds!r}",
            flush=True,
        )
    if n>=100:
        kinds=Counter(str(action.kind) for action in request.actions)
        print(
            "FANOUT_LARGE "
            f"actions={n} kinds={tuple(sorted(kinds.items()))!r}",
            flush=True,
        )
    return request


rules.rules_decision_request=traced_request
episode.rules_decision_request=traced_request
tutor_q.rules_decision_request=traced_request
mc.rules_decision_request=traced_request

import phase5i_hand12_world_eval as hand12


if __name__=="__main__":
    import sys
    sys.argv=[sys.argv[0],"--sample-id","0"]
    try:
        hand12.main()
    finally:
        print(
            f"FANOUT_SUMMARY max_actions={max_actions} kinds={max_kinds!r}",
            flush=True,
        )
