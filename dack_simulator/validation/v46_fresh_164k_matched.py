#!/usr/bin/env python3
"""N256 genuinely new paired full-game acceptance if v46 dev gate passes.

The prior 163k random seven K/C development outcomes DO NOT appear in 164k.
Frozen v43 and one stage-isolated v46 candidate each run in a separate
interpreter to avoid global rule/model contamination. Original same 99 slots,
seat, stable dice, strict real beam160. Goldfish Dack deployment, not
four-player cEDH wins. Never run this if all four dev stage/model gates fail.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
DEV=ROOT/"benchmark_results/v46_first_two_sevens_random_dev_N64.json"
MODEL=ROOT/"models/v46_early_Q2_residual_RESEARCH.json"
SCHEMA="dack_v46_fresh164k_stage_isolated_v43_pair_N16_shard_v1"
CHILD=(
 "import sys,time,json\n"
 "p=sys.argv[1];gid=int(sys.argv[2]);stage=int(sys.argv[3]);mode=sys.argv[4]\n"
 "t=time.perf_counter()\n"
 "if p=='baseline':\n"
 " import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as m\n"
 " m.audit();ref=m.ref\n"
 "else:\n"
 " import dack_paired_counterfactual_v46_early_one_stage_20261101 as m\n"
 " m.install(stage,mode,True);ref=m.ref\n"
 "g=ref.game('one_key_34',gid)\n"
 "print('DACK_V46_164K_REAL_GAME',json.dumps({"
 "'turn':g['win_turn'],'seat':g['seat'],'keep_n':g['keep_n'],"
 "'history':g['history'],'seconds':round(time.perf_counter()-t,5)}))\n"
)
def value(gid,pol,stage,mode):
    z=subprocess.run([sys.executable,"-c",CHILD,pol,str(gid),str(stage),mode],
        cwd=ROOT,text=True,capture_output=True,timeout=600)
    if z.returncode:raise RuntimeError(("164k candidate physical child failure",
             gid,pol,z.stdout[-1000:],z.stderr[-2000:]))
    found=[s[len("DACK_V46_164K_REAL_GAME "):] for s in z.stdout.splitlines()
           if s.startswith("DACK_V46_164K_REAL_GAME ")]
    assert len(found)==1
    return json.loads(found[0])
def run(start,out):
    if start not in range(164000,164256,16):raise ValueError("only 16 fixed 164k N16 shards")
    dev=json.loads(DEV.read_text())
    assert dev["status"]=="PASS" and dev["no_model_or_policy_approved"]
    assert dev["new_164k_future_full_game_test_UNOPENED"]
    cand=dev["preferred_development_candidate_if_any"]
    assert cand is not None,"No dev gate passed: do not open new physical acceptance"
    stage=int(cand["stage"]);mode=cand["mode"]
    assert stage in (0,1) and mode in ("C_only","ridge_C")
    assert dev["dev_results"][str(stage)][mode]["development_gate_pass"]
    model_hash=hashlib.sha256(MODEL.read_bytes()).hexdigest()
    assert model_hash==dev["source_model_sha256"]
    rows=[]
    for gid in range(start,start+16):
        a=value(gid,"baseline",stage,mode)
        b=value(gid,"candidate",stage,mode)
        assert a["seat"]==b["seat"] and a["history"][0]["seven_slots"]==b["history"][0]["seven_slots"]
        assert a["turn"] in (0,1,2,3) and b["turn"] in (0,1,2,3)
        # Before the modified stage, the new policy must match v43.
        for i in range(min(len(a["history"]),len(b["history"]),stage)):
            assert a["history"][i]["kept"]==b["history"][i]["kept"]
            assert a["history"][i]["hand"]==b["history"][i]["hand"]
        rows.append({"gid":gid,"v43":a,"v46":b})
        print("DACK_V46_NEW164K_MATCHED_PHYSICAL_GAME",gid,
              "v43",a["turn"],"v46",b["turn"],flush=True)
    output={
      "schema":SCHEMA,"status":"PASS","game_ids":[start,start+15],
      "N_independent_physical_groups":16,
      "frozen_stage":stage,"frozen_mode":mode,
      "source_model_sha256":model_hash,
      "source_dev_sha256":hashlib.sha256(DEV.read_bytes()).hexdigest(),
      "strict_original_99_slots_and_beam160":True,
      "real_game_no_v5_lookahead_in_any_mulligan":True,
      "stage0_and_stage1_NOT_simultaneously_changed":True,
      "two_isolated_policy_interpreters":True,
      "physical_164k_unseen_in_fit_and_dev":True,
      "not_multiplayer_cedh_winrate":True,
      "research_policy_NOT_promoted":True,"rows":rows,
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(output,f,sort_keys=True)
    print("DACK_V46_NEW164K_MATCHED_N16_REAL_GAMES_PASS",start,flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--out",required=True)
    q=p.parse_args();run(q.start,q.out)
