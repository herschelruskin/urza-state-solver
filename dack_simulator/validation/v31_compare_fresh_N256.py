#!/usr/bin/env python3
"""Fresh 104k matched full-game deployment: v31 action regret vs frozen v27."""
from __future__ import annotations
import argparse,gzip,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
POLICIES=("v27_frozen","v31_action_regret")
SCRIPTS={
 "v27_frozen":"dack_paired_counterfactual_v27_T2_only_DP_20261101",
 "v31_action_regret":"dack_paired_counterfactual_v31_action_regret_DP_20261101"
}
CHILD=(
 "import json,sys,time\n"
 "module=__import__(sys.argv[1]);gid=int(sys.argv[2]);module.audit()\n"
 "ref=module.ref;start=time.perf_counter();x=ref.game('one_key_34',gid)\n"
 "print('DACK_V31_ACTUAL_GAME',json.dumps({'game_id':gid,'turn':x['win_turn'],"
 "'keep_n':x['keep_n'],'seat':x['seat'],'history':x['history'],"
 "'seconds':round(time.perf_counter()-start,5)}),flush=True)\n"
)
def run_one(gid,policy):
    m=SCRIPTS[policy]
    p=subprocess.run([sys.executable,"-c",CHILD,m,str(gid)],
                 cwd=ROOT,capture_output=True,text=True,timeout=900)
    if p.returncode:
        print("DACK_V31_FRESH_GAME_FAIL",gid,policy,p.stdout[-1800:],p.stderr[-2200:],flush=True)
        raise RuntimeError("prospective subproc game failed")
    rows=[s[len("DACK_V31_ACTUAL_GAME "):] for s in p.stdout.splitlines()
            if s.startswith("DACK_V31_ACTUAL_GAME ")]
    assert len(rows)==1,(gid,policy,p.stdout[-300:])
    return json.loads(rows[0])

def run(start,games,out):
    if not (104000<=start and games==4 and start+games<=104256 and start%4==0):
        raise ValueError("requires independent 104k fixed four-game shard")
    files=(
      "models/v14_curve/v14_teacher_groups_128.json",
      "models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json",
      "models/dack_v27_T2_only_continuations_EXPERIMENTAL.json",
      "models/dack_v31_Q_advantage_residual_EXPERIMENTAL.json"
    )
    hashes={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in files}
    rows=[]
    for gid in range(start,start+games):
        row={"game_id":gid}
        for p in POLICIES:row[p]=run_one(gid,p)
        assert len(set(row[p]["seat"] for p in POLICIES))==1
        assert len(set(tuple(row[p]["history"][0]["seven_slots"]) for p in POLICIES))==1
        assert all(row[p]["turn"] in (0,1,2,3) for p in POLICIES)
        rows.append(row)
        print("DACK_V31_FRESH_GAME_PAIRED",gid,
              {p:(row[p]["turn"],row[p]["keep_n"]) for p in POLICIES},flush=True)
    doc={
       "schema":"dack_v31_prospective_104k_matched_v27_v31",
       "status":"PASS","game_ids":[start,start+games-1],
       "n_physical_games":games,"same_seat_and_initial_physical_seven":True,
       "strict_gameplay_beam":160,
       "source_sha256":hashes,
       "no_prospective_training":True,
       "student_model_approved":False,
       "policies":POLICIES,"rows":rows,
    }
    path=Path(out);path.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("DACK_V31_FRESH_PROSPECTIVE_SHARD_PASS",start,games,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--games",type=int,default=4)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.start,a.games,a.out)
