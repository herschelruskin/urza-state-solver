#!/usr/bin/env python3
import argparse, json, os
import dack_artifact_paired_v076 as m

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--target",required=True)
    ap.add_argument("--game",type=int,required=True)
    ap.add_argument("--replacement",choices=["Generic Rock","Snow Plains"],required=True)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    name=a.target+" -> "+a.replacement
    m.d.DECK=m.deck_for(name)
    row=m.b.simulate_game(a.game)
    payload={"target":a.target,"game_id":a.game,"replacement":a.replacement,
             "variant":name,"win_turn":row["win_turn"],"keep_n":row["keep_n"],"seat":row["seat"],
             "base_deck_sha256":m.BASE_HASH,"policy_signature":m.b.CONFIG}
    os.makedirs(os.path.dirname(a.out) or ".",exist_ok=True)
    json.dump(payload,open(a.out,"w"),indent=2)
    print(json.dumps(payload),flush=True)
if __name__=="__main__": main()
