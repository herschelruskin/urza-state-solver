#!/usr/bin/env python3
"""Dack fair-die and hidden-next-draw pilots.

Experiment A, fair_d4: a genuinely sampled d4 (seeded independently of the
action tree) AFTER committing the activation location, mana payment and KCI
response based on expected success across all four faces. Unlike the old
state-hashed oracle, neither pre-roll search nor commitment can see the roll.

Experiment B, strict_current/strict_buck: same game, additionally commit
exactly one T1 pass-state by public resource heuristic before revealing T2.
This removes the turn-one path-selection oracle. Bucknard is not activated on
T1 in B (conservative restricted policy), and may activate on T2 blindly.

Every mode uses a separate game-seeded shuffle for search-based reshuffles.
Multiset-conditional replay inside a single game remains canonical (known
remaining library order can still inform in-turn tutor/scry choices). This is
a POC for more stringent nonclairvoyance, NOT a completed POMDP solver.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random
from collections import Counter
from dataclasses import replace
import dack_bucknard_blind_roll_audit_20261016 as prior

root=prior.root
d=root.d
m=root.m
BUCK=prior.PURSE
ORIG_SHUFFLE=d.shuffled_unknown
ORIG_ROLL=prior.ORIG_ROLL
ORIG_UTIL=prior.ORIG_UTIL
SEED_BASE=prior.SEED_BASE
VARIANTS={"fair_d4":prior.VARIANT,"strict_current":"current","strict_buck":prior.VARIANT}

def uniform_seed(*parts):
    data="|".join(str(x) for x in parts).encode("utf8")
    return int.from_bytes(hashlib.sha256(data).digest()[:16],"big")

def configure_events(gid):
    seed=SEED_BASE+int(gid)*1000003
    # Die events are uniform over game IDs, independent of action sequence.
    # This function excludes the identity/contents of d.key(state).
    def independent_roll(state,card,sides,salt=0):
        return random.Random(uniform_seed(seed,"DIE",card,state.turn,salt)).randint(1,sides)
    def reshuffle(lib):
        cards=sorted(lib)
        random.Random(uniform_seed(seed,"SHUFFLE",len(cards),*cards)).shuffle(cards)
        return tuple(cards)
    prior.ORIG_ROLL=independent_roll
    d.shuffled_unknown=reshuffle
    return seed

def public_pre_roll_actions(s,collect):
    acts=ORIG_UTIL(s)
    if prior.eligible(s):
        # Record commitments before they can see a random outcome.
        collect[d.key(s)]=s
        acts=[q for q in acts if not prior.activated(s,q)]
    return acts

def evaluate_commitments(candidates,beam,k):
    best=(0.,None,None)
    examined=0
    # The original solver's resource score does NOT depend on the hidden
    # random outcome. Search each eligible state with its die withheld.
    ranked=sorted(candidates.values(),key=d.score,reverse=True)[:k]
    for s in ranked:
        for committed in prior.activation_templates(s):
            outcomes=tuple(prior.post_activation_T2(committed,die,beam)
                           for die in (1,2,3,4))
            examined+=1
            expected=sum(outcomes)/4.
            if expected>best[0]:
                best=(expected,committed,outcomes)
            if best[0]>=1:break
        if best[0]>=1:break
    return best,examined

def sampled_result(gid,best):
    expected,committed,outcomes=best
    # Critically: draw once, and only AFTER the fixed commitment has been
    # selected by the expectation. No search branch observes it in advance.
    seed=SEED_BASE+int(gid)*1000003
    die=random.Random(uniform_seed(seed,"BUCKNARD",0)).randint(1,4)
    return {"rolled":die,"expected_prob_T2":expected,
            "win_T2":int(bool(outcomes[die-1])) if outcomes else 0,
            "commitment_turn":committed.turn if committed else None}

def prepare(gid,variant):
    configure_events(gid)
    root.install(variant)
    d.clear_distribution_cache()
    prior.set_roll(2) # unknown dice cannot leak into mulligan simulator
    seed,seat,state,keep,audit=prior.pregame(gid)
    return seed,seat,state,keep,audit

def fair_d4(gid,beam,k):
    seed,seat,state,keep,audit=prepare(gid,prior.VARIANT)
    immediate,candidates,counts=prior.blind_pre_candidates(state,seat,beam,limit=k)
    if immediate:
        return {"game_id":gid,"seat":seat,"keep_n":keep,
                "win_T2":1,"expected_prob_T2":1., "rolled":None,
                "commitment_turn":None,"candidates":sum(counts.values()),
                "choices_evaluated":0}
    # Note prior.blind_pre_candidates includes at most k candidates
    # from each turn, and has withheld die events throughout.
    options={d.key(s):s for s in candidates}
    best,ex=evaluate_commitments(options,beam,k*2)
    resolved=sampled_result(gid,best)
    return {"game_id":gid,"seat":seat,"keep_n":keep,
            "candidates":sum(counts.values()),"choices_evaluated":ex,**resolved}

def search_no_dice(states,beam,turn,candidates):
    def hidden_activation(s):return public_pre_roll_actions(s,candidates)
    prior.set_roll(2)
    d.utility_actions=hidden_activation
    try:
        return d.search_turn_frontier_many(states,beam=beam,depth=22 if turn==1 else 24)
    finally:
        d.utility_actions=ORIG_UTIL

def strict_T2(gid,beam,k,variant):
    seed,seat,state,keep,audit=prepare(gid,variant)
    starts=[d.draw(s,1) for s in d._pregame_states(d.State(1,state.hand,state.library),seat)]
    t1_candidates={}
    wins,pass_frontier=search_no_dice(starts,beam,1,t1_candidates)
    if wins:
        return {"game_id":gid,"seat":seat,"keep_n":keep,"win_T2":1,
                "expected_prob_T2":1.,"rolled":None,"commitment_turn":None,
                "choices_evaluated":0,"t1_pass_committed":True,
                "t1_candidates_suppressed":len(t1_candidates)}
    assert pass_frontier
    # The T1 branch is committed BEFORE the next draw is revealed.
    # It is intentionally a conservative heuristic, not an optimal POMDP.
    chosen=max(pass_frontier,key=d.score)
    q=d.untap_and_begin(replace(chosen,turn=2))
    q=d.add_opponent_cycle_resources(q)
    t2_states=[]
    for u in d.mana_vault_upkeep_options(q):
        t2_states.append(d.begin_first_main(d.saga_advance(d.draw(u,1))))
    t2_candidates={}
    wins,_=search_no_dice(t2_states,beam,2,t2_candidates)
    if wins:
        return {"game_id":gid,"seat":seat,"keep_n":keep,"win_T2":1,
                "expected_prob_T2":1.,"rolled":None,"commitment_turn":None,
                "choices_evaluated":0,"t1_pass_committed":True,
                "t1_candidates_suppressed":len(t1_candidates)}
    if variant=="current":
        return {"game_id":gid,"seat":seat,"keep_n":keep,"win_T2":0,
                "expected_prob_T2":0.,"rolled":None,"commitment_turn":None,
                "choices_evaluated":0,"t1_pass_committed":True,
                "t1_candidates_suppressed":0}
    best,ex=evaluate_commitments(t2_candidates,beam,k)
    resolution=sampled_result(gid,best)
    return {"game_id":gid,"seat":seat,"keep_n":keep,"choices_evaluated":ex,
            "t1_pass_committed":True,"t1_candidates_suppressed":len(t1_candidates),
            **resolution}

def audit():
    prior.selftest()
    for gid in (0,1,2,3):
        seed=configure_events(gid)
        a=[random.Random(uniform_seed(seed,"BUCKNARD",0)).randint(1,4) for _ in range(3)]
        assert len(set(a))==1 and 1<=a[0]<=4
        # Only a game's seed, not state, participates in a die roll.
        s1=d.State(1,(),(),c=1)
        s2=d.State(1,("Plains",),(),c=5)
        assert prior.ORIG_ROLL(s1,BUCK,4)==prior.ORIG_ROLL(s2,BUCK,4)
        assert d.shuffled_unknown(("Plains","Ancient Tomb","Sol Ring"))==d.shuffled_unknown(
             ("Sol Ring","Plains","Ancient Tomb"))
    # Fair d4 has no biased modulo reduction: Python randint uses unbiased
    # rejection sampling. Verify its reproducibility for a fixed game seed.
    configure_events(0)
    root.install(prior.VARIANT)
    st=d.State(1,(),tuple(root.COMBO),battlefield=(d.Perm(BUCK),),c=1)
    for roll in (1,2,3,4):
        prior.set_roll(roll)
        options=[q for q in ORIG_UTIL(st) if prior.activated(st,q)]
        assert options and all(q.treasures==roll for q in options)
    assert BUCK not in root.CURRENT and BUCK in prior.buck.VARIANTS[prior.VARIANT]
    assert "Component Pouch" not in root.CURRENT
    print("FAIR_RANDOM_AND_TURN_COMMIT_SELFTEST_PASS",flush=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",action="store_true")
    ap.add_argument("--mode",choices=tuple(VARIANTS),default="fair_d4")
    ap.add_argument("--shard",type=int,default=0)
    ap.add_argument("--games",type=int,default=8)
    ap.add_argument("--beam",type=int,default=120)
    ap.add_argument("--candidate-limit",type=int,default=8)
    ap.add_argument("--out",default="fair_roll_shard.json.gz")
    args=ap.parse_args()
    audit()
    if args.audit:return
    assert args.shard>=0 and args.games>0 and args.beam>=40 and args.candidate_limit>=1
    rows=[]
    for j in range(args.games):
        gid=args.shard*args.games+j
        r=(fair_d4(gid,args.beam,args.candidate_limit) if args.mode=="fair_d4"
           else strict_T2(gid,args.beam,args.candidate_limit,VARIANTS[args.mode]))
        rows.append(r)
        print("FAIR_RANDOM_GAME",args.mode,json.dumps(r),flush=True)
    variant=VARIANTS[args.mode]
    deck=prior.buck.VARIANTS[variant]
    result={"schema":"dack_unbiased_v1","mode":args.mode,"variant":variant,
            "beam":args.beam,"candidate_limit":args.candidate_limit,
            "seed_base":SEED_BASE,"shard":args.shard,"games":args.games,
            "deck_sha256":hashlib.sha256("\n".join(deck).encode()).hexdigest(),
            "rows":rows}
    with gzip.open(args.out,"wt",encoding="utf8") as f:json.dump(result,f,separators=(",",":"))
    print("FAIR_RANDOM_SHARD_PASS",args.mode,args.games,flush=True)

if __name__=="__main__":main()
