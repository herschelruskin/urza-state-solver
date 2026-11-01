#!/usr/bin/env python3
"""v46 group-disjoint physical KEEP calibration and first/second seven-card
development test. NO v5 teacher. Full-game efficacy NOT claimed.

Train 128 new independent deals, two potential seven stages per deal,
16 real blind K futures per state. Frozen v43 continuation empirical C128
per seat+stage. Independent dev = 64 outer 156k groups; they never enter fit.
All samples at a seat/stage share one finite C128 lottery (two-source CI).
"""
from __future__ import annotations
import argparse,gzip,glob,hashlib,json,random,sys
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from sklearn.ensemble import RandomForestRegressor
import dack_mulligan_v46_seven_physical_calibration as runtime
import dack_mulligan_teacher_features_v13_20261031 as feat
import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as v43

SCHEMA="dack_v46_n128_train_n64_dev_first_two_sevens_physical_value_v1"
KSCHEMA="dack_v46_first_two_sevens_new_physical_K16_v1"
CSCHEMA="dack_v46_first_two_sevens_shared_full99_C128_v1"
TREES=80
MINLEAF=12
MAXDEPTH=5
BLEND=runtime.BLEND
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def by(t,h):return int(0<int(t)<=h)

def sources(root):
    ks=sorted(glob.glob(str(Path(root)/"v46_K_*.json.gz")))
    cs=sorted(glob.glob(str(Path(root)/"v46_C_*.json.gz")))
    assert len(ks)==12 and len(cs)==8,(len(ks),len(cs))
    groups={};hashes=[]
    for p in ks:
        with gzip.open(p,"rt") as f:d=json.load(f)
        assert d["schema"]==KSCHEMA and d["status"]=="PASS"
        assert d["independent_outer_physical_deals"]==16
        assert d["two_stages_per_deal"]==[0,1]
        assert d["K_futures_per_state"]==16
        assert d["strict_99_real_cards_actual_beam160"]
        assert d["frozen_v43_24_deal_continuation_parity_passed"]
        assert d["no_bottoms_for_either_seven_card_stage"]
        assert d["physical_shuffles_and_chance_independent_of_model_scores"]
        assert d["source_v27_model_sha256"]==digest(ROOT/"models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json")
        hashes.append([Path(p).name,digest(p)])
        for r in d["rows"]:
            key=(r["gid"],r["stage"])
            assert key not in groups and r["stage"] in (0,1) and r["no_bottom_cards"]
            assert len(r["turns"])==16 and len(r["seven"])==7
            assert all(t in (0,1,2,3) for t in r["turns"])
            assert d["split"]==("train" if r["gid"]<=156127 else "dev")
            groups[key]=r
    assert set(groups)=={(g,s) for g in range(156000,156192) for s in (0,1)}
    csamples={}
    for p in cs:
        with gzip.open(p,"rt") as f:d=json.load(f)
        assert d["schema"]==CSCHEMA and d["status"]=="PASS"
        assert d["full99_returned_at_every_later_stage"]
        assert d["exact_frozen_v43_downstream_replay_parity"]
        assert d["shared_C_across_train_and_dev_uncertainty_not_independent"]
        assert d["C_independent_full99_futures"]==128
        cell=(d["seat"],d["stage"]);assert cell not in csamples
        csamples[cell]=d["turns"]
        assert len(csamples[cell])==128
        hashes.append([Path(p).name,digest(p)])
    assert set(csamples)=={(seat,stage) for seat in range(4) for stage in (0,1)}
    assert len({g for g,s in groups})==192
    return groups,csamples,hashes

def represent(r):
    from collections import Counter
    deck=Counter(v43.ref.SLOT_VARIANTS["one_key_34"].values())
    seven=tuple(r["seven"])
    unk=deck-Counter(seven)
    assert sum(unk.values())==92
    x=runtime.features(seven,unk,r["seat"],r["stage"],
       r["v43_pred_Q2"],r["v43_DP"])
    assert len(x)==len(runtime.NAMES)
    return x

def tree_export(model):
    result=[]
    for e in model.estimators_:
        t=e.tree_
        result.append({
          "left":[int(i) for i in t.children_left],
          "right":[int(i) for i in t.children_right],
          "feature":[int(i) for i in t.feature],
          "threshold":[float(x) for x in t.threshold],
          "value":[float(v[0][0]) for v in t.value],
        })
    assert len(result)==TREES
    return result

def train_model(groups,C,hashes):
    training=[groups[(gid,stage)] for gid in range(156000,156128) for stage in (0,1)]
    X=np.asarray([represent(r) for r in training],dtype=np.float32)
    W=np.asarray([.5]*len(training),dtype=float)
    assert X.shape==(256,len(runtime.NAMES)) and W.sum()==128
    model={
      "schema":runtime.SCHEMA,"policy_approved":False,
      "source_feature_sha256":feat.feature_hash(),
      "source_v27_model_sha256":digest(ROOT/"models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json"),
      "feature_names":list(runtime.NAMES),
      "train_independent_groups":128,"train_stage_states":256,
      "dev_independent_groups":64,"K_independent_futures_per_stage":16,
      "C_shared_futures_per_seat_stage":128,
      "source_shards":hashes,
      "training_used_original_v5_labels":False,
      "physical_outcomes_not_new_full_game_winrates":True,
      "blend":runtime.BLEND,"deadband":runtime.DEADBAND,
      "t3_harm_cap":runtime.T3_LOSS_CAP,
      "downstream_policy":"exact frozen v43 candidate max Q2, not learned new stage1 policy",
      "heads":{},"shared_C":{},
    }
    skl={}
    for h in (2,3):
        target=np.asarray([sum(by(t,h) for t in r["turns"])/16 for r in training])
        rf=RandomForestRegressor(n_estimators=TREES,max_depth=MAXDEPTH,
           min_samples_leaf=MINLEAF,min_samples_split=2*MINLEAF,
           max_features=0.8,random_state=4600+h,n_jobs=1)
        rf.fit(X,target,sample_weight=W)
        model["heads"][f"T{h}"]=tree_export(rf)
        skl[h]=rf
    for seat in range(4):
        model["shared_C"][str(seat)]={}
        for stage in (0,1):
            turns=C[(seat,stage)]
            model["shared_C"][str(seat)][str(stage)]={
                "T1":sum(by(t,1) for t in turns)/128,
                "T2":sum(by(t,2) for t in turns)/128,
                "T3":sum(by(t,3) for t in turns)/128,
            }
    # Exact sklearn-JSON scorer parity: 100 randomly selected training rows.
    for ii in random.Random(46).sample(range(len(training)),100):
        x=X[ii]
        for h in (2,3):
            ref=float(skl[h].predict(x.reshape(1,-1))[0])
            got=runtime.head(model,f"T{h}",list(x))
            assert abs(ref-got)<1e-9,(h,ref,got)
    return model

def evaluate(groups,C,model):
    dev=[groups[(gid,stage)] for gid in range(156128,156192) for stage in (0,1)]
    changes=[]
    for r in dev:
        x=represent(r)
        proposed,p2,p3=runtime.decide(model,x,r["seat"],r["stage"],r["v43_early_KEEP"])
        old=bool(r["v43_early_KEEP"])
        cell=(r["seat"],r["stage"])
        assert proposed in (True,False)
        entry={
          "gid":r["gid"],"seat":r["seat"],"stage":r["stage"],
          "old_v43_keep":old,"v46_keep":proposed,
          "v43_Q2":r["v43_pred_Q2"],"v43_DP":r["v43_DP"],
          "v46_K2":p2,"v46_K3":p3,"C2":model["shared_C"][str(r["seat"])][str(r["stage"])]["T2"],
          "C3":model["shared_C"][str(r["seat"])][str(r["stage"])]["T3"],
          "physical_K_turns":r["turns"],
        }
        changes.append(entry)
    assert len(changes)==128 and len(set(z["gid"] for z in changes))==64
    def summary(xs):
        if not xs:return None
        n=len(xs);changed=[z for z in xs if z["old_v43_keep"]!=z["v46_keep"]]
        out={"stage_states":n,"independent_outer_groups":len({z["gid"] for z in xs}),
             "changed_actions":len(changed),
             "keep_to_mull":sum(z["old_v43_keep"] and not z["v46_keep"] for z in xs),
             "mull_to_keep":sum(not z["old_v43_keep"] and z["v46_keep"] for z in xs)}
        for h in (1,2,3):
            summ=0.
            for z in xs:
                sign=int(z["v46_keep"])-int(z["old_v43_keep"])
                k=sum(by(t,h) for t in z["physical_K_turns"])/16
                c=sum(by(t,h) for t in C[(z["seat"],z["stage"])])/128
                summ+=sign*(k-c)
            out[f"T{h}_conditional_action_gain_pp"]=100*summ/n
        return out
    totals=summary(changes)
    bystage={str(s):summary([z for z in changes if z["stage"]==s]) for s in (0,1)}
    rng=random.Random(460064)
    B=2500
    gp=defaultdict(list)
    for z in changes:gp[z["gid"]].append(z)
    assert len(gp)==64 and all(len(v)==2 for v in gp.values())
    ids=sorted(gp)
    boots={h:[] for h in (1,2,3)}
    for b in range(B):
        Cvals={}
        for cell,turns in C.items():
            drawn=[turns[rng.randrange(128)] for i in range(128)]
            Cvals[cell]={h:sum(by(t,h) for t in drawn)/128 for h in (1,2,3)}
        vals={h:0. for h in (1,2,3)}
        for _ in range(64):
            for z in gp[ids[rng.randrange(64)]]:
                delta=int(z["v46_keep"])-int(z["old_v43_keep"])
                if delta==0:continue
                sampled=[z["physical_K_turns"][rng.randrange(16)] for i in range(16)]
                for h in (1,2,3):
                    vals[h]+=delta*(sum(by(t,h) for t in sampled)/16-Cvals[(z["seat"],z["stage"])][h])
        for h in (1,2,3):boots[h].append(100*vals[h]/128)
    ci={}
    for h in (1,2,3):
        ordered=sorted(boots[h])
        ci[f"T{h}"]=[ordered[62],ordered[2436]]
    passed=(totals["changed_actions"]>=5 and
            totals["T2_conditional_action_gain_pp"]>0 and
            totals["T3_conditional_action_gain_pp"]>=-2.0)
    return {
      "status":"PASS","N_random_dev_groups":64,"N_potential_stage_states":128,
      "dev_source_groups_never_fit":True,
      "shared_C_is_only_one_finite_lottery_per_cell":True,
      "stage1_hypothetical_until_actually_reached":True,
      "dev_is_conditional_action_value_NOT_full_game":True,
      "no_model_tuning_or_threshold_search_on_dev":True,
      "dev_pass_full_game_gate":bool(passed),
      "dev_gate_min_changed_actions":5,
      "dev_gate_T2_gain_positive":True,
      "dev_gate_T3_minimum_pp":-2.,
      "totals":totals,"by_stage":bystage,
      "hierarchical_group_K_and_shared_C_bootstrap_95ci_pp":ci,
      "per_state_research_diagnostics":changes,
    }

def run(out_model,out_report,source_dir):
    groups,C,hashes=sources(source_dir)
    model=train_model(groups,C,hashes)
    mp=Path(out_model);mp.parent.mkdir(parents=True,exist_ok=True)
    mp.write_text(json.dumps(model,sort_keys=True,separators=(",",":"))+"\n")
    reloaded=runtime.load(mp)
    dev=evaluate(groups,C,reloaded)
    report={
      "schema":SCHEMA,"status":"PASS","source_groups_train":128,"source_groups_dev":64,
      "physical_K_total_futures":6144,"shared_C_total_futures":1024,
      "model_approved":False,
      "source_156k_dev_predeclared_and_not_used_in_fit":True,
      "original_v5_teacher_not_used":True,
      "model_sha256":digest(mp),
      "dev":dev,
    }
    rp=Path(out_report);rp.parent.mkdir(parents=True,exist_ok=True)
    rp.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V46_REAL_SEVEN_CARD_PHYSICAL_TRAIN_DEV_PASS",
         json.dumps({"model_sha256":digest(mp),"dev":{k:v for k,v in dev.items() if k!="per_state_research_diagnostics"}},sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--sources",default="benchmark_results/v46_new_156k_KC_physical_shards")
    p.add_argument("--model",default="models/v46_real_first_two_sevens_RESEARCH.json")
    p.add_argument("--report",default="benchmark_results/v46_156k_two_sevens_physical_train_dev.json")
    a=p.parse_args();run(a.model,a.report,a.sources)
