#!/usr/bin/env python3
"""v36 paired fresh 125k actual 99-card, stable dice beam160 full game.

Only run after untouched independent 124k gate PASSES. All four
policies evaluate SAME original 125k physical game IDs, actual
London stage sevens/seat. Separate subprocess each policy prevents
module-global model/engine mutations. No data reused from training.
"""
from __future__ import annotations
from collections import Counter
import argparse,gzip,hashlib,json,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
POLICIES=("v5","v27","v33b","v36")
MODULES={
 "v5":"dack_paired_counterfactual_v5_stable_chance_20261031",
 "v27":"dack_paired_counterfactual_v27_T2_only_DP_20261101",
 "v33b":"dack_paired_counterfactual_v33b_regret_bottom_only_20261101",
 "v36":"dack_paired_counterfactual_v36_targeted_keep_20261101"}
CHILD=(
 "import json,sys,time\n"
 "m=__import__(sys.argv[1]);gid=int(sys.argv[2]);a=m.audit()\n"
 "r=m.reference if sys.argv[1].startswith('dack_paired_counterfactual_v5_') else m.ref\n"
 "t=time.perf_counter();g=r.game('one_key_34',gid)\n"
 "print('V36_125K_REAL_GAME',json.dumps({'id':gid,'turn':g['win_turn'],"
 "'seat':g['seat'],'keep_n':g['keep_n'],'history':g['history'],"
 "'seconds':time.perf_counter()-t}),flush=True)\n"
)

def one(gid,policy):
    p=subprocess.run([sys.executable,"-c",CHILD,MODULES[policy],str(gid)],
                     cwd=ROOT,capture_output=True,text=True,timeout=1800)
    if p.returncode:
        raise RuntimeError(("physical prospective policy failure",policy,gid,
                            p.stdout[-1400:],p.stderr[-1400:]))
    rows=[q[len("V36_125K_REAL_GAME "):] for q in p.stdout.splitlines()
          if q.startswith("V36_125K_REAL_GAME ")]
    assert len(rows)==1
    return json.loads(rows[0])

def run(start,out):
    assert 125000<=start<125256 and start%4==0 and start+4<=125256
    gate=ROOT/"benchmark_results/v36_124k_untouched_validation.json"
    report=json.loads(gate.read_text())
    assert report["status"]=="PASS" and report["precommitted_gate_passed"]
    assert report["next_step"]=="125k_PROSPECTIVE_ALLOWED"
    assert report["frozen_candidate_sha256"]==hashlib.sha256(
         (ROOT/"models/dack_v36_targeted_real_keep_EXPERIMENTAL.json").read_bytes()).hexdigest()
    source={
      p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
      for p in ("models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json",
                "models/dack_v27_T2_only_continuations_EXPERIMENTAL.json",
                "models/dack_v33b_ridge_regret_EXPERIMENTAL.json",
                "models/dack_v36_targeted_real_keep_EXPERIMENTAL.json",
                "benchmark_results/v36_124k_untouched_validation.json")}
    rows=[]
    for gid in range(start,start+4):
        r={"game_id":gid}
        for p in POLICIES:r[p]=one(gid,p)
        assert len(set(r[p]["seat"] for p in POLICIES))==1
        assert len(set(tuple(r[p]["history"][0]["seven_slots"]) for p in POLICIES))==1
        assert all(r[p]["turn"] in (0,1,2,3) for p in POLICIES)
        va=r["v27"]["history"];vb=r["v33b"]["history"]
        assert len(va)==len(vb)
        assert all((a["stage"],a["keep_n"],a["kept"],a["seven_slots"])==
                   (b["stage"],b["keep_n"],b["kept"],b["seven_slots"])
                   for a,b in zip(va,vb))
        vc=r["v36"]["history"]
        assert vc[-1]["kept"]
        for h in vc:
            assert Counter(h["seven"])==Counter(h["hand"])+Counter(h["bottom"])
            assert h["stage"]<3 or h["kept"]==h["v36_frozen_v27_original_keep"]
            assert h["v36_action_diagnostic"]["new_keep"]==h["kept"]
        unchanged=all(h["kept"]==h["v36_frozen_v27_original_keep"] for h in vc)
        if unchanged:
            assert len(vc)==len(vb)
            assert all(Counter(a["hand"])==Counter(b["hand"]) and
                       Counter(a["bottom"])==Counter(b["bottom"])
                       for a,b in zip(vc,vb))
            assert r["v36"]["turn"]==r["v33b"]["turn"],(
                "same physical seven/bottom and seed MUST yield same game result",gid)
        rows.append(r)
        print("DACK_V36_125K_PROSPECTIVE_GAME_PASS",gid,{
           p:(r[p]["turn"],r[p]["keep_n"]) for p in POLICIES},flush=True)
    doc={
      "schema":"dack_v36_125k_four_policy_full_game_physical_prospective",
      "status":"PASS","physical_group_count":4,
      "game_ids":[start,start+3],"policy_order":POLICIES,
      "strict_gameplay_beam160":True,"matching_seat_sevens_across_policies":True,
      "separate_processes_no_global_state_leak":True,
      "unchanged_actions_reproduce_v33b_exact_game_turn":True,
      "original_v5_and_v27_reference_frozen":True,
      "independent_124k_gate_passed_before_run":True,
      "all_125k_outcomes_untouched_during_training":True,
      "source_sha256":source,
      "policy_approved":False,
      "rows":rows}
    path=Path(out);path.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("DACK_V36_125K_FOUR_POLICY_SHARD_PASS",start,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.start,a.out)
