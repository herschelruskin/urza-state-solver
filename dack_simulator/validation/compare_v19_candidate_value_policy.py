#!/usr/bin/env python3
"""Fresh 72k full-game common-random-number paired test of v19 value policy.

v5 exact stable-dice reference, frozen v14-128 clone, and v19 hybrid:
same physical 99 deck and London stage shuffle per outer game, same
unchanged beam-160 actual gameplay; separate Python processes protect
from monkeypatch/global-cache contamination. v19 only changes candidate
bottom choice at keep-n 3..6 to learned *real outcome* utility.
"""
from __future__ import annotations
import argparse,gzip,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
POLICIES=("v5","v14_128","v19_value")
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
    " import dack_paired_counterfactual_v19_real_candidate_value_20261101 as p\n"
    " p.audit();runner=p.ref\n"
    " assert p.VALUE_MODEL['deployed_policy_approved'] is False\n"
    "t=time.perf_counter();r=runner.game('one_key_34',gid)\n"
    "print('V19_PHYSICAL_GAME',json.dumps({'turn':r['win_turn'],"
    "'keep_n':r['keep_n'],'seat':r['seat'],"
    "'history':r['history'],"
    "'seconds':round(time.perf_counter()-t,4)}),flush=True)\n"
)

def run_game(gid,policy):
    r=subprocess.run([sys.executable,"-c",CHILD,str(gid),policy],
                     cwd=ROOT,text=True,capture_output=True,timeout=1500)
    if r.returncode:
        print("V19_CHILD_FAILED",gid,policy,r.stdout[-1200:],r.stderr[-1800:],flush=True)
        raise RuntimeError("paired gameplay failed")
    found=[line[len("V19_PHYSICAL_GAME "):] for line in r.stdout.splitlines()
           if line.startswith("V19_PHYSICAL_GAME ")]
    if len(found)!=1:raise AssertionError("missing policy outcome")
    return json.loads(found[0])

def main(start,games,path):
    if not (72000<=start and start+games<=73000) or games<1:
        raise ValueError("reserve fresh 72k independent game seeds only")
    records=[]
    for gid in range(start,start+games):
        rec={"game_id":gid}
        for p in POLICIES:rec[p]=run_game(gid,p)
        if len({rec[p]["seat"] for p in POLICIES})!=1:
            raise AssertionError("paired physical seat mismatch")
        records.append(rec)
        print("V19_VALUE_REAL_PAIRED_GAME",gid,{
            p:(rec[p]["turn"],rec[p]["keep_n"],rec[p]["seconds"])
            for p in POLICIES},flush=True)
    def metrics(p):
        a=[rec[p] for rec in records]
        return {"n":len(a),
                "T1":sum(r["turn"]==1 for r in a),
                "T2":sum(r["turn"] in (1,2) for r in a),
                "T3":sum(r["turn"] in (1,2,3) for r in a),
                "mean_keep":sum(r["keep_n"] for r in a)/len(a),
                "runtime_seconds":round(sum(r["seconds"] for r in a),4)}
    out={
        "schema":"dack_v19_actual_bottom_utility_paired_research",
        "status":"PASS","game_ids":[start,start+games-1],
        "all_models_unapproved":True,
        "unchanged_actual_gameplay_beam":160,
        "model_changes_only_bottom_choice_at_keep_n_3_to_6":True,
        "metrics":{p:metrics(p) for p in POLICIES},
        "rows":records,
        "warning":"Low-N conditional goldfish test, not evidence of population noninferiority."
    }
    target=Path(path);target.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(target,"wt") as f:json.dump(out,f)
    print("V19_VALUE_REAL_PAIRED_SHARD_PASS",json.dumps({
        k:v for k,v in out.items() if k!="rows"},sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,default=72000)
    p.add_argument("--games",type=int,default=2)
    p.add_argument("--out",default="shards/v19_value_pair_72000.json.gz")
    a=p.parse_args()
    main(a.start,a.games,a.out)
