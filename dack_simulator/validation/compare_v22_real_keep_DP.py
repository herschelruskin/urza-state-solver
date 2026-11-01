#!/usr/bin/env python3
"""Fresh independent 86k physical-game test of REAL value vs London continuation.

Three policies:
 - strict original v5 beam-based London with stable dice;
 - unchanged v14-128 teacher-imitation student;
 - v22 keeps original v14 bottom choice but compares REAL-OUTCOME keep U
   against seat-specific offline London continuation expectation.

All policies execute the SAME strict beam-160 goldfish after an actual keep.
They run in fresh subprocesses so global monkeypatches/caches cannot leak.
"""
from __future__ import annotations
import argparse,gzip,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
POLICIES=("v5","v14_128","v22_real_keep_DP")
CHILD=(
    "import json,sys,time\n"
    "gid=int(sys.argv[1]);policy=sys.argv[2]\n"
    "if policy=='v5':\n"
    " import dack_paired_counterfactual_v5_stable_chance_20261031 as p\n"
    " p.audit();runner=p.reference\n"
    "elif policy=='v14_128':\n"
    " import dack_paired_counterfactual_v13_teacher_distill_20261031 as p\n"
    " p.audit('models/v14_curve/v14_teacher_groups_128.json');runner=p.ref\n"
    " assert p.MODEL['deployed_policy_approved'] is False\n"
    "else:\n"
    " import dack_paired_counterfactual_v22_all_stage_real_keep_DP_20261101 as p\n"
    " p.audit();runner=p.ref\n"
    " assert p.MODEL['deployed_policy_approved'] is False\n"
    "before=time.perf_counter();result=runner.game('one_key_34',gid)\n"
    "print('V22_RESEARCH_GAME',json.dumps({'turn':result['win_turn'],"
    "'keep_n':result['keep_n'],'seat':result['seat'],"
    "'history':result['history'],"
    "'seconds':round(time.perf_counter()-before,4)}),flush=True)\n"
)

def run_game(gid,policy):
    r=subprocess.run([sys.executable,"-c",CHILD,str(gid),policy],
                     cwd=ROOT,text=True,capture_output=True,timeout=1500)
    if r.returncode:
        print("V22_CHILD_FAILED",gid,policy,r.stdout[-1200:],r.stderr[-1800:],flush=True)
        raise RuntimeError("child policy game failed")
    rows=[line[len("V22_RESEARCH_GAME "):] for line in r.stdout.splitlines()
          if line.startswith("V22_RESEARCH_GAME ")]
    if len(rows)!=1:raise AssertionError("missing real policy game")
    return json.loads(rows[0])

def main(start,games,out):
    if not 86000<=start or games<1 or start+games>87000:
        raise ValueError("use only never-trained 86k physical game IDs")
    records=[]
    for gid in range(start,start+games):
        rec={"game_id":gid}
        for policy in POLICIES:
            rec[policy]=run_game(gid,policy)
        if len({rec[p]["seat"] for p in POLICIES})!=1:
            raise AssertionError("paired seat changed")
        records.append(rec)
        print("V22_KEEP_DP_REAL_GAME",gid,{
            p:(rec[p]["turn"],rec[p]["keep_n"],rec[p]["seconds"]) for p in POLICIES
        },flush=True)
    def metrics(policy):
        s=[r[policy] for r in records]
        return {"n":len(s),
                "T1":sum(x["turn"]==1 for x in s),
                "T2":sum(x["turn"] in (1,2) for x in s),
                "T3":sum(x["turn"] in (1,2,3) for x in s),
                "average_keep":sum(x["keep_n"] for x in s)/len(s),
                "seconds":round(sum(x["seconds"] for x in s),4)}
    res={
        "schema":"dack_v22_all_stage_real_keep_continuation_physical_game",
        "status":"PASS",
        "game_ids":[start,start+games-1],
        "model_deployment_approved":False,
        "actual_gameplay_beam":160,
        "same_physical_99_slot_stage_shuffles":True,
        "all_lookahead_gameplay_beams_removed_from_student_mulligans":True,
        "metrics":{p:metrics(p) for p in POLICIES},
        "rows":records,
        "warning":"Experimental goldfish n small, not multiplayer winrate or policy noninferiority."
    }
    target=Path(out);target.parent.mkdir(exist_ok=True,parents=True)
    with gzip.open(target,"wt") as fp:json.dump(res,fp)
    print("V22_REAL_KEEP_DP_PAIRED_PASS",json.dumps({
        k:v for k,v in res.items() if k!="rows"},sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,default=86000)
    p.add_argument("--games",type=int,default=2)
    p.add_argument("--out",default="shards/v22_keep_pair_86000.json.gz")
    a=p.parse_args()
    main(a.start,a.games,a.out)
