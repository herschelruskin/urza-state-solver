#!/usr/bin/env python3
"""Direct T1 failure trace: locate legal T1 setups that win after the REAL T2 draw.

The real draw is deliberately used as an audit-only counterfactual label, NEVER
for game planning. Compare whether the Realistic Beam (nonclairvoyant) planner
1) admitted that T1 state into top9/top24, 2) valued it highly, 3) chose it.

Trace runs a no-random-Bucknard candidate probe; that omission is flagged.
"""
import argparse,json,random,hashlib
from dataclasses import replace
from pathlib import Path
import dack_realistic_information_beam_v2_20261017 as v2
v1=v2.v1
fair=v2.fair
root=v2.root
d=v2.d
m=v2.m

FULL_T2_MISS={"current":{0,1,22},"buck_worldmap":{0,1,22,31}}

def compact(q):
    # This summary is for human-readable debugging only.
    return {
      "hand":list(q.hand),
      "battlefield":[str(p.name)+("*" if p.tapped else "")+
         (":"+str(p.counters) if p.counters else "") for p in q.battlefield],
      "floating":{"w":q.w,"c":q.c,"any":q.any,
                  "legend":q.restricted_legend,"artifact":q.restricted_artifact},
      "treasures":q.treasures,"spawn":q.spawn,
      "land_played":q.land_played,
      "actual_next_draw_AUDIT_ONLY":q.library[0] if q.library else None
    }

def prospective(q):
    # Benchmark current score against what it says once nonbankable mana is
    # lost. The latter does not use information from the unseen card.
    prepared=d.untap_and_begin(replace(q,turn=q.turn+1))
    return round(v1.public_score(prepared),3)

def actual_t2_probe(q,beam=120):
    if not q.library:return False
    nextstate=fair.turnstart(q,2)
    fair.overridden_roll(1)
    d.utility_actions=fair.utility_without_roll
    try:
        winners,front=d.search_turn_frontier_many([nextstate],beam=beam,depth=24)
    finally:
        d.utility_actions=fair.ORIG_UTILITY
    return bool(winners)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--variant",choices=tuple(FULL_T2_MISS),required=True)
    p.add_argument("--gid",type=int,required=True)
    p.add_argument("--max-candidates",type=int,default=24)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    assert a.gid in FULL_T2_MISS[a.variant]
    v2.selftest()
    root.install(a.variant)
    fair.install_honest_scry()
    v2.activate_v2(3,2,2)
    seed=v2.SEED_BASE+a.gid*1000003
    v1.configure(seed,3,9,3,42,18)
    m.set_trial_seed(seed)
    rng=random.Random(seed)
    seat=rng.randrange(4)
    fair.overridden_roll(2)
    keep_state,keep,audit=root.choose_hand_with_free(rng,seat)
    pre,n_pre=fair.choose_pregame(keep_state,seat)
    first=fair.turnstart(pre,1)
    pre_roll={}
    def blocked(x):
        if any(d.effective_name(z)==fair.PURSE and not z.tapped for z in x.battlefield):
            pre_roll[v1.private_order_free_signature(x)]=x
        return fair.utility_without_roll(x)
    fair.overridden_roll(1)
    d.utility_actions=blocked
    try:
        wins,front=d.search_turn_frontier_many([first],beam=120,depth=22)
    finally:
        d.utility_actions=fair.ORIG_UTILITY
    assert not wins,("Unexpected T1 win in failure case",a.variant,a.gid)
    states=v1.short_list(front,a.max_candidates)
    selected,activation,plans,selection_value,nn=v1.select_plan(
        front,list(pre_roll.values()),1)
    assert selected is not None
    selected_sig=v1.private_order_free_signature(selected)
    payload=[]
    for index,q in enumerate(states):
        actual=actual_t2_probe(q)
        payload.append({
            "rank_by_original_score":index+1,
            "selected":selected_sig==v1.private_order_free_signature(q),
            "original_heuristic_score":round(v1.public_score(q),3),
            "score_after_floating_mana_expires":prospective(q),
            "actual_T2_cast_if_committed_AUDIT_ONLY":int(actual),
            "state":compact(q)
        })
    all_sorted=sorted(payload,key=lambda q:q["score_after_floating_mana_expires"],reverse=True)
    for rank,x in enumerate(all_sorted,1):x["rank_by_stable_score"]=rank
    chosen=[q for q in payload if q["selected"]]
    chosen_r=chosen[0] if chosen else {
        "state":compact(selected),"actual_T2_cast_if_committed_AUDIT_ONLY":
            int(actual_t2_probe(selected)),
        "score_after_floating_mana_expires":prospective(selected),
        "original_heuristic_score":round(v1.public_score(selected),3)}
    results={
        "status":"PASS","variant":a.variant,"game_id":a.gid,
        "intended_use":"Audit-only use of actual future draw; no hidden draw used for selection",
        "seat":seat,"keep_n":keep,"kept_hand":list(keep_state.hand),
        "opening_draw":first.hand,
        "possible_T1_endings":len(front),
        "tested_top_candidates":len(payload),
        "top9_T2_witness_count":sum(q["actual_T2_cast_if_committed_AUDIT_ONLY"] for q in payload[:9]),
        "top24_T2_witness_count":sum(q["actual_T2_cast_if_committed_AUDIT_ONLY"] for q in payload),
        "chosen_v2":chosen_r,
        "v2_choice_value":round(selection_value,6),
        "bucknard_activation_chosen":activation is not None,
        "all_candidates":payload,
        "limits":[
          "This is a counterfactual diagnostic, not an honest policy",
          "No Bucknard die resolution in hypothetical T2 probes",
          "One state with actual next draw is tested by normal inner beam 120; no full 240-width reconstruction",
          "Selecting more than top24 states could reveal an omitted T2 witness",
          "Outcome differences may also arise from scry policy and earlier bottoming choices"
        ]}
    Path(a.out).write_text(json.dumps(results,indent=2)+"\n")
    print("DACK_T1_COUNTERFACTUAL_TRACE_PASS",json.dumps({
        "variant":a.variant,"gid":a.gid,"keep":keep,
        "top9_wins":results["top9_T2_witness_count"],
        "top24_wins":results["top24_T2_witness_count"],
        "selected_wins":chosen_r["actual_T2_cast_if_committed_AUDIT_ONLY"],
        "selected_score":chosen_r["original_heuristic_score"],
        "selected_stable":chosen_r["score_after_floating_mana_expires"]
    }),flush=True)

if __name__=="__main__":main()
