#!/usr/bin/env python3
"""v44 prospective, physical matched N256 v27/v43/v44 comparison.

Run frozen models in separate Python interpreters to isolate monkeypatched
Python globals, with the same 99-card slot deck, seed and London physical
sevens and original strict beam160 gameplay. Goldfish deployment, not actual
multiplayer cEDH win rate. 155000..155255 remain untouched until the
frozen 154k dev source has been scored and the acceptance gate is met.
"""
from __future__ import annotations
import argparse,gzip,json,hashlib,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SCHEMA="dack_v44_first_prospective_physical_155k_three_policy_N256_shard"
POLICIES=("v27","v43","v44")
MODULES={
 "v27":"dack_paired_counterfactual_v27_T2_only_DP_20261101",
 "v43":"dack_paired_counterfactual_v43_v27_max_Q2_20261101",
 "v44":"dack_paired_counterfactual_v44_physical_candidate_Q2_20261101",
}
CHILD=(
 "import json,sys,time\n"
 "mod=sys.argv[1];gid=int(sys.argv[2])\n"
 "m=__import__(mod);audit=m.audit()\n"
 "assert audit['status']=='PASS'\n"
 "ref=m.ref\n"
 "t=time.perf_counter()\n"
 "g=ref.game('one_key_34',gid)\n"
 "print('DACK_V44_155K_PHYSICAL',json.dumps({'turn':g['win_turn'],"
 "'seat':g['seat'],'keep_n':g['keep_n'],'history':g['history'],"
 "'seconds':round(time.perf_counter()-t,6)}),flush=True)\n"
)
def one(gid,policy):
    p=subprocess.run([sys.executable,"-c",CHILD,MODULES[policy],str(gid)],
       cwd=ROOT,capture_output=True,text=True,timeout=600)
    if p.returncode:raise RuntimeError((gid,policy,p.stdout[-1000:],p.stderr[-1300:]))
    rows=[s[len("DACK_V44_155K_PHYSICAL "):] for s in p.stdout.splitlines()
          if s.startswith("DACK_V44_155K_PHYSICAL ")]
    assert len(rows)==1
    return json.loads(rows[0])
def run(start,out):
    if start not in range(155000,155256,32):
        raise ValueError("only eight predeclared N32 seed groups")
    files=[
     "models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json",
     "models/dack_v27_T2_only_continuations_EXPERIMENTAL.json",
     "models/v44_all_candidate_Q2_residual_RESEARCH.json",
    ]
    sha={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files}
    rows=[];t0=time.perf_counter()
    for gid in range(start,start+32):
        group={"gid":gid}
        for policy in POLICIES:group[policy]=one(gid,policy)
        assert len({group[p]["seat"] for p in POLICIES})==1
        assert len({tuple(group[p]["history"][0]["seven_slots"]) for p in POLICIES})==1
        assert len({tuple(group[p]["history"][0]["seven"]) for p in POLICIES})==1
        assert all(group[p]["turn"] in (0,1,2,3) for p in POLICIES)
        rows.append(group)
        if len(rows)%8==0:
            print("DACK_V44_155K_PHYSICAL_PROGRESS",gid,
               {p:sum(0<r[p]["turn"]<=2 for r in rows) for p in POLICIES},
               "elapsed",round(time.perf_counter()-t0,2),flush=True)
    doc={
      "schema":SCHEMA,"status":"PASS","games":32,
      "gid_range":[start,start+31],"policies":POLICIES,
      "models_sha256":sha,"strict_99_physical_slots_beam160":True,
      "same_seats_real_London_sevens_and_stateless_gameplay_chance":True,
      "v44_model_immutable_before_155k_test":True,
      "no_v5_lookahead_runtime_for_all_three":True,
      "no_model_fitting_or_threshold_tuning_on_155k":True,
      "v44_not_yet_promoted":True,"rows":rows,
    }
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(dest,"wt") as g:json.dump(doc,g,sort_keys=True)
    print("DACK_V44_155K_N32_THREE_POLICY_MATCHED_GAME_PASS",start,flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--start",type=int,required=True);p.add_argument("--out",required=True)
    x=p.parse_args();run(x.start,x.out)
