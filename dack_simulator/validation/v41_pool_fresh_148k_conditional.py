#!/usr/bin/env python3
"""Two-source hierarchical bootstrap of NEW 148k physical early-action comparison.

All decisions were frozen before their physical rollout results. Resample
physical game groups (with three correlated London stage observations each),
their independent KEEP futures and one shared C lottery per seat/stage cell.
Report T2/T3 for all stage states and reached-oracle-agnostic hypothetical
stages separately. No v5 and no end-to-end policy outcome claims.
"""
from __future__ import annotations
import argparse,glob,gzip,json,random
from collections import Counter,defaultdict
from pathlib import Path
SCHEMA="dack_v41_148k_prospective_conditional_physical_K_C_1"
OUT="dack_v41_148k_fresh_conditional_T2_T3_validation_1"
GAMES=64
K=8
C=64

def y(t,h):return int(0<int(t)<=h)

def run(kpattern,cpattern,out):
    Kpaths=sorted(glob.glob(kpattern))
    Cpaths=sorted(glob.glob(cpattern))
    assert len(Kpaths)==8 and len(Cpaths)==12,(len(Kpaths),len(Cpaths))
    groups=defaultdict(list);Ksha=None
    for path in Kpaths:
        with gzip.open(path,"rt") as f:z=json.load(f)
        assert z["schema"]==SCHEMA and z["action"]=="K" and z["status"]=="PASS"
        assert z["model_decision_made_before_futures"]
        assert z["strict_actual_beam160"] and z["prospective_groups_not_used_in_fit"]
        assert z["source_v27_keep_and_v33b_bottom_frozen"]
        assert z["no_original_v5_calls"] and z["not_end_to_end_winrate"]
        assert z["groups"]==8 and z["futures_per_stage"]==K
        if Ksha is None:Ksha=z["source_v41_model_sha256"]
        assert z["source_v41_model_sha256"]==Ksha
        for r in z["rows"]:
            gid=int(r["game_id"]);stage=int(r["stage"])
            assert 148000<=gid<=148063 and stage in (0,1,2)
            assert len(r["physical_K_turns"])==K
            assert all(t in (0,1,2,3) for t in r["physical_K_turns"])
            assert len(r["selected_v33b_hand"])==r["keep_n"]
            assert len(r["selected_v33b_bottom"])==7-r["keep_n"]
            groups[gid].append(r)
    assert sorted(groups)==list(range(148000,148064))
    for gid in groups:
        assert sorted(r["stage"] for r in groups[gid])==[0,1,2]
        assert len(set(r["seat"] for r in groups[gid]))==1
    Ccells={}
    for path in Cpaths:
        with gzip.open(path,"rt") as f:z=json.load(f)
        assert z["schema"]==SCHEMA and z["status"]=="PASS" and z["action"]=="C"
        assert z["strict_actual_beam160"] and z["all_99_cards_returned_on_mull"]
        assert z["frozen_downstream_v27_keep_v33b_bottom"]
        assert z["model_fixed_prior_to_C_futures"] and z["not_end_to_end_winrate"]
        assert z["source_v41_model_sha256"]==Ksha
        assert z["independent_full99_futures"]==C
        key=(int(z["seat"]),int(z["stage"]))
        assert key not in Ccells and key[0] in range(4) and key[1] in range(3)
        turns=z["turns"]
        assert len(turns)==C and all(t in (0,1,2,3) for t in turns)
        Ccells[key]=turns
    assert len(Ccells)==12
    detail=[]
    for gid in sorted(groups):
        for r in groups[gid]:
            cell=(int(r["seat"]),int(r["stage"]))
            ck=Ccells[cell]
            records={
              "gid":gid,"stage":int(r["stage"]),"seat":int(r["seat"]),
              "old_keep":bool(r["v27_keep"]),"new_keep":bool(r["v41_keep"]),
              "changed":bool(r["v27_keep"]!=r["v41_keep"]),
            }
            for h in (1,2,3):
                a=sum(y(t,h) for t in r["physical_K_turns"])/K
                b=sum(y(t,h) for t in ck)/C
                records[f"K{h}"]=a;records[f"C{h}"]=b
                records[f"T{h}_delta"]=(int(r["v41_keep"])-int(r["v27_keep"]))*(a-b)
            detail.append(records)
    def summarize(rr):
        if not rr:return None
        return {
          "N_stage_observations":len(rr),
          "N_independent_groups":len(set(r["gid"] for r in rr)),
          "changed_stages":sum(r["changed"] for r in rr),
          "keep_to_mull":sum(r["old_keep"] and not r["new_keep"] for r in rr),
          "mull_to_keep":sum(not r["old_keep"] and r["new_keep"] for r in rr),
          **{f"conditional_T{h}_one_step_gain_pp":
              100*sum(r[f"T{h}_delta"] for r in rr)/len(rr) for h in (1,2,3)},
        }
    base=summarize(detail)
    assert base["N_stage_observations"]==192 and base["N_independent_groups"]==64
    assert base["changed_stages"]==(base["keep_to_mull"]+base["mull_to_keep"])
    rng=random.Random(148410)
    gids=sorted(groups)
    B=2500;reps={h:[] for h in (1,2,3)}
    for b in range(B):
        # One C lottery per cell, shared across all resampled physical games.
        Cvals={}
        for cell,arr in Ccells.items():
            chosen=[arr[rng.randrange(C)] for _ in range(C)]
            Cvals[cell]={h:sum(y(t,h) for t in chosen)/C for h in (1,2,3)}
        delta={h:0. for h in (1,2,3)}
        for _ in range(GAMES):
            group=groups[gids[rng.randrange(GAMES)]]
            for r in group:
                sign=int(r["v41_keep"])-int(r["v27_keep"])
                if sign==0:continue
                cell=(r["seat"],r["stage"])
                sample=[r["physical_K_turns"][rng.randrange(K)] for _ in range(K)]
                for h in (1,2,3):
                    kval=sum(y(t,h) for t in sample)/K
                    delta[h]+=sign*(kval-Cvals[cell][h])
        for h in (1,2,3):reps[h].append(100*delta[h]/(GAMES*3))
    intervals={}
    for h in (1,2,3):
        a=sorted(reps[h])
        intervals[f"T{h}"]={
           "mean_delta_pp":base[f"conditional_T{h}_one_step_gain_pp"],
           "two_source_group_bootstrap_95ci_pp":[a[int(B*.025)],a[int(B*.975)-1]],
        }
    report={
      "schema":OUT,"status":"PASS","source_model_sha256":Ksha,
      "N_independent_new_physical_deals":GAMES,
      "N_early_stage_K_states":len(detail),
      "true_K_gameplay_rollouts":GAMES*3*K,
      "independent_shared_C_lottery_rollouts":12*C,
      "K_futures_per_early_stage":K,"C_futures_per_seat_stage":C,
      "physical_group_and_K_future_and_shared_C_bootstrap":True,
      "decisions_frozen_before_new_outcomes":True,
      "models_approved":False,
      "not_a_full_game_winrate_test":True,
      "same_downstream_continuation_v27_keep_v33b_bottom":True,
      "unseen_original_v5_teacher_not_used":True,
      "summary_all_192_hypothetical_stage_states":base,
      "by_stage":{str(s):summarize([r for r in detail if r["stage"]==s])
                  for s in (0,1,2)},
      "by_changed":summarize([r for r in detail if r["changed"]]),
      "two_source_ci":intervals,
      "warning":"N64 initial diagnostic and hypothetical stages not necessarily path-reached; T2 one-step conditional gain is not whole-game policy improvement.",
    }
    path=Path(out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("DACK_V41_FRESH_148K_TWOSOURCE_CONDITIONAL_POOL_PASS",
          json.dumps({"all":base,"by_stage":report["by_stage"],
                     "CI":intervals},sort_keys=True),flush=True)

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--K",required=True)
    a.add_argument("--C",required=True)
    a.add_argument("--out",default="benchmark_results/v41_fresh_148k_N64_conditional.json")
    v=a.parse_args();run(v.K,v.C,v.out)
