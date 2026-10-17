#!/usr/bin/env python3
"""Dack Realistic Beam v1 -- information-aware beam with expected-draw commitment.

The historical Oct 16 full-beam benchmark and its source are left intact.
This fork retains beam search INSIDE turns, but:
  1. Commits to one turn-ending line using a chance-aware evaluation across
     sampled possible NEXT draws, never by looking at the actual upcoming card.
  2. Resolves Bucknard with an independent fair d4 ONLY after committing
     activation payment and KCI response using expected outcomes.
  3. Commits Gemstone pregame and Mana Vault upkeep before their draws.
  4. Preserves visible-only scry handling inherited from fair-play v1.

Caveat: this is a heuristic imperfect-information rollout policy, not a fully
information-set solver. Some mid-turn draw/tutor actions still use original
perfect-order beam transitions. The "full beam" upper-bound proxy is frozen.
"""
from __future__ import annotations
import argparse, gzip, hashlib, json, math, random, time
from collections import Counter
from dataclasses import replace
import dack_fair_random_deployment_v1_20261016 as fair

root=fair.root
trial=fair.trial
d=fair.d
m=fair.m
PURSE=fair.PURSE
SEED_BASE=fair.SEED_BASE
POLICY="realistic_info_beam_v1"
TRIAL_SEED=0
PARAMS={}
COUNTERS={}

def configure(seed,rollout_draws=3,pass_cap=7,buck_cap=3,
              rollout_beam=42,rollout_depth=14):
    global TRIAL_SEED,PARAMS,COUNTERS
    TRIAL_SEED=int(seed)
    PARAMS={"rollout_draws":int(rollout_draws),"pass_cap":int(pass_cap),
            "buck_cap":int(buck_cap),"rollout_beam":int(rollout_beam),
            "rollout_depth":int(rollout_depth)}
    COUNTERS={"rollout_calls":0,"turn_commitments":0,"buck_plans_checked":0,
              "library_order_invariance_tests":0}

def private_order_free_signature(state):
    """Policy may use deck multiset, but not order of unknown library."""
    return (state.turn,state.hand,tuple(sorted(state.library)),
            state.battlefield,state.grave,state.exile,state.land_played,
            state.w,state.c,state.any,state.restricted_legend,
            state.restricted_artifact,state.restricted_dack_white,
            state.treasures,state.spawn,state.spells,state.nonartifact_spells,
            state.noncreature_spells,state.saga_age,state.map_bonus_used)

def public_score(state):
    # Does NOT use state.library[0] or any hidden draw order.
    return fair.heuristic(state)

def short_list(states,cap):
    """Keep multiple strategically distinct beam continuations."""
    result={}
    for s in sorted(states,key=public_score,reverse=True):
        token=private_order_free_signature(s)
        if token not in result:result[token]=s
        if len(result)>=cap:break
    return list(result.values())

def hypothetical_next_start(state,sample_index):
    """A counterfactual next draw sampled solely from the remaining multiset.

    Does NOT inspect original state.library[0]. Its shuffle is seeded from a
    game seed + stable multiset; counterfactual draws are common across arms.
    """
    assert state.library
    cards=sorted(state.library)
    key=f"{TRIAL_SEED}|future|{state.turn}|{sample_index}|{len(cards)}"
    seed=int.from_bytes(hashlib.sha256(key.encode()).digest()[:8],"big")
    rng=random.Random(seed)
    index=rng.randrange(len(cards))
    drawn=cards.pop(index)
    rng.shuffle(cards)
    q=d.untap_and_begin(replace(state,turn=state.turn+1))
    q=d.add_opponent_cycle_resources(q)
    # Upkeep choice must be made without knowledge of the future drawn card.
    options=list(d.mana_vault_upkeep_options(q))
    q=max(options,key=public_score) if options else q
    q=replace(q,library=(drawn,)+tuple(cards))
    q=d.begin_first_main(d.saga_advance(d.draw(q,1)))
    return q

def one_future_sample_value(state,sample_index):
    # This value must not depend on the actual NEXT card's identity.
    if state.turn>=3:return public_score(state)/5000.
    if not state.library:return public_score(state)/5000.
    nxt=hypothetical_next_start(state,sample_index)
    # In simulated futures, Bucknard dice are UNREVEALED, not secretly fixed
    # favourable rolls for selection. This underestimates future Bucknard ramp.
    fair.overridden_roll(1)
    d.utility_actions=fair.utility_without_roll
    try:
        wins,front=d.search_turn_frontier_many(
            [nxt],beam=PARAMS["rollout_beam"],
            depth=PARAMS["rollout_depth"])
    finally:
        d.utility_actions=fair.ORIG_UTILITY
    COUNTERS["rollout_calls"]+=1
    if wins:return 1.0+min(0.05,public_score(max(wins,key=public_score))/100000.)
    # A small public-resource tie-break; a proven immediate win dominates.
    return min(0.15,max(0.,public_score(max(front,key=public_score))/6000.)) if front else 0.

def expected_future_value(state):
    if state.turn>=3:return public_score(state)/5000.
    return sum(one_future_sample_value(state,j) for j in
               range(PARAMS["rollout_draws"]))/PARAMS["rollout_draws"]

def post_roll_value(template,die):
    """Adapt to the die only AFTER committing activation/KCI payment.

    Search ordinary intra-turn mana sequencing, then evaluate any surviving
    end-state over possible next draws (not the actual draw).
    """
    assert 1<=die<=4
    outcome=replace(template,treasures=template.treasures+die-1)
    fair.overridden_roll(1)
    d.utility_actions=fair.utility_without_roll
    try:
        wins,front=d.search_turn_frontier_many([outcome],
            beam=PARAMS["rollout_beam"],
            depth=PARAMS["rollout_depth"])
    finally:
        d.utility_actions=fair.ORIG_UTILITY
    COUNTERS["rollout_calls"]+=1
    if wins:return 1.05
    if not front:return public_score(outcome)/5000.
    # Choose an ordinary post-roll pass state by an information-blind heuristic.
    # This is a nested approximation, not clairvoyance about next draw.
    candidates=short_list(front,2)
    return max(expected_future_value(q) for q in candidates)

def select_plan(no_roll_frontier,pre_roll_candidates,turn):
    """Evaluate hidden-information-consistent endings using Monte Carlo futures.

    Candidates come from a full intra-turn beam, rather than forcing the
    highest heuristic state as the only allowed plan. The selected plan is
    determined before the real future card or Bucknard die is observed.
    """
    COUNTERS["turn_commitments"]+=1
    endings=short_list(no_roll_frontier,PARAMS["pass_cap"])
    if not endings:
        return None,None,0,0.,0
    selected=max(((expected_future_value(q),public_score(q),q)
                  for q in endings),key=lambda x:(x[0],x[1]))
    best_value,best_score,best_state=selected
    best_template=None
    plans=0
    if pre_roll_candidates:
        starts=short_list(pre_roll_candidates,PARAMS["buck_cap"])
        for s in starts:
            for template in fair.candidate_action_states(s):
                # One payment / KCI response template for ALL four die faces.
                vals=[post_roll_value(template,die) for die in (1,2,3,4)]
                plans+=1
                av=sum(vals)/4.
                if av>best_value:
                    best_value=av
                    best_state=s
                    best_template=template
    COUNTERS["buck_plans_checked"]+=plans
    return best_state,best_template,plans,best_value,len(endings)

def realistic_turn(start,beam,die_rng):
    fair.overridden_roll(1)
    before_roll={}
    def filter_actions(s):
        if any(d.effective_name(p)==PURSE and not p.tapped
               for p in s.battlefield):
            before_roll[private_order_free_signature(s)]=s
        return fair.utility_without_roll(s)
    d.utility_actions=filter_actions
    try:
        wins,front=d.search_turn_frontier_many(
            [start],beam=beam,depth=22 if start.turn==1 else 24)
    finally:
        d.utility_actions=fair.ORIG_UTILITY
    if wins:
        return True,max(wins,key=public_score),{
          "die":None,"phase":"pre-roll win",
          "pass_candidates":0,"buck_plans":0}
    state,template,plans,value,num=select_plan(front,
        list(before_roll.values()),start.turn)
    if state is None:state=start
    if template is None:
        return False,state,{"die":None,"phase":"expected-draw pass",
            "pass_candidates":num,"buck_plans":plans,
            "pass_value":round(value,5)}
    # NOW -- and only now -- sample the actual die.
    roll=die_rng.randint(1,4)
    resolved=replace(template,treasures=template.treasures+roll-1)
    assert resolved.treasures>=roll
    fair.overridden_roll(1)
    d.utility_actions=fair.utility_without_roll
    try:
        wins,front=d.search_turn_frontier_many(
            [resolved],beam=beam,depth=22 if start.turn==1 else 24)
    finally:
        d.utility_actions=fair.ORIG_UTILITY
    if wins:
        return True,max(wins,key=public_score),{
            "die":roll,"phase":"post-roll win",
            "pass_candidates":num,"buck_plans":plans}
    if front:
        # Choose an end state without using the upcoming real draw.
        chosen=max(short_list(front,PARAMS["pass_cap"]),
                   key=expected_future_value)
    else:chosen=resolved
    return False,chosen,{"die":roll,"phase":"post-roll pass",
                         "pass_candidates":num,"buck_plans":plans}

def simulate(variant,gid,beam,pass_cap,buck_cap,draws,rollout_beam,rollout_depth):
    assert tuple(d.DECK)==trial.VARIANTS[variant]
    seed=SEED_BASE+int(gid)*1000003
    configure(seed,draws,pass_cap,buck_cap,rollout_beam,rollout_depth)
    m.set_trial_seed(seed)
    chooser=random.Random(seed)
    seat=chooser.randrange(4)
    fair.overridden_roll(2)
    first,keep_n,audit=root.choose_hand_with_free(chooser,seat)
    die_seed=int.from_bytes(hashlib.sha256(
        f"bucknard-independent-d4|{seed}".encode()).digest()[:8],"big")
    dice=random.Random(die_seed)
    current,pregame_choices=fair.choose_pregame(first,seat)
    audit=[]
    win=0
    for turn in (1,2,3):
        start=fair.turnstart(current,turn)
        was_win,current,meta=realistic_turn(start,beam,dice)
        audit.append({"turn":turn,**meta})
        if was_win:
            win=turn
            break
    d.utility_actions=fair.ORIG_UTILITY
    fair.overridden_roll(2)
    return {"game_id":gid,"seed":seed,"seat":seat,"keep_n":keep_n,
            "win_turn":win,"pregame_options":pregame_choices,
            "rolls":[x["die"] for x in audit if x["die"] is not None],
            "turn_audit":audit,"planning_counts":dict(COUNTERS)}

def audit():
    fair.audit()
    fair.install_honest_scry()
    root.install("buck_worldmap")
    configure(SEED_BASE,rollout_draws=3)
    from collections import Counter as C
    a=d.State(1,("Plains",),("Sol Ring","Ancient Tomb","Mana Vault"),w=1)
    b=replace(a,library=tuple(reversed(a.library)))
    assert private_order_free_signature(a)==private_order_free_signature(b)
    assert public_score(a)==public_score(b)
    for j in range(8):
        assert hypothetical_next_start(a,j)==hypothetical_next_start(b,j)
    # Changing a hidden future order can NEVER change the expected draw value.
    # This test is intentionally evaluated using the engine rather than merely
    # testing deterministic sample generation.
    assert expected_future_value(a)==expected_future_value(b)
    fair.overridden_roll(1)
    t=d.State(2,(),tuple(root.COMBO),battlefield=(
        d.Perm(PURSE),d.Perm("Krark-Clan Ironworks")),c=1)
    choices=fair.candidate_action_states(t)
    assert any(PURSE in q.grave for q in choices)
    assert any(PURSE not in q.grave for q in choices)
    for k in (1,2,3,4):
        assert all(q.treasures+k-1==k for q in choices)
    assert all(card not in root.CURRENT for card in ("Mana Crypt","Jeweled Lotus"))
    print("REALISTIC_BEAM_INFORMATION_ORDER_AUDIT_PASS",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--variant",choices=("current","buck_worldmap"),
                   default="current")
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--games",type=int,default=4)
    p.add_argument("--beam",type=int,default=160)
    p.add_argument("--pass-cap",type=int,default=7)
    p.add_argument("--buck-cap",type=int,default=3)
    p.add_argument("--draw-samples",type=int,default=3)
    p.add_argument("--rollout-beam",type=int,default=42)
    p.add_argument("--rollout-depth",type=int,default=14)
    p.add_argument("--out",default="dack_realistic_beam_shard.json.gz")
    args=p.parse_args()
    assert args.games>=1 and args.shard>=0 and args.beam>=40
    assert args.pass_cap>=1 and args.buck_cap>=1 and args.draw_samples>=1
    assert 4<=args.rollout_depth<=24 and args.rollout_beam>=16
    audit()
    if args.audit:return
    root.install(args.variant)
    d._WIN_CACHE.clear()
    fair.install_honest_scry()
    rows=[]; t0=time.time()
    for j in range(args.games):
        gid=args.shard*args.games+j
        q=simulate(args.variant,gid,args.beam,args.pass_cap,
             args.buck_cap,args.draw_samples,args.rollout_beam,
             args.rollout_depth)
        rows.append(q)
        print("REALISTIC_BEAM_GAME",args.variant,gid,q["win_turn"],
              "rollouts",q["planning_counts"]["rollout_calls"],flush=True)
    obj={
      "schema":POLICY,"variant":args.variant,
      "policy":"Expected sampled unknown next draws choose among beam endings; uniform d4 after committed payment/KCI; visible scry, no Gemstone/upkeep hindsight",
      "beam":args.beam,"pass_cap":args.pass_cap,"buck_cap":args.buck_cap,
      "draw_samples":args.draw_samples,"rollout_beam":args.rollout_beam,
      "rollout_depth":args.rollout_depth,
      "shard":args.shard,"games":args.games,"seed_base":SEED_BASE,
      "deck_sha256":hashlib.sha256(
           "\n".join(trial.VARIANTS[args.variant]).encode()).hexdigest(),
      "counts":{str(k):v for k,v in Counter(x["win_turn"] for x in rows).items()},
      "elapsed_sec":round(time.time()-t0,2),"rows":rows
    }
    with gzip.open(args.out,"wt",encoding="utf8") as f:
        json.dump(obj,f,separators=(",",":"))
    print("REALISTIC_INFORMATION_BEAM_SHARD_PASS",args.variant,args.games,flush=True)

if __name__=="__main__":main()
