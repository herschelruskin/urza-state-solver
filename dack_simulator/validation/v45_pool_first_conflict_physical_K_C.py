#!/usr/bin/env python3
"""v45 combine new first v5-v43 conflicts true physical QKEEP vs shared Qmull.

For each of 44 previously selected actual first-disagreement physical London
hands, original v5 and v43 choose opposite KEEP/MULL actions. The forced KEEP
has exactly the frozen v43 bottom; MULL restores full99 and follows frozen
v43 downstream continuation. For each source game estimate signed ADVANTAGE
of original v5's first action over v43's action on an independent physical
future lottery, and bootstrap:
  (1) outer 44 independent source hands by game ID;
  (2) 32 KEEP physical futures within each sampled hand;
  (3) ONE 96-future shared C lottery per seat/stage, reused by hands.
This is conditional on *selected v5-v43 disagreements* and cannot be
converted to a population full-game winrate.
"""
from __future__ import annotations
import glob,gzip,json,random
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
KSCHEMA="dack_v45_original_v5_v43_151k_first_conflict_true_forced_Qkeep_N44"
CSCHEMA="dack_v45_157k_real_v43_conditional_next_london_continuation_v1"
TRIALS_K=32;TRIALS_C=96;N=44
def by(t,h):return int(0<int(t)<=h)
def load():
    filesK=sorted(glob.glob(str(ROOT/"benchmark_results/v45_v5_v43_first_conflict_physical_K_shards/v45_v5_v43_firstK_*.json.gz")))
    filesC=sorted(glob.glob(str(ROOT/"benchmark_results/v45_real_v43_continuation_20cells_shards/v45_v43_C_*.json.gz")))
    assert len(filesK)==4 and len(filesC)==20,(len(filesK),len(filesC))
    ks={}
    for path in filesK:
        with gzip.open(path,"rt") as f:z=json.load(f)
        assert z["schema"]==KSCHEMA and z["status"]=="PASS"
        assert z["original_v43_candidate_hand_and_bottom_replayed_exactly"]
        assert z["fixed_original_v5_v43_first_disagreement_selection_before_new_QKEEP"]
        assert z["strict_original_99_slot_beam160"]
        assert z["K_real_unknown92_future_rollouts_per_group"]==TRIALS_K
        for r in z["rows"]:
            gid=int(r["gid"]);assert gid not in ks and len(r["true_physical_KEEP_turns"])==TRIALS_K
            ks[gid]=r
    assert len(ks)==44
    assert sum(z["v5_earlier"] for z in ks.values())==16
    assert sum(z["v43_earlier"] for z in ks.values())==28
    cs={}
    for path in filesC:
        with gzip.open(path,"rt") as f:z=json.load(f)
        assert z["schema"]==CSCHEMA and z["status"]=="PASS"
        assert z["future_full_99_card_decks_restored"]
        assert z["original_v43_candidate_choice_and_KEEP_reproduced_exactly"]
        assert z["physical_C_futures"]==TRIALS_C
        key=(int(z["seat"]),int(z["rejected_stage"]))
        assert key not in cs and len(z["results"])==TRIALS_C
        cs[key]=[r["win_turn"] for r in z["results"]]
    assert len(cs)==20
    assert all((r["seat"],r["stage"]) in cs for r in ks.values())
    return ks,cs

def summarize(rows):
    if not rows:return None
    n=len(rows)
    d={
      "N_first_disagreement_physical_outer_groups":n,
      "v5_kept_earlier":sum(r["v5_earlier"] for r in rows),
      "v43_kept_earlier":sum(r["v43_earlier"] for r in rows),
      "estimated_v5_action_physically_better_T2_groups":sum(r["v5_action_T2_signed_gain"]>0 for r in rows),
      "estimated_v43_action_physically_better_T2_groups":sum(r["v5_action_T2_signed_gain"]<0 for r in rows),
      "physical_T2_ties_at_estimate":sum(r["v5_action_T2_signed_gain"]==0 for r in rows),
    }
    for h in (1,2,3):
        d[f"conditional_mean_original_v5_action_gain_T{h}_pp"]=100*sum(
            r[f"v5_action_T{h}_signed_gain"] for r in rows)/n
    return d
def run():
    ks,cs=load()
    details=[]
    for gid,r in sorted(ks.items()):
        seat=int(r["seat"]);stage=int(r["stage"])
        K=r["true_physical_KEEP_turns"]
        C=cs[(seat,stage)]
        # sign +1: v5 keeps and v43 mulls; sign -1: v5 mulls and v43 keeps
        sign=int(r["original_v5_kept_this_stage"])-int(r["original_v43_kept_this_stage"])
        assert sign in (-1,1)
        a={
          "gid":gid,"seat":seat,"stage":stage,
          "v5_earlier":bool(r["v5_earlier"]),
          "v43_earlier":bool(r["v43_earlier"]),
          "v5_FIRST_action_keep":bool(r["original_v5_kept_this_stage"]),
          "v43_FIRST_action_keep":bool(r["original_v43_kept_this_stage"]),
          "original_v43_exact_legal_bottom":r["exact_v43_bottom"],
          "KEEP_N_physical_trials":TRIALS_K,"MULL_shared_C_N_physical_trials":TRIALS_C,
        }
        for h in (1,2,3):
            valK=sum(by(t,h) for t in K)/TRIALS_K
            valC=sum(by(t,h) for t in C)/TRIALS_C
            a[f"QKEEP_byT{h}"]=valK
            a[f"QMULL_frozen_v43_byT{h}"]=valC
            a[f"v5_action_T{h}_signed_gain"]=sign*(valK-valC)
        details.append(a)
    s={"all":summarize(details)}
    s["v43_kept_earlier"]=summarize([x for x in details if x["v43_earlier"]])
    s["v5_kept_earlier"]=summarize([x for x in details if x["v5_earlier"]])
    s["early_stage0_1"]=summarize([x for x in details if x["stage"] in (0,1)])
    for stage in range(5):
        s[f"stage_{stage}"]=summarize([x for x in details if x["stage"]==stage])
    rng=random.Random(450051)
    groups=sorted(ks)
    B=4000
    boot={h:[] for h in (1,2,3)}
    for _rep in range(B):
        cdraw={}
        for cell,turns in cs.items():
            sampled=[turns[rng.randrange(TRIALS_C)] for _ in range(TRIALS_C)]
            cdraw[cell]={h:sum(by(t,h) for t in sampled)/TRIALS_C
                          for h in (1,2,3)}
        gains={h:0. for h in (1,2,3)}
        for _ in range(N):
            g=ks[groups[rng.randrange(N)]]
            cell=(g["seat"],g["stage"])
            sign=int(g["original_v5_kept_this_stage"])-int(g["original_v43_kept_this_stage"])
            K=g["true_physical_KEEP_turns"]
            sampled=[K[rng.randrange(TRIALS_K)] for _ in range(TRIALS_K)]
            for h in (1,2,3):
                qK=sum(by(t,h) for t in sampled)/TRIALS_K
                gains[h]+=sign*(qK-cdraw[cell][h])
        for h in (1,2,3):boot[h].append(100*gains[h]/N)
    intervals={}
    for h in (1,2,3):
        v=sorted(boot[h])
        intervals[f"T{h}_selected_disagreement_two_source_95ci_pp"]=[v[99],v[3899]]
    doc={
      "schema":"dack_v45_fresh_physical_v5_v43_first_disagreement_conditional_regret_N44",
      "status":"PASS",
      "outer_selected_game_groups":N,
      "frozen_v43_exact_hand_and_bottom_KEEP_32_futures":True,
      "frozen_v43_future_full99_MULL_shared96_per_cell":True,
      "K_physical_new_gameplay_runs":N*TRIALS_K,
      "C_physical_new_gameplay_runs":len(cs)*TRIALS_C,
      "bootstrap_resamples_original_hands_Kfuture_and_SHARED_Ccell":True,
      "original_v5_actual_first_action_used_only_as_retrospective_reference":True,
      "no_v5_beam_lookahead_in_physical_recheck":True,
      "preselected_151k_first_conflicts_NOT_population_random_sample":True,
      "not_cedh_multiplayer_or_fullgame_winrate":True,
      "no_new_model_fit_or_threshold_tuning":True,
      "summary":s,"two_source_bootstrap":intervals,
      "per_selected_hand":details,
    }
    path=ROOT/"benchmark_results/v45_first_v5_v43_conflict_physical_K_vs_C_N44.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print("DACK_V45_ORIGINAL_V5_V43_FIRST_CONFLICT_TRUE_PHYSICAL_REGRET_PASS",
          json.dumps({"summary":s,"two_source_ci":intervals},sort_keys=True),flush=True)
if __name__=="__main__":run()
