#!/usr/bin/env python3
"""Pool new 155k matched frozen v27, v43, v44 strict physical games.

Reports paired group bootstrap 95% uncertainty for T1/T2/T3, and objective
U_exact = PbyT2 + 0.5 P(exactT3). Do not infer actual cEDH multiplayer winrate.
"""
from __future__ import annotations
import glob,gzip,json,random
from pathlib import Path
N=256
POLICIES=("v27","v43","v44")
def by(t,h):return int(0<int(t)<=h)
def util(t):return (1. if 0<t<=2 else (.5 if t==3 else 0.))
def main():
    paths=sorted(glob.glob("collected/v44_155k_*.json.gz"))
    assert len(paths)==8,("need 8 complete physical N32 shards",len(paths))
    rows=[];sha=None
    for path in paths:
        with gzip.open(path,"rt") as gz:q=json.load(gz)
        assert q["schema"]=="dack_v44_first_prospective_physical_155k_three_policy_N256_shard"
        assert q["status"]=="PASS" and q["strict_99_physical_slots_beam160"]
        assert q["same_seats_real_London_sevens_and_stateless_gameplay_chance"]
        assert q["v44_model_immutable_before_155k_test"] and q["no_model_fitting_or_threshold_tuning_on_155k"]
        assert tuple(q["policies"])==POLICIES
        if sha is None:sha=q["models_sha256"]
        assert sha==q["models_sha256"]
        rows+=q["rows"]
    rows.sort(key=lambda r:r["gid"])
    assert [r["gid"] for r in rows]==list(range(155000,155256))
    rates={}
    for policy in POLICIES:
        turns=[r[policy]["turn"] for r in rows]
        rates[policy]={
          f"by_T{h}":sum(by(t,h) for t in turns) for h in (1,2,3)}
        rates[policy]["U_exact"]=round(sum(util(t) for t in turns)/N,6)
        rates[policy]["mean_kept_cards"]=sum(r[policy]["keep_n"] for r in rows)/N
        rates[policy]["total_seconds"]=round(sum(r[policy]["seconds"] for r in rows),3)
    diffs={}
    for old,new in (("v43","v44"),("v27","v44"),("v27","v43")):
        for h in (1,2,3):
            dl=[by(r[new]["turn"],h)-by(r[old]["turn"],h) for r in rows]
            rng=random.Random(155000+h+sum(ord(c) for c in new+old))
            boot=sorted(100*sum(dl[rng.randrange(N)] for _ in range(N))/N
                        for _ in range(10000))
            diffs[f"{new}_minus_{old}_byT{h}"]={
              "net_games":sum(dl),
              "delta_pp":100*sum(dl)/N,
              "new_only_successes":dl.count(1),
              "old_only_successes":dl.count(-1),
              "paired_bootstrap95_pp":[boot[249],boot[9749]],
            }
    # Report change rates and sanity-check equal full end hands.
    end={}
    for old,new in (("v43","v44"),("v27","v44")):
        same=0;different_bottom=0;different_stage=0
        for r in rows:
            a=r[old]["history"][-1];b=r[new]["history"][-1]
            if a["stage"]!=b["stage"]:different_stage+=1
            elif a["hand"]==b["hand"] and a["bottom"]==b["bottom"]:
                same+=1
                assert r[old]["turn"]==r[new]["turn"],(r["gid"],old,new)
            else:different_bottom+=1
        assert same+different_bottom+different_stage==N
        end[f"{new}_vs_{old}"]={
            "same_final_stage_and_hand":same,
            "same_stage_different_bottom":different_bottom,
            "different_final_keep_stage":different_stage,
        }
    data={
     "schema":"dack_v44_actual_physical_candidate_model_155k_new_N256",
     "status":"PASS","N_physical_groups":N,
     "no_future_or_model_tuning_on_155k":True,
     "original_v5_not_run_and_no_claim_parity_to_v5":True,
     "not_multiplayer_cedh_wins":True,
     "frozen_sha256":sha,
     "scores":rates,"paired":diffs,"stage_bottom":end,
     "v44_policy_still_unapproved":True,
    }
    p=Path("benchmark_results/v44_fresh_155k_three_policy_N256.json")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,sort_keys=True,indent=2)+"\n")
    print("DACK_V44_FRESH_155K_THREE_POLICY_PHYSICAL_PASS",
          json.dumps(data,sort_keys=True),flush=True)
if __name__=="__main__":main()
