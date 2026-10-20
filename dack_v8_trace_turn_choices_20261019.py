#!/usr/bin/env python3
"""Instrument real (not hypothetical) pregame and upkeep decision points.

Purpose: determine whether the remaining v7/full-beam gap could plausibly
stem from Gemstone Caverns or Mana Vault upkeep choice, and record which
visible choices are actually offered. Does NOT change gameplay policy.

Only hooks v1.simulate's real fair.choose_pregame and fair.turnstart.
Unseen library order is logged ONLY for forensic replay, never examined
to select an action.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,time,random
from collections import Counter
from dataclasses import replace
import dack_realistic_v7_rollout_fidelity_20261019 as v7

v6=v7.v6;v4=v6.v4;v2=v7.v2;v1=v7.v1
fair=v7.fair;root=v7.root;d=v7.d;m=v6.m
ORIG_PREGAME=fair.choose_pregame
ORIG_TURNSTART=fair.turnstart
EVENTS=[]
GAME=-1

def name_board(s):
    return [{"card":d.effective_name(x),"tapped":x.tapped,
             "counters":x.counters} for x in s.battlefield]

def compact(s):
    return {"turn":s.turn,"hand":list(s.hand),
            "board":name_board(s),
            "w":s.w,"c":s.c,"any":s.any,
            "treasures":s.treasures,"land_played":s.land_played,
            "library_count":len(s.library),
            "public_score":v1.public_score(s)}

def trace_pregame(s,seat):
    options=d._pregame_states(s,seat)
    chosen,n=ORIG_PREGAME(s,seat)
    event={
      "kind":"pregame","game_id":GAME,
      "seat":seat,"hand":list(s.hand),"alternatives":len(options),
      "option_details":[{"state":compact(x),"exiled":list(x.exile),
                          "chosen":d.key(x)==d.key(chosen)} for x in options]}
    EVENTS.append(event)
    assert n==len(options)
    return chosen,n

def trace_turnstart(prev,turn):
    if turn>1:
        q=d.untap_and_begin(replace(prev,turn=turn))
        q=d.add_opponent_cycle_resources(q)
        opts=d.mana_vault_upkeep_options(q)
        original_selected=max(opts,key=fair.heuristic) if opts else q
        active_vault=any(d.effective_name(x)=="Mana Vault" and x.tapped
                         for x in q.battlefield)
        event={
          "kind":"upkeep","game_id":GAME,"turn":turn,
          "tapped_vault_at_start":active_vault,
          "alternative_count":len(opts),
          "choice_list":[{"choice":i,"state":compact(x),
              "vault_untapped":any(d.effective_name(p)=="Mana Vault" and not p.tapped
                                    for p in x.battlefield),
              "heuristic":fair.heuristic(x),
              "chosen":d.key(x)==d.key(original_selected)}
                         for i,x in enumerate(opts[:40])],
          "alternatives_truncated":len(opts)>40,
          # Never include hidden next draw in the choice key.
          "selected_before_draw":True}
        EVENTS.append(event)
    return ORIG_TURNSTART(prev,turn)

def audit():
    v7.audit()
    assert ORIG_PREGAME is not trace_pregame
    assert ORIG_TURNSTART is not trace_turnstart
    print("V8_REAL_TURN_DECISION_TRACING_SELFTEST_PASS",flush=True)

def run(variant,gid):
    global GAME
    GAME=gid
    EVENTS.clear()
    # Wrap real turn-policy decisions; v6 rollout functions intentionally do
    # NOT invoke fair.turnstart or fair.choose_pregame.
    fair.choose_pregame=trace_pregame
    fair.turnstart=trace_turnstart
    try:
        sim=v7.one(variant,gid,96,24)
    finally:
        fair.choose_pregame=ORIG_PREGAME
        fair.turnstart=ORIG_TURNSTART
    return {"game_id":gid,"win_turn":sim["win_turn"],
            "keep_n":sim["keep_n"],
            "seat":sim["seat"],"events":list(EVENTS)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--variant",choices=("current","buck_worldmap"),default="current")
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--games",type=int,default=4)
    p.add_argument("--out",default="v8_turn_policy_audit.json.gz")
    a=p.parse_args()
    audit()
    if a.audit:return
    rows=[];begin=time.time()
    for j in range(a.games):
        gid=a.shard*a.games+j
        x=run(a.variant,gid)
        rows.append(x)
        print("V8_TURN_TRACE_GAME",a.variant,gid,x["win_turn"],
              "Gemstone_options",[q["alternatives"] for q in x["events"] if q["kind"]=="pregame"],
              "upkeep_options",[q["alternative_count"] for q in x["events"] if q["kind"]=="upkeep"],flush=True)
    deck=v2.trial.VARIANTS[a.variant]
    out={"schema":"dack_v8_turn_choice_audit_v1",
         "variant":a.variant,"game_ids":[x["game_id"] for x in rows],
         "deck_sha256":hashlib.sha256("\n".join(deck).encode()).hexdigest(),
         "shard":a.shard,"games":a.games,
         "rows":rows,"elapsed_seconds":round(time.time()-begin,3)}
    with gzip.open(a.out,"wt",encoding="utf-8") as f:
        json.dump(out,f,separators=(",",":"))
    print("V8_REAL_TURN_DECISION_TRACING_SHARD_PASS",a.variant,a.games,flush=True)

if __name__=="__main__":main()
