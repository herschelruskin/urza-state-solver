#!/usr/bin/env python3
"""Non-clairvoyant Bucknard audit for the Oct 16 Boonweaver T2 deployment proxy.

Two separate estimates:
  neutral_fixed2: deterministic two-Treasure stress test (NOT a d4 expectation).
  blind_T2: lower-bound policy: evaluate pre-activation candidate lines on the
            average of *all four* rolls, choose a line BEFORE observing the roll,
            then allow ordinary post-roll play. Does not select a better prefix
            based on the realized die. Stops at T2 (the disputed primary outcome).

Beam search remains approximate. The pre-activation policy search retains only
the top K distinct *eligible pre-roll states per turn*; reported gains are
conservative relative to the best possible nonclairvoyant strategy, but they
may still benefit from the engine's existing perfect-knowledge sampled draws.
"""
from __future__ import annotations
import argparse, gzip, json, math, random, hashlib
from collections import Counter
from dataclasses import replace
import dack_bucknard_minimal_swaps_20261016 as buck

root=buck.root
d=root.d
m=root.m
PURSE=buck.NEW
VARIANT="buck_worldmap"
SEED_BASE=7604096001
ORIG_ROLL=m._roll
ORIG_UTIL=d.utility_actions

def roll_with_value(value):
    def roll(s,card,sides,salt=0):
        if card==PURSE:
            assert sides==4
            return value
        return ORIG_ROLL(s,card,sides,salt)
    return roll

def set_roll(value):
    assert 1<=value<=4
    m._roll=roll_with_value(value)

def pregame(gid):
    seed=SEED_BASE+int(gid)*1000003
    m.set_trial_seed(seed)
    rng=random.Random(seed)
    seat=rng.randrange(4)
    set_roll(2) # neutral die during all mulligan/candidate decisions
    d._WIN_CACHE.clear()
    state,keep_n,audit=root.choose_hand_with_free(rng,seat)
    return seed,seat,state,keep_n,audit

def has_purse(s):
    return any(d.effective_name(p)==PURSE and not p.tapped for p in s.battlefield)

def eligible(s):
    if not has_purse(s):return False
    return bool(d.pay_options(s,1))

def activated(s,q):
    # Only Bucknard's activation both transfers the Purse away and makes d4
    # Treasures in this particular deck/engine. KCI's response also qualifies.
    old=sum(d.effective_name(p)==PURSE for p in s.battlefield)
    new=sum(d.effective_name(p)==PURSE for p in q.battlefield)
    return new<old and q.treasures>s.treasures

def blind_pre_candidates(state,seat,beam,limit=4):
    """Beam-search T1 and T2 with Bucknard dice strictly unavailable.

    An eligible activation *state*, not a lucky postroll state, is collected.
    If Dack is cast without the die by T2, p=1 without needing Bucknard.
    """
    candidates={1:{},2:{}}
    def without_bucknard(s):
        acts=ORIG_UTIL(s)
        if eligible(s):
            candidates[s.turn][d.key(s)]=s
            acts=[a for a in acts if not activated(s,a)]
        return acts

    set_roll(2)
    d.utility_actions=without_bucknard
    try:
        states=d._pregame_states(d.State(1,state.hand,state.library),seat)
        for turn in (1,2):
            nxt=[]
            if turn==1:
                nxt=[d.draw(s,1) for s in states]
            else:
                for s in states:
                    q=d.untap_and_begin(replace(s,turn=turn))
                    q=d.add_opponent_cycle_resources(q)
                    for u in d.mana_vault_upkeep_options(q):
                        nxt.append(d.begin_first_main(d.saga_advance(d.draw(u,1))))
            wins,fr=d.search_turn_frontier_many(nxt,beam=beam,depth=22 if turn==1 else 24)
            if wins:
                return True,[],dict((i,len(z)) for i,z in candidates.items())
            if turn==1:
                fr.sort(key=d.score,reverse=True)
                states=fr[:beam]
    finally:
        d.utility_actions=ORIG_UTIL
    ranked=[]
    for turn,states in candidates.items():
        # Keep candidates with different mana/land/board postures. Exact state
        # dedupe happened above; heuristic top-K is our stated approximation.
        vals=sorted(states.values(),key=d.score,reverse=True)
        ranked.extend(vals[:limit])
    return False,ranked,{str(k):len(v) for k,v in candidates.items()}

def post_activation_T2(s,roll,beam):
    """Resolve a known die AFTER the activation, and play adaptively."""
    set_roll(roll)
    d.utility_actions=ORIG_UTIL
    # Distinct legal KCI and ordinary handoff resolutions may both be chosen
    # postactivation, but there is no die-dependent choice before activation.
    acts=ORIG_UTIL(s)
    after=[q for q in acts if activated(s,q)]
    assert after,(s,"purse not activatable")
    successes=[]
    for start in after:
        if d.can_cast_dack(start):
            return True
        wins,fr=d.search_turn_frontier_many([start],beam=beam,
                                             depth=24 if s.turn==1 else 24)
        if wins:return True
        if s.turn==2:continue
        fr.sort(key=d.score,reverse=True)
        t2=[]
        for q in fr[:beam]:
            q=d.untap_and_begin(replace(q,turn=2))
            q=d.add_opponent_cycle_resources(q)
            for u in d.mana_vault_upkeep_options(q):
                t2.append(d.begin_first_main(d.saga_advance(d.draw(u,1))))
        if not t2:continue
        wins,_=d.search_turn_frontier_many(t2,beam=beam,depth=24)
        if wins:return True
    return False

def blind_T2(gid,beam=160,limit=4):
    """Expected chance success, no die clairvoyance in activation commitment."""
    seed,seat,state,keep,audit=pregame(gid)
    immediate,candidates,count=blind_pre_candidates(state,seat,beam,limit)
    if immediate:
        return {"gid":gid,"prob_T2":1.0,"keep_n":keep,"candidate_counts":count,
                "evaluated":0,"chosen":None,"roll_successes":4}
    best=(0.,None,0)
    for s in candidates:
        hits=0
        for die in (1,2,3,4):
            hits+=int(post_activation_T2(s,die,beam))
        expected=hits/4
        if expected>best[0]:
            best=(expected,s.turn,hits)
        if best[0]==1:break
    set_roll(2)
    return {"gid":gid,"prob_T2":best[0],"keep_n":keep,
            "candidate_counts":count,"evaluated":len(candidates),
            "chosen":best[1],"roll_successes":best[2]}

def neutral_fixed2(gid,beam=240):
    seed=SEED_BASE+int(gid)*1000003
    set_roll(2)
    d._WIN_CACHE.clear()
    result=root.simulate(VARIANT,gid,beam)
    return {"gid":gid,"turn":result["win_turn"],
            "success_T2":int(0<result["win_turn"]<=2),
            "keep_n":result["keep_n"]}

def selftest():
    buck.audit()
    assert len(buck.VARIANTS[VARIANT])==99
    assert buck.ORIGINAL.count("World Map")==1
    assert "World Map" not in buck.VARIANTS[VARIANT]
    assert PURSE in buck.VARIANTS[VARIANT]
    assert all(roll_with_value(i)(None,PURSE,4)==i for i in (1,2,3,4))
    from collections import Counter as C
    assert C(buck.VARIANTS[VARIANT])-C(buck.ORIGINAL)==C([PURSE])
    assert C(buck.ORIGINAL)-C(buck.VARIANTS[VARIANT])==C(["World Map"])
    assert d.COMBO_CREATURES==root.COMBO
    root.install(VARIANT)
    set_roll(2)
    st=d.State(1,(),tuple(root.COMBO),battlefield=(d.Perm(PURSE),),c=1)
    q=[x for x in ORIG_UTIL(st) if activated(st,x)]
    assert q and all(z.treasures==2 for z in q),(q,"neutral roll not fixed")
    for die in (1,2,3,4):
        set_roll(die)
        q=[x for x in ORIG_UTIL(st) if activated(st,x)]
        assert q and all(z.treasures==die for z in q)
    # Activation remains a real paid action (1 generic) and source is gone;
    # it is never both on our battlefield and giving us treasures.
    set_roll(2)
    st0=d.State(1,(),tuple(root.COMBO),battlefield=(d.Perm(PURSE),),c=0)
    assert not any(activated(st0,z) for z in ORIG_UTIL(st0))
    d.utility_actions=ORIG_UTIL
    print("BUCKNARD_BLIND_AUDIT_SELFTEST_PASS",flush=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",action="store_true")
    ap.add_argument("--mode",choices=("blind_T2","neutral_fixed2"),default="blind_T2")
    ap.add_argument("--shard",type=int,default=0)
    ap.add_argument("--games",type=int,default=8)
    ap.add_argument("--beam",type=int,default=160)
    ap.add_argument("--candidate-limit",type=int,default=4)
    ap.add_argument("--out",default="blind_bucknard.json.gz")
    a=ap.parse_args()
    selftest()
    if a.audit:return
    assert a.games>=1 and a.beam>=30 and a.candidate_limit>=1
    root.install(VARIANT)
    d._WIN_CACHE.clear()
    records=[]
    for j in range(a.games):
        gid=a.shard*a.games+j
        rec=(blind_T2(gid,a.beam,a.candidate_limit)
             if a.mode=="blind_T2" else neutral_fixed2(gid,a.beam))
        records.append(rec)
        print("BLIND_BUCK_GAME",a.mode,json.dumps(rec),flush=True)
    payload={"schema":"blind_bucknard_v1","mode":a.mode,
             "variant":VARIANT,
             "swaps":[["World Map",PURSE]],
             "seed_base":SEED_BASE,
             "beam":a.beam,"candidate_limit":a.candidate_limit,
             "shard":a.shard,"games":a.games,
             "deck_sha256":hashlib.sha256("\n".join(buck.VARIANTS[VARIANT]).encode()).hexdigest(),
             "rows":records}
    with gzip.open(a.out,"wt",encoding="utf8") as f:
        json.dump(payload,f,separators=(",",":"))
    print("BLIND_BUCK_SHARD_PASS",a.mode,a.games,flush=True)

if __name__=="__main__":
    main()
