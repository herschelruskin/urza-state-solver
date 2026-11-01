#!/usr/bin/env python3
"""v42 read-only causal-mechanism census of ORIGINAL v5 vs frozen v27.

No gameplay, no v5 lookahead, no fitting. Uses identical 115k physical
seven/seat at first naturally reached KEEP/MULL disagreement and the existing
v34c physical forced-action outcomes. Distinguishes:
  A. v5 would keep under frozen native threshold, but assertive +bump rejects
  B. v5 already would reject under native threshold (different value estimates)
  C. v5 keeps and v27 rejects (bump cannot cause this direction)
All physical rates are retrospective and conditional, not population WR.
"""
from __future__ import annotations
import gzip,glob,json,sys,math
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v5_stable_chance_20261031 as teacher
from dack_simulator.validation import v34c_pool_actual_disagreement as physical

ref=teacher.reference
BUMP={7:.200,6:.120,5:.055,4:.015}
SCHEMA="dack_v42_v5_structural_threshold_and_reality_diagnostic_v1"

def by(t,turn):return int(0<int(t)<=turn)

def read_115k():
    files=sorted(glob.glob(str(ROOT/"benchmark_results/v33b_prospective_115k_shards/v33b_115k_*.json.gz")))
    assert len(files)==64
    rows=[]
    for p in files:
        with gzip.open(p,"rt") as f:d=json.load(f)
        assert d["status"]=="PASS"
        assert d["schema"]=="dack_v33b_prospective_115k_three_policy_strict"
        assert d["v27_v33b_identical_london_stages_and_keep_actions"]
        rows+=d["rows"]
    rows.sort(key=lambda r:r["game_id"])
    assert [int(r["game_id"]) for r in rows]==list(range(115000,115256))
    return rows

def do(out):
    rows=read_115k()
    selected,cs,sha=physical.load(
      str(ROOT/"benchmark_results/v34c_forced_keep_shards/v34c_keep_*.json.gz"),
      str(ROOT/"benchmark_results/v34_consistent_regret_shards/v34_C_*.json.gz"))
    ph={int(r["game_id"]):r for r in selected}
    assert len(ph)==100
    assert tuple(ref.sim.STAGES)==(7,7,6,5,4,3,2,1)
    assert BUMP==ref.sim.ASSERTIVE_BUMPS
    assert ref.batch.CONFIG["lambda"]==.5
    continuation=tuple(float(ref.batch.FROZEN_CONTINUATION[k-1]) for k in range(2,8))
    summary=Counter()
    categories=defaultdict(lambda:{"N":0,"T2":0.,"T3":0.,"T1":0.,
                                     "teacher_v5_t2_win":0,"student_v27_t2_win":0})
    cases=[]
    bystage=defaultdict(Counter)
    for outer in rows:
        gid=int(outer["game_id"])
        v5=outer["v5"]["history"]
        v27=outer["v27_frozen"]["history"]
        assert v5 and v27 and v5[-1]["kept"] and v27[-1]["kept"]
        assert [q["stage"] for q in v5]==list(range(len(v5)))
        assert [q["stage"] for q in v27]==list(range(len(v27)))
        s5=int(v5[-1]["stage"]);s27=int(v27[-1]["stage"])
        summary["N_outer_games"]+=1
        summary["same_actual_keep_stage"]+=int(s5==s27)
        if s5==s27:
            last5=v5[-1];last27=v27[-1]
            summary["same_stage_different_kept_hand"]+=int(
                Counter(last5["hand"])!=Counter(last27["hand"]))
            summary["same_stage_different_bottom"]+=int(
                tuple(last5["bottom"])!=tuple(last27["bottom"]))
            summary["same_stage_different_ordered_bottom_but_same_cards"]+=int(
                Counter(last5["bottom"])==Counter(last27["bottom"])
                and tuple(last5["bottom"])!=tuple(last27["bottom"]))
            continue
        stage=min(s5,s27)
        assert stage<7 and gid in ph
        a=v5[stage];b=v27[stage]
        assert a["stage"]==b["stage"]==stage
        assert a["seven"]==b["seven"] and a["seven_slots"]==b["seven_slots"]
        assert not any(q["kept"] for q in v5[:stage])
        assert not any(q["kept"] for q in v27[:stage])
        v5_keep=bool(a["kept"]);v27_keep=bool(b["kept"])
        assert v5_keep!=v27_keep
        kn=int(a["keep_n"])
        raw=float(a["raw"]);t1=float(a["sampled_t1"])
        std=(0. if kn==1 else float(ref.batch.FROZEN_CONTINUATION[kn-1]))
        bump=float(BUMP.get(kn,0.))
        native=(kn==1 or raw>=std)
        expected=std+(0. if native and t1>0 else bump)
        assert abs(float(a["threshold"])-expected)<1e-6,(
            "original-v5 threshold replay invalid",gid,stage,a["threshold"],expected)
        assert v5_keep==(kn==1 or raw>=expected)
        if not v5_keep:
            if native:
                reason="v5_assertive_bump_veto"
                assert bump>0 and not t1>0
            else:
                reason="v5_native_keep_value_below_native_C"
        else:
            reason="v5_keep_v27_mull__not_an_assertive_veto"
            assert native
        assert (reason=="v5_keep_v27_mull__not_an_assertive_veto")==v5_keep
        assert int(ph[gid]["stage"])==stage
        assert bool(ph[gid]["v5_first_keeps"])==v5_keep
        assert tuple(ph[gid]["seven"])==tuple(a["seven"])
        assert int(ph[gid]["seat"])==int(outer["v5"]["seat"])
        future=ph[gid]["fresh_keep_futures_by_split"]
        kept=future["calibration"]+future["replication"]
        cont=cs[(int(ph[gid]["seat"]),stage)]["calibration"]+cs[(int(ph[gid]["seat"]),stage)]["replication"]
        assert len(kept)==32 and len(cont)==96
        groupstats={}
        for horizon in (1,2,3):
            diff=sum(by(x,horizon) for x in kept)/len(kept)-sum(by(x,horizon) for x in cont)/len(cont)
            groupstats[f"T{horizon}_signed_v5_advantage"]=(1 if v5_keep else -1)*diff
            categories[reason][f"T{horizon}"]+=groupstats[f"T{horizon}_signed_v5_advantage"]
        categories[reason]["N"]+=1
        bystage[stage][reason]+=1
        summary["different_actual_keep_stage"]+=1
        summary[reason]+=1
        if t1>0:summary["first_disagreement_v5_t1_positive"]+=1
        if raw>=std:summary["first_disagreement_native_would_keep"]+=1
        cases.append({
           "game_id":gid,"seat":ph[gid]["seat"],"stage":stage,"keep_n":kn,
           "v5_keeps":v5_keep,"v27_keeps":v27_keep,"mechanism":reason,
           "v5_raw":raw,"v5_frozen_native_C":std,
           "v5_effective_threshold":expected,
           "v5_raw_minus_native_C":round(raw-std,7),
           "v5_raw_minus_actual_threshold":round(raw-expected,7),
           "v5_sampled_T1":t1,"assertive_bump":bump,
           "v27_pred_Qkeep":b.get("raw",b.get("Qkeep")),
           "v27_threshold":b.get("threshold"),
           "v5_hand":a["hand"],"v27_hand":b["hand"],
           "v5_bottom":a["bottom"],"v27_bottom":b["bottom"],
           **groupstats,
        })
    assert summary["N_outer_games"]==256
    assert summary["different_actual_keep_stage"]==100
    assert summary["same_actual_keep_stage"]==156
    assert set(ph)==set(x["game_id"] for x in cases)
    diag={}
    for label,z in categories.items():
        diag[label]={"N":z["N"],"mean_physical_v5_action_advantage_T1_pp":100*z["T1"]/z["N"],
                     "mean_physical_v5_action_advantage_T2_pp":100*z["T2"]/z["N"],
                     "mean_physical_v5_action_advantage_T3_pp":100*z["T3"]/z["N"]}
    assert sum(z["N"] for z in diag.values())==100
    result={
      "schema":SCHEMA,"status":"PASS",
      "source":"historical 115k original-v5 and v27 identical physical outer slots + original v34c physical KEEP/C",
      "no_new_gameplay_or_lookahead":True,
      "no_new_teacher_model_or_policy":True,
      "historical_selected_sample_NOT_new_validation":True,
      "original_v5_actual_policy_assertive":True,
      "v5_continuation_native_by_keep_n":{str(k):float(ref.batch.FROZEN_CONTINUATION[k-1]) for k in range(2,8)},
      "v5_assertive_bumps_by_keep_n":{str(k):v for k,v in BUMP.items()},
      "v5_internal_CONFIG":{str(k):v for k,v in ref.batch.CONFIG.items()
                            if isinstance(v,(int,float,str,bool))},
      "t3_teacher_utility_weight":float(ref.batch.CONFIG["lambda"]),
      "counts":dict(summary),
      "different_stage_first_stage_mechanisms":diag,
      "first_disagreement_by_stage":{str(s):dict(count) for s,count in sorted(bystage.items())},
      "physical_effect_is_causal_1step_same_v33b_bottom_and_v27_future_NOT_original_v5_game":True,
      "cases":cases,
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("DACK_V42_ORIGINAL_TEACHER_THRESHOLD_CAUSAL_MECHANISM_PASS",
        json.dumps({
         "counts":dict(summary),"mechanisms":diag,
         "stages":result["first_disagreement_by_stage"],
         "original_native_continuations":result["v5_continuation_native_by_keep_n"],
         "v5_config":result["v5_internal_CONFIG"],
        },sort_keys=True),flush=True)

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",default="benchmark_results/v42_original_v5_vs_v27_threshold_mechanism_115k.json")
    a=parser.parse_args();do(a.out)
