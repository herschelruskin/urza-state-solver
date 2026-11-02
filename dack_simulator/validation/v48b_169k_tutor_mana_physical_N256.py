#!/usr/bin/env python3
"""Fresh disjoint v48b verified-tutor/no-draw vs no-tutor witness matched
to physical forced-first-seven goldfish on 169000..169255. Zero policy
changes or training and does not examine prior 168k outcomes for actions.
"""
from __future__ import annotations
import argparse,gzip,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dack_simulator.validation import v48_firstseven_168k_turn_mana_physical_N256 as prior
import dack_turn_aware_mana_tutor_guaranteed_v48b_20261101 as tutor
ref=prior.ref
SCHEMA="dack_v48b_169k_verified_guaranteed_tutor_vs_no_tutor_firstseven_physical_N256"
def main(start,out):
    assert start in range(169000,169256,32)
    prior.v43.audit()
    rows=[]
    for gid in range(start,start+32):
        row=prior.record(gid)
        seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(seed)
        deck=ref.SLOT_VARIANTS["one_key_34"]
        seven=tuple(deck[s] for s in orders[0][:7])
        unknown=tuple(deck[s] for s in orders[0][7:])
        t0=time.perf_counter()
        upgraded=tutor.analyze(seven,unknown,seat,beam=32,depth=9)
        cost=time.perf_counter()-t0
        assert upgraded["hand"]==row["feat"]["hand"]
        # Bounded beam search is not monotone: adding tutor branches can
        # crowd an old witness. Record such sensitivity, never assert it away.
        row["tutor_T1_lost_prior_witness"]=bool(
            row["feat"]["mana_witness_T1_no_draw"] and
            not upgraded["T1_tutor_legal_no_draw_witness"])
        row["tutor_T2_lost_prior_witness"]=bool(
            row["feat"]["mana_witness_T2_no_draw"] and
            not upgraded["T2_tutor_legal_no_draw_witness"])
        row["tutor_feat"]=upgraded;row["tutor_feature_seconds"]=cost
        rows.append(row)
        if len(rows)%8==0:
            print("DACK_V48B_169K_PROGRESS",gid,
                "base_witness",sum(x["feat"]["mana_witness_T2_no_draw"] for x in rows),
                "tutor_witness",sum(x["tutor_feat"]["T2_tutor_legal_no_draw_witness"] for x in rows),
                "physical_byT2",sum(x["physical_forced_keep_byT2"] for x in rows),flush=True)
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(dest,"wt") as f:
        json.dump({"schema":SCHEMA,"status":"PASS","source_deals":32,"start":start,
            "same_one_physical_outcome_for_both_feature_extractors":True,
            "source_seat_and_draw_order_shared":True,"actual_hidden_order_not_seen_by_features":True,
            "no_policy_change_or_new_model":True,
            "not_acceptance_155k_preserved":True,"rows":rows},f,sort_keys=True)
    print("DACK_V48B_169K_PHYSICAL_N32_PASS",start,flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--start",type=int,required=True);p.add_argument("--out",required=True)
    a=p.parse_args();main(a.start,a.out)
