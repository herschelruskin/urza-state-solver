#!/usr/bin/env python3
"""Realistic v10: blind-mulligan-policy population benchmark.

The engine source on THIS BRANCH canonicalizes unknown library order before
sampling mulligan futures. Physical game shuffles/draws are unchanged.

Historical Full Beam/v6/v7 use the old ordering-dependent evaluator and
remain on their original branches. This script runs the same v7 turn
planner so ONLY keep/bottom evaluation's information leak is corrected.
Mulligan thresholds are still frozen and merit recalibration separately.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,time,random
from collections import Counter
import dack_realistic_v7_rollout_fidelity_20261019 as v7
from dack_boonweaver_exact99_20261016 import batch

v6=v7.v6;v2=v7.v2;v1=v7.v1;d=v7.d;m=v6.m;root=v7.root

def selftest():
    v7.audit()
    root.install("current")
    m.set_trial_seed(7604096001)
    if hasattr(d,"_WEIGHTED_SEAT_CACHE"):d._WEIGHTED_SEAT_CACHE.clear()
    seven=("Plains","Ancient Tomb","Mana Vault","Sol Ring",
           "Brainstone","Enlightened Tutor","Gemstone Caverns")
    cards=list(d.DECK)
    for c in seven:cards.remove(c)
    r1=tuple(cards)
    r2=tuple(reversed(cards))
    # Same observable hand + multiset implies identical London estimates.
    for keep_n in (7,6):
        z1=d.dack_bottom_weighted_ev_seat(seven,keep_n,r1,seat=2,
                beam=35,samples=3,t3_weight=.5,finalists_n=2)
        z2=d.dack_bottom_weighted_ev_seat(seven,keep_n,r2,seat=2,
                beam=35,samples=3,t3_weight=.5,finalists_n=2)
        assert z1[0]==z2[0],(keep_n,z1[0],z2[0])
        assert z1[1]==z2[1],keep_n
        assert z1[3:5]==z2[3:5],keep_n
        assert z1[5]==r1 and z2[5]==r2
    # The physical draw order MUST still be preserved for actual gameplay.
    s1=d.State(1,("Plains",),r1)
    s2=d.State(1,("Plains",),r2)
    assert d.draw(s1,1).hand!=d.draw(s2,1).hand
    print("DACK_V10_MULLIGAN_HIDDEN_ORDER_INVARIANCE_PASS",flush=True)

def run_one(variant,gid):
    q=v7.one(variant,gid,96,24)
    return {"game_id":gid,"win_turn":q["win_turn"],
            "keep_n":q["keep_n"],"seat":q["seat"],
            "rolls":q["rolls"],"turn_audit":q["turn_audit"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--variant",choices=("current","buck_worldmap"),default="current")
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--games",type=int,default=4)
    p.add_argument("--out",default="v10_blind_mulligan.json.gz")
    a=p.parse_args();selftest()
    if a.audit:return
    rows=[];start=time.time()
    for i in range(a.games):
        gid=a.shard*a.games+i
        x=run_one(a.variant,gid)
        rows.append(x)
        print("DACK_V10_BLIND_MULL_GAME",a.variant,gid,
              "T",x["win_turn"],"keep",x["keep_n"],flush=True)
    deck=v2.trial.VARIANTS[a.variant]
    out={"schema":"dack_v10_blind_mulligans",
         "variant":a.variant,"shard":a.shard,"games":a.games,
         "seed_base":v2.SEED_BASE,"actual_beam":120,
         "forecast_beam":96,"forecast_depth":24,
         "deck_sha256":hashlib.sha256("\n".join(deck).encode()).hexdigest(),
         "counts":{str(k):v for k,v in Counter(r["win_turn"] for r in rows).items()},
         "elapsed_seconds":round(time.time()-start,2),"rows":rows}
    with gzip.open(a.out,"wt",encoding="utf8") as f:
        json.dump(out,f,separators=(",",":"))
    print("DACK_V10_BLIND_MULLIGAN_SHARD_PASS",a.variant,a.games,flush=True)
if __name__=="__main__":main()
