#!/usr/bin/env python3
"""V11 experimental observation barrier for Scroll Rack / Brainstone.

Within-turn deterministic mana sequences still use the normal beam.
Rack/Brainstone activation is explicitly a *pre-reveal action*: choose the
payment / cards placed by Scroll Rack by expectation over sampled top cards,
then observe physical cards and resume beam after the new information exists.
Brainstone pays and draws three, then selects the two cards put back AFTER
revealing those three cards (as rules require).

The original unmodified full-beam, v6, v7 and v10 remain on their branches.
Other within-turn hidden events (Staff, cantrips, Tezzeret reshuffles)
still require later barriers; this is deliberately scoped, not a claim that
all hidden-information errors are fixed.
"""
from __future__ import annotations
import argparse,gzip,hashlib,itertools,json,random,time
from collections import Counter
from dataclasses import replace
import dack_v10_blind_mulligan_20261019 as v10

v7=v10.v7; v6=v7.v6; v4=v6.v4; v2=v7.v2; v1=v7.v1
fair=v7.fair; d=v7.d; root=v7.root; m=v6.m
ORIG_REPAIR=d.repair_actions
ORIG_TURN=v1.realistic_turn
ACTIVE_CONTEXT=None
SAMPLES=4
PLAN_CAP=8
SOURCE_CAP=4
SEARCH_BEAM=42
SEARCH_DEPTH=18
AUDIT={"considered":0,"activated":0,"rack":0,"brainstone":0,"counterfactual_rollouts":0}

def has_ready(s,name):
    return any(d.effective_name(x)==name and not x.tapped for x in s.battlefield)

def is_rack_result(s,q):
    for i,p in enumerate(s.battlefield):
        if d.effective_name(p)=="Scroll Rack" and not p.tapped:
            if i<len(q.battlefield) and d.effective_name(q.battlefield[i])=="Scroll Rack" and q.battlefield[i].tapped:
                return True
    return False

def is_brain_result(s,q):
    return q.grave.count("Brainstone")>s.grave.count("Brainstone")

def filter_reveals(s):
    if ACTIVE_CONTEXT is not None and (has_ready(s,"Scroll Rack") or
                                       has_ready(s,"Brainstone")):
        k=v1.private_order_free_signature(s)
        ACTIVE_CONTEXT.setdefault(k,s)
    return [q for q in ORIG_REPAIR(s)
            if not is_rack_result(s,q) and not is_brain_result(s,q)]

def plans_for(s):
    out=[]
    for name,cost in (("Scroll Rack",1),("Brainstone",2)):
        if not has_ready(s,name):continue
        if name=="Scroll Rack" and (not s.hand or not s.library):continue
        if name=="Brainstone" and len(s.library)<3:continue
        for paid in d.pay_options(s,cost):
            idx=next((i for i,p in enumerate(paid.battlefield)
                if d.effective_name(p)==name and not p.tapped),None)
            if idx is None:continue
            if name=="Brainstone":
                out.append((name,paid,idx,()))
                continue
            # Scroll Rack: the subset/putback order is chosen BEFORE drawing.
            H=list(paid.hand)
            max_k=min(3,len(H),len(paid.library))
            for k in range(1,max_k+1):
                for indices in itertools.combinations(range(len(H)),k):
                    putback=tuple(H[i] for i in indices)
                    if k>1:
                        # Legal order selection is committed before reveal.
                        orders=(putback,tuple(reversed(putback)))
                    else:orders=(putback,)
                    for order in dict.fromkeys(orders):
                        out.append((name,paid,idx,order))
    return out

def public_plan_score(plan):
    name,paid,idx,putback=plan
    score=v1.public_score(paid)
    if name=="Scroll Rack":
        # Prioritize getting combo creatures BACK in library, but never
        # condition candidate selection on unknown top card.
        score+=90*sum(x in root.COMBO for x in putback)
        score-=6*sum(x in d.RAMP_PROTECTED for x in putback)
    return score

def best_public_plans(sources):
    out=[]
    for s in v1.short_list(sources,SOURCE_CAP):
        out.extend(plans_for(s))
    # Deduplicate by information-visible mana payment and planned putbacks.
    dedup={}
    for plan in sorted(out,key=public_plan_score,reverse=True):
        name,paid,idx,putback=plan
        signature=(name,v1.private_order_free_signature(paid),idx,putback)
        dedup.setdefault(signature,plan)
        if len(dedup)>=PLAN_CAP:break
    return list(dedup.values())

def sample_library(paid,name,j):
    known=v4.known_top(paid)
    cards=sorted(paid.library)
    if known is not None:
        cards.remove(known)
    seed=int.from_bytes(hashlib.sha256(
        f"{v1.TRIAL_SEED}|observation-{name}|turn{paid.turn}|sample{j}|{len(cards)}".encode()
    ).digest()[:16],"big")
    rng=random.Random(seed)
    rng.shuffle(cards)
    return ((known,)+tuple(cards)) if known is not None else tuple(cards)

def resolve(plan,source_library):
    name,paid,idx,putback=plan
    # Actual physical sample cannot be consulted UNTIL the plan is chosen.
    bf=list(paid.battlefield)
    if name=="Scroll Rack":
        H=list(paid.hand)
        for x in putback:H.remove(x)
        k=len(putback)
        after=replace(paid,hand=d.sort_hand(tuple(H)+tuple(source_library[:k])),
                      library=putback+tuple(source_library[k:]),
                      battlefield=tuple(replace(p,tapped=True) if i==idx else p
                                         for i,p in enumerate(bf)),
                      repaired=paid.repaired+sum(x in root.COMBO for x in putback))
        v4.register_known(after.library,putback[0])
        return [after]
    # Brainstone draws 3, then player chooses ANY two cards from whole hand.
    bf.pop(idx)
    pool=list(paid.hand)+list(source_library[:3])
    results={}
    for inds in itertools.combinations(range(len(pool)),2):
        kept=[x for i,x in enumerate(pool) if i not in inds]
        picked=(pool[inds[0]],pool[inds[1]])
        orders=(picked,tuple(reversed(picked))) if picked[0]!=picked[1] else (picked,)
        for order in orders:
            after=replace(paid,hand=d.sort_hand(tuple(kept)),
              library=order+tuple(source_library[3:]),
              battlefield=tuple(bf),grave=paid.grave+("Brainstone",),
              repaired=paid.repaired+sum(x in root.COMBO for x in order))
            results[d.key(after)]=after
            v4.register_known(after.library,order[0])
    return list(results.values())

def evaluate_plan(plan):
    name,paid,idx,putback=plan
    values=[]
    for j in range(SAMPLES):
        libs=sample_library(paid,name,j)
        candidates=resolve(plan,libs)
        wins,front=d.search_turn_frontier_many(candidates,
                                                beam=SEARCH_BEAM,depth=SEARCH_DEPTH)
        AUDIT["counterfactual_rollouts"]+=1
        if wins:
            values.append(2.0 if paid.turn==1 else (1.6 if paid.turn==2 else 1.2))
        elif paid.turn<3 and front:
            values.append(max(v1.expected_future_value(x)
                        for x in v1.short_list(front,2)))
        else:
            values.append(0.)
    return sum(values)/len(values)

def v11_turn(start,beam,dice):
    global ACTIVE_CONTEXT
    before_roll={}
    ACTIVE_CONTEXT={}
    fair.overridden_roll(1)
    def filter_roll(s):
        if any(d.effective_name(p)==v1.PURSE and not p.tapped
               for p in s.battlefield):
            before_roll[v1.private_order_free_signature(s)]=s
        return fair.utility_without_roll(s)
    d.utility_actions=filter_roll
    d.repair_actions=filter_reveals
    try:
        wins,front=d.search_turn_frontier_many([start],beam=beam,
                                                depth=22 if start.turn==1 else 24)
        if wins:
            return True,max(wins,key=v1.public_score),{"phase":"pre-observation win",
                "die":None,"obs":None}
        base,template,_,basevalue,_=v1.select_plan(front,list(before_roll.values()),start.turn)
        if base is None:base=start
        plans=best_public_plans(list(ACTIVE_CONTEXT.values()))
        AUDIT["considered"]+=len(plans)
        chosen=None
        best=basevalue
        for plan in plans:
            reward=evaluate_plan(plan)
            if reward>best:
                best=reward;chosen=plan
        if chosen is not None:
            name,paid,idx,putback=chosen
            # Real hidden information is revealed ONLY now.
            outcomes=resolve(chosen,paid.library)
            w,fr=d.search_turn_frontier_many(outcomes,beam=beam,
                           depth=22 if start.turn==1 else 24)
            AUDIT["activated"]+=1;AUDIT["rack"]+=int(name=="Scroll Rack")
            AUDIT["brainstone"]+=int(name=="Brainstone")
            if w:
                return True,max(w,key=v1.public_score),{
                    "phase":"post-observation win","die":None,"obs":name,
                    "obs_plan_value":round(best,4)}
            if fr and start.turn<3:
                x=max(v1.short_list(fr,9),key=v1.expected_future_value)
            else:x=max(fr,key=v1.public_score) if fr else outcomes[0]
            return False,x,{"phase":"post-observation pass",
                "die":None,"obs":name,"obs_plan_value":round(best,4)}
        if template is None:
            return False,base,{"phase":"expected-draw pass",
                "die":None,"obs":None,"pass_value":round(basevalue,4)}
        die=dice.randint(1,4)
        q=replace(template,treasures=template.treasures+die-1)
        w,fr=d.search_turn_frontier_many([q],beam=beam,
                                         depth=22 if start.turn==1 else 24)
        if w:return True,max(w,key=v1.public_score),{"phase":"post-roll win","die":die,"obs":None}
        x=(max(v1.short_list(fr,9),key=v1.expected_future_value)
           if fr and start.turn<3 else (max(fr,key=v1.public_score) if fr else q))
        return False,x,{"phase":"post-roll pass","die":die,"obs":None}
    finally:
        ACTIVE_CONTEXT=None
        d.utility_actions=fair.ORIG_UTILITY
        d.repair_actions=ORIG_REPAIR

def install():
    v1.realistic_turn=v11_turn

def audit():
    v10.selftest()
    root.install("current")
    v6.v4.KNOWN.clear()
    v2.activate_v2(3,2,2)
    v6.setup(12,6)
    v1.configure(v2.SEED_BASE,3,9,3,42,18)
    s=d.State(1,("Boonweaver Giant","Plains"),
       tuple(root.COMBO)+("Sol Ring","Mana Vault","Ancient Tomb","Plains"),
       battlefield=(d.Perm("Scroll Rack"),),c=1)
    a=next(x for x in plans_for(s) if x[0]=="Scroll Rack" and
           x[3]==("Boonweaver Giant",))
    a1=replace(a[1],library=s.library)
    outcomes=resolve(a,s.library)
    assert any("Boonweaver Giant" in q.library and
               "Boonweaver Giant" not in q.hand for q in outcomes)
    assert all(q.library[0]=="Boonweaver Giant" for q in outcomes)
    # The pay/putback choice is independent of the unobserved top card.
    reversed_s=replace(s,library=tuple(reversed(s.library)))
    b=next(x for x in plans_for(reversed_s) if x[0]=="Scroll Rack" and
           x[3]==("Boonweaver Giant",))
    assert a[0]==b[0] and a[3]==b[3]
    assert a[1].hand==b[1].hand and a[1].battlefield==b[1].battlefield
    brain=d.State(1,("Plains",),tuple(root.COMBO)+("Mana Vault","Sol Ring"),
                  battlefield=(d.Perm("Brainstone"),),c=2)
    op=next(x for x in plans_for(brain) if x[0]=="Brainstone")
    results=resolve(op,brain.library)
    assert results and all("Brainstone" in q.grave for q in results)
    assert any("Boonweaver Giant" in q.library for q in results)
    assert all(q.library[:2] for q in results)
    print("DACK_V11_SCROLL_RACK_BRAINSTONE_PREOBSERVATION_PASS",flush=True)

def simulate(variant,gid):
    root.install(variant)
    v4.KNOWN.clear()
    v2.activate_v2(3,2,2)
    d._WIN_CACHE.clear()
    v6.setup(12,6)
    install()
    before=dict(AUDIT)
    q=v1.simulate(variant,gid,120,9,3,3,42,18)
    return {"game_id":gid,"keep_n":q["keep_n"],"seat":q["seat"],
      "win_turn":q["win_turn"],"turn_audit":q["turn_audit"],
      "rolls":q["rolls"],"observation_activations":sum(1 for x in q["turn_audit"] if x["obs"]),
      "planning_counterfactual_samples":AUDIT["counterfactual_rollouts"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--variant",choices=("current","buck_worldmap"),default="current")
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--games",type=int,default=1)
    p.add_argument("--out",default="dack_v11_observation.json.gz")
    a=p.parse_args()
    audit()
    if a.audit:return
    rows=[];t0=time.time()
    for i in range(a.games):
        gid=a.shard*a.games+i
        q=simulate(a.variant,gid)
        rows.append(q)
        print("V11_OBSERVATION_BARRIER_GAME",a.variant,gid,q["win_turn"],
              "activation",q["observation_activations"],flush=True)
    out={"schema":"dack_v11_pre_reveal_rack_brainstone",
        "variant":a.variant,"shard":a.shard,"games":a.games,
        "policy":"No Scroll Rack/Brainstone hidden outcome in preactivation beam; evaluate plan over counterfactual draws, then actual reveal; other draw actions still legacy",
        "n_hidden_draw_samples":SAMPLES,
        "deck_sha256":hashlib.sha256("\n".join(v2.trial.VARIANTS[a.variant]).encode()).hexdigest(),
        "elapsed_seconds":round(time.time()-t0,2),
        "counts":dict(Counter(x["win_turn"] for x in rows)),
        "rows":rows}
    with gzip.open(a.out,"wt",encoding="utf8") as f:json.dump(out,f,separators=(",",":"))
    print("V11_OBSERVATION_BARRIER_SHARD_PASS",a.variant,a.games,flush=True)
if __name__=="__main__":main()
