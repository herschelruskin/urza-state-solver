#!/usr/bin/env python3
"""Read-only 96k physical N256 v5-v14 bottoming frequency analysis.

96k is frozen evaluation. This is descriptive and MUST NOT train model,
calibrate thresholds, or select future search strategy based on 96k.
"""
import collections,glob,gzip,json
from pathlib import Path

def main():
    files=sorted(glob.glob("benchmark_results/v25_96k_full_game_shards/v25_96k_*.json.gz"))
    assert len(files)==64,len(files)
    rows=[]
    for path in files:
        with gzip.open(path,"rt") as stream:
            obj=json.load(stream)
        assert obj["status"]=="PASS" and obj["physical_first_seven_parity"]
        rows.extend(obj["rows"])
    rows.sort(key=lambda z:z["game_id"])
    assert [x["game_id"] for x in rows]==list(range(96000,96256))
    bottom=collections.Counter()
    common=collections.Counter()
    v5only=collections.Counter()
    studentonly=collections.Counter()
    by_keep=collections.defaultdict(collections.Counter)
    groups=[]
    for r in rows:
        h5=r["v5"]["history"]
        h14=r["v14_128"]["history"]
        s5={x["stage"]:x for x in h5}
        s14={x["stage"]:x for x in h14}
        for stage in sorted(set(s5)&set(s14)):
            x=s5[stage];y=s14[stage]
            assert x["seven_slots"]==y["seven_slots"]
            assert x["keep_n"]==y["keep_n"]
            if x["keep_n"]==7:
                continue
            v5=collections.Counter(x["bottom"])
            learner=collections.Counter(y["bottom"])
            bottom.update(v5)
            common["paired_stages"]+=1
            common["same_bottom_multiset"]+=int(v5==learner)
            common["different_bottom_multiset"]+=int(v5!=learner)
            common["same_ordered_bottom"]+=int(x["bottom"]==y["bottom"])
            by_keep[str(x["keep_n"])]["paired"]+=1
            by_keep[str(x["keep_n"])]["differ"]+=int(v5!=learner)
            if v5!=learner:
                v5only.update(v5-learner)
                studentonly.update(learner-v5)
                groups.append({
                    "game_id":r["game_id"],"stage":stage,"keep_n":x["keep_n"],
                    "visible_seven":x["seven"],
                    "teacher_keep_here":bool(x["kept"]),
                    "student_keep_here":bool(y["kept"]),
                    "v5_bottom":x["bottom"],
                    "student_bottom":y["bottom"],
                    "v5_kept_hand":x["hand"],
                    "student_kept_hand":y["hand"],
                })
    report={
        "schema":"dack_v28_readonly_v25_96k_bottom_choice_disagreements",
        "status":"PASS",
        "game_ids":[96000,96255],
        "physical_game_count":len(rows),
        "matched_london_stage_bottom_n":common["paired_stages"],
        "counts":dict(common),
        "by_keep_n":{k:dict(v) for k,v in by_keep.items()},
        "teacher_bottom_all_cards":dict(bottom.most_common()),
        "v5_bottomed_but_v14_kept":dict(v5only.most_common()),
        "v14_bottomed_but_v5_kept":dict(studentonly.most_common()),
        "bottom_disagreement_cases":groups,
        "source_v25_96k_is_evaluation_only":True,
        "no_policy_fitting":True,
        "warning":"Includes only London stages both policies visited, conditioning on survival to that stage. Frequencies do not show causal effect or future-card leakage."
    }
    out=Path("benchmark_results/v28_v25_readonly_bottom_choices_N256.json")
    out.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("V28_V25_READONLY_BOTTOM_DISAGREEMENT_AUDIT_PASS",json.dumps({
        "n":len(rows),"paired":common["paired_stages"],"counts":dict(common),
        "by_keep_n":report["by_keep_n"],
        "v5_only_cards":dict(v5only.most_common(12)),
        "student_only_cards":dict(studentonly.most_common(12)),
        "disagreement_example":groups[:1],
    },sort_keys=True),flush=True)

if __name__=="__main__":
    main()
