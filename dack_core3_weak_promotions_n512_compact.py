#!/usr/bin/env python3
"""Compact N512 runner for weak-slot promotions on the validated core3 shell.

Rows are encoded as [game_id, seat, keep_n, win_turn]. Seed is deterministic from
CONFIG.seed_base + game_id*1000003, so it is not duplicated per row. Full mulligan
audits / kept-hand strings are intentionally omitted from production shards.
"""
import argparse, json, time
from collections import Counter
import dack_full_deck_accel_n512_batch as b
import dack_v077_full_deck_accel as m

BASE="ablate__Final4_revert_Voltaic_to_Candelabra"
VARIANTS=(
    BASE,
    "package__Core3_plus_Incubator_over_Prismatic",
    "package__Core3_plus_Lantern_over_Everflowing",
    "package__Core3_plus_Sonic_over_Everflowing",
)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--variant",required=True,choices=VARIANTS)
    ap.add_argument("--shard",type=int,required=True)
    ap.add_argument("--games",type=int,default=32)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    assert m.selftest()
    start=time.time(); rows=[]
    for i in range(a.games):
        gid=a.shard*a.games+i
        r=b.simulate_game(a.variant,gid)
        rows.append([int(r["game_id"]),int(r["seat"]),int(r["keep_n"]),int(r["win_turn"])])
        print(json.dumps({"variant":a.variant,"shard":a.shard,"done":i+1,
                          "game_id":gid,"win_turn":r["win_turn"],"keep_n":r["keep_n"]}),flush=True)
    c=Counter(x[3] for x in rows)
    payload={
        "schema":"dack_compact_rows_v1",
        "columns":["game_id","seat","keep_n","win_turn"],
        "seed_formula":"seed_base + game_id*1000003",
        "seed_base":b.CONFIG["seed_base"],
        "variant":a.variant,
        "replace":b.VARIANTS[a.variant]["replace"],
        "shard":a.shard,
        "games":a.games,
        "elapsed_seconds":time.time()-start,
        "counts":{str(k):int(v) for k,v in sorted(c.items())},
        "rows":rows,
    }
    with open(a.out,"w",encoding="utf-8") as f:
        json.dump(payload,f,separators=(",",":"))
    print(json.dumps({"status":"complete","variant":a.variant,"counts":payload["counts"],
                      "elapsed_seconds":payload["elapsed_seconds"]}),flush=True)

if __name__=="__main__":
    main()
