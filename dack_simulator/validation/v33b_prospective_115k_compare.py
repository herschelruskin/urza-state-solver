#!/usr/bin/env python3
"""v33b prospective 115k real-game paired v5 / frozen v27 / regret bottom.

Separate interpreter per policy prevents mutable module-global/monkeypatch
contamination. Identical physical 99 slots, seat and each London seven.
v33b and frozen v27 MUST have exactly the same keep/mull action sequence.
Strict actual beam160 gameplay and original stable seeded effects.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
POLICIES=("v5","v27_frozen","v33b_regret_bottom")
MODULES={
 "v5":"dack_paired_counterfactual_v5_stable_chance_20261031",
 "v27_frozen":"dack_paired_counterfactual_v27_T2_only_DP_20261101",
 "v33b_regret_bottom":"dack_paired_counterfactual_v33b_regret_bottom_only_20261101"
}
CHILD=(
 "import json,sys,time\n"
 "m=__import__(sys.argv[1]);gid=int(sys.argv[2]);a=m.audit()\n"
 "r=m.reference if sys.argv[1].startswith('dack_paired_counterfactual_v5_') else m.ref\n"
 "st=time.perf_counter();g=r.game('one_key_34',gid)\n"
 "print('V33B_PROSPECTIVE_ONE',json.dumps({'game_id':gid,"
 "'turn':g['win_turn'],'keep_n':g['keep_n'],'seat':g['seat'],"
 "'history':g['history'],'seconds':round(time.perf_counter()-st,6)}),flush=True)\n"
)

def one(gid,policy):
    p=subprocess.run([sys.executable,"-c",CHILD,MODULES[policy],str(gid)],
                     cwd=ROOT,capture_output=True,text=True,timeout=1500)
    if p.returncode:
        raise RuntimeError(f"policy {policy} gid {gid} failed: "+p.stdout[-1200:]+p.stderr[-1400:])
    a=[s[len("V33B_PROSPECTIVE_ONE "):] for s in p.stdout.splitlines()
       if s.startswith("V33B_PROSPECTIVE_ONE ")]
    assert len(a)==1,(gid,policy,p.stdout[-900:])
    return json.loads(a[0])

def run(start,out):
    if not 115000<=start<115256 or start%4 or start+4>115256:
        raise ValueError("115k prospective shards of exactly four")
    paths=("models/v14_curve/v14_teacher_groups_128.json",
           "models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json",
           "models/dack_v27_T2_only_continuations_EXPERIMENTAL.json",
           "models/dack_v33b_ridge_regret_EXPERIMENTAL.json")
    sha={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    rows=[]
    for gid in range(start,start+4):
        r={"game_id":gid}
        for p in POLICIES:
            r[p]=one(gid,p)
        assert len({r[p]["seat"] for p in POLICIES})==1
        assert len({tuple(r[p]["history"][0]["seven_slots"]) for p in POLICIES})==1
        assert all(r[p]["turn"] in (0,1,2,3) for p in POLICIES)
        va=r["v27_frozen"]["history"];vb=r["v33b_regret_bottom"]["history"]
        assert len(va)==len(vb)
        for a,b in zip(va,vb):
            assert (a["stage"],a["keep_n"],a["kept"],a["seven_slots"])==(
                    b["stage"],b["keep_n"],b["kept"],b["seven_slots"])
        assert r["v27_frozen"]["keep_n"]==r["v33b_regret_bottom"]["keep_n"]
        rows.append(r)
        print("DACK_V33B_PROSPECTIVE_MATCHED_GAME",gid,
              {p:(r[p]["turn"],r[p]["keep_n"]) for p in POLICIES},flush=True)
    doc={"schema":"dack_v33b_prospective_115k_three_policy_strict",
         "status":"PASS","game_ids":[start,start+3],
         "physical_groups":4,"policies":POLICIES,"source_sha256":sha,
         "strict_gameplay_beam":160,
         "v27_v33b_identical_london_stages_and_keep_actions":True,
         "initial_99_card_shuffle_and_seat_identical_across_policies":True,
         "unseen_future_never_used_to_decide_bottom":True,
         "115k_not_used_for_training_or_validation":True,
         "models_unapproved":True,"rows":rows}
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(dest,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("DACK_V33B_PROSPECTIVE_SHARD_PASS",start,4,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--out",required=True)
    x=p.parse_args();run(x.start,x.out)
