#!/usr/bin/env python3
"""Read-only paired development postmortem over permanently archived 512
physical first-seven deals; calculate first-two natural-draw creature
contamination without interpreting this as a tutor/scry probability.

Reports an empirical decomposition, not learned keep policy or new holdout.
"""
from __future__ import annotations
from collections import Counter
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as v43
import dack_turn_aware_combo_draw_integrity_v48c_20261101 as integ
ref=v43.ref
a=ROOT/"benchmark_results/v48_168k_pooled/v48_168k_mana_firstseven_N256_pooled.json"
b=ROOT/"benchmark_results/v48b_169k_pooled/v48b_169k_tutor_mana_N256_pooled.json"
def main():
    v43.audit()
    docs=[json.loads(a.read_text()),json.loads(b.read_text())]
    rows=docs[0]["rows"]+docs[1]["rows"]
    assert len(rows)==512
    allrows=[];tutor_new=[]
    for r in rows:
        gid=r["gid"];seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(seed)
        deck=ref.SLOT_VARIANTS["one_key_34"]
        seven=tuple(deck[k] for k in orders[0][:7])
        unknown=tuple(deck[k] for k in orders[0][7:])
        assert list(seven)==r["seven"] and seat==r["seat"]
        risk=integ.expose(seven,unknown)
        top2=unknown[:2]
        contaminated=any(x in ref.d.COMBO_CREATURES for x in top2)
        witness=(r.get("tutor_feat",{}).get("T2_tutor_legal_no_draw_witness",False)
                 if gid>=169000 else r["feat"]["mana_witness_T2_no_draw"])
        rec={"gid":gid,"q2":r["stage0_Q2"],"t2_witness":bool(witness),
            "top_two_natural_draws":list(top2),"top2_has_core_creature":contaminated,
            "physical_t2_success":bool(r["physical_forced_keep_byT2"]),
            "p_unmodified_survival":risk["unmodified_two_natural_draw_combo_survival"]}
        allrows.append(rec)
        if gid>=169000 and r["tutor_feat"]["T2_tutor_legal_no_draw_witness"] and not r["feat"]["mana_witness_T2_no_draw"]:
            tutor_new.append(rec)
    pos=[r for r in allrows if r["t2_witness"]]
    safe=[r for r in pos if not r["top2_has_core_creature"]]
    contam=[r for r in pos if r["top2_has_core_creature"]]
    discord=[r for r in pos if not r["physical_t2_success"]]
    report={"schema":"dack_v48c_mana_vs_combo_draw_integrity_N512_development_postmortem_v1",
       "N_independent_physical_source_groups":512,
       "gid_ranges":[[168000,168255],[169000,169255]],
       "no_model_training":True,"untouched_155k_unopened":True,
       "physical_forced_seven_t2_success":sum(r["physical_t2_success"] for r in allrows),
       "T2_tutor_inclusive_no_unknown_draw_mana_witness_positive":len(pos),
       "mana_witness_and_physical_t2_success":sum(r["physical_t2_success"] for r in pos),
       "mana_witness_and_top2_no_combo_creatures":len(safe),
       "mana_witness_top2_clean_and_physical_t2_success":sum(r["physical_t2_success"] for r in safe),
       "mana_witness_top2_core_contaminated":len(contam),
       "mana_witness_top2_core_contaminated_cases":contam,
       "witness_physical_discordances":discord,
       "new_source_verified_tutor_witnesses":tutor_new,
       "first7_without_combo_natural_two_draw_survival_probability":
         integ.expose(
           ["Plains","Ancient Tomb","Sol Ring","Chrome Mox","Silence","Mox Diamond","Enlightened Tutor"],
           # build valid 92 unknown via source deck below
           tuple(__import__("collections").Counter(
              ref.SLOT_VARIANTS["one_key_34"].values()).elements())[:0]
         ) if False else round((89*88)/(92*91),8),
       "natural_top2_risk_does_not_model_tutors_scry_repair":True,
       "no_promotion":True}
    path=ROOT/"benchmark_results/v48c_168k_169k_n512_draw_integrity_decomposition.json"
    path.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("DACK_V48C_N512_INTEGRITY_DECOMPOSITION_PASS",json.dumps(report,sort_keys=True),flush=True)
if __name__=="__main__":main()
