#!/usr/bin/env python3
"""Static integrity checks for the versioned human calibration fixtures.

This smoke validates fixture semantics only. It deliberately does not require a
solver policy to agree with human choices or exactly reproduce historical rates.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FIXTURE_DIR = ROOT / "benchmarks" / "human"
MULLIGAN_SUMMARY = FIXTURE_DIR / "human_mulligan_benchmark_summary.json"
MULLIGAN_EXACT = FIXTURE_DIR / "human_mulligan_exact_hands.json"
GOLDFISH = FIXTURE_DIR / "human_goldfish_baseline.json"


def expected_keep_size(mulligan_count: int) -> int:
    if mulligan_count in (0, 1):
        return 7
    return 8 - mulligan_count


def main() -> None:
    mull = json.loads(MULLIGAN_SUMMARY.read_text(encoding="utf-8"))
    exact = json.loads(MULLIGAN_EXACT.read_text(encoding="utf-8"))
    gold = json.loads(GOLDFISH.read_text(encoding="utf-8"))

    assert mull["n_rows"] == 36
    assert mull["mulligan_semantics"]["stages"] == {
        "0": 7, "1": 7, "2": 6, "3": 5, "4": 4, "5": 3, "6": 2,
    }
    assert mull["mulligan_semantics"]["solver_keep_floor"] == 2
    assert mull["rating_semantics"]["comparability"] == "within keep_size only"
    assert mull["quality"]["primary_benchmark_usable_count"] == 35
    assert mull["quality"]["primary_excluded_hand_ids"] == [10]
    assert mull["quality"]["current_repo_runnable_count"] == 35
    assert mull["quality"]["normalized_card_slot_hand_ids"] == [24, 34]
    assert mull["quality"]["historical_two_card_goldfishes"] == 5
    assert mull["descriptive"]["decision_counts"] == {"Keep": 27, "Mulligan": 9}
    assert mull["descriptive"]["by_keep_size"]["7"] == {"n": 22, "keeps": 13, "mulligans": 9}
    assert mull["descriptive"]["by_keep_size"]["2"] == {"n": 0, "keeps": 0, "mulligans": 0}
    assert mull["descriptive"]["seven_card_stage"]["initial_m0"]["keep_rate"] == 0.5
    assert mull["descriptive"]["seven_card_stage"]["free_second_m1"]["keep_rate"] == 2 / 3
    assert mull["counterfactual_keep_at_six"]["22"] == {"decision": "Keep", "bottom": ["Vexing Bauble"]}
    assert mull["counterfactual_keep_at_six"]["23"]["decision"] == "Uncertain"
    assert mull["counterfactual_keep_at_six"]["23"]["lean"] == "Mulligan"
    assert mull["counterfactual_keep_at_six"]["32"]["decision"] == "Uncertain"
    assert mull["counterfactual_keep_at_six"]["32"]["lean"] == "Mulligan"
    assert mull["counterfactual_keep_at_six"]["35"]["decision"] == "Mulligan"

    assert exact["schema_version"] == 2
    assert exact["deck_snapshot"]["baseline"] == "Codex Shredder deck"
    hands = exact["hands"]
    assert len(hands) == 36
    assert [hand["hand_id"] for hand in hands] == list(range(1, 37))
    by_id = {hand["hand_id"]: hand for hand in hands}
    usable = runnable = 0
    excluded = []
    for hand in hands:
        stage = int(hand["mulligan_count"])
        keep_size = expected_keep_size(stage)
        assert hand["keep_size"] == keep_size
        assert hand["decision"] in {"Keep", "Mulligan"}
        if hand["primary_benchmark_usable"]:
            usable += 1
            assert len(hand["drawn_seven"]) == 7
            if hand["decision"] == "Keep":
                assert len(hand["cards_bottomed"]) == 7 - keep_size
                assert hand["kept_hand"] is not None
                assert len(hand["kept_hand"]) == keep_size
                for card in hand["cards_bottomed"]:
                    assert card in hand["drawn_seven"]
        else:
            excluded.append(hand["hand_id"])
        if hand["current_repo_runnable"]:
            runnable += 1
            assert hand["primary_benchmark_usable"]
            assert not hand["cards_not_in_repo_decklist"]

    assert usable == 35
    assert runnable == 35
    assert excluded == [10]
    assert by_id[30]["drawn_seven"][-1] == "Swan Song"
    assert by_id[36]["drawn_seven"][-1] == "Uthros Research Craft"
    for hand_id in (24, 34):
        hand = by_id[hand_id]
        assert "Codex Shredder" in hand["drawn_seven"]
        assert "Fugitive Droid" not in hand["drawn_seven"]
        assert "Fugitive Droid" in hand["recorded_drawn_seven"]
        assert hand["card_slot_normalization"]["benchmark_card"] == "Codex Shredder"

    assert gold["source_rows"] == 250
    assert gold["deck_snapshot"]["baseline"] == "Codex Shredder deck"
    assert gold["historical_tracking_horizon"] == 7
    assert gold["simulator_terminal_horizon"] == 6
    assert gold["blank_winning_turn_semantics"] == ">T7 / never"
    assert gold["mystic_rhystic_goldfish_rule"] == "2 additional draws per full turn cycle while active"
    assert gold["mulligan_semantics"]["stages"]["6"] == 2
    assert gold["mulligan_semantics"]["historical_two_card_keeps"] == 5
    assert gold["mulligan_semantics"]["solver_keep_floor"] == 2
    assert gold["mull_distribution"]["6"] == 5
    assert gold["outcomes"]["win_turn_counts"] == {"3": 79, "4": 129, "5": 27, "6": 9, "7": 5}
    assert gold["outcomes"]["never_gt_t7_count"] == 1
    assert gold["cumulative"]["win_by_t3"]["count"] == 79
    assert gold["cumulative"]["win_by_t4"]["count"] == 208
    assert gold["cumulative"]["win_by_t6"]["count"] == 244
    assert gold["cumulative"]["loss_at_t6_horizon"]["count"] == 6

    print("PASS annotated-hand benchmark summary semantics")
    print(f"PASS exact annotated hands rows={len(hands)} usable={usable} repo_runnable={runnable}")
    print("PASS historical mulligan_count=6 -> keep 2 semantics")
    print("PASS 250-run historical outcome baseline semantics")
    print("HUMAN BENCHMARK FIXTURE SMOKE: ALL PASS")


if __name__ == "__main__":
    main()
