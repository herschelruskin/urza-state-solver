#!/usr/bin/env python3
"""Realistic Beam v3 reward AB test: bankable mana + graded continuation.

Do not modify Full Beam, Realistic v1 or Realistic v2.
On exact previously missed games, replay v2 unchanged and compare to v3
with identical initial seed, mulligans, draws, roll sampler, widths and depth.

v3 corrections:
- PASS-state score previews the next upkeep, after floating mana expires and
  ordinary reusable lands/rocks untap; no hidden next draw is inspected.
- When a sampled continuation has no T2/T3 cast, retain a smooth resource
  readiness gradient instead of near-zero, often saturated legacy tiebreak.
- Actual cast rewards (1.5 for T2 and .5 for T3) remain unchanged.
"""
import argparse,json,math
from dataclasses import replace
from pathlib import Path
import dack_realistic_information_beam_v2_20261017 as v2
v1=v2.v1
fair=v2.fair
root=v2.root
d=v2.d

EXPECTED={
  "current":{0:0,1:0,22:3},
  "buck_worldmap":{0:0,1:0,22:3,31:0}
}
ORIG_PUBLIC=v1.public_score

def bankable_readiness_score(state):
    """Score sustainable future resources without inspecting a hidden draw."""
    if state.turn>=3:
        return fair.heuristic(state)
    upcoming=d.untap_and_begin(replace(state,turn=state.turn+1))
    upcoming=d.add_opponent_cycle_resources(upcoming)
    return fair.heuristic(upcoming)

def bounded_readiness(states):
    """0..0.10 continuation reward, never overrides a verified Dack cast."""
    if not states:return 0.
    score=max(bankable_readiness_score(q) for q in v1.short_list(states,3))
    return min(0.10,max(0.,score/8500.))

def shaped_T2_T3_value(state,j):
    if state.turn>=3:return bankable_readiness_score(state)/5000.
    if not state.library:return bounded_readiness([state])
    win,front=v2.rollout_one_turn(state,j)
    if state.turn==2:
        if win:return 0.5
        return bounded_readiness(front)
    if win:return 1.5
    p3=v2.remaining_t3_chance(front)
    return 0.5*p3+bounded_readiness(front)

def arm(variant,gid,shaped):
    root.install(variant)
    fair.install_honest_scry()
    d._WIN_CACHE.clear()
    v2.activate_v2(draws=3,t3_samples=2,t2_continuations=2)
    v1.public_score=bankable_readiness_score if shaped else ORIG_PUBLIC
    if shaped:v1.one_future_sample_value=shaped_T2_T3_value
    try:
        r=v1.simulate(variant,gid,120,9,3,3,42,18)
        return {"win_turn":r["win_turn"],"keep_n":r["keep_n"],
                "rolls":r["rolls"],
                "turn_actions":[{"turn":q["turn"],"phase":q["phase"],
                   "pass_candidates":q.get("pass_candidates"),
                   "buck_plans":q.get("buck_plans"),
                   "pass_value":q.get("pass_value")} for q in r["turn_audit"]],
                "rollout_calls":r["planning_counts"]["rollout_calls"]}
    finally:
        v1.public_score=ORIG_PUBLIC

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--variant",choices=tuple(EXPECTED),required=True)
    p.add_argument("--gid",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    assert a.gid in EXPECTED[a.variant]
    v2.selftest()
    # Score must be invariant to hidden library order.
    state=d.State(1,("Plains",),("Ancient Tomb","Sol Ring","Mana Vault"),w=2,c=5)
    shuffled=replace(state,library=tuple(reversed(state.library)))
    assert bankable_readiness_score(state)==bankable_readiness_score(shuffled)
    assert bankable_readiness_score(state)==bankable_readiness_score(replace(
       state,w=0,c=0))
    baseline=arm(a.variant,a.gid,False)
    assert baseline["win_turn"]==EXPECTED[a.variant][a.gid],(
      "Original v2 replay does not match frozen archive",a.variant,a.gid,baseline)
    candidate=arm(a.variant,a.gid,True)
    assert baseline["keep_n"]==candidate["keep_n"]
    result={
       "status":"PASS","variant":a.variant,"game_id":a.gid,
       "policy_variations":"v2 exact baseline versus v3 bankable turn-reset pass score plus smooth [0,.10] non-win resource reward",
       "baseline_v2":baseline,"shaped_v3":candidate,
       "T2_recovered":bool(0<candidate["win_turn"]<=2 and baseline["win_turn"] not in (1,2)),
       "T3_recovered":bool(candidate["win_turn"] and not baseline["win_turn"]),
       "lost_T3":bool(baseline["win_turn"] and not candidate["win_turn"]),
       "limits":["Selected failure sample only; this is not a winrate","No full oracle eliminated mid-turn",
                 "No inference about optimal weights from seven selected games",
                 "Resource bonus is an experimental heuristic, not a rules-derived probability"]}
    Path(a.out).write_text(json.dumps(result,indent=2)+"\n")
    print("DACK_REALISTIC_BEAM_REWARD_AB_PASS",json.dumps({
       "variant":a.variant,"gid":a.gid,
       "v2_turn":baseline["win_turn"],"v3_turn":candidate["win_turn"],
       "v2_rollouts":baseline["rollout_calls"],
       "v3_rollouts":candidate["rollout_calls"]}),flush=True)

if __name__=="__main__":main()
