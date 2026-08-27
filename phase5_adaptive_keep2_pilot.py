#!/usr/bin/env python3
"""Tiny executable pilot for the forced keep-two adaptive stage.

This is not a calibrated mulligan model. It exists to prove the full nested path:
fresh seven -> all legal keep-two bottom multisets -> tie-preserving screen ->
fresh-world confirmation -> selective tutor-Q continuation -> stage-6 value.

Stage 6 is forced keep, so no current hand is compared against a future seven.
"""

from __future__ import annotations

import json
from pathlib import Path

from phase5_adaptive_mulligan import AdaptiveMulliganStageTrainer


def load_deck():
    cards=[]
    for raw in Path("decklist.txt").read_text(encoding="utf-8").splitlines():
        line=raw.strip()
        if not line:
            continue
        count,name=line.split(" ",1)
        if name=="Urza, Lord High Artificer":
            continue
        cards.extend([name]*int(count))
    assert len(cards)==99
    return tuple(cards)


def main():
    trainer=AdaptiveMulliganStageTrainer(
        load_deck(),
        hand_samples_per_stage=1,
        earliest_stage=6,
        screen_rollouts_per_bottom=1,
        confirm_rollouts_per_bottom=1,
        shortlist_size=4,
        mc_root_seed=2026082701,
        q_mc_root_seed=2026082702,
        horizon=6,
        screen_q_rollouts=1,
        confirm_q_rollouts=1,
        q_shortlist_size=3,
        max_episode_steps=512,
        strict_terminal_reasons=True,
    )
    model=trainer.train()
    stage=model.stage_estimate(6)
    assert stage.keep_size==2
    assert stage.kept_count==1
    assert stage.mulligan_count==0
    assert len(model.hand_decisions)==1
    assert model.hand_decisions[0].decision=="Keep"

    payload={
        "kind":"phase5-adaptive-keep2-pilot",
        "version":model.version,
        "mc_root_seed":model.mc_root_seed,
        "q_mc_root_seed":model.q_mc_root_seed,
        "stage":{
            "stage":stage.stage,
            "keep_size":stage.keep_size,
            "value":{
                "win_probability":stage.value.win_probability,
                "exact_win":list(stage.value.exact_win),
                "no_win":stage.value.no_win,
                "win_families":[list(x) for x in stage.value.win_families],
            },
            "sampled_hands":stage.sampled_hands,
            "kept_count":stage.kept_count,
            "mulligan_count":stage.mulligan_count,
            "legal_bottoms_screened":stage.legal_bottoms_screened,
            "bottoms_confirmed":stage.bottoms_confirmed,
            "chosen_terminal_reason_counts":[
                list(x) for x in stage.chosen_terminal_reason_counts
            ],
        },
        "decision":{
            "seven":list(model.hand_decisions[0].seven),
            "best_bottom":list(model.hand_decisions[0].best_bottom),
            "legal_bottom_count":model.hand_decisions[0].legal_bottom_count,
            "confirmed_bottom_count":model.hand_decisions[0].confirmed_bottom_count,
            "keep_value_key":list(model.hand_decisions[0].keep_value_key),
        },
        "q_cache":{
            "hits":model.q_cache_hits,
            "misses":model.q_cache_misses,
        },
    }
    Path("phase5_adaptive_keep2_pilot.json").write_text(
        json.dumps(payload,indent=2)+"\n",encoding="utf-8"
    )
    print(json.dumps(payload,indent=2))


if __name__=="__main__":
    main()
