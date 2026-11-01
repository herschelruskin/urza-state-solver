#!/usr/bin/env python3
"""v37 PREPARED, strictly GATED 128k N256 four-policy full game comparison.

Requires existing 127k true physical independent action-regret report
with *passed* frozen conditional and actual-path coverage gates.
Reference v5, v27, v33b and v37 each run in own isolated subprocess.
Match actual physical 99-card outer slots and seat, London sevens,
strict stable dice and beam160 engine. Unchanged v37 action sequence
must reproduce v33b *identical actual win turn*, without exception.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,subprocess,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
POLICIES=("v5","v27","v33b","v37")
MODS={
 "v5":"dack_paired_counterfactual_v5_stable_chance_20261031",
 "v27":"dack_paired_counterfactual_v27_T2_only_DP_20261101",
 "v33b":"dack_paired_counterfactual_v33b_regret_bottom_only_20261101",
 "v37":"dack_paired_counterfactual_v37_direct_regret_20261101"}
CHILD=(
 "import json,sys,time\n"
 "m=__import__(sys.argv[1]);gid=int(sys.argv[2]);m.audit()\n"
 "r=m.reference if sys.argv[1].startswith('dack_paired_counterfactual_v5_') else m.ref\n"
 "a=time.perf_counter();z=r.game('one_key_34',gid)\n"
 "print('V37_PROSPECTIVE_TRUE_GAME',json.dumps({'gid':gid,'turn':z['win_turn'],"
 "'seat':z['seat'],'keep_n':z['keep_n'],'history':z['history'],"
 "'elapsed':time.perf_counter()-a}),flush=True)\n")
def one(policy,gid):
    proc=subprocess.run([sys.executable,"-c",CHILD,MODS[policy],str(gid)],
                        cwd=ROOT,capture_output=True,text=True,timeout=1500)
    if proc.returncode:
        raise RuntimeError(("v37 prospective physical game",policy,gid,proc.stdout[-1200:],proc.stderr[-1200:]))
    lines=[x[len("V37_PROSPECTIVE_TRUE_GAME "):] for x in proc.stdout.splitlines()
           if x.startswith("V37_PROSPECTIVE_TRUE_GAME ")]
    assert len(lines)==1
    return json.loads(lines[0])
def main(start,out):
    if not 128000<=start<128256 or (start-128000)%4 or start+4>128256:raise ValueError
    g=ROOT/"benchmark_results/v37_127k_independent_direct_regret.json"
    gate=json.loads(g.read_text())
    assert gate["status"]=="PASS" and gate["precommitted_full_gate_passed"]
    assert gate["next_step"]=="128k_FULL_GAME_PROSPECTIVE_ALLOWED"
    assert gate["model_sha256"]==hashlib.sha256(
      (ROOT/"models/dack_v37_direct_regret_EXPERIMENTAL.json").read_bytes()).hexdigest()
    rows=[]
    for gid in range(start,start+4):
        z={"game_id":gid}
        for p in POLICIES:z[p]=one(p,gid)
        assert len(set(z[p]["seat"] for p in POLICIES))==1
        assert len(set(tuple(z[p]["history"][0]["seven_slots"]) for p in POLICIES))==1
        assert all(z[p]["turn"] in (0,1,2,3) for p in POLICIES)
        h0=z["v27"]["history"];h1=z["v33b"]["history"]
        assert len(h0)==len(h1)
        assert all((a["stage"],a["keep_n"],a["kept"],a["seven_slots"])==
                   (b["stage"],b["keep_n"],b["kept"],b["seven_slots"])
                   for a,b in zip(h0,h1))
        new=z["v37"]["history"]
        assert new[-1]["kept"]
        for record in new:
            assert Counter(record["seven"])==Counter(record["hand"])+Counter(record["bottom"])
            assert record["stage"]<3 or record["kept"]==record["v37_frozen_v27_original_keep"]
        if all(a["kept"]==a["v37_frozen_v27_original_keep"] for a in new):
            assert len(new)==len(h1) and z["v37"]["turn"]==z["v33b"]["turn"]
            assert all(Counter(a["hand"])==Counter(b["hand"]) and
                       Counter(a["bottom"])==Counter(b["bottom"])
                       for a,b in zip(new,h1))
        rows.append(z)
        print("DACK_V37_FOUR_POLICY_REAL_GAME",gid,
              {p:(z[p]["turn"],z[p]["keep_n"]) for p in POLICIES},flush=True)
    d={"schema":"dack_v37_128k_strict_prospective_four_policy_game",
       "status":"PASS","policy_approved":False,
       "game_ids":[start,start+3],"policies":POLICIES,
       "physical_outer_groups":4,
       "strict_actual_gameplay_beam160":True,
       "identical_99_card_outer_deals_and_seat":True,
       "full_game_prospective_precommitted_127k_gate_passed":True,
       "no_training_or_validation_on_128k":True,
       "separate_process_model_global_mutation_prevented":True,
       "v37_no_action_change_has_exact_v33b_game_turn":True,
       "model_sha256":gate["model_sha256"],
       "rows":rows}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(d,f,sort_keys=True)
    print("DACK_V37_PROSPECTIVE_PHYSICAL_SHARD_PASS",start,flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--out",required=True)
    x=p.parse_args();main(x.start,x.out)
