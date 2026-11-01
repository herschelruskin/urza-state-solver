#!/usr/bin/env python3
"""v42 verify same-final-stage vs bottom difference outcome attribution.

No new gameplay. Same physical seat, initial shuffle, rules and stable dice
are assumed as archived; if final kept hand AND ordered bottom agree, the
strict terminal turn MUST match across policies. Fail loudly otherwise.
"""
import gzip,glob,json
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SCHEMA="dack_v42_115k_keep_stage_bottom_outcome_decomposition_v1"
def by(turn,h):return int(0<int(turn)<=h)
def run(out):
    files=sorted(glob.glob(str(ROOT/"benchmark_results/v33b_prospective_115k_shards/v33b_115k_*.json.gz")))
    assert len(files)==64
    rows=[]
    for p in files:
        with gzip.open(p,"rt") as f:z=json.load(f)
        assert z["schema"]=="dack_v33b_prospective_115k_three_policy_strict"
        assert z["status"]=="PASS" and z["strict_gameplay_beam"]==160
        assert z["v27_v33b_identical_london_stages_and_keep_actions"]
        rows+=z["rows"]
    rows.sort(key=lambda z:z["game_id"])
    assert [r["game_id"] for r in rows]==list(range(115000,115256))
    groups=defaultdict(list)
    bad=[]
    for r in rows:
        v5=r["v5"];v27=r["v27_frozen"];v33=r["v33b_regret_bottom"]
        assert v5["seat"]==v27["seat"]==v33["seat"]
        assert v27["history"][-1]["stage"]==v33["history"][-1]["stage"]
        same_stage=v5["history"][-1]["stage"]==v27["history"][-1]["stage"]
        h5=v5["history"][-1];h27=v27["history"][-1];h33=v33["history"][-1]
        same_h5_27=(Counter(h5["hand"])==Counter(h27["hand"]) and
                    tuple(h5["bottom"])==tuple(h27["bottom"]))
        same_h5_33=(Counter(h5["hand"])==Counter(h33["hand"]) and
                    tuple(h5["bottom"])==tuple(h33["bottom"]))
        if same_stage and same_h5_27 and v5["turn"]!=v27["turn"]:
            bad.append({"gid":r["game_id"],"pair":"v5-v27","v5":v5["turn"],"other":v27["turn"]})
        if same_stage and same_h5_33 and v5["turn"]!=v33["turn"]:
            bad.append({"gid":r["game_id"],"pair":"v5-v33b","v5":v5["turn"],"other":v33["turn"]})
        if same_stage and same_h5_27:
            key="same_stage_identical_v5_v27_final_hand_and_bottom"
        elif same_stage:
            key="same_stage_different_v5_v27_final_hand_or_bottom"
        else:key="different_final_stage"
        if same_stage and v5["history"][-1]["keep_n"]>=7:
            assert same_h5_27
        if same_stage and v5["history"][-1]["keep_n"]<=6:
            groups["same_stage_bottom_eligible"].append(r)
        groups[key].append(r)
        if same_stage and same_h5_33:
            groups["same_stage_identical_v5_v33b_final_hand_and_bottom"].append(r)
        if same_stage and not same_h5_33:
            groups["same_stage_different_v5_v33b_final_hand_or_bottom"].append(r)
    if bad:raise AssertionError(("GAMEPLAY PARITY FAIL, identical final hand and seat",bad[:8]))
    metrics={}
    for kind,rr in groups.items():
        diff={}
        for other in ("v27_frozen","v33b_regret_bottom"):
            for horizon in (1,2,3):
                d=[by(r["v5"]["turn"],horizon)-by(r[other]["turn"],horizon)
                   for r in rr]
                diff[f"v5_minus_{other}_byT{horizon}_games"]=sum(d)
                diff[f"v5_minus_{other}_byT{horizon}_gains"]=d.count(1)
                diff[f"v5_minus_{other}_byT{horizon}_losses"]=d.count(-1)
        metrics[kind]={"N_games":len(rr),**diff}
    assert metrics["same_stage_identical_v5_v27_final_hand_and_bottom"]["v5_minus_v27_frozen_byT2_games"]==0
    assert metrics["same_stage_identical_v5_v33b_final_hand_and_bottom"]["v5_minus_v33b_regret_bottom_byT2_games"]==0
    assert sum(metrics[k]["N_games"] for k in (
      "same_stage_identical_v5_v27_final_hand_and_bottom",
      "same_stage_different_v5_v27_final_hand_or_bottom",
      "different_final_stage"))==256
    result={
      "schema":SCHEMA,"status":"PASS","N":256,
      "exact_same_kept_hand_bottom_gameplay_parity_proven":True,
      "source_115k_already_consumed":True,
      "no_new_gameplay_or_policy":True,
      "not_causal_attribution_on_different_final_stage":True,
      "metrics":metrics,
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("DACK_V42_SAME_STAGE_BOTTOM_PHY_GAME_PARITY_PASS",json.dumps(metrics,sort_keys=True),flush=True)
if __name__=="__main__":
    run(ROOT/"benchmark_results/v42_115k_bottom_vs_stage_split.json")
