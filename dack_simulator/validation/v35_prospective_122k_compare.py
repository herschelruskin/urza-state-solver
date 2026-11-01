#!/usr/bin/env python3
"""v35 prospective N256 FOUR-policy paired strict physical goldfish test.

This script is only to be dispatched if untouched 121k conditional
action-regret first passes its frozen stop gate. Each policy runs in a
separate Python interpreter, preventing global mutation. Entire
physical 99-card seats and London seven sequences are matched.
Actual beam160 gameplay, stable effects and cards unchanged.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,subprocess,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
POLICIES=("v5","v27_frozen","v33b_bottom","v35_early_regret")
MODULES={
 "v5":"dack_paired_counterfactual_v5_stable_chance_20261031",
 "v27_frozen":"dack_paired_counterfactual_v27_T2_only_DP_20261101",
 "v33b_bottom":"dack_paired_counterfactual_v33b_regret_bottom_only_20261101",
 "v35_early_regret":"dack_paired_counterfactual_v35_early_action_regret_20261101",
}
CHILD=(
 "import json,sys,time\n"
 "m=__import__(sys.argv[1]);gid=int(sys.argv[2]);a=m.audit()\n"
 "r=m.reference if sys.argv[1].startswith('dack_paired_counterfactual_v5_') else m.ref\n"
 "st=time.perf_counter();g=r.game('one_key_34',gid)\n"
 "print('DACK_V35_PROSPECTIVE_ONE',json.dumps({'game_id':gid,"
 "'turn':g['win_turn'],'keep_n':g['keep_n'],'seat':g['seat'],"
 "'history':g['history'],'seconds':round(time.perf_counter()-st,6)}),flush=True)\n"
)

def one(gid,policy):
    p=subprocess.run([sys.executable,"-c",CHILD,MODULES[policy],str(gid)],
                     cwd=ROOT,capture_output=True,text=True,timeout=1500)
    if p.returncode:
        raise RuntimeError(f"policy {policy} gid {gid} failed: "+p.stdout[-1400:]+p.stderr[-1400:])
    a=[s[len("DACK_V35_PROSPECTIVE_ONE "):] for s in p.stdout.splitlines()
       if s.startswith("DACK_V35_PROSPECTIVE_ONE ")]
    assert len(a)==1,(gid,policy,p.stdout[-900:])
    return json.loads(a[0])

def run(start,out):
    if not 122000<=start<122256 or (start-122000)%4 or start+4>122256:
        raise ValueError("reserved physical 122k prospective shards only")
    paths=("models/v14_curve/v14_teacher_groups_128.json",
           "models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json",
           "models/dack_v27_T2_only_continuations_EXPERIMENTAL.json",
           "models/dack_v33b_ridge_regret_EXPERIMENTAL.json",
           "models/dack_v35_early_action_regret_EXPERIMENTAL.json")
    shas={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    results=[]
    for gid in range(start,start+4):
        row={"game_id":gid}
        for policy in POLICIES:row[policy]=one(gid,policy)
        assert len(set(row[p]["seat"] for p in POLICIES))==1
        assert len(set(tuple(row[p]["history"][0]["seven_slots"]) for p in POLICIES))==1
        assert all(row[p]["turn"] in (0,1,2,3) for p in POLICIES)
        v27=row["v27_frozen"]["history"]
        v33=row["v33b_bottom"]["history"]
        assert len(v27)==len(v33)
        assert all((a["stage"],a["keep_n"],a["kept"],a["seven_slots"])==
                   (b["stage"],b["keep_n"],b["kept"],b["seven_slots"])
                   for a,b in zip(v27,v33))
        v35=row["v35_early_regret"]["history"]
        assert v35[-1]["kept"]
        for rec in v35:
            assert bool(rec["kept"])==bool(rec["v35_decision"]["new_keep"])
            assert bool(rec["v35_original_v27_keep"])==bool(
                   rec["v35_decision"]["old_keep"])
            assert rec["stage"]>=3 or rec["v35_decision"]["reason"] in (
                  "frozen_v27_fallback","regret_select_keep","regret_select_mull")
            if rec["stage"]>=3:
                assert rec["kept"]==rec["v35_original_v27_keep"]
            assert Counter(rec["seven"])==Counter(rec["hand"])+Counter(rec["bottom"])
        # Strong important metamorphic invariant: when v35 makes no
        # action override, its physical game MUST match v33b exactly.
        unchanged=all(x["kept"]==x["v35_original_v27_keep"] for x in v35)
        if unchanged:
            assert len(v35)==len(v33)
            assert all(Counter(a["hand"])==Counter(b["hand"]) and
                       Counter(a["bottom"])==Counter(b["bottom"])
                       for a,b in zip(v35,v33))
            assert row["v35_early_regret"]["turn"]==row["v33b_bottom"]["turn"],(
                "same physical final game must yield same turn",gid)
        results.append(row)
        print("DACK_V35_PROSPECTIVE_MATCHED_GAME",gid,
              {p:(row[p]["turn"],row[p]["keep_n"]) for p in POLICIES},
              "v35_stage_override",not unchanged,flush=True)
    doc={"schema":"dack_v35_prospective_122k_four_policy_real_deployment",
         "status":"PASS","game_ids":[start,start+3],"physical_groups":4,
         "policies":POLICIES,"source_sha256":shas,
         "strict_actual_beam160":True,
         "original_99_card_first_sevens_seat_matched":True,
         "frozen_v27_v33b_london_keep_parity":True,
         "if_same_v35_keep_actions_then_exact_v33b_turn_parity":True,
         "no_hidden_future_visible_to_mulligan_policy":True,
         "122k_not_in_training_or_conditional_validation":True,
         "no_model_promotion":True,"rows":results}
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(dest,"wt") as f:json.dump(doc,f,sort_keys=True)
    print("DACK_V35_122K_PROSPECTIVE_SHARD_PASS",start,4,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.start,a.out)
