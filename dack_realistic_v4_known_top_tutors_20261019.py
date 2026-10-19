#!/usr/bin/env python3
"""Realistic Beam v4 known-top observation trial.

Track the identity of an actual library tuple produced by Enlightened Tutor
or Loyal Tutor. This card is publicly known to its controller. Future-draw
rollouts must use the known card, while shuffling ONLY the unknown remainder.

Library tuple identity is tracked with strong references (avoids Python id
reuse) and cleared between games. New shuffles necessarily yield a new tuple
and lose the tag; drawing the tutored card consumes the tagged tuple.
This is a narrowly scoped experiment, NOT complete information-state tracking.

Also reserves up to 3 pass candidates with legally known top cards rather than
pruning those lines by a score intended for generic random draws.
"""
from __future__ import annotations
import argparse,hashlib,json,random
from pathlib import Path
from dataclasses import replace
import dack_realistic_information_beam_v2_20261017 as v2

v1=v2.v1
fair=v2.fair
root=v2.root
d=v2.d
m=v2.m
KNOWN={}
ORIG_CAST=None
ORIG_KEY=None
ORIG_SIG=None
ORIG_NEXT=None
ORIG_SHORT=None
ACTIVE=False
EXPECTED={
    "current":{0:0,1:0,22:3},
    "buck_worldmap":{0:0,1:0,22:3,31:0}
}

def register_known(lib,target):
    assert lib and lib[0]==target
    KNOWN[id(lib)]=(lib,target)

def known_top(state):
    rec=KNOWN.get(id(state.library))
    if rec is not None and rec[0] is state.library:
        assert rec[1]==state.library[0]
        return rec[1]
    return None

def known_cast_actions(state):
    successors=ORIG_CAST(state)
    for q in successors:
        for n in ("Enlightened Tutor","Loyal Tutor"):
            if (n in state.hand and n not in q.hand
                  and q.grave.count(n)>state.grave.count(n)
                  and len(q.library)==len(state.library)-1
                  and q.library):
                register_known(q.library,q.library[0])
    return successors

def knowledge_key(state):
    return ORIG_KEY(state)+(known_top(state),)

def knowledge_signature(state):
    return ORIG_SIG(state)+(known_top(state),)

def known_next_draw(state,sample_index):
    expected=known_top(state)
    if expected is None:return ORIG_NEXT(state,sample_index)
    assert state.library and state.library[0]==expected
    unknown=sorted(state.library[1:])
    material=f"{v1.TRIAL_SEED}|unknown-tail|{state.turn}|{sample_index}|{len(unknown)}"
    seed=int.from_bytes(hashlib.sha256(material.encode()).digest()[:8],"big")
    random.Random(seed).shuffle(unknown)
    start=d.untap_and_begin(replace(state,turn=state.turn+1))
    start=d.add_opponent_cycle_resources(start)
    # Like the original planner: select Mana Vault upkeep before revealing
    # the top card (although it is already known here, this is conservative).
    options=list(d.mana_vault_upkeep_options(start))
    start=max(options,key=v1.public_score) if options else start
    start=replace(start,library=(expected,)+tuple(unknown))
    return d.begin_first_main(d.saga_advance(d.draw(start,1)))

def known_short_list(states,cap):
    # Candidate retention must not erase tutor-established information before
    # its future win chance is assessed. Still leave most slots for generic lines.
    all_states=ORIG_SHORT(states,len(states))
    if cap>=len(all_states):return all_states
    known=[x for x in all_states if known_top(x) is not None]
    quota=min(3,max(1,cap//3))
    chosen=known[:quota]
    seen={v1.private_order_free_signature(q) for q in chosen}
    for state in all_states:
        if len(chosen)>=cap:break
        sig=v1.private_order_free_signature(state)
        if sig in seen:continue
        chosen.append(state);seen.add(sig)
    return chosen

def install():
    global ACTIVE,ORIG_CAST,ORIG_KEY,ORIG_SIG,ORIG_NEXT,ORIG_SHORT
    if ACTIVE:return
    ORIG_CAST=d.cast_actions
    ORIG_KEY=d.key
    ORIG_SIG=v1.private_order_free_signature
    ORIG_NEXT=v1.hypothetical_next_start
    ORIG_SHORT=v1.short_list
    d.cast_actions=known_cast_actions
    d.key=knowledge_key
    v1.private_order_free_signature=knowledge_signature
    v1.hypothetical_next_start=known_next_draw
    v1.short_list=known_short_list
    ACTIVE=True

def audit():
    v2.selftest()
    root.install("current")
    fair.install_honest_scry()
    install()
    KNOWN.clear()
    base=d.State(1,("Enlightened Tutor",),
       tuple(root.COMBO)+("Lion's Eye Diamond","Mana Vault","Plains"),w=1)
    successors=d.cast_actions(base)
    tutors=[q for q in successors if q.grave.count("Enlightened Tutor")>0]
    assert tutors,("no Enlightened Tutor cast in audit")
    assert all(known_top(q)==q.library[0] for q in tutors)
    first=tutors[0]
    v1.configure(v2.SEED_BASE,3,9,3,42,18)
    q1=v1.hypothetical_next_start(first,0)
    q2=v1.hypothetical_next_start(first,1)
    target=known_top(first)
    assert target in q1.hand and target in q2.hand
    assert not any(known_top(q) for q in (q1,q2))
    # Unknown top order is never selected by the rollout; known top must
    # produce the same drawn card even if the hidden tail is permuted.
    alt=replace(first,library=(target,)+tuple(reversed(first.library[1:])))
    register_known(alt.library,target)
    assert target in v1.hypothetical_next_start(alt,0).hand
    # Metadata is invalidated on any library change without explicit tutor.
    untagged=replace(first,library=tuple(reversed(first.library)))
    assert known_top(untagged) is None
    assert d.key(first)!=d.key(untagged)
    KNOWN.clear()
    print("DACK_KNOWN_TOP_TUTOR_POLICY_AUDIT_PASS",flush=True)

def play(variant,gid,with_known):
    KNOWN.clear()
    root.install(variant)
    # The audit already installed the honest-scry wrapper beneath our
    # known-tutor wrapper. Do not reinstall fair scry here or it would
    # silently replace the instrumentation.
    v2.activate_v2(draws=3,t3_samples=2,t2_continuations=2)
    if with_known:
        assert ACTIVE and d.cast_actions is known_cast_actions
        assert d.key is knowledge_key
    d._WIN_CACHE.clear()
    result=v1.simulate(variant,gid,120,9,3,3,42,18)
    return {"win_turn":result["win_turn"],
        "keep_n":result["keep_n"],"rolls":result["rolls"],
        "rollout_calls":result["planning_counts"]["rollout_calls"],
        "turns":[{"turn":x["turn"],"phase":x["phase"],
                  "pass_candidates":x.get("pass_candidates"),
                  "pass_value":x.get("pass_value")} for x in result["turn_audit"]]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--variant",choices=tuple(EXPECTED),default="current")
    p.add_argument("--gid",type=int,default=0)
    p.add_argument("--out",default="known_top_qa.json")
    a=p.parse_args()
    audit()
    if a.audit:return
    assert a.gid in EXPECTED[a.variant]
    # Apply baseline before installing the optional known-info wrappers.
    # Audit has installed them, so baseline comparisons are sourced from
    # separately verified archived v2 outcomes, not an invalid in-process AB.
    known=play(a.variant,a.gid,True)
    result={"status":"PASS","variant":a.variant,"game_id":a.gid,
        "frozen_v2_win_turn":EXPECTED[a.variant][a.gid],
        "known_top_v4":known,
        "T2_recovered":bool(0<known["win_turn"]<=2 and
                            EXPECTED[a.variant][a.gid] not in (1,2)),
        "T3_recovered":bool(known["win_turn"] and
                            not EXPECTED[a.variant][a.gid]),
        "limits":[
            "Tutors tracked by library tuple identity; some known cards from other effects not tracked",
            "A new shuffle creates an untagged library as intended",
            "Information tags are lost if the engine internally reconstructs an identical library tuple",
            "Chosen known-top candidate quota is a heuristic; requires population testing",
            "Inherited within-turn draw lookahead still exists",
            "Goldfish and finite rollout beam, not calibrated game win rate"]}
    Path(a.out).write_text(json.dumps(result,indent=2)+"\n")
    print("DACK_KNOWN_TOP_REPLAY_PASS",json.dumps({
        "variant":a.variant,"gid":a.gid,"v2":EXPECTED[a.variant][a.gid],
        "v4":known["win_turn"],"recovered_T2":result["T2_recovered"]}),flush=True)

if __name__=="__main__":main()
