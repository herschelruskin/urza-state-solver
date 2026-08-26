#!/usr/bin/env python3
"""Regression coverage for Knack/Helix replay mana classes."""

import urza_solver as solver


def margin(card, *, urza, battlefield=()):
    source=solver.Perm("Valley Floodcaller",instance_tag=-999)
    state=solver.State(
        turn=4,
        library=(),
        hand=(card,),
        battlefield=tuple(battlefield),
        urza=urza,
        commander_in_command_zone=not urza,
    )
    return solver.replay_mana_margin(state,source,card)


def test_native_profiles():
    assert margin("Sol Ring",urza=False)>0
    assert margin("Mana Vault",urza=False)>0
    assert margin("Grim Monolith",urza=False)>0

    # Opal is native-positive only when the replayed Opal restores metalcraft.
    assert margin("Mox Opal",urza=False)==0
    assert margin(
        "Mox Opal",
        urza=False,
        battlefield=(solver.Perm("Welding Jar"),solver.Perm("Tormod's Crypt")),
    )>0

    for card in sorted(solver.ZERO_ARTIFACTS-{"Mox Diamond","Mox Opal"}):
        assert margin(card,urza=False)==0,(card,margin(card,urza=False))
    assert margin("Basalt Monolith",urza=False)==0
    assert solver.replay_mana_margin(
        solver.State(turn=4,library=(),hand=("Mox Diamond",),battlefield=()),
        solver.Perm("Valley Floodcaller",instance_tag=-999),
        "Mox Diamond",
    ) is None
    print("native replay positive/neutral boundary: PASS")


def test_urza_profiles():
    for card in sorted(solver.URZA_REPLAY_POSITIVE_BASE):
        value=margin(card,urza=True)
        assert value>0,(card,value)

    # Cam is the conditional thirteenth positive: a distinct artifact creature
    # supplies the second Urza conversion through Cam's ETB untap.
    cam=margin(
        "Sewer-veillance Cam",
        urza=True,
        battlefield=(solver.Perm("Spellskite",instance_tag=7),),
    )
    assert cam>0,cam
    assert margin("Sewer-veillance Cam",urza=True)==0

    # Current deck uses Codex Shredder; Fugitive Droid is the historical slot
    # alias and is intentionally not required to be engine-runnable here.
    current_neutral=solver.URZA_REPLAY_NEUTRAL_BASE-{"Fugitive Droid"}
    assert len(current_neutral)==15
    for card in sorted(current_neutral):
        value=margin(card,urza=True)
        assert value==0,(card,value)

    assert margin("Welding Jar",urza=False)==0
    assert margin("Welding Jar",urza=True)>0
    assert margin("Aether Spellbomb",urza=True)==0
    print("Urza-enabled replay positive/neutral boundary: PASS")


def test_producer_promotions():
    # VFC + Knack + neutral one-drop + Station should become positive.
    vfc=solver.Perm(
        "Valley Floodcaller",sick=False,knack_granted=True,instance_tag=1
    )
    state=solver.State(
        turn=4,
        library=("Island",),
        hand=("Aether Spellbomb",),
        battlefield=(
            solver.Perm(solver.COMMANDER,sick=False,instance_tag=2),
            vfc,
            solver.Perm("Grinding Station",instance_tag=3),
        ),
        urza=True,
        commander_in_command_zone=False,
        blue=1,
    )
    assert solver.replay_mana_margin(state,vfc,"Aether Spellbomb")>0
    won=solver.check_win(state)
    assert won.won and won.win_family=="Knack/Helix + Valley Floodcaller"

    # Golem's own untap is reserved for the Knack bounce; Gadgeteer is the
    # additional producer that promotes a neutral Top replay above zero.
    golem=solver.Perm(
        "Battered Golem",sick=False,knack_granted=True,instance_tag=11
    )
    state=solver.State(
        turn=4,
        library=("Island",),
        hand=("Sensei's Divining Top",),
        battlefield=(
            solver.Perm(solver.COMMANDER,sick=False,instance_tag=12),
            golem,
            solver.Perm("Forensic Gadgeteer",sick=False,instance_tag=13),
        ),
        urza=True,
        commander_in_command_zone=False,
        blue=1,
    )
    assert solver.replay_mana_margin(state,golem,"Sensei's Divining Top")>0
    won=solver.check_win(state)
    assert won.won and won.win_family=="Knack/Helix + Battered Golem"

    # Multiple visible producers can promote a normally negative artifact too.
    state=solver.State(
        turn=4,
        library=("Island",),
        hand=("The Reality Chip",),
        battlefield=(
            solver.Perm(solver.COMMANDER,sick=False,instance_tag=20),
            golem,
            solver.Perm("Grinding Station",instance_tag=21),
            solver.Perm("Forensic Gadgeteer",sick=False,instance_tag=22),
        ),
        urza=True,
        commander_in_command_zone=False,
    )
    assert solver.replay_mana_margin(state,golem,"The Reality Chip")>0
    print("visible producers dynamically promote replay classes: PASS")


def main():
    test_native_profiles()
    test_urza_profiles()
    test_producer_promotions()
    print("PHASE5 REPLAY ECONOMICS SMOKE: ALL PASS")


if __name__=="__main__":
    main()
