#!/usr/bin/env python3
"""Independent 87k physically paired v14-128 and v22 value-DP research game test.

No expensive beam mulligans; strict beam160 actual deployment unchanged.
Paired physical stage shuffles are the same per game ID, but realized
subsequent draws can differ after distinct London decisions. The
conditional value and continuation models were frozen before 87k sampling.
"""
from __future__ import annotations
import argparse,gzip,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
POLICIES=("v14_128","v22_real_keep_DP")
CHILD=(
    "import json,sys,time\n"
    "gid=int(sys.argv[1]);policy=sys.argv[2]\n"
    "if policy=='v14_128':\n"
    " import dack_paired_counterfactual_v13_teacher_distill_20261031 as p\n"
    " p.audit('models/v14_curve/v14_teacher_groups_128.json');runner=p.ref\n"
    " assert p.MODEL['deployed_policy_approved'] is False\n"
    "else:\n"
    " import dack_paired_counterfactual_v22_all_stage_real_keep_DP_20261101 as p\n"
    " p.audit();runner=p.ref\n"
    " assert p.MODEL['deployed_policy_approved'] is False\n"
    "start=time.perf_counter();r=runner.game('one_key_34',gid)\n"
    "print('V22_INDEPENDENT_GAME',json.dumps({'turn':r['win_turn'],"
    "'keep_n':r['keep_n'],'seat':r['seat'],'history':r['history'],"
    "'seconds':round(time.perf_counter()-start,4)}),flush=True)\n"
)
def run_game(gid,policy):
    r=subprocess.run([sys.executable,"-c",CHILD,str(gid),policy],
                     cwd=ROOT,text=True,capture_output=True,timeout=900)
    if r.returncode:
        print("STUDENT_PAIR_FAILED",gid,policy,r.stdout[-1500:],r.stderr[-1500:],flush=True)
        raise RuntimeError("student paired process failed")
    xs=[x[len("V22_INDEPENDENT_GAME "):] for x in r.stdout.splitlines()
        if x.startswith("V22_INDEPENDENT_GAME ")]
    if len(xs)!=1:raise AssertionError(("missing game result",gid,policy))
    return json.loads(xs[0])

def main(start,games,out):
    if games<1 or not(87000<=start and start+games<=88000):
        raise ValueError("independent 87k game IDs only")
    rows=[]
    for gid in range(start,start+games):
        rec={"game_id":gid}
        for p in POLICIES:rec[p]=run_game(gid,p)
        if rec["v14_128"]["seat"]!=rec["v22_real_keep_DP"]["seat"]:
            raise AssertionError("paired seats differ")
        rows.append(rec)
        print("V22_VALUE_DP_STUDENT_PAIR",gid,
              {p:(rec[p]["turn"],rec[p]["keep_n"],rec[p]["seconds"]) for p in POLICIES},flush=True)
    report={"schema":"dack_v22_two_policy_independent_full_game",
            "status":"PASS","game_ids":[start,start+games-1],
            "gameplay_beam":160,"mulligan_beam":0,
            "models_approved":False,"common_physical_london_seeds":True,
            "same_bottom_policy":True,
            "rows":rows}
    target=Path(out);target.parent.mkdir(exist_ok=True,parents=True)
    with gzip.open(target,"wt") as f:json.dump(report,f)
    print("V22_STUDENT_PAIRED_SHARD_PASS",start,games,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,default=87000)
    p.add_argument("--games",type=int,default=8)
    p.add_argument("--out",default="shards/v22_student_pair_87000.json.gz")
    a=p.parse_args()
    main(a.start,a.games,a.out)
