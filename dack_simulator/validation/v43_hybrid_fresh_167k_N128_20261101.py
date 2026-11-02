#!/usr/bin/env python3
"""Prospective development-only 167k matched v43 / consistent-DP / selective
physical fallback comparison. All three arms use isolated processes and the
actual same 99-slot outer shuffle, seat, and final-game stable dice.

The fallback's six hypothetical unseen92 futures are independently shuffled
using only visible seven and remaining multiset, never the actual game's
hidden order. Its RNG is restored before actual gameplay.
"""
from __future__ import annotations
import argparse,gzip,json,subprocess,sys,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SCHEMA="dack_v43_hybrid_selective_167k_matched_threearm_strict_physical_v1"
CHILD=r"""
import json,sys,time
import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as v43
import dack_paired_counterfactual_v43_selective_line_20261101 as hybrid
mode=sys.argv[1];gid=int(sys.argv[2]);t0=time.perf_counter()
if mode=="v43":
    v43.audit()
elif mode in ("dp","hybrid"):
    hybrid.install(enabled=(mode=="hybrid"))
    # Outer game ID is NOT provided to keep/mull scoring; this only restores
    # the actual game's stable dice state after hypothetical trials.
    hybrid.OUTER_SEED=int(hybrid.ref.SPEC["seed_base"])+gid*hybrid.ref.SEED_STRIDE
else:raise ValueError(mode)
g=v43.ref.game("one_key_34",gid)
print("DACK_HYBRID_REAL",json.dumps({"gid":gid,"mode":mode,"turn":int(g["win_turn"] or 0),
 "seat":g["seat"],"keep_n":g["keep_n"],"hand":g["hand"],
 "bottom":g["history"][-1]["bottom"],"first3":g["first3"],
 "history":g["history"],"fallback_stats":dict(hybrid.STATS),
 "elapsed":time.perf_counter()-t0},separators=(",",":")))
"""
def one(gid,mode):
    p=subprocess.run([sys.executable,"-c",CHILD,mode,str(gid)],cwd=ROOT,capture_output=True,text=True,timeout=300)
    if p.returncode:
        raise RuntimeError(("physical child failed",gid,mode,p.stdout[-1400:],p.stderr[-1500:]))
    lines=[s[len("DACK_HYBRID_REAL "):] for s in p.stdout.splitlines()
           if s.startswith("DACK_HYBRID_REAL ")]
    assert len(lines)==1,(gid,mode)
    return json.loads(lines[0])
def main(start,out):
    if start not in range(167000,167128,32):raise ValueError("only four specified disjoint N32 shards")
    rows=[];t0=time.perf_counter()
    for gid in range(start,start+32):
        rec={}
        for mode in ("v43","dp","hybrid"):
            rec[mode]=one(gid,mode)
        assert len({rec[x]["seat"] for x in rec})==1
        assert len({tuple(rec[x]["history"][0]["seven_slots"]) for x in rec})==1
        assert len({tuple(rec[x]["history"][0]["seven"]) for x in rec})==1
        for left,right in (("dp","hybrid"),("v43","hybrid"),("dp","v43")):
            a=rec[left];b=rec[right]
            if (a["keep_n"],a["hand"],a["bottom"])==(b["keep_n"],b["hand"],b["bottom"]):
                assert a["turn"]==b["turn"],("no-op real gameplay parity",gid,left,right)
                assert a["first3"]==b["first3"]
        rows.append({"gid":gid,**rec})
        if len(rows)%8==0:
            print("V43_HYBRID_167K_PROGRESS",gid,"T2",{
              mode:sum(0<r[mode]["turn"]<=2 for r in rows)
              for mode in ("v43","dp","hybrid")},"trigger",
              sum(r["hybrid"]["fallback_stats"].get("fallback_invoked",0) for r in rows),
              "action_changed",
              sum(r["hybrid"]["fallback_stats"].get("fallback_changed_keep",0) for r in rows),
              flush=True)
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(dest,"wt") as f:json.dump({
       "schema":SCHEMA,"status":"PASS","N_independent_outer_deals":32,
       "start_gid":start,"no_historical_cohort_labels_for_actions":True,
       "strict_physical_beam160":True,"frozen_v43_and_Q2":True,
       "three_arms_isolated_interpreters":True,"source_deal_and_actual_chance_shared":True,
       "future_samples_for_policy_are_NOT_shared_with_actual_game":True,
       "prospective_dev_not_promotion":True,
       "elapsed_wall_seconds":time.perf_counter()-t0,"rows":rows},f,sort_keys=True)
    print("DACK_V43_HYBRID_MATCHED_SHARD_PASS",start,round(time.perf_counter()-t0,2),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--start",type=int,required=True)
    p.add_argument("--out",required=True);q=p.parse_args();main(q.start,q.out)
