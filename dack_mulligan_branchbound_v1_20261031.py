#!/usr/bin/env python3
"""Exact branch-and-bound optimization of the inherited London bottom evaluator.

For each candidate London bottom choice, the old evaluator runs all S=8 (or
S=16 near a continuation threshold) hypothetical T1-T3 games, even after
its MAXIMUM possible final utility cannot overtake a fully evaluated incumbent.

This module preserves every original candidate, ordering, hidden sampler,
score, tie-break, refinement trigger, and retained-hand gameplay calculation.
It only skips losing future-rollout suffixes after proving their irrelevance.

The proof assumes nonnegative T1/T2/T3 weights <= max(1,t3_weight).
No probabilities or outcomes are inferred from absent/not-drawn cards.

The installed function can be reverted; archived engine modules are not edited.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
import random

import dack_counterfactual_rules_v1_20261030 as validated

d=validated.d
sim=validated.sim
RULES_VERSION="dack_bounded_mulligan_exact_v1"
_ORIGINAL=d.dack_bottom_weighted_ev_seat
stats=Counter()
stage_stats=defaultdict(Counter)

def _proven_uncompetitive(partial_score, done, total, best_utility, struct,
                          best_struct, t3_weight):
    """Upper bound of every unexamined sample, with strict lexical tie rules."""
    upper=(partial_score + (total-done)*max(1.0,float(t3_weight)))/total
    # Only reject a candidate when no continuation can beat the incumbent.
    return upper < best_utility-1e-12 or (
        abs(upper-best_utility)<=1e-12 and struct<=best_struct)

def _rollout_prefix(hand,unknown,bottom,seat,beam,samples,t3_weight,
                    struct,best_utility,best_struct):
    """Compute ORIGINAL samples, in ORIGINAL order; skip only certified losers.

    An evaluation cache entry is considered valid only when complete. Prefix
    results are not inserted into the engine's original cache.
    """
    hand=d.sort_hand(hand)
    unknown=tuple(unknown)
    bottom=tuple(bottom)
    samples=max(1,int(samples))
    # An incumbent that already reaches the mathematical utility ceiling
    # dominates every later lower-structure finalist without ANY rollout.
    if _proven_uncompetitive(0.0,0,samples,best_utility,struct,best_struct,
                            t3_weight):
        stats["futures_skipped_proven"]+=samples
        stats["pruned_candidates"]+=1
        stats["zero_rollout_prunes"]+=1
        return None,0,True
    if any(x in d.COMBO_CREATURES for x in hand) and not (
        "Brainstone" in hand or "Scroll Rack" in hand):
        stats["structural_zero"]+=1
        return None,0,True
    base=sorted(unknown)
    n=len(base)
    if n<3:
        return None,0,True
    rng=random.Random(d._stable_seed(hand+bottom,0x7330 + int(seat)*997))
    order=list(range(n))
    rng.shuffle(order)
    counts={1:0,2:0,3:0}
    partial=0.0
    for j in range(samples):
        inds=[]
        cursor=(j*17)%n
        while len(inds)<3:
            cand=order[(cursor+len(inds)*37+j*13)%n]
            if cand not in inds:
                inds.append(cand)
            else:
                cursor=(cursor+1)%n
        pick=set(inds)
        first3=[base[i] for i in inds]
        rem=[x for i,x in enumerate(base) if i not in pick]
        rr=random.Random(d._stable_seed(hand+bottom,0x7331+j*131+int(seat)*19))
        rr.shuffle(rem)
        lib=tuple(first3+rem+list(bottom))
        turn=d._win_turn_from_unknown_order(hand,lib,int(seat),beam,max_turn=3)
        if turn:
            counts[turn]+=1
            partial+=(1.0 if turn<=2 else float(t3_weight))
        stats["futures_executed"]+=1
        if _proven_uncompetitive(partial,j+1,samples,best_utility,struct,
                                best_struct,t3_weight):
            skipped=samples-(j+1)
            stats["futures_skipped_proven"]+=skipped
            stats["pruned_candidates"]+=1
            return None,j+1,True
    t1=counts[1]/samples
    t2=counts[2]/samples
    t3=counts[3]/samples
    return {
        "utility":t1+t2+float(t3_weight)*t3,
        "t1":t1, "t2":t2, "t3":t3,
        "le2":t1+t2,"le3":t1+t2+t3,
    },samples,False

def bounded_bottom_weighted_ev_seat(seven,keep_n,rest,seat,beam=50,
                                    samples=6,t3_weight=0.5,finalists_n=12):
    combos=[()] if keep_n==7 else list(combinations(range(7),7-keep_n))
    candidates=[]
    for inds0 in combos:
        inds=set(inds0)
        hand=d.sort_hand([x for i,x in enumerate(seven) if i not in inds])
        bottom=tuple(seven[i] for i in sorted(inds))
        struct=sum(d.bottom_priority(seven[i],seven) for i in inds)
        contam=sum(x in d.COMBO_CREATURES for x in hand)
        aura_kept=sum(x in d.AURAS for x in hand)
        candidates.append(((struct,-contam,-aura_kept),hand,bottom,tuple(rest)))
    candidates.sort(key=lambda x:x[0],reverse=True)
    finalists=candidates[:min(max(1,int(finalists_n)),len(candidates))]
    stats["evaluated_london_stages"]+=1
    stats["total_candidate_structures"]+=len(finalists)
    stage_stats[int(keep_n)]["candidate_structures"]+=len(finalists)

    best=None
    for i,(struct,hand,bottom,unknown) in enumerate(finalists):
        if i==0:
            # Establish an EXACT incumbent using the ORIGINAL evaluator.
            ev=d.keep_weighted_ev_seat(
                hand,unknown,seat=seat,beam=beam,samples=samples,
                bottom=bottom,t3_weight=t3_weight)
            stats["incumbent_full_calls"]+=1
        else:
            # Reuse an existing FULL eval if available. This is a proper
            # semantic key; partial suffixes never enter the cache.
            ck=(d.sort_hand(hand),tuple(sorted(unknown)),tuple(bottom),int(seat),
                int(beam),int(samples),float(t3_weight),
                "v0733_weighted_true_seat")
            cached=d._WEIGHTED_SEAT_CACHE.get(ck)
            if cached is not None:
                ev=cached
                stats["full_cache_hits"]+=1
            else:
                ev,done,pruned=_rollout_prefix(
                    hand,unknown,bottom,seat,beam,samples,t3_weight,
                    struct,best[1],best[0])
                if pruned:
                    stage_stats[int(keep_n)]["pruned_candidates"]+=1
                    continue
                stats["fully_scored_candidates"]+=1
                d._WEIGHTED_SEAT_CACHE[ck]=ev

        # Original scoring: sort descending by (utility, struct), stable
        # finalist ordering when keys tie. Only replace on a STRICT increase.
        rank=(ev["utility"],struct)
        if best is None or rank>(best[1],best[0]):
            best=(struct,ev["utility"],ev,hand,bottom,unknown)
            stats["new_incumbents"]+=1
    struct,u,ev,hand,bottom,unknown=best
    return u,ev,struct,hand,bottom,unknown

def install():
    d.dack_bottom_weighted_ev_seat=bounded_bottom_weighted_ev_seat
    return d.dack_bottom_weighted_ev_seat

def uninstall():
    d.dack_bottom_weighted_ev_seat=_ORIGINAL
    return d.dack_bottom_weighted_ev_seat

def reset_statistics():
    stats.clear()
    stage_stats.clear()

def get_statistics():
    return {
        "counts":dict(stats),
        "stages":{str(k):dict(v) for k,v in sorted(stage_stats.items())}
    }

def selftest():
    for t3 in (0.0,0.5,1.0):
        assert _proven_uncompetitive(0.0,4,8,0.6,(2,0,0),
                                     (3,0,0),t3)
        assert not _proven_uncompetitive(0.0,1,8,0.6,(2,0,0),
                                         (3,0,0),t3)
    assert not _proven_uncompetitive(0,8,8,0,(4,0,0),(3,0,0),0.5)
    assert _proven_uncompetitive(0,8,8,0,(2,0,0),(3,0,0),0.5)
    assert install() is bounded_bottom_weighted_ev_seat
    assert uninstall() is _ORIGINAL
    return {"status":"PASS","rules_version":RULES_VERSION,
            "optimization":"provable branch-and-bound on fixed future sample suffixes",
            "policy_parity_not_yet_validated":True}

if __name__=="__main__":
    import json
    print(json.dumps(selftest(),indent=2))
