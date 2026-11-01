#!/usr/bin/env python3
"""Prospective locked 97k physical-game v5/v22/v26 comparison.

All models and London continuations must be archived BEFORE this runs.
No policy fit, hyperparameter tuning, or v25 96k evaluation reuse.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
POLICIES=("v5","v22_real_keep_DP","v26_expanded_keep_DP")
SCRIPT=(
    "import json,sys,time\n"
    "gid=int(sys.argv[1]);policy=sys.argv[2]\n"
    "if policy=='v5':\n"
    " import dack_paired_counterfactual_v5_stable_chance_20261031 as p\n"
    " p.audit(); runner=p.reference\n"
    "elif policy=='v22_real_keep_DP':\n"
    " import dack_paired_counterfactual_v22_all_stage_real_keep_DP_20261101 as p\n"
    " p.audit(); runner=p.ref\n"
    " assert p.MODEL['deployed_policy_approved'] is False\n"
    "else:\n"
    " import dack_paired_counterfactual_v26_expanded_keep_DP_20261101 as p\n"
    " p.audit(); runner=p.ref\n"
    " assert p.original.MODEL['deployed_policy_approved'] is False\n"
    "st=time.perf_counter();v=runner.game('one_key_34',gid)\n"
    "print('V26_REAL_GAME',json.dumps({'turn':v['win_turn'],"
    "'keep_n':v['keep_n'],'seat':v['seat'],'history':v['history'],"
    "'seconds':round(time.perf_counter()-st,4)}),flush=True)\n"
)

def run_one(gid,policy):
    x=subprocess.run([sys.executable,"-c",SCRIPT,str(gid),policy],
            cwd=ROOT,capture_output=True,text=True,timeout=1500)
    if x.returncode:
        print("V26_GAME_CHILD_FAIL",gid,policy,x.stdout[-1200:],x.stderr[-2000:],flush=True)
        raise RuntimeError("v26 paired reference game failed")
    parts=[z[len("V26_REAL_GAME "):] for z in x.stdout.splitlines() if z.startswith("V26_REAL_GAME ")]
    assert len(parts)==1,(gid,policy,x.stdout[-1500:])
    return json.loads(parts[0])

def main(start,games,out):
    if not 97000<=start or games!=4 or start+games>97256:
        raise ValueError("strict fresh physical 97k four-game shards only")
    files=[
       "models/v14_curve/v14_teacher_groups_128.json",
       "models/dack_v22_real_all_stage_keep_value_EXPERIMENTAL.json",
       "models/dack_v22_all_stage_continuations_EXPERIMENTAL.json",
       "models/dack_v26_expanded_real_keep_value_EXPERIMENTAL.json",
       "models/dack_v26_expanded_all_stage_continuations_EXPERIMENTAL.json"
    ]
    checksums={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
    records=[]
    for gid in range(start,start+games):
        row={"game_id":gid}
        for p in POLICIES:row[p]=run_one(gid,p)
        assert len({row[p]["seat"] for p in POLICIES})==1
        assert len({tuple(row[p]["history"][0]["seven_slots"]) for p in POLICIES})==1
        assert all(row[p]["turn"] in (0,1,2,3) for p in POLICIES)
        records.append(row)
        print("V26_FRESH_PHYSICAL_GAME",gid,{
            p:(row[p]["turn"],row[p]["keep_n"]) for p in POLICIES},flush=True)
    result={
       "schema":"dack_v26_frozen_physical_97k_test",
       "status":"PASS","game_ids":[start,start+games-1],
       "actual_gameplay_beam":160,"mulligan_lookahead_beam_v26":0,
       "same_first_physical_seven_verified":True,
       "v26_unapproved":True,"models_sha256":checksums,
       "rows":records,
    }
    target=Path(out);target.parent.mkdir(exist_ok=True,parents=True)
    with gzip.open(target,"wt") as f:json.dump(result,f,sort_keys=True)
    print("V26_FRESH_PAIRED_SHARD_PASS",start,games,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--games",type=int,default=4)
    p.add_argument("--out",required=True)
    a=p.parse_args();main(a.start,a.games,a.out)
