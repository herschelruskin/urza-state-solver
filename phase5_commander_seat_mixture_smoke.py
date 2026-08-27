#!/usr/bin/env python3
"""Seat-conditioned Commander/Gemstone aggregation regression."""

from __future__ import annotations

from dataclasses import dataclass

from phase3_value_engine import WinDistributionValue
from phase5_mulligan import (
    CommanderSeatMulliganTrainer,
    OpeningEnvironment,
    commander_opening_environments,
    mix_commander_seat_values,
)


def value(p: float) -> WinDistributionValue:
    return WinDistributionValue(
        horizon=2,
        exact_win=(p, 0.0),
        no_win=1.0-p,
    )


def test_environment_surface():
    envs=commander_opening_environments(4)
    assert tuple(e.seat for e in envs)==(1,2,3,4)
    assert tuple(e.caverns_live for e in envs)==(False,True,True,True)
    assert all(e.player_count==4 for e in envs)
    print("Commander seat environments preserve Caverns live/dead split: PASS")


def test_post_policy_mixture():
    mixed=mix_commander_seat_values(
        ((1,value(0.10)),(2,value(0.30)),(3,value(0.50)),(4,value(0.70))),
        player_count=4,
    )
    assert abs(mixed.win_probability-0.40)<1e-12
    assert abs(mixed.exact_win[0]-0.40)<1e-12
    print("seat-conditioned values mix uniformly only after optimization: PASS")


@dataclass
class FakeStage:
    stage:int
    keep_size:int
    value:WinDistributionValue
    sampled_hands:int=1
    kept_count:int=1
    mulligan_count:int=0

    @property
    def keep_rate(self):
        return 1.0


@dataclass
class FakeModel:
    opening_environment:OpeningEnvironment

    def stage_estimate(self,stage:int):
        # seat 1 is intentionally weak; live Caverns seats are stronger.
        p=0.10 if self.opening_environment.seat==1 else 0.50
        return FakeStage(stage,7 if stage<2 else max(2,8-stage),value(p))


class FakeTrainer:
    def __init__(self,*args,opening_environment=None,**kwargs):
        self.environment=opening_environment

    def train(self):
        return FakeModel(self.environment)


def test_wrapper_separates_seats(monkeypatch_target=None):
    import phase5_mulligan as m

    original=m.MulliganStageTrainer
    m.MulliganStageTrainer=FakeTrainer
    try:
        model=CommanderSeatMulliganTrainer(
            ("Island",)*99,
            player_count=4,
            hand_samples_per_stage=1,
            rollout_count_per_bottom=1,
            horizon=2,
        ).train()
    finally:
        m.MulliganStageTrainer=original

    assert tuple(seat for seat,_ in model.seat_models)==(1,2,3,4)
    assert model.seat_model(1).opening_environment.caverns_live is False
    assert model.seat_model(2).opening_environment.caverns_live is True
    stage0=model.stage_estimate(0)
    assert abs(stage0.value.win_probability-0.40)<1e-12
    assert dict(stage0.seat_values)[1].win_probability==0.10
    assert dict(stage0.seat_values)[2].win_probability==0.50
    print("Commander wrapper trains distinct known-seat policies before mixture: PASS")


def main():
    test_environment_surface()
    test_post_policy_mixture()
    test_wrapper_separates_seats()
    print("PHASE5 COMMANDER SEAT MIXTURE SMOKE: ALL PASS")


if __name__=="__main__":
    main()
