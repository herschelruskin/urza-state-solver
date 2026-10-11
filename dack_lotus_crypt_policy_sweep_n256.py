#!/usr/bin/env python3
"""Matched DACK v0.77 policy-sensitivity experiment on Lotus+Crypt deck.

Same real engine and game IDs as prior 1024 result; only mulligan continuation
thresholds and artifact tutor choice change. No proxy mana simulation.
"""
import argparse, gzip, json, random
import dack_lotus_crypt_n1024 as sim

m=sim.m
d=sim.d
batch=sim.batch
ORIGINAL_TUTOR=d.artifact_tutor_choice
ORIGINAL_CONT=dict(batch.FROZEN_CONTINUATION)
ARMS=(
    ("frozen",0.00,False),
    ("deeper_005",0.05,False),
    ("deeper_010",0.10,False),
    ("lotus_tutor",0.00,True),
    ("lotus_tutor_deeper_005",0.05,True),
)
def prefer_lotus(s):
    original=ORIGINAL_TUTOR(s)
    # Preserve repair/contamination safety at all times.
    if original not in ("Lion's Eye Diamond","Mana Vault","Sol Ring"):
        return original
    if "Jeweled Lotus" not in s.library:
        return original
    # LED's no-tap sacrifice is materially better for Gardens copies.
    if original=="Lion's Eye Diamond" and (
        "The Mycosynth Gardens" in s.hand
        or any(p.name=="The Mycosynth Gardens" for p in s.battlefield)):
        return original
    return "Jeweled Lotus"

def evaluate(arm,game_id):
    name,extra,tutor=arm
    d.artifact_tutor_choice=prefer_lotus if tutor else ORIGINAL_TUTOR
    # The threshold is the estimated continuation value of a fresh smaller hand.
    # Raising it makes us mulligan more often without changing how hand EV is valued.
    batch.FROZEN_CONTINUATION={k:(v+extra if k>0 else 0.0)
                               for k,v in ORIGINAL_CONT.items()}
    try:
        result=batch.simulate_game("C_lotus_mana_crypt",game_id)
    finally:
        d.artifact_tutor_choice=ORIGINAL_TUTOR
        batch.FROZEN_CONTINUATION=dict(ORIGINAL_CONT)
    result["arm"]=name
    return result

def audit():
    sim.validate()
    lib=("Jeweled Lotus","Lion's Eye Diamond","Mana Vault")+tuple(d.COMBO_CREATURES)
    s=d.State(1,(),lib)
    assert ORIGINAL_TUTOR(s)=="Lion's Eye Diamond"
    assert prefer_lotus(s)=="Jeweled Lotus"
    s=d.State(1,("The Mycosynth Gardens",),lib)
    assert prefer_lotus(s)=="Lion's Eye Diamond"
    assert ORIGINAL_CONT[6]<ORIGINAL_CONT[6]+0.05
    assert sim.build_deck("C_lotus_mana_crypt").count("Jeweled Lotus")==1
    print("POLICY_SWEEP_AUDIT_PASS",flush=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",action="store_true")
    ap.add_argument("--shard",type=int,default=0)
    ap.add_argument("--games",type=int,default=8)
    ap.add_argument("--out",default="shard.json.gz")
    args=ap.parse_args()
    audit()
    if args.audit:return
    variants={name:[] for name,_,_ in ARMS}
    for i in range(args.games):
        gid=args.shard*args.games+i
        for arm in ARMS:
            r=evaluate(arm,gid)
            variants[arm[0]].append({
                "id":r["game_id"],"seed":r["seed"],"seat":r["seat"],
                "keep_n":r["keep_n"],"win_turn":r["win_turn"],
                "kept_hand":r["kept_hand"],"bottomed_cards":r["bottomed_cards"],
                "utility":r["keep_utility"],
            })
        print(json.dumps({"shard":args.shard,"done":i+1,"game_id":gid}),flush=True)
    payload={
        "schema":"dack_policy_sweep_n256_v1",
        "deck_sha256":batch.deck_sha(sim.build_deck("C_lotus_mana_crypt")),
        "engine":batch.CONFIG["engine"],"source_1024_run":38082688686,
        "seed_base":batch.CONFIG["seed_base"],"shard":args.shard,
        "games":args.games,"arms":variants,
    }
    with gzip.open(args.out,"wt",encoding="utf8") as f:
        json.dump(payload,f,separators=(",",":"))
    print("POLICY_SHARD_PASS",args.shard,flush=True)

if __name__=="__main__":
    main()
