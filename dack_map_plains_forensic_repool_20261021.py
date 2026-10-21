#!/usr/bin/env python3
"""Pool the successful 24-game Map->Plains forensic shards from GH Actions run 39630947748.

Corrects only the report-level indexing mismatch in the earlier pooler: the
per-case ID is nested in current34.gid and plains35.gid. NO simulation rerun.
"""
import argparse, gzip, json
from pathlib import Path
from collections import Counter
from dack_map_plains_discordant_replay_20261021 import EXPECTED

def pool(path,out):
    data={}
    shards=sorted(Path(path).rglob("*.json.gz"))
    assert len(shards)==6,(len(shards),shards)
    for f in shards:
        with gzip.open(f,"rt",encoding="utf8") as inp:q=json.load(inp)
        assert q["schema"]=="dack_map_plains_t2_forensics_v1"
        for rec in q["records"]:
            idmap=rec["current34"]["gid"]
            assert idmap==rec["plains35"]["gid"] and idmap in EXPECTED
            assert idmap not in data
            rec["gid"]=idmap
            data[idmap]=rec
    assert set(data)==set(EXPECTED),(len(data),len(EXPECTED))
    n=len(data)
    mapwins=[q for q in data.values() if 0<q["expected_win_map"]<=2 and not (0<q["expected_win_plains"]<=2)]
    plainswins=[q for q in data.values() if 0<q["expected_win_plains"]<=2 and not (0<q["expected_win_map"]<=2)]
    assert len(mapwins)==14 and len(plainswins)==10
    mismatch=[q for q in data.values() if not q["same_stage_choice"]]
    diffkeep=[q for q in data.values() if not q["same_keep_size"]]
    def depth(q):
        a,b=q["current34"]["stage_idx"],q["plains35"]["stage_idx"]
        if a>b:return "map"
        if a<b:return "plains"
        return "same"
    map_search_survivors=[q for q in mapwins if not q.get("map_search_required_for_t2")]
    search_required=[q for q in mapwins if q.get("map_search_required_for_t2")]
    if not all(isinstance(q.get("map_search_required_for_t2"),bool) for q in mapwins):
        raise AssertionError("Missing Map search ablation")
    report={
      "status":"PASS","replayed_game_ids":n,"shards":len(shards),
      "source_run":39630947748,
      "map_only_by_T2":len(mapwins),"plains_only_by_T2":len(plainswins),
      "keep_size_different":len(diffkeep),
      "stage_different":len(mismatch),
      "deeper_mulligan_winning_side":sum(depth(q)=="map" for q in mapwins)+sum(depth(q)=="plains" for q in plainswins),
      "deeper_mulligan_losing_side":sum(depth(q)=="plains" for q in mapwins)+sum(depth(q)=="map" for q in plainswins),
      "stage_tied":sum(depth(q)=="same" for q in data.values()),
      "depth_map_only":{"map_deeper":sum(depth(q)=="map" for q in mapwins),"plains_deeper":sum(depth(q)=="plains" for q in mapwins),"same":sum(depth(q)=="same" for q in mapwins)},
      "depth_plains_only":{"map_deeper":sum(depth(q)=="map" for q in plainswins),"plains_deeper":sum(depth(q)=="plains" for q in plainswins),"same":sum(depth(q)=="same" for q in plainswins)},
      "map_only_T2_still_wins_without_map_search":len(map_search_survivors),
      "map_only_T2_fails_without_map_search":len(search_required),
      "map_only_T2_search_survivor_ids":[q["gid"] for q in map_search_survivors],
      "map_only_map_in_kept_hand":sum("World Map" in q["current34"]["kept_hand"] for q in mapwins),
      "map_only_map_in_top3_after_mulligan":sum("World Map" in q["current34"]["top3"] for q in mapwins),
      "same_stage_decision_divergence_when_swapped_card_absent_from_both_sevens":sum(
           any(x["map_accepted"]!=x["plains_accepted"] and not x["map_in_seven"]
               for x in q["same_stage"])
           for q in data.values()),
      "per_game":{str(k):data[k] for k in sorted(data)}
    }
    Path(out).write_text(json.dumps(report,indent=2),encoding="utf8")
    print("FORENSIC_REPOOL_PASS",json.dumps({k:v for k,v in report.items() if k!="per_game"}),flush=True)
if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--path",default="shards")
    ap.add_argument("--out",default="dack_map_plains_forensic_n24.json")
    a=ap.parse_args()
    pool(a.path,a.out)
