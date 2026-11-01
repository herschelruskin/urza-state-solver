#!/usr/bin/env python3
"""Pool controlled v29 chance-coupling metamorphic audit across fixed scenarios."""
import collections,gzip,glob,json
from pathlib import Path

def main():
    files=sorted(glob.glob("collected/v29_*.json.gz"))
    assert len(files)==4,(len(files),files)
    out={}
    for path in files:
        with gzip.open(path,"rt") as f:data=json.load(f)
        assert data["schema"]=="dack_v29_neutral_bottom_candidate_chance_coupling"
        assert data["status"]=="PASS" and data["n_games"]==12
        scenario=data["scenario"]
        assert scenario not in out
        assert data["unknown_92_identical_across_bottoms"]
        assert data["diagnostic_mode_NOT_approved"]
        # Cumulative by-T2 and by-T3. This test is tiny and is not a winrate
        # estimator; purpose is metamorphic invariance only.
        bymode={}
        for mode in ("original_full_state_dice","coupled_filler_dice"):
            a=collections.defaultdict(lambda:collections.Counter())
            for row in data["results"]:
                for item in row["alternatives"][mode]:
                    keep=item["keep_blank"];turn=item["turn"]
                    a[keep]["T1"]+=int(turn==1)
                    a[keep]["T2"]+=int(0<turn<=2)
                    a[keep]["T3"]+=int(0<turn<=3)
            bymode[mode]=dict(a)
        out[scenario]={
            "n":12,
            "reference_core":data["fixed_visible_core"],
            "original_turn_all_equal":data["original_dice_all_equal_n"],
            "coupled_turn_all_equal":data["coupled_dice_all_equal_n"],
            "original_turn_differ":data["original_dice_turn_disagreement_n"],
            "coupled_turn_differ":data["coupled_dice_turn_disagreement_n"],
            "by_keep_blank_and_mode":bymode,
            "per_game_original_and_coupled_turn_triplets":[
                {"game_id":r["game_id"],"original":r["original_dice_turns"],
                 "coupled":r["coupled_dice_turns"]} for r in data["results"]
            ],
        }
    assert set(out)=={
       "bucknard_key","mana_vault_tutor","mox_opal_exception","chrome_mox_exception"}
    report={
       "schema":"dack_v29_neutral_bottom_metamorphic_N48",
       "status":"PASS",
       "n_independent_future_orders_per_scenario":12,
       "n_scenarios":4,
       "simulations":4*12*3*2,
       "scenario_results":out,
       "protected_v5_v14_v26_v27_unchanged":True,
       "no_model_training":True,
       "warning":"A single card may be non-ramp but still relevant to imprints, artifacts, tutor access, defensive effects, or search pruning. Research-only chance coupling is an audit, NOT validated gameplay. Do not treat these 48 designed states as random game winrates.",
    }
    dest=Path("benchmark_results/v29_neutral_bottom_metamorphic_N48.json")
    dest.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("DACK_V29_NEUTRAL_BOTTOM_POOL_PASS",json.dumps({
         "scenarios":{n:{k:v[k] for k in (
            "original_turn_differ","coupled_turn_differ","original_turn_all_equal",
            "coupled_turn_all_equal")} for n,v in out.items()},
         "simulations":report["simulations"]
    },sort_keys=True),flush=True)

if __name__=="__main__":
    main()
