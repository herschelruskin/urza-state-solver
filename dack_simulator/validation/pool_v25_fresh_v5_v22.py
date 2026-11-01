#!/usr/bin/env python3
"""Pool v25 fresh frozen-policy 96k paired experiment; never promote models."""
from __future__ import annotations
import gzip
import glob
import json
import math
import random
from pathlib import Path

FIRST, LAST, N = 96000, 96255, 256
POLICIES = ("v5", "v14_128", "v22_real_keep_DP")

def comparison(rows, policy, reference, threshold):
    d = [int(0 < r[policy]["turn"] <= threshold) -
         int(0 < r[reference]["turn"] <= threshold) for r in rows]
    n = len(d)
    gain, loss = d.count(1), d.count(-1)
    rng = random.Random(250000 + threshold * 100 + len(policy) * 13 + len(reference))
    boots = sorted(100 * sum(d[rng.randrange(n)] for _ in range(n)) / n
                   for _ in range(8000))
    discordant = gain + loss
    if discordant:
        tail = sum(math.comb(discordant, k)
                   for k in range(min(gain, loss) + 1))
        p = min(1.0, 2.0 * tail / (2 ** discordant))
    else:
        p = 1.0
    return {
        "delta_pp": 100 * sum(d) / n, "gain_games": gain, "loss_games": loss,
        "paired_bootstrap_95ci_pp": [boots[199], boots[7799]],
        "exploratory_exact_mcnemar_two_sided_p": p,
    }

def measures(rows, policy):
    z = [r[policy] for r in rows]
    return {
        "n": len(z), "T1": sum(x["turn"] == 1 for x in z),
        "T2": sum(x["turn"] in (1, 2) for x in z),
        "T3": sum(x["turn"] in (1, 2, 3) for x in z),
        "mean_keep_n": sum(x["keep_n"] for x in z) / len(z),
        "sum_simulation_seconds": round(sum(x["seconds"] for x in z), 4),
    }

def main():
    shards = sorted(glob.glob("collected/v25_96k_*.json.gz"))
    assert len(shards) == 64, ("missing 96k shard", len(shards))
    rows, hashes = [], None
    for shard in shards:
        with gzip.open(shard, "rt", encoding="utf-8") as f:
            doc = json.load(f)
        assert doc["schema"] == "dack_v25_fresh_reference_physical_shard"
        assert doc["status"] == "PASS" and doc["actual_gameplay_beam"] == 160
        assert doc["experimental_policy_approved"] is False
        assert doc["physical_first_seven_parity"] is True
        if hashes is None:
            hashes = doc["model_sha256"]
        else:
            assert hashes == doc["model_sha256"], "model changed across shards"
        assert len(doc["rows"]) == 4
        assert doc["game_ids"] == [doc["rows"][0]["game_id"], doc["rows"][-1]["game_id"]]
        rows += doc["rows"]
    rows.sort(key=lambda x: x["game_id"])
    assert [r["game_id"] for r in rows] == list(range(FIRST, LAST + 1))
    for row in rows:
        assert len({row[p]["seat"] for p in POLICIES}) == 1
        assert len({tuple(row[p]["history"][0]["seven_slots"]) for p in POLICIES}) == 1
    metrics = {p: measures(rows, p) for p in POLICIES}
    pairwise = {
        a + "_minus_" + b: {
            "T" + str(t): comparison(rows, a, b, t) for t in (1, 2, 3)
        }
        for a, b in (
            ("v22_real_keep_DP", "v5"),
            ("v14_128", "v5"),
            ("v22_real_keep_DP", "v14_128"),
        )
    }
    report = {
        "schema": "dack_v25_fresh_reference_full_game_N256",
        "status": "PASS", "game_ids": [FIRST, LAST],
        "independent_paired_physical_game_ids": N,
        "prespecified_primary_endpoint": "cumulative by Turn 2; paired v22 minus v5",
        "secondary_endpoints": "T1 and cumulative T3 descriptive",
        "goldfish_gameplay_beam": 160, "mulligan_model_approved": False,
        "model_sha256": hashes,
        "matched_first_physical_seven_verified": True,
        "metrics": metrics, "paired": pairwise,
        "observed_online_speedup_v5_over_v22":
            metrics["v5"]["sum_simulation_seconds"] /
            max(1e-6, metrics["v22_real_keep_DP"]["sum_simulation_seconds"]),
        "interpretation": "Exploratory independent full-game comparison. Goldfish Dack deployment, not multiplayer win rate. No noninferiority claim without a predefined margin and appropriately powered prospective test.",
        "training_use_forbidden": "96k outer-game IDs reserved as evaluation only",
    }
    target = Path("benchmark_results/v25_96k_fresh_v5_vs_v22_N256.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print("V25_FRESH_PAIRED_N256_PASS", json.dumps(report, sort_keys=True), flush=True)

if __name__ == "__main__":
    main()
