#!/usr/bin/env python3
"""Sharded T1-T3 cast-availability benchmark for the Oct-12 Dack flicker list.

Output reports assumed combo wins at legal Dack CAST, except the provisional Abdel+Solar hand pair.
Keeps the established v0.77 conditional-draw London mulligan policy frozen,
so comparisons are paired. All opponent-dependent gameplay is excluded.
"""
import argparse, gzip, hashlib, json, time
from collections import Counter
import dack_flicker_v078 as fork
import dack_full_deck_accel_n512_batch as batch

VARIANTS=("baseline","battlefront_over_prismatic","battlefront_over_amulet","ramp_restore5")
batch.build_deck=fork.build_deck
batch.CONFIG.update({
    "engine":"v0.78-flicker-current100-deployment-only",
    "policy":"v0.77_stable_lambda_0.5_frozen_mulligans_new_cards",
    "max_turn":3,
})
def audit():
    assert fork.selftest()
    assert len(fork.BASE_DECK)==99
    assert len(fork.build_deck("battlefront_over_prismatic"))==99
    assert fork.BASE_DECK.count("United Battlefront")==0
    assert fork.build_deck("battlefront_over_prismatic").count("United Battlefront")==1
    assert len(fork.build_deck("ramp_restore5"))==99
    assert set(fork.build_deck("ramp_restore5"))-set(fork.BASE_DECK)=={
        new for _,new in fork.RAMP_RESTORE5_SWAPS}
    assert set(fork.BASE_DECK)-set(fork.build_deck("ramp_restore5"))=={
        old for old,_ in fork.RAMP_RESTORE5_SWAPS}
    for v in VARIANTS:
        assert len(set(fork.build_deck(v)))==87
    print("DACK_FLICKER_V078_RUNNER_AUDIT_PASS",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--variant",choices=VARIANTS,default="baseline")
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--games",type=int,default=2)
    p.add_argument("--beam",type=int,default=240)
    p.add_argument("--out",default="dack_flicker_shard.json.gz")
    args=p.parse_args()
    assert args.games>=0 and args.shard>=0
    audit()
    if args.audit:return
    batch.CONFIG["gameplay_beam"]=args.beam
    deck=fork.install(args.variant)
    start=time.time()
    rows=[]
    for i in range(args.games):
        gid=args.shard*args.games+i
        result=batch.simulate_game(args.variant,gid)
        rows.append(result)
        print(json.dumps({"game_id":gid,"win_turn":result["win_turn"],
                          "keep_n":result["keep_n"]}),flush=True)
    counts=Counter(str(x["win_turn"]) for x in rows)
    payload={
        "schema":"dack_flicker_t1t3_deployment_v078",
        "objective":"earliest goldfish win: cast Dack with mana and without Abdel+Radiant Solar both in hand; assume combo wins",
        "deck_sha256":hashlib.sha256("\n".join(deck).encode()).hexdigest(),
        "variant":args.variant,"seed_base":batch.CONFIG["seed_base"],
        "seed_scheme":"seed_base + game_id * 1000003",
        "shard":args.shard,"games":args.games,"beam":args.beam,
        "counts":dict(counts),"elapsed_sec":round(time.time()-start,3),
        "mulligan_policy":batch.CONFIG["policy"],
        "limitations":["No opponent interactions or protection probabilities",
                       "Smothering Tithe generates 3 Treasures per completed opponent cycle",
                       "Fomori Vault selection modeled; The Mind Stone harness deferred to post-T3 engine",
                       "Dack cast assumed to immediately win if Abdel+Radiant Solar are not both in hand; combo mechanics not resolved",
                       "Staff life payments tracked; other sources of life loss ignored",
                       "Abdel+Radiant Solar in hand is the sole provisional blocking condition",
                       "Legacy mulligan continuation calibrated for an older deck"],
        "rows":rows,
    }
    with gzip.open(args.out,"wt",encoding="utf8") as f:
        json.dump(payload,f,separators=(",",":"))
    print("DACK_FLICKER_SHARD_PASS",args.variant,args.games,counts,flush=True)

if __name__=="__main__":
    main()
