#!/usr/bin/env python3
"""Trace lost Dack deployments to isolate prune/score/rollout/beam issues.

Diagnostic only: use *actual next draw* solely to label candidate states after
computing pre-draw scores. Never use oracle labels to pick the player policy.
Candidates include T1 full 120 frontier, top 9 and top 24 ranked on public
state, and a separate original beam=240 (with pregame alternatives).
"""
from __future__ import annotations
import argparse,hashlib,json,random
from collections import Counter
from pathlib import Path
import dack_realistic_information_beam_v2_20261017 as v2

v1=v2.v1
fair=v2.fair
root=v2.root
d=v2.d
m=v2.m

def snap(s):
    return {
      "turn":s.turn,"hand":list(s.hand),
      "top_unknown_for_audit":list(s.library[:3]),
      "board":[{"name":d.effective_name(p),"tapped":p.tapped,
                "counters":p.counters,"aux":p.aux} for p in s.battlefield],
      "mana":{"white":s.w,"colorless":s.c,"flexible":s.any,
              "restricted_artifact":s.restricted_artifact,
              "restricted_legend":s.restricted_legend,
              "restricted_dack_white":s.restricted_dack_white},
      "treasures":s.treasures,"spawn":s.spawn,"land_played":s.land_played,
      "library_size":len(s.library),
      "resource_score":round(float(v1.public_score(s)),3)
    }

def pass_mana_expiring(s):
    q=d.untap_and_begin(v1.replace(s,turn=s.turn+1))
    return float(v1.public_score(q))

def candidate_label(s,beam):
    # This intentionally uses actual future draw, post-policy for diagnosis
    # only: it measures whether the candidate was in fact salvageable.
    q=fair.turnstart(s,s.turn+1)
    fair.overridden_roll(1)
    d.utility_actions=fair.utility_without_roll
    try:
        wins,_=d.search_turn_frontier_many([q],beam=beam,depth=24)
    finally:
        d.utility_actions=fair.ORIG_UTILITY
    return bool(wins)

def frontier(starts,beam):
    fair.overridden_roll(1)
    d.utility_actions=fair.utility_without_roll
    try:
        wins,fr=d.search_turn_frontier_many(starts,beam=beam,depth=22)
    finally:
        d.utility_actions=fair.ORIG_UTILITY
    return wins,fr

def evaluate(variant,gid,top_count,oracle_beam):
    root.install(variant)
    fair.install_honest_scry()
    v2.activate_v2(draws=3,t3_samples=2,t2_continuations=2)
    seed=v2.SEED_BASE+gid*1000003
    m.set_trial_seed(seed)
    chooser=random.Random(seed)
    seat=chooser.randrange(4)
    fair.overridden_roll(2)
    st,keep_n,mull_audit=root.choose_hand_with_free(chooser,seat)
    full_pregame=d._pregame_states(st,seat)
    chosen,_=fair.choose_pregame(st,seat)
    real_t1=fair.turnstart(chosen,1)
    wins,fr=frontier([real_t1],120)
    assert not wins,("already wins T1; no gap")
    short=v1.short_list(fr,9)
    longer=v1.short_list(fr,24)
    v1.configure(seed,rollout_draws=3,pass_cap=9,buck_cap=3,
                 rollout_beam=42,rollout_depth=18)
    candidates=v1.short_list(fr,top_count)
    details=[]
    for rank,s in enumerate(candidates):
        prospective=v1.expected_future_value(s)
        actual=candidate_label(s,oracle_beam)
        details.append({
          "rank":rank+1,"in_cap9":d.key(s) in {d.key(x) for x in short},
          "in_cap24":d.key(s) in {d.key(x) for x in longer},
          "t2_winnable_given_actual_draw":actual,
          "prior_T2_T3_reward":round(prospective,7),
          "score_in_turn":round(v1.public_score(s),4),
          "score_next_turn_before_draw":round(pass_mana_expiring(s),4),
          "snapshot":snap(s)})
        print("TRACE_CANDIDATE",variant,gid,rank+1,"actual_win",int(actual),
              "prior_value",round(prospective,6),"score",round(v1.public_score(s),3),
              flush=True)
    # Full Beam can choose among all original Gemstone pregame states.
    # Enumerate whether pregame branching is material for this case.
    alternatives=[]
    for i,pregame in enumerate(full_pregame):
        start=fair.turnstart(pregame,1)
        w,f=frontier([start],240)
        alternatives.append({
          "pregame_index":i,
          "pregame_board":[q.name for q in pregame.battlefield],
          "pregame_hand":list(pregame.hand),
          "t1_frontier_count":len(f),"t1_wins":bool(w),
          "top_3_t1":[snap(x) for x in f[:3]],
          "visible_heuristic":round(v1.public_score(pregame),3)})
    summary={
        "variant":variant,"game_id":gid,
        "seat":seat,"keep_n":keep_n,
        "start_hand":list(st.hand),"start_library_top_for_audit":list(st.library[:4]),
        "pregame_choice":snap(chosen),"pregame_alternatives":alternatives,
        "t1_frontier_count":len(fr),
        "top9_unbiased_actual_T2_hits":sum(z["t2_winnable_given_actual_draw"]
                                           for z in details if z["in_cap9"]),
        "top24_unbiased_actual_T2_hits":sum(z["t2_winnable_given_actual_draw"]
                                           for z in details if z["in_cap24"]),
        "topN_actual_T2_hits":sum(z["t2_winnable_given_actual_draw"] for z in details),
        "first_T2_winning_rank":next((z["rank"] for z in details
                                    if z["t2_winnable_given_actual_draw"]),None),
        "candidates":details,
        "limitations":[
          "Oracle labels use realized next card ONLY in this diagnostic, never in policy",
          "Independent per-candidate future replay may differ from joint Full Beam's beam",
          "V2 and Full Beam use different 120/240 widths and Gemstone pregame policy",
          "No complete action histories, only state snapshots",
          "Pre-roll activation disabled for this T1 resource-path audit"]}
    return summary

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--variant",choices=("current","buck_worldmap"),required=True)
    p.add_argument("--gid",type=int,required=True)
    p.add_argument("--candidate-count",type=int,default=24)
    p.add_argument("--oracle-beam",type=int,default=120)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    assert a.gid in (0,1,22,31) and a.candidate_count>=9
    v2.selftest()
    result=evaluate(a.variant,a.gid,a.candidate_count,a.oracle_beam)
    Path(a.out).write_text(json.dumps(result,indent=2)+"\n")
    print("DACK_CANDIDATE_ACTUAL_DRAW_DIAGNOSTIC_PASS",
          a.variant,a.gid,"candidate_hits",result["topN_actual_T2_hits"],
          "first_hit",result["first_T2_winning_rank"],flush=True)

if __name__=="__main__":main()
