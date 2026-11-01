#!/usr/bin/env python3
"""Posthoc v40 true-v5 students over previously measured 115k v5-v27 disagreements.

Zero physics, no fitting, no changed threshold. This is an ALREADY CONSUMED
research diagnostic: it CANNOT validate prospective full-game win rate.
The same 100 source hands have 32 physical keep and 96 shared-C futures in
v34c archives, with one common v33b retained-hand bottom and continuation.
We evaluate v40 keep/mull at the preselected first v5-v27 disagreement;
student's own earlier-path divergences are counted separately.
"""
from __future__ import annotations
from collections import Counter
import hashlib,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_mulligan_teacher_features_v13_20261031 as f
from dack_simulator.validation.collect_teacher_london_v13 import finalists
from dack_simulator.validation import v34c_pool_actual_disagreement as physics
from dack_paired_counterfactual_v1_20261030 import SPEC,SEED_STRIDE,stage_slots,SLOT_VARIANTS
from collections import Counter as Bag

MODES=("full","portable")
MODEL_PATTERN="models/v40_true_v5_archived/v40_archived_actual_v5_{}_1288_RESEARCH.json"
SCHEMA="dack_v40_recovered_teacher_student_115k_disagreement_overlay_1"
DECK="one_key_34"

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def vote(trees,x):
    z=0.
    for tree in trees:
        k=0
        while tree["left"][k]>=0:
            feat=int(tree["feature"][k])
            val=struct.unpack("<f",struct.pack("<f",float(x[feat])))[0]
            k=tree["left"][k] if val<=tree["threshold"][k] else tree["right"][k]
        z+=tree["positive"][k]
    return z/len(trees)

def model(mode):
    path=ROOT/MODEL_PATTERN.format(mode)
    m=json.loads(path.read_text())
    assert m["schema"]=="dack_v40_true_v5_behavior_cloning_two_head_v1"
    assert m["feature_schema_sha256"]==f.feature_hash()
    assert m["mode"]==mode and m["train_group_n"]==1288 and not m["policy_approved"]
    assert m["source_corpus_sha256"]==sha(ROOT/"datasets/v40_recovered_original_v5_history_1592.jsonl.gz")
    assert all(f.FEATURES[int(i)]==name for i,name in zip(m["feature_indices"],m["feature_names"]))
    return m,sha(path)

def score(m,seven,unknown,seat,stage):
    kn=(7,7,6,5,4,3,2,1)[stage]
    opts=finalists(seven,kn,unknown)
    allx=[]
    for i,op in enumerate(opts):
        feats=f.extract(seven,op["hand"],op["bottom"],Bag(unknown),
                        seat,kn,stage,op["struct_rank"],i)
        allx.append([feats[j] for j in m["feature_indices"]])
    chosen=max(range(len(opts)),key=lambda i:(vote(m["choice_trees"],allx[i]),-i))
    keep_prob=vote(m["keep_trees"],allx[chosen])
    keep=(kn==1 or keep_prob>=m["keep_threshold"])
    return {"keep":keep,"keep_vote":keep_prob,
            "bottom_index":chosen,"hand":opts[chosen]["hand"],
            "bottom":opts[chosen]["bottom"]}

def simulate_actions(gid,seat,m):
    seed=int(SPEC["seed_base"])+gid*SEED_STRIDE
    actual_seat,orders=stage_slots(seed)
    assert seat==actual_seat
    deck=SLOT_VARIANTS[DECK]
    assert len(deck)==99
    actions=[]
    for stage,order in enumerate(orders):
        seven=tuple(deck[s] for s in order[:7])
        unseen=tuple(deck[s] for s in order[7:])
        assert len(unseen)==92 and Bag(seven)+Bag(unseen)==Bag(deck.values())
        result=score(m,seven,unseen,seat,stage)
        actions.append(result)
    return actions

def y(turn,t):return int(0<int(turn)<=t)

def run(output):
    groups,cont,csha=physics.load(
        str(ROOT/"benchmark_results/v34c_forced_keep_shards/v34c_keep_*.json.gz"),
        str(ROOT/"benchmark_results/v34_consistent_regret_shards/v34_C_*.json.gz"))
    assert len(groups)==100
    report={
        "schema":SCHEMA,"status":"PASS",
        "source": "archived 100 v5-v27 first-disagreement games in 115000..115255",
        "source_shards_are_prior_consumed_diagnostic":True,
        "no_new_physics_no_fit_no_v5_lookahead":True,
        "common_physical_bottom":"v33b (not student or teacher bottom)",
        "common_downstream_policy":"v27 keep and v33b bottom",
        "physical_estimate":"32 independent forced keep trials and 96 shared-C per seat-stage",
        "population_winrate_claim_permitted":False,
        "models":{},
    }
    for mode in MODES:
        m,msha=model(mode)
        counts=Counter();details=[]
        for r in groups:
            gid=int(r["game_id"]);s=int(r["stage"]);seat=int(r["seat"])
            assert 0<=s<=6
            acts=simulate_actions(gid,seat,m)
            action=acts[s]["keep"]
            teacher=bool(r["v5_first_keeps"])
            baseline=not teacher
            prior_student=next(i for i,a in enumerate(acts) if a["keep"])
            # v5/v27 both rejected prior stages; only a clean forced-stage
            # experiment if student ALSO rejected all earlier stages.
            reached=all(not a["keep"] for a in acts[:s])
            values={}
            k=r["fresh_keep_futures_by_split"]["calibration"]+r["fresh_keep_futures_by_split"]["replication"]
            c=cont[(seat,s)]["calibration"]+cont[(seat,s)]["replication"]
            assert len(k)==32 and len(c)==96
            for turn in (1,2,3):
                adv=sum(y(v,turn) for v in k)/32-sum(y(v,turn) for v in c)/96
                # Signed relative to frozen v27 action, at the FIRST prior
                # v5/v27 disagreement. No causal conclusion for preceding path.
                signed=(int(action)-int(baseline))*adv
                values[f"T{turn}_student_minus_v27"]=signed
                values[f"T{turn}_v5_minus_v27"]=(int(teacher)-int(baseline))*adv
            counts["total"]+=1
            counts["matches_v5_at_conflict"]+=int(action==teacher)
            counts["matches_v27_at_conflict"]+=int(action==baseline)
            counts["student_reaches_conflict"]+=int(reached)
            counts["student_reaches_and_matches_v5"]+=int(reached and action==teacher)
            counts["student_reaches_and_differs_from_v5"]+=int(reached and action!=teacher)
            counts["v5_keep_v27_mull"]+=int(teacher)
            counts["v5_mull_v27_keep"]+=int(not teacher)
            counts[f"stage_{s}"]+=1
            if s<=2:
                counts["early_0_2"]+=1
                counts["early_student_matches_v5"]+=int(action==teacher)
                counts["early_student_reaches"]+=int(reached)
            details.append({
                "game_id":gid,"stage":s,"seat":seat,
                "v5_first_keeps":teacher,
                "student_first_keep_stage":prior_student,
                "student_reaches_original_conflict":reached,
                "student_keep_at_original_conflict":action,
                "student_vote":round(acts[s]["keep_vote"],6),
                "student_bottom_candidate":acts[s]["bottom_index"],
                **values,
            })
        overall={}
        for horizon in (1,2,3):
            overall[f"T{horizon}_conditional_student_minus_v27_pp"]=100*sum(
                z[f"T{horizon}_student_minus_v27"] for z in details)/100
            overall[f"T{horizon}_conditional_v5_minus_v27_pp"]=100*sum(
                z[f"T{horizon}_v5_minus_v27"] for z in details)/100
            active=[z for z in details if z["student_reaches_original_conflict"]]
            overall[f"T{horizon}_reached_student_minus_v27_pp_on_reached_only"]=(
                100*sum(z[f"T{horizon}_student_minus_v27"] for z in active)/len(active)
                if active else None)
        assert counts["total"]==100 and counts["matches_v5_at_conflict"]+counts["matches_v27_at_conflict"]==100
        report["models"][mode]={
            "model_sha256":msha,"counts":dict(counts),"conditional_diagnostic":overall,
            "per_game":details,
            "caveat":"Selection was based on v5-v27, not student. Counterfactual only at first v5-v27 conflict under shared v33b bottom; student may have made an earlier different action. No full-game estimate."}
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("DACK_V40_STUDENT_REPLAY_PHYSICAL_REGRET_OVERLAY_PASS",
          json.dumps({m:{"counts":x["counts"],"diagnostic":x["conditional_diagnostic"]}
                      for m,x in report["models"].items()},sort_keys=True),flush=True)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="benchmark_results/v40_student_v5_vs_v27_115k_physical_overlay.json")
    a=p.parse_args();run(a.out)
