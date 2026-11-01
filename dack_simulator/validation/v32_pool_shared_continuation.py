#!/usr/bin/env python3
"""Pool 28 independent v32 physical continuation cells.

Each cell: 96 new training trials + 32 *separate* validation trials,
all from frozen v27 after forcing one London mulligan. No current seven
is involved. Validation is diagnostic only; do not tune alpha on it.
Predeclared mild shrinkage alpha=.75 to real observed rate, .25 old DP.
"""
from __future__ import annotations
import glob,hashlib,json,math
from pathlib import Path

ALPHA=.75
OLD="models/dack_v27_T2_only_continuations_EXPERIMENTAL.json"
MODEL="models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json"
STUDENT="models/v14_curve/v14_teacher_groups_128.json"

def filehash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    paths=sorted(glob.glob("collected/v32_c_*.json"))
    assert len(paths)==28,(len(paths),paths)
    old=json.loads(Path(OLD).read_text())
    assert old["schema"]=="dack_v22_all_stage_london_continuation_dp"
    cells={}
    diagnostics=[]
    for file in paths:
        x=json.loads(Path(file).read_text())
        assert x["schema"]=="dack_v32_shared_mull_continuation_frozen_v27"
        assert x["status"]=="PASS" and x["model_approved"] is False
        assert x["train_count"]==96 and x["validation_count"]==32
        assert x["initial_seven_independent"] and x["all_99_returned_on_mull"]
        assert x["policy_after_mull"]=="frozen_v27_all_eight_stages_v14_bottom"
        assert x["actual_beam"]==160
        k=(int(x["seat"]),int(x["stage"]))
        assert k not in cells and 0<=k[0]<4 and 0<=k[1]<7
        cells[k]=x
    assert len(cells)==28
    tab={}
    for seat in range(4):
        prior=list(old["seat_continuations"][str(seat)]["thresholds_by_london_stage"])
        assert len(prior)==8 and prior[7]==-1
        t=[]
        for stage in range(7):
            d=cells[(seat,stage)]
            tr=[int(0<r["turn"]<=2) for r in d["results"] if r["split"]=="train"]
            va=[int(0<r["turn"]<=2) for r in d["results"] if r["split"]=="validation"]
            assert len(tr)==96 and len(va)==32
            raw=sum(tr)/96.
            c=ALPHA*raw+(1-ALPHA)*float(prior[stage])
            assert 0<=c<=1.
            t.append(c)
            info={
                "seat":seat,"stage":stage,
                "train_96_real_Qmull_T2":raw,
                "validation_32_real_Qmull_T2":sum(va)/32.,
                "old_v27_predicted_continuation":float(prior[stage]),
                "v32_shrunk_continuation":c,
                "train_96_T2_successes":sum(tr),
                "validation_32_T2_successes":sum(va),
                "standard_error_train_binomial":math.sqrt(raw*(1-raw)/96.),
                "old_validation_squared_error_sum":sum((y-prior[stage])**2 for y in va),
                "new_validation_squared_error_sum":sum((y-c)**2 for y in va),
                "raw_validation_squared_error_sum":sum((y-raw)**2 for y in va),
                "total_train_n":96,"total_validation_n":32,
            }
            diagnostics.append(info)
        t.append(-1.)
        tab[str(seat)]={
          "samples_per_london_cell":96,
          "independent_validation_per_cell":32,
          "thresholds_by_london_stage":t,
          "old_v27_thresholds_by_london_stage":prior
        }
    n=32*28
    brier={what:sum(x[what+"_validation_squared_error_sum"] for x in diagnostics)/n
        for what in ("old","new","raw")}
    model={
        "schema":"dack_v32_physical_Qmull_shared_continuation_UNAPPROVED",
        "status":"PASS",
        "model_approved":False,
        "frozen_v27_downstream_policy":True,
        "frozen_v14_bottom_policy":True,
        "keep_estimator_unchanged_v27_93k_all_eight_stages":True,
        "fixed_predeclared_real_weight":ALPHA,
        "train_108k_independent_downstream_goldfish_futures":96*28,
        "validation_108k_independent_downstream_goldfish_futures":32*28,
        "actual_gameplay_beam":160,
        "source_v27_model_file_sha256":filehash(MODEL),
        "source_v27_dp_file_sha256":filehash(OLD),
        "source_v14_bottom_file_sha256":filehash(STUDENT),
        "seat_continuations":tab,
        "validation_Brier_T2":brier,
        "continuation_independent_of_rejected_seven":True,
        "no_sampling_at_inference":True,
        "validation_not_used_to_choose_shrinkage":True,
        "warning":"Separate 96-trial cell estimates have residual ~3-5pp standard error. Comparisons on 32 validation futures per cell are noisy. A static shared table is exact in conditioning, not in finite-sample value. Future policy changes invalidate this table.",
    }
    report={
        "schema":"dack_v32_shared_continuation_108k_calibration_report",
        "status":"PASS","brier_validation":brier,
        "total_training_futures":96*28,
        "total_validation_futures":32*28,
        "cell_details":diagnostics,
        "model_approved":False,
        "predeclared_alpha":ALPHA,
    }
    a=Path("models/dack_v32_shared_Qmull_continuation_EXPERIMENTAL.json")
    a.parent.mkdir(parents=True,exist_ok=True)
    a.write_text(json.dumps(model,indent=2,sort_keys=True)+"\n")
    b=Path("benchmark_results/v32_shared_continuation_108k_diagnostic.json")
    b.parent.mkdir(parents=True,exist_ok=True)
    b.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("DACK_V32_SHARED_CONTINUATION_POOL_PASS",
          json.dumps({"train":96*28,"validation":32*28,
                      "brier":brier,"thresholds":{
                        s:t["thresholds_by_london_stage"] for s,t in tab.items()}
            },sort_keys=True),flush=True)

if __name__=="__main__":main()
