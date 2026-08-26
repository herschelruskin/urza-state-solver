#!/usr/bin/env python3
"""Static integrity checks for the versioned human calibration summaries.

This smoke validates fixture semantics only.  It deliberately does not require a
solver policy to agree with human choices or exactly reproduce historical rates.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FIXTURE_DIR = ROOT / "benchmarks" / "human"
MULLIGAN = FIXTURE_DIR / "human_mulligan_benchmark_summary.json"
GOLDFISH = FIXTURE_DIR / "human_goldfish_baseline.json"


def main() -> None:
    mull = json.loads(MULLIGAN.read_text(encoding="utf-8"))
    gold = json.loads(GOLDFISH.read_text(encoding="utf-8"))

    assert mull["n_rows"] == 36
    assert mull["mulligan_semantics"]["stages"] == {
        "0": 7,
        "1": 7,
        "2": 6,
        "3": 5,
        "4": 4,
        "5": 3,
    }
    assert mull["rating_semantics"]["comparability"] == "within keep_size only"
    assert mull["quality"]["primary_benchmark_usable_count"] == 33
    assert mull["quality"]["primary_excluded_hand_ids"] == [10, 30, 36]
    assert mull["quality"]["current_repo_runnable_count"] == 31
    assert mull["quality"]["deck_snapshot_drift_hand_ids"] == [24, 34]
    assert mull["descriptive"]["decision_counts"] == {"Keep": 27, "Mulligan": 9}
    assert mull["descriptive"]["by_keep_size"]["7"] == {
        "n": 22,
        "keeps": 13,
        "mulligans": 9,
    }
    assert mull["descriptive"]["seven_card_stage"]["initial_m0"]["keep_rate"] == 0.5
    assert mull["descriptive"]["seven_card_stage"]["free_second_m1"]["keep_rate"] == 2 / 3

    assert gold["source_rows"] == 250
    assert gold["historical_tracking_horizon"] == 7
    assert gold["simulator_terminal_horizon"] == 6
    assert gold["blank_winning_turn_semantics"] == ">T7 / never"
    assert gold["mystic_rhystic_goldfish_rule"] == "2 additional draws per full turn cycle while active"
    assert gold["outcomes"]["win_turn_counts"] == {
        "3": 79,
        "4": 129,
        "5": 27,
        "6": 9,
        "7": 5,
    }
    assert gold["outcomes"]["never_gt_t7_count"] == 1
    assert gold["cumulative"]["win_by_t3"]["count"] == 79
    assert gold["cumulative"]["win_by_t4"]["count"] == 208
    assert gold["cumulative"]["win_by_t6"]["count"] == 244
    assert gold["cumulative"]["loss_at_t6_horizon"]["count"] == 6

    print("PASS annotated-hand benchmark semantics")
    print("PASS 250-run historical outcome baseline semantics")
    print("HUMAN BENCHMARK FIXTURE SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
