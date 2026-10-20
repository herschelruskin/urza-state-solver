#!/usr/bin/env python3
"""Realistic Beam v10 diagnostic: original Full-Beam-calibrated London hand keeps.

Instrument the SAME exact Realistic v6 gameplay; record the actual sampled
London mulligan evaluator, thresholds, acceptance margins and future actual
turn of Dack deployment for each game. Nothing about gameplay or keep policy
is altered. Intended to identify miscalibrated keeps before modifying them.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json
from collections import Counter
import dack_realistic_v6_stratified_reward_20261019 as v6

root=v6.root;v2=v6.v2
ORIGINAL_CHOOSE=root.choose_hand_with_free

def run(variant,gid):
    reports=[]
    def instrumented_choose(rng,seat):
        s,n,audit=ORIGINAL_CHOOSE(rng,seat)
        reports.append({"keep_n":n,"steps":audit,
           "final_margin":float(audit[-1]["utility"])-float(audit[-1]["threshold"]),
           "final_raw":float(audit[-1]["utility"]),
           "final_threshold":float(audit[-1]["threshold"]),
           "free_mull_used":len(audit)>1})
        return s,n,audit
    root.choose_hand_with_free=instrumented_choose
    try:
        q=v6.simulate(variant,gid,12,6)
    finally:
        root.choose_hand_with_free=ORIGINAL_CHOOSE
    assert len(reports)==1 and reports[0]["keep_n"]==q["keep_n"]
    return {"game_id":gid,"win_turn":q["win_turn"],
        "keep_n":q["keep_n"],"mulligan":reports[0]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--variant",choices=("current","buck_worldmap"),required=True)
    p.add_argument("--shard",type=int,required=True)
    p.add_argument("--games",type=int,default=4)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    assert a.shard>=0 and a.games>0
    v6.audit()
    rows=[]
    for j in range(a.games):
        gid=a.shard*a.games+j
        r=run(a.variant,gid)
        rows.append(r)
        print("MULLIGAN_AUDIT_GAME",a.variant,gid,
              "keep",r["keep_n"],"raw",r["mulligan"]["final_raw"],
              "threshold",r["mulligan"]["final_threshold"],
              "win",r["win_turn"],flush=True)
    data={"schema":"dack_realistic_original_london_policy_diagnostic_v10",
      "variant":a.variant,"shard":a.shard,"games":a.games,
      "seed_base":v2.SEED_BASE,
      "deck_sha256":hashlib.sha256("\n".join(v2.trial.VARIANTS[a.variant]).encode()).hexdigest(),
      "counts":{str(k):v for k,v in Counter(x["win_turn"] for x in rows).items()},
      "rows":rows}
    with gzip.open(a.out,"wt",encoding="utf8") as f:
        json.dump(data,f,separators=(",",":"))
    print("REALISTIC_MULLIGAN_TRACE_SHARD_PASS",a.variant,a.games,flush=True)
if __name__=="__main__":main()
