#!/usr/bin/env python3
"""Forensic reward trace on matched Full-Beam-only T2 games.

Replays v2 exactly, captures T1 candidate frontier and selected state without
changing the policy, then (offline, AFTER gameplay) reveals actual next draw
to ask which alternative T1 states would have won on T2. This hindsight
diagnosis is NEVER fed back into the live simulated policy.

Reports end-turn floated mana score bias, strategy labels, sampled T2 reward
sparsity, actual next draw, and whether oracle winning candidate was retained.
"""
import argparse,json,random,collections
from dataclasses import replace
from pathlib import Path
import dack_realistic_information_beam_v2_20261017 as v2

v1=v2.v1
fair=v2.fair
root=v2.root
d=v2.d
m=v2.m
N=36

def fmt(s):
    next_turn=replace(s,turn=min(3,s.turn+1))
    nxt=d.untap_and_begin(next_turn)
    return {
      "hand":list(s.hand),
      "battlefield":[{"card":d.effective_name(p),"tap":p.tapped,
                      "counters":p.counters} for p in s.battlefield],
      "land_played":s.land_played,
      "float_mana":{"w":s.w,"c":s.c,"any":s.any,"restricted_artifact":s.restricted_artifact,
                    "restricted_legend":s.restricted_legend,"restricted_dack_white":s.restricted_dack_white},
      "floating_total":s.w+s.c+s.any+s.restricted_artifact+s.restricted_legend+s.restricted_dack_white,
      "banked":{"treasures":s.treasures,"spawn":s.spawn,"permanents":len(s.battlefield)},
      "current_score":round(v1.public_score(s),3),
      "score_after_pool_reset":round(v1.public_score(nxt),3),
      "score_inflation_due_floating":round(v1.public_score(s)-v1.public_score(nxt),3),
      "true_next_draw":s.library[0] if s.library else None}

def oracle_next(s,beam=160,strict_upkeep=False):
    q=d.untap_and_begin(replace(s,turn=2))
    q=d.add_opponent_cycle_resources(q)
    options=list(d.mana_vault_upkeep_options(q))
    if strict_upkeep:
        options=[max(options,key=v1.public_score)] if options else [q]
    starts=[d.begin_first_main(d.saga_advance(d.draw(a,1))) for a in options]
    fair.overridden_roll(1)
    d.utility_actions=fair.utility_without_roll
    try:
        wins,_=d.search_turn_frontier_many(starts,beam=beam,depth=24)
    finally:
        d.utility_actions=fair.ORIG_UTILITY
    return bool(wins)

def replay(variant,gid,cap_probe):
    v2.selftest()
    root.install(variant)
    fair.install_honest_scry()
    v2.activate_v2(draws=3,t3_samples=2,t2_continuations=2)
    d._WIN_CACHE.clear()
    seed=v2.SEED_BASE+int(gid)*1000003
    rng=random.Random(seed)
    seat=rng.randrange(4)
    m.set_trial_seed(seed)
    fair.overridden_roll(2)
    state,keep,mull=root.choose_hand_with_free(rng,seat)
    information={"seat":seat,"kept_cards":list(state.hand),
                 "hand_size":keep,"game_id":gid,
                 "first_real_card":state.library[0],
                 "second_real_card":state.library[1],
                 "candidate_count_reached":None}
    capture={}
    original=v1.select_plan
    def logged(front,pre,turn):
        result=original(front,pre,turn)
        if turn==1:
            cap=max(36,cap_probe)
            candidates=v1.short_list(front,cap)
            selected=result[0]
            capture["states"]=candidates
            capture["selected"]=selected
            capture["original_frontier_size"]=len(front)
            capture["t1_pre_roll_states"]=len(pre)
            capture["chosen_template"]=result[1] is not None
        return result
    v1.select_plan=logged
    try:
        result=v1.simulate(variant,gid,120,9,3,3,42,18)
    finally:
        v1.select_plan=original
    assert len(capture["states"])>0,(variant,gid)
    info_states=capture["states"][:cap_probe]
    candidates=[]
    for rank,s in enumerate(info_states):
        x=fmt(s)
        x.update({"candidate_rank":rank+1,
                  "selected":s==capture["selected"]})
        x["oracle_T2_if_next_card_revealed"]=oracle_next(s,160,False)
        x["oracle_T2_if_upkeep_committed"]=oracle_next(s,160,True)
        candidates.append(x)
    selected=capture["selected"]
    selected_x=fmt(selected)
    selected_x["oracle_T2_if_next_card_revealed"]=oracle_next(selected,160,False)
    # How sparse would the sampled T2 observations be? Observe the sampled
    # (never the actual) next cards in the policy.
    sampled_cards=[]
    for k in range(3):
        q=v1.hypothetical_next_start(selected,k)
        sampled_cards.append(next(iter(collections.Counter(q.hand)-collections.Counter(selected.hand)),None))
    return {
      "status":"PASS","variant":variant,"game_id":gid,"seed":seed,
      "opening_info":information,
      "gameplay_v2":{"win_turn":result["win_turn"],"keep_n":result["keep_n"],
                     "turn_audit":result["turn_audit"]},
      "frontier_counts":{"end_states":capture["original_frontier_size"],
                         "candidate_probe":len(candidates),
                         "pre_roll_states":capture["t1_pre_roll_states"]},
      "top_candidates":candidates,
      "selected_state":selected_x,
      "sampled_hypothetical_next_cards":sampled_cards,
      "best_T2_in_top9":sum(x["oracle_T2_if_next_card_revealed"] for x in candidates[:9]),
      "best_T2_in_top36":sum(x["oracle_T2_if_next_card_revealed"] for x in candidates),
      "best_T2_committed_upkeep_top36":sum(x["oracle_T2_if_upkeep_committed"] for x in candidates),
      "selected_T2_works":selected_x["oracle_T2_if_next_card_revealed"],
      "average_score_inflation_top9":round(sum(x["score_inflation_due_floating"] for x in candidates[:9])/min(9,len(candidates)),3),
      "debug_no_policy_change":True}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--variant",choices=("current","buck_worldmap"),required=True)
    ap.add_argument("--gid",type=int,required=True)
    ap.add_argument("--probe",type=int,default=18)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    assert a.gid in (0,1,11,17,22,31) and 9<=a.probe<=36
    x=replay(a.variant,a.gid,a.probe)
    Path(a.out).write_text(json.dumps(x,indent=2)+"\n")
    print("DACK_REWARD_CAUSAL_TRACE_PASS",json.dumps({
        "variant":a.variant,"gid":a.gid,"t1_front":x["frontier_counts"],
        "actual_next":x["opening_info"]["second_real_card"],
        "selected_wins_T2":x["selected_T2_works"],
        "winnable_T2_in_top9":x["best_T2_in_top9"],
        "winnable_T2_in_probe":x["best_T2_in_top36"],
        "avg_float_score_inflation":x["average_score_inflation_top9"]}),flush=True)

if __name__=="__main__":main()
