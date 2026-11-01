#!/usr/bin/env python3
"""Stage vs bottom decomposition of v43 coupling gain on fresh 151k N256.
The contrast is observable full-game stage and hand selection, not an
identification of counterfactual causal effects when stages diverge.
"""
import glob,gzip,json
from collections import defaultdict,Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def by(t,h):return int(0<int(t)<=h)
def run():
    ps=sorted(glob.glob(str(ROOT/"benchmark_results/v43_fresh_151k_maxQ2_shards/v43_151k_*.json.gz")))
    assert len(ps)==8
    rr=[]
    for p in ps:
        with gzip.open(p,"rt") as f:z=json.load(f)
        assert z["schema"]=="dack_v43_fresh_151k_v27_vs_maxQ2_N256_paired_shard"
        assert z["status"]=="PASS" and z["strict_physical_99_beam160"]
        rr+=z["rows"]
    rr.sort(key=lambda x:x["gid"])
    assert [x["gid"] for x in rr]==list(range(151000,151256))
    parts=defaultdict(list)
    for r in rr:
        a=r["v27"];b=r["maxQ2"]
        sa=int(a["history"][-1]["stage"]);sb=int(b["history"][-1]["stage"])
        assert a["seat"]==b["seat"]
        same_hand=(Counter(a["history"][-1]["hand"])==Counter(b["history"][-1]["hand"])
            and tuple(a["history"][-1]["bottom"])==tuple(b["history"][-1]["bottom"]))
        if sa!=sb:
            key="different_final_london_stage"
        elif same_hand:
            key="identical_final_stage_hand_bottom"
            assert a["turn"]==b["turn"]
        else:
            key="same_final_stage_different_bottom"
        parts[key].append(r)
        if sa<sb:parts["v27_kept_earlier"].append(r)
        if sb<sa:parts["maxQ2_kept_earlier"].append(r)
    result={}
    for key,items in parts.items():
        result[key]={"N":len(items)}
        for h in (1,2,3):
            diffs=[by(r["maxQ2"]["turn"],h)-by(r["v27"]["turn"],h) for r in items]
            result[key][f"T{h}_net_game_gain"]=sum(diffs)
            result[key][f"T{h}_gains"]=diffs.count(1)
            result[key][f"T{h}_losses"]=diffs.count(-1)
    assert sum(result[k]["N"] for k in (
       "different_final_london_stage",
       "identical_final_stage_hand_bottom",
       "same_final_stage_different_bottom"))==256
    assert result["identical_final_stage_hand_bottom"]["T2_net_game_gain"]==0
    assert (result["different_final_london_stage"]["T2_net_game_gain"]+
            result["same_final_stage_different_bottom"]["T2_net_game_gain"])==11
    o={
      "schema":"dack_v43_151k_coupled_candidate_gain_stage_bottom_descriptive_split",
      "status":"PASS","N":256,
      "strict_identical_final_hand_gameplay_parity":True,
      "purely_descriptive_noncausal_between_selection_groups":True,
      "new_151k_already_inspected_not_sealed":True,
      "groups":result
    }
    p=ROOT/"benchmark_results/v43_151k_maxQ2_stage_bottom_outcome_split.json"
    p.write_text(json.dumps(o,indent=2,sort_keys=True)+"\n")
    print("DACK_V43_NEW151K_STAGE_BOTTOM_GAIN_SPLIT_PASS",json.dumps(o,sort_keys=True),flush=True)
if __name__=="__main__":run()
