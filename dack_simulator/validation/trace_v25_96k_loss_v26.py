#!/usr/bin/env python3
"""Read-only v25 loss taxonomy: 96k is locked evaluation, never fitted.

Counterfactual outcome differences are NOT causal proof of a bad mulligan.
This diagnoses hand-size/hand-identity/decision-disagreement categories.
"""
import collections
import gzip
import glob
import json
import statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
FILES="benchmark_results/v25_96k_full_game_shards/v25_96k_*.json.gz"
POLICIES=("v5","v14_128","v22_real_keep_DP")

def read():
    files=sorted(glob.glob(FILES))
    assert len(files)==64, ("incomplete v25 96k",len(files))
    rows=[]
    for path in files:
        with gzip.open(path,"rt") as stream:
            packet=json.load(stream)
        assert packet["status"]=="PASS" and packet["physical_first_seven_parity"]
        rows.extend(packet["rows"])
    rows.sort(key=lambda x:x["game_id"])
    assert [x["game_id"] for x in rows]==list(range(96000,96256))
    return rows

def prefix_decisions(a,b):
    h1=a["history"];h2=b["history"];stop=min(len(h1),len(h2))
    mismatch_keep=next((i for i in range(stop)
                        if h1[i]["kept"]!=h2[i]["kept"]),None)
    mismatch_bottom=next((i for i in range(stop)
                        if sorted(h1[i]["bottom"])!=sorted(h2[i]["bottom"])),None)
    mismatch_proposed_hand=next((i for i in range(stop)
                        if sorted(h1[i]["hand"])!=sorted(h2[i]["hand"])),None)
    return mismatch_keep,mismatch_bottom,mismatch_proposed_hand

def rowcase(row):
    a=row["v5"];b=row["v22_real_keep_DP"];c=row["v14_128"]
    a2=0<a["turn"]<=2;b2=0<b["turn"]<=2
    ak=a["history"][-1];bk=b["history"][-1]
    kdiff,bdiff,hdiff=prefix_decisions(a,b)
    same_final=sorted(ak["hand"])==sorted(bk["hand"])
    if same_final:
        kind="same_kept_multiset"
    elif a["keep_n"]==b["keep_n"]:
        kind="same_keep_depth_different_final_hand"
    else:
        kind="different_keep_depth"
    return {
       "game_id":row["game_id"],"seat":a["seat"],
       "v5_turn":a["turn"],"v22_turn":b["turn"],"v14_turn":c["turn"],
       "v5_keep_n":a["keep_n"],"v22_keep_n":b["keep_n"],
       "v14_keep_n":c["keep_n"],"kind":kind,
       "first_keep_disagreement_stage":kdiff,
       "first_bottom_disagreement_stage":bdiff,
       "first_proposed_hand_disagreement_stage":hdiff,
       "v5_first_seven":a["history"][0]["seven"],
       "v5_final_hand":ak["hand"],"v22_final_hand":bk["hand"],
       "v5_final_decision":{k:ak.get(k) for k in
             ("stage","raw","threshold","sampled_t1","kept","hand","bottom")},
       "v22_final_decision":{k:bk.get(k) for k in
             ("stage","raw","threshold","old_classifier_keep_vote","kept","hand","bottom")},
       "v5_history":[{k:z.get(k) for k in
             ("stage","keep_n","kept","raw","threshold","sampled_t1","hand","bottom")}
             for z in a["history"]],
       "v22_history":[{k:z.get(k) for k in
             ("stage","keep_n","kept","raw","threshold","old_classifier_keep_vote","hand","bottom")}
             for z in b["history"]],
       "v14_history":[{k:z.get(k) for k in
             ("stage","keep_n","kept","raw","threshold","hand","bottom")}
             for z in c["history"]],
    }

def summarize(rows):
    cases=[rowcase(x) for x in rows]
    groups={
       "v22_lost_T2": [z for z in cases if z["v5_turn"] in (1,2) and z["v22_turn"] not in (1,2)],
       "v22_gained_T2":[z for z in cases if z["v22_turn"] in (1,2) and z["v5_turn"] not in (1,2)],
       "both_T2":[z for z in cases if z["v5_turn"] in (1,2) and z["v22_turn"] in (1,2)],
       "neither_T2":[z for z in cases if z["v5_turn"] not in (1,2) and z["v22_turn"] not in (1,2)],
    }
    d={}
    for name,arr in groups.items():
        d[name]={
            "n":len(arr),
            "kind":dict(collections.Counter(x["kind"] for x in arr)),
            "v22_kept_more":sum(x["v22_keep_n"]>x["v5_keep_n"] for x in arr),
            "v22_kept_less":sum(x["v22_keep_n"]<x["v5_keep_n"] for x in arr),
            "same_keep_depth":sum(x["v22_keep_n"]==x["v5_keep_n"] for x in arr),
            "v5_mean_keep":statistics.mean(x["v5_keep_n"] for x in arr) if arr else None,
            "v22_mean_keep":statistics.mean(x["v22_keep_n"] for x in arr) if arr else None,
            "first_keep_disagree":dict(collections.Counter(str(x["first_keep_disagreement_stage"]) for x in arr)),
            "first_bottom_disagree":dict(collections.Counter(str(x["first_bottom_disagreement_stage"]) for x in arr)),
            "seat":dict(collections.Counter(str(x["seat"]) for x in arr)),
            "v14_t2_success":sum(x["v14_turn"] in (1,2) for x in arr),
            "v22_same_final_hand_as_v5":sum(x["kind"]=="same_kept_multiset" for x in arr)
        }
    mismatched_same_hand=[
        {"game_id":z["game_id"],"v5_turn":z["v5_turn"],"v22_turn":z["v22_turn"]}
        for z in cases if z["kind"]=="same_kept_multiset" and
            z["v5_turn"]!=z["v22_turn"]
    ]
    report={
        "schema":"dack_v26_v25_loss_diagnosis",
        "status":"PASS",
        "v25_96k_for_evaluation_only":True,
        "all_256_verified":True,
        "groups":d,
        "same_final_hand_different_turn_anomalies":mismatched_same_hand,
        "lost_T2_individual_cases":groups["v22_lost_T2"],
        "gained_T2_individual_cases":groups["v22_gained_T2"],
        "warning":"Paired differences do not identify which selected hand is optimal in expectation; evaluating on this set cannot be used for learned fitting.",
    }
    return report

if __name__=="__main__":
    data=summarize(read())
    path=Path("benchmark_results/v26_v25_loss_diagnosis_EVAL_ONLY.json")
    path.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
    print("V26_READONLY_LOSS_DIAG_PASS",json.dumps({
        "groups":data["groups"],
        "same_final_hand_different_turn_anomalies":data["same_final_hand_different_turn_anomalies"],
    },sort_keys=True),flush=True)
