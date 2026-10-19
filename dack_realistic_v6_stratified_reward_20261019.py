#!/usr/bin/env python3
"""Dack Realistic Beam v6: stratified, probability-weighted future draws.

Keep the v4 known-top info-set hooks and frozen v2 beam mechanics. Replace
v5's IID Monte Carlo draws (with replacement) by a deterministic weighted
stratification of REMAINING UNKNOWN CARDS. Draw candidates are classified by
card role using public deck information, not hidden draw order:

  premium fast mana / critical tutors, white lands, other lands,
  other low-cost artifact mana, other spells.

Every nonempty stratum is sampled at least once. Each selected card is
weighted by (# cards in its stratum / total remaining cards) / (# sampled
cards in that stratum), making the reward an unbiased stratified estimate
of the original uniform next-card distribution for a fixed continuation
policy. Sampling happens without replacement *within strata*.

- Known-top tutoring overrides any random sampling (weight exactly 1).
- Mana Vault upkeep commitments happen before sampling the card.
- The actual unseen draw is NEVER used in action choice.
- Full Beam / Realistic v1-v5 sources remain unchanged.
- Nested T3 evaluation uses the pre-existing independent hidden-draw sampler.
- Still uses finite within-turn beam and may inherit midturn lookahead biases.
"""
from __future__ import annotations
import argparse, gzip, hashlib, json, random, math, time
from collections import Counter
from dataclasses import replace
from pathlib import Path
import dack_realistic_v5_denser_reward_20261019 as v5

v4=v5.v4;v2=v5.v2;v1=v5.v1
d=v5.d;fair=v5.fair;root=v5.root;m=v5.m
ORIG_NEXT=None
SAMPLE_CACHE={}
T1_SAMPLES=12
T2_SAMPLES=6
FAST={
    "Lion's Eye Diamond","Lotus Petal","Sol Ring","Mana Vault",
    "Chrome Mox","Mox Diamond","Mox Opal","Grim Monolith",
    "Basalt Monolith","Moonsilver Key","Tezzeret, Cruel Captain",
    "Enlightened Tutor","Loyal Tutor","Mishra's Workshop"
}
WHITE_EXTRA={"Emeria's Call","Razorgrass Ambush","Razorgrass Field",
             "Gemstone Caverns","Cavern of Souls","Talon Gates of Madara"}

def group(card):
    if card in FAST:return "premium"
    if card in d.GUARANTEED_WHITE_LANDS or card in WHITE_EXTRA:
        return "white"
    if card in d.LANDS:return "other_land"
    if d.is_artifact_perm(card) and card in d.COSTS:
        g,w,cc=d.COSTS[card]
        if g+w+cc<=3:return "other_artifact"
    return "other"

def setup(draws=12,next_draws=6):
    global T1_SAMPLES,T2_SAMPLES,ORIG_NEXT
    assert draws>=5 and next_draws>=5
    T1_SAMPLES=int(draws);T2_SAMPLES=int(next_draws)
    v4.install()
    assert d.cast_actions is v4.known_cast_actions
    ORIG_NEXT=v4.known_next_draw
    v1.hypothetical_next_start=strat_next_start
    v1.expected_future_value=strat_expected_future
    SAMPLE_CACHE.clear()

def weighted_plan(s):
    top=v4.known_top(s)
    if top is not None:
        assert top==s.library[0]
        return [(top,1.0,True)]
    cards=sorted(s.library)
    if not cards:return []
    n=min(len(cards),T1_SAMPLES if s.turn==1 else T2_SAMPLES)
    cachekey=(v1.TRIAL_SEED,v1.private_order_free_signature(s),n)
    got=SAMPLE_CACHE.get(cachekey)
    if got is not None:return got
    strata={}
    for card in cards:strata.setdefault(group(card),[]).append(card)
    distinct=sorted(strata)
    # Once per nonempty stratum (not per card); extra slots allocated by
    # residual proportional mass in a deterministic largest-remainder scheme.
    assert n>=len(distinct)
    allocation={name:1 for name in distinct}
    for _ in range(n-len(distinct)):
        best=max(distinct,key=lambda k:(
            len(strata[k])/max(1,allocation[k]),
            len(strata[k]),
            -distinct.index(k)))
        allocation[best]+=1
    for name in distinct:
        allocation[name]=min(allocation[name],len(strata[name]))
    # Reassign any surplus if a stratum was smaller than its allocated quota.
    while sum(allocation.values())<n:
        choices=[k for k in distinct if allocation[k]<len(strata[k])]
        if not choices:break
        best=max(choices,key=lambda k:len(strata[k])/max(1,allocation[k]))
        allocation[best]+=1
    result=[]
    for name in distinct:
        source=list(strata[name])
        rng=random.Random(int.from_bytes(hashlib.sha256(
            f"{v1.TRIAL_SEED}|strat-draw|{s.turn}|{name}|{len(source)}|{len(cards)}".encode()
        ).digest()[:16],"big"))
        rng.shuffle(source)
        chosen=source[:allocation[name]]
        w=len(strata[name])/len(cards)/len(chosen)
        result.extend((card,w,False) for card in chosen)
    assert len(result)==n,(n,len(result))
    assert abs(sum(w for _,w,_ in result)-1)<1e-9
    SAMPLE_CACHE[cachekey]=result
    return result

def strat_next_start(s,sample_index):
    if sample_index>=10001:
        return ORIG_NEXT(s,sample_index)
    items=weighted_plan(s)
    assert items and 0<=sample_index<len(items), (s.turn,sample_index,len(items))
    card,weight,known=items[sample_index]
    if known:return ORIG_NEXT(s,sample_index)
    tail=list(s.library)
    tail.remove(card)
    rng=random.Random(int.from_bytes(hashlib.sha256(
        f"{v1.TRIAL_SEED}|strat-tail|{s.turn}|{sample_index}|{card}|{len(tail)}".encode()
    ).digest()[:16],"big"))
    tail.sort();rng.shuffle(tail)
    q=d.untap_and_begin(replace(s,turn=s.turn+1))
    q=d.add_opponent_cycle_resources(q)
    # Mana Vault choice is made before any unknown drawn card is in hand.
    opts=list(d.mana_vault_upkeep_options(q))
    q=max(opts,key=v1.public_score) if opts else q
    q=replace(q,library=(card,)+tuple(tail))
    q=d.begin_first_main(d.saga_advance(d.draw(q,1)))
    return q

def strat_expected_future(s):
    if s.turn>=3:return v1.public_score(s)/5000.
    plan=weighted_plan(s)
    if not plan:return v1.public_score(s)/5000.
    return sum(weight*v2.lookahead_T2_T3_value(s,i)
               for i,(_,weight,_) in enumerate(plan))

def audit():
    v5.selftest()
    root.install("current")
    v4.KNOWN.clear()
    v1.configure(v2.SEED_BASE,3,9,3,42,18)
    setup(12,6)
    names=("Mana Vault","Sol Ring","Plains","Ancient Tomb","Enlightened Tutor",
           "Fellwar Stone","Mox Diamond","Moonsilver Key","Command Beacon",
           "Deafening Silence","Brainstone","Crystal Vein","Grim Monolith")
    a=d.State(1,("Plains",),names,w=1)
    b=replace(a,library=tuple(reversed(names)))
    assert v1.private_order_free_signature(a)==v1.private_order_free_signature(b)
    for q in (a,b):
        plan=weighted_plan(q)
        assert abs(sum(w for _,w,_ in plan)-1)<1.e-10
        assert len(set(c for c,_,_ in plan))==len(plan)
        assert set(group(c) for c,_,_ in plan)==set(group(c) for c in names)
    assert weighted_plan(a)==weighted_plan(b)
    for j in range(len(weighted_plan(a))):
        assert strat_next_start(a,j)==strat_next_start(b,j)
    assert strat_expected_future(a)==strat_expected_future(b)
    c=d.State(1,(),("Mana Vault","Plains","Ancient Tomb"),w=1)
    v4.register_known(c.library,"Mana Vault")
    assert weighted_plan(c)==[("Mana Vault",1.,True)]
    assert "Mana Vault" in strat_next_start(c,0).hand
    v4.KNOWN.clear()
    print("DACK_V6_STRATIFIED_UNSEEN_DRAW_AUDIT_PASS",flush=True)

def simulate(variant,gid,draws,next_draws):
    root.install(variant)
    assert d.cast_actions is v4.known_cast_actions
    v4.KNOWN.clear()
    v2.activate_v2(3,2,2)
    d._WIN_CACHE.clear()
    # v1.simulate calls configure(seed), and our expected reward will then
    # consume the newly set seed. Do not reset stratified cache midgame.
    setup(draws,next_draws)
    tic=time.time()
    r=v1.simulate(variant,gid,120,9,3,3,42,18)
    return {"game_id":gid,"win_turn":r["win_turn"],
            "keep_n":r["keep_n"],"rolls":r["rolls"],
            "rollout_calls":r["planning_counts"]["rollout_calls"],
            "turn_audit":r["turn_audit"],
            "elapsed_seconds":round(time.time()-tic,3)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--variant",choices=("current","buck_worldmap"),default="current")
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--games",type=int,default=4)
    p.add_argument("--draws",type=int,default=12)
    p.add_argument("--next-draws",type=int,default=6)
    p.add_argument("--out",default="stratified_v6.json.gz")
    a=p.parse_args()
    audit()
    if a.audit:return
    assert a.shard>=0 and a.games>=1
    rows=[]
    for j in range(a.games):
        gid=a.shard*a.games+j
        x=simulate(a.variant,gid,a.draws,a.next_draws)
        rows.append(x)
        print("DACK_V6_STRATIFIED_GAME",a.variant,gid,x["win_turn"],
              "rollouts",x["rollout_calls"],flush=True)
    variant_cards=v2.trial.VARIANTS[a.variant]
    data={
      "schema":"dack_realistic_stratified_reward_v6",
      "policy":"stratified_visible_information_draws",
      "variant":a.variant,"draws":a.draws,"next_draws":a.next_draws,
      "beam":120,"pass_cap":9,"shard":a.shard,"games":a.games,
      "seed_base":v2.SEED_BASE,
      "deck_sha256":hashlib.sha256("\n".join(variant_cards).encode()).hexdigest(),
      "counts":{str(k):v for k,v in Counter(q["win_turn"] for q in rows).items()},
      "rows":rows}
    with gzip.open(a.out,"wt",encoding="utf8") as f:
        json.dump(data,f,separators=(",",":"))
    print("DACK_V6_STRATIFIED_SHARD_PASS",a.variant,a.games,flush=True)
if __name__=="__main__":main()
