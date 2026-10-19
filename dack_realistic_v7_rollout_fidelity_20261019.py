#!/usr/bin/env python3
"""Dack Realistic v7: controlled rollout-fidelity comparison to v6.

Only changes the *counterfactual forecasting* search from beam=42/depth=18
to beam=96/depth=24, retaining:
  - identical actual gameplay beam=120, T1/T2/T3 windows
  - v6 weighted stratification: 12 drawn T2 candidates, 6 drawn T3
  - knowledge-preserving Enlightened/Loyal Tutor wrapper
  - independent fair d4 after Bucknard commitment
  - identical sampled games, mulligans, seat and draw order
No actual next card or future die is used to choose a present action.
Some inherited within-turn hidden-order search remains; do not call this
a fully imperfect-information-correct solver.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,time
from collections import Counter
import dack_realistic_v6_stratified_reward_20261019 as v6
v2=v6.v2; v1=v6.v1; d=v6.d; fair=v6.fair; root=v6.root
V7_BEAM=96
V7_DEPTH=24

def one(variant,gid,forecast_beam=V7_BEAM,forecast_depth=V7_DEPTH):
    root.install(variant)
    v6.v4.KNOWN.clear()
    v2.activate_v2(3,2,2)
    d._WIN_CACHE.clear()
    v6.setup(12,6)
    assert d.cast_actions is v6.v4.known_cast_actions
    assert d.key is v6.v4.knowledge_key
    start=time.time()
    r=v1.simulate(variant,gid,120,9,3,3,forecast_beam,forecast_depth)
    return {"game_id":gid,"win_turn":r["win_turn"],
            "keep_n":r["keep_n"],"seat":r["seat"],
            "rolls":r["rolls"],"turn_audit":r["turn_audit"],
            "forecast_rollout_calls":r["planning_counts"]["rollout_calls"],
            "runtime_seconds":round(time.time()-start,3)}

def audit():
    v6.audit()
    for v in ("current","buck_worldmap"):
        root.install(v)
        assert all(q not in v2.trial.VARIANTS[v] for q in ("Mana Crypt","Jeweled Lotus"))
        assert len(v2.trial.VARIANTS[v])==99
    root.install("current")
    v2.activate_v2(3,2,2)
    v6.setup(12,6)
    assert v1.expected_future_value is v6.strat_expected_future
    assert v1.hypothetical_next_start is v6.strat_next_start
    assert d.cast_actions is v6.v4.known_cast_actions
    print("REALISTIC_V7_FORECAST_FIDELITY_AUDIT_PASS",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--variant",choices=("current","buck_worldmap"),default="current")
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--games",type=int,default=4)
    p.add_argument("--forecast-beam",type=int,default=V7_BEAM)
    p.add_argument("--forecast-depth",type=int,default=V7_DEPTH)
    p.add_argument("--out",default="dack_v7_forecast.json.gz")
    a=p.parse_args()
    audit()
    if a.audit:return
    assert a.shard>=0 and a.games>=1 and 42<=a.forecast_beam<=240
    assert 18<=a.forecast_depth<=32
    rows=[]
    for n in range(a.games):
        gid=a.shard*a.games+n
        rec=one(a.variant,gid,a.forecast_beam,a.forecast_depth)
        rows.append(rec)
        print("DACK_V7_GAME",a.variant,gid,rec["win_turn"],
              "forecast_beam",a.forecast_beam,
              "forecast_rollouts",rec["forecast_rollout_calls"],flush=True)
    deck=v2.trial.VARIANTS[a.variant]
    payload={"schema":"dack_realistic_forecast_fidelity_v7",
             "variant":a.variant,"forecast_beam":a.forecast_beam,
             "forecast_depth":a.forecast_depth,"actual_beam":120,
             "turn_end_candidates":9,"stratified_T2_draws":12,
             "stratified_T3_draws":6,"games":a.games,"shard":a.shard,
             "seed_base":v2.SEED_BASE,
             "deck_sha256":hashlib.sha256("\n".join(deck).encode()).hexdigest(),
             "counts":{str(k):v for k,v in Counter(z["win_turn"] for z in rows).items()},
             "rows":rows}
    with gzip.open(a.out,"wt",encoding="utf8") as f:
        json.dump(payload,f,separators=(",",":"))
    print("DACK_V7_FIDELITY_SHARD_PASS",a.variant,a.games,flush=True)

if __name__=="__main__":main()
