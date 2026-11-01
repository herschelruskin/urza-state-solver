#!/usr/bin/env python3
"""v36 four-policy CPU time to finish London mulligan ONLY, no gameplay.

Separate interpreter per policy, same four canonical physical 99 game
seeds, same seat and all London sevens. Compare v5 50-beam
hypothetical sampling, frozen v27 fast Q/C, v33b fast bottom ridge,
and v36 fast direct-Q forest (8×32 trees/head).
This is NOT deck T1/T2/T3 or cEDH game benchmark.
"""
from __future__ import annotations
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
POLICIES={
 "v5":"dack_paired_counterfactual_v5_stable_chance_20261031",
 "v27":"dack_paired_counterfactual_v27_T2_only_DP_20261101",
 "v33b":"dack_paired_counterfactual_v33b_regret_bottom_only_20261101",
 "v36":"dack_paired_counterfactual_v36_targeted_keep_20261101"
}
CHILD=(
 "import json,sys,time\n"
 "m=__import__(sys.argv[1]);a=m.audit()\n"
 "r=m.reference if sys.argv[1].startswith('dack_paired_counterfactual_v5_') else m.ref\n"
 "result=[]\n"
 "for gid in range(125900,125904):\n"
 " seed=int(r.SPEC['seed_base'])+gid*r.SEED_STRIDE\n"
 " seat,orders=r.stage_slots(seed)\n"
 " r.sim.reset_caches();r.sim.root.install('one_key_34')\n"
 " r.sim.m.set_trial_seed(seed)\n"
 " start=time.perf_counter()\n"
 " state,hist=r.choose_keep(r.SLOT_VARIANTS['one_key_34'],seat,orders)\n"
 " elapsed=time.perf_counter()-start\n"
 " assert hist[-1]['kept'] and len(state.hand)==hist[-1]['keep_n']\n"
 " result.append({'gid':gid,'seat':seat,'seconds':elapsed,'stage':hist[-1]['stage'],'keep_n':hist[-1]['keep_n']})\n"
 "print('DACK_V36_MULLIGAN_TIMING',json.dumps(result),flush=True)\n"
)

def run():
    result={}
    for policy,mod in POLICIES.items():
        p=subprocess.run([sys.executable,"-c",CHILD,mod],
                         cwd=ROOT,capture_output=True,text=True,timeout=1100)
        if p.returncode:
            raise RuntimeError(("policy",policy,p.stdout[-1000:],p.stderr[-1000:]))
        arr=[s[len("DACK_V36_MULLIGAN_TIMING "):] for s in p.stdout.splitlines()
             if s.startswith("DACK_V36_MULLIGAN_TIMING ")]
        assert len(arr)==1
        data=json.loads(arr[0]);assert len(data)==4
        result[policy]={"per_game":data,
          "sum_london_seconds":sum(x["seconds"] for x in data)}
        print("DACK_V36_MULLIGAN_ONLY_CPU_POLICY_PASS",policy,
              result[policy]["sum_london_seconds"],flush=True)
    assert len(result)==4
    for gid in range(125900,125904):
        matching=[next(q for q in result[policy]["per_game"] if q["gid"]==gid)
                  for policy in POLICIES]
        assert len({q["seat"] for q in matching})==1
    result["speedup_v5_over_v36_London_only"]=(
      result["v5"]["sum_london_seconds"]/result["v36"]["sum_london_seconds"])
    result["speedup_v5_over_v33b_London_only"]=(
      result["v5"]["sum_london_seconds"]/result["v33b"]["sum_london_seconds"])
    result["purpose"]="CPU time choose_keep only, excludes actual beam160 game"
    result["policy_approved"]=False
    p=ROOT/"benchmark_results/v36_four_policy_mulligan_CPU_only_N4.json"
    p.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("DACK_V36_NO_BEAM_POLICY_RUNTIME_BENCHMARK_PASS",
          result["speedup_v5_over_v36_London_only"],flush=True)

if __name__=="__main__":run()
