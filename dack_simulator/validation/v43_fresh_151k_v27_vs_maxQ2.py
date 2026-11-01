#!/usr/bin/env python3
"""Fresh 151k matched strict goldfish benchmark: v27 vs v43 max-Q2.
Unchanged deck, same seat/shuffles/chance; each policy separate interpreter.
"""
from __future__ import annotations
import argparse,gzip,json,subprocess,sys,hashlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SCHEMA="dack_v43_fresh_151k_v27_vs_maxQ2_N256_paired_shard"
CHILD=(
 "import json,time,sys\n"
 "p=sys.argv[1];g=int(sys.argv[2]);t=time.perf_counter()\n"
 "if p=='v27':\n"
 " import dack_paired_counterfactual_v27_T2_only_DP_20261101 as m\n"
 " m.audit();ref=m.ref\n"
 "else:\n"
 " import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as m\n"
 " m.audit();ref=m.ref\n"
 "r=ref.game('one_key_34',g)\n"
 "print('DACK_V43_PHYSICAL_GAME',json.dumps({'turn':r['win_turn'],"
 "'seat':r['seat'],'keep_n':r['keep_n'],'history':r['history'],"
 "'seconds':round(time.perf_counter()-t,5)}))\n"
)
def one(gid,pol):
    p=subprocess.run([sys.executable,"-c",CHILD,pol,str(gid)],
      cwd=ROOT,capture_output=True,text=True,timeout=420)
    if p.returncode:raise RuntimeError(("child_error",gid,pol,p.stdout[-900:],p.stderr[-1000:]))
    matches=[s[len("DACK_V43_PHYSICAL_GAME "):] for s in p.stdout.splitlines()
             if s.startswith("DACK_V43_PHYSICAL_GAME ")]
    assert len(matches)==1,(gid,pol)
    return json.loads(matches[0])
def main(start,out):
    if start not in range(151000,151256,32):raise ValueError("8 sealed N32 groups")
    a=[];t0=time.perf_counter()
    for gid in range(start,start+32):
        a0=one(gid,"v27");a1=one(gid,"maxQ2")
        assert a0["seat"]==a1["seat"]
        assert a0["history"][0]["seven_slots"]==a1["history"][0]["seven_slots"]
        assert a0["history"][0]["seven"]==a1["history"][0]["seven"]
        assert a0["turn"] in (0,1,2,3) and a1["turn"] in (0,1,2,3)
        a.append({"gid":gid,"v27":a0,"maxQ2":a1})
        if len(a)%8==0:
            print("DACK_V43_151K_MATCHED_PROGRESS",gid,
               "T2",sum(0<r["v27"]["turn"]<=2 for r in a),
               sum(0<r["maxQ2"]["turn"]<=2 for r in a),
               "elapsed",round(time.perf_counter()-t0,2),flush=True)
    models={
      k:hashlib.sha256((ROOT/k).read_bytes()).hexdigest() for k in (
      "models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json",
      "models/dack_v27_T2_only_continuations_EXPERIMENTAL.json",
      "models/v14_curve/v14_teacher_groups_128.json")
    }
    report={
      "schema":SCHEMA,"status":"PASS","game_ids":[start,start+31],
      "N_independent_outer_games":32,"strict_physical_99_beam160":True,
      "model_sha256":models,"frozen_policy_prior_to_151k":True,
      "outcome":"Dack goldfish deployment, not multiplayer victory",
      "maxQ2_is_unapproved_and_ood_across_bottoms":True,
      "no_training_or_threshold_tuning_on_151k":True,"rows":a,
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(report,f,sort_keys=True)
    print("DACK_V43_FRESH_151K_N32_PAIRED_SHARD_PASS",start,flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--start",type=int,required=True);p.add_argument("--out",required=True)
    q=p.parse_args();main(q.start,q.out)
