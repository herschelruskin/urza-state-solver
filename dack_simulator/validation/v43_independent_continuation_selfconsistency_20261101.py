#!/usr/bin/env python3
"""Read-only v43-v27 DP self-consistency comparison on fresh development 1637xx hands.

No threshold overrides, no physical acceptance outcome use, no new model.
Within each source gid, all eight hypothetical stages share the same outer
physical 99-slot source group; bootstrap samples gid groups, not stage rows.
"""
from __future__ import annotations
from collections import Counter,defaultdict
from pathlib import Path
import json,random,statistics,sys,time
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as v43
import dack_mulligan_teacher_features_v13_20261031 as f
from dack_simulator.validation.collect_teacher_london_v13 import finalists
ref=v43.ref
START=163700;GAMES=1024
BOOT=500

def thresholds(matrix):
    if not matrix:raise ValueError("need data")
    value=sum(x[7] for x in matrix)/len(matrix)
    cont={1:value}
    for kn in range(2,8):
        stage=8-kn
        value=sum(max(x[stage],value) for x in matrix)/len(matrix)
        cont[kn]=value
    return [cont[7],cont[6],cont[5],cont[4],cont[3],cont[2],cont[1],-1.]

def main():
    v43.audit()
    per_seat=defaultdict(list);runtime=time.monotonic()
    deck=ref.SLOT_VARIANTS["one_key_34"]
    for gid in range(START,START+GAMES):
        seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(seed)
        vals=[]
        for stage,(kn,order) in enumerate(zip(ref.sim.STAGES,orders)):
            seven=tuple(deck[s] for s in order[:7])
            unknown=tuple(deck[s] for s in order[7:])
            pool=Counter(unknown)
            cand=finalists(seven,kn,unknown)
            qmax=-1.
            for i,c in enumerate(cand):
                x=f.extract(seven,c["hand"],c["bottom"],pool,seat,kn,stage,c["struct_rank"],i)
                q=float(v43.v27.original.estimator.predict(v43.v27.original.MODEL,x))
                qmax=max(qmax,q)
            assert 0<=qmax<=1
            vals.append(qmax)
        per_seat[str(seat)].append(vals)
        if (gid-START+1)%128==0:
            print("V43_RECOMPUTE_CONTINUATION_PROGRESS",gid-START+1,round(time.monotonic()-runtime,2),flush=True)
    rng=random.Random(20261101)
    rows={}
    for seat in map(str,range(4)):
        a=per_seat[seat]
        assert len(a)>=150,(seat,len(a))
        old=[float(z) for z in v43.v27.original.DP["seat_continuations"][seat]["thresholds_by_london_stage"]]
        now=thresholds(a)
        bootstrap=[]
        for _ in range(BOOT):
            sample=[a[rng.randrange(len(a))] for __ in a]
            bootstrap.append(thresholds(sample))
        data=[]
        for stage in range(8):
            sorted_vals=sorted(boot[stage] for boot in bootstrap)
            data.append({
              "stage":stage,"keep_n":ref.sim.STAGES[stage],
              "frozen_v27_threshold":old[stage],"v43_model_self_consistent_threshold":now[stage],
              "change":now[stage]-old[stage],
              "bootstrap_group95":[sorted_vals[int(BOOT*.025)],sorted_vals[int(BOOT*.975)-1]],
              "predicted_keep_mean":statistics.mean(row[stage] for row in a)})
        rows[seat]={"outer_source_groups":len(a),"stage_values":data}
        print("V43_CONTINUATION_SEAT",seat,len(a),"old",old[:3],"v43",now[:3],flush=True)
    result={
      "schema":"dack_v43_independent_development_model_only_DP_self_consistency_v1",
      "status":"PASS","start_gid":START,"game_ids":[START,START+GAMES-1],
      "N_independent_outer_physical_deals":GAMES,
      "unique_source_groups_by_seat":{seat:len(v) for seat,v in per_seat.items()},
      "GID_stage_repeated_sample_dependency_respected":True,
      "bootstrap_outer_groups_per_seat":BOOT,
      "fixed_frozen_v27_Q2_model":True,"v43_candidate_max_before_keep":True,
      "no_threshold_or_policy_changes":True,
      "no_physical_outcome_labels":True,
      "not_real_keep_vs_mull_calibration":True,
      "not_acceptance_benchmark":True,
      "elapsed_seconds":round(time.monotonic()-runtime,3),
      "seats":rows}
    dest=ROOT/"benchmark_results/v43_independent_model_only_continuation_self_consistency_163700_N1024.json"
    dest.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("DACK_V43_FROZEN_Q2_CONTINUATION_RECOMPUTE_PASS",json.dumps({
      "N":GAMES,"seats":{seat:{"n":z["outer_source_groups"],
          "first_seven_old":z["stage_values"][0]["frozen_v27_threshold"],
          "first_seven_v43":z["stage_values"][0]["v43_model_self_consistent_threshold"],
          "second_seven_old":z["stage_values"][1]["frozen_v27_threshold"],
          "second_seven_v43":z["stage_values"][1]["v43_model_self_consistent_threshold"]}
          for seat,z in rows.items()}},sort_keys=True),flush=True)
if __name__=="__main__":main()
