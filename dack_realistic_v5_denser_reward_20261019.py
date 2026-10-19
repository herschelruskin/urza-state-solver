#!/usr/bin/env python3
"""Dack v5: choose information-aware beam endings by denser future-draw rollout.

A/B compared with frozen Realistic v2, and v4 known-top case outcomes.

Fixes *reward estimation*, not physical game mechanics:
 - Future draws use a common-random-number set drawn from remaining multiset.
 - Enlightened/Loyal Tutor known-top-card observation is honored.
 - Evaluate 12+ possible future cards instead of just 3.
 - Optional faster-T2 objective (T2 success weight 2.5 rather than 1.5).
 - Do not reward actual unseen T2/T3 cards or tune actions based on those.

Tests are selected historical misses; use a future independent population run
before claiming winrate improvements.
"""
from __future__ import annotations
import argparse, hashlib, json, math, random
from pathlib import Path
import dack_realistic_v4_known_top_tutors_20261019 as v4

v2=v4.v2;v1=v4.v1;fair=v4.fair;root=v4.root;d=v4.d;m=v4.m
CASES={"current":{0:0,1:0,22:3},
       "buck_worldmap":{0:0,1:0,22:3,31:0}}
ORIGINAL_EV=v1.expected_future_value
REWARD_POLICY="denser_draws"
DRAWS=12
NEXT_DRAWS=6
WIN_T2_WEIGHT=1.5
CACHE={}
COUNTS={"rollouts":0,"ev_states":0}

def set_reward(draws,policy):
    global DRAWS,NEXT_DRAWS,WIN_T2_WEIGHT,REWARD_POLICY
    assert draws>=3 and policy in ("balanced","t2_heavy")
    DRAWS=int(draws)
    NEXT_DRAWS=max(4,DRAWS//2)
    REWARD_POLICY=policy
    WIN_T2_WEIGHT=1.5 if policy=="balanced" else 2.5
    v1.expected_future_value=dense_future_value

def dense_future_value(state):
    if state.turn>=3:
        return v1.public_score(state)/5000.
    if not state.library:
        return v1.public_score(state)/5000.
    signature=v1.private_order_free_signature(state)
    token=(int(v1.TRIAL_SEED),signature,REWARD_POLICY,DRAWS,NEXT_DRAWS)
    if token in CACHE:return CACHE[token]
    count=DRAWS if state.turn==1 else NEXT_DRAWS
    vals=[]
    for j in range(count):
        value=v2.lookahead_T2_T3_value(state,j)
        if state.turn==1 and value>=1.5:
            # The only change to the objective is giving an immediate T2
            # commander deployment extra reward. This does not peek at the
            # actual draw because lookahead uses counterfactual samples.
            assert abs(value-1.5)<1.e-6
            value=WIN_T2_WEIGHT
        vals.append(value)
    result=sum(vals)/count
    CACHE[token]=result
    COUNTS["rollouts"]+=count
    COUNTS["ev_states"]+=1
    return result

def play(variant,gid,policy,draws):
    root.install(variant)
    fair.install_honest_scry()
    v4.install()
    v4.KNOWN.clear()
    v2.activate_v2(draws=3,t3_samples=2,t2_continuations=2)
    set_reward(draws,policy)
    d._WIN_CACHE.clear()
    CACHE.clear()
    COUNTS.update({"rollouts":0,"ev_states":0})
    q=v1.simulate(variant,gid,120,9,3,3,42,18)
    return {
      "win_turn":q["win_turn"],"keep_n":q["keep_n"],
      "rolls":q["rolls"],"rollout_calls":q["planning_counts"]["rollout_calls"],
      "reward_sample_calls":COUNTS["rollouts"],"reward_states":COUNTS["ev_states"],
      "turns":[{"turn":r["turn"],"phase":r["phase"],
               "pass_candidates":r.get("pass_candidates"),
               "pass_value":r.get("pass_value")} for r in q["turn_audit"]]}

def selftest():
    v4.audit()
    root.install("current")
    fair.install_honest_scry()
    v4.install()
    set_reward(12,"balanced")
    # Real next-card order MUST NOT affect the reward estimator.
    v1.configure(v2.SEED_BASE,3,9,3,42,18)
    a=d.State(1,("Plains",),("Ancient Tomb","Sol Ring","Mana Vault"),w=1)
    b=v1.replace(a,library=tuple(reversed(a.library)))
    CACHE.clear()
    left=dense_future_value(a)
    right=dense_future_value(b)
    assert left==right,(left,right)
    assert 0<=left<=2.5
    # Known-top information is a legit exception and must influence futures.
    c=d.State(1,(),("Mana Vault","Plains","Ancient Tomb"),w=1)
    v4.register_known(c.library,"Mana Vault")
    assert v4.known_top(c)=="Mana Vault"
    nxt=v1.hypothetical_next_start(c,0)
    assert "Mana Vault" in nxt.hand
    v4.KNOWN.clear()
    print("DACK_V5_DENser_REWARD_INFORMATION_AUDIT_PASS",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--variant",choices=tuple(CASES),default="current")
    p.add_argument("--gid",type=int,default=0)
    p.add_argument("--draws",type=int,default=12)
    p.add_argument("--policy",choices=("balanced","t2_heavy"),default="balanced")
    p.add_argument("--out",default="v5_reward.json")
    a=p.parse_args()
    selftest()
    if a.audit:return
    assert a.gid in CASES[a.variant]
    result=play(a.variant,a.gid,a.policy,a.draws)
    payload={"status":"PASS","game_id":a.gid,"variant":a.variant,
       "policy":a.policy,"draws":a.draws,
       "v2_original_win_turn":CASES[a.variant][a.gid],
       "result":result,
       "limitations":[
          "Failure-focused sample; cannot be used to estimate overall rates",
          "T2 and T3 lookahead remain bounded beam approximations",
          "Known-top observation tags use library object identity",
          "Only select known-top tutors are currently modeled",
          "Within-turn search can still view later unobserved cards"]}
    Path(a.out).write_text(json.dumps(payload,indent=2)+"\n")
    print("DACK_DENSER_REWARD_GAME_PASS",a.variant,a.gid,a.policy,
          "win",result["win_turn"],"rollouts",result["rollout_calls"],flush=True)

if __name__=="__main__":main()
