#!/usr/bin/env python3
"""Exact deep Manifold Key arm for a paired N=4096 comparison against the frozen
Giant's Boulder current-99 baseline.

The completed Boulder baseline already contains these exact 4096 game IDs/seeds.
This runner changes ONE card only:
    Giant's Boulder -> Manifold Key
and otherwise preserves the validated v0.76 engine, London mulligan policy,
continuation thresholds, actual-seat-before-mulligans, gameplay beam, and max turn.
"""
import argparse, hashlib, json, random, time
from collections import Counter
import dack_v076_current99_20261002 as v

d=v.d

FROZEN_CONTINUATION = {
    0:0.0,
    1:0.06171875,
    2:0.19234,
    3:0.31419,
    4:0.42268,
    5:0.51025,
    6:0.55603,
}

BOULDER_DECK = tuple(v.CURRENT_DECK)
assert BOULDER_DECK.count("Giant's Boulder")==1
assert BOULDER_DECK.count("Manifold Key")==0

KEY_DECK = tuple("Manifold Key" if x=="Giant's Boulder" else x for x in BOULDER_DECK)
assert len(KEY_DECK)==99
assert KEY_DECK.count("Manifold Key")==1
assert KEY_DECK.count("Giant's Boulder")==0

CONFIG = {
    "engine":"v0.76-current99-20261002",
    "comparison":"Giant's Boulder -> Manifold Key",
    "arm":"Manifold Key",
    "baseline_arm":"Giant's Boulder",
    "policy":"stable_lambda_0.5_frozen_continuation",
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
    "seed_base":7604096001,
    "continuation":FROZEN_CONTINUATION,
    "boulder_deck_sha256":hashlib.sha256("\n".join(BOULDER_DECK).encode()).hexdigest(),
    "key_deck_sha256":hashlib.sha256("\n".join(KEY_DECK).encode()).hexdigest(),
    "paired_to_baseline_file":"results/dack_v076_current99_n4096_final_games.csv",
}

def set_key_deck():
    # Preserve card ordering exactly; replacing the card in place means identical RNG shuffles
    # correspond to identical deck positions in the two paired arms.
    d.DECK=list(KEY_DECK)
    v.clear_caches()

def key_selftest():
    # Validate frozen Boulder engine first, then mutate only the comparison slot.
    assert v.selftest()
    set_key_deck()
    assert len(d.DECK)==99
    assert d.DECK.count("Manifold Key")==1
    assert d.DECK.count("Giant's Boulder")==0
    assert d.COSTS["Manifold Key"]==(1,0,0)
    # 1,T: untap another artifact must remain live in the current engine.
    s=d.State(1,(),(),(d.Perm("Manifold Key"),d.Perm("Mana Vault",True)),c=1)
    outs=d.special_actions(s)
    assert any(
        any(d.effective_name(p)=="Mana Vault" and not p.tapped for p in q.battlefield)
        and any(d.effective_name(p)=="Manifold Key" and p.tapped for p in q.battlefield)
        for q in outs
    ), "Manifold Key untap ability missing"
    return True

def evaluate_keep(seven,keep_n,rest,seat):
    raw,ev,struct,hand,bottom,unknown=d.dack_bottom_weighted_ev_seat(
        seven,keep_n,rest,seat=seat,beam=CONFIG["mulligan_eval_beam"],
        samples=CONFIG["screen_samples"],t3_weight=CONFIG["lambda"],
        finalists_n=CONFIG["bottom_finalists"])
    threshold=0.0 if keep_n==CONFIG["min_keep"] else FROZEN_CONTINUATION[keep_n-1]
    refined=False
    if (keep_n>CONFIG["min_keep"]
            and abs(float(raw)-float(threshold))<=CONFIG["refine_margin"]):
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
        raw,ev,struct,hand,bottom,unknown,threshold,refined=evaluate_keep(
            seven,keep_n,rest,seat)
        audit.append({
            "keep_n":int(keep_n),
            "utility":float(raw),
            "threshold":float(threshold),
            "le2_est":float(ev["le2"]),
            "t3_exact_est":float(ev["t3"]),
            "le3_est":float(ev["le3"]),
            "refined":bool(refined),
        })
        if keep_n==CONFIG["min_keep"] or float(raw)>=float(threshold):
            lib=tuple(unknown)+tuple(bottom)
            return (
                d.State(1,hand,lib), keep_n, float(raw),
                tuple(hand), tuple(bottom), audit
            )
    raise RuntimeError("no terminal London keep")

def simulate_game(game_id):
    set_key_deck()
    seed=CONFIG["seed_base"]+int(game_id)*1000003
    rng=random.Random(seed)
    seat=rng.randrange(4)
    state,keep_n,keep_u,kept_hand,bottomed,audit=choose_hand(rng,seat)
    win=d._win_turn_from_unknown_order(
        state.hand,state.library,seat,
        beam=CONFIG["gameplay_beam"],max_turn=CONFIG["max_turn"])
    return {
        "game_id":int(game_id),
        "seed":int(seed),
        "seat":int(seat),
        "keep_n":int(keep_n),
        "mulligans":int(7-keep_n),
        "keep_utility":float(keep_u),
        "win_turn":int(win) if win else 0,
        "kept_hand":list(kept_hand),
        "bottomed_cards":list(bottomed),
        "mulligan_audit":audit,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--shard",type=int,required=True)
    ap.add_argument("--games",type=int,default=32)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    assert key_selftest()
    start=time.time()
    rows=[]
    for i in range(a.games):
        game_id=a.shard*a.games+i
        row=simulate_game(game_id); rows.append(row)
        print(json.dumps({
            "shard":a.shard,"done":i+1,"games":a.games,
            "game_id":game_id,"win_turn":row["win_turn"],
            "keep_n":row["keep_n"]
        }),flush=True)
    c=Counter(r["win_turn"] for r in rows)
    payload={
        "compatibility_signature":CONFIG,
        "shard":int(a.shard),
        "games":int(a.games),
        "elapsed_seconds":time.time()-start,
        "counts":{str(k):int(vv) for k,vv in sorted(c.items())},
        "rows":rows,
    }
    with open(a.out,"w",encoding="utf-8") as f:
        json.dump(payload,f,indent=2)
    print(json.dumps({
        "status":"complete","out":a.out,
        "elapsed_seconds":payload["elapsed_seconds"],
        "counts":payload["counts"]
    }),flush=True)

if __name__=="__main__":
    main()
