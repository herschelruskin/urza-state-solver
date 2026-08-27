#!/usr/bin/env python3
"""Focused regressions for explicit opening seat / Gemstone Caverns context."""

from __future__ import annotations

from dataclasses import dataclass

from phase5_mulligan import (
    MulliganEvaluationError,
    OpeningEnvironment,
    OpeningKeepEvaluator,
    OpeningPregameChoice,
    NO_PREGAME_CHOICE,
    opening_runtime,
    unique_pregame_choices,
)


def deck_and_seven():
    seven=(
        "Gemstone Caverns",
        "Sol Ring",
        "Island",
        "Mystical Tutor",
        "Vexing Bauble",
        "Mana Vault",
        "Swan Song",
    )
    rest=tuple(f"Filler {i:02d}" for i in range(92))
    deck=seven+rest
    assert len(deck)==99
    return deck,seven


def test_seat_semantics():
    play=OpeningEnvironment(seat=1,player_count=4)
    draw2=OpeningEnvironment(seat=2,player_count=4)
    draw4=OpeningEnvironment(seat=4,player_count=4)
    assert not play.caverns_live
    assert draw2.caverns_live
    assert draw4.caverns_live
    assert play.key()!=draw2.key()
    print("seat 1 Caverns-dead; later Commander seats Caverns-live: PASS")


def test_pregame_choice_surface():
    _,seven=deck_and_seven()
    dead=unique_pregame_choices(seven,OpeningEnvironment(seat=1))
    live=unique_pregame_choices(seven,OpeningEnvironment(seat=2))
    assert dead==(NO_PREGAME_CHOICE,)
    assert len(live)==7
    assert live[0]==NO_PREGAME_CHOICE
    assert {
        choice.exile_card for choice in live if choice.use_caverns
    }==set(seven)-{"Gemstone Caverns"}
    print("Caverns live exposes decline plus every distinct legal exile: PASS")


def test_physical_zone_resolution_and_value_identity():
    deck,seven=deck_and_seven()
    live=OpeningEnvironment(seat=3)
    choice=OpeningPregameChoice(True,"Swan Song")
    used=opening_runtime(
        deck,seven,(),
        opening_environment=live,
        pregame_choice=choice,
        rollout_game_seed=11,
    )
    state=used.true_state
    assert "Gemstone Caverns" not in state.hand
    assert "Swan Song" not in state.hand
    assert state.exile==("Swan Song",)
    assert len(state.battlefield)==1
    assert state.battlefield[0].name=="Gemstone Caverns"
    assert state.battlefield[0].mode=="luck"
    assert state.battlefield[0].counters==1
    assert state.trace[-1]=="pregame Caverns exiles Swan Song"

    declined=opening_runtime(
        deck,seven,(),
        opening_environment=live,
        pregame_choice=NO_PREGAME_CHOICE,
        rollout_game_seed=11,
    )
    assert "Gemstone Caverns" in declined.true_state.hand
    assert declined.true_state.battlefield==()
    assert declined.true_state.exile==()
    assert used.value_key()!=declined.value_key()

    try:
        opening_runtime(
            deck,seven,(),
            opening_environment=OpeningEnvironment(seat=1),
            pregame_choice=choice,
        )
    except MulliganEvaluationError:
        pass
    else:
        raise AssertionError("seat 1 incorrectly allowed Gemstone Caverns pregame use")
    print("Caverns choice materializes exact hand/battlefield/exile state: PASS")


@dataclass
class FakeEpisodeResult:
    runtime: object
    won: bool

    @property
    def won_by_horizon(self):
        return bool(self.won)

    @property
    def win_turn(self):
        return 1 if self.won else None

    @property
    def win_family(self):
        return "caverns-test" if self.won else ""

    @property
    def terminal_reason(self):
        return "win" if self.won else "horizon"


def fake_episode_runner(runtime,*,horizon,policy,max_steps):
    # Make one particular Caverns exile strictly best. This proves the opening
    # evaluator is optimizing the real pregame choice instead of importing the
    # Oracle's legacy card-priority heuristic.
    won="Swan Song" in runtime.true_state.exile
    return FakeEpisodeResult(runtime,won)


def test_keep_value_jointly_optimizes_caverns_choice():
    deck,seven=deck_and_seven()
    live_eval=OpeningKeepEvaluator(
        deck,
        rollout_count=2,
        mc_root_seed=17,
        horizon=6,
        episode_runner=fake_episode_runner,
        opening_environment=OpeningEnvironment(seat=2),
    ).evaluate(seven,stage=1)
    assert live_eval.opening_environment.seat==2
    assert live_eval.pregame_variants_evaluated==7
    assert live_eval.best.pregame_choice==OpeningPregameChoice(True,"Swan Song")
    assert live_eval.best.value.win_probability==1.0

    dead_eval=OpeningKeepEvaluator(
        deck,
        rollout_count=2,
        mc_root_seed=17,
        horizon=6,
        episode_runner=fake_episode_runner,
        opening_environment=OpeningEnvironment(seat=1),
    ).evaluate(seven,stage=1)
    assert dead_eval.pregame_variants_evaluated==1
    assert dead_eval.best.pregame_choice==NO_PREGAME_CHOICE
    assert dead_eval.best.value.win_probability==0.0
    print("opening value optimizes Caverns use/exile only when seat makes it live: PASS")


def test_bottomed_caverns_has_no_pregame_branch():
    deck,seven=deck_and_seven()
    evaluation=OpeningKeepEvaluator(
        deck,
        rollout_count=1,
        mc_root_seed=23,
        horizon=6,
        episode_runner=fake_episode_runner,
        opening_environment=OpeningEnvironment(seat=2),
    ).evaluate(
        seven,
        stage=2,
        candidate_bottoms=(("Gemstone Caverns",),),
    )
    assert evaluation.pregame_variants_evaluated==1
    assert evaluation.best.bottom==("Gemstone Caverns",)
    assert evaluation.best.pregame_choice==NO_PREGAME_CHOICE
    print("bottoming Caverns removes the pregame Caverns branch: PASS")


def main():
    test_seat_semantics()
    test_pregame_choice_surface()
    test_physical_zone_resolution_and_value_identity()
    test_keep_value_jointly_optimizes_caverns_choice()
    test_bottomed_caverns_has_no_pregame_branch()
    print("PHASE5 CAVERNS OPENING SMOKE: ALL PASS")


if __name__=="__main__":
    main()
