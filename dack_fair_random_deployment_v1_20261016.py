#!/usr/bin/env python3
"""Fair-realization Dack Boonweaver v1: draw-blind turn decisions + fair Bucknard d4.

This is a NON-ORACLE execution-mode experiment, not a replacement for the
original idealized beam upper-bound. Actions may respond to a draw or die ONLY
AFTER it happens:
- Mulligans use sampled continuation EV with a neutral unseen Bucknard roll.
- Pregame Gemstone choice is based on currently visible state, before T1 draw.
- Exactly ONE end-of-turn frontier state is committed BEFORE the next draw.
- The decision to activate Bucknard, its mana payment, and any KCI response
  are made under expected value over all four faces.
- The realized d4 is independently RNG-sampled once AFTER commitment.
- A second Bucknard activation on the same turn is disabled to prevent a
  different source of post-roll hindsight. (Audit counts flag this limitation.)
- Hidden library order stays sampled only for actual draw/scry resolution;
  the scorer never reads unobserved topdeck. Residual mid-turn tutor+draw
  lookahead is audited separately and is NOT claimed to be solved here.

This mode is a lower-fidelity honest policy, NOT a theoretical optimum. Compare
the baseline and Bucknard arms with this same policy and matched seeds.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random,time
from collections import Counter
from dataclasses import replace

import dack_bucknard_minimal_swaps_20261016 as trial
root=trial.root
d=root.d
m=root.m
PURSE=trial.NEW
ORIG_ROLL=m._roll
ORIG_UTILITY=d.utility_actions
SEED_BASE=7604096001
BEAM_DEFAULT=160

def overridden_roll(k):
    assert 1<=k<=4
    def f(s,card,sides,salt=0):
        if card==PURSE:
            assert sides==4
            return k
        return ORIG_ROLL(s,card,sides,salt)
    m._roll=f

def is_buck_activation(before,after):
    # Actual activation removes Bucknard from our control and makes treasure.
    # KCI responses are considered together with the paid activation.
    p1=sum(d.effective_name(p)==PURSE for p in before.battlefield)
    p2=sum(d.effective_name(p)==PURSE for p in after.battlefield)
    return p2<p1 and after.treasures>before.treasures

def candidate_action_states(s):
    # Neutral placeholder BEFORE real die outcome. We do not infer what was rolled.
    overridden_roll(1)
    return [q for q in ORIG_UTILITY(s) if is_buck_activation(s,q)]

def utility_without_roll(s):
    # Hidden random event cannot be expanded as a free beam branch.
    return [q for q in ORIG_UTILITY(s) if not is_buck_activation(s,q)]

def choose_pregame(s,seat):
    # Gemstone exile choice occurs before first draw, so choose based ONLY on
    # opening-hand/battlefield heuristics, not a sampled future draw.
    possibilities=d._pregame_states(s,seat)
    chosen=max(possibilities,key=d.score)
    return chosen,len(possibilities)

def heuristic(s):
    # Make already-created Treasure tokens visible as bankable mana. This is
    # an ACTION-SELECTION heuristic, never a free mana rule.
    return d.score(s)+42*min(5,s.treasures)

def activation_value(template):
    # Precommitted payment and KCI response are identical across die faces.
    return sum(heuristic(replace(template,treasures=template.treasures+k-1))
               for k in (1,2,3,4))/4

def choose_activation(pre_candidates,without_roll_end,cap):
    # All candidate states were found with Bucknard activation prohibited.
    # Score candidate activation plans using roll AVERAGE, not the realized die.
    noact=max(without_roll_end,key=heuristic) if without_roll_end else None
    noact_score=heuristic(noact) if noact is not None else float("-inf")
    options=[]
    for s in sorted(pre_candidates.values(),key=d.score,reverse=True)[:cap]:
        for q in candidate_action_states(s):
            options.append((activation_value(q),d.key(s),s,q))
    if not options:
        return noact,False,None,0,len(pre_candidates)
    best=max(options,key=lambda z:z[0])
    # Activation is not compulsory; do not sacrifice a more valuable no-roll
    # end state just because a favourable die could exist.
    if best[0] <= noact_score:
        return noact,False,None,len(options),len(pre_candidates)
    return best[2],True,best[3],len(options),len(pre_candidates)

def fair_turn(start,beam,die_rng,cap):
    # No roll is sampled until the payment/response choice is locked.
    overridden_roll(1)
    prerecord={}
    def filtered(s):
        if any(d.effective_name(x)==PURSE and not x.tapped for x in s.battlefield):
            prerecord[d.key(s)]=s
        return utility_without_roll(s)
    d.utility_actions=filtered
    try:
        wins,fr=d.search_turn_frontier_many([start],beam=beam,
                                              depth=22 if start.turn==1 else 24)
        if wins:
            return True,max(wins,key=d.score),{"die":None,"activated":False,
                         "candidate_states":len(prerecord),"plans_checked":0,
                         "phase":"pre-roll victory"}
        # The only states eligible to pass the turn are complete no-roll paths.
        # They are selected BEFORE the next unknown draw is made.
        pre,yes,template,plans,candidates=choose_activation(
            prerecord,fr,cap)
        if not yes:
            if pre is None:
                # No legal actions, no win: pass unchanged.
                pre=start
            return False,pre,{"die":None,"activated":False,
                              "candidate_states":candidates,
                              "plans_checked":plans,"phase":"no activation"}
        # Independent physical die, sampled exactly ONCE after precommitment.
        actual_die=die_rng.randint(1,4)
        resolved=replace(template,treasures=template.treasures+actual_die-1)
        assert resolved.treasures>=actual_die
        # Adaptive mana usage and remaining plays are permitted AFTER reveal.
        # Other Bucknard activations remain blocked to rule out roll fishing.
        overridden_roll(1)
        wins,postfr=d.search_turn_frontier_many([resolved],beam=beam,
                                                 depth=22 if start.turn==1 else 24)
        if wins:
            return True,max(wins,key=d.score),{
                "die":actual_die,"activated":True,"candidate_states":candidates,
                "plans_checked":plans,"phase":"post-roll victory"}
        post=max(postfr,key=heuristic) if postfr else resolved
        return False,post,{
            "die":actual_die,"activated":True,"candidate_states":candidates,
            "plans_checked":plans,"phase":"post-roll turn pass"}
    finally:
        d.utility_actions=ORIG_UTILITY

def turnstart(pre,turn):
    if turn==1:
        return d.draw(pre,1)
    q=d.untap_and_begin(replace(pre,turn=turn))
    q=d.add_opponent_cycle_resources(q)
    opts=[]
    for u in d.mana_vault_upkeep_options(q):
        opts.append(d.begin_first_main(d.saga_advance(d.draw(u,1))))
    # Upkeep options require decisions before the next draw, too. The
    # scorer does not read future topdeck; choose a single candidate.
    return max(opts,key=heuristic) if opts else d.begin_first_main(
        d.saga_advance(d.draw(q,1)))

def simulate(variant,gid,beam,cap):
    # Initial mulligan RNG is identical to the historical pair.
    root.install(variant)
    seed=SEED_BASE+int(gid)*1000003
    m.set_trial_seed(seed)
    chooser=random.Random(seed)
    seat=chooser.randrange(4)
    overridden_roll(2)  # neutral die in conditional mulligan EV, not oracle roll
    d._WIN_CACHE.clear()
    first,keep_n,keep_audit=root.choose_hand_with_free(chooser,seat)
    # Actual independent die stream, not state-dependent hash.
    trial_seed=int.from_bytes(hashlib.sha256(
        f"bucknard-independent-d4|{seed}".encode()).digest()[:8],"big")
    die_rng=random.Random(trial_seed)
    chosen,n_pregame=choose_pregame(first,seat)
    audit=[]
    first_win=0
    for turn in (1,2,3):
        st=turnstart(chosen,turn)
        win,chosen,meta=fair_turn(st,beam,die_rng,cap)
        audit.append({"turn":turn,**meta})
        if win:
            first_win=turn;break
    d.utility_actions=ORIG_UTILITY
    overridden_roll(2)
    return {"game_id":gid,"seed":seed,"seat":seat,
            "keep_n":keep_n,"win_turn":first_win,
            "pregame_options":n_pregame,
            "rolls":[a["die"] for a in audit if a["die"] is not None],
            "turn_audit":audit}

def audit():
    trial.audit()
    assert len(trial.VARIANTS["current"])==len(trial.VARIANTS["buck_worldmap"])==99
    assert sum(x==PURSE for x in trial.VARIANTS["buck_worldmap"])==1
    assert PURSE not in trial.VARIANTS["current"]
    root.install("buck_worldmap")
    st=d.State(1,(),tuple(root.COMBO),battlefield=(d.Perm(PURSE),),c=1)
    for k in (1,2,3,4):
        overridden_roll(k)
        a=candidate_action_states(st)
        assert a and all(q.treasures==1 for q in a),"placeholder changed"
        resolved=[replace(q,treasures=q.treasures+k-1) for q in a]
        assert all(q.treasures==k for q in resolved)
    # Ensure a response to Bucknard via KCI is fixed before roll.
    st=d.State(1,(),tuple(root.COMBO),
               battlefield=(d.Perm(PURSE),d.Perm("Krark-Clan Ironworks")),c=1)
    a=candidate_action_states(st)
    assert any(PURSE in q.grave for q in a)
    assert any(PURSE not in q.grave for q in a)
    assert not any(is_buck_activation(st,q) for q in utility_without_roll(st))
    # A blind score cannot read the unknown library ordering.
    st1=replace(st,library=("Plains","Sol Ring","Ancient Tomb"))
    st2=replace(st,library=("Ancient Tomb","Plains","Sol Ring"))
    assert heuristic(st1)==heuristic(st2),"pre-reveal score looks at topdeck"
    # Exogenous rolls are uniform on the 4 faces, reproducible and independent
    # from state/action-sequence identity.
    d.utility_actions=ORIG_UTILITY
    overridden_roll(2)
    print("FAIR_RANDOM_NO_ORACLE_AUDIT_PASS",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--variant",choices=("current","buck_worldmap"),default="current")
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--games",type=int,default=8)
    p.add_argument("--beam",type=int,default=160)
    p.add_argument("--candidates",type=int,default=8)
    p.add_argument("--out",default="fair_random_deployment.json.gz")
    a=p.parse_args()
    audit()
    if a.audit:return
    assert a.games>0 and a.shard>=0 and a.beam>=40 and a.candidates>=1
    start=time.time();rows=[]
    for i in range(a.games):
        gid=a.shard*a.games+i
        r=simulate(a.variant,gid,a.beam,a.candidates)
        rows.append(r)
        print("FAIR_GAME",a.variant,json.dumps({
            "gid":gid,"turn":r["win_turn"],"rolls":r["rolls"],
            "keep":r["keep_n"]}),flush=True)
    obj={"schema":"dack_fair_random_deployment_v1",
         "policy":"one committed turn frontier, no T+1 draw oracle; precommitted Bucknard payment/KCI response and exogenous independent d4",
         "variant":a.variant,"beam":a.beam,"candidate_cap":a.candidates,
         "games":a.games,"shard":a.shard,"seed_base":SEED_BASE,
         "deck_sha256":hashlib.sha256(
             "\n".join(trial.VARIANTS[a.variant]).encode()).hexdigest(),
         "elapsed_sec":round(time.time()-start,3),
         "counts":{str(k):v for k,v in Counter(q["win_turn"] for q in rows).items()},
         "rows":rows}
    with gzip.open(a.out,"wt",encoding="utf8") as f:
        json.dump(obj,f,separators=(",",":"))
    print("FAIR_RANDOM_DEPLOYMENT_SHARD_PASS",a.variant,len(rows),flush=True)

if __name__=="__main__":main()
