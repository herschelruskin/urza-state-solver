#!/usr/bin/env python3
"""Pool 8*32 independent matched fresh physical v27 vs v43 max-Q2.
No model selection; threshold, feature and candidate architecture frozen
before game 151000. Purely exploratory test, no v5 reference on these games.
"""
import glob,gzip,json,random
from pathlib import Path
N=256
def by(t,h):return int(0<int(t)<=h)
def run():
    p=sorted(glob.glob("collected/v43_151k_*.json.gz"))
    assert len(p)==8,(len(p),p)
    a=[];sh=None
    for file in p:
        with gzip.open(file,"rt") as f:x=json.load(f)
        assert x["status"]=="PASS"
        assert x["schema"]=="dack_v43_fresh_151k_v27_vs_maxQ2_N256_paired_shard"
        assert x["frozen_policy_prior_to_151k"] and x["no_training_or_threshold_tuning_on_151k"]
        assert x["strict_physical_99_beam160"] and x["maxQ2_is_unapproved_and_ood_across_bottoms"]
        if sh is None:sh=x["model_sha256"]
        assert x["model_sha256"]==sh
        a+=x["rows"]
    a.sort(key=lambda r:r["gid"])
    assert [r["gid"] for r in a]==list(range(151000,151256))
    scores={};paired={};changed=0;bottom=0
    for pol in ("v27","maxQ2"):
        scores[pol]={f"by_T{h}":sum(by(r[pol]["turn"],h) for r in a) for h in (1,2,3)}
        scores[pol]["seconds"]=round(sum(r[pol]["seconds"] for r in a),3)
        scores[pol]["mean_kept_n"]=sum(r[pol]["keep_n"] for r in a)/N
    for r in a:
        x=r["v27"];y=r["maxQ2"]
        changed+=int(x["keep_n"]!=y["keep_n"])
        bottom+=int(x["history"][-1]["bottom"]!=y["history"][-1]["bottom"])
    for h in (1,2,3):
        d=[by(r["maxQ2"]["turn"],h)-by(r["v27"]["turn"],h) for r in a]
        rand=random.Random(151000+h)
        reps=sorted(100*sum(d[rand.randrange(N)] for _ in range(N))/N for _ in range(12000))
        paired[f"T{h}"]={
            "maxQ2_minus_v27_pp":100*sum(d)/N,"net_games":sum(d),
            "maxQ2_only":d.count(1),"v27_only":d.count(-1),
            "paired_bootstrap_95ci_pp":[reps[299],reps[11699]],
        }
    o={
      "schema":"dack_v43_frozen_v27_vs_maxQ2_N256_prospective_151k",
      "status":"PASS","N_independent_games":N,
      "same_physical_99_seat_and_shuffle":True,
      "strict_beam160_goldfish_outcomes":True,
      "original_v5_reference_not_run_in_new_cohort":True,
      "v43_candidate_max_policy_not_approved":True,
      "candidate_maxQ2_out_of_distribution_caution":True,
      "frozen_model_sha256":sh,
      "different_final_keep_stages":changed,
      "different_final_bottoms":bottom,
      "scores":scores,"paired":paired,
    }
    f=Path("benchmark_results/v43_fresh_151k_v27_vs_maxQ2_N256.json")
    f.parent.mkdir(parents=True,exist_ok=True)
    f.write_text(json.dumps(o,indent=2,sort_keys=True)+"\n")
    print("DACK_V43_FRESH_CANDIDATE_MAX_Q2_STRICT_N256_PASS",json.dumps(o,sort_keys=True),flush=True)
if __name__=="__main__":run()
