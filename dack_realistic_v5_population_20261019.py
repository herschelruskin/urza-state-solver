#!/usr/bin/env python3
"""Independent 0..31 population trial for Dack v5 denser future-draw reward.

Same seat/mulligans/decks/beam as frozen v4; v5 averages twelve T1 candidate
draw futures and six at later turns, and keeps the existing T2/T3 weights.
No selection of test games based on historical misses.
"""
import argparse,gzip,hashlib,json,time
from collections import Counter
import dack_realistic_v5_denser_reward_20261019 as v5

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--variant",choices=("current","buck_worldmap"),required=True)
    p.add_argument("--shard",type=int,required=True)
    p.add_argument("--games",type=int,default=4)
    p.add_argument("--draws",type=int,default=12)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    assert a.shard>=0 and a.games>=1 and a.draws>=3
    v5.selftest()
    rows=[];started=time.time()
    for j in range(a.games):
        gid=a.shard*a.games+j
        result=v5.play(a.variant,gid,"balanced",a.draws)
        row={"game_id":gid,"win_turn":result["win_turn"],
             "keep_n":result["keep_n"],"rolls":result["rolls"],
             "rollout_calls":result["rollout_calls"],
             "reward_states":result["reward_states"],
             "reward_sample_calls":result["reward_sample_calls"]}
        rows.append(row)
        print("DACK_V5_POPULATION_GAME",a.variant,gid,row["win_turn"],
              "samples",row["reward_sample_calls"],flush=True)
    deck=v5.trial.VARIANTS[a.variant] if hasattr(v5,"trial") else v5.v2.trial.VARIANTS[a.variant]
    output={
      "schema":"dack_realistic_population_v5",
      "variant":a.variant,"policy":"balanced_12_future_draw_samples",
      "draws":a.draws,"shard":a.shard,"games":a.games,
      "seed_base":v5.v2.SEED_BASE,
      "deck_sha256":hashlib.sha256("\n".join(deck).encode()).hexdigest(),
      "counts":{str(k):v for k,v in Counter(x["win_turn"] for x in rows).items()},
      "elapsed_sec":round(time.time()-started,2),"rows":rows}
    with gzip.open(a.out,"wt",encoding="utf8") as f:json.dump(output,f,separators=(",",":"))
    print("DACK_V5_POPULATION_SHARD_PASS",a.variant,a.games,flush=True)

if __name__=="__main__":
    main()
