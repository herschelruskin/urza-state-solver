#!/usr/bin/env python3
"""v27 prospective N256 strict physical beam160 comparison on new 98k seeds."""
from __future__ import annotations
import argparse,gzip,hashlib,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation.compare_v26_fresh_n256 import run_one as prior_run_one
POLICIES=("v5","v26_expanded_keep_DP","v27_T2_only_DP")
CHILD=(
    "import json,sys,time\n"
    "gid=int(sys.argv[1])\n"
    "import dack_paired_counterfactual_v27_T2_only_DP_20261101 as policy\n"
    "policy.audit(); runner=policy.ref\n"
    "start=time.perf_counter();r=runner.game('one_key_34',gid)\n"
    "print('V27_PHYSICAL_GAME',json.dumps({'turn':r['win_turn'],"
    "'keep_n':r['keep_n'],'seat':r['seat'],'history':r['history'],"
    "'seconds':round(time.perf_counter()-start,4)}),flush=True)\n"
)
def execute(gid,policy):
    if policy=="v27_T2_only_DP":
        p=subprocess.run([sys.executable,"-c",CHILD,str(gid)],
                         cwd=ROOT,capture_output=True,text=True,timeout=1500)
        if p.returncode:
            print("V27_POLICY_FAIL",gid,p.stdout[-1000:],p.stderr[-1500:],flush=True)
            raise RuntimeError("fresh v27 game subprocess error")
        z=[s[len("V27_PHYSICAL_GAME "):] for s in p.stdout.splitlines()
           if s.startswith("V27_PHYSICAL_GAME ")]
        assert len(z)==1,(gid,p.stdout[-1000:])
        return json.loads(z[0])
    return prior_run_one(gid,policy)

def run(start,games,out):
    if not 98000<=start or games!=4 or start+games>98256:
        raise ValueError("v27 requires four-game shard on unused 98k physical IDs")
    files=[
      "models/v14_curve/v14_teacher_groups_128.json",
      "models/dack_v26_expanded_real_keep_value_EXPERIMENTAL.json",
      "models/dack_v26_expanded_all_stage_continuations_EXPERIMENTAL.json",
      "models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json",
      "models/dack_v27_T2_only_continuations_EXPERIMENTAL.json",
    ]
    hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
    rows=[]
    for gid in range(start,start+games):
        row={"game_id":gid}
        for pol in POLICIES:row[pol]=execute(gid,pol)
        assert len({row[pol]["seat"] for pol in POLICIES})==1
        assert len({tuple(row[pol]["history"][0]["seven_slots"]) for pol in POLICIES})==1
        assert all(row[pol]["turn"] in (0,1,2,3) for pol in POLICIES)
        rows.append(row)
        print("V27_PHYSICAL_PAIRED",gid,{
          pol:(row[pol]["turn"],row[pol]["keep_n"]) for pol in POLICIES},flush=True)
    doc={
      "schema":"dack_v27_fresh_98k_physical_beam160_shard","status":"PASS",
      "game_ids":[start,start+games-1],
      "models_sha256":hashes,"actual_gameplay_beam":160,
      "experimental_policies_unapproved":True,
      "same_seat_and_physical_first_seven":True,"rows":rows,
    }
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(dest,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("DACK_V27_PROSPECTIVE_98K_SHARD_PASS",start,games,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--games",type=int,default=4)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    run(a.start,a.games,a.out)
