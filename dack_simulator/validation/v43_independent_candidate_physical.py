#!/usr/bin/env python3
"""Independent physical 16-future re-evaluation of every legal candidate at
two PRESELECTED real v5/v27 disagreement hands, 115003 and 115017.

Uses common blind hidden92 permutations per hand/future and identical chance
seed for candidate comparison. Original v5 internal scorer remains unchanged;
this separate physical beam160 estimate is NOT original teacher's scoring,
and cases are deliberately selected (not representative random hands).
"""
from __future__ import annotations
import argparse,hashlib,json,random,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v5_stable_chance_20261031 as teacher
ref=teacher.reference
GIDS=(115003,115017)
N=16
SCHEMA="dack_v43_selected_conflict_original_8_sample_vs_independent_16_future_beam160_1"

def seed(*parts):
    return int.from_bytes(hashlib.sha256(json.dumps(parts,sort_keys=True,
         separators=(",",":")).encode()).digest()[:8],"big")

def evaluate(gid):
    assert gid in GIDS
    source=ROOT/f"benchmark_results/v43_original_v5_candidate_profiles/v43_original_v5_candidates_{gid}.json"
    doc=json.loads(source.read_text())
    assert doc["status"]=="PASS" and doc["actual_original_v5_scorer_and_selection_archival_parity"]
    teacher.audit()
    assert ref.SPEC["beam"]==160
    case=doc["case"];stage=int(case["stage"]);seat=int(case["seat"])
    canon_seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
    check_seat,orders=ref.stage_slots(canon_seed)
    assert seat==check_seat
    seven=[ref.SLOT_VARIANTS["one_key_34"][x] for x in orders[stage][:7]]
    unknown=tuple(ref.SLOT_VARIANTS["one_key_34"][x] for x in orders[stage][7:])
    assert seven==case["seven"] and len(unknown)==92
    scores={}
    for c in doc["candidates"]:
        idx=int(c["structural_candidate_index"])
        hand=tuple(c["hand"]);bottom=tuple(c["bottom"])
        assert Counter(hand)+Counter(bottom)==Counter(seven)
        turns=[]
        for future in range(N):
            hidden=list(unknown)
            random.Random(seed("v43_new_blind_physical_unseen_92",gid,stage,future)).shuffle(hidden)
            ref.sim.reset_caches();ref.sim.root.install("one_key_34")
            ref.sim.m.set_trial_seed(seed("v43_new_blind_common_chance",gid,stage,future))
            ref.d._WIN_CACHE.clear()
            v=ref.d._win_turn_from_unknown_order(hand,tuple(hidden)+bottom,seat,beam=160,max_turn=3)
            assert v is None or v in (0,1,2,3)
            turns.append(int(v or 0))
        scores[str(idx)]={
           "hand":list(hand),"bottom":list(bottom),"turns":turns,
           "by_T1":sum(t==1 for t in turns),
           "by_T2":sum(t in (1,2) for t in turns),
           "by_T3":sum(t in (1,2,3) for t in turns),
           "physical_U_T2_plus_half_exactT3":(
              sum(t in (1,2) for t in turns)+.5*sum(t==3 for t in turns))/N,
           "original_teacher_U8":c["full_unpruned_original_ev"]["8"]["U"],
           "original_teacher_U16":c["full_unpruned_original_ev"].get("16",{}).get("U"),
           "frozen_v27_Q2":c["v27_and_other_candidate_scores"]["Qkeep_T2"],
        }
        print("DACK_V43_NEW_PHYSICAL_CHOICE",gid,stage,idx,
              "T2",scores[str(idx)]["by_T2"],"of",N,
              "teacher_U8",scores[str(idx)]["original_teacher_U8"],flush=True)
    return {
      "schema":SCHEMA,"status":"PASS","gid":gid,"seat":seat,"stage":stage,
      "physical_futures_per_candidate":N,
      "candidate_count":len(scores),"candidate_results":scores,
      "selected_original_v5":case["v5_selected_candidate"],
      "selected_frozen_v14":case["v27_selected_candidate"],
      "selected_frozen_v27_Q2_max":case["other_learned_candidate_rankers"]["v27_Qkeep"],
      "teacher_v5_uses_original_8_16_sample_beam60":True,
      "new_physical_16_futures_blind_unseen92_beam160":True,
      "same_hidden92_per_future_across_candidates":True,
      "same_stateless_chance_seed_per_future_across_candidates":True,
      "not_population_random_sevens":True,
      "not_a_new_mulligan_policy":True,
    }

def run(gid,out):
    doc=evaluate(gid)
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print("DACK_V43_INDEPENDENT_CANDIDATE_PHYSICAL_RECHECK_PASS",gid,flush=True)

if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--gid",type=int,required=True);a.add_argument("--out",required=True)
    z=a.parse_args();run(z.gid,z.out)
