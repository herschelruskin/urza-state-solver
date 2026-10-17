#!/usr/bin/env python3
"""Realistic Beam v2: keep information-aware beam, plan through T3.

This complements (does NOT edit) Realistic Beam v1 and frozen Full Beam.

A T1 ending is ranked by expected chance of T2 commander deployment and by
expected chance of T3 after a T2 miss. Unknown draws are sampled from the
remaining CARD MULTISET independent of actual library order; the turn's beam
can adapt only AFTER each hypothetical observation.

Planner utility: 1.5 * P(T2) + 0.5 * P(T3 exactly).
This is equivalent to P(by T2) + 0.5 * P(by T3), excluding constant T1 wins.

Still experimental: finite candidate rollouts, heuristics for choosing a T2
state, and inherited in-turn tutor/draw future peek limitations.
"""
from __future__ import annotations
import argparse, gzip, hashlib, json, math, time
from collections import Counter
import dack_realistic_information_beam_20261017 as v1

fair=v1.fair
root=v1.root
trial=v1.trial
d=v1.d
m=v1.m
SEED_BASE=v1.SEED_BASE
POLICY="realistic_info_beam_v2"
ORIGINAL_ONE_SAMPLE=v1.one_future_sample_value
LEVEL3=2
T2_CONTINUATIONS=2

def top_known_state_score(q):
    return v1.public_score(q)

def rollout_one_turn(state, j):
    if not state.library:return False,[]
    nxt=v1.hypothetical_next_start(state,j)
    fair.overridden_roll(1)
    d.utility_actions=fair.utility_without_roll
    try:
        wins,front=d.search_turn_frontier_many([nxt],
              beam=v1.PARAMS["rollout_beam"],
              depth=v1.PARAMS["rollout_depth"])
    finally:
        d.utility_actions=fair.ORIG_UTILITY
    v1.COUNTERS["rollout_calls"]+=1
    return bool(wins),front

def remaining_t3_chance(t2_states):
    """Choose T2 pass after T2 draw, but before unknown T3 draw."""
    if not t2_states:return 0.
    viable=v1.short_list(t2_states,T2_CONTINUATIONS)
    estimates=[]
    for s in viable:
        chances=[]
        for z in range(LEVEL3):
            if not s.library:
                chances.append(0.)
                continue
            win,_=rollout_one_turn(s,z+10001)
            chances.append(float(win))
        estimates.append(sum(chances)/LEVEL3)
    return max(estimates,default=0.)

def lookahead_T2_T3_value(state,j):
    if state.turn>=3:return top_known_state_score(state)/5000.
    if not state.library:return top_known_state_score(state)/5000.
    win,front=rollout_one_turn(state,j)
    if state.turn==2:
        if win:return 0.5
        return min(0.045,max(0.,top_known_state_score(max(front,key=top_known_state_score))/18000.)) if front else 0.
    # On T1: a win on sampled T2 draw counts for both cumulative T2/T3.
    if win:return 1.5
    p3=remaining_t3_chance(front)
    score=0.5*p3
    # Resource tiebreak accounts for simulator's depth/beam misses.
    if front:
        score+=min(0.025,max(0.,top_known_state_score(max(front,key=top_known_state_score))/24000.))
    return score

def activate_v2(draws=3,t3_samples=2,t2_continuations=2):
    global LEVEL3,T2_CONTINUATIONS
    LEVEL3=int(t3_samples);T2_CONTINUATIONS=int(t2_continuations)
    assert LEVEL3>=1 and T2_CONTINUATIONS>=1
    v1.one_future_sample_value=lookahead_T2_T3_value

def selftest():
    v1.audit()
    root.install("current")
    fair.install_honest_scry()
    activate_v2(2,2,2)
    v1.configure(SEED_BASE,rollout_draws=2,pass_cap=4,buck_cap=2,
                 rollout_beam=24,rollout_depth=10)
    a=d.State(1,("Plains",),("Sol Ring","Ancient Tomb","Mana Vault"),w=1)
    b=v1.replace(a,library=tuple(reversed(a.library)))
    assert v1.private_order_free_signature(a)==v1.private_order_free_signature(b)
    assert v1.hypothetical_next_start(a,0)==v1.hypothetical_next_start(b,0)
    assert lookahead_T2_T3_value(a,0)==lookahead_T2_T3_value(b,0)
    assert v1.expected_future_value(a)==v1.expected_future_value(b)
    assert lookahead_T2_T3_value(a,0)>=0
    root.install("buck_worldmap")
    t=d.State(2,(),tuple(root.COMBO),battlefield=(d.Perm(v1.PURSE),),c=1)
    opts=fair.candidate_action_states(t)
    assert opts and all(q.treasures==1 for q in opts)
    print("REALISTIC_BEAM_V2_T2_T3_INFORMATION_AUDIT_PASS",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--variant",choices=("current","buck_worldmap"),default="current")
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--games",type=int,default=4)
    p.add_argument("--beam",type=int,default=120)
    p.add_argument("--pass-cap",type=int,default=9)
    p.add_argument("--buck-cap",type=int,default=3)
    p.add_argument("--draw-samples",type=int,default=3)
    p.add_argument("--rollout-beam",type=int,default=42)
    p.add_argument("--rollout-depth",type=int,default=18)
    p.add_argument("--t3-samples",type=int,default=2)
    p.add_argument("--t2-continuations",type=int,default=2)
    p.add_argument("--out",default="realistic_v2_shard.json.gz")
    args=p.parse_args()
    assert args.games>=1 and args.shard>=0
    selftest()
    if args.audit:return
    root.install(args.variant)
    fair.install_honest_scry()
    activate_v2(args.draw_samples,args.t3_samples,args.t2_continuations)
    d._WIN_CACHE.clear()
    rows=[];started=time.time()
    for j in range(args.games):
        gid=args.shard*args.games+j
        q=v1.simulate(args.variant,gid,args.beam,args.pass_cap,
            args.buck_cap,args.draw_samples,args.rollout_beam,args.rollout_depth)
        rows.append(q)
        print("REALISTIC_V2_GAME",args.variant,gid,q["win_turn"],
              "rollouts",q["planning_counts"]["rollout_calls"],flush=True)
    obj={
      "schema":POLICY,"variant":args.variant,
      "policy":"T1 decisions use sampled T2 and conditional T3 deployments across unknown draws; actual draws/d4 are hidden until committed",
      "beam":args.beam,"pass_cap":args.pass_cap,"buck_cap":args.buck_cap,
      "draw_samples":args.draw_samples,"rollout_beam":args.rollout_beam,
      "rollout_depth":args.rollout_depth,"t3_samples":args.t3_samples,
      "t2_continuations":args.t2_continuations,
      "shard":args.shard,"games":args.games,"seed_base":SEED_BASE,
      "deck_sha256":hashlib.sha256("\n".join(trial.VARIANTS[args.variant]).encode()).hexdigest(),
      "counts":{str(k):v for k,v in Counter(q["win_turn"] for q in rows).items()},
      "elapsed_sec":round(time.time()-started,2),"rows":rows
    }
    with gzip.open(args.out,"wt",encoding="utf8") as f:json.dump(obj,f,separators=(",",":"))
    print("REALISTIC_BEAM_V2_SHARD_PASS",args.variant,args.games,flush=True)

if __name__=="__main__":main()
