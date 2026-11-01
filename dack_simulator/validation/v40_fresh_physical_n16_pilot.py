#!/usr/bin/env python3
"""Frozen v40 real-v5 students vs original v5 and v27. Fresh physical pilot.

All policies in separate Python interpreters because rules/model modules are
process-global. Same real 99-card seed, seat, stage shuffles, strict beam160.
N16 is a correctness and directional pilot, NOT a power-calibrated comparison.
"""
from __future__ import annotations
import argparse,gzip,json,subprocess,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
START,STOP=147000,147016
POLICIES=("v5","v27","v40_full","v40_portable")
CHILD=(
 "import sys,json,time\n"
 "p=sys.argv[1];gid=int(sys.argv[2])\n"
 "if p=='v5':\n"
 " import dack_paired_counterfactual_v5_stable_chance_20261031 as m\n"
 " m.audit();ref=m.reference\n"
 "elif p=='v27':\n"
 " import dack_paired_counterfactual_v27_T2_only_DP_20261101 as m\n"
 " m.audit();ref=m.ref\n"
 "else:\n"
 " import dack_paired_counterfactual_v40_true_v5_student_20261101 as m\n"
 " m.audit(p.replace('v40_',''));ref=m.ref\n"
 "t=time.perf_counter();r=ref.game('one_key_34',gid)\n"
 "print('V40_PROSPECTIVE_PHYSICAL_GAME',json.dumps({'turn':r['win_turn'],"
 "'keep_n':r['keep_n'],'seat':r['seat'],'history':r['history'],"
 "'seconds':round(time.perf_counter()-t,4)}))\n"
)

def one(gid,policy):
    p=subprocess.run([sys.executable,"-c",CHILD,policy,str(gid)],
      cwd=ROOT,text=True,capture_output=True,timeout=1500)
    if p.returncode:
        raise RuntimeError(("child failure",gid,policy,p.stdout[-1200:],p.stderr[-1300:]))
    lines=[s[len("V40_PROSPECTIVE_PHYSICAL_GAME "):] for s in p.stdout.splitlines()
           if s.startswith("V40_PROSPECTIVE_PHYSICAL_GAME ")]
    assert len(lines)==1
    return json.loads(lines[0])

def run(start,out):
    if start not in (147000,147004,147008,147012):
        raise ValueError("exact predeclared four N4 shards only")
    rows=[]
    for gid in range(start,start+4):
        row={"game_id":gid}
        for pol in POLICIES:
            row[pol]=one(gid,pol)
        assert len({row[p]["seat"] for p in POLICIES})==1
        assert len({tuple(row[p]["history"][0]["seven_slots"]) for p in POLICIES})==1
        assert all(row[p]["turn"] in (0,1,2,3) for p in POLICIES)
        rows.append(row)
        print("DACK_V40_PROSPECTIVE_PAIRED_GAME",gid,
              {p:row[p]["turn"] for p in POLICIES},flush=True)
    source={}
    for mode in ("full","portable"):
        path=ROOT/f"models/v40_true_v5_archived/v40_archived_actual_v5_{mode}_1288_RESEARCH.json"
        source[mode]=hashlib.sha256(path.read_bytes()).hexdigest()
    report={
        "schema":"dack_v40_paired_strict_beam160_physical_pilot_v1",
        "status":"PASS","source_model_sha256":source,
        "game_ids":[start,start+3],"independent_physical_groups":4,
        "no_training_or_threshold_tuning_on_147k":True,
        "same_physical_99_slot_first_seven_and_seat":True,
        "goldfish_beam":160,"policies":POLICIES,
        "not_multiplayer_winrate":True,"pilot_only_not_approval":True,"rows":rows}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(report,f,sort_keys=True)
    print("DACK_V40_PROSPECTIVE_N4_PASS",start,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args();run(args.start,args.out)
