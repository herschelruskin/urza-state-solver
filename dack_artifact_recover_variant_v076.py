#!/usr/bin/env python3
import argparse, json, os
import dack_artifact_paired_v076 as m

def utility(t):
    return 1.0 if t in (1,2) else 0.5 if t==3 else 0.0

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--target",required=True)
    ap.add_argument("--game",type=int,required=True)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    assert a.target in m.GROUPS["threes"]
    assert m.v.selftest()
    names=["baseline",a.target+" -> Generic Rock",a.target+" -> Snow Plains"]
    vr={}
    for name in names:
        m.d.DECK=m.deck_for(name)
        row=m.b.simulate_game(a.game)
        vr[name]={"win_turn":row["win_turn"],"keep_n":row["keep_n"],
                  "seat":row["seat"],"utility":utility(row["win_turn"])}
    m.d.DECK=list(m.BASE_DECK)
    payload={"test":"artifact_threes_recovery_variant_v076","target":a.target,
             "game_id":a.game,"base_deck_sha256":m.BASE_HASH,
             "policy_signature":m.b.CONFIG,"variants":vr}
    os.makedirs(os.path.dirname(a.out) or ".",exist_ok=True)
    json.dump(payload,open(a.out,"w"),indent=2)
    print(json.dumps(payload),flush=True)

if __name__=="__main__": main()
