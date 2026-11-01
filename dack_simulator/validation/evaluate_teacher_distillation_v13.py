"""Independent off-policy London teacher imitation on never-trained stage groups."""
from __future__ import annotations
import argparse,gzip,json,hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from dack_simulator.validation.train_teacher_distillation_v13 import read,evaluate

def main(files,model_path,output):
    rows,groups,sha=read(files,"imitation_test")
    assert groups and all(62000<=g<63000 for g in groups)
    m=json.loads(Path(model_path).read_text())
    assert m["source_manifest_sha256"]==sha
    assert m["deployed_policy_approved"] is False
    scores=evaluate(rows,m)
    report={"schema":"dack_v13_independent_teacher_imitator",
            "status":"PASS","independent_games":len(groups),
            "no_overlap_with_training":True,
            "model_sha256":hashlib.sha256(Path(model_path).read_bytes()).hexdigest(),
            "metrics":{k:v for k,v in scores.items() if k!="per_stage_results"},
            "examples":scores["per_stage_results"],
            "warning":"Teacher agreement is not full-game performance."}
    p=Path(output);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(report,indent=2)+"\n")
    print("TEACHER_V13_INDEPENDENT_IMITATION_PASS",json.dumps(report["metrics"]),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--labels",nargs="+",required=True)
    p.add_argument("--model",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    main(a.labels,a.model,a.out)
