#!/usr/bin/env python3
"""Experimental Realistic Beam v9 -- optimize Gemstone Caverns pregame decisions.

The existing policy chooses a Caverns pregame configuration with a public
resource heuristic. V9 chooses among the SAME legal options by expected T1,
T2 and T3 Dack-cast reward, integrating over STRATIFIED UNKNOWN T1 draws.

Crucially, Gemstone's action and exiled card are COMMITTED before a single
real draw. No future hidden draw is used in option selection. The normal
T1/T2/T3 Realistic Beam decision policy, mulligans and chance semantics are
unchanged. Expensive option evaluation is run ONLY when multiple real
pregame options exist.

The legacy Full Beam and v6/v7 implementations are unchanged. Finite
forecast beams and residual in-turn hidden-draw oracle remain limitations.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,time
from dataclasses import replace
from collections import Counter
import dack_realistic_v7_rollout_fidelity_20261019 as v7

v6=v7.v6;v2=v7.v2;v1=v7.v1;fair=v7.fair
root=v7.root;d=v7.d;v4=v6.v4
ORIGINAL_CHOOSE=fair.choose_pregame
COUNTS={}
T1_BEAM=42;T1_DEPTH=18;SIMULATED_FUTURE_CANDIDATES=1

def reset():
    COUNTS.clear()
    COUNTS.update({"pregame_alternative_games":0,
                   "pregame_options_total":0,
                   "pregame_changed_decisions":0,
                   "pregame_rollouts":0,
                   "decision_logs":[]})

def hypothetical_t1(opt,card,index):
    # Construct a counterfactual first draw from multiset, not actual top.
    # Every candidate gets the same shuffled tail for the same card/index.
    if v4.known_top(opt)==card:
        return d.draw(opt,1)
    remaining=list(opt.library)
    remaining.remove(card)
    remaining.sort()
    seed=int.from_bytes(hashlib.sha256(
        f"{v1.TRIAL_SEED}|v9-pregame|{index}|{card}|{len(remaining)}".encode()
    ).digest()[:16],"big")
    random.Random(seed).shuffle(remaining)
    return d.draw(replace(opt,library=(card,)+tuple(remaining)),1)

def expected_option(opt,draw_plan):
    ev=0.
    for idx,(card,weight,known) in enumerate(draw_plan):
        trial=hypothetical_t1(opt,card,idx)
        fair.overridden_roll(1)
        d.utility_actions=fair.utility_without_roll
        try:
            wins,fr=d.search_turn_frontier_many(
                [trial],beam=T1_BEAM,depth=T1_DEPTH)
        finally:
            d.utility_actions=fair.ORIG_UTILITY
        COUNTS["pregame_rollouts"]+=1
        if wins:
            value=2.0
        elif fr:
            # A T1 continuation needs to be chosen before its real T2 draw.
            # Expected_future_value already integrates weighted T2/T3.
            candidates=v1.short_list(fr,SIMULATED_FUTURE_CANDIDATES)
            value=max(v1.expected_future_value(x) for x in candidates)
        else:
            value=0.
        ev+=weight*value
    return ev

def choose_pregame_ev(state,seat):
    opts=d._pregame_states(state,seat)
    if len(opts)<=1:
        return ORIGINAL_CHOOSE(state,seat)
    COUNTS["pregame_alternative_games"]+=1
    COUNTS["pregame_options_total"]+=len(opts)
    # Shared counterfactual card identities/weights for all pregame options.
    # A Gemstone pregame exile removes a HAND card, never a LIBRARY card.
    assert all(sorted(x.library)==sorted(opts[0].library) for x in opts)
    draw_plan=v6.weighted_plan(opts[0])
    assert draw_plan and abs(sum(w for _,w,_ in draw_plan)-1)<1e-8
    assessed=[]
    for opt in opts:
        expected=expected_option(opt,draw_plan)
        assessed.append((expected,v1.public_score(opt),opt))
    chosen=max(assessed,key=lambda z:(z[0],z[1]))[2]
    simple,n=ORIGINAL_CHOOSE(state,seat)
    assert n==len(opts)
    same=v1.private_order_free_signature(chosen)==v1.private_order_free_signature(simple)
    COUNTS["pregame_changed_decisions"]+=int(not same)
    COUNTS["decision_logs"].append({
        "seat":seat,"hand":list(state.hand),"options":len(opts),
        "original_exile":list(simple.exile),
        "ev_exile":list(chosen.exile),
        "changed":not same,
        "scores":[{"expected":round(ev,7),"static":round(sc,3),
                   "exile":list(x.exile),
                   "gemstone_deployed":any(q.name=="Gemstone Caverns" for q in x.battlefield)}
                  for ev,sc,x in assessed]})
    return chosen,n

def audit():
    v7.audit()
    root.install("current")
    v2.activate_v2(3,2,2)
    v6.setup(12,6)
    v1.configure(v2.SEED_BASE,3,9,3,42,18)
    state=d.State(1,("Gemstone Caverns","Ancient Tomb","Sol Ring","Plains"),
                  ("Mana Vault","Moonsilver Key","Lotus Petal","Plains"))
    before=d._pregame_states(state,2)
    assert len(before)>1
    reversed_state=replace(state,library=tuple(reversed(state.library)))
    assert len(d._pregame_states(reversed_state,2))==len(before)
    # Literal option evaluation is only seeded from game seed + multiset.
    plan=v6.weighted_plan(before[0]);reversed_plan=v6.weighted_plan(d._pregame_states(reversed_state,2)[0])
    assert plan==reversed_plan
    for i,(name,_,_) in enumerate(plan):
        q=hypothetical_t1(before[0],name,i)
        z=hypothetical_t1(d._pregame_states(reversed_state,2)[0],name,i)
        assert q==z
    print("DACK_V9_PREGAME_EV_ORDER_INDEPENDENCE_PASS",flush=True)

def simulate(variant,gid):
    reset()
    fair.choose_pregame=choose_pregame_ev
    try:
        rec=v7.one(variant,gid,96,24)
    finally:
        fair.choose_pregame=ORIGINAL_CHOOSE
        d.utility_actions=fair.ORIG_UTILITY
    return {"game_id":gid,"win_turn":rec["win_turn"],
            "keep_n":rec["keep_n"],"seat":rec["seat"],
            "rolls":rec["rolls"],"pregame_audit":dict(COUNTS),
            "turn_audit":rec["turn_audit"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--variant",choices=("current","buck_worldmap"),default="current")
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--games",type=int,default=4)
    p.add_argument("--out",default="dack_v9_pregame.json.gz")
    a=p.parse_args()
    audit()
    if a.audit:return
    assert a.shard>=0 and a.games>=1
    rows=[];start=time.time()
    for j in range(a.games):
        gid=a.shard*a.games+j
        z=simulate(a.variant,gid)
        rows.append(z)
        print("DACK_V9_PREGAME_GAME",a.variant,gid,z["win_turn"],
              "options",z["pregame_audit"]["pregame_options_total"],
              "changed",z["pregame_audit"]["pregame_changed_decisions"],
              flush=True)
    cards=v2.trial.VARIANTS[a.variant]
    payload={"schema":"dack_v9_pregame_ev","variant":a.variant,
      "seed_base":v2.SEED_BASE,"shard":a.shard,"games":a.games,
      "deck_sha256":hashlib.sha256("\n".join(cards).encode()).hexdigest(),
      "actual_beam":120,"forecast_beam":96,"forecast_depth":24,
      "stratified_pregame_draws":12,
      "counts":{str(k):v for k,v in Counter(r["win_turn"] for r in rows).items()},
      "elapsed_seconds":round(time.time()-start,3),"rows":rows}
    with gzip.open(a.out,"wt",encoding="utf8") as f:json.dump(payload,f,separators=(",",":"))
    print("DACK_V9_PREGAME_EV_SHARD_PASS",a.variant,a.games,flush=True)

if __name__=="__main__":main()
