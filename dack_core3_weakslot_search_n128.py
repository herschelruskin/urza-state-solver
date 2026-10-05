#!/usr/bin/env python3
"""Broad N=128 weak-slot search on top of validated Bucknard+KCI+Manifold core3."""
import argparse, hashlib, json, random, time
from collections import Counter
import dack_full_deck_accel_n512_batch as b
import dack_v077_full_deck_accel as m

d=m.d
CORE3_REPLACE=(
    ("Pearl Medallion","Krark-Clan Ironworks"),
    ("Liquimetal Torque","Bucknard's Everfull Purse"),
    ("Giant's Boulder","Manifold Key"),
)
CANDIDATES=(
    "Helm of Awakening",
    "Inspiring Statuary",
    "Marble Diamond",
    "Sonic Screwdriver",
    "Urza's Incubator",
    "Worn Powerstone",
    "Chromatic Lantern",
    "Honor-Worn Shaku",
    "Component Pouch",
    "Oketra's Monument",
    "Cloud Key",
    "Pentad Prism",
    "Thran Dynamo",
    "Extraplanar Lens",
    "Kozilek's Command",
    "Voltaic Key",
)
CUTS=(
    "Prismatic Lens",
    "The Mind Stone",
    "Everflowing Chalice",
    "Mind Stone",
    "Tooth of Ramos",
    "Basalt Monolith",
    "Implements of Sacrifice",
)

def build_deck(candidate,cut):
    deck=list(b.CURRENT)
    for old,new in CORE3_REPLACE:
        if deck.count(old)!=1: raise AssertionError((old,deck.count(old)))
        deck[deck.index(old)]=new
    if candidate!="__BASE__":
        if candidate not in CANDIDATES: raise AssertionError(candidate)
        if cut not in CUTS: raise AssertionError(cut)
        if deck.count(cut)!=1: raise AssertionError((cut,deck.count(cut)))
        deck[deck.index(cut)]=candidate
    else:
        if cut!="__NONE__": raise AssertionError(cut)
    assert len(deck)==99
    return tuple(deck)

def deck_sha(deck):
    return hashlib.sha256("\n".join(deck).encode()).hexdigest()

def simulate(candidate,cut,game_id):
    deck=build_deck(candidate,cut)
    m.set_deck(deck)
    seed=b.CONFIG["seed_base"]+int(game_id)*1000003
    m.set_trial_seed(seed)
    rng=random.Random(seed)
    seat=rng.randrange(4)
    state,keep_n,keep_u,kept,bottom,audit=b.choose_hand(rng,seat)
    win=d._win_turn_from_unknown_order(
        state.hand,state.library,seat,
        beam=b.CONFIG["gameplay_beam"],max_turn=b.CONFIG["max_turn"])
    return {
        "game_id":int(game_id),"seed":int(seed),"seat":int(seat),
        "keep_n":int(keep_n),"mulligans":int(7-keep_n),
        "keep_utility":float(keep_u),"win_turn":int(win) if win else 0,
        "kept_hand":list(kept),"bottomed_cards":list(bottom),
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--candidate",required=True,choices=("__BASE__",)+CANDIDATES)
    ap.add_argument("--cut",required=True,choices=("__NONE__",)+CUTS)
    ap.add_argument("--shard",type=int,required=True)
    ap.add_argument("--games",type=int,default=64)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    if a.candidate=="__BASE__" and a.cut!="__NONE__": raise SystemExit("baseline requires __NONE__")
    if a.candidate!="__BASE__" and a.cut=="__NONE__": raise SystemExit("candidate requires cut")
    assert m.selftest()
    deck=build_deck(a.candidate,a.cut)
    start=time.time(); rows=[]
    for i in range(a.games):
        gid=a.shard*a.games+i
        row=simulate(a.candidate,a.cut,gid); rows.append(row)
        print(json.dumps({"candidate":a.candidate,"cut":a.cut,"shard":a.shard,
                          "done":i+1,"game_id":gid,"win_turn":row["win_turn"],
                          "keep_n":row["keep_n"]}),flush=True)
    c=Counter(r["win_turn"] for r in rows)
    label="CORE3_BASE" if a.candidate=="__BASE__" else a.candidate+"__OVER__"+a.cut
    payload={
        "label":label,"candidate":a.candidate,"cut":a.cut,
        "core_replace":CORE3_REPLACE,
        "compatibility_signature":{**b.CONFIG,
            "search":"core3_weakslot_search_n128",
            "candidate":a.candidate,"cut":a.cut,
            "deck_sha256":deck_sha(deck)},
        "shard":a.shard,"games":a.games,"elapsed_seconds":time.time()-start,
        "counts":{str(k):int(v) for k,v in sorted(c.items())},"rows":rows,
    }
    with open(a.out,"w",encoding="utf-8") as f: json.dump(payload,f,indent=2)

if __name__=="__main__":main()
