#!/usr/bin/env python3
"""v45 read-only residual T2 gap: original v5 vs coupled v43 SAME 151k N128.

All real original-v5 and v43 physical outcomes were already obtained in v43.
No physical gameplay, training, or new future information is used. Pure
matched-seed audit of the remaining eight-game v5-v43 by-T2 advantage.

Disjoint observed comparison strata:
  A same London kept stage, same selected hand and bottom => parity
  B same kept stage but different bottom/hand => bottom-associated outcome
  C different kept stage => stage-and-possibly-hand-associated outcome
Neither B nor C is claimed to be a universal causal treatment effect.
"""
from __future__ import annotations
import gzip,glob,json
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SCHEMA="dack_v45_original_v5_vs_coupled_v43_matched_151k_N128_residual_audit"
def by(t,h):return int(0<int(t)<=h)
def load():
    a={}
    for path in sorted(glob.glob(str(ROOT/"benchmark_results/v43_v5_151k_N128_shards/v43_original_v5_151k_*.json.gz"))):
        with gzip.open(path,"rt") as g:x=json.load(g)
        assert x["schema"]=="dack_v43_same_151k_original_v5_reference_N128_shard"
        assert x["status"]=="PASS" and x["original_v5_with_no_modifications"]
        for r in x["rows"]:
            gid=r["game_id"]
            assert gid not in a
            a[gid]=r
    b={}
    for path in sorted(glob.glob(str(ROOT/"benchmark_results/v43_fresh_151k_maxQ2_shards/v43_151k_*.json.gz"))):
        with gzip.open(path,"rt") as g:x=json.load(g)
        assert x["schema"]=="dack_v43_fresh_151k_v27_vs_maxQ2_N256_paired_shard"
        assert x["status"]=="PASS" and x["strict_physical_99_beam160"]
        for r in x["rows"]:
            gid=r["gid"]
            if 151000<=gid<151128:
                assert gid not in b
                b[gid]=r["maxQ2"]
    assert set(a)==set(b)==set(range(151000,151128))
    return a,b

def run(out):
    va,vb=load()
    groups=defaultdict(list);first=defaultdict(Counter)
    records=[]
    for gid in sorted(va):
        a=va[gid];b=vb[gid]
        assert a["seat"]==b["seat"]
        h5=a["history"];h43=b["history"]
        assert h5 and h43 and h5[-1]["kept"] and h43[-1]["kept"]
        assert [r["stage"] for r in h5]==list(range(len(h5)))
        assert [r["stage"] for r in h43]==list(range(len(h43)))
        assert h5[0]["seven_slots"]==h43[0]["seven_slots"]
        assert h5[0]["seven"]==h43[0]["seven"]
        s5=h5[-1]["stage"];s43=h43[-1]["stage"]
        stage=min(s5,s43)
        if s5==s43:
            same=(h5[-1]["hand"]==h43[-1]["hand"] and
                  h5[-1]["bottom"]==h43[-1]["bottom"])
            typ=("same_stage_same_final_hand_bottom" if same
                 else "same_stage_different_bottom")
            if same:
                assert a["turn"]==b["turn"],("identical hand parity failure",gid)
            direction="same_stage"
        else:
            typ="different_keep_stage"
            direction=("v5_earlier" if s5<s43 else "v43_earlier")
            assert h5[stage]["seven"]==h43[stage]["seven"]
            assert h5[stage]["seven_slots"]==h43[stage]["seven_slots"]
            assert h5[stage]["kept"]!=h43[stage]["kept"]
        first[stage][direction]+=1
        rec={
          "gid":gid,"seat":a["seat"],"first_conflict_stage":stage,
          "last_stage_v5":s5,"last_stage_v43":s43,
          "comparison_stratum":typ,
          "stage_direction":direction,
          "v5_keep_on_first_comparable_stage":bool(h5[stage]["kept"]),
          "v43_keep_on_first_comparable_stage":bool(h43[stage]["kept"]),
          "v5_original_hand":h5[-1]["hand"],
          "v5_original_bottom":h5[-1]["bottom"],
          "v43_hand":h43[-1]["hand"],
          "v43_bottom":h43[-1]["bottom"],
          "turn_v5":a["turn"],"turn_v43":b["turn"],
          "v5_only_T2":by(a["turn"],2)==1 and by(b["turn"],2)==0,
          "v43_only_T2":by(a["turn"],2)==0 and by(b["turn"],2)==1,
        }
        records.append(rec);groups[typ].append(rec);groups[direction].append(rec)
    def stats(items):
        n=len(items)
        out={"N_physical_outer_groups":n}
        for h in (1,2,3):
            d=[by(r["turn_v5"],h)-by(r["turn_v43"],h) for r in items]
            out[f"v5_minus_v43_byT{h}_net_games"]=sum(d)
            out[f"v5_only_byT{h}"]=d.count(1)
            out[f"v43_only_byT{h}"]=d.count(-1)
        return out
    s={name:stats(rows) for name,rows in groups.items()}
    total=stats(records)
    assert len(records)==128
    assert total["v5_minus_v43_byT2_net_games"]==8
    assert (s["same_stage_same_final_hand_bottom"]["v5_minus_v43_byT2_net_games"]==0)
    for h in (1,2,3):
        assert sum(s[k][f"v5_minus_v43_byT{h}_net_games"]
                   for k in ("same_stage_same_final_hand_bottom",
                             "same_stage_different_bottom",
                             "different_keep_stage"))==total[f"v5_minus_v43_byT{h}_net_games"]
    strong=[r for r in records if r["v5_only_T2"] or r["v43_only_T2"]]
    report={
      "schema":SCHEMA,"status":"PASS",
      "old_151k_cohort_already_inspected_not_fresh_acceptance":True,
      "all_real_strict_beam160_deployment_outcomes_matched_by_99slot_game_id":True,
      "no_new_v5_or_student_gameplay":True,
      "no_model_training_or_selection":True,
      "identical_final_hand_has_exact_terminal_parity":True,
      "outcome_is_goldfish_Dack_deployment_not_multiplayer_win":True,
      "N_matched_games":128,
      "v5_original_byT2":sum(by(r["turn_v5"],2) for r in records),
      "v43_coupled_byT2":sum(by(r["turn_v43"],2) for r in records),
      "total":total,"strata":s,
      "first_comparable_stage_by_direction":{str(k):dict(v) for k,v in sorted(first.items())},
      "T2_discordant_outers":strong,
      "all_records":records,
      "warning":"This is a selected same-seed outcome decomposition, not causal identification of exact bottom and stage effects.",
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("DACK_V45_ORIGINAL_V5_V43_RESIDUAL_N128_STRICT_PARITY_PASS",
       json.dumps({"total":total,"strata":s,
                    "first_stage":report["first_comparable_stage_by_direction"],
                    "N_T2_discordant_outers":len(strong)},sort_keys=True),flush=True)

if __name__=="__main__":
    run(ROOT/"benchmark_results/v45_v5_v43_remaining_T2_gap_same151k_N128.json")
