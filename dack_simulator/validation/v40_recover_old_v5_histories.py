#!/usr/bin/env python3
"""Recover historical ORIGINAL v5 decisions from archived raw GitHub shards.

Read-only: NO v5 gameplay, teacher rollouts, student training, or modification
of historical results. Reconstruct feature-visible unknown CARD COUNTS using
physical game ID and frozen 99-slot shuffle. Never export realized unseen order
or historical physical win outcomes into the teacher imitation corpus.

A historical benchmark group is *consumed evaluation data*: after recovery it
may be used for exploratory student training, but it is NOT a new holdout.
Distinct physical game IDs, not stage rows or rollout calls, are sample units.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import glob
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import dack_paired_counterfactual_v5_stable_chance_20261031 as teacher
from dack_simulator.validation.collect_teacher_london_v13 import finalists

ref = teacher.reference
SCHEMA = "dack_v40_reused_original_v5_historical_teacher_observations_v1"
DECK = "one_key_34"
# Immutable source paths, number of shards, unique physical ID bands.
GAME = {
    "v22_86k": ("benchmark_results/v22_real_keep_DP_paired_shards/v22_keep_pair_*.json.gz", 8, (86000, 86015)),
    "v22_88k": ("benchmark_results/v22_88k_v5_paired_shards/v22_88k_pair_*.json.gz", 32, (88000, 88063)),
    "v25_96k": ("benchmark_results/v25_96k_full_game_shards/v25_96k_*.json.gz", 64, (96000, 96255)),
    "v26_97k": ("benchmark_results/v26_97k_full_game_shards/v26_97k_*.json.gz", 64, (97000, 97255)),
    "v27_98k": ("benchmark_results/v27_98k_full_game_shards/v27_98k_*.json.gz", 64, (98000, 98255)),
    "v32_110k": ("benchmark_results/v32_110k_shards/v32_110k_*.json.gz", 64, (110000, 110255)),
    "v33b_115k": ("benchmark_results/v33b_prospective_115k_shards/v33b_115k_*.json.gz", 64, (115000, 115255)),
}
DEDICATED = {
    "v13_teacher": ("datasets/teacher_v13_20261031/distill_v13_*.jsonl.gz", 24, (60000, 61007)),
    "v14_teacher": ("datasets/teacher_v14_expansion/v14_*.jsonl.gz", 160, (60016, 61039)),
    "v15_student_visited": ("datasets/teacher_v15_student_states/v15_*.jsonl.gz", 48, (67100, 68115)),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def outer(gid):
    seed = int(ref.SPEC["seed_base"]) + int(gid) * ref.SEED_STRIDE
    seat, orders = ref.stage_slots(seed)
    return seat, orders


def convert(gid, stage, seat, seven, hand, bottom, kept, raw,
            threshold, sampled_t1, refined, source, sampling, original_candidates=None,
            seven_slots=None, keep_n=None, actual_v5_natural=None):
    slot_seat, orders = outer(gid)
    assert seat == slot_seat and 0 <= stage < 8
    stage_kn = int(ref.sim.STAGES[stage])
    assert keep_n is None or int(keep_n) == stage_kn
    deck = ref.SLOT_VARIANTS[DECK]
    order = orders[stage]
    assert seven_slots is None or list(order[:7]) == list(seven_slots)
    assert list(seven) == [deck[s] for s in order[:7]], (source, gid, stage, "seven mismatch")
    unknown = tuple(deck[s] for s in order[7:])
    assert len(unknown) == 92
    assert Counter(seven) + Counter(unknown) == Counter(deck.values())
    assert Counter(hand) + Counter(bottom) == Counter(seven)
    assert len(hand) == stage_kn and len(bottom) == 7-stage_kn
    opts = finalists(tuple(seven), stage_kn, tuple(unknown))
    possible = [i for i, item in enumerate(opts)
                if Counter(item["hand"]) == Counter(hand)
                and tuple(item["bottom"]) == tuple(bottom)]
    if not possible:
        raise AssertionError(("v5 retained hand/bottom not in top12", source, gid, stage,
                              list(seven), list(hand), list(bottom)))
    if original_candidates is not None:
        # The archived teacher records stored EXACT v5 top-12 candidates.
        assert len(original_candidates) == len(opts)
        for old, new in zip(original_candidates, opts):
            assert Counter(old["hand"]) == Counter(new["hand"])
            assert tuple(old["bottom"]) == tuple(new["bottom"])
    row = {
        "type": "stage", "schema": SCHEMA, "game_id": int(gid),
        "group_id": f"{DECK}:{gid}", "source": source,
        "sampling": sampling,
        "naturally_reached_by_v5": actual_v5_natural,
        "seat": int(seat), "stage": int(stage), "keep_n": stage_kn,
        "seven": list(seven),
        "unknown_counts": dict(sorted(Counter(unknown).items())),
        "teacher_keep": bool(kept), "teacher_raw": float(raw),
        "teacher_threshold": float(threshold),
        "teacher_sampled_t1": float(sampled_t1),
        "teacher_refined": bool(refined),
        "teacher_hand": list(hand), "teacher_bottom": list(bottom),
        "teacher_candidate_index": possible[0], "candidate_rows": opts,
        "no_hidden_92_order_exported": True,
        "no_historical_game_result_exported": True,
        "not_independent_prospective_holdout": True,
    }
    assert 0 <= row["teacher_candidate_index"] < len(row["candidate_rows"])
    return row


def recover_game(source, pattern, shard_count, interval, outputs, ledger):
    paths = sorted(glob.glob(str(ROOT/pattern)))
    assert len(paths) == shard_count, (source, "missing historical shards", len(paths))
    observed = set()
    for path in paths:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            item = json.load(f)
        assert item["status"] == "PASS", (source, path)
        assert isinstance(item["rows"], list)
        for rec in item["rows"]:
            gid = int(rec["game_id"])
            assert interval[0] <= gid <= interval[1]
            assert gid not in observed
            observed.add(gid)
            v5 = rec["v5"]
            seat = int(v5["seat"])
            history = v5["history"]
            assert history and history[-1]["kept"], (source, gid)
            assert len(history) <= 8
            assert [int(h["stage"]) for h in history] == list(range(len(history)))
            for h in history:
                out = convert(
                    gid, int(h["stage"]), seat, h["seven"],
                    h["hand"], h["bottom"], h["kept"],
                    h["raw"], h["threshold"], h["sampled_t1"], h["refined"],
                    source, "v5_naturally_reached_full_game",
                    seven_slots=h["seven_slots"], keep_n=h["keep_n"],
                    actual_v5_natural=True)
                outputs.append(out)
                ledger[source]["stage_records"] += 1
                ledger[source]["nonstructural_teacher_bottom"] += (out["teacher_candidate_index"] > 0)
        ledger[source]["shards"] += 1
    assert observed == set(range(interval[0], interval[1]+1)), (source, len(observed))
    ledger[source]["physical_groups"] = len(observed)
    ledger[source]["original_outcome_used_as_model_label"] = 0


def recover_dedicated(source, pattern, shard_count, interval, outputs, ledger, used_gids):
    paths = sorted(glob.glob(str(ROOT/pattern)))
    assert len(paths) == shard_count, (source, len(paths))
    ids = set()
    for path in paths:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            records = [json.loads(s) for s in f if s.strip()]
        assert records and records[0]["type"] == "metadata"
        m = records[0]
        assert m["source_manifest_sha256"] == sha(ref.MANIFEST_PATH)
        assert m["source_spec_sha256"] == sha(ref.SPEC_PATH)
        assert m.get("games") == 1, (source, path, m.get("games"))
        gid = int(m["start"])
        assert interval[0] <= gid <= interval[1] and gid not in ids
        assert gid not in used_gids
        assert len(records) > 1
        ids.add(gid)
        for h in records[1:]:
            assert h["type"] == "stage" and int(h["game_id"]) == gid
            assert h.get("variant", DECK) == DECK
            out = convert(
                gid, int(h["stage"]), int(h["seat"]),
                h["seven"], h["teacher_selected_hand"], h["teacher_selected_bottom"],
                h["teacher_keep"], h["teacher_raw"], h["teacher_threshold"],
                h["teacher_sampled_t1"], h["teacher_refined"],
                source, ("v5_student_visited" if source == "v15_student_visited"
                         else "v5_naturally_reached_teacher_corpus"),
                original_candidates=h.get("candidate_rows"),
                keep_n=h["keep_n"],
                actual_v5_natural=(None if source == "v15_student_visited" else True))
            outputs.append(out)
            ledger[source]["stage_records"] += 1
            ledger[source]["nonstructural_teacher_bottom"] += out["teacher_candidate_index"] > 0
        ledger[source]["shards"] += 1
    assert len(ids) == shard_count
    ledger[source]["physical_groups"] = len(ids)
    return ids


def run(out, report):
    assert len(ref.SLOTS) == 99
    outputs = []
    ledger = defaultdict(Counter)
    used_gids = set()
    for src, (pattern, count, interval) in GAME.items():
        recover_game(src, pattern, count, interval, outputs, ledger)
        used_gids |= set(range(interval[0], interval[1] + 1))
    for src, (pattern, count, interval) in DEDICATED.items():
        ids = recover_dedicated(src, pattern, count, interval, outputs, ledger, used_gids)
        used_gids |= ids
    assert len(used_gids) == sum(s["physical_groups"] for s in ledger.values())
    assert len(used_gids) == 1592, (len(used_gids), "historical group total changed")
    assert len(outputs) > len(used_gids)
    # Stage uniqueness must be within each physically distinct source group.
    group_stage = set()
    counts = Counter()
    for r in outputs:
        key = (r["game_id"], r["stage"])
        assert key not in group_stage, key
        group_stage.add(key)
        counts[f"london_stage_{r['stage']}"] += 1
        counts["teacher_keeps"] += int(r["teacher_keep"])
        counts["teacher_mulls"] += int(not r["teacher_keep"])
    outputs.sort(key=lambda x: (x["game_id"], x["stage"]))
    p = Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            "type": "metadata", "schema": SCHEMA, "teacher": "actual_original_v5",
            "independent_physical_groups": len(used_gids),
            "reused_archived_historical_data": True,
            "original_model_assessment_cohorts_consumed_not_holdouts": True,
            "source_manifest_sha256": sha(ref.MANIFEST_PATH),
            "source_spec_sha256": sha(ref.SPEC_PATH),
            "no_physical_gameplay_or_v5_recalculation": True,
            "no_realized_future_order_or_outcome_exports": True,
        }, sort_keys=True)+"\n")
        for r in outputs:
            f.write(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")
    result = {
        "schema": SCHEMA, "status": "PASS", "data_path": str(p),
        "data_sha256": sha(p), "group_n": len(used_gids),
        "stage_n": len(outputs), "groups_not_rows_are_independent": True,
        "source_counts": {source: dict(ledger[source]) for source in sorted(ledger)},
        "stage_counts": dict(counts),
        "historical_holdout_status": "ALL_CONSUMED__not_independent_new_validation",
        "v15_student_state_sampling_not_population_representative": True,
        "no_gameplay_executed": True,
        "no_v5_teacher_resampled": True,
        "not_model_approved": True,
    }
    dest = Path(report)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print("DACK_V40_ARCHIVED_TRUE_V5_1592_GROUP_RECOVERY_PASS",
          json.dumps({"group_n":len(used_gids),"stage_n":len(outputs),
                      "source_counts":result["source_counts"],
                      "data_sha256":result["data_sha256"]}, sort_keys=True),
          flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="datasets/v40_recovered_original_v5_history_1592.jsonl.gz")
    p.add_argument("--report", default="benchmark_results/v40_recovered_original_v5_1592_summary.json")
    x = p.parse_args()
    run(x.out, x.report)
