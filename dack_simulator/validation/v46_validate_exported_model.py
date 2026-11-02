#!/usr/bin/env python3
"""Independent numerical replay parity of v46 exported pure-Python forest.

Refit deterministic sklearn model on archived train-only physical source,
compare exported tree paths/scores for 32 source states. Verify frozen v43
unchanged at all non-seven-card London stages; no prospective test accessed.
"""
import glob,json,hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from dack_simulator.validation import v46_train_early_seven_Q2 as trainer
import dack_paired_counterfactual_v46_early_seven_Q2_20261101 as runtime
import dack_mulligan_teacher_features_v13_20261031 as features

def run():
    root=Path(__file__).resolve().parents[2]
    path=root/"models/v46_first_two_sevens_Q2_residual_RESEARCH.json"
    report=root/"benchmark_results/v46_first_two_sevens_160k_dev_N64.json"
    saved=json.loads(path.read_text())
    existing=json.loads(report.read_text())
    assert saved["status"]=="EXPERIMENTAL_UNAPPROVED" and saved["policy_approved"] is False
    assert existing["status"]=="PASS" and existing["predeclared_directional_dev_gate_passed"]
    assert hashlib.sha256(path.read_bytes()).hexdigest()==existing["model_sha256"]
    assert saved["feature_hash"]==features.feature_hash()
    assert saved["model_input_n"]==len(saved["feature_names"])
    data,shards=trainer.read_k(str(root/"benchmark_results/v46_first_two_sevens_160k_physical_shards/v46_K_*.json.gz"))
    train=[data[(gid,stage)] for gid in range(160000,160128) for stage in (0,1)]
    fit=trainer.fit(train)
    rt=runtime.audit()
    assert rt["status"]=="PASS" and rt["policy_approved"] is False
    for gid in range(160000,160016):
        for stage in (0,1):
            r=data[(gid,stage)]
            x=trainer.feats(r)
            q=float(r["v43_raw_Q2"])
            expected=trainer.corrected(fit,x,q)
            actual=runtime.calibrated_q(saved,x,q)
            assert abs(expected-actual)<1e-7,("sklearn versus exported tree disagreement",gid,stage,expected,actual)
    print("DACK_V46_EXPORTED_STUDENT_SKLEARN_PARITY_PASS",32,flush=True)

if __name__=="__main__":run()
