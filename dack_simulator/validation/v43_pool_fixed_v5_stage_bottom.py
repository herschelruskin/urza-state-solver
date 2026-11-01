#!/usr/bin/env python3
"""Pool genuine fixed-stage v5 vs v14-bottom N256 physical 115k hybrid."""
import glob,gzip,json,random
from pathlib import Path
N=256
def passed(t,h):return int(0<int(t)<=h)
def run():
    paths=sorted(glob.glob("collected/v43_v5stage_v14bottom_*.json.gz"))
    assert len(paths)==8
    a=[]
    for p in paths:
        with gzip.open(p,"rt") as f:d=json.load(f)
        assert d["schema"]=="dack_v43_fixed_original_v5_stage_v14_bottom_physical_hybrid_1"
        assert d["status"]=="PASS" and d["exact_original_v5_terminal_win_parity_per_game"]
        assert d["unchanged_original_v5_keep_stage"]
        assert d["uses_only_legal_visible_cards_for_bottom_decision"]
        a.extend(d["results"])
    a.sort(key=lambda x:x["game_id"])
    assert [x["game_id"] for x in a]==list(range(115000,115256))
    diff={}
    for label in ("v5_stage_plus_v14_bottom_win_turn","original_v27_final_turn","original_v33b_final_turn"):
        e={}
        for h in (1,2,3):
            d=[passed(x[label],h)-passed(x["original_v5_win_turn_replayed"],h) for x in a]
            rng=random.Random(430000+h+sum(ord(c) for c in label))
            bs=sorted(100*sum(d[rng.randrange(N)] for _ in range(N))/N for _ in range(7000))
            e[f"by_T{h}"]={
              "count":sum(passed(x[label],h) for x in a),
              "delta_vs_original_v5_pp":100*sum(d)/N,
              "positive_games":d.count(1),"negative_games":d.count(-1),
              "paired_bootstrap_95ci_pp":[bs[174],bs[6824]],
            }
        diff[label]=e
    original={f"by_T{h}":sum(passed(x["original_v5_win_turn_replayed"],h) for x in a) for h in (1,2,3)}
    changes=[x for x in a if x["bottom_changed_only"]]
    for r in a:
        if not r["bottom_changed_only"]:
            assert r["v5_stage_plus_v14_bottom_win_turn"]==r["original_v5_win_turn_replayed"]
    result={
      "schema":"dack_v43_115k_fixed_original_v5_stage_hybrid_N256",
      "status":"PASS","independent_physical_outer_groups":N,
      "original_archived_v5_replay_exact_parity":True,
      "experiment_is_bottom_only_at_same_v5_keep_stage":True,
      "no_original_v5_beam_recalculation":True,
      "past_cohort_NOT_new_prospective_validation":True,
      "original_v5_by_turn":original,
      "frozen_v14_bottom_at_v5_stage":diff["v5_stage_plus_v14_bottom_win_turn"],
      "other_existing_polices":{k:v for k,v in diff.items() if k!="v5_stage_plus_v14_bottom_win_turn"},
      "bottom_changed_games":len(changes),
      "bottom_changed_v14_T2_better":sum(passed(x["v5_stage_plus_v14_bottom_win_turn"],2)>passed(x["original_v5_win_turn_replayed"],2) for x in changes),
      "bottom_changed_v5_T2_better":sum(passed(x["v5_stage_plus_v14_bottom_win_turn"],2)<passed(x["original_v5_win_turn_replayed"],2) for x in changes),
      "cross_component_interaction_not_estimated":True,
    }
    p=Path("benchmark_results/v43_fixed_v5_stage_v14_bottom_N256.json")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("DACK_V43_FIXED_V5_STAGE_V14_BOTTOM_REAL_N256_PASS",json.dumps(result,sort_keys=True),flush=True)
if __name__=="__main__":run()
