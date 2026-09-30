#!/usr/bin/env python3
import argparse, json, random, time, hashlib
from collections import Counter
import dack_v076_creature_sequences as v

d=v.d

# Keep the established lambda objective for first validation. Continuation values will be
# recalibrated before a new canonical absolute baseline, because legal creature-hand lines
# change London continuation values slightly.
FROZEN_CONTINUATION = {
    0:0.0,
    1:0.06171875,
    2:0.19234,
    3:0.31419,
    4:0.42268,
    5:0.51025,
    6:0.55603,
}
CONFIG={
    "engine":"v0.76-creature-sequences",
    "policy":"lambda_0.5_pre_recalibration_validation",
    "lambda":0.5,
    "min_keep":1,
    "actual_seat_before_mulligans":True,
    "mulligan_eval_beam":60,
    "screen_samples":8,
    "refine_samples":16,
    "refine_margin":0.125,
    "bottom_finalists":12,
    "gameplay_beam":240,
    "max_turn":3,
    "continuation":FROZEN_CONTINUATION,
    "seed_base":7602405001,
}
CONFIG["deck_sha256"]=hashlib.sha256("\n".join(d.DECK).encode()).hexdigest()

def evaluate_keep(seven,keep_n,rest,seat):
    raw,ev,struct,hand,bottom,unknown=d.dack_bottom_weighted_ev_seat(
        seven,keep_n,rest,seat=seat,beam=CONFIG["mulligan_eval_beam"],
        samples=CONFIG["screen_samples"],t3_weight=CONFIG["lambda"],
        finalists_n=CONFIG["bottom_finalists"])
    threshold=0.0 if keep_n==CONFIG["min_keep"] else FROZEN_CONTINUATION[keep_n-1]
    refined=False
    if keep_n>CONFIG["min_keep"] and abs(float(raw)-float(threshold))<=CONFIG["refine_margin"]:
        raw,ev,struct,hand,bottom,unknown=d.dack_bottom_weighted_ev_seat(
            seven,keep_n,rest,seat=seat,beam=CONFIG["mulligan_eval_beam"],
            samples=CONFIG["refine_samples"],t3_weight=CONFIG["lambda"],
            finalists_n=CONFIG["bottom_finalists"])
        refined=True
    return raw,ev,struct,hand,bottom,unknown,threshold,refined

def choose_hand(rng,seat):
    audit=[]
    for keep_n in range(7,CONFIG["min_keep"]-1,-1):
        deck=list(d.DECK); rng.shuffle(deck)
        seven,rest=deck[:7],deck[7:]
        raw,ev,struct,hand,bottom,unknown,threshold,refined=evaluate_keep(seven,keep_n,rest,seat)
        audit.append({"keep_n":keep_n,"utility":float(raw),"threshold":float(threshold),
                      "le2_est":float(ev["le2"]),"t3_est":float(ev["t3"]),"refined":bool(refined)})
        if keep_n==CONFIG["min_keep"] or float(raw)>=float(threshold):
            return d.State(1,hand,tuple(unknown)+tuple(bottom)),keep_n,float(raw),audit
    raise RuntimeError("no terminal London keep")

def simulate_game(game_id):
    v.clear_caches()
    seed=CONFIG["seed_base"]+int(game_id)*1000003
    rng=random.Random(seed); seat=rng.randrange(4)
    state,keep_n,keep_u,audit=choose_hand(rng,seat)
    win=d._win_turn_from_unknown_order(state.hand,state.library,seat,
        beam=CONFIG["gameplay_beam"],max_turn=CONFIG["max_turn"])
    return {"game_id":int(game_id),"seed":int(seed),"seat":int(seat),"keep_n":int(keep_n),
            "keep_utility":float(keep_u),"win_turn":int(win) if win else 0,"mulligan_audit":audit}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--shard",type=int,required=True)
    ap.add_argument("--games",type=int,default=16); ap.add_argument("--out",required=True)
    a=ap.parse_args(); assert v.selftest()
    start=time.time(); rows=[]
    for i in range(a.games):
        gid=a.shard*a.games+i; rows.append(simulate_game(gid))
        print(json.dumps({"shard":a.shard,"done":i+1,"game_id":gid,
                          "win_turn":rows[-1]["win_turn"],"keep_n":rows[-1]["keep_n"]}),flush=True)
    c=Counter(r["win_turn"] for r in rows)
    payload={"compatibility_signature":CONFIG,"shard":a.shard,"games":a.games,
             "elapsed_seconds":time.time()-start,
             "counts":{str(k):int(vv) for k,vv in sorted(c.items())},"rows":rows}
    with open(a.out,"w") as f: json.dump(payload,f,indent=2)
    print(json.dumps({"status":"complete","out":a.out,"counts":payload["counts"]}),flush=True)

if __name__=="__main__":
    main()
