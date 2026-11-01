#!/usr/bin/env python3
"""v39 strict independent 131k physical T2-regret validation with shared C.

All random 1024 physical game IDs ×3 actual early stages remain
in population denominator, including exact-zero contribution when
both policies choose the same action. Simulate ONLY changed K
unknown92 physical futures, shared C seat/stage from full99 later
London 128-future physical replays. 4000 grouped bootstraps:
512/1024 group identity kept, K outcomes within-hand resampled,
all relevant shared C cells sampled ONCE each per replication.
"""
from __future__ import annotations
import argparse,gzip,glob,hashlib,json,random
from collections import Counter,defaultdict
from pathlib import Path

LO=131000;HI=132023
GROUPS=1024;STAGES=(0,1,2)
FUTURES_K=32;FUTURES_C=128
CENSUS=Path("datasets/v39_131k_frozen_outcome_blind_census.json")
SCHEMA="dack_v39_131k_N1024_real_action_regret_two_source_v1"

def hit(turn,t):
    return int(0<int(turn)<=t)

def load(K,C):
    raw=CENSUS.read_bytes();c=json.loads(raw)
    assert c["schema"]=="dack_v39_131k_new_random_1024_outcome_blind_census_v1"
    assert c["status"]=="PASS" and c["random_stage_state_denominator"]==3072
    assert c["physical_random_outer_groups"]==GROUPS
    assert c["no_full_game_or_counterfactual_rollouts_at_selection"]
    assert c["actual_action_changes"]>=24 and c["changed_actual_London_path_games"]>=12
    rows=c["all_early_stage_decisions"]
    assert len(rows)==3072 and sorted(set(r["game_id"] for r in rows))==list(range(LO,HI+1))
    assert len(set((r["game_id"],r["stage"]) for r in rows))==3072
    old={ (r["game_id"],r["stage"]):r for r in rows if r["changed"] }
    assert len(old)==c["actual_action_changes"]
    kfiles=sorted(glob.glob(K));cfiles=sorted(glob.glob(C))
    assert len(kfiles)==16 and len(cfiles)==12
    seenK={}
    for file in kfiles:
        with gzip.open(file,"rt") as f:d=json.load(f)
        assert d["schema"]=="dack_v39_131k_changed_only_true_physical_KEEP_v1"
        assert d["status"]=="PASS" and d["gameplay_beam"]==160
        assert d["n_futures_per_changed_state"]==FUTURES_K
        assert d["source_census_sha256"]==hashlib.sha256(raw).hexdigest()
        assert d["model_sha256"]==c["frozen_v37_direct_regret_model_sha256"]
        assert d["source_v33b_bottom_sha256"]==c["frozen_v33b_bottom_sha256"]
        for r in d["physical_result_rows"]:
            key=(r["game_id"],r["stage"])
            assert key in old and key not in seenK
            assert (r["game_id"]-LO)%16==d["shard"]
            assert r["old_keep"]==old[key]["old_keep"] and r["new_keep"]==old[key]["new_keep"]
            arr=r["true_KEEP_win_turns"]
            assert len(arr)==FUTURES_K and all(t in (0,1,2,3) for t in arr)
            assert 0<=r["T1"]<=r["T2"]<=r["T3"]<=1
            seenK[key]=arr
    assert set(seenK)==set(old)
    needed=set((r["seat"],r["stage"]) for r in old.values())
    shared={}
    for file in cfiles:
        with gzip.open(file,"rt") as f:d=json.load(f)
        assert d["schema"]=="dack_v39_131k_independent_shared_true_MULL_v1"
        assert d["status"]=="PASS" and d["gameplay_beam"]==160
        assert d["source_census_sha256"]==hashlib.sha256(raw).hexdigest()
        assert d["reject_seven_restored_complete99_each_future"]
        assert d["frozen_bottom_sha256"]==c["frozen_v33b_bottom_sha256"]
        key=(d["seat"],d["stage"])
        assert key not in shared and key[0] in range(4) and key[1] in STAGES
        vals=d["physical_win_turns"]
        assert len(vals)==(FUTURES_C if key in needed else 0)
        assert all(v in (0,1,2,3) for v in vals)
        shared[key]=vals
    assert len(shared)==12 and set(key for key,vals in shared.items() if vals)==needed
    return c,rows,old,seenK,shared

def comparisons(rows,keep,C,t):
    cm={cell:sum(hit(z,t) for z in vals)/len(vals)
        for cell,vals in C.items() if vals}
    out=[]
    for r in rows:
        k=(r["game_id"],r["stage"])
        sign=int(r["new_keep"])-int(r["old_keep"])
        gain=sign*(sum(hit(z,t) for z in keep[k])/FUTURES_K-cm[(r["seat"],r["stage"])]) if sign else 0.
        out.append({"gid":r["game_id"],"stage":r["stage"],"seat":r["seat"],
          "changed":bool(sign),"direction":("mull_to_keep" if sign==1 else
            "keep_to_mull" if sign==-1 else "unchanged"),
          "gain":gain})
    return out

def summarize(rows):
    n=len(rows)
    return {"n_stage_states":n,
       "action_changes":sum(r["changed"] for r in rows),
       "keep_to_mull":sum(r["direction"]=="keep_to_mull" for r in rows),
       "mull_to_keep":sum(r["direction"]=="mull_to_keep" for r in rows),
       "mean_population_action_gain_pp":100*sum(r["gain"] for r in rows)/n,
       "changed_beneficial":sum(r["gain"]>0 for r in rows),
       "changed_harmful":sum(r["gain"]<0 for r in rows),
       "changed_tied":sum(r["changed"] and r["gain"]==0 for r in rows)}

def boot(rows,keep,C,t,B=4000):
    rng=random.Random(390131+t)
    pergroup=defaultdict(list)
    for r in rows:
        if r["changed"]:pergroup[r["game_id"]].append(r)
    gidlist=list(range(LO,HI+1))
    bvals=[]
    for _ in range(B):
        shared={}
        for key,vals in C.items():
            if vals:
                shared[key]=sum(hit(vals[rng.randrange(FUTURES_C)],t)
                                for _ in range(FUTURES_C))/FUTURES_C
        tot=0.
        for _ in range(GROUPS):
            gid=gidlist[rng.randrange(GROUPS)]
            for r in pergroup.get(gid,()):
                state=(gid,r["stage"]);a=keep[state]
                kv=sum(hit(a[rng.randrange(FUTURES_K)],t)
                       for _ in range(FUTURES_K))/FUTURES_K
                sign=1 if r["direction"]=="mull_to_keep" else -1
                tot+=sign*(kv-shared[(r["seat"],r["stage"])])
        bvals.append(100*tot/(GROUPS*3))
    bvals.sort()
    return [bvals[int(.025*B)],bvals[int(.975*B)-1]]

def run(K,C,out):
    for z in range(4):
        assert hit(z,1)<=hit(z,2)<=hit(z,3)
    c,raw,changed,keep,shared=load(K,C)
    outdoc={
      "schema":SCHEMA,"status":"PASS","policy_approved":False,
      "random_game_ids":[LO,HI],
      "n_outer_physical_groups":GROUPS,"n_early_stage_states":3072,
      "frozen_130k_future_games_unseen":True,
      "n_changed_stage_states":len(changed),
      "n_changed_actual_London_games":c["changed_actual_London_path_games"],
      "actual_K_beam160_rollouts":len(changed)*FUTURES_K,
      "actual_C_beam160_rollouts":sum(len(x) for x in shared.values()),
      "zero_regret_unchanged_stage_states":3072-len(changed),
      "model_sha256":c["frozen_v37_direct_regret_model_sha256"],
      "census_sha256":hashlib.sha256(CENSUS.read_bytes()).hexdigest(),
      "all_3072_original_population_denominator_included":True,
      "physical_group_and_shared_C_lottery_bootstrap":True,
      "one_step_same_frozen_future_not_policy_Bellman":True,
      "results":{}}
    for t in (1,2,3):
        r=comparisons(raw,keep,shared,t)
        z=summarize(r)
        z["two_source_group_bootstrap_95ci_pp"]=boot(r,keep,shared,t)
        z["by_stage"]={str(s):summarize([v for v in r if v["stage"]==s]) for s in STAGES}
        outdoc["results"]["T"+str(t)]=z
    a=outdoc["results"]["T1"];b=outdoc["results"]["T2"];d=outdoc["results"]["T3"]
    gate=(len(changed)>=24 and c["changed_actual_London_path_games"]>=12
          and b["two_source_group_bootstrap_95ci_pp"][0]>0
          and a["two_source_group_bootstrap_95ci_pp"][1]>=0
          and d["mean_population_action_gain_pp"]>=-1.5)
    outdoc["predeclared_gate_passed"]=bool(gate)
    outdoc["prospective_133k"]="ALLOWED" if gate else "STOP"
    outdoc["posthoc_retuning_on_131k_prohibited"]=True
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(outdoc,sort_keys=True,indent=2)+"\n")
    print("DACK_V39_NEW131K_INDEPENDENT_TWO_SOURCE_T2_REGRET_GATE",json.dumps({
       "gate":gate,"K":outdoc["actual_K_beam160_rollouts"],
       "C":outdoc["actual_C_beam160_rollouts"],"changed":len(changed),
       "reached":c["changed_actual_London_path_games"],
       "T1":{k:a[k] for k in ("mean_population_action_gain_pp","two_source_group_bootstrap_95ci_pp")},
       "T2":{k:b[k] for k in ("mean_population_action_gain_pp","two_source_group_bootstrap_95ci_pp")},
       "T3":{k:d[k] for k in ("mean_population_action_gain_pp","two_source_group_bootstrap_95ci_pp")}
     },sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--K",default="collected/v39_K_*.json.gz")
    p.add_argument("--C",default="collected/v39_C_*.json.gz")
    p.add_argument("--out",default="benchmark_results/v39_131k_independent_action_regret.json")
    a=p.parse_args();run(a.K,a.C,a.out)
