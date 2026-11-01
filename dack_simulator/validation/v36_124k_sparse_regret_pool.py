#!/usr/bin/env python3
"""v36 124k exactly sparse one-step conditional regret, full population.

Every of the 256 independent physical game IDs has 3 early-stage
frozen action comparisons. Only counterfactuals at nonidentical
actions need outcome sampling; identical actions have EXACT
per-state regret zero, not an imputed or approximated outcome.
Shared C per seat-stage is sampled from 64 fresh physically
independent full99 continuation trials (frozen v27+v33b future).
Hierarchical bootstraps resample outer game IDs, changed-hand
physical futures and each shared C lottery once per iteration.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import gzip,glob,hashlib,json,random
from pathlib import Path

LO=124000;HI=124255
GAMES=256
STAGES=(0,1,2)
FUTURES_K=32
FUTURES_C=64
CENSUS=Path("datasets/v36_124k_outcome_blind_action_census.json")

def hit(turn,t):
    return int(0<int(turn)<=t)

def load(K,C):
    c=json.loads(CENSUS.read_text())
    assert c["schema"]=="dack_v36_124k_frozen_actions_outcome_blind_census_v1"
    assert c["status"]=="PASS" and c["stage_states"]==768
    assert c["complete_independent_random_outer_groups"]==GAMES
    assert c["computed_before_any_124k_gameplay_outcomes"]
    assert c["unchanged_one_step_action_regret_is_EXACT_ZERO"]
    allstates=c["all_decisions"]
    ids=sorted(set(r["game_id"] for r in allstates))
    assert ids==list(range(LO,HI+1))
    assert len(set((r["game_id"],r["stage"]) for r in allstates))==GAMES*len(STAGES)
    assert all(sorted(r["stage"] for r in allstates if r["game_id"]==gid)==list(STAGES) for gid in ids)
    changed={ (r["game_id"],r["stage"]):r for r in allstates if r["keep_changed"] }
    assert len(changed)==c["changed_actions"]
    assert all(r["old_keep"]!=r["new_keep"] for r in changed.values())
    Kfiles=sorted(glob.glob(K));Cfiles=sorted(glob.glob(C))
    required_cells=set((r["seat"],r["stage"]) for r in changed.values())
    assert len(Kfiles)==16 and len(Cfiles)==len(required_cells),(
           "missing sparse physical replay/required continuation cells",
           len(Kfiles),len(Cfiles),len(required_cells))
    real={}
    for path in Kfiles:
        with gzip.open(path,"rt") as f:d=json.load(f)
        assert d["schema"]=="dack_v36_124k_changed_only_physical_keep_outcomes"
        assert d["status"]=="PASS" and d["actual_gameplay_beam160"]
        assert d["total_unconditional_action_stage_states"]==768
        assert d["fresh_physical_futures_per_changed_state"]==FUTURES_K
        assert d["no_gameplay_for_exact_zero_action_regret"]
        assert d["frozen_action_census_sha256"]==hashlib.sha256(CENSUS.read_bytes()).hexdigest()
        assert d["model_sha256"]==c["source_candidate_model_sha256"]
        assert d["v33b_bottom_sha256"]==c["source_frozen_v33b_model_sha256"]
        for r in d["rows"]:
            key=(r["game_id"],r["stage"])
            assert key in changed and key not in real
            assert r["game_id"]%16==d["shard"]
            assert r["old_keep"]==changed[key]["old_keep"]
            assert r["new_keep"]==changed[key]["new_keep"]
            arr=r["true_KEEP_turns"]
            assert len(arr)==FUTURES_K and all(t in (0,1,2,3) for t in arr)
            assert 0<=r["real_KEEP_by_T1"]<=r["real_KEEP_by_T2"]<=r["real_KEEP_by_T3"]<=1
            real[key]=arr
    assert set(real)==set(changed),("must label exactly every changed action",len(real),len(changed))
    shared={}
    for path in Cfiles:
        with gzip.open(path,"rt") as f:d=json.load(f)
        assert d["schema"]=="dack_v36_physical_shared_frozen_v33b_Qmull_1"
        assert d["status"]=="PASS" and d["split"]=="holdout"
        assert d["futures_per_cell"]==FUTURES_C and d["strict_gameplay_beam160"]
        assert d["all_99_shuffled_at_each_later_stage"]
        assert d["source_frozen_v33b_sha256"]==c["source_frozen_v33b_model_sha256"]
        key=(d["seat"],d["stage"])
        assert key not in shared and key in required_cells
        turns=d["physical_turns"]
        assert len(turns)==FUTURES_C and all(t in (0,1,2,3) for t in turns)
        shared[key]=turns
    assert set(shared)==required_cells
    return c,allstates,changed,real,shared

def estimate(allstates,changed,real,shared,t):
    C={key:sum(hit(z,t) for z in arr)/FUTURES_C for key,arr in shared.items()}
    rows=[]
    for r in allstates:
        key=(r["game_id"],r["stage"])
        change=int(r["new_keep"])-int(r["old_keep"])
        if change==0:
            gain=0.
        else:
            K=real[key]
            kmean=sum(hit(z,t) for z in K)/FUTURES_K
            gain=change*(kmean-C[(r["seat"],r["stage"])])
        rows.append({"game_id":r["game_id"],"seat":r["seat"],
                     "stage":r["stage"],"changed":bool(change),
                     "direction":("mull_to_keep" if change==1 else
                                  "keep_to_mull" if change==-1 else "same"),
                     "gain":gain})
    assert len(rows)==768
    return rows

def stat(rows):
    if not rows:return None
    return {"n_stage_states":len(rows),
      "changed_actions":sum(r["changed"] for r in rows),
      "mull_to_keep":sum(r["direction"]=="mull_to_keep" for r in rows),
      "keep_to_mull":sum(r["direction"]=="keep_to_mull" for r in rows),
      "mean_regret_improvement_pp":100*sum(r["gain"] for r in rows)/len(rows),
      "observed_positive_changed_states":sum(r["gain"]>0 for r in rows),
      "observed_negative_changed_states":sum(r["gain"]<0 for r in rows),
      "observed_exactly_tied_changed_states":sum(r["changed"] and r["gain"]==0 for r in rows)}

def bootstrap(allstates,changed,real,shared,t,n=5000):
    rng=random.Random(361240+t)
    bygid=defaultdict(list)
    for r in allstates:bygid[r["game_id"]].append(r)
    gids=list(range(LO,HI+1))
    assert all(len(bygid[gid])==3 for gid in gids)
    boot=[]
    for rep in range(n):
        C={}
        for cell,arr in shared.items():
            C[cell]=sum(hit(arr[rng.randrange(FUTURES_C)],t)
                        for _ in range(FUTURES_C))/FUTURES_C
        total=0.
        for _ in range(GAMES):
            gid=gids[rng.randrange(GAMES)]
            for state in bygid[gid]:
                k=(gid,state["stage"])
                sign=int(state["new_keep"])-int(state["old_keep"])
                if not sign:continue
                arr=real[k]
                keep=sum(hit(arr[rng.randrange(FUTURES_K)],t)
                         for _ in range(FUTURES_K))/FUTURES_K
                total+=sign*(keep-C[(state["seat"],state["stage"])])
        boot.append(100*total/(GAMES*len(STAGES)))
    boot.sort()
    return [boot[int(.025*n)],boot[int(.975*n)-1]]

def main(K,C,out):
    assert hit(0,1)==0 and hit(1,1)==1 and hit(1,2)==1 and hit(1,3)==1
    assert hit(2,1)==0 and hit(2,2)==1 and hit(3,2)==0 and hit(3,3)==1
    census,allstates,changed,real,shared=load(K,C)
    report={
      "schema":"dack_v36_sparse_exact_zero_regret_124k_random_population",
      "status":"PASS","policy_approved":False,
      "validation_outer_game_ids":[LO,HI],
      "population_random_outer_physical_groups":GAMES,
      "population_early_stage_states":768,
      "unchanged_actions_exact_zero_contribution":768-len(changed),
      "changed_actions_true_outcomes_simulated":len(changed),
      "required_seat_stage_C_cells_only":len(shared),
      "new_KEEP_futures_per_changed_state":FUTURES_K,
      "new_actual_KEEP_beam160_outcomes":len(changed)*FUTURES_K,
      "new_full99_C_beam160_outcomes":len(shared)*FUTURES_C,
      "new_total_physical_beam160_outcomes":len(changed)*FUTURES_K+len(shared)*FUTURES_C,
      "physical_futures_saved_vs_all_768_12_each_and_full_12_C":768*12+12*FUTURES_C-len(changed)*FUTURES_K-len(shared)*FUTURES_C,
      "original_768_population_denominator_retained":True,
      "no_outcome_dependence_in_counterfactual_sampling_selection":True,
      "true_ZERO_if_same_action_is_exact_identity":True,
      "training_model_sha256":census["source_candidate_model_sha256"],
      "frozen_v33b_bottom_sha256":census["source_frozen_v33b_model_sha256"],
      "frozen_124k_action_census_sha256":hashlib.sha256(CENSUS.read_bytes()).hexdigest(),
      "two_source_outer_group_and_C_bootstrap":True,
      "changed_policy_Bellman_consistency_not_claimed":True,
      "not_full_game_winrate":True,"turns":{}}
    for t in (1,2,3):
        rr=estimate(allstates,changed,real,shared,t)
        st=stat(rr)
        st["two_source_95ci_pp"]=bootstrap(allstates,changed,real,shared,t)
        st["by_stage"]={str(stage):stat([r for r in rr if r["stage"]==stage])
                        for stage in STAGES}
        st["by_action_direction"]={
          way:stat([r for r in rr if r["direction"]==way])
          for way in ("mull_to_keep","keep_to_mull")}
        report["turns"][f"T{t}"]=st
    t1=report["turns"]["T1"];t2=report["turns"]["T2"];t3=report["turns"]["T3"]
    accept=(len(changed)>=8 and t2["two_source_95ci_pp"][0]>0 and
            t1["two_source_95ci_pp"][1]>=0 and
            t3["two_source_95ci_pp"][1]>=0)
    report["precommitted_gate_passed"]=bool(accept)
    report["next_step"]="125k_PROSPECTIVE_ALLOWED" if accept else "STOP_NO_125k_PROSPECTIVE"
    report["no_posthoc_tuning_on_124k"]=True
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V36_124K_SPARSE_EXACT_REGRET_HOLDOUT_GATE_PASS",json.dumps({
        "accept":accept,"changed":len(changed),
        "total_beam_calls":report["new_total_physical_beam160_outcomes"],
        "T1":{k:t1[k] for k in ("mean_regret_improvement_pp","two_source_95ci_pp")},
        "T2":{k:t2[k] for k in ("mean_regret_improvement_pp","two_source_95ci_pp","by_stage")},
        "T3":{k:t3[k] for k in ("mean_regret_improvement_pp","two_source_95ci_pp")}},sort_keys=True),flush=True)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--K",default="collected/v36_changed_K_*.json.gz")
    p.add_argument("--C",default="collected/v36_C_*.json.gz")
    p.add_argument("--out",default="benchmark_results/v36_124k_untouched_validation.json")
    a=p.parse_args();main(a.K,a.C,a.out)
