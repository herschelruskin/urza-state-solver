#!/usr/bin/env python3
"""v46 retrospective action-transfer check on 26 previously inspected
original-v5 versus frozen-v43 first disagreements at stage0 or stage1.

Uses ONLY card and score information from already observed 151k source
and the independently trained/frozen physical 163k model; NOT a prospective
acceptance or an end-to-end physical winrate claim.
"""
from __future__ import annotations
import json,hashlib
from collections import Counter,defaultdict
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v45_frozen_v43_continuation as k
import dack_mulligan_v46_first_two_sevens_physical as f

SOURCE=ROOT/"benchmark_results/v45_v5_v43_matched_151k_N128_first_conflict.json"
MODEL=ROOT/"models/v46_early_Q2_residual_RESEARCH.json"
DEV=ROOT/"benchmark_results/v46_first_two_sevens_random_dev_N64.json"
def run():
    m=json.loads(MODEL.read_text());dev=json.loads(DEV.read_text())
    assert m["schema"]==f.SCHEMA and m["policy_approved"] is False
    assert dev["source_model_sha256"]==f.hash_file(MODEL)
    src=json.loads(SOURCE.read_text())
    assert src["status"]=="PASS" and src["counts"]=={"N":128,"v5_byT2":73,"v43_byT2":65}
    k.initialize();ref=k.ref;deck=ref.SLOT_VARIANTS[k.DECK_KEY]
    cases=[]
    for r in src["cases"]:
        stage=r["first_disagreement_stage"]
        if stage not in (0,1):continue
        gid=int(r["gid"]);seat=int(r["seat"])
        seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        actual_seat,orders=ref.stage_slots(seed)
        assert actual_seat==seat
        a=k.choose_at(stage,seat,orders[stage],deck)
        assert Counter(a["hand"])==Counter(r["v43_selected_hand_at_comparison"])
        assert a["bottom"]==[]
        assert abs(a["raw"]-r["v43_predicted_T2"])<1e-6
        assert abs(a["threshold"]-r["v43_DP_continuation"])<1e-6
        assert a["kept"]==(not r["v5_keeps_first"])
        seven=tuple(a["seven"]);unknown=tuple(deck[s] for s in orders[stage][7:])
        x=f.features(seven,unknown,seat,stage,a["raw"],a["threshold"])
        corrected=f.corrected(m,x,a["raw"])
        C2=m["frozen_v43_true_full99_C128_physical"][f"{seat}:{stage}"]["T2"]
        aC=(a["raw"]>=C2);aR=(corrected>=C2)
        cases.append({
          "gid":gid,"seat":seat,"stage":stage,
          "v5_would_keep":bool(r["v5_keeps_first"]),
          "old_v43_kept":bool(a["kept"]),
          "C_only_keeps":aC,"ridge_C_keeps":aR,
          "raw_Q2":a["raw"],"corrected_Q2":corrected,
          "old_continuation":a["threshold"],"physical_C2":C2,
          "visible_seven":list(seven),
        })
    assert len(cases)==26
    def counts(rs):
        n=len(rs)
        return {
           "N":n,"v5_early_KEEP":sum(r["v5_would_keep"] for r in rs),
           "v43_early_KEEP":sum(r["old_v43_kept"] for r in rs),
           "C_only_early_KEEP":sum(r["C_only_keeps"] for r in rs),
           "ridge_C_early_KEEP":sum(r["ridge_C_keeps"] for r in rs),
           "C_only_matches_v5":sum(r["C_only_keeps"]==r["v5_would_keep"] for r in rs),
           "ridge_C_matches_v5":sum(r["ridge_C_keeps"]==r["v5_would_keep"] for r in rs),
           "C_only_changed_vs_v43":sum(r["C_only_keeps"]!=r["old_v43_kept"] for r in rs),
           "ridge_C_changed_vs_v43":sum(r["ridge_C_keeps"]!=r["old_v43_kept"] for r in rs),
        }
    result={
      "schema":"dack_v46_consumed_151k_v5_v43_early_first_conflict_transfer_audit",
      "status":"PASS","model_train_163k_independent_of_archived_151k":True,
      "previously_inspected_151k_selected_conflicts_NOT_validation":True,
      "no_new_physical_trials_or_policy_fit_on_these_conflicts":True,
      "no_policy_approved":True,
      "overall":counts(cases),
      "stage0":counts([r for r in cases if r["stage"]==0]),
      "stage1":counts([r for r in cases if r["stage"]==1]),
      "v5_early_keep_v43_mull":counts([r for r in cases if r["v5_would_keep"]]),
      "v43_early_keep_v5_mull":counts([r for r in cases if not r["v5_would_keep"]]),
      "cases":cases,
    }
    p=ROOT/"benchmark_results/v46_old_151k_first_conflict_early_transfer_audit.json"
    p.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("DACK_V46_CONSUMED_151K_EARLY_CONFLICT_MECHANISM_TRANSFER_PASS",
          json.dumps({k:result[k] for k in ("overall","stage0","stage1",
              "v5_early_keep_v43_mull","v43_early_keep_v5_mull")},sort_keys=True),flush=True)
if __name__=="__main__":run()
