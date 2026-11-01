#!/usr/bin/env python3
"""v37 independent 127k EXACT sparse one-step population action-regret test.

Frozen physical candidate vs original v27 early KEEP/MULL actions;
same original frozen v33b bottom, v27+v33b MULL future.
Unchanged action contributes exactly zero, retains all 768 stage
states, 256 independent outer physical game groups. Changed hands
get 32 fresh hidden92 physical rollouts; shared C gets 128 fresh
full99 futures per necessary seat-stage cell. Bootstrap physical
outer game groups, within-hand KEEP futures, and C ONCE per cell.
No model or hyperparameter selection on holdout.
"""
from __future__ import annotations
import argparse,glob,gzip,hashlib,json,random
from collections import defaultdict,Counter
from pathlib import Path
N=256;STAGES=(0,1,2);K_N=32;C_N=128
CENSUS=Path("datasets/v37_127k_outcome_blind_census.json")
SCHEMA="dack_v37_127k_two_source_independent_real_action_regret_v1"

def y(turn,t):return int(0<int(turn)<=t)
def load(kpat,cpat):
    raw=CENSUS.read_bytes();data=json.loads(raw)
    assert data["schema"]=="dack_v37_127k_unseen_complete_outcome_blind_action_census_v1"
    assert data["status"]=="PASS" and data["no_127k_actual_game_outcomes_sampled"]
    assert data["random_stage_states"]==768 and data["random_physical_outer_groups"]==256
    states=data["complete_stage_rows"]
    assert len(states)==768
    assert sorted(set(r["game_id"] for r in states))==list(range(127200,127456))
    changes={(r["game_id"],r["stage"]):r for r in states if r["changed"]}
    assert len(changes)==data["changed_stage_decisions"]
    kfiles=sorted(glob.glob(kpat));cfiles=sorted(glob.glob(cpat))
    assert len(kfiles)==64 and len(cfiles)==12,("missing full fixed sparse shards",len(kfiles),len(cfiles))
    keep={}
    for path in kfiles:
        with gzip.open(path,"rt") as f:d=json.load(f)
        assert d["schema"]=="dack_v37_127k_true_changed_action_KEEP_only_v1"
        assert d["status"]=="PASS" and d["strict_actual_gameplay_beam160"]
        assert d["complete_outcome_blind_action_census_sha256"]==hashlib.sha256(raw).hexdigest()
        assert d["model_sha256"]==data["model_sha256"]
        assert d["source_v33b_sha256"]==data["source_v33b_sha256"]
        assert d["keep_futures_per_changed_state"]==K_N
        for r in d["rows"]:
            key=(r["game_id"],r["stage"])
            assert key in changes and key not in keep
            assert 127200+4*d["shard"]<=r["game_id"]<127204+4*d["shard"]
            assert changes[key]["new_keep"]==r["new_keep"]
            assert changes[key]["old_keep"]==r["old_keep"]
            a=r["physical_KEEP_turns"]
            assert len(a)==K_N and all(x in (0,1,2,3) for x in a)
            keep[key]=a
    assert set(keep)==set(changes)
    C={}
    required=set((r["seat"],r["stage"]) for r in changes.values())
    for path in cfiles:
        with gzip.open(path,"rt") as f:d=json.load(f)
        assert d["schema"]=="dack_v37_127k_true_shared_frozen_QMULL_v1"
        assert d["status"]=="PASS" and d["strict_actual_beam160"]
        assert d["source_v33b_sha256"]==data["source_v33b_sha256"]
        assert d["census_sha256"]==hashlib.sha256(raw).hexdigest()
        cell=(d["seat"],d["stage"]);assert cell not in C
        assert d["required_by_changed_action"]==(cell in required)
        a=d["turns"];assert len(a)==(C_N if cell in required else 0)
        assert all(x in (0,1,2,3) for x in a)
        C[cell]=a
    assert set(C)==set((a,b) for a in range(4) for b in STAGES)
    return data,states,changes,keep,C,required

def metric(states,keep,C,t):
    means={cell:sum(y(x,t) for x in vals)/len(vals)
           for cell,vals in C.items() if vals}
    results=[]
    for row in states:
        old=int(row["old_keep"]);new=int(row["new_keep"])
        sg=new-old
        if sg:
            vals=keep[(row["game_id"],row["stage"])]
            k=sum(y(x,t) for x in vals)/K_N
            delta=sg*(k-means[(row["seat"],row["stage"])])
        else:delta=0.
        results.append({
          "game_id":row["game_id"],"stage":row["stage"],
          "sign":sg,"gain":delta,
        })
    return results

def stat(rows):
    return {
      "n_population_stage_states":len(rows),
      "changed_actions":sum(bool(r["sign"]) for r in rows),
      "mull_to_keep":sum(r["sign"]==1 for r in rows),
      "keep_to_mull":sum(r["sign"]==-1 for r in rows),
      "mean_population_action_value_gain_pp":100*sum(r["gain"] for r in rows)/len(rows),
      "positive_changed":sum(r["gain"]>0 for r in rows),
      "negative_changed":sum(r["gain"]<0 for r in rows)
    }

def bootstrap(states,keep,C,t,reps=4000):
    rng=random.Random(371270+t)
    bygid=defaultdict(list)
    for row in states:bygid[row["game_id"]].append(row)
    gids=list(range(127200,127456))
    assert all(len(bygid[gid])==3 for gid in gids)
    out=[]
    for _ in range(reps):
        cm={}
        for cell,arr in C.items():
            if arr:
                cm[cell]=sum(y(arr[rng.randrange(C_N)],t) for j in range(C_N))/C_N
        total=0.
        for j in range(N):
            gid=gids[rng.randrange(N)]
            for r in bygid[gid]:
                sign=int(r["new_keep"])-int(r["old_keep"])
                if not sign:continue
                vals=keep[(gid,r["stage"])]
                km=sum(y(vals[rng.randrange(K_N)],t) for _ in range(K_N))/K_N
                total+=sign*(km-cm[(r["seat"],r["stage"])])
        out.append(100*total/(N*3))
    out.sort()
    return [out[int(.025*reps)],out[int(.975*reps)-1]]

def run(K,C,out):
    assert y(0,1)==0 and y(1,1)==1 and y(1,2)==1 and y(2,1)==0 and y(2,2)==1 and y(3,2)==0 and y(3,3)==1
    census,states,changes,keep,cont,required=load(K,C)
    nchanged=len(changes)
    report={
      "schema":SCHEMA,"status":"PASS","policy_approved":False,
      "model_sha256":census["model_sha256"],
      "holdout_physical_group_ids":[127200,127455],
      "independent_physical_outer_groups":N,
      "actual_stage_states_in_population":768,
      "changed_stage_decisions":nchanged,
      "changed_reached_actual_London_games":census["changed_reached_final_physical_games"],
      "unchanged_states_exact_zero":768-nchanged,
      "futures_PER_changed_KEEP":K_N,
      "futures_per_required_FULL99_shared_C":C_N,
      "required_shared_seat_stage_cells":len(required),
      "fresh_actual_beam160_rollouts":nchanged*K_N+len(required)*C_N,
      "correct_separate_K_C_lottery_bootstrap":True,
      "no_outcome_based_policy_or_label_selection":True,
      "no_new_future_policy_Bellman_consistency_claim":True,
      "no_full_game_winrate_claim":True,
      "turns":{}
    }
    for t in (1,2,3):
        details=metric(states,keep,cont,t)
        z=stat(details)
        z["hierarchical_two_source_95ci_pp"]=bootstrap(states,keep,cont,t)
        z["by_stage"]={str(s):stat([r for r in details if r["stage"]==s])
                       for s in STAGES}
        z["on_changed_states_only_descriptive"]=stat([r for r in details if r["sign"]])
        report["turns"][f"T{t}"]=z
    a=report["turns"]["T1"];b=report["turns"]["T2"];c=report["turns"]["T3"]
    report["precommitted_coverage_gate_met"]=bool(census["coverage_prerequisite_satisfied"])
    passgate=(report["precommitted_coverage_gate_met"] and
              b["hierarchical_two_source_95ci_pp"][0]>0 and
              a["hierarchical_two_source_95ci_pp"][1]>=0 and
              c["hierarchical_two_source_95ci_pp"][1]>=0)
    report["precommitted_full_gate_passed"]=bool(passgate)
    report["next_step"]="128k_FULL_GAME_PROSPECTIVE_ALLOWED" if passgate else "STOP_NO_PROSPECTIVE_128k"
    report["posthoc_holdout_tuning_forbidden"]=True
    path=Path(out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V37_NEW127K_GROUPED_REGRET_RESULT",json.dumps({
      "full_gate_passed":passgate,"coverage":report["precommitted_coverage_gate_met"],
      "changed_stages":nchanged,
      "reached_games":report["changed_reached_actual_London_games"],
      "beam160_rollouts":report["fresh_actual_beam160_rollouts"],
      "T2_pp":b["mean_population_action_value_gain_pp"],
      "T2_95CI":b["hierarchical_two_source_95ci_pp"],
      "T3_pp":c["mean_population_action_value_gain_pp"],
      "T3_95CI":c["hierarchical_two_source_95ci_pp"]},sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--K",default="collected/v37_127k_K_*.json.gz")
    p.add_argument("--C",default="collected/v37_127k_C_*.json.gz")
    p.add_argument("--out",default="benchmark_results/v37_127k_independent_direct_regret.json")
    a=p.parse_args();run(a.K,a.C,a.out)
