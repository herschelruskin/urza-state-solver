#!/usr/bin/env python3
"""Unselected matched N32 Realistic v4 known-top tutor policy population audit.

Tests all game IDs 0..31, rather than selecting only historical Full-Beam
failures. V2 comparison uses frozen archived exact game IDs and identical
deck hashes; no hidden future draw enters live action choice.
"""
from __future__ import annotations
import argparse,hashlib,gzip,json,time
from collections import Counter
import dack_realistic_v4_known_top_tutors_20261019 as v4

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--variant",choices=("current","buck_worldmap"),required=True)
    p.add_argument("--shard",type=int,required=True)
    p.add_argument("--games",type=int,default=4)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    assert a.shard>=0 and a.games>=1
    v4.audit()
    rows=[]
    tic=time.time()
    for j in range(a.games):
        gid=a.shard*a.games+j
        r=v4.play(a.variant,gid,True)
        rows.append({"game_id":gid,"win_turn":r["win_turn"],
                     "keep_n":r["keep_n"],"rolls":r["rolls"],
                     "rollout_calls":r["rollout_calls"],
                     "turns":r["turns"]})
        print("KNOWN_TOP_POPULATION_GAME",a.variant,gid,r["win_turn"],flush=True)
    deck=v4.v2.trial.VARIANTS[a.variant]
    data={"schema":"dack_known_top_population_v4","variant":a.variant,
          "beam":120,"pass_cap":9,"samples":3,"shard":a.shard,"games":a.games,
          "deck_sha256":hashlib.sha256("\n".join(deck).encode()).hexdigest(),
          "seed_base":v4.v2.SEED_BASE,"rows":rows,
          "counts":{str(k):v for k,v in Counter(q["win_turn"] for q in rows).items()},
          "elapsed_sec":round(time.time()-tic,2)}
    with gzip.open(a.out,"wt",encoding="utf8") as f:json.dump(data,f,separators=(",",":"))
    print("KNOWN_TOP_POPULATION_SHARD_PASS",a.variant,a.games,flush=True)
if __name__=="__main__":main()
