#!/usr/bin/env python3
"""Frozen v43 vs model-only policy-consistent continuation: strict independent
matched physical goldfish benchmark. Read-only except raw test artifacts.

Source DP calibrated on 163700..164723, previously developed on 164800..164863.
This run samples 166000..166255 before reading any of their outcomes. The
candidate is DP-only: no card, model, bottom, or game-rule changes.
"""
from __future__ import annotations
import argparse,gzip,json,hashlib,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
DP_PATH=ROOT/"models/dack_v43_model_only_policy_consistent_DP_163700_N1024_RESEARCH.json"
SCHEMA="dack_v43_policy_consistent_DP_vs_frozen_v43_matched_goldfish_166k_n32_v1"
CHILD=r"""
import json,sys,time
import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as v43
from pathlib import Path
mode=sys.argv[1];gid=int(sys.argv[2]);t0=time.perf_counter()
v43.audit()
ref=v43.ref
if mode=="dp":
    tab=json.loads(Path("models/dack_v43_model_only_policy_consistent_DP_163700_N1024_RESEARCH.json").read_text())
    assert tab["n_independent_outer_deals"]==1024 and tab["source_groups"]==[163700,164723]
    assert tab["stage_keep_counts"]==list(ref.sim.STAGES)
    for seat,vals in tab["seats"].items():
        ref_dp=v43.v27.original.DP["seat_continuations"][seat]["thresholds_by_london_stage"]
        assert len(ref_dp)==len(vals["thresholds_by_london_stage"])==8
        ref_dp[:]=list(vals["thresholds_by_london_stage"])
elif mode!="v43":raise ValueError(mode)
g=ref.game("one_key_34",gid)
print("DACK_V43_DP_REAL",json.dumps({"gid":gid,"mode":mode,"turn":int(g["win_turn"] or 0),
 "seat":g["seat"],"keep_n":g["keep_n"],"hand":g["hand"],
 "bottom":g["history"][-1]["bottom"],"first3":g["first3"],
 "history":g["history"],"elapsed":time.perf_counter()-t0}))
"""
def one(gid,mode):
    r=subprocess.run([sys.executable,"-c",CHILD,mode,str(gid)],cwd=ROOT,capture_output=True,text=True,timeout=180)
    if r.returncode:
        raise RuntimeError(("physical child failed",gid,mode,r.stdout[-1000:],r.stderr[-1600:]))
    lines=[s[len("DACK_V43_DP_REAL "):] for s in r.stdout.splitlines() if s.startswith("DACK_V43_DP_REAL ")]
    assert len(lines)==1,(gid,mode)
    return json.loads(lines[0])
def check(a,b):
    assert a["gid"]==b["gid"] and a["seat"]==b["seat"]
    assert a["history"][0]["seven"]==b["history"][0]["seven"]
    assert a["history"][0]["seven_slots"]==b["history"][0]["seven_slots"]
    assert a["turn"] in (0,1,2,3) and b["turn"] in (0,1,2,3)
    if (a["keep_n"],a["hand"],a["bottom"])==(b["keep_n"],b["hand"],b["bottom"]):
        assert a["first3"]==b["first3"] and a["turn"]==b["turn"],("no-op parity",a["gid"])
def main(start,out):
    if start not in range(166000,166256,32):raise ValueError("requires one of eight disjoint N32 groups")
    assert DP_PATH.is_file()
    sha=hashlib.sha256(DP_PATH.read_bytes()).hexdigest()
    rows=[];t0=time.perf_counter()
    for gid in range(start,start+32):
        a=one(gid,"v43");b=one(gid,"dp");check(a,b)
        rows.append({"gid":gid,"v43":a,"dp":b})
        if len(rows)%8==0:
            print("V43_DP_N32_PROGRESS",start,gid,"T1",
              sum(x["v43"]["turn"]==1 for x in rows),sum(x["dp"]["turn"]==1 for x in rows),
              "T2",sum(0<x["v43"]["turn"]<=2 for x in rows),
              sum(0<x["dp"]["turn"]<=2 for x in rows),flush=True)
    report={"schema":SCHEMA,"status":"PASS","gid_start":start,"N_independent_outer_deals":32,
       "frozen_Q2_and_candidate_selection":True,"same_physical99_shuffles_chance":True,
       "only_DP_threshold_substitution":True,"strict_beam160":True,
       "no_155k_or_165k":True,"not_a_promotion":True,
       "dp_research_json_sha256":sha,"elapsed_seconds":time.perf_counter()-t0,"rows":rows}
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(dest,"wt") as f:json.dump(report,f,sort_keys=True)
    print("DACK_V43_DP_MATCHED_SHARD_PASS",start,round(report["elapsed_seconds"],2),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--start",type=int,required=True)
    p.add_argument("--out",required=True);z=p.parse_args();main(z.start,z.out)
