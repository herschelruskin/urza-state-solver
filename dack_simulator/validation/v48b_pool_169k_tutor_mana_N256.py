#!/usr/bin/env python3
"""Pool independent 169k N256 tutor-guaranteed physical validation; do not fit.

Compare the new legally tutored no-unknown-draw witness against the previous
strict no-library-change mana witness on the exact same physical deals.
"""
from __future__ import annotations
import argparse,gzip,json,statistics
from pathlib import Path
N=256;START=169000
def main(folder,out):
    paths=sorted(Path(folder).glob("mana169k_*.json.gz"))
    assert len(paths)==8,(len(paths),paths)
    rows=[]
    for p in paths:
        with gzip.open(p,"rt") as f:x=json.load(f)
        assert x["status"]=="PASS" and x["source_deals"]==32
        assert x["schema"]=="dack_v48b_169k_verified_guaranteed_tutor_vs_no_tutor_firstseven_physical_N256"
        rows+=x["rows"]
    rows.sort(key=lambda r:r["gid"])
    assert [r["gid"] for r in rows]==list(range(START,START+N))
    obs=[]
    for turn in (1,2):
        oldkey="mana_witness_T"+str(turn)+"_no_draw"
        newkey="T"+str(turn)+"_tutor_legal_no_draw_witness"
        old=[r for r in rows if r["feat"][oldkey]]
        new=[r for r in rows if r["tutor_feat"][newkey]]
        added=[r for r in rows if r["tutor_feat"][newkey] and not r["feat"][oldkey]]
        lost=[r for r in rows if r["feat"][oldkey] and not r["tutor_feat"][newkey]]
        actual=lambda x:sum(0<r["physical_forced_keep_turn"]<=turn for r in x)
        obs.append({"turn":turn,"old_witness_n":len(old),"new_witness_n":len(new),
           "extra_witnesses_n":len(added),"old_witness_successes":actual(old),
           "new_witness_successes":actual(new),
           "extra_witness_successes":actual(added),
           "extra_witness_failures":len(added)-actual(added),
           "lost_witnesses_from_bounded_beam_n":len(lost),
           "lost_witness_successes":actual(lost),
           "actual_physical_deployments":actual(rows),
           "new_witnesses_with_tutor_used_n":sum(
              r["tutor_feat"].get("T"+str(turn)+"_tutor_count_in_witness",0) not in (None,0)
              for r in new),
           "added_cases":[{"gid":r["gid"],"seven":r["seven"],"seat":r["seat"],
                "physical_turn":r["physical_forced_keep_turn"],"Q2":r["stage0_Q2"],
                "tutors":r["tutor_feat"]["T"+str(turn)+"_tutor_count_in_witness"]}
                         for r in added],
           "lost_cases":[{"gid":r["gid"],"Q2":r["stage0_Q2"],
               "seven":r["seven"],"physical_turn":r["physical_forced_keep_turn"]}
                          for r in lost]})
    outv={"schema":"dack_v48b_guaranteed_tutor_vs_no_tutor_firstseven_N256_screen_v1",
       "status":"PASS","N_independent_outer_deals":N,"gids":[START,START+N-1],
       "per_turn":obs,
       "original_v43_model_and_rules_frozen":True,
       "not_a_new_fast_mulligan_policy":True,
       "no_hidden_future_order_in_feature_inputs":True,
       "mean_base_seconds":statistics.mean(r["feature_seconds"] for r in rows),
       "mean_tutor_seconds":statistics.mean(r["tutor_feature_seconds"] for r in rows),
       "physical_T1":sum(r["physical_forced_keep_byT1"] for r in rows),
       "physical_T2":sum(r["physical_forced_keep_byT2"] for r in rows),
       "untouched_155k_unopened":True,"no_model_fit":True,"rows":rows}
    target=Path(out);target.parent.mkdir(exist_ok=True,parents=True)
    target.write_text(json.dumps(outv,indent=2,sort_keys=True)+"\n")
    print("DACK_V48B_169K_N256_TUTOR_SCREEN_PASS",json.dumps({
      k:outv[k] for k in ("N_independent_outer_deals","per_turn",
        "mean_base_seconds","mean_tutor_seconds","physical_T1","physical_T2")},sort_keys=True),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--folder",required=True);p.add_argument("--out",required=True)
    z=p.parse_args();main(z.folder,z.out)
