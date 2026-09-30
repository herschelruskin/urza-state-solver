#!/usr/bin/env python3
import argparse, json, os, random
import dack_artifact_paired_v076 as m

TARGETS=("Prismatic Lens","Pearl Medallion","Implements of Sacrifice","Tooth of Ramos")
GENERIC=m.GENERIC
_orig_seed=m.d._stable_seed
_orig_shuffle=m.d.shuffled_unknown

CURRENT_TARGET=None

def canon(x):
    return CURRENT_TARGET if x==GENERIC else x

def crn_seed(items,salt=0):
    # Canonical multiset identity: benchmark replacement hashes as the original target.
    mapped=sorted(canon(x) for x in items)
    return _orig_seed(tuple(mapped),salt)

def crn_shuffle(lib):
    # Same post-tutor permutation under baseline and replacement.
    items=sorted(list(lib),key=lambda x:canon(x))
    mapped=tuple(sorted(canon(x) for x in items))
    rng=random.Random(_orig_seed(mapped,0xDACC50))
    rng.shuffle(items)
    return tuple(items)

m.d._stable_seed=crn_seed
m.d.shuffled_unknown=crn_shuffle

def utility(t): return 1.0 if t in (1,2) else 0.5 if t==3 else 0.0

def main():
    global CURRENT_TARGET
    ap=argparse.ArgumentParser()
    ap.add_argument("--target",choices=TARGETS,required=True)
    ap.add_argument("--start",type=int,required=True)
    ap.add_argument("--games",type=int,default=4)
    ap.add_argument("--out",required=True)
    a=ap.parse_args(); CURRENT_TARGET=a.target
    assert m.v.selftest()
    rows=[]
    for gid in range(a.start,a.start+a.games):
        vr={}
        for name in ("baseline",a.target+" -> Generic Rock"):
            m.d.DECK=m.deck_for(name)
            row=m.b.simulate_game(gid)
            vr[name]={"win_turn":row["win_turn"],"keep_n":row["keep_n"],"seat":row["seat"],
                      "utility":utility(row["win_turn"])}
        bt=vr["baseline"]["win_turn"]; gt=vr[a.target+" -> Generic Rock"]["win_turn"]
        dominance_violation=(a.target=="Prismatic Lens" and
                             (4 if gt==0 else gt)<(4 if bt==0 else bt))
        rows.append({"game_id":gid,"variants":vr,"lens_dominance_violation":dominance_violation})
        print(json.dumps(rows[-1]),flush=True)
    m.d.DECK=list(m.BASE_DECK)
    payload={"test":"artifact_generic_crn_v076","target":a.target,"start":a.start,"games":a.games,
             "base_deck_sha256":m.BASE_HASH,"policy_signature":m.b.CONFIG,
             "seed_pairing":"benchmark aliases to original target in conditional-future and post-tutor shuffle seeds",
             "rows":rows}
    os.makedirs(os.path.dirname(a.out) or ".",exist_ok=True)
    json.dump(payload,open(a.out,"w"),indent=2)

if __name__=="__main__": main()
