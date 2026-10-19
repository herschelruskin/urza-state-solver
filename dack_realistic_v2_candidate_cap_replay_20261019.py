#!/usr/bin/env python3
"""Audit Realistic Beam v2 candidate-cap losses on exact Full-Beam-only games.

Replay exact seeds with original cap 9 and widened cap 24. Only difference is
number of turn-end alternatives admitted to expected-draw rollouts; mana
engine, fair roll, mulligans, and future-draw samples remain fixed.

Baseline replay of original cap 9 MUST exactly match the archived v2 outcome,
otherwise stop rather than interpreting a mismatched experiment.
"""
import argparse,json,random
from pathlib import Path
import dack_realistic_information_beam_v2_20261017 as v2

root=v2.root
fair=v2.fair
m=v2.m
BASE_EXPECTED={
    "current":{0:0,1:0,22:3},
    "buck_worldmap":{0:0,1:0,22:3,31:0}
}

def get_hand(variant,gid):
    root.install(variant)
    seed=v2.SEED_BASE+gid*1000003
    m.set_trial_seed(seed)
    rng=random.Random(seed)
    seat=rng.randrange(4)
    fair.overridden_roll(2)
    state,keep,audit=root.choose_hand_with_free(rng,seat)
    return {"keep_n":keep,"seat":seat,"kept_hand":list(state.hand),
            "next_draws_raw":list(state.library[:3]),
            "mull_stages":len(audit)}

def run_one(variant,gid,cap):
    root.install(variant)
    fair.install_honest_scry()
    v2.activate_v2(draws=3,t3_samples=2,t2_continuations=2)
    v2.d._WIN_CACHE.clear()
    r=v2.v1.simulate(variant,gid,120,cap,3,3,42,18)
    return {"win_turn":r["win_turn"],"keep_n":r["keep_n"],
            "rolls":r["rolls"],
            "turns":[{
                "turn":t["turn"],"phase":t["phase"],
                "pass_candidates":t.get("pass_candidates",0),
                "buck_plans":t.get("buck_plans",0),
                "pass_value":t.get("pass_value"),
                "die":t.get("die")
            } for t in r["turn_audit"]],
            "rollout_calls":r["planning_counts"]["rollout_calls"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--variant",choices=tuple(BASE_EXPECTED),required=True)
    p.add_argument("--gid",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    assert a.gid in BASE_EXPECTED[a.variant]
    v2.selftest()
    hand=get_hand(a.variant,a.gid)
    original=run_one(a.variant,a.gid,9)
    assert original["win_turn"]==BASE_EXPECTED[a.variant][a.gid],(
        "archived v2 replay drift",a.variant,a.gid,
        original["win_turn"],BASE_EXPECTED[a.variant][a.gid])
    widened=run_one(a.variant,a.gid,24)
    assert original["keep_n"]==widened["keep_n"]==hand["keep_n"]
    out={"status":"PASS","variant":a.variant,"game_id":a.gid,
         "baseline_v2_cap9_replay_verified":True,"hand":hand,
         "cap9":original,"cap24":widened,
         "by_T2":{"cap9":int(0<original["win_turn"]<=2),
                  "cap24":int(0<widened["win_turn"]<=2)},
         "by_T3":{"cap9":int(original["win_turn"]>0),
                  "cap24":int(widened["win_turn"]>0)},
         "interpretation":"Widen only preselection of turn-end beam candidates; no new information may be used to pick one"}
    Path(a.out).write_text(json.dumps(out,indent=2)+"\n")
    print("REALISTIC_V2_CAP9_VS_CAP24_REPLAY_PASS",json.dumps({
        "variant":a.variant,"game_id":a.gid,
        "cap9_win":original["win_turn"],"cap24_win":widened["win_turn"],
        "keep":original["keep_n"],"rollout9":original["rollout_calls"],
        "rollout24":widened["rollout_calls"]}),flush=True)

if __name__=="__main__":
    main()
