#!/usr/bin/env python3
"""Focused Urza's Incubator audit for Dack Fayden, Helping Hand.

Oracle/model target:
- Dack Fayden, Helping Hand is a Human Advisor costing 4WW.
- Urza's Incubator costs 3; as it enters choose Human.
- Human creature spells cost 2 generic less.
The DACK simulator only cares about the first commander cast through turn 3, so
commander tax and reductions to unrelated creatures are outside this focused path.
"""
from dataclasses import replace
import dack_v077_full_deck_accel as m

d=m.d

def main():
    assert m.selftest()
    lib=tuple(d.COMBO_CREATURES)

    # Base Dack is 4WW: two white plus four generic.
    base=d.State(1,(),lib,(),w=2,c=4)
    assert d.can_cast_dack(base), "4WW baseline should cast"
    assert not d.can_cast_dack(replace(base,c=3)), "baseline underpaid generic"

    # Incubator on Human makes Dack 2WW, never reducing the WW requirement.
    inc=d.Perm("Urza's Incubator",aux="INCUBATOR:Human")
    s=d.State(1,(),lib,(inc,),w=2,c=2)
    assert d.can_cast_dack(s), "Human Incubator should reduce 4WW to 2WW"
    assert not d.can_cast_dack(replace(s,c=1)), "Incubator reduced more than two generic"
    assert not d.can_cast_dack(replace(s,w=1,c=20)), "Incubator must not reduce white pips"

    # The as-enters choice is materialized when the real Incubator is cast.
    cast_state=d.State(1,("Urza's Incubator",),lib,(),c=3)
    outs=d.cast_actions(cast_state)
    assert any(p.name=="Urza's Incubator" and p.aux=="INCUBATOR:Human"
               for q in outs for p in q.battlefield), "cast Incubator did not choose Human"

    # Cost reducers stack on generic mana only.
    pearl=d.Perm("Pearl Medallion")
    s=d.State(1,(),lib,(inc,pearl),w=2,c=1)
    assert d.can_cast_dack(s), "Incubator + Pearl should make Dack 1WW"

    # Mycosynth Gardens becoming a copy does not re-enter and therefore does not
    # make a new creature-type choice; an unchosen Incubator copy provides no reduction.
    garden=d.Perm("The Mycosynth Gardens",aux="COPY:Urza's Incubator")
    s=d.State(1,(),lib,(garden,),w=2,c=2)
    assert not d.can_cast_dack(s), "Gardens copy incorrectly inherited Human choice"

    # Incubator has no mana ability and must not be a Moonsilver Key mana target.
    assert "Urza's Incubator" not in d.MOONSILVER_MANA_ARTIFACTS

    print("INCUBATOR_AUDIT_PASS")

if __name__=="__main__":
    main()
