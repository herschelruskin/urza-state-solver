#!/usr/bin/env python3
"""Predeclared N256 prospective v43 vs frozen v46 full-game paired test.

Do not invoke unless training+dev gate passed. Exact same physical seed,
first seven, seat, actual strict beam160; separate interpreters protect
process-global rules and cached model state. Retain v43 stages >=2 exactly.
"""
from __future__ import annotations
import argparse,gzip,json,hashlib,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SCHEMA="dack_v46_161k_independent_full_goldfish_v43_v46_paired_shard_v1"
CHILD=(
 "import json,sys,time\n"
 "p=sys.argv[1];gid=int(sys.argv[2])\n"
 "if p=='v43':\n"
 " import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as m\n"
 "else:\n"
 " import dack_paired_counterfactual_v46_early_seven_Q2_20261101 as m\n"
 "a=m.audit();assert a['status']=='PASS'\n"
 "ref=m.ref;t=time.perf_counter();g=ref.game('one_key_34',gid)\n"
 "print('DACK_V46_NEW_GAME',json.dumps({'turn':g['win_turn'],"
 "'keep_n':g['keep_n'],'seat':g['seat'],'history':g['history'],"
 "'seconds':round(time.perf_counter()-t,5)}),flush=True)\n"
)
def one(gid,which):
    proc=subprocess.run([sys.executable,"-c",CHILD,which,str(gid)],
       cwd=ROOT,capture_output=True,text=True,timeout=600)
    if proc.returncode:raise RuntimeError((gid,which,proc.stdout[-800:],proc.stderr[-1400:]))
    z=[t[len("DACK_V46_NEW_GAME "):] for t in proc.stdout.splitlines()
       if t.startswith("DACK_V46_NEW_GAME ")]
    assert len(z)==1
    return json.loads(z[0])
def run(start,out):
    assert start in range(161000,161256,32)
    de=json.loads((ROOT/"benchmark_results/v46_first_two_sevens_160k_dev_N64.json").read_text())
    assert de["status"]=="PASS" and de["predeclared_directional_dev_gate_passed"]
    assert not de["model_approved"] and de["N_development_source_deals"]==64
    sha=hashlib.sha256((ROOT/"models/v46_first_two_sevens_Q2_residual_RESEARCH.json").read_bytes()).hexdigest()
    assert sha==de["model_sha256"]
    rows=[];t=time.perf_counter()
    for gid in range(start,start+32):
        a=one(gid,"v43");b=one(gid,"v46")
        assert a["seat"]==b["seat"]
        assert a["history"][0]["seven_slots"]==b["history"][0]["seven_slots"]
        assert a["history"][0]["seven"]==b["history"][0]["seven"]
        assert a["turn"] in (0,1,2,3) and b["turn"] in (0,1,2,3)
        rows.append({"gid":gid,"v43":a,"v46":b})
        if len(rows)%8==0:print("DACK_V46_161K_PAIRED_PROGRESS",gid,
            {p:sum(0<z[p]["turn"]<=2 for z in rows) for p in ("v43","v46")},
            "sec",round(time.perf_counter()-t,2),flush=True)
    doc={"schema":SCHEMA,"status":"PASS","ids":[start,start+31],
       "real_independent_outer_groups":32,
       "same_first_seven_and_seat":True,
       "exact_99_slot_strict_beam160_goldfish":True,
       "dev_gate_passed_before_opening_161k":True,
       "model_sha256":sha,"no_v5_lookahead_for_either_policy":True,
       "no_model_fit_on_161k":True,"policy_approved":False,
       "not_multiplayer_winrate":True,"rows":rows}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("DACK_V46_161K_PAIRED_SHARD_PASS",start,flush=True)
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--start",type=int,required=True)
    a.add_argument("--out",required=True);q=a.parse_args();run(q.start,q.out)
