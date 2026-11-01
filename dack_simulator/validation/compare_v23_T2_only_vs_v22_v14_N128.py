#!/usr/bin/env python3
"""Fresh N128 real-game comparison of v14, v22 and new T2-only v23.

Same physical 99-card deck and deterministic London shuffles per outer
game, actual strict beam160 goldfish after the keep. No hypothetical game
beams during any learned-policy mulligan. Each policy gets independent
Python process to avoid mutable global rules and simulator cache leakage.

88k IDs are unseen by the v21/22/23 training, validation, DP, and the
already exposed 87k larger v22-v14 N128 comparator.
"""
from __future__ import annotations
import argparse,gzip,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
POLICIES=("v14_128","v22_U_half_T3","v23_T2_only")
CHILD=(
    "import json,sys,time\n"
    "gid=int(sys.argv[1]);policy=sys.argv[2]\n"
    "if policy=='v14_128':\n"
    " import dack_paired_counterfactual_v13_teacher_distill_20261031 as p\n"
    " p.audit('models/v14_curve/v14_teacher_groups_128.json');runner=p.ref\n"
    " assert p.MODEL['deployed_policy_approved'] is False\n"
    "elif policy=='v22_U_half_T3':\n"
    " import dack_paired_counterfactual_v22_all_stage_real_keep_DP_20261101 as p\n"
    " p.audit();runner=p.ref\n"
    " assert p.MODEL['deployed_policy_approved'] is False\n"
    "else:\n"
    " import dack_paired_counterfactual_v23_T2_only_keep_DP_20261101 as p\n"
    " p.audit();runner=p.ref\n"
    " assert p.MODEL['deployed_policy_approved'] is False\n"
    "start=time.perf_counter();r=runner.game('one_key_34',gid)\n"
    "print('V23_NEW_GAME',json.dumps({'turn':r['win_turn'],"
    "'keep_n':r['keep_n'],'seat':r['seat'],"
    "'history':r['history'],"
    "'seconds':round(time.perf_counter()-start,4)}),flush=True)\n"
)
def single(gid,policy):
    run=subprocess.run([sys.executable,"-c",CHILD,str(gid),policy],
                       cwd=ROOT,text=True,capture_output=True,timeout=1200)
    if run.returncode:
        print("V23_COMPARISON_CHILD_FAILED",gid,policy,run.stdout[-1500:],
              run.stderr[-1500:],flush=True)
        raise RuntimeError("new T2-only source policy failed")
    matches=[line[len("V23_NEW_GAME "):] for line in run.stdout.splitlines()
             if line.startswith("V23_NEW_GAME ")]
    if len(matches)!=1:raise ValueError("missing child record")
    return json.loads(matches[0])
def main(start,games,out):
    if games<1 or start<88000 or start+games>88200:
        raise ValueError("comparison strictly 88k physical seed band")
    rows=[]
    for gid in range(start,start+games):
        x={"game_id":gid}
        for policy in POLICIES:x[policy]=single(gid,policy)
        if len({x[p]["seat"] for p in POLICIES})!=1:
            raise AssertionError("physically paired seat inconsistent")
        rows.append(x)
        print("V23_T2_ONLY_PAIRED_REAL_GAME",gid,
              {p:(x[p]["turn"],x[p]["keep_n"],x[p]["seconds"])
               for p in POLICIES},flush=True)
    def summarize(policy):
        v=[r[policy] for r in rows]
        return {
            "n":len(v),"T1":sum(x["turn"]==1 for x in v),
            "T2":sum(x["turn"] in (1,2) for x in v),
            "T3":sum(x["turn"] in (1,2,3) for x in v),
            "mean_keep":sum(x["keep_n"] for x in v)/len(v),
            "seconds":round(sum(x["seconds"] for x in v),4)
        }
    report={"schema":"dack_v23_T2_only_value_policy_physical_paired",
            "status":"PASS","game_ids":[start,start+games-1],
            "actual_gameplay_beam":160,
            "same_physical_99_slot_and_seat":True,
            "all_mulligan_beams_removed":True,
            "all_models_unapproved":True,
            "metrics":{p:summarize(p) for p in POLICIES},
            "rows":rows}
    path=Path(out);path.parent.mkdir(exist_ok=True,parents=True)
    with gzip.open(path,"wt") as f:json.dump(report,f)
    print("V23_N128_PAIRED_REAL_SHARD_PASS",json.dumps({
        k:v for k,v in report.items() if k!="rows"},sort_keys=True),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,default=88000)
    p.add_argument("--games",type=int,default=8)
    p.add_argument("--out",default="shards/v23_pair_88000.json.gz")
    a=p.parse_args()
    main(a.start,a.games,a.out)
