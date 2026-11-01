#!/usr/bin/env python3
"""Pool strict N256 independent 164k v43-v46 paired goldfish games.

No acceptance or promotion from a positive point estimate alone.
"""
from __future__ import annotations
import glob,gzip,json,random
from pathlib import Path
N=256
SCHEMA="dack_v46_fresh164k_stage_isolated_v43_pair_N16_shard_v1"
def by(t,h):return int(0<int(t)<=h)
def run():
    paths=sorted(glob.glob("collected/v46_164k_*.json.gz"))
    assert len(paths)==16,("exact sixteen 164k shards",len(paths))
    rows=[];sha=None;dev=None;stage=None;mode=None
    for p in paths:
        with gzip.open(p,"rt") as f:d=json.load(f)
        assert d["schema"]==SCHEMA and d["status"]=="PASS"
        assert d["N_independent_physical_groups"]==16
        assert d["strict_original_99_slots_and_beam160"] and d["two_isolated_policy_interpreters"]
        assert d["physical_164k_unseen_in_fit_and_dev"]
        assert d["stage0_and_stage1_NOT_simultaneously_changed"]
        assert d["research_policy_NOT_promoted"]
        if sha is None:
            sha=d["source_model_sha256"];dev=d["source_dev_sha256"]
            stage=d["frozen_stage"];mode=d["frozen_mode"]
        assert sha==d["source_model_sha256"] and dev==d["source_dev_sha256"]
        assert stage==d["frozen_stage"] and mode==d["frozen_mode"]
        rows.extend(d["rows"])
    rows.sort(key=lambda r:r["gid"])
    assert [r["gid"] for r in rows]==list(range(164000,164256))
    outcome={}
    for p in ("v43","v46"):
        turns=[r[p]["turn"] for r in rows]
        outcome[p]={f"byT{h}":sum(by(t,h) for t in turns) for h in (1,2,3)}
        outcome[p]["mean_keep_n"]=sum(r[p]["keep_n"] for r in rows)/N
        outcome[p]["runtime_seconds"]=round(sum(r[p]["seconds"] for r in rows),2)
    paired={}
    for h in (1,2,3):
        ds=[by(r["v46"]["turn"],h)-by(r["v43"]["turn"],h) for r in rows]
        rng=random.Random(164001+h)
        boot=sorted(100*sum(ds[rng.randrange(N)] for _ in range(N))/N for _ in range(12000))
        paired[f"T{h}"]={
          "v46_minus_v43_pp":100*sum(ds)/N,
          "net_games":sum(ds),"v46_only":ds.count(1),"v43_only":ds.count(-1),
          "paired_outer_group_bootstrap95_pp":[boot[299],boot[11699]]
        }
    extra={
      "different_final_keep_stage":sum(r["v43"]["history"][-1]["stage"]!=r["v46"]["history"][-1]["stage"] for r in rows),
      "source_first_seven_changed_keep_decision":sum(
          r["v43"]["history"][0]["kept"]!=r["v46"]["history"][0]["kept"] for r in rows)}
    result={
      "schema":"dack_v46_164k_new_strict_N256_frozen_early_variant_vs_original_v43",
      "status":"PASS","N":N,"frozen_stage":stage,"frozen_mode":mode,
      "original_99_cards_and_same_physical_deals":True,
      "no_existing_original_v5_reference_in_new_group":True,
      "no_policy_approved":True,"source_model_sha256":sha,
      "source_dev_sha256":dev,
      "goldfish_dack_deployment_not_four_player_cedh_wins":True,
      "counts":outcome,"paired":paired,"stage_changes":extra,
    }
    path=Path("benchmark_results/v46_new_164k_N256_v43_comparison.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("DACK_V46_NEW_INDEPENDENT_N256_STRICT_PHYSICAL_COMPARISON_PASS",
       json.dumps(result,sort_keys=True),flush=True)
if __name__=="__main__":run()
