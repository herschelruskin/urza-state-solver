#!/usr/bin/env python3
"""Development-only physically matched full-game sensitivity: frozen v43 DP vs
Q2-max internally consistent MODEL-ONLY DP. No model trained or policy promoted.

DP is rebuilt on untouched 163700..164723 outer deals before outcomes on
164800..164863 are evaluated. v43 and original v27 sources remain frozen.
"""
from __future__ import annotations
import json,random,sys,time
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as v43
from dack_simulator.validation import v43_independent_continuation_selfconsistency_20261101 as dp
ref=v43.ref
START=164800;N=64
OUT=ROOT/"benchmark_results/v43_new_model_only_DP_physical_sensitivity_dev_N64.json"
def metrics(rows,field):
    ans={}
    for t in (1,2,3):
        da=[int(0<r["alternative"]["turn"]<=t)-int(0<r["frozen_v43"]["turn"]<=t) for r in rows]
        rng=random.Random(16480000+t)
        boot=[]
        for _ in range(4000):
            boot.append(100*sum(da[rng.randrange(len(da))] for __ in da)/len(da))
        boot.sort()
        ans["T"+str(t)]={
           "frozen_v43":sum(0<r["frozen_v43"]["turn"]<=t for r in rows),
           "model_only_DP":sum(0<r["alternative"]["turn"]<=t for r in rows),
           "unique_gain":da.count(1),"unique_loss":da.count(-1),
           "paired_delta_pp":round(100*sum(da)/len(da),5),
           "paired_bootstrap95_pp":[boot[99],boot[3899]]}
    return ans

def main():
    t0=time.monotonic()
    v43.audit()
    dp.main()
    table=json.loads((ROOT/"benchmark_results/v43_independent_model_only_continuation_self_consistency_163700_N1024.json").read_text())["seats"]
    original_dp=v43.v27.original.DP
    backup={seat:list(original_dp["seat_continuations"][seat]["thresholds_by_london_stage"]) for seat in map(str,range(4))}
    alt={seat:[float(stage["v43_model_self_consistent_threshold"]) for stage in table[seat]["stage_values"]] for seat in backup}
    for s in backup:
        assert len(backup[s])==len(alt[s])==8 and backup[s][-1]==alt[s][-1]==-1
    rows=[]
    try:
        for gid in range(START,START+N):
            arm={}
            for name,thresholds in (("frozen_v43",backup),("alternative",alt)):
                for seat in backup:
                    original_dp["seat_continuations"][seat]["thresholds_by_london_stage"]=list(thresholds[seat])
                ref.sim.reset_caches()
                out=ref.game("one_key_34",gid)
                arm[name]={
                    "turn":int(out["win_turn"]),"keep_n":int(out["keep_n"]),
                    "seat":out["seat"],"history":out["history"],
                    "hand":list(out["hand"]),
                    "first3":list(out["first3"]),
                    "seconds":None}
            assert arm["frozen_v43"]["seat"]==arm["alternative"]["seat"]
            a,b=arm["frozen_v43"],arm["alternative"]
            assert a["history"][0]["seven"]==b["history"][0]["seven"]
            if a["hand"]==b["hand"] and a["keep_n"]==b["keep_n"] and a["history"][-1]["bottom"]==b["history"][-1]["bottom"]:
                assert a["turn"]==b["turn"],("unchanged-hand downstream parity",gid,a["turn"],b["turn"])
                assert a["first3"]==b["first3"],("unchanged-hand future order parity",gid)
            rows.append({"gid":gid,**arm})
            if (gid-START+1)%8==0:
                print("DP_SENSITIVITY_PHYSICAL_PROGRESS",gid,metrics(rows,"turn")["T2"]["frozen_v43"],metrics(rows,"turn")["T2"]["model_only_DP"],round(time.monotonic()-t0,2),flush=True)
    finally:
        for s in backup:
            original_dp["seat_continuations"][s]["thresholds_by_london_stage"]=backup[s]
    changed=[r for r in rows if r["frozen_v43"]["keep_n"]!=r["alternative"]["keep_n"] or r["frozen_v43"]["hand"]!=r["alternative"]["hand"]]
    result={"schema":"dack_v43_model_only_DP_threshold_sensitivity_real_physical_N64_DEV",
       "status":"PASS","source_dp_163700_164723_model_only":True,
       "physical_gid_start":START,"physical_gid_end":START+N-1,
       "independent_outer_physical_deals":N,
       "frozen_v43_and_model_only_DP_same_candidate_model":True,
       "no_model_train":True,"no_promotion":True,"not_acceptance":True,
       "beam160_stateless_original_chance":True,"same_shuffles_and_seats":True,
       "orig_thresholds":backup,"model_only_v43_Qmax_thresholds":alt,
       "changed_final_hand_or_stage":len(changed),
       "mean_keep_original":sum(r["frozen_v43"]["keep_n"] for r in rows)/N,
       "mean_keep_model_only_DP":sum(r["alternative"]["keep_n"] for r in rows)/N,
       "paired":metrics(rows,"turn"),"elapsed_seconds":round(time.monotonic()-t0,2),"rows":rows}
    OUT.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("DACK_V43_PHYSICAL_DP_SENSITIVITY_PASS",json.dumps({
      "N":N,"changed_final_hand_or_stage":result["changed_final_hand_or_stage"],
      "mean_keep_original":result["mean_keep_original"],
      "mean_keep_model_only_DP":result["mean_keep_model_only_DP"],
      "paired":result["paired"],"seconds":result["elapsed_seconds"]},sort_keys=True),flush=True)

if __name__=="__main__":main()
