#!/usr/bin/env python3
"""Rebuild the *live*, honestly provisional Assertive ramp card leaderboard.

Works with completed individual shard artifacts before a full screening run
finishes. Once official strict pooled summary + raw report artifacts exist,
uses their exact validated data. Never treats incomplete cases as final.

Each observed direct one-card head-to-head is strictly paired by game ID;
the card-rank statistic averages correlated contextual contrasts, so it is
only a *screening heuristic*, never a causal effect or confirmatory interval.
"""
from __future__ import annotations
import argparse, gzip, json
from pathlib import Path
import dack_assertive_ramp_card_leaderboard as board

MIN_INTERIM_GAMES=24

def shard_trial(config,root):
    m=config["module"]
    assert config["name"] in ("screen20","flex41")
    pattern=("assertive_ramp_shard_*.json.gz" if config["name"]=="screen20"
             else "flex_shard_*.json.gz")
    files=sorted(root.rglob(pattern)) if root.exists() else []
    rows={}
    hashes={name:board.deck_hash(cards) for name,cards in m.VARIANTS.items()}
    for path in files:
        with gzip.open(path,"rt",encoding="utf8") as f:q=json.load(f)
        assert q["schema"]==m.SCHEMA,(path,"schema")
        assert q["seed_base"]==m.SEED_BASE,(path,"seed")
        assert q["policy"]=="assertive" and q["beam"]==160,(path,"policy/beam")
        assert q["deck_hashes"]==hashes,(path,"hashes")
        assert q["games"]==m.PER_SHARD and len(q["rows"])==m.PER_SHARD,(path,"length")
        for offset,rec in enumerate(q["rows"]):
            gid=q["shard"]*m.PER_SHARD+offset
            assert gid==rec["gid"] and 0<=gid<config["n"]
            assert gid not in rows,("duplicate game ID",gid)
            assert set(rec["arms"])==set(m.VARIANTS)
            assert len({q["seat"] for q in rec["arms"].values()})==1
            assert len({q["seed"] for q in rec["arms"].values()})==1
            for arm in rec["arms"].values():
                assert arm["seed"]==m.SEED_BASE+gid*1000003
                assert arm["keep_n"] in range(1,8)
                assert arm["turn"] in (0,1,2,3)
            rows[gid]=rec
    return {"config":config,"rows":[rows[k] for k in sorted(rows)],
            "completed_shard_count":len(files),
            "found_games":len(rows),"hashes":hashes}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--screen20-shards",default="imported/shards20")
    p.add_argument("--flex41-shards",default="imported/shards41")
    p.add_argument("--screen20-report",default="")
    p.add_argument("--screen20-raw",default="")
    p.add_argument("--flex41-report",default="")
    p.add_argument("--flex41-raw",default="")
    p.add_argument("--json-out",default="benchmark_results/dack_assertive_ramp_card_tracker.json")
    p.add_argument("--md-out",default="DACK_ASSERTIVE_RAMP_CARD_LEADERBOARD.md")
    args=p.parse_args()
    trial_inputs={"screen20":(args.screen20_report,args.screen20_raw),
                  "flex41":(args.flex41_report,args.flex41_raw)}
    roots={"screen20":Path(args.screen20_shards),"flex41":Path(args.flex41_shards)}
    ledger=board.build({"screen20":(None,None),"flex41":(None,None)})
    ledger["live_note"]="Interim ranks are based only on completed shard artifacts, NOT a complete independent replicate."
    ledger["minimum_paired_games_for_provisional_rank"]=MIN_INTERIM_GAMES
    ledger["preliminary_card_effects_are_not_causal"]=True
    progress={}
    trials=[]
    for config in board.TRIALS:
        key=config["name"]
        rp,raw=trial_inputs[key]
        if rp and raw:
            t=board.load_trial(config,rp,raw)
            t["completed_shard_count"]=config["n"]//config["module"].PER_SHARD
            t["found_games"]=config["n"]
            validated=True
        else:
            t=shard_trial(config,roots[key])
            validated=False
        n=t["found_games"]
        progress[key]={"paired_games":n,"expected_games":config["n"],
            "complete_shards":t["completed_shard_count"],
            "expected_shards":config["n"]//config["module"].PER_SHARD,
            "source_validated_full_pool":validated,
            "eligible_for_provisional_ranking":validated or n>=MIN_INTERIM_GAMES}
        ledger["screen_status"][key].update(progress[key])
        ledger["screen_status"][key]["status"]=(
            "VALIDATED" if validated
            else f"PARTIAL_{n}_OF_{config['n']}" if n else "WAITING_FOR_COMPLETED_SHARDS")
        if validated or n>=MIN_INTERIM_GAMES:
            trials.append(t)
    comparisons=[]
    for t in trials:
        comparisons.extend(board.one_slot_contrasts(t))
    ranks=board.rank_cards(comparisons)
    ledger["live_progress"]=progress
    ledger["single_swap_comparison_count"]=len(comparisons)
    ledger["single_swap_head_to_heads"]=sorted(
        comparisons,key=lambda r:-r["metrics"]["T2"]["delta_pp"])
    ledger["exploratory_card_ranking"]=ranks
    for x in ledger["tracked_ramp_inventory"]:
        if x["card"] in {r["card"] for r in ranks}:
            x["screening_status"]="PROVISIONAL_DIRECT_PAIRED_EVIDENCE"
    ledger["fixed_anchor_cards_needing_future_dedicated_trials"]=[
        x for x in board.ANCHORS if x not in {r["card"] for r in ranks}]
    dest=Path(args.json_out)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(ledger,indent=2)+"\n")
    notes=[
        "# Dack Assertive ramp-piece leaderboard",
        "",
        "**LIVE SCREENING STATUS — not a finalized card ranking.** The provisional table only appears once at least 24 completed matched games from a screen are available. Both screens preserve the same frozen Assertive mulligan policy, and all numbers are conditional on the optimistic goldfish Dack-cast model.",
        "",
        "| Trial | Games recovered | Completed shards | Data status |",
        "|---|---:|---:|---|"
    ]
    for name,rec in progress.items():
        notes.append(f"| {name} | {rec['paired_games']}/{rec['expected_games']} | {rec['complete_shards']}/{rec['expected_shards']} | {'Fully pooled and validated' if rec['source_validated_full_pool'] else 'Partial exploratory evidence'} |")
    notes += ["","---",""]
    base=board.markdown(ledger).split("\n")
    # The central report has its own title; keep a single heading in live copy.
    base=base[1:]
    Path(args.md_out).write_text("\n".join(notes+base))
    print("ASSERTIVE_LIVE_LEADERBOARD_PASS",json.dumps({
        "progress":progress,
        "head_to_heads":len(comparisons),
        "provisional_ranked_cards":len(ranks),
        "top_provisional_cards":[{"card":x["card"],
            "observed_context_weighted_T2_delta_pp":x["exploratory_context_weighted_T2_pp"],
            "n_contexts":x["matched_single_card_contexts"]} for x in ranks[:8]]
    }),flush=True)

if __name__=="__main__":
    main()
