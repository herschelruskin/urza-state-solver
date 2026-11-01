#!/usr/bin/env python3
"""Independent 110k N256 full-game v5/v27/v32 (unapproved) comparison.

Each physical game uses exact same first seven and seat across policies.
Sampled outcomes are NEVER train features. Gameplay untouched strict beam160.
Original v5 lookahead expensive; v32/v27 zero London beams.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
POLICIES=("v5","v27_frozen","v32_shared_C")
NAMES={
 "v5":"dack_paired_counterfactual_v5_stable_chance_20261031",
 "v27_frozen":"dack_paired_counterfactual_v27_T2_only_DP_20261101",
 "v32_shared_C":"dack_paired_counterfactual_v32_shared_continuation_DP_20261101"
}
CHILD=(
    "import json,sys,time\n"
    "module=__import__(sys.argv[1]);gid=int(sys.argv[2]);module.audit()\n"
    "ref=module.reference if sys.argv[1].startswith('dack_paired_counterfactual_v5_') else module.ref\n"
    "start=time.perf_counter();res=ref.game('one_key_34',gid)\n"
    "print('V32_PROSPECTIVE_GAME',json.dumps({'game_id':gid,'turn':res['win_turn'],"
    "'keep_n':res['keep_n'],'seat':res['seat'],'history':res['history'],"
    "'seconds':round(time.perf_counter()-start,5)}),flush=True)\n"
)

def game(gid,policy):
    p=subprocess.run([sys.executable,"-c",CHILD,NAMES[policy],str(gid)],
                  cwd=ROOT,capture_output=True,text=True,timeout=1500)
    if p.returncode:
        print("V32_SUBPROCESS_ERROR",gid,policy,p.stdout[-1600:],p.stderr[-2000:],flush=True)
        raise RuntimeError("v32 prospective one physical game errored")
    lines=[s[len("V32_PROSPECTIVE_GAME "):] for s in p.stdout.splitlines()
           if s.startswith("V32_PROSPECTIVE_GAME ")]
    assert len(lines)==1,(gid,policy,p.stdout[-500:])
    return json.loads(lines[0])

def run(start,games,out):
    if not (110000<=start and games==4 and start+games<=110256 and start%4==0):
        raise ValueError("v32 prospective requires four fresh 110k games")
    files=[
      "models/v14_curve/v14_teacher_groups_128.json",
      "models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json",
      "models/dack_v27_T2_only_continuations_EXPERIMENTAL.json",
      "models/dack_v32_shared_Qmull_continuation_EXPERIMENTAL.json",
    ]
    sha={x:hashlib.sha256((ROOT/x).read_bytes()).hexdigest() for x in files}
    records=[]
    for gid in range(start,start+games):
        row={"game_id":gid}
        for policy in POLICIES:row[policy]=game(gid,policy)
        assert len(set(row[p]["seat"] for p in POLICIES))==1
        assert len(set(tuple(row[p]["history"][0]["seven_slots"]) for p in POLICIES))==1
        assert all(row[p]["turn"] in (0,1,2,3) for p in POLICIES)
        records.append(row)
        print("V32_PROSPECTIVE_MATCHED_GAME",gid,
          {p:(row[p]["turn"],row[p]["keep_n"]) for p in POLICIES},flush=True)
    doc={
       "schema":"dack_v32_prospective_110k_three_policy_strict",
       "status":"PASS","game_ids":[start,start+games-1],
       "n_game_groups":games,
       "actual_gameplay_beam":160,"mulligan_beams_v32":0,
       "same_physical_first_seven_and_seat":True,
       "v32_approved":False,
       "source_sha256":sha,
       "policies":POLICIES,"rows":records,
       "test_cohort_never_in_training_or_threshold_calibration":True
    }
    dest=Path(out);dest.parent.mkdir(exist_ok=True,parents=True)
    with gzip.open(dest,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("V32_PROSPECTIVE_SHARD_PASS",start,games,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--games",type=int,default=4)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.start,a.games,a.out)
