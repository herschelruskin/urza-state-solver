#!/usr/bin/env python3
"""Human-audited deterministic Urza win-line catalog.

These are terminal *states*, not tutor priorities.  Strategic search/Q still decides
which line to pursue.  Spellseeker's one-card Cam route is deliberately excluded
from automatic terminal recognition because its mana/ready-creature requirements
must be executed or proven by a line planner.
"""

import urza_solver as solver


U = solver.Perm(solver.COMMANDER, sick=False, instance_tag=100)


def won(state, family):
    row=solver.check_win(state)
    assert row.won and row.win_family==family,(family,row.win_family,state)
    return row


def test_power_artifact():
    for rock,family in (
        ("Grim Monolith","Power Artifact + Grim"),
        ("Basalt Monolith","Power Artifact + Basalt"),
    ):
        won(solver.State(
            turn=4,library=(),hand=(),urza=True,commander_in_command_zone=False,
            pa_target=rock,
            battlefield=(U,solver.Perm(rock),solver.Perm("Power Artifact")),
        ),family)
    print("catalog: Power Artifact monoliths PASS")


def test_chip_producers():
    for producer in sorted(solver.PRODUCERS):
        won(solver.State(
            turn=4,library=("Island",),hand=(),urza=True,commander_in_command_zone=False,
            chip_attached=True,chip_target=solver.COMMANDER,
            battlefield=(
                U,
                solver.Perm("Sensei's Divining Top"),
                solver.Perm("The Reality Chip",mode="chip_attached"),
                solver.Perm(producer,sick=False),
            ),
        ),"Top + Reality Chip")
    print("catalog: attached Chip + Top + all 3 producers PASS")


def test_ftt():
    won(solver.State(
        turn=4,library=("Island",),hand=(),urza=True,commander_in_command_zone=False,
        ftt_level=3,spell_cast_this_turn=True,
        battlefield=(U,solver.Perm("Sensei's Divining Top"),solver.Perm("Fortune Teller's Talent")),
    ),"Top + FTT L3")

    for producer in sorted(solver.PRODUCERS):
        won(solver.State(
            turn=4,library=("Island",),hand=(),urza=True,commander_in_command_zone=False,
            ftt_level=2,spell_cast_this_turn=True,
            battlefield=(
                U,solver.Perm("Sensei's Divining Top"),
                solver.Perm("Fortune Teller's Talent"),
                solver.Perm(producer,sick=False),
            ),
        ),"Top + FTT L2 + producer")
    print("catalog: FTT L3 and L2 + all 3 producers PASS")


def test_chrome_dome():
    for producer in ("Grinding Station","Battered Golem"):
        won(solver.State(
            turn=4,library=(),hand=(),urza=True,commander_in_command_zone=False,
            colorless=5,
            battlefield=(U,solver.Perm("Chrome Dome"),solver.Perm(producer,sick=False)),
        ),"Chrome Dome")
    # Obscure positive-copy line: PA on Dome + Gadgeteer reduces {5} to {2};
    # Mana Vault copies enter untapped and tap for {3}, so each loop nets +1.
    won(solver.State(
        turn=4,library=(),hand=(),urza=True,commander_in_command_zone=False,
        pa_target="Chrome Dome",
        battlefield=(
            U,
            solver.Perm("Chrome Dome",sick=False),
            solver.Perm("Forensic Gadgeteer",sick=False),
            solver.Perm("Power Artifact"),
            solver.Perm("Mana Vault"),
        ),
    ),"Chrome Dome + PA + Gadgeteer + Mana Vault")
    print("catalog: Chrome Dome Station/Golem + PA/Gadgeteer/Vault PASS")


def test_gadgeteer():
    won(solver.State(
        turn=4,library=(),hand=(),urza=True,commander_in_command_zone=False,
        battlefield=(U,solver.Perm("Basalt Monolith"),solver.Perm("Forensic Gadgeteer",sick=False)),
    ),"Basalt + Gadgeteer")

    for producer in ("Grinding Station","Battered Golem"):
        won(solver.State(
            turn=4,library=("Island",),hand=(),urza=True,commander_in_command_zone=False,
            battlefield=(
                U,solver.Perm("Sensei's Divining Top"),
                solver.Perm("Forensic Gadgeteer",sick=False),
                solver.Perm(producer,sick=False),
            ),
        ),"Top + Gadgeteer + producer")
    print("catalog: Gadgeteer Basalt and Top + producer PASS")


def test_knack_helix():
    # VFC + grant + positive replay artifact.
    vfc=solver.Perm("Valley Floodcaller",sick=False,knack_granted=True,instance_tag=1)
    won(solver.State(
        turn=4,library=("Island",),hand=("Welding Jar",),urza=True,
        commander_in_command_zone=False,battlefield=(U,vfc),
    ),"Knack/Helix + Valley Floodcaller")

    # VFC + neutral replay + a separate producer.
    won(solver.State(
        turn=4,library=("Island",),hand=("Aether Spellbomb",),urza=True,
        commander_in_command_zone=False,blue=1,
        battlefield=(U,vfc,solver.Perm("Grinding Station",instance_tag=2)),
    ),"Knack/Helix + Valley Floodcaller")

    # Golem + grant + positive replay artifact.
    golem=solver.Perm("Battered Golem",sick=False,knack_granted=True,instance_tag=11)
    won(solver.State(
        turn=4,library=("Island",),hand=("Welding Jar",),urza=True,
        commander_in_command_zone=False,battlefield=(U,golem),
    ),"Knack/Helix + Battered Golem")

    # Golem + neutral replay + a distinct producer.
    won(solver.State(
        turn=4,library=("Island",),hand=("Sensei's Divining Top",),urza=True,
        commander_in_command_zone=False,blue=1,
        battlefield=(U,golem,solver.Perm("Forensic Gadgeteer",sick=False,instance_tag=12)),
    ),"Knack/Helix + Battered Golem")

    # Cam remains its own deterministic recurrence once a ready grant is live.
    won(solver.State(
        turn=4,library=("Island",),hand=(),urza=True,commander_in_command_zone=False,
        battlefield=(U,solver.Perm("Sewer-veillance Cam"),golem),
    ),"Knack/Helix + Cam")
    print("catalog: Knack/Helix VFC/Golem/Cam families PASS")


def test_spellseeker_is_not_presence_terminal():
    state=solver.State(
        turn=4,
        library=("Banishing Knack","Retraction Helix","Transmute Artifact","Sewer-veillance Cam"),
        hand=("Spellseeker",),
        battlefield=(U,),
        blue=20,colorless=20,
        urza=True,commander_in_command_zone=False,
    )
    assert not solver.check_win(state).won
    print("catalog: Spellseeker remains a conversion choice, not presence terminal PASS")


def main():
    test_power_artifact()
    test_chip_producers()
    test_ftt()
    test_chrome_dome()
    test_gadgeteer()
    test_knack_helix()
    test_spellseeker_is_not_presence_terminal()
    print("PHASE5 WIN CATALOG SMOKE: ALL PASS")


if __name__=="__main__":
    main()
