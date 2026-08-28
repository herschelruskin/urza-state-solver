#!/usr/bin/env python3
"""Diagnostic-only Hand-12 Q nesting/RSS trace.

No policy/rules semantics are changed. The wrapper records evaluator nesting,
candidate kinds, cache size, and current RSS so an OOM can be tied to a precise
nested Q call.
"""

from __future__ import annotations

import itertools
import os
import sys

import phase5_monte_carlo as mc


def rss_mb():
    try:
        for line in open("/proc/self/status",encoding="utf-8"):
            if line.startswith("VmRSS:"):
                return int(line.split()[1])/1024.0
    except OSError:
        pass
    return -1.0


_original=mc.Phase5MonteCarloDecisionEvaluator.evaluate
_counter=itertools.count(1)
_depth=0


def traced_evaluate(self,runtime,*,candidate_actions=None):
    global _depth
    call_id=next(_counter)
    depth=_depth
    _depth+=1
    actions=tuple(candidate_actions or ())
    kinds=tuple(str(a.kind) for a in actions)
    cache_len=len(self.cache) if self.cache is not None else 0
    before=rss_mb()
    print(
        "QTRACE_ENTER "
        f"id={call_id} depth={depth} rss_mb={before:.1f} "
        f"turn={runtime.true_state.turn} namespace={self.sample_namespace!r} "
        f"rollouts={self.rollout_count} cache={cache_len} "
        f"candidate_kinds={kinds!r}",
        flush=True,
    )
    try:
        result=_original(self,runtime,candidate_actions=candidate_actions)
        after=rss_mb()
        print(
            "QTRACE_EXIT "
            f"id={call_id} depth={depth} rss_mb={after:.1f} "
            f"delta_mb={after-before:.1f} cache="
            f"{len(self.cache) if self.cache is not None else 0} "
            f"best_kind={result.best_action.kind!r}",
            flush=True,
        )
        return result
    except BaseException as exc:
        print(
            "QTRACE_ERROR "
            f"id={call_id} depth={depth} rss_mb={rss_mb():.1f} "
            f"type={type(exc).__name__} msg={str(exc)[:300]!r}",
            flush=True,
        )
        raise
    finally:
        _depth-=1


mc.Phase5MonteCarloDecisionEvaluator.evaluate=traced_evaluate

import phase5i_hand12_world_eval as hand12


if __name__=="__main__":
    sys.argv=[sys.argv[0],"--sample-id","0"]
    hand12.main()
