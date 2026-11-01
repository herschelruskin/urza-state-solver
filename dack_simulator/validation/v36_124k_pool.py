#!/usr/bin/env python3
"""v36 independent 124k validation of ONE precommitted policy.

No refit. 256 independent random game IDs, each actual stage0,1,2,
12 truly shuffled unknown-92 beam160 game futures per stage.
Separately 4 seats×3 stages×64 blind full99 Qmull futures under
EXACT frozen v27 future keep and v33b bottom.
Hierarchical bootstrap resamples physical game groups, within-hand
futures and each seat-stage shared C lottery ONCE per iteration.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import gzip,glob,hashlib,json,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_mulligan_v36_keep_value as modelrun
import dack_mulligan_v36_features as feat

GAMES=256
STAGES=(0,1,2)
K_FUTURES=12
C_FUTURES=64

def hit(turn,t):
    return int(0<int(turn)<=t)

def load(K,C):
    modelpath=ROOT/"models/dack_v36_targeted_real_keep_EXPERIMENTAL.json"
    raw=modelpath.read_bytes()
    model=modelrun.read_model(json.loads(raw))
    sha=hashlib.sha256(raw).hexdigest()
    files=sorted(glob.glob(K));cfiles=sorted(glob.glob(C))
    assert len(files)==64 and len(cfiles)==12,("incomplete 124k",len(files),len(cfiles))
    groups={}
    for file in files:
        with gzip.open(file,"rt") as f:d=json.load(f)
        assert d["schema"]=="dack_v36_real_keep_value_labels_1"
        assert d["status"]=="PASS" and d["split"]=="holdout"
        assert d["futures_per_state"]==K_FUTURES and d["physical_groups"]==4
        assert d["manifest_sha256"]=="fresh_random_124k_unselected"
        assert d["strict_actual_gameplay_beam160"]
        assert d["v33b_bottom_sha256"]==model["source_frozen_v33b_sha256"]
        assert d["v36_feature_schema_sha256"]==feat.feature_hash()
        for r in d["rows"]:
            assert r["source_stratum"]=="unconditional_holdout" and r["selection_metadata"] is None
            assert 124000<=r["game_id"]<124256
            assert r["stage"] in STAGES and r["game_id"] in d["game_ids"]
            assert len(r["features"])==len(feat.NAMES)
            assert len(r["true_turns"])==K_FUTURES
            assert all(t in (0,1,2,3) for t in r["true_turns"])
            assert 0<=r["cumulative_T2"]<=r["cumulative_T3"]<=1
            new,dec=modelrun.choose(model,r["features"],r["seat"],r["stage"],
                                    r["frozen_v27_old_keep"],r["old_v27_Qkeep"])
            r["v36_new_keep"]=new;r["v36_prediction"]=dec
            groups.setdefault(r["game_id"],[]).append(r)
    assert sorted(groups)==list(range(124000,124256))
    assert all(sorted(r["stage"] for r in rr)==list(STAGES) for rr in groups.values())
    Cvals={}
    for file in cfiles:
        with gzip.open(file,"rt") as f:d=json.load(f)
        assert d["schema"]=="dack_v36_physical_shared_frozen_v33b_Qmull_1"
        assert d["status"]=="PASS" and d["split"]=="holdout"
        assert d["futures_per_cell"]==C_FUTURES and d["strict_gameplay_beam160"]
        assert d["all_99_shuffled_at_each_later_stage"] and d["rejected_seven_not_visible_in_shared_C"]
        assert d["source_frozen_v33b_sha256"]==model["source_frozen_v33b_sha256"]
        key=(d["seat"],d["stage"])
        assert key not in Cvals and key[0] in range(4) and key[1] in STAGES
        a=d["physical_turns"]
        assert len(a)==C_FUTURES and all(t in (0,1,2,3) for t in a)
        Cvals[key]=a
    assert len(Cvals)==12
    return model,sha,groups,Cvals

def detail(groups,C,t):
    out=[]
    cmean={k:sum(hit(z,t) for z in vals)/C_FUTURES for k,vals in C.items()}
    for gid,grp in groups.items():
        for r in grp:
            keep=sum(hit(z,t) for z in r["true_turns"])/K_FUTURES
            cv=cmean[(r["seat"],r["stage"])]
            old=int(r["frozen_v27_old_keep"]);new=int(r["v36_new_keep"])
            out.append({
              "game_id":gid,"seat":r["seat"],"stage":r["stage"],
              "changed":old!=new,
              "direction":("mull_to_keep" if new and not old else
                           "keep_to_mull" if old and not new else "none"),
              "gain":(new-old)*(keep-cv),
              "real_Qkeep":keep,"real_Qmull":cv,
              "v27_pred_Qkeep":r["old_v27_Qkeep"],
              "v36_pred_Qkeep":r["v36_prediction"].get("predicted_Qkeep_T2_median"),
              "old_v27_action":bool(old),"v36_action":bool(new),
            })
    return out

def stats(rows):
    if not rows:return None
    return {
       "stage_states":len(rows),
       "actions_changed":sum(r["changed"] for r in rows),
       "mull_to_keep":sum(r["direction"]=="mull_to_keep" for r in rows),
       "keep_to_mull":sum(r["direction"]=="keep_to_mull" for r in rows),
       "mean_conditional_action_value_gain_pp":100*sum(r["gain"] for r in rows)/len(rows),
       "positive_changed_states":sum(r["gain"]>0 for r in rows),
       "negative_changed_states":sum(r["gain"]<0 for r in rows),
       "tied_changed_states":sum(r["changed"] and r["gain"]==0 for r in rows),
    }

def bootstrap(groups,C,t,iters=5000):
    gids=sorted(groups);rng=random.Random(361240+t)
    out=[]
    for it in range(iters):
        cmeans={}
        for key,vals in C.items():
            cmeans[key]=sum(hit(vals[rng.randrange(C_FUTURES)],t)
                           for _ in range(C_FUTURES))/C_FUTURES
        gain=0.
        for _ in range(GAMES):
            group=groups[gids[rng.randrange(GAMES)]]
            for r in group:
                old=int(r["frozen_v27_old_keep"]);new=int(r["v36_new_keep"])
                if old==new:continue
                kept=r["true_turns"]
                kv=sum(hit(kept[rng.randrange(K_FUTURES)],t)
                       for j in range(K_FUTURES))/K_FUTURES
                gain+=(new-old)*(kv-cmeans[(r["seat"],r["stage"])])
        out.append(100*gain/(GAMES*len(STAGES)))
    out.sort()
    return [out[int(.025*iters)],out[int(.975*iters)-1]]

def run(K,C,out):
    assert hit(0,1)==0 and hit(1,1)==1 and hit(1,2)==1
    assert hit(2,1)==0 and hit(2,2)==1 and hit(3,2)==0 and hit(3,3)==1
    model,sha,groups,cont=load(K,C)
    report={
       "schema":"dack_v36_124k_strict_independent_conditional_action_validation_1",
       "status":"PASS","policy_approved":False,
       "frozen_candidate_sha256":sha,
       "frozen_training_physical_group_ids":[123000,123639],
       "validation_unconditional_game_ids":[124000,124255],
       "n_independent_outer_physical_groups":256,
       "n_early_stage_states":768,
       "true_K_rollouts":256*3*K_FUTURES,
       "true_full99_C_rollouts":12*C_FUTURES,
       "total_new_physical_beam160_rollouts":256*3*K_FUTURES+12*C_FUTURES,
       "shared_C_group_and_independent_K_bootstrap":True,
       "all_val_groups_unselected":True,
       "model_frozen_before_124k_outcomes":True,
       "stage0_free_seven_distinct_from_stage1":True,
       "no_v36_changed_future_Bellman_consistency_assumption":True,
       "not_prospective_end_to_end_full_game_winrate":True,
       "results":{}}
    for t in (1,2,3):
        a=detail(groups,cont,t)
        s=stats(a)
        s["independent_two_source_95ci_pp"]=bootstrap(groups,cont,t)
        s["by_stage"]={str(stage):stats([r for r in a if r["stage"]==stage])
                       for stage in STAGES}
        s["by_action_direction"]={
          way:stats([r for r in a if r["direction"]==way])
          for way in ("keep_to_mull","mull_to_keep")}
        report["results"][f"T{t}"]=s
    # Predeclared acceptance gate: a strictly positive lower T2 endpoint,
    # no persuasive T1 or T3 harm, and enough changed heldout states.
    t2=report["results"]["T2"];t1=report["results"]["T1"];t3=report["results"]["T3"]
    accept=(t2["actions_changed"]>=8 and
            t2["independent_two_source_95ci_pp"][0]>0 and
            t1["independent_two_source_95ci_pp"][1]>=0 and
            t3["independent_two_source_95ci_pp"][1]>=0)
    report["precommitted_gate_passed"]=bool(accept)
    report["next_step"]="125k_PROSPECTIVE_ALLOWED" if accept else "STOP_NO_125k_PROSPECTIVE"
    report["posthoc_parameter_tuning_forbidden"]=True
    p=Path(out);p.parent.mkdir(exist_ok=True,parents=True)
    p.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V36_124K_INDEPENDENT_GATE",json.dumps({
      "passed":accept,"T1":{k:t1[k] for k in
                 ("actions_changed","mean_conditional_action_value_gain_pp","independent_two_source_95ci_pp")},
      "T2":{k:t2[k] for k in
                 ("actions_changed","mean_conditional_action_value_gain_pp","independent_two_source_95ci_pp","by_stage")},
      "T3":{k:t3[k] for k in
                 ("actions_changed","mean_conditional_action_value_gain_pp","independent_two_source_95ci_pp")},
    },sort_keys=True),flush=True)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--K",default="collected/v36_holdout_K_*.json.gz")
    p.add_argument("--C",default="collected/v36_holdout_C_*.json.gz")
    p.add_argument("--out",default="benchmark_results/v36_124k_untouched_validation.json")
    a=p.parse_args();run(a.K,a.C,a.out)
