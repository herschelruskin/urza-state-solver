#!/usr/bin/env python3
"""No gameplay beam: calibrate proxy keep aggressiveness on disjoint training hands.

Match an externally fixed *mean keep size* (5.125) from a prior 1,024-game
historical assertive benchmark. This is policy calibration, NOT fitting win
rates or true cast probabilities. It does not establish policy quality.

All training seeds are disjoint from the four N4 pilot seeds. Print an
entire cutoff table so v6b can freeze it before separate gameplay holdout.
"""
from __future__ import annotations
import argparse
import json
from statistics import mean

import dack_paired_counterfactual_v1_20261030 as ref
import dack_mulligan_analytic_policy_v6_20261031 as model

TARGET_KEEP=5.125
TRAIN_START=10000
TRAIN_GAMES=512
VARIANT="one_key_34"

def collect(start,count):
    deck=ref.SLOT_VARIANTS[VARIANT]
    features=[]
    for gid in range(start,start+count):
        seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,stages=ref.stage_slots(seed)
        game=[]
        for keep_n,order in zip(ref.sim.STAGES,stages):
            seven=[deck[x] for x in order[:7]]
            unknown=[deck[x] for x in order[7:]]
            _,_,feat=model.select_bottom(seven,keep_n,unknown,seat)
            game.append((int(keep_n),float(feat["proxy_utility"])))
        features.append(game)
    return features

def policy_mean_keep(scores,scale):
    kept=[]
    for game in scores:
        outcome=1
        for keep_n,score in game:
            if keep_n==1 or score>=model.CUTOFFS[keep_n]*scale:
                outcome=keep_n
                break
        kept.append(outcome)
    return mean(kept),{str(k):kept.count(k) for k in sorted(set(kept))}

def calibrate(scores,target):
    lo=0.;hi=2.
    for _ in range(38):
        mid=(lo+hi)/2
        observed,_=policy_mean_keep(scores,mid)
        if observed>target:
            lo=mid
        else:
            hi=mid
    best=min([lo,(lo+hi)/2,hi],
             key=lambda x:abs(policy_mean_keep(scores,x)[0]-target))
    obs,distribution=policy_mean_keep(scores,best)
    return {"scale":best,"mean_keep_training":obs,
            "keep_distribution_training":distribution,
            "cutoffs":{str(k):round(v*best,8) for k,v in model.CUTOFFS.items()}}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,default=TRAIN_START)
    p.add_argument("--games",type=int,default=TRAIN_GAMES)
    p.add_argument("--out",default="benchmark_results/analytic_london_v6_aggressiveness_training_512.json")
    args=p.parse_args()
    assert not set(range(args.start,args.start+args.games)).intersection(range(0,6))
    scores=collect(args.start,args.games)
    result={
        "schema":"dack_analytic_london_aggressiveness_calibration_v1",
        "training_start":args.start,"training_n":args.games,
        "variant":VARIANT,"target_historical_mean_keep":TARGET_KEEP,
        "used_gameplay_beam":False,"used_future_reveal":False,
        "trained_on_gameplay_results":False,
        "policy_formula_version":model.POLICY_VERSION,
        "fixed_baseline_mean_keep_source":"dack_onekey_36lands_untaidake_n1024_20261030_report.json",
        "unscaled_mean_keep":policy_mean_keep(scores,1.)[0],
        "candidates":[{"scale":s,"mean_keep":policy_mean_keep(scores,s)[0]}
                      for s in (.1,.2,.3,.4,.5,.6,.7,.8,1.0,1.5)],
        "selection":calibrate(scores,TARGET_KEEP)
    }
    from pathlib import Path
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+"\n")
    print("ANALYTIC_KEEP_CALIBRATION",json.dumps(result),flush=True)
