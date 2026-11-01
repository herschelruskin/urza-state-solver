#!/usr/bin/env python3
"""v43 independent physical K futures for original v5 vs v14/v27 bottom candidates.

For each selected already-inspected v5/v27 stage2 disagreement, use SAME
seven, same unknown92 card slots, same seat, same 32 *new* random futures and
same stateless chance seed on each arm. v5 and v27 bottoms are frozen in the
validated historical candidate microscope before this physical experiment.
NEVER call original v5 lookahead while selecting a bottom; no hindsight.
This is a stratified retrospective *conditional retained-hand* experiment,
NOT population v5 versus v27 full-game deployment WR.
"""
from __future__ import annotations
import argparse,hashlib,json,random,sys,gzip
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v5_stable_chance_20261031 as teacher
ref=teacher.reference
IDS=(115003,115004,115119,115153)
N=32
SCHEMA="dack_v43_independent_paired_physical_candidate_K_32_v1"

def seed(*parts):
    blob=json.dumps(("v43_candidate_physical_blind_seat_stage",*parts),separators=(",",":")).encode()
    return int.from_bytes(hashlib.sha256(blob).digest()[:8],"big")

def run(gid,out):
    if gid not in IDS:raise ValueError("fixed four selected diagnostic games")
    p=ROOT/f"benchmark_results/v43_candidate_profiles/v43_candidate_{gid}.json"
    record=json.loads(p.read_text())
    assert record["schema"]=="dack_v43_real_original_v5_top12_candidate_profile_v1"
    assert record["status"]=="PASS" and record["game_id"]==gid
    assert record["stage"]==2 and record["keep_n"]==6
    assert record["v5_archived_winner_and_raw_score_reproduced_exactly"]
    assert record["source_historical_115k_previously_inspected"]
    i5=int(record["v5_real_selected_index"])
    i27=int(record["v27_real_selected_index"])
    assert i5!=i27
    teacher.install()
    deck=ref.SLOT_VARIANTS["one_key_34"]
    seat,orders=ref.stage_slots(int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE)
    assert seat==record["seat"]
    stage=record["stage"]
    order=orders[stage]
    seven=tuple(deck[s] for s in order[:7])
    assert seven==tuple(record["opening_seven"])
    unknown_slots=tuple(order[7:])
    assert len(unknown_slots)==92
    assert len(set(order))==99
    candidates=[record["candidate_table"][i] for i in (i5,i27)]
    for c in candidates:
        assert Counter(c["hand"])+Counter(c["bottom"])==Counter(seven)
        assert len(c["hand"])==6 and len(c["bottom"])==1
    rolls=[]
    for j in range(N):
        newslots=list(unknown_slots)
        random.Random(seed(gid,stage,j,"shared_92_slot_shuffle")).shuffle(newslots)
        library_unknown=tuple(deck[s] for s in newslots)
        paired={}
        for name,candidate in (("v5_bottom",candidates[0]),("v27_bottom",candidates[1])):
            ref.sim.reset_caches()
            ref.sim.root.install("one_key_34")
            ref.sim.m.set_trial_seed(seed(gid,stage,j,"common_gameplay_chance"))
            hand=tuple(candidate["hand"])
            bottom=tuple(candidate["bottom"])
            win=ref.d._win_turn_from_unknown_order(
                hand,library_unknown+bottom,seat,beam=160,max_turn=3)
            assert win is None or int(win) in (0,1,2,3)
            paired[name]=int(win or 0)
        rolls.append(paired)
        if (j+1)%8==0:
            print("DACK_V43_PAIRED_BOTTOM_PHYSICAL_PROGRESS",gid,j+1,
                   sum(0<x["v5_bottom"]<=2 for x in rolls),
                   sum(0<x["v27_bottom"]<=2 for x in rolls),flush=True)
    summary={}
    for name in ("v5_bottom","v27_bottom"):
        ts=[q[name] for q in rolls]
        summary[name]={f"byT{h}":sum(0<t<=h for t in ts) for h in (1,2,3)}
        summary[name]["U_T2_plus_half_exactT3"]=(
           summary[name]["byT2"]+.5*(summary[name]["byT3"]-summary[name]["byT2"]))/N
    summary["paired_T2_v5_minus_v27_net"]=summary["v5_bottom"]["byT2"]-summary["v27_bottom"]["byT2"]
    outdata={
     "schema":SCHEMA,"status":"PASS","game_id":gid,"stage":2,
     "seat":seat,"original_profile_sha256":hashlib.sha256(p.read_bytes()).hexdigest(),
     "v5_bottom_index":i5,"v27_bottom_index":i27,
     "v5_hand":candidates[0]["hand"],"v5_bottom":candidates[0]["bottom"],
     "v27_hand":candidates[1]["hand"],"v27_bottom":candidates[1]["bottom"],
     "v5_original_candidate_EV8":candidates[0]["original_sampler_beam60_8"],
     "v27_original_candidate_EV8":candidates[1]["original_sampler_beam60_8"],
     "v5_original_candidate_EV16":candidates[0]["original_sampler_beam60_16"],
     "v27_original_candidate_EV16":candidates[1]["original_sampler_beam60_16"],
     "v27_predicted_T2_for_v5_bottom":candidates[0]["v27_pred_T2_keep_value"],
     "v27_predicted_T2_for_v27_bottom":candidates[1]["v27_pred_T2_keep_value"],
     "physical_K_trials_per_candidate":N,
     "shared_unknown_92_physical_slot_shuffle":True,
     "same_seat_and_stateless_gameplay_seed_within_pair":True,
     "strict_actual_beam160":True,
     "no_teacher_lookahead_or_new_model_training":True,
     "source_historical_disagreement_selection_not_representative":True,
     "model_promoted":False,
     "summary":summary,"pairs":rolls,
    }
    path=Path(out);path.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path,"wt") as f:json.dump(outdata,f,sort_keys=True)
    print("DACK_V43_REAL_PHYSICAL_BOTTOM_32_PAIR_PASS",json.dumps({
      "gid":gid,"summary":summary,"v5_bottom":candidates[0]["bottom"],
      "v27_bottom":candidates[1]["bottom"]},sort_keys=True),flush=True)
if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--gid",type=int,required=True)
    a.add_argument("--out",required=True)
    z=a.parse_args();run(z.gid,z.out)
