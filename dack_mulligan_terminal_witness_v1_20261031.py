#!/usr/bin/env python3
"""Exact, temporary early winning-witness collapse for London future rollouts.

The inherited beam solver scans the entire current frontier even AFTER it
encounters a legal Dack-winning state. In a keep-EV future rollout, the caller
requires only whether a win exists at this turn. Returning the first legal
winning state immediately (without evaluating unrelated siblings or computing
a pass-state reservoir) is provably equivalent for this *existential* query.

The normal full search remains the default everywhere else, especially the
final played-hand search and its frontier diagnostic trace.

Caveat: this preserves the outcome of the existing beam-160/60 solver, NOT
a guarantee of perfect information-set optimal gameplay.
"""
from __future__ import annotations

from contextlib import contextmanager
from collections import Counter
import dack_mulligan_branchbound_v1_20261031 as bounded

d=bounded.d
RULES_VERSION="dack_exact_terminal_witness_mulligan_v1"
_ORIGINAL_SEARCH=d.search_turn_frontier_many
_ORIGINAL_KEEP=d.keep_weighted_ev_seat
_ORIGINAL_PREFIX=bounded._rollout_prefix
counters=Counter()

def search_turn_frontier_win_only(states,beam=6000,depth=24):
    """Original frontier search except return immediately on reachable winner.

    The no-winner path is copied exactly, including the dominance and
    diversity heuristics, frontier ranking, and pass-state reservoir.
    The win path is intentionally allowed to return an empty reservoir
    because ONLY the existential-boolean consumer uses this method.
    """
    kcache={}
    scache={}
    def kf(q):
        oid=id(q)
        got=kcache.get(oid)
        if got is not None and got[0] is q:
            return got[1]
        v=d.key(q)
        kcache[oid]=(q,v)
        return v
    def sf(q):
        oid=id(q)
        got=scache.get(oid)
        if got is not None and got[0] is q:
            return got[1]
        v=d.score(q)
        scache[oid]=(q,v)
        return v

    frontier=d.prune_dominated_frontier_states(list(states))
    seen={kf(q) for q in frontier}
    end_by_key={kf(q):q for q in frontier}
    for _ in range(depth):
        nxt=[]
        for qi,q in enumerate(frontier):
            if d.can_cast_dack(q) and not d.city_trigger_pending(q):
                counters["terminal_witnesses"]+=1
                counters["unexplored_current_frontier"]+=len(frontier)-qi-1
                return [q],[]
            if d.city_trigger_pending(q):
                resp_special=[
                    a for a in d.special_actions(q)
                    if a.hand==q.hand and a.library==q.library
                    and len(a.battlefield)==len(q.battlefield)
                ]
                acts=(d.tap_mana_actions(q)+d.utility_actions(q)+resp_special+
                      d.nasty_mana_actions(q)+d.resolve_city_trigger_actions(q))
            else:
                kq=kf(q)
                prev=end_by_key.get(kq)
                if prev is None or sf(q)>sf(prev):
                    end_by_key[kq]=q
                acts=(d.play_land_actions(q)+d.tap_mana_actions(q)+
                      d.utility_actions(q)+d.special_actions(q)+
                      d.v03_actions(q)+d.nasty_mana_actions(q)+
                      d.repair_actions(q)+d.saga_tutor_actions(q)+
                      d.cast_actions(q))
            for a in acts:
                k=kf(a)
                if k not in seen:
                    seen.add(k)
                    nxt.append(a)
        if not nxt:
            break
        nxt=d.prune_dominated_frontier_states(nxt)
        nxt.sort(key=sf,reverse=True)
        sigbest={}
        for q in nxt:
            names=frozenset(x.name for x in q.battlefield)
            sig=(q.land_played,
                 min(2,sum(x in d.GUARANTEED_WHITE_LANDS for x in q.hand)),
                 "Urza's Saga" in names,"Mana Vault" in names,
                 "Sol Ring" in names,
                 ("Lion's Eye Diamond" in names or "Lion's Eye Diamond" in q.hand),
                 min(3,sum(x in d.LANDS or x in {"Emeria's Call","Razorgrass Ambush"} for x in q.hand)),
                 "Coalition Relic" in names,
                 any(x.name in {"Brainstone","Scroll Rack"} for x in q.battlefield))
            if sig not in sigbest:
                sigbest[sig]=q
        diverse=sorted(sigbest.values(),key=sf,reverse=True)[:max(1,beam//3)]
        dk={kf(q) for q in diverse}
        frontier=diverse+[q for q in nxt if kf(q) not in dk][:max(0,beam-len(diverse))]
        if len(end_by_key)>beam*3:
            vals=d.prune_dominated_frontier_states(end_by_key.values())
            vals=sorted(vals,key=sf,reverse=True)
            keep=vals[:beam]
            end_by_key={kf(q):q for q in keep}

    # Preserve even the legacy final-depth success predicate verbatim.
    wins=[q for q in frontier if d.can_cast_dack(q)]
    if wins:
        counters["terminal_witnesses_at_depth_end"]+=1
        return wins[:1],[]
    for q in frontier:
        if not d.city_trigger_pending(q):
            end_by_key[kf(q)]=q
    endvals=d.prune_dominated_frontier_states(end_by_key.values())
    return [],sorted(endvals,key=sf,reverse=True)[:beam]

@contextmanager
def conditional_win_only():
    old=d.search_turn_frontier_many
    d.search_turn_frontier_many=search_turn_frontier_win_only
    try:
        yield
    finally:
        d.search_turn_frontier_many=old

def certified_keep_weighted_ev_seat(*args,**kwargs):
    with conditional_win_only():
        return _ORIGINAL_KEEP(*args,**kwargs)

def certified_bounded_rollout_prefix(*args,**kwargs):
    with conditional_win_only():
        return _ORIGINAL_PREFIX(*args,**kwargs)

def install():
    """All hypothetical futures, including branch-bound suffixes; not gameplay."""
    d.keep_weighted_ev_seat=certified_keep_weighted_ev_seat
    bounded._rollout_prefix=certified_bounded_rollout_prefix
    return certified_keep_weighted_ev_seat

def uninstall():
    d.keep_weighted_ev_seat=_ORIGINAL_KEEP
    bounded._rollout_prefix=_ORIGINAL_PREFIX
    return _ORIGINAL_KEEP

def clear_counters():
    counters.clear()

def selftest():
    assert d.search_turn_frontier_many is _ORIGINAL_SEARCH
    install()
    assert d.keep_weighted_ev_seat is certified_keep_weighted_ev_seat
    assert bounded._rollout_prefix is certified_bounded_rollout_prefix
    uninstall()
    assert d.keep_weighted_ev_seat is _ORIGINAL_KEEP
    assert bounded._rollout_prefix is _ORIGINAL_PREFIX
    assert d.search_turn_frontier_many is _ORIGINAL_SEARCH
    return {"status":"PASS","version":RULES_VERSION,
            "scope":"London hypothetical futures only"}

if __name__=="__main__":
    import json
    print(json.dumps(selftest(),indent=2))
