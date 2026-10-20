#!/usr/bin/env python3
"""Dack v9: legal Gemstone Caverns exile choice via pre-draw expected value.

One pregame commitment is selected BEFORE seeing the actual T1 draw. For
each legal exile (including declining Gemstone), score independent possible
T1 draws over the remaining deck multiset. Reveal the *hypothetical* draw,
beam-search legal mana lines, and evaluate T2/T3 expected deployment from
those continuations. Actual game proceeds with its original hidden library.

This is an experimental rule-correct nonclairvoyant policy, not a claim of
optimal POMDP play. Same v6 mulligan, chance-aware turn commitments and dice.
"""
from __future__ import annotations
import argparse,hashlib,json,random,time
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
import dack_realistic_v6_stratified_reward_20261019 as v6

v1=v6.v1;v2=v6.v2;v4=v6.v4;fair=v6.fair;root=v6.root;d=v6.d;m=v6.m
ORIG_PREGAME=fair.choose_pregame
GID=-1
ACTIVE=[]
MAX_PER_STRATUM=1
EARLY_BEAM=48

def opening_scenarios(s):
    """No dependence on s.library order, only public multiset and game seed."""
    groups=defaultdict(list)
    for c in sorted(s.library):groups[v6.group(c)].append(c)
    count=len(s.library);out=[]
    if count==0:return out
    for g in sorted(groups):
        a=groups[g]
        seed=int.from_bytes(hashlib.sha256(
          f"{v1.TRIAL_SEED}|gemstone-first-draw|{g}|{count}|{sorted(a)}".encode()
        ).digest()[:16],"big")
        rng=random.Random(seed)
        pool=list(a);rng.shuffle(pool)
        picked=pool[:min(MAX_PER_STRATUM,len(pool))]
        w=len(a)/(count*len(picked))
        out.extend((c,w) for c in picked)
    assert abs(sum(w for _,w in out)-1)<1e-9
    return out

def counterfactual_first_draw(s,drawn,i):
    tail=sorted(s.library);tail.remove(drawn)
    seed=int.from_bytes(hashlib.sha256(
        f"{v1.TRIAL_SEED}|gemstone-tail|{i}|{drawn}|{len(tail)}".encode()
        ).digest()[:16],"big")
    random.Random(seed).shuffle(tail)
    return d.draw(replace(s,library=(drawn,)+tuple(tail)),1)

def expected_pregame_option(s):
    """E[P(T1) priority, P(T2)+.5P(T3) thereafter], no real draw peek."""
    score=0.
    for idx,(draw,weight) in enumerate(opening_scenarios(s)):
        starts=[counterfactual_first_draw(s,draw,idx)]
        fair.overridden_roll(1)
        d.utility_actions=fair.utility_without_roll
        try:
            wins,front=d.search_turn_frontier_many(starts,beam=EARLY_BEAM,depth=22)
        finally:
            d.utility_actions=fair.ORIG_UTILITY
        if wins:
            # An immediate T1 Dack beats any continuation and is desirable.
            val=2.0
        elif front:
            # After seeing the hypothetical T1 card, ordinary beam selection
            # may adapt, but the REAL card remains hidden during this ranking.
            keep=v1.short_list(front,1)
            val=max((v6.strat_expected_future(q) for q in keep),default=0.)
        else:
            val=0.
        score+=weight*val
    return score

def choose_pregame_ev(s,seat):
    opts=d._pregame_states(s,seat)
    if len(opts)==1:return opts[0],1
    static,n=ORIG_PREGAME(s,seat)
    assert n==len(opts)
    values=[expected_pregame_option(q) for q in opts]
    best_idx=max(range(len(opts)),key=lambda i:(values[i],v1.public_score(opts[i])))
    best=opts[best_idx]
    prev_idx=next(j for j,q in enumerate(opts) if q==static)
    ACTIVE.append({
      "game_id":GID,"seat":seat,"options":len(opts),
      "static_index":prev_idx,"ev_index":best_idx,
      "static_exiled":list(static.exile),"ev_exiled":list(best.exile),
      "values":[round(x,8) for x in values],
      "changed":best_idx!=prev_idx})
    return best,len(opts)

def selftest():
    v6.audit()
    root.install("current")
    v2.activate_v2(3,2,2);v6.setup(12,6)
    v1.configure(v2.SEED_BASE,3,9,3,42,18)
    example=d.State(1,("Gemstone Caverns","Ancient Tomb","Plains"),
      ("Sol Ring","Mana Vault","Plains","Mind Stone","Enlightened Tutor"))
    reverse=replace(example,library=tuple(reversed(example.library)))
    assert opening_scenarios(example)==opening_scenarios(reverse)
    assert sum(w for _,w in opening_scenarios(example))>0.999999
    assert len(d._pregame_states(example,1))>1
    print("DACK_V9_GEMSTONE_KNOWN_BOUNDARY_AUDIT_PASS",flush=True)

def play(variant,gid,early_beam=48):
    global GID,EARLY_BEAM
    GID=gid;EARLY_BEAM=int(early_beam);ACTIVE.clear()
    root.install(variant)
    v4.KNOWN.clear()
    v2.activate_v2(3,2,2)
    d._WIN_CACHE.clear()
    v6.setup(12,6)
    fair.choose_pregame=choose_pregame_ev
    start=time.time()
    try:
        q=v1.simulate(variant,gid,120,9,3,3,42,18)
    finally:
        fair.choose_pregame=ORIG_PREGAME
        d.utility_actions=fair.ORIG_UTILITY
    return {"win_turn":q["win_turn"],"keep_n":q["keep_n"],
      "seat":q["seat"],"rolls":q["rolls"],
      "choices":list(ACTIVE),"elapsed_sec":round(time.time()-start,2)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--variant",choices=("current","buck_worldmap"),default="current")
    p.add_argument("--gid",type=int,default=1)
    p.add_argument("--early-beam",type=int,default=48)
    p.add_argument("--out",default="dack_v9_gemstone.json")
    a=p.parse_args()
    selftest()
    if a.audit:return
    assert a.gid in (1,13,29),"targeted Gemstone decision cases only"
    # Compare same game seed with original untouched v6 before patching chooser.
    baseline=v6.simulate(a.variant,a.gid,12,6)
    result=play(a.variant,a.gid,a.early_beam)
    assert baseline["keep_n"]==result["keep_n"]
    rec={"status":"PASS","variant":a.variant,"game_id":a.gid,
       "baseline_turn":baseline["win_turn"],"v9_turn":result["win_turn"],
       "baseline_keep":baseline["keep_n"],"v9":result,
       "limits":["Historical Gemstone-eligible cases selected for diagnosis",
        "Future T1 sample is one card per stratified category",
        "T1 and later within-turn searches still have finite-beam action-order assumptions",
        "No effect on mulligan, cards, Dack combo or opponent interaction"]}
    Path(a.out).write_text(json.dumps(rec,indent=2)+"\n")
    print("DACK_V9_GEMSTONE_CASE_PASS",a.variant,a.gid,
      "v6",baseline["win_turn"],"v9",result["win_turn"],
      "choices",result["choices"],flush=True)
if __name__=="__main__":main()
