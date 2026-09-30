#!/usr/bin/env python3
import argparse, copy, hashlib, json, os, statistics, math
import dack_v075_current99 as v
import dack_current99_batch as b

LANDS = [
    "Urza's Cave",
    "Petrified Hamlet",
    "Command Beacon",
    "Talon Gates of Madara",
    "Great Hall of the Citadel",
    "Cavern of Souls",
]
BASE_DECK = tuple(v.CURRENT_DECK)
BASE_HASH = hashlib.sha256("\n".join(BASE_DECK).encode()).hexdigest()

def deck_for(name):
    if name == "baseline":
        return list(BASE_DECK)
    target = name
    deck = list(BASE_DECK)
    i = deck.index(target)
    deck[i] = "Plains"
    assert len(deck) == 99
    assert deck.count("Plains") == 14
    return deck

def outcome_utility(turn):
    if turn in (1,2): return 1.0
    if turn == 3: return 0.5
    return 0.0

def run_one(game_id):
    assert v.selftest()
    out = {"game_id": int(game_id), "base_deck_sha256": BASE_HASH, "variants": {}}
    for name in ["baseline"] + LANDS:
        b.d.DECK = deck_for(name)
        row = b.simulate_game(game_id)
        out["variants"][name] = {
            "win_turn": row["win_turn"],
            "keep_n": row["keep_n"],
            "seat": row["seat"],
            "utility": outcome_utility(row["win_turn"]),
        }
    b.d.DECK = list(BASE_DECK)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--start",type=int,required=True)
    ap.add_argument("--games",type=int,default=4)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    rows=[]
    for gid in range(a.start,a.start+a.games):
        r=run_one(gid)
        rows.append(r)
        print(json.dumps({"game_id":gid,"baseline":r["variants"]["baseline"]["win_turn"],
                          "swaps":{k:v["win_turn"] for k,v in r["variants"].items() if k!="baseline"}}),flush=True)
    payload={
      "test":"land_to_plains_paired",
      "engine":"v0.75-current99",
      "base_deck_sha256":BASE_HASH,
      "policy_signature":b.CONFIG,
      "lands":LANDS,
      "start":a.start,"games":a.games,"rows":rows
    }
    os.makedirs(os.path.dirname(a.out) or ".",exist_ok=True)
    with open(a.out,"w") as f: json.dump(payload,f,indent=2)
    print(json.dumps({"status":"complete","out":a.out,"games":a.games}),flush=True)

if __name__=="__main__":
    main()
