#!/usr/bin/env python3
"""Independent 128-game per deck confirmation of unmodified Realistic Beam v6."""
from __future__ import annotations
import argparse,gzip,hashlib,json,time
from collections import Counter
import dack_realistic_v6_stratified_reward_20261019 as v6
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--variant",choices=("current","buck_worldmap"),required=True)
    p.add_argument("--shard",type=int,required=True)
    p.add_argument("--games",type=int,default=8)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    assert a.shard>=0 and a.games>0
    v6.audit()
    rows=[];t0=time.time()
    for j in range(a.games):
        gid=a.shard*a.games+j
        q=v6.simulate(a.variant,gid,12,6)
        rows.append({"game_id":gid,"win_turn":q["win_turn"],
                     "keep_n":q["keep_n"],
                     "rolls":q["rolls"],
                     "rollout_calls":q["rollout_calls"]})
        print("DACK_REALISTIC_V6_CONFIRM_GAME",a.variant,gid,
              q["win_turn"],flush=True)
    obj={"schema":"dack_realistic_v6_confirm_n128","variant":a.variant,
      "shard":a.shard,"games":a.games,"seed_base":v6.v2.SEED_BASE,
      "deck_sha256":hashlib.sha256("\n".join(v6.v2.trial.VARIANTS[a.variant]).encode()).hexdigest(),
      "counts":{str(k):v for k,v in Counter(r["win_turn"] for r in rows).items()},
      "elapsed_seconds":round(time.time()-t0,2),"rows":rows}
    with gzip.open(a.out,"wt",encoding="utf8") as f:
        json.dump(obj,f,separators=(",",":"))
    print("DACK_V6_CONFIRM_N128_SHARD_PASS",a.variant,a.games,flush=True)
if __name__=="__main__":main()
