#!/usr/bin/env python3
import argparse, hashlib, json, os
import dack_v075_current99 as v
import dack_current99_batch as b
import dack_thought_vessel_patch as tv

LANDS=["Urza's Cave","Petrified Hamlet","Command Beacon","Talon Gates of Madara","Great Hall of the Citadel","Cavern of Souls"]
BASE_DECK=tuple(v.CURRENT_DECK)
BASE_HASH=hashlib.sha256("\n".join(BASE_DECK).encode()).hexdigest()
ROCK="Thought Vessel"

def deck_for(name):
    if name=="baseline": return list(BASE_DECK)
    deck=list(BASE_DECK)
    i=deck.index(name); deck[i]=ROCK
    assert len(deck)==99 and deck.count(ROCK)==1
    return deck

def utility(t):
    return 1.0 if t in (1,2) else 0.5 if t==3 else 0.0

def run_one(game_id):
    assert v.selftest() and tv.selftest()
    out={"game_id":int(game_id),"base_deck_sha256":BASE_HASH,"variants":{}}
    for name in ["baseline"]+LANDS:
        b.d.DECK=deck_for(name)
        row=b.simulate_game(game_id)
        out["variants"][name]={"win_turn":row["win_turn"],"keep_n":row["keep_n"],"seat":row["seat"],"utility":utility(row["win_turn"])}
    b.d.DECK=list(BASE_DECK)
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--start",type=int,required=True); ap.add_argument("--games",type=int,default=4); ap.add_argument("--out",required=True); a=ap.parse_args()
    rows=[]
    for gid in range(a.start,a.start+a.games):
        r=run_one(gid); rows.append(r)
        print(json.dumps({"game_id":gid,"baseline":r["variants"]["baseline"]["win_turn"],"swaps":{k:v["win_turn"] for k,v in r["variants"].items() if k!="baseline"}}),flush=True)
    payload={"test":"land_to_thought_vessel_paired","replacement":ROCK,"engine":"v0.75-current99+thought-vessel","base_deck_sha256":BASE_HASH,"policy_signature":b.CONFIG,"lands":LANDS,"start":a.start,"games":a.games,"rows":rows}
    os.makedirs(os.path.dirname(a.out) or ".",exist_ok=True); json.dump(payload,open(a.out,"w"),indent=2)
    print(json.dumps({"status":"complete","out":a.out,"games":a.games}),flush=True)
if __name__=="__main__": main()
