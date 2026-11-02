#!/usr/bin/env python3
"""Physical conditional candidate contrast on development-only 1624xx states.

Candidate arms selected by frozen predictions BEFORE observing physical results.
Two naturally reached keep-four stages plus one high predicted-exclusion
hypothetical keep-four stage; not a population or full-policy benchmark.
"""
from __future__ import annotations
import hashlib,json,random,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as v43
import dack_mulligan_teacher_features_v13_20261031 as f
from dack_simulator.validation.collect_teacher_london_v13 import finalists
ref=v43.ref
CASES=((162403,4),(162408,4),(162409,4))
N=32
PROTO="DACK_V43_INDEPENDENT_CONDITIONAL_CANDIDATE_PHYSICAL_1624XX_V1"

def seed(*parts):
    s=json.dumps((PROTO,*parts),separators=(",",":"),sort_keys=False)
    return int.from_bytes(hashlib.sha256(s.encode()).digest()[:8],"big")

def main():
    v43.audit()
    out=[]
    t0=time.monotonic()
    for gid,stage in CASES:
        source_seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(source_seed)
        deck=ref.SLOT_VARIANTS["one_key_34"]
        state,hist=v43.choose_keep(deck,seat,orders)
        order=orders[stage]
        seven=tuple(deck[s] for s in order[:7])
        hidden=tuple(deck[s] for s in order[7:])
        pool=Counter(hidden);kn=ref.sim.STAGES[stage]
        allc=finalists(seven,kn,hidden,limit=99)
        scores=[]
        for i,c in enumerate(allc):
            x=f.extract(seven,c["hand"],c["bottom"],pool,seat,kn,stage,c["struct_rank"],i)
            scores.append(float(v43.v27.original.estimator.predict(v43.v27.original.MODEL,x)))
        top=max(range(min(12,len(allc))),key=lambda i:(scores[i],-i))
        globalmax=max(range(len(allc)),key=lambda i:(scores[i],-i))
        target=[("v43_top12",top),("model_global_Q2",globalmax),("structural_first",0)]
        arms={}
        for label,i in target:
            c=allc[i]
            signature=json.dumps([c["hand"],c["bottom"]])
            if signature not in arms:
                arms[signature]={"labels":[label],"index":i,"q":scores[i],
                                 "hand":list(c["hand"]),"bottom":list(c["bottom"]),"turns":[]}
            else:arms[signature]["labels"].append(label)
        for future in range(N):
            unseen=list(hidden)
            random.Random(seed(gid,stage,future,"unseen92")).shuffle(unseen)
            for a in arms.values():
                ref.sim.reset_caches()
                ref.sim.root.install("one_key_34")
                ref.sim.m.set_trial_seed(seed(gid,stage,future,"shared_chance"))
                ref.d._WIN_CACHE.clear()
                turn=ref.d._win_turn_from_unknown_order(tuple(a["hand"]),
                     tuple(unseen)+tuple(a["bottom"]),seat,beam=160,max_turn=3)
                assert turn in (0,1,2,3,None)
                a["turns"].append(int(turn or 0))
        for a in arms.values():
            a["T1"]=sum(t==1 for t in a["turns"])
            a["by_T2"]=sum(t in (1,2) for t in a["turns"])
            a["by_T3"]=sum(t in (1,2,3) for t in a["turns"])
        values=list(arms.values())
        t2_base=next(a for a in values if "v43_top12" in a["labels"])
        contrasts=[]
        for arm in values:
            if arm is t2_base:continue
            diffs=[int(0<x<=2)-int(0<y<=2) for x,y in zip(arm["turns"],t2_base["turns"])]
            contrasts.append({"vs":arm["labels"],"t2_gain":diffs.count(1),
               "t2_loss":diffs.count(-1),"t2_delta_pp":100*sum(diffs)/N})
        case={"gid":gid,"stage":stage,"kn":kn,"seat":seat,
              "reached":len(hist)>stage,"actually_kept_here":len(hist)>stage and hist[-1]["stage"]==stage,
              "source_seven":list(seven),
              "all_candidates":len(allc),"max_top12_q":scores[top],
              "global_max_q":scores[globalmax],
              "global_max_excluded":globalmax>=12,
              "arms":values,"contrasts_vs_v43":contrasts}
        out.append(case)
        print("PHYSICAL_CASE",json.dumps({k:case[k] for k in ("gid","reached","all_candidates","max_top12_q","global_max_q","global_max_excluded","contrasts_vs_v43")}),flush=True)
    result={"status":"PASS","schema":"dack_v43_conditional_candidate_blind_physical_v1",
       "development_only_selected_source_states":True,
       "physical_futures_per_arm":N,"same_hidden_92_per_future":True,
       "same_gameplay_chance_seed_per_future":True,
       "strict_goldfish_beam":160,"not_full_policy":True,"not_prospective_acceptance":True,
       "elapsed_seconds":round(time.monotonic()-t0,3),"cases":out}
    dest=ROOT/"benchmark_results/v43_new_candidate_pruning_physical_selected_1624xx.json"
    dest.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("DACK_V43_CONDITIONAL_PHYSICAL_PASS",result["elapsed_seconds"],flush=True)

if __name__=="__main__":main()
