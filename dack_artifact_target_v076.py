#!/usr/bin/env python3
import argparse, json, os
import dack_artifact_paired_v076 as m

TARGETS=tuple(m.GROUPS["twos"]+m.GROUPS["threes"])
def utility(t): return 1.0 if t in (1,2) else 0.5 if t==3 else 0.0

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--target",choices=TARGETS,required=True)
    ap.add_argument("--start",type=int,required=True)
    ap.add_argument("--games",type=int,default=4)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    assert m.v.selftest()
    names=["baseline",a.target+" -> Generic Rock",a.target+" -> Snow Plains"]
    rows=[]
    for gid in range(a.start,a.start+a.games):
        vr={}
        for name in names:
            m.d.DECK=m.deck_for(name)
            row=m.b.simulate_game(gid)
            vr[name]={"win_turn":row["win_turn"],"keep_n":row["keep_n"],
                      "seat":row["seat"],"utility":utility(row["win_turn"])}
        rows.append({"game_id":gid,"variants":vr})
        print(json.dumps({"target":a.target,"game_id":gid,
                          "wins":{k:v["win_turn"] for k,v in vr.items()}}),flush=True)
    m.d.DECK=list(m.BASE_DECK)
    payload={"test":"artifact_target_extension_v076","target":a.target,
             "base_deck_sha256":m.BASE_HASH,"policy_signature":m.b.CONFIG,
             "generic_benchmark":"{2} artifact, untapped, T: add {C}",
             "start":a.start,"games":a.games,"rows":rows}
    os.makedirs(os.path.dirname(a.out) or ".",exist_ok=True)
    json.dump(payload,open(a.out,"w"),indent=2)

if __name__=="__main__": main()
