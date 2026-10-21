#!/usr/bin/env python3
"""Matched 34-land World Map vs 35-land Plains discordant-game forensic replay.

For the 24 by-T2 discordant game IDs from validated N256 result:
- reproduce the ORIGINAL free London mulligan choices and sizes exactly;
- log every seen seven, proposed bottoming/kept hand and threshold;
- compare same-stage opening hands across the two variants;
- selectively rerun map-only wins with the World Map activated search
  DISABLED, but the exact same kept hand/library and legal artifact synergies;
- do not change the frozen 34 vs 35 land runners.
"""
from __future__ import annotations
import argparse, gzip, hashlib, json, random, time
from pathlib import Path
from collections import Counter
import dack_map_to_plains_paired_20261021 as trial

root=trial.root
d=trial.d
m=trial.m

# 24 games where T2 outcome differs. (world-map time, plains time, map keep, plains keep)
EXPECTED={
 2:(2,0,3,4),10:(2,3,4,5),22:(2,3,7,3),38:(0,2,6,6),
 84:(2,3,7,7),87:(3,2,7,6),114:(2,0,7,3),117:(1,3,2,4),
 123:(3,2,7,6),128:(1,3,6,7),130:(3,2,5,6),136:(0,2,7,5),
 137:(3,2,7,5),156:(2,3,4,6),169:(3,2,7,5),180:(3,2,4,4),
 182:(2,3,7,7),190:(3,2,7,6),205:(2,3,7,7),211:(2,3,6,6),
 240:(2,3,7,5),241:(2,3,5,6),246:(2,0,4,5),251:(3,2,5,7)
}
assert len(EXPECTED)==24
SEED_BASE=root.batch.CONFIG["seed_base"]

def replay_mulligan(variant,gid):
    root.install(variant)
    seed=SEED_BASE+int(gid)*1000003
    m.set_trial_seed(seed)
    rng=random.Random(seed)
    seat=rng.randrange(4)
    steps=[]
    orig=root.batch.evaluate_keep
    def wrapped(seven,keep_n,rest,seat_arg):
        x=orig(seven,keep_n,rest,seat_arg)
        raw,ev,struct,hand,bottom,unknown,threshold,refined=x
        cutoff=0.0 if keep_n==1 else root.batch.FROZEN_CONTINUATION[keep_n-1]
        step={
          "stage":len(steps),"keep_n":keep_n,"raw":round(float(raw),7),
          "threshold":round(float(cutoff),7),
          "accepted":bool(keep_n==1 or raw>=cutoff),
          "drawn_seven":list(seven),
          "picked_hand":list(hand),"bottom":list(bottom),
          "unknown_top3":list(unknown[:3]),"refined":bool(refined),
          "le2_ev":round(float(ev["le2"]),6),"le3_ev":round(float(ev["le3"]),6),
          "map_in_seven":"World Map" in seven,
          "plains_in_seven":seven.count("Plains"),
        }
        steps.append(step)
        return x
    root.batch.evaluate_keep=wrapped
    try:
        st,keep,audit=root.choose_hand_with_free(rng,seat)
    finally:
        root.batch.evaluate_keep=orig
    assert len(steps)==len(audit)
    assert steps[-1]["accepted"]
    assert steps[-1]["keep_n"]==keep
    assert tuple(st.hand)==tuple(steps[-1]["picked_hand"])
    return st,{"variant":variant,"gid":gid,"seat":seat,"keep_n":keep,
               "kept_hand":list(st.hand),"bottomed":steps[-1]["bottom"],
               "top3":list(st.library[:3]),"stage_idx":len(steps)-1,
               "combo_in_library":sum(k in st.library for k in root.COMBO),
               "mulligan_steps":steps}

def no_map_ability_win(gid,st,seat):
    # Same physical keep and draw order. Only World Map activated abilities
    # are removed; its casting, artifact presence, KCI and metalcraft remain.
    orig=d.utility_actions
    try:
        d.utility_actions=root._previous_utility
        d._WIN_CACHE.clear()
        x=d._win_turn_from_unknown_order(st.hand,st.library,seat,
                                         beam=160,max_turn=3)
        return int(x or 0)
    finally:
        d.utility_actions=orig
        d._WIN_CACHE.clear()

def case(gid):
    expected=EXPECTED[gid]
    state={}
    logs={}
    for v in ("current34","plains35"):
        st,rr=replay_mulligan(v,gid)
        state[v]=st;logs[v]=rr
    assert logs["current34"]["seat"]==logs["plains35"]["seat"]
    assert logs["current34"]["keep_n"]==expected[2],(gid,"map kept",logs["current34"]["keep_n"],expected[2])
    assert logs["plains35"]["keep_n"]==expected[3],(gid,"plains kept",logs["plains35"]["keep_n"],expected[3])
    s1=logs["current34"]["mulligan_steps"]
    s2=logs["plains35"]["mulligan_steps"]
    same_stage=[]
    for i in range(min(len(s1),len(s2))):
        a,b=Counter(s1[i]["drawn_seven"]),Counter(s2[i]["drawn_seven"])
        match=(a==b or
           (a-b)==Counter({"World Map":1}) and
           (b-a)==Counter({"Plains":1}))
        assert match,(gid,i,a-b,b-a)
        same_stage.append({
          "stage":i,"original_seven_equal_except_substitution":bool(match),
          "map_raw":s1[i]["raw"],"plains_raw":s2[i]["raw"],
          "map_accepted":s1[i]["accepted"],"plains_accepted":s2[i]["accepted"],
          "map_in_seven":s1[i]["map_in_seven"],"map_keep":s1[i]["keep_n"],
          "plains_keep":s2[i]["keep_n"]
        })
    logs["expected_win_map"]=expected[0]
    logs["expected_win_plains"]=expected[1]
    logs["same_stage"]=same_stage
    logs["same_keep_size"]=logs["current34"]["keep_n"]==logs["plains35"]["keep_n"]
    logs["same_stage_choice"]=logs["current34"]["stage_idx"]==logs["plains35"]["stage_idx"]
    # World Map was the only card substituted; does the Map win rely on
    # its printed activated search at all?
    map_only_t2=(0<expected[0]<=2 and not (0<expected[1]<=2))
    if map_only_t2:
        root.install("current34")
        m.set_trial_seed(SEED_BASE+gid*1000003)
        d._WIN_CACHE.clear()
        with_map=d._win_turn_from_unknown_order(
            state["current34"].hand,state["current34"].library,
            logs["current34"]["seat"],beam=160,max_turn=3)
        assert int(with_map or 0)==expected[0],(gid,"replay winner mismatch",with_map,expected[0])
        logs["map_fixed_hand_no_search_win_turn"]=no_map_ability_win(
            gid,state["current34"],logs["current34"]["seat"])
        logs["map_search_required_for_t2"]=(logs["map_fixed_hand_no_search_win_turn"]!=expected[0])
    return logs

def pool(path,out,expected):
    data={};paths=sorted(Path(path).glob("*.json.gz"))
    assert paths,("no shards",path)
    for p in paths:
        with gzip.open(p,"rt",encoding="utf8") as f:q=json.load(f)
        assert q["schema"]=="dack_map_plains_t2_forensics_v1"
        for rec in q["records"]:
            gid=rec["gid"];assert gid not in data;data[gid]=rec
    assert set(data)==set(EXPECTED),(set(EXPECTED)-set(data),set(data)-set(EXPECTED))
    assert len(data)==expected
    mismatch=[q for q in data.values() if not q["same_stage_choice"]]
    diff_keep=[q for q in data.values() if not q["same_keep_size"]]
    mapwins=[q for q in data.values() if 0<q["expected_win_map"]<=2 and not (0<q["expected_win_plains"]<=2)]
    plainswins=[q for q in data.values() if 0<q["expected_win_plains"]<=2 and not (0<q["expected_win_map"]<=2)]
    nosearch=[q for q in mapwins if not q.get("map_search_required_for_t2")]
    report={
      "status":"PASS","n":len(data),"map_t2_only":len(mapwins),"plains_t2_only":len(plainswins),
      "different_mulligan_stage":len(mismatch),"different_keep_size":len(diff_keep),
      "map_t2_only_with_different_mulligan_stage":sum(not q["same_stage_choice"] for q in mapwins),
      "plains_t2_only_with_different_mulligan_stage":sum(not q["same_stage_choice"] for q in plainswins),
      "map_t2_only_unchanged_with_map_search_disabled":len(nosearch),
      "map_t2_only_search_disabled_losses":len(mapwins)-len(nosearch),
      "cases_map_survived_without_search":[q["gid"] for q in nosearch],
      "mismatched_mulligan_games":[q["gid"] for q in mismatch],
      "same_stage_mulligan_games":[q["gid"] for q in data.values() if q["same_stage_choice"]],
      "cases":{str(k):data[k] for k in sorted(data)}
    }
    Path(out).write_text(json.dumps(report,indent=2),encoding="utf8")
    print("MAP_PLAINS_FORENSICS_POOLED_PASS",json.dumps({k:v for k,v in report.items() if k!="cases"}),flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--chunk",type=int,default=4)
    p.add_argument("--pool",action="store_true")
    p.add_argument("--expected",type=int,default=24)
    p.add_argument("--path",default="shards")
    p.add_argument("--out",default="forensic.json.gz")
    a=p.parse_args()
    if a.pool:return pool(a.path,a.out,a.expected)
    assert len(trial.CURRENT)==len(trial.PROPOSED)==99
    assert Counter(trial.PROPOSED)-Counter(trial.CURRENT)==Counter(["Plains"])
    assert Counter(trial.CURRENT)-Counter(trial.PROPOSED)==Counter(["World Map"])
    if a.audit:
        print("MAP_PLAINS_FORENSICS_AUDIT_PASS",len(EXPECTED),flush=True)
        return
    items=sorted(EXPECTED)
    gids=items[a.shard*a.chunk:(a.shard+1)*a.chunk]
    assert gids,(a.shard,a.chunk)
    start=time.time();records=[]
    for gid in gids:
        x=case(gid);records.append(x)
        print("FORENSIC_CASE",gid,
              "map",x["expected_win_map"],x["current34"]["keep_n"],x["current34"]["stage_idx"],
              "plains",x["expected_win_plains"],x["plains35"]["keep_n"],x["plains35"]["stage_idx"],
              "map_search_required",x.get("map_search_required_for_t2"),
              flush=True)
    payload={"schema":"dack_map_plains_t2_forensics_v1",
             "shard":a.shard,"chunk":a.chunk,"elapsed_sec":round(time.time()-start,2),
             "records":records}
    with gzip.open(a.out,"wt",encoding="utf8") as f:json.dump(payload,f,separators=(",",":"))
    print("MAP_PLAINS_FORENSIC_SHARD_PASS",a.shard,len(gids),round(time.time()-start,2),flush=True)
if __name__=="__main__":main()
