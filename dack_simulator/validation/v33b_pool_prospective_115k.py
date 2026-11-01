#!/usr/bin/env python3
"""Pool 256 matched NEW physical games and actual timed T1/T2/T3 outcomes.

Paired game IDs are the only resampling unit. No prospective labels
used for fitting or threshold selection. Need strict frozen v27 KEEP/MULL
parity; bottom is the only intervention in the v33b-v27 contrast.
"""
from __future__ import annotations
import collections
import gzip
import glob
import json
import math
import random
from pathlib import Path
POLICIES=("v5","v27_frozen","v33b_regret_bottom")
N=256

def passby(turn,at):
    return int(0<int(turn)<=at)

def exact_mcnemar(g,l):
    n=g+l
    if n==0:return 1.
    return min(1.,2*sum(math.comb(n,k) for k in range(min(g,l)+1))/2**n)

def paired(rows,new,old,turn):
    diffs=[passby(r[new]["turn"],turn)-passby(r[old]["turn"],turn) for r in rows]
    rng=random.Random(115500+turn+sum(map(ord,new+old)))
    bootstrap=sorted(100*sum(diffs[rng.randrange(N)] for _ in range(N))/N
                     for _ in range(12000))
    gains=diffs.count(1);losses=diffs.count(-1)
    return {"gain_games":gains,"loss_games":losses,"paired_ties":N-gains-losses,
            "delta_pp":100*sum(diffs)/N,
            "paired_game_bootstrap_95ci_pp":[bootstrap[299],bootstrap[11699]],
            "exploratory_exact_mcnemar_p":exact_mcnemar(gains,losses)}

def pool(source,out):
    paths=sorted(glob.glob(source))
    assert len(paths)==64,("expected 64 complete prospective shards",len(paths))
    rows=[];sha=None
    for p in paths:
        with gzip.open(p,"rt") as f:d=json.load(f)
        assert d["schema"]=="dack_v33b_prospective_115k_three_policy_strict"
        assert d["status"]=="PASS" and d["physical_groups"]==4
        assert tuple(d["policies"])==POLICIES
        assert d["strict_gameplay_beam"]==160
        assert d["v27_v33b_identical_london_stages_and_keep_actions"]
        assert d["initial_99_card_shuffle_and_seat_identical_across_policies"]
        assert d["unseen_future_never_used_to_decide_bottom"]
        assert d["115k_not_used_for_training_or_validation"] and d["models_unapproved"]
        if sha is None:sha=d["source_sha256"]
        assert d["source_sha256"]==sha
        rows+=d["rows"]
    rows.sort(key=lambda r:r["game_id"])
    assert [r["game_id"] for r in rows]==list(range(115000,115256))
    per={}
    for p in POLICIES:
        x=[r[p] for r in rows]
        per[p]={
          "N":N,
          "T1_exact_count":sum(y["turn"]==1 for y in x),
          "by_T2_count":sum(passby(y["turn"],2) for y in x),
          "by_T3_count":sum(passby(y["turn"],3) for y in x),
          "mean_kept_n":sum(y["keep_n"] for y in x)/N,
          "sum_gameplay_seconds":sum(y["seconds"] for y in x)
        }
    changes=collections.Counter()
    for r in rows:
        va=r["v27_frozen"]["history"]
        vb=r["v33b_regret_bottom"]["history"]
        assert len(va)==len(vb)
        for a,b in zip(va,vb):
            assert (a["stage"],a["keep_n"],a["kept"],a["seven_slots"])==(
                b["stage"],b["keep_n"],b["kept"],b["seven_slots"])
        assert r["v27_frozen"]["keep_n"]==r["v33b_regret_bottom"]["keep_n"]
        a=va[-1];b=vb[-1]
        changed=(collections.Counter(a["hand"])!=collections.Counter(b["hand"]))
        assert changed==bool(b["v33b_bottom_only_override"])
        changes["bottom_changed"]+=int(changed)
        changes["same_bottom"]+=int(not changed)
        if changed:
            changes["bottom_changed_T2_gain"]+=int(
                 passby(r["v33b_regret_bottom"]["turn"],2)>
                 passby(r["v27_frozen"]["turn"],2))
            changes["bottom_changed_T2_loss"]+=int(
                 passby(r["v33b_regret_bottom"]["turn"],2)<
                 passby(r["v27_frozen"]["turn"],2))
            changes["bottom_changed_T3_gain"]+=int(
                 passby(r["v33b_regret_bottom"]["turn"],3)>
                 passby(r["v27_frozen"]["turn"],3))
            changes["bottom_changed_T3_loss"]+=int(
                 passby(r["v33b_regret_bottom"]["turn"],3)<
                 passby(r["v27_frozen"]["turn"],3))
    outdoc={
      "schema":"dack_v33b_prospective_115k_N256_goldfish_deployment",
      "status":"PASS","source_ids":[115000,115255],
      "strict_physical_99_and_beam160":True,
      "source_model_file_sha256":sha,
      "policy_approved":False,"goldfish_not_multiplayer_win_probability":True,
      "bottom_only_intervention":True,
      "no_prospective_training_or_tuning":True,
      "per_policy":per,"bottom_change_stats":dict(changes),
      "paired":{
        f"{new}_minus_{old}_T{t}":paired(rows,new,old,t)
        for new,old in (("v33b_regret_bottom","v27_frozen"),
                        ("v33b_regret_bottom","v5"),
                        ("v27_frozen","v5"))
        for t in (1,2,3)},
      "speedup_v5_over_v33b_gameplay":
         per["v5"]["sum_gameplay_seconds"]/per["v33b_regret_bottom"]["sum_gameplay_seconds"],
      "speedup_v5_over_v27_gameplay":
         per["v5"]["sum_gameplay_seconds"]/per["v27_frozen"]["sum_gameplay_seconds"],
      "warning":"N256 is not powered to detect ~1-2pp gains reliably; training/conditional validation runtime excluded, only end-to-end policy gameplay measured. Do not promote without clear prospective evidence."}
    dest=Path(out);dest.parent.mkdir(exist_ok=True,parents=True)
    dest.write_text(json.dumps(outdoc,sort_keys=True,indent=2)+"\n")
    print("DACK_V33B_PROSPECTIVE_POOL_PASS",json.dumps({
      "per_policy":per,
      "bottom_change_stats":dict(changes),
      "primary":outdoc["paired"]["v33b_regret_bottom_minus_v27_frozen_T2"],
      "speedup_v5_over_v33b":outdoc["speedup_v5_over_v33b_gameplay"]},
      sort_keys=True),flush=True)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--source",default="collected/v33b_115k_*.json.gz")
    p.add_argument("--out",default="benchmark_results/v33b_prospective_115k_N256.json")
    a=p.parse_args();pool(a.source,a.out)
