#!/usr/bin/env python3
"""Isolated performance breakdown of paired reference game without changing decisions."""
from __future__ import annotations
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

import dack_paired_counterfactual_v1_20261030 as p

def profile(variant, game_id):
    p.audit()
    per_stage = defaultdict(lambda:{"calls":0,"seconds":0.0})
    real_keep = p.batch.evaluate_keep
    real_game_search = p.d._win_turn_from_unknown_order
    summary={"evaluations":0,"evaluate_seconds":0.0,
             "search_calls":0,"search_seconds":0.0}
    phase=["keep"]
    def evaluate_keep(*args,**kwargs):
        stage=int(args[1])
        tick=time.perf_counter()
        try:return real_keep(*args,**kwargs)
        finally:
            delta=time.perf_counter()-tick
            per_stage[stage]["calls"]+=1
            per_stage[stage]["seconds"]+=delta
            summary["evaluations"]+=1
            summary["evaluate_seconds"]+=delta
    def search(*args,**kwargs):
        tick=time.perf_counter()
        try:return real_game_search(*args,**kwargs)
        finally:
            if phase[0]=="gameplay":
                summary["search_calls"]+=1
                summary["search_seconds"]+=time.perf_counter()-tick
    real_choose=p.choose_keep
    def choose_keep(*args,**kwargs):
        t=time.perf_counter()
        try:return real_choose(*args,**kwargs)
        finally:
            summary["keep_total_seconds"]=time.perf_counter()-t
            phase[0]="gameplay"
    p.batch.evaluate_keep=evaluate_keep
    p.d._win_turn_from_unknown_order=search
    p.choose_keep=choose_keep
    t=time.perf_counter()
    try:result=p.game(variant,game_id)
    finally:
        p.batch.evaluate_keep=real_keep
        p.d._win_turn_from_unknown_order=real_game_search
        p.choose_keep=real_choose
    total=time.perf_counter()-t
    summary.update({
        "variant":variant,"game_id":game_id,
        "total_seconds":total,"keep_seconds":summary["keep_total_seconds"],
        "gameplay_seconds":summary["search_seconds"],
        "other_seconds":total-summary["keep_total_seconds"]-summary["search_seconds"],
        "game_result":{"keep_n":result["keep_n"],"win_turn":result["win_turn"],
                       "seat":result["seat"]},
        "per_keep_size":dict(sorted(per_stage.items(),reverse=True)),
        "rules_version":p.RULES_VERSION,
    })
    print("COUNTERFACTUAL_COST_PROFILE",json.dumps(summary,sort_keys=True),flush=True)
    return summary

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--variant",default="one_key_34")
    a.add_argument("--game-id",type=int,default=0)
    opt=a.parse_args()
    profile(opt.variant,opt.game_id)
