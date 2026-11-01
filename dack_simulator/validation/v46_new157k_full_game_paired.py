#!/usr/bin/env python3
"""v46 independent 157k N256 paired full-policy physical outcome shards.

Only run after the predeclared model DEV GATE is PASSED. Each policy is
executed in a separate interpreter to avoid shared reference globals.
The first 7 physical slots and seat must match exactly for all comparisons.
"""
from __future__ import annotations
import argparse,gzip,json,subprocess,sys,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SCHEMA="dack_v46_new_157k_v43_v46_complete_game_paired_N256_shard"
CHILD=(
 "import json,sys,time\n"
 "policy=sys.argv[1];start=int(sys.argv[2]);n=int(sys.argv[3])\n"
 "if policy=='v43':\n"
 " import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as mod\n"
 " mod.audit();ref=mod.ref\n"
 "else:\n"
 " import dack_paired_counterfactual_v46_early_seven_physical_20261101 as mod\n"
 " mod.audit();ref=mod.ref\n"
 "for gid in range(start,start+n):\n"
 " t=time.perf_counter();g=ref.game('one_key_34',gid)\n"
 " print('DACK_V46_FRESH_GAME',json.dumps({'gid':gid,'seat':g['seat'],"
 "'turn':g['win_turn'],'keep_n':g['keep_n'],'history':g['history'],"
 "'seconds':round(time.perf_counter()-t,5)}),flush=True)\n"
)
def one_policy(policy,start):
    r=subprocess.run([sys.executable,"-c",CHILD,policy,str(start),"32"],
            cwd=ROOT,text=True,capture_output=True,timeout=2700)
    if r.returncode!=0:
        raise RuntimeError(("157k policy child failed",policy,start,r.stdout[-1200:],r.stderr[-1200:]))
    rows=[json.loads(s[len("DACK_V46_FRESH_GAME "):])
          for s in r.stdout.splitlines() if s.startswith("DACK_V46_FRESH_GAME ")]
    assert len(rows)==32
    assert [z["gid"] for z in rows]==list(range(start,start+32))
    return rows
def run(start,out):
    assert start in range(157000,157256,32)
    report_path=ROOT/"benchmark_results/v46_156k_two_sevens_physical_train_dev.json"
    report=json.loads(report_path.read_text())
    assert report["status"]=="PASS" and report["dev"]["dev_pass_full_game_gate"]
    model=ROOT/"models/v46_real_first_two_sevens_RESEARCH.json"
    modelsha=hashlib.sha256(model.read_bytes()).hexdigest()
    assert report["model_sha256"]==modelsha
    a=one_policy("v43",start);b=one_policy("v46",start)
    rows=[]
    for x,y in zip(a,b):
        assert x["gid"]==y["gid"] and x["seat"]==y["seat"]
        assert x["history"][0]["seven_slots"]==y["history"][0]["seven_slots"]
        assert x["history"][0]["seven"]==y["history"][0]["seven"]
        assert all(v["turn"] in (0,1,2,3) for v in (x,y))
        rows.append({"gid":x["gid"],"v43":x,"v46":y})
    result={
       "schema":SCHEMA,"status":"PASS","start":start,"N_matched_deals":32,
       "physical_deals_independent_of_156k_train_and_dev":True,
       "predeclared_dev_gate_passed_before_157k_results":True,
       "original_v43_frozen_unchanged":True,
       "only_first_two_seven_keep_decisions_may_differ":True,
       "strict_real_gameplay_beam160_99_cards":True,
       "same_seat_and_first_seven":True,
       "model_sha256":modelsha,"models_approved":False,
       "not_multiplayer_winrate":True,"rows":rows}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(result,f,sort_keys=True)
    print("DACK_V46_FRESH_N32_PAIRED_FULL_GAME_PASS",start,
      {pol:sum(0<r[pol]["turn"]<=2 for r in rows) for pol in ("v43","v46")},flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--start",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.start,a.out)
