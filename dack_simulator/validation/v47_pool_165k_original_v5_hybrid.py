#!/usr/bin/env python3
"""Pool N256 new v43 vs v47 hybrid, and N128 same-seed original full-v5.

Scientific claims: goldfish Dack deployment T1/T2/T3, not 4-player
victories. N128 original-v5 subset is intentionally predeclared rather
than retrospectively added after outcomes. Preserve raw complete traces.
"""
from __future__ import annotations
import argparse,glob,gzip,json,random
from collections import Counter
from pathlib import Path
SCHEMA="dack_v47_fresh_165k_v43_vs_original_early_two_sevens_N16_shard"
N=256
def success(t,h):return int(0<int(t)<=h)
def rates(rr,policy):
    return {
      f"by_T{h}":sum(success(r[policy]["turn"],h) for r in rr) for h in (1,2,3)
    } | {"mean_keep_n":sum(r[policy]["keep_n"] for r in rr)/len(rr),
         "total_wallclock_seconds":round(sum(r[policy]["seconds"] for r in rr),3)}
def pair(rr,new,old):
    n=len(rr)
    d={}
    for h in (1,2,3):
        diff=[success(r[new]["turn"],h)-success(r[old]["turn"],h) for r in rr]
        rng=random.Random(471650+len(rr)+h+sum(ord(z) for z in new+old))
        boot=sorted(100*sum(diff[rng.randrange(n)] for _ in range(n))/n for _ in range(10000))
        d[f"T{h}"]={
         "delta_pp":100*sum(diff)/n,"net_game_deployments":sum(diff),
         "new_only":diff.count(1),"old_only":diff.count(-1),
         "paired_group_bootstrap95_pp":[boot[249],boot[9749]],
        }
    return d
def run(source,out):
    ps=sorted(glob.glob(source))
    assert len(ps)==16,(len(ps),"16 exact N16 shards required")
    rows=[]
    for path in ps:
        with gzip.open(path,"rt") as f:q=json.load(f)
        assert q["schema"]==SCHEMA and q["status"]=="PASS"
        assert q["N_independent_groups"]==16
        assert q["source_comparison_wholly_new_165k_not_dev"]
        assert q["original_99_slots_and_same_physical_first_seven_seat"]
        assert q["real_strict_beam160_and_stateless_stable_dice"]
        assert q["experimental_v47_uses_original_v5_beam60_at_0_1_ONLY"]
        assert q["frozen_v43_from_stage2_onward"]
        assert q["exact_original_v5_early_action_parity_where_reference_present"]
        assert not q["model_or_policy_approved"]
        rows+=q["rows"]
    rows.sort(key=lambda r:r["gid"])
    assert [r["gid"] for r in rows]==list(range(165000,165256))
    refs=[r for r in rows if r["original_v5"] is not None]
    assert len(refs)==128 and [r["gid"] for r in refs]==list(range(165000,165128))
    for r in rows:
        assert r["v43"]["seat"]==r["v47"]["seat"]
        assert r["v43"]["history"][0]["seven_slots"]==r["v47"]["history"][0]["seven_slots"]
        if r["original_v5"] is not None:
            assert r["original_v5"]["seat"]==r["v47"]["seat"]
    allcounts={p:rates(rows,p) for p in ("v43","v47")}
    refcounts={p:rates(refs,p) for p in ("v43","v47","original_v5")}
    allpair=pair(rows,"v47","v43")
    refpair={
       "v47_minus_original_v5":pair(refs,"v47","original_v5"),
       "v43_minus_original_v5":pair(refs,"v43","original_v5"),
       "v47_minus_v43":pair(refs,"v47","v43"),
    }
    first_diff=Counter()
    for r in rows:
        a=r["v43"]["history"];b=r["v47"]["history"]
        first=min(int(a[-1]["stage"]),int(b[-1]["stage"]))
        if int(a[-1]["stage"])!=int(b[-1]["stage"]):
            first_diff[str(first)]+=1
    # Acceptance evidence is not simply a positive point estimate.
    report={
      "schema":"dack_v47_165k_new_N256_v43_vs_restricted_early_true_v5_and_N128_complete_v5",
      "status":"PASS","n_new_outer_deals":256,
      "n_complete_original_v5_reference":128,
      "all_99_physical_cards_strict_beam160_same_seeds":True,
      "no_training_or_development_on_165k":True,
      "original_v5_unchanged_real_beam60_mulligan_and_beam160_gameplay":True,
      "hybrid_true_v5_early_two_sevens_then_frozen_v43":True,
      "v47_is_not_a_no_beam_policy":True,
      "no_model_or_policy_approved":True,
      "deployment_outcomes_not_multiplayer_cedh_wins":True,
      "all_N256_counts":allcounts,"all_N256_paired":allpair,
      "matched_N128_with_full_v5_counts":refcounts,
      "matched_N128_paired":refpair,
      "different_final_stage_first_stages":dict(first_diff),
      "actual_full_v5_over_hybrid_runtime_ratio_on_128":(
         refcounts["original_v5"]["total_wallclock_seconds"]/
         refcounts["v47"]["total_wallclock_seconds"]),
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V47_FRESH_NEW_165K_N256_AND_V5_N128_FULL_GAME_PAIR_PASS",
          json.dumps(report,sort_keys=True),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--source",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();run(a.source,a.out)
