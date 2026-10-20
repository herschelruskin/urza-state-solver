#!/usr/bin/env python3
"""Realistic Dack v8: information-aware upkeep Mana Vault commitment.

When untap Mana Vault can be paid for during upkeep, its payment, tap actions,
and chosen source of mana MUST be decided before the draw step. v6 chose only
by static resource score. This experiment selects among those same LEGAL
upkeep outcomes by a chance-weighted expected Dack deployment score,
computed from a hidden-order-independent stratified draw distribution.

The full-beam legacy, v6 and all card rules are untouched. Turn 1, Gemstone
pregame, London mulligans, and the end-of-turn planner are unchanged.

Known cards on top (from an actual tutor) remain known; all other future cards
are chosen using the library multiset, never the actual top-card identity.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,time
from collections import Counter
from dataclasses import replace
import dack_realistic_v6_stratified_reward_20261019 as v6

v1=v6.v1;v2=v6.v2;v4=v6.v4;root=v6.root;fair=v6.fair;d=v6.d;m=v6.m
ORIGINAL_TURNSTART=fair.turnstart
COUNTS={}
FORECAST_BEAM=42
FORECAST_DEPTH=18
FUTURE_DRAWS=12

def reset_counters():
    COUNTS.clear()
    COUNTS.update({"upkeeps":0,"multiple_upkeep_options":0,
        "different_upkeep_decision":0,"upkeep_rollouts":0,
        "upkeep_options_max":0,"upkeep_options_evaluated":0,
        "upkeep_choice_log":[]})

def draw_current_turn_after_upkeep(q,card,sample_index,known):
    """Resolve only after upkeep payment is fixed; never reveal actual unknown top."""
    if known:
        assert v4.known_top(q)==card and q.library[0]==card
        staged=q  # legally top-known; no ability to peek at remaining tail
    else:
        tail=list(q.library)
        tail.remove(card)
        tail.sort()
        seed=int.from_bytes(hashlib.sha256(
            f"{v1.TRIAL_SEED}|upkeep-tail|{q.turn}|{sample_index}|{card}|{len(tail)}".encode()
        ).digest()[:16],"big")
        random.Random(seed).shuffle(tail)
        staged=replace(q,library=(card,)+tuple(tail))
    return d.begin_first_main(d.saga_advance(d.draw(staged,1)))

def evaluate_upkeep_option(q):
    """Ex ante deployment chances from one committed upkeep state."""
    plan=v6.weighted_plan(q)
    if not plan:
        return (0.,v1.public_score(q))
    exp=0.
    for i,(card,weight,known) in enumerate(plan):
        drawn=draw_current_turn_after_upkeep(q,card,i,known)
        fair.overridden_roll(1)
        d.utility_actions=fair.utility_without_roll
        try:
            wins,front=d.search_turn_frontier_many(
                [drawn],beam=FORECAST_BEAM,depth=FORECAST_DEPTH)
        finally:
            d.utility_actions=fair.ORIG_UTILITY
        COUNTS["upkeep_rollouts"]+=1
        if wins:
            # On T2 a win also counts toward cumulative T3.
            payoff=1.5 if q.turn==2 else 0.5
        elif q.turn==2 and front:
            # After T2 draw, any T3 decision must itself be made without T3 card.
            payoff=0.5*v2.remaining_t3_chance(front)
        else:
            payoff=0.
        # Only a tiny resource tiebreak, never larger than a modest true win chance.
        if not wins and front:
            payoff+=min(.002,max(0.,v1.public_score(max(front,key=v1.public_score))/200000.))
        exp+=weight*payoff
    return exp,v1.public_score(q)

def choose_upkeep_option(options):
    """Return legal paid/no-pay choice before hidden draw, with audit."""
    if len(options)==1:
        return options[0]
    COUNTS["multiple_upkeep_options"]+=1
    COUNTS["upkeep_options_max"]=max(COUNTS["upkeep_options_max"],len(options))
    # Deduplicate exact states, not results of observing any draw.
    distinct={}
    for q in options:
        distinct[v1.private_order_free_signature(q)]=q
    options=list(distinct.values())
    simple=max(options,key=fair.heuristic)
    evaluated=[]
    for q in options:
        ev,static=evaluate_upkeep_option(q)
        evaluated.append((ev,static,q))
    COUNTS["upkeep_options_evaluated"]+=len(evaluated)
    best=max(evaluated,key=lambda x:(x[0],x[1]))[2]
    if v1.private_order_free_signature(best)!=v1.private_order_free_signature(simple):
        COUNTS["different_upkeep_decision"]+=1
    COUNTS["upkeep_choice_log"].append({
        "turn":options[0].turn,
        "options":len(options),
        "old_score":round(fair.heuristic(simple),5),
        "new_score":round(fair.heuristic(best),5),
        "old_upkeep_choice":str(tuple((d.effective_name(x),x.tapped) for x in simple.battlefield)),
        "new_upkeep_choice":str(tuple((d.effective_name(x),x.tapped) for x in best.battlefield)),
        "ev_values":[round(ev,6) for ev,_,_ in evaluated],
        "changed":v1.private_order_free_signature(best)!=v1.private_order_free_signature(simple)})
    return best

def turnstart_with_upkeep_ev(pre,turn):
    if turn==1:return ORIGINAL_TURNSTART(pre,turn)
    COUNTS["upkeeps"]+=1
    q=d.untap_and_begin(replace(pre,turn=turn))
    q=d.add_opponent_cycle_resources(q)
    options=list(d.mana_vault_upkeep_options(q))
    committed=choose_upkeep_option(options) if options else q
    return d.begin_first_main(d.saga_advance(d.draw(committed,1)))

def audit():
    v6.audit()
    root.install("current")
    v2.activate_v2(3,2,2)
    v6.setup(12,6)
    v1.configure(v2.SEED_BASE,3,9,3,42,18)
    reset_counters()
    # At an actual upkeep the player can either decline or pay {4} to untap,
    # but cannot use new information from the subsequent draw to decide.
    s=d.State(2,(),("Sol Ring","Plains","Mana Vault","Ancient Tomb"),
       battlefield=(d.Perm("Mana Vault",True),d.Perm("Ancient Tomb",False),
                    d.Perm("Sol Ring",False)),c=0)
    t=replace(s,library=tuple(reversed(s.library)))
    opts=list(d.mana_vault_upkeep_options(s))
    reversed_opts=list(d.mana_vault_upkeep_options(t))
    assert len(opts)>1 and len(opts)==len(reversed_opts)
    assert any(any(d.effective_name(p)=="Mana Vault" and not p.tapped
       for p in q.battlefield) for q in opts)
    # The calculator and decision must be invariant to permuting unknown cards.
    q1=choose_upkeep_option(opts)
    q2=choose_upkeep_option(reversed_opts)
    assert v1.private_order_free_signature(q1)==v1.private_order_free_signature(q2)
    assert abs(sum(weight for _,weight,_ in v6.weighted_plan(q1))-1)<1e-9
    root.install("buck_worldmap")
    assert len(v2.trial.VARIANTS["buck_worldmap"])==99
    assert all(c not in v2.trial.VARIANTS["buck_worldmap"] for c in ("Mana Crypt","Jeweled Lotus"))
    print("DACK_V8_UPKEEP_HIDDEN_ORDER_AUDIT_PASS",flush=True)

def simulate(variant,gid,beam=120,forecast_beam=42,forecast_depth=18,draws=12):
    global FORECAST_BEAM,FORECAST_DEPTH,FUTURE_DRAWS
    FORECAST_BEAM=forecast_beam;FORECAST_DEPTH=forecast_depth;FUTURE_DRAWS=draws
    root.install(variant)
    v4.KNOWN.clear()
    v2.activate_v2(3,2,2)
    d._WIN_CACHE.clear()
    v6.setup(draws,6)
    assert d.cast_actions is v4.known_cast_actions
    reset_counters()
    fair.turnstart=turnstart_with_upkeep_ev
    try:
        q=v1.simulate(variant,gid,beam,9,3,3,42,18)
    finally:
        fair.turnstart=ORIGINAL_TURNSTART
        d.utility_actions=fair.ORIG_UTILITY
    return {"game_id":gid,"win_turn":q["win_turn"],"seat":q["seat"],
        "keep_n":q["keep_n"],"rolls":q["rolls"],
        "rollout_calls":q["planning_counts"]["rollout_calls"],
        "upkeep_audit":dict(COUNTS),"turn_audit":q["turn_audit"]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",action="store_true")
    ap.add_argument("--variant",choices=("current","buck_worldmap"),default="current")
    ap.add_argument("--shard",type=int,default=0)
    ap.add_argument("--games",type=int,default=4)
    ap.add_argument("--forecast-beam",type=int,default=42)
    ap.add_argument("--forecast-depth",type=int,default=18)
    ap.add_argument("--draws",type=int,default=12)
    ap.add_argument("--out",default="dack_v8_upkeep.json.gz")
    a=ap.parse_args()
    audit()
    if a.audit:return
    assert a.shard>=0 and a.games>=1
    rows=[]
    for j in range(a.games):
        gid=a.shard*a.games+j
        result=simulate(a.variant,gid,forecast_beam=a.forecast_beam,
            forecast_depth=a.forecast_depth,draws=a.draws)
        rows.append(result)
        print("DACK_V8_UPKEEP_GAME",a.variant,gid,result["win_turn"],
              "choices",result["upkeep_audit"]["multiple_upkeep_options"],
              "changes",result["upkeep_audit"]["different_upkeep_decision"],flush=True)
    payload={"schema":"dack_upkeep_legal_ev_v8","variant":a.variant,
      "games":a.games,"shard":a.shard,"seed_base":v2.SEED_BASE,
      "forecast_beam":a.forecast_beam,"forecast_depth":a.forecast_depth,
      "stratified_draws":a.draws,"actual_beam":120,
      "deck_sha256":hashlib.sha256("\n".join(v2.trial.VARIANTS[a.variant]).encode()).hexdigest(),
      "counts":{str(k):v for k,v in Counter(q["win_turn"] for q in rows).items()},
      "rows":rows}
    with gzip.open(a.out,"wt",encoding="utf8") as f:json.dump(payload,f,separators=(",",":"))
    print("DACK_V8_UPKEEP_SHARD_PASS",a.variant,a.games,flush=True)

if __name__=="__main__":main()
