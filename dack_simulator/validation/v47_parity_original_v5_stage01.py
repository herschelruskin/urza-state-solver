#!/usr/bin/env python3
"""Original archived 151000..151015 v5 first-two-seven exact parity pilot.

Uses original v5 physical seven and stable dice. Compare recorded raw U,
T1, threshold, KEEP decision and legal hand at every *actually reached*
stage0/1, then measure hybrid full-game terminal. Historical 151k is
already inspected and used ONLY for engineering parity, not acceptance.
"""
import gzip,json,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import dack_paired_counterfactual_v47_v5_early_two_sevens_20261101 as v47

ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/"benchmark_results/v43_v5_151k_N128_shards/v43_original_v5_151k_151000.json.gz"
def run():
    with gzip.open(SRC,"rt") as f:src=json.load(f)
    assert src["status"]=="PASS"
    assert src["schema"]=="dack_v43_same_151k_original_v5_reference_N128_shard"
    assert [r["game_id"] for r in src["rows"]]==list(range(151000,151016))
    v47.audit()
    orig={r["game_id"]:r for r in src["rows"]}
    stats={"n":0,"v5_stage0_keep":0,"v5_stage1_keep":0,
      "stage1_naturally_reached":0,"original_v5_raw_threshold_t1_parity":True,
      "v47_byT1":0,"v47_byT2":0,"v47_byT3":0,"original_v5_byT2":0}
    t0=time.perf_counter()
    for gid,r in orig.items():
        x=v47.ref.game("one_key_34",gid)
        teacher=r["history"];hybrid=x["history"]
        assert teacher[0]["seven"]==hybrid[0]["seven"]
        stats["stage1_naturally_reached"]+=int(len(teacher)>1)
        for stage in (0,1):
            if stage>=len(teacher):break
            a=teacher[stage];b=hybrid[stage]
            for key in ("stage","keep_n","kept","seven","seven_slots","hand","bottom","refined"):
                assert a[key]==b[key],("true original-v5 early stage parity",gid,stage,key,a[key],b[key])
            for key in ("raw","threshold","sampled_t1"):
                assert abs(float(a[key])-float(b[key]))<=1e-7,(gid,stage,key,a[key],b[key])
            assert b["policy_provenance"]=="original_v5_true_gameplay_value"
            if stage==0:stats["v5_stage0_keep"]+=int(b["kept"])
            if stage==1:stats["v5_stage1_keep"]+=int(b["kept"])
        assert x["win_turn"] in (0,1,2,3)
        stats["n"]+=1
        stats["v47_byT1"]+=int(x["win_turn"]==1)
        stats["v47_byT2"]+=int(0<x["win_turn"]<=2)
        stats["v47_byT3"]+=int(0<x["win_turn"]<=3)
        stats["original_v5_byT2"]+=int(0<r["turn"]<=2)
        print("DACK_V47_REAL_ORIGINAL_V5_STAGE01_PARITY",gid,
              "orig_v5",r["turn"],"hybrid",x["win_turn"],flush=True)
    assert stats["n"]==16
    print("DACK_V47_ORIGINAL_V5_STAGE01_EXACT_ARCHIVED_PARITY_PASS",
        json.dumps({**stats,"whole_pilot_seconds":round(time.perf_counter()-t0,3)},sort_keys=True),flush=True)
if __name__=="__main__":run()
