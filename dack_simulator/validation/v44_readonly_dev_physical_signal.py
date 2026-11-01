#!/usr/bin/env python3
"""Read-only v44 64-dev source signal and functional equivalence analysis.

No fitting; NO selection of another model/hyperparameter from these consumed
dev labels. Count how often the legal candidate set has ANY real physical T2
variation and how often changed v44 candidate is strictly worse at T3.

Potential 'oracle best' on the same eight futures is *in-sample hindsight*,
optimistically biased; report solely to quantify signal coverage, never as
a projected or attainable model win rate.
"""
from __future__ import annotations
import glob,gzip,json
from collections import Counter,defaultdict
from pathlib import Path
SCHEMA="dack_v44_dev_exhaustive_candidate_physical_signal_audit_v1"
def by(t,h):return int(0<t<=h)
def main():
    paths=sorted(glob.glob("datasets/v44_original_legal_candidates_154k_shards/v44_dev_*.json.gz"))
    assert len(paths)==4
    groups={}
    for p in paths:
        with gzip.open(p,"rt") as gz:z=json.load(gz)
        assert z["schema"]=="dack_v44_154k_candidate_physical_counterfactual_source_v1"
        assert z["split"]=="dev" and z["status"]=="PASS"
        assert z["same_physical_unseen92_futures_across_candidate_bottoms"]
        for r in z["rows"]:
            gid=r["gid"]
            assert gid not in groups
            groups[gid]=r
    assert set(groups)==set(range(154192,154256))
    report=json.loads(Path("benchmark_results/v44_all_candidate_Q2_residual_dev_N64.json").read_text())
    assert report["status"]=="PASS" and report["dev_independent_groups"]==64
    byid={r["gid"]:r for r in report["dev_per_group"]}
    assert set(byid)==set(groups)
    total=Counter();stage=defaultdict(Counter);details=[]
    for gid,g in sorted(groups.items()):
        a=byid[gid];c=g["candidates"]
        assert len(c)==g["N_candidate_rows"]
        old=c[a["old_index"]];new=c[a["new_index"]]
        assert old["idx"]==g["source_v27_maxq_index"]
        assert old["turns"]==a["old_turns"] and new["turns"]==a["new_turns"]
        all_t2=[x["physical_Q2"] for x in c]
        all_t3=[x["physical_Q3"] for x in c]
        t2_signatures={tuple(by(t,2) for t in x["turns"]) for x in c}
        t3_signatures={tuple(by(t,3) for t in x["turns"]) for x in c}
        observable_t2_range=max(all_t2)-min(all_t2)
        hindsight=max(all_t2)-old["physical_Q2"]
        diff_t2=new["physical_Q2"]-old["physical_Q2"]
        diff_t3=new["physical_Q3"]-old["physical_Q3"]
        flags={
          "has_any_physical_T2_variation":len(t2_signatures)>1,
          "has_any_physical_T3_variation":len(t3_signatures)>1,
          "old_at_hindsight_T2_max":hindsight==0,
          "old_and_new_physically_T2_equivalent_on_all_eight":
              tuple(by(t,2) for t in old["turns"])==tuple(by(t,2) for t in new["turns"]),
          "changed_bottom":old["idx"]!=new["idx"],
          "changed_bottom_and_T2_equivalent":
              old["idx"]!=new["idx"] and
              tuple(by(t,2) for t in old["turns"])==tuple(by(t,2) for t in new["turns"]),
          "changed_bottom_and_T3_worse":old["idx"]!=new["idx"] and diff_t3<0,
          "changed_bottom_and_T3_better":old["idx"]!=new["idx"] and diff_t3>0,
        }
        for k,v in flags.items():
            total[k]+=int(v);stage[g["stage"]][k]+=int(v)
        total["groups"]+=1;stage[g["stage"]]["groups"]+=1
        total["candidate_rows"]+=len(c)
        total["hindsight_candidate_T2_upperbound_sum"]+=hindsight
        entry={
          "gid":gid,"stage":g["stage"],"n_candidates":len(c),
          "old_index":old["idx"],"new_index":new["idx"],
          "old_bottom":old["bottom"],"new_bottom":new["bottom"],
          "empirical_T2_min":min(all_t2),"empirical_T2_max":max(all_t2),
          "empirical_T3_min":min(all_t3),"empirical_T3_max":max(all_t3),
          "old_selected_physical_T2":old["physical_Q2"],
          "new_selected_physical_T2":new["physical_Q2"],
          "old_selected_physical_T3":old["physical_Q3"],
          "new_selected_physical_T3":new["physical_Q3"],
          "T2_distinct_8future_signatures":len(t2_signatures),
          "T3_distinct_8future_signatures":len(t3_signatures),
          "hindsight_T2_optimistic_improvement":hindsight,
          **flags,
        }
        details.append(entry)
    assert total["groups"]==64 and total["changed_bottom"]==19
    assert total["changed_bottom_and_T2_equivalent"]==19
    assert total["changed_bottom_and_T3_worse"]==5
    assert sum(stage[s]["groups"] for s in (2,3,4,5))==64
    doc={
      "schema":SCHEMA,"status":"PASS","N_source_independent_physical_groups":64,
      "full_legal_candidate_T2_T3_physical_outcomes_analyzed":True,
      "all_8_matched_candidate_futures_preserved":True,
      "no_new_fitting_or_model_tuning":True,
      "dev_outcomes_ALREADY_CONSUMED_NOT_FRESH_HOLDOUT":True,
      "hindsight_oracle_is_UPWARD_BIASED_and_NOT_a_policy":True,
      "counts":dict(total),
      "hindsight_T2_max_minus_baseline_avg_pp":
          100*total["hindsight_candidate_T2_upperbound_sum"]/64,
      "by_stage":{str(s):dict(stage[s]) for s in (2,3,4,5)},
      "changed_selected_cases":[x for x in details if x["changed_bottom"]],
      "all_cases":details,
    }
    p=Path("benchmark_results/v44_154k_dev_candidate_signal_equivalence_audit.json")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print("DACK_V44_154K_DEVELOPMENT_CANDIDATE_SIGNAL_AUDIT_PASS",
          json.dumps({k:v for k,v in doc.items() if k not in ("all_cases","changed_selected_cases")},sort_keys=True),flush=True)
if __name__=="__main__":main()
