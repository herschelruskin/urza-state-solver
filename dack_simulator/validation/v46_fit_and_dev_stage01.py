#!/usr/bin/env python3
"""Train bounded v46 K2 residual from N192 random outer seven-deal groups.

Held-out N64 independent dev groups, with two counterfactual seven-card
London states each. Fit on physical QKEEP from 16 independent blind future
draws; use frozen v43 Q2 as a stabilizing prior. The shared physical
Qmull C128 seat-stage cell is used ONLY for thresholds and selected-action
regret evaluation, not for regression labels.

For STAGE0 ONLY, the stage1 policy remains frozen v43. For STAGE1 ONLY,
stages2+ remain v43. Do not combine both without re-estimating stage0 C.
"""
from __future__ import annotations
import argparse,gzip,glob,json,random,hashlib,sys
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
import dack_mulligan_v46_first_two_sevens_physical as v
import dack_mulligan_teacher_features_v13_20261031 as f
from dack_simulator.validation.v45_frozen_v43_continuation import ref

K_SCHEMA="dack_v46_random_seven_real_beam160_stage0_stage1_K16_v1"
C_SCHEMA="dack_v46_new_frozen_v43_full99_shared_C128_stage01_v1"
TRAIN_IDS=range(163000,163192);DEV_IDS=range(163192,163256)

def by(t,h):return int(0<int(t)<=h)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def source(folder):
    paths=sorted(glob.glob(str(Path(folder)/"v46_K_*.json.gz")))
    cp=sorted(glob.glob(str(Path(folder)/"v46_C_*.json.gz")))
    assert len(paths)==16 and len(cp)==8,(len(paths),len(cp))
    rows={}; hashes=[]
    deck=ref.SLOT_VARIANTS["one_key_34"]
    for path in paths:
        with gzip.open(path,"rt") as f0:d=json.load(f0)
        assert d["schema"]==K_SCHEMA and d["status"]=="PASS"
        assert d["strict_99_card_beam160_original_dice"] and d["source_data_is_new_random_physical_not_teacher_selected"]
        assert d["stage0_and_stage1_have_no_bottom_choices"] and d["stage1_sampled_even_if_stage0_would_keep"]
        assert d["N_independent_physical_groups"]==16 and d["K_independent_blind_futures_per_stage"]==16
        hashes.append((Path(path).name,sha(path)))
        for r in d["rows"]:
            gid=int(r["gid"]);stage=int(r["stage"])
            assert gid in range(163000,163256) and stage in (0,1)
            assert (gid,stage) not in rows
            assert len(r["seven"])==7 and len(r["physical_keep_turns"])==16
            assert all(t in (0,1,2,3) for t in r["physical_keep_turns"])
            assert Counter(r["seven"])<=Counter(deck.values())
            assert r["source_v43_keep"]==(r["source_v43_pred_Q2"]>=r["source_v43_DP"])
            rows[(gid,stage)]=r
    assert set(rows)=={(gid,s) for gid in range(163000,163256) for s in (0,1)}
    C={};csha=[]
    for path in cp:
        with gzip.open(path,"rt") as f0:d=json.load(f0)
        assert d["schema"]==C_SCHEMA and d["status"]=="PASS"
        assert d["all_99_cards_restored_before_each_London_draw"]
        assert d["full_99_deck_including_original_rejected_seven"]
        assert d["shared_across_unrelated_K_seven_groups_same_seat_stage"]
        assert d["frozen_v43_policy_full_exact_continuation"]
        assert d["future_orders_new_tag_not_prior_v45_C"]
        key=(int(d["seat"]),int(d["stage"]))
        assert key not in C and len(d["turns"])==128
        C[key]=d["turns"]
        csha.append((Path(path).name,sha(path)))
    assert set(C)=={(seat,stage) for seat in range(4) for stage in (0,1)}
    return rows,C,hashes,csha

def vectors(rows):
    x=[];y=[];w=[]
    deck=ref.SLOT_VARIANTS["one_key_34"]
    for (gid,stage),r in sorted(rows.items()):
        visible=tuple(r["seven"])
        unseen=Counter(deck.values())-Counter(visible)
        hidden=tuple(c for c,n in sorted(unseen.items()) for _ in range(n))
        x.append(v.features(visible,hidden,int(r["seat"]),stage,
                            float(r["source_v43_pred_Q2"]),float(r["source_v43_DP"])))
        k2=sum(by(t,2) for t in r["physical_keep_turns"])/16
        y.append(k2-float(r["source_v43_pred_Q2"]))
        w.append(.5) # each of the 192 independent physical groups contributes one unit
    return np.asarray(x,dtype=float),np.asarray(y,dtype=float),np.asarray(w,dtype=float)

def fit(rows,C,hashes,csha):
    assert {gid for gid,_ in rows}==set(TRAIN_IDS)
    X,y,w=vectors(rows)
    assert X.shape==(384,len(v.NAMES))
    scaler=StandardScaler().fit(X,sample_weight=w)
    model=Ridge(alpha=v.ALPHA).fit(scaler.transform(X),y,sample_weight=w)
    doc={
      "schema":v.SCHEMA,"status":"EXPERIMENTAL_UNAPPROVED",
      "policy_approved":False,"original_99_card_deck":"one_key_34",
      "training_distinct_outer_deals":192,"train_deals":[163000,163191],
      "dev_deals_excluded_from_fit":[163192,163255],
      "two_correlated_counterfactual_seven_stages_per_deal":True,
      "train_physical_futures_per_stage":16,
      "source_v43_Q2_is_original_prediction_for_exact_seven":True,
      "train_target":"real physical P(byT2 KEEP) minus frozen v43 predicted Q2",
      "feature_hash":f.feature_hash(),"feature_names":list(v.NAMES),
      "alpha":v.ALPHA,"shrink":v.SHRINK,"residual_clip_abs":v.CLIP,
      "mean":[float(z) for z in scaler.mean_],
      "scale":[float(z) for z in scaler.scale_],
      "coefficients":[float(z) for z in model.coef_],
      "intercept":float(model.intercept_),
      "frozen_v43_true_full99_C128_physical":{
          f"{s}:{st}":{
             "T1":sum(by(t,1) for t in turns)/128,
             "T2":sum(by(t,2) for t in turns)/128,
             "T3":sum(by(t,3) for t in turns)/128
          } for (s,st),turns in sorted(C.items())},
      "source_K_shards_sha256":hashes,"source_C_shards_sha256":csha,
      "old_155k_cohort_not_touched":True,
      "stage0_and_stage1_must_not_be_simultaneously_edited_under_old_stage0_C":True,
    }
    for i in range(min(100,len(X))):
        a=float(model.predict(scaler.transform(X[i:i+1]))[0])
        a=max(-v.CLIP,min(v.CLIP,a))
        raw=next(iter(rows.values()))["source_v43_pred_Q2"] if False else 0.
        b=float(doc["intercept"])+sum(c*(float(t)-mu)/sd for c,t,mu,sd
            in zip(doc["coefficients"],X[i],doc["mean"],doc["scale"]))
        assert abs(a-max(-v.CLIP,min(v.CLIP,b)))<1e-9
    return doc

def add_rows(dev,mdl,C):
    deck=ref.SLOT_VARIANTS["one_key_34"]
    out=[]
    for (gid,stage),r in sorted(dev.items()):
        seat=int(r["seat"]);seven=tuple(r["seven"])
        unseen=Counter(deck.values())-Counter(seven)
        hidden=tuple(c for c,n in sorted(unseen.items()) for _ in range(n))
        q=float(r["source_v43_pred_Q2"])
        old_cut=float(r["source_v43_DP"])
        x=v.features(seven,hidden,seat,stage,q,old_cut)
        qc=v.corrected(mdl,x,q)
        Cmean={h:sum(by(t,h) for t in C[(seat,stage)])/128 for h in (1,2,3)}
        old=bool(r["source_v43_keep"])
        alternative={
            "C_only":q>=Cmean[2],
            "ridge_C":qc>=Cmean[2],
        }
        out.append({
           "gid":gid,"stage":stage,"seat":seat,"old_keep":old,
           "old_pred_Q2":q,"old_frozen_DP":old_cut,
           "physical_C_Q2":Cmean[2],"physical_C_Q3":Cmean[3],
           "corrected_Q2":qc,
           "physical_K_turns":r["physical_keep_turns"],
           "candidates":alternative,
        })
    assert len(out)==128
    return out

def outcome(rr,C,mode):
    if not rr:return None
    num=len(rr);changed=[]
    for row in rr:
        if row["candidates"][mode]!=row["old_keep"]:changed.append(row)
    out={"N_stage_states":num,"N_independent_physical_deals":len({r["gid"] for r in rr}),
         "decisions_changed":len(changed),
         "early_KEEP_to_MULL":sum(r["old_keep"] and not r["candidates"][mode] for r in changed),
         "early_MULL_to_KEEP":sum(not r["old_keep"] and r["candidates"][mode] for r in changed)}
    for h in (1,2,3):
        s=0.
        for r in rr:
            sign=int(r["candidates"][mode])-int(r["old_keep"])
            k=sum(by(t,h) for t in r["physical_K_turns"])/16
            c=sum(by(t,h) for t in C[(r["seat"],r["stage"])])/128
            s+=sign*(k-c)
        out[f"physical_one_step_T{h}_pp"]=100*s/num
    return out

def boots(rr,C,mode,stage):
    rr=[r for r in rr if r["stage"]==stage]
    assert len(rr)==64 and len({r["gid"] for r in rr})==64
    rng=random.Random(461630+stage+(0 if mode=="C_only" else 1000))
    B=2400;res={h:[] for h in (2,3)}
    for iteration in range(B):
        Cmean={}
        for seat in range(4):
            t=C[(seat,stage)]
            picks=[t[rng.randrange(128)] for _ in range(128)]
            Cmean[seat]={h:sum(by(z,h) for z in picks)/128 for h in (2,3)}
        delta={h:0. for h in (2,3)}
        for i in range(64):
            r=rr[rng.randrange(64)]
            sign=int(r["candidates"][mode])-int(r["old_keep"])
            if sign==0:continue
            turns=r["physical_K_turns"]
            picks=[turns[rng.randrange(16)] for _ in range(16)]
            for h in (2,3):
                k=sum(by(t,h) for t in picks)/16
                delta[h]+=sign*(k-Cmean[r["seat"]][h])
        for h in (2,3):res[h].append(100*delta[h]/64)
    return {f"T{h}_95ci_pp":[sorted(res[h])[59],sorted(res[h])[2339]] for h in (2,3)}

def run(folder,out,modelpath):
    rows,C,kh,ch=source(folder)
    train={k:r for k,r in rows.items() if k[0] in TRAIN_IDS}
    dev={k:r for k,r in rows.items() if k[0] in DEV_IDS}
    assert len(train)==384 and len(dev)==128 and set(train).isdisjoint(dev)
    mdl=fit(train,C,kh,ch)
    m=Path(modelpath);m.parent.mkdir(parents=True,exist_ok=True)
    m.write_text(json.dumps(mdl,sort_keys=True,indent=2)+"\n")
    cases=add_rows(dev,mdl,C)
    tests={}
    for stage in (0,1):
        tests[str(stage)]={}
        for name in ("C_only","ridge_C"):
            r=[x for x in cases if x["stage"]==stage]
            point=outcome(r,C,name)
            point.update(boots(cases,C,name,stage))
            # PREDECLARED exploratory development gate, not approval.
            point["development_gate_pass"]=bool(
               point["decisions_changed"]>=3
               and point["physical_one_step_T2_pp"]>=1.
               and point["physical_one_step_T3_pp"]>=-2.
               and point["T2_95ci_pp"][0]>-3.)
            tests[str(stage)][name]=point
            print("DACK_V46_STAGE01_RANDOM_DEV",stage,name,
                  json.dumps(point,sort_keys=True),flush=True)
    eligible=[(stage,mode,data) for stage,methods in tests.items()
        for mode,data in methods.items() if data["development_gate_pass"]]
    eligible.sort(key=lambda x:(-x[2]["physical_one_step_T2_pp"],x[1]!="C_only",x[0]))
    best=(None if not eligible else {"stage":int(eligible[0][0]),
           "mode":eligible[0][1],
           "pilot_development_T2_pp":eligible[0][2]["physical_one_step_T2_pp"]})
    doc={
      "schema":"dack_v46_random_sevens_train192_dev64_real_K16_shared_C128",
      "status":"PASS","no_model_or_policy_approved":True,
      "source_model_sha256":sha(m),
      "train_outer_independent_deals":192,"dev_outer_independent_deals":64,
      "train_K_physical_futures":192*2*16,
      "dev_K_physical_futures":64*2*16,
      "new_shared_C_real_futures":8*128,
      "stage1_is_counterfactual_if_stage0_baseline_kept":True,
      "group_level_stages_correlated_not_independent_sevens":True,
      "stage0_continuation_exact_ONLY_if_stage1_frozen_v43":True,
      "stage1_continuation_exact_if_later_stages_frozen_v43":True,
      "DO_NOT_combine_stage0_and_stage1_without_NEW_stage0_C":True,
      "development_data_NOT_used_to_fit_residual":True,
      "not_end_to_end_full_game_T2_winrate":True,
      "new_164k_future_full_game_test_UNOPENED":True,
      "dev_results":tests,"preferred_development_candidate_if_any":best,
      "dev_per_stage_case_decisions":cases
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print("DACK_V46_RANDOM_PHYSICAL_STAGE01_DEV_AND_NO_CONTINUATION_LEAKAGE_PASS",
          json.dumps({"preferred":best,"dev":tests},sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--folder",required=True)
    p.add_argument("--out",default="benchmark_results/v46_first_two_sevens_random_dev_N64.json")
    p.add_argument("--model",default="models/v46_early_Q2_residual_RESEARCH.json")
    z=p.parse_args();run(z.folder,z.out,z.model)
