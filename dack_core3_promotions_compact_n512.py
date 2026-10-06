#!/usr/bin/env python3
"""Compact paired N=512 promotion runner.

Each worker runs the core3 baseline and all three promoted fourth-slot variants for
the same game IDs, then writes only the fields needed for paired inference.
Detailed kept hands and mulligan traces are intentionally omitted from screening
artifacts; discordant games can be replayed deterministically from game_id/seed.
"""
import argparse,gzip,hashlib,json
import dack_full_deck_accel_n512_batch as b

BASE="ablate__Final4_revert_Voltaic_to_Candelabra"
VARS=(
    BASE,
    "package__Core3_plus_Incubator_over_Prismatic",
    "package__Core3_plus_Lantern_over_Everflowing",
    "package__Core3_plus_Sonic_over_Everflowing",
)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--shard",type=int,required=True)
    ap.add_argument("--games",type=int,default=16)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()

    rows={v:[] for v in VARS}
    for i in range(a.games):
        gid=a.shard*a.games+i
        for v in VARS:
            r=b.simulate_game(v,gid)
            # Compact row: game_id, seed, seat, keep_n, win_turn.
            rows[v].append([r["game_id"],r["seed"],r["seat"],r["keep_n"],r["win_turn"]])
        print(json.dumps({"shard":a.shard,"done":i+1,"game_id":gid}),flush=True)

    manifest={
        "schema":"dack_compact_v1",
        "engine":b.CONFIG["engine"],
        "policy":b.CONFIG["policy"],
        "seed_base":b.CONFIG["seed_base"],
        "games":a.games,
        "shard":a.shard,
        "columns":["game_id","seed","seat","keep_n","win_turn"],
        "variants":{v:{
            "replace":b.VARIANTS[v]["replace"],
            "deck_sha256":b.deck_sha(b.build_deck(v)),
            "rows":rows[v],
        } for v in VARS},
    }
    raw=json.dumps(manifest,separators=(",",":")).encode()
    with gzip.open(a.out,"wb",compresslevel=9) as f:f.write(raw)
    print(json.dumps({"status":"complete","bytes_raw":len(raw),"out":a.out}),flush=True)

if __name__=="__main__":
    main()
