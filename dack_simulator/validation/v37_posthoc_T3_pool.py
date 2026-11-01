#!/usr/bin/env python3
"""v37 POSTHOC descriptive physically measured 24 T3-blocked tradeoffs.

Selection happened after 127k model predictions were inspected:
DO NOT present as independent population policy validation.
24 original v27 KEEP states have physical forced KEEP, 32 new
unknown92 futures each. Each of nine shared seat-stage full99
forced-MULL continuation cells has 128 independent futures.
Compare benefit from choosing MULL instead, by cumulative T1/T2/T3,
and weighted alternative T2+0.5*T3 cumulative versus
PbyT2+0.5*PexactT3. Bootstrap by independent physical group,
within-hand futures, and one shared C lottery per cell.
"""
from __future__ import annotations
import argparse,gzip,glob,hashlib,json,random
from collections import defaultdict
from pathlib import Path
MAN=Path("datasets/v37_POSTHOC_T3_blocked_physical_diagnostic_manifest.json")
NKEEP=32;NC=128

def y(t,turn):return int(0<int(turn)<=t)
def load(K,C):
    raw=MAN.read_bytes();m=json.loads(raw)
    assert m["schema"]=="dack_v37_posthoc_127k_T3_only_blocked_action_census_exploratory"
    assert m["status"]=="PASS" and m["number_T2_gate_passed_T3_only_blocked"]==24
    initial={(r["game_id"],r["stage"]):r for r in m["blocked_visible_actions"]}
    assert len(initial)==24
    kfiles=sorted(glob.glob(K));cfiles=sorted(glob.glob(C))
    assert len(kfiles)==8 and len(cfiles)==12
    observed={}
    for p in kfiles:
        with gzip.open(p,"rt") as f:d=json.load(f)
        assert d["schema"]=="dack_v37_posthoc_T3blocked_127k_TRUE_KEEP_1"
        assert d["status"]=="PASS" and d["physical_beam160"]
        assert d["clearly_posthoc_exploratory_not_independent_validation"]
        assert d["source_manifest_sha256"]==hashlib.sha256(raw).hexdigest()
        for z in d["rows"]:
            key=(z["game_id"],z["stage"])
            assert key in initial and key not in observed
            assert z["seat"]==initial[key]["seat"]
            assert z["source_manifest_selected_index"]%8==d["shard"]
            t=z["true_KEEP_turns"];assert len(t)==NKEEP and all(x in (0,1,2,3) for x in t)
            observed[key]=t
    assert set(observed)==set(initial)
    cvals={}
    needed=set((r["seat"],r["stage"]) for r in initial.values())
    for p in cfiles:
        with gzip.open(p,"rt") as f:d=json.load(f)
        assert d["schema"]=="dack_v37_posthoc_T3blocked_127k_TRUE_QMULL_1"
        assert d["status"]=="PASS" and d["strict_beam160"]
        assert d["source_manifest_sha256"]==hashlib.sha256(raw).hexdigest()
        assert d["future_full99_reshuffles_return_rejected_seven"]
        cell=(d["seat"],d["stage"])
        assert cell not in cvals
        assert d["required_for_blocked_actions"]==(cell in needed)
        t=d["turns"];assert len(t)==(NC if cell in needed else 0)
        cvals[cell]=t
    assert set(cvals)==set((seat,stage) for seat in range(4) for stage in range(3))
    return m,initial,observed,cvals

def contrast(m,initial,keep,C):
    cmean={cell:{t:sum(y(t,z) for z in vals)/len(vals) for t in (1,2,3)}
           for cell,vals in C.items() if vals}
    rows=[]
    for key,r in initial.items():
        kval={t:sum(y(t,z) for z in keep[key])/NKEEP for t in (1,2,3)}
        ci=cmean[(r["seat"],r["stage"])]
        gains={t:ci[t]-kval[t] for t in (1,2,3)}
        rows.append({
          "gid":r["game_id"],"seat":r["seat"],"stage":r["stage"],
          "T1_MULL_minus_KEEP":gains[1],
          "T2_MULL_minus_KEEP":gains[2],
          "T3_MULL_minus_KEEP":gains[3],
          "utility_PbyT2_plus_half_PexactT3_MULL_minus_KEEP":.5*(gains[2]+gains[3]),
          "utility_PbyT2_plus_half_PbyT3_MULL_minus_KEEP":gains[2]+.5*gains[3],
          "model_pred_MULL_minus_KEEP_T2":-r["v37_pred_T2_median"],
          "model_pred_MULL_minus_KEEP_T3":-r["v37_pred_T3_median"],
        })
    return rows

def summary(rows,key):
    data=[x[key] for x in rows]
    return {"n_selected_action_states":len(data),"mean_gain_pp":100*sum(data)/len(data),
            "positive_gain":sum(x>0 for x in data),"negative_gain":sum(x<0 for x in data)}

def bootstrap(initial,keep,C,t,rep=5000):
    bygid=defaultdict(list)
    for key,r in initial.items():bygid[r["game_id"]].append((key,r))
    gids=sorted(bygid);rng=random.Random(371240+t)
    out=[]
    for i in range(rep):
        means={}
        for cell,arr in C.items():
            if arr:
                means[cell]=sum(y(t,arr[rng.randrange(NC)]) for _ in range(NC))/NC
        total=0.;denom=0
        for j in gids:
            gid=gids[rng.randrange(len(gids))]
            for key,r in bygid[gid]:
                a=keep[key];q=sum(y(t,a[rng.randrange(NKEEP)]) for _ in range(NKEEP))/NKEEP
                total+=means[(r["seat"],r["stage"])]-q;denom+=1
        assert denom>0
        out.append(100*total/denom)
    out.sort()
    return [out[int(.025*rep)],out[int(.975*rep)-1]]

def bootstrap_utility(initial,keep,C,profile,rep=5000):
    """Jointly resample physical T2/T3 outcomes; never combine marginal CI endpoints."""
    assert profile in ("cumulative_T3","exact_T3")
    def reward(turn):
        p2=y(2,turn);p3=y(3,turn)
        return p2+.5*p3 if profile=="cumulative_T3" else .5*(p2+p3)
    bygid=defaultdict(list)
    for key,r in initial.items():bygid[r["game_id"]].append((key,r))
    gids=sorted(bygid)
    rng=random.Random(371350 if profile=="cumulative_T3" else 371351)
    vals=[]
    for i in range(rep):
        means={}
        for cell,arr in C.items():
            if arr:
                means[cell]=sum(reward(arr[rng.randrange(NC)]) for _ in range(NC))/NC
        total=0.;denom=0
        for _ in gids:
            gid=gids[rng.randrange(len(gids))]
            for key,r in bygid[gid]:
                a=keep[key]
                q=sum(reward(a[rng.randrange(NKEEP)]) for _ in range(NKEEP))/NKEEP
                total+=means[(r["seat"],r["stage"])]-q
                denom+=1
        vals.append(100*total/denom)
    vals.sort()
    return [vals[int(.025*rep)],vals[int(.975*rep)-1]]

def main(K,C,out):
    assert y(1,0)==0 and y(1,1)==1 and y(1,2)==0 and y(2,2)==1 and y(3,3)==1
    assert all(y(1,turn)<=y(2,turn)<=y(3,turn) for turn in (0,1,2,3))
    m,initial,keep,cont=load(K,C)
    rows=contrast(m,initial,keep,cont)
    s={}
    for t in (1,2,3):
        k=f"T{t}_MULL_minus_KEEP"
        s[k]=summary(rows,k)
        s[k]["physical_outer_game_and_C_95ci_pp"]=bootstrap(initial,keep,cont,t)
    for k in ("utility_PbyT2_plus_half_PexactT3_MULL_minus_KEEP",
              "utility_PbyT2_plus_half_PbyT3_MULL_minus_KEEP",
              "model_pred_MULL_minus_KEEP_T2","model_pred_MULL_minus_KEEP_T3"):
        s[k]=summary(rows,k)
    s["utility_PbyT2_plus_half_PexactT3_MULL_minus_KEEP"][
        "joint_physical_outer_group_and_C_95ci_pp"]=bootstrap_utility(
           initial,keep,cont,"exact_T3")
    s["utility_PbyT2_plus_half_PbyT3_MULL_minus_KEEP"][
        "joint_physical_outer_group_and_C_95ci_pp"]=bootstrap_utility(
           initial,keep,cont,"cumulative_T3")
    report={
      "schema":"dack_v37_POSTHOC_T3_blocked_true_physical_tradeoff_1",
      "status":"PASS","policy_approved":False,
      "POSTHOC_selected_after_127k_model_inspection":True,
      "NOT_independent_validation":True,
      "NOT_population_average_gain":True,
      "n_T3blocked_early_stage_states":len(rows),
      "n_independent_game_ids":len(set(r["gid"] for r in rows)),
      "new_KEEP_actual_beam160_physical_futures":len(rows)*NKEEP,
      "new_FULL99_C_actual_beam160_futures":sum(len(v) for v in cont.values()),
      "blocked_selection_manifest_sha256":hashlib.sha256(MAN.read_bytes()).hexdigest(),
      "physical_real_action_contrasts":s,
      "state_details":rows,
      "qualifiers":[
        "This is a same-frozen-v27-future one-step contrast, NOT full-policy winning rate",
        "Only 24 model-selected T2-vs-T3 conflicts, not random unselected hands",
        "127k data already inspected, do not use for threshold/model selection then claim heldout",
        "T3 exact objective and cumulative T3 objective differ mathematically",
        "New holdout needed for any future T2-only or utility-weighted policy"]
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V37_POSTHOC_TRUE_PHYSICAL_T2_T3_TRADEOFF_PASS",
          json.dumps(s,sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--K",default="collected/v37_blocked_K_*.json.gz")
    p.add_argument("--C",default="collected/v37_blocked_C_*.json.gz")
    p.add_argument("--out",default="benchmark_results/v37_posthoc_T3_blocked_physical_tradeoff.json")
    a=p.parse_args();main(a.K,a.C,a.out)
