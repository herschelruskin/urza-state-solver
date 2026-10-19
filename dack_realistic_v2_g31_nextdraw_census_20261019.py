#!/usr/bin/env python3
"""Exact multiset census of T2 draw outcomes for Bucknard game 31's two T1 plans.

Unlike earlier three-sample reward rollouts, this enumerates EVERY possible
next physical card with multiplicity. It labels candidate success using a
beam after revealing the sampled card, not by inspecting the actual upcoming
T2 draw when choosing the policy. The library tail is deterministically
shuffled from an independent audit seed per candidate/draw to avoid using
the originally sampled (hidden) order after the top card.
"""
import argparse,hashlib,json,random
from collections import Counter
from dataclasses import replace
from pathlib import Path
import dack_realistic_information_beam_v2_20261017 as v2
v1=v2.v1;fair=v2.fair;root=v2.root;d=v2.d;m=v2.m

def seeded_lib_remainder(cards,rank,draw,rep):
    remain=list(cards)
    remain.remove(draw)
    seed=int.from_bytes(hashlib.sha256(
        ("dack-exhaustive-t2|31|"+str(rank)+"|"+draw+"|"+str(rep)).encode()).digest()[:8],"big")
    random.Random(seed).shuffle(remain)
    return tuple(remain)

def setup():
    variant="buck_worldmap";gid=31
    v2.selftest();root.install(variant);fair.install_honest_scry()
    v2.activate_v2(draws=3,t3_samples=2,t2_continuations=2)
    seed=v2.SEED_BASE+gid*1000003
    v1.configure(seed,rollout_draws=3,pass_cap=9,buck_cap=3,
                 rollout_beam=42,rollout_depth=18)
    m.set_trial_seed(seed);rng=random.Random(seed);seat=rng.randrange(4)
    fair.overridden_roll(2)
    hand,keep,_=root.choose_hand_with_free(rng,seat)
    chosen,_=fair.choose_pregame(hand,seat)
    start=fair.turnstart(chosen,1)
    fair.overridden_roll(1)
    d.utility_actions=fair.utility_without_roll
    try:w,fr=d.search_turn_frontier_many([start],beam=120,depth=22)
    finally:d.utility_actions=fair.ORIG_UTILITY
    assert not w
    states=v1.short_list(fr,3)
    assert len(states)==3
    return states,{"seat":seat,"keep":keep,"opening_hand":list(hand.hand),
                   "actual_future_t2_card_for_audit":states[0].library[0]}

def play_draw(s,draw,rank,rep,beam):
    tail=seeded_lib_remainder(s.library,rank,draw,rep)
    observed=replace(s,library=(draw,)+tail)
    st=fair.turnstart(observed,2)
    fair.overridden_roll(1)
    d.utility_actions=fair.utility_without_roll
    try:
        wins,front=d.search_turn_frontier_many([st],beam=beam,depth=24)
    finally:d.utility_actions=fair.ORIG_UTILITY
    return bool(wins)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--rank",type=int,choices=(1,2),required=True)
    p.add_argument("--tails",type=int,default=1)
    p.add_argument("--beam",type=int,default=120)
    p.add_argument("--out",required=True)
    a=p.parse_args();assert a.tails>=1 and a.beam>=40
    states,meta=setup();s=states[a.rank-1]
    cards=Counter(s.library);size=len(s.library)
    assert size>=80
    vals={}
    hit_n=0
    for j,(name,n) in enumerate(sorted(cards.items())):
        results=[play_draw(s,name,a.rank,rep,a.beam) for rep in range(a.tails)]
        vals[name]={"copies":n,"wins_per_tail":sum(results),
                    "tails":a.tails,"probability":sum(results)/a.tails}
        hit_n+=n*(sum(results)/a.tails)
        if (j+1)%10==0:
            print("CENSUS_PROGRESS",a.rank,j+1,len(cards),
                  "weighted_success",round(hit_n/(size*a.tails),5),flush=True)
    out={"status":"PASS","variant":"buck_worldmap","game_id":31,"candidate_rank":a.rank,
         "meta":meta,"sampled_tails_per_unique_card":a.tails,"beam":a.beam,
         "top_board":[{"card":d.effective_name(x),"tapped":x.tapped} for x in s.battlefield],
         "hand":list(s.hand),"score":v1.public_score(s),
         "forecast_reward_v2":v1.expected_future_value(s),
         "deck_count":size,"unique_draws":len(cards),
         "T2_win_probability_over_all_cards":hit_n/size,
         "T2_win_draws":{name:result for name,result in vals.items()
              if result["wins_per_tail"]>0},
         "all_draw_outcomes":vals,
         "note":"Oracle draw is used only for verifying historical particular outcome, never for deciding plan; this census estimates ex-ante success by full deck multiset"}
    Path(a.out).write_text(json.dumps(out,indent=2)+"\n")
    print("DACK_T2_DRAW_CENSUS_PASS",a.rank,
          round(out["T2_win_probability_over_all_cards"],6),
          "historical_forecast_reward",out["forecast_reward_v2"],flush=True)
if __name__=="__main__":main()
