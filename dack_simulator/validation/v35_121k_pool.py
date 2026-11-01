#!/usr/bin/env python3
"""v35 fully held-out conditional regret screening with two-source bootstrap.

No parameter selection; heldout 121k outcomes cannot feed back into model.
For every possible stage before terminal, the one-step changed action
has empirical value (new_keep-old_keep)*(Qkeep_real-Qmull_real).
Qmull cell is shared across hands, hence MUST resample each seat-stage
lottery ONCE per bootstrap draw, not independently for each hand.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import gzip,glob,json,math,random
from pathlib import Path
GAMES=128
STAGES=tuple(range(7))
FUTURES_K=8
FUTURES_C=64

def passby(turn,t):
    return int(0<int(turn)<=t)

def load(kglob,cglob):
    kk=sorted(glob.glob(kglob));cc=sorted(glob.glob(cglob))
    if len(kk)!=32 or len(cc)!=28:
        raise ValueError("missing physical 121k shards: %d K, %d C"%(len(kk),len(cc)))
    groups={};modelsha=None;v33bsha=None
    for f in kk:
        with gzip.open(f,"rt") as h:d=json.load(h)
        assert d["schema"]=="dack_v35_121k_fresh_stages_Qkeep"
        assert d["status"]=="PASS" and d["actual_gameplay_beam"]==160
        assert d["futures_per_stage"]==FUTURES_K and d["physical_groups"]==4
        assert d["no_future_peeking"] and d["no_refitting"] and not d["policy_approved"]
        if modelsha is None:modelsha=d["model_sha256"];v33bsha=d["fixed_v33b_sha256"]
        assert modelsha==d["model_sha256"] and v33bsha==d["fixed_v33b_sha256"]
        for row in d["rows"]:
            gid=row["game_id"]
            assert 121000<=gid<121128 and row["stage"] in STAGES
            assert len(row["futures"])==FUTURES_K
            assert all(turn in range(4) for turn in row["futures"])
            assert row["model_prediction"]["new_keep"]==row["new_v35_keep"]
            assert row["model_prediction"]["old_keep"]==row["original_v27_keep"]
            assert row["new_v35_keep"]==row["original_v27_keep"] or row["stage"]<=2
            groups.setdefault(gid,[]).append(row)
    assert sorted(groups)==list(range(121000,121128))
    assert all(sorted(r["stage"] for r in v)==list(STAGES) for v in groups.values())
    C={}
    for f in cc:
        with gzip.open(f,"rt") as h:d=json.load(h)
        assert d["schema"]=="dack_v35_fresh121k_shared_Qmull"
        assert d["status"]=="PASS" and d["strict_gameplay_beam"]==160
        assert d["futures_per_cell"]==FUTURES_C and not d["policy_approved"]
        assert d["frozen_downstream_v27_keep_v33b_bottom"]
        assert d["complete_99_cards_reshuffled_each_future_stage"]
        assert d["current_seven_not_used"]
        assert d["model_v33b_sha256"]==v33bsha
        key=(d["seat"],d["stage"])
        assert key not in C and key[0] in range(4) and key[1] in STAGES
        vals=d["outcome_turns"]
        assert len(vals)==FUTURES_C and all(z in range(4) for z in vals)
        C[key]=vals
    assert len(C)==28
    return groups,C,modelsha,v33bsha

def empirical(groups,C,t):
    cm={k:sum(passby(v,t) for v in arr)/len(arr) for k,arr in C.items()}
    result=[]
    for gid,rows in groups.items():
        for r in rows:
            old=int(r["original_v27_keep"]);new=int(r["new_v35_keep"])
            keep=sum(passby(turn,t) for turn in r["futures"])/FUTURES_K
            mull=cm[(r["seat"],r["stage"])]
            diff=(new-old)*(keep-mull)
            result.append({
              "game_id":gid,"stage":r["stage"],"seat":r["seat"],
              "change":new!=old,"change_type":("mull_to_keep" if new and not old else
                 "keep_to_mull" if old and not new else "none"),
              "gain":diff,"keep_real":keep,"mull_real":mull,
              "old_margin":r["old_Qkeep"]-r["old_C"],
              "predicted_margin":r["model_prediction"]["T2_median"],
            })
    return result

def metrics(results):
    n=len(results)
    if not n:return None
    return {
      "n_physical_stage_states":n,
      "changed_actions":sum(q["change"] for q in results),
      "mull_to_keep":sum(q["change_type"]=="mull_to_keep" for q in results),
      "keep_to_mull":sum(q["change_type"]=="keep_to_mull" for q in results),
      "T2_or_T3_expected_conditional_gain_pp":100*sum(q["gain"] for q in results)/n,
      "positive_group_changes":sum(q["gain"]>0 for q in results),
      "negative_group_changes":sum(q["gain"]<0 for q in results),
      "zero_group_changes":sum(q["gain"]==0 for q in results),
    }

def bootstrap(groups,C,t,n=3500):
    rng=random.Random(350121+t)
    gids=sorted(groups)
    # Group physically independent outer IDs and physical lottery per
    # shared continuation. Within-hand 8 independent hidden futures
    # resampled only for changed actions.
    out=[]
    for it in range(n):
        cm={}
        for cell,arr in C.items():
            cm[cell]=sum(passby(arr[rng.randrange(FUTURES_C)],t)
                         for _ in range(FUTURES_C))/FUTURES_C
        total=0.
        for i in range(GAMES):
            gid=gids[rng.randrange(GAMES)]
            for r in groups[gid]:
                diff=int(r["new_v35_keep"])-int(r["original_v27_keep"])
                if not diff:continue
                arr=r["futures"]
                keep=sum(passby(arr[rng.randrange(FUTURES_K)],t)
                         for _ in range(FUTURES_K))/FUTURES_K
                total+=diff*(keep-cm[(r["seat"],r["stage"])])
        out.append(100*total/(GAMES*len(STAGES)))
    out.sort()
    return [out[int(.025*n)],out[int(.975*n)-1]]

def run(K,C,out):
    groups,c,modelsha,v33bsha=load(K,C)
    report={
      "schema":"dack_v35_121k_independent_conditional_action_regret_screen",
      "status":"PASS","policy_approved":False,
      "new_physical_game_ids":[121000,121127],
      "independent_outer_games":GAMES,
      "conditional_stage_states":GAMES*len(STAGES),
      "K_futures_per_stage":FUTURES_K,
      "C_futures_per_seat_stage":FUTURES_C,
      "total_new_strict_beam160_rollouts":GAMES*len(STAGES)*FUTURES_K+28*FUTURES_C,
      "candidate_model_sha256":modelsha,"frozen_bottom_sha256":v33bsha,
      "prediction_frozen_before_outcome_simulation":True,
      "no_validation_tuning":True,
      "one_step_frozen_future_policy_not_new_policy_bellman":True,
      "T2_primary":True,"T1_T3_safeguards":True,
      "by_turn":{}}
    for t in (1,2,3):
        rows=empirical(groups,c,t)
        d=metrics(rows)
        d["two_source_physical_group_bootstrap_95ci_pp"]=bootstrap(groups,c,t)
        d["by_stage"]={str(stage):metrics([r for r in rows if r["stage"]==stage])
                       for stage in STAGES}
        d["changed_only"]=metrics([r for r in rows if r["change"]])
        report["by_turn"][f"T{t}"]=d
    # Cumulative nondecreasing probabilities, input labels direct
    # physical deployment <=t. Changing policy can have nonmonotone
    # deltas, so check outcomes, not delta monotonicity.
    assert passby(0,1)==0 and passby(1,1)==1 and passby(1,3)==1
    assert passby(2,1)==0 and passby(2,2)==1 and passby(3,2)==0 and passby(3,3)==1
    outpath=Path(out);outpath.parent.mkdir(parents=True,exist_ok=True)
    outpath.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V35_121K_TWO_SOURCE_VALIDATION_PASS",json.dumps({
         "T1":{k:report["by_turn"]["T1"][k] for k in
                 ("changed_actions","T2_or_T3_expected_conditional_gain_pp",
                  "two_source_physical_group_bootstrap_95ci_pp")},
         "T2":{k:report["by_turn"]["T2"][k] for k in
                 ("changed_actions","T2_or_T3_expected_conditional_gain_pp",
                  "two_source_physical_group_bootstrap_95ci_pp","by_stage")},
         "T3":{k:report["by_turn"]["T3"][k] for k in
                 ("changed_actions","T2_or_T3_expected_conditional_gain_pp",
                  "two_source_physical_group_bootstrap_95ci_pp")}
      },sort_keys=True),flush=True)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--K",default="collected/v35_K_*.json.gz")
    p.add_argument("--C",default="collected/v35_C_*.json.gz")
    p.add_argument("--out",default="benchmark_results/v35_121k_conditional_validation.json")
    a=p.parse_args();run(a.K,a.C,a.out)
