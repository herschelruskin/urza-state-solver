#!/usr/bin/env python3
"""Parity for direct numeric strategic runtime Q identity."""

from dataclasses import replace

import urza_solver as solver
from non_oracle_runtime import make_runtime_state
from non_oracle_runtime_value_key import canonical_runtime_object_value_key
from phase5_compact_runtime_encoding import compact_runtime_value_digest


def relation(a,b,expected):
    legacy=(canonical_runtime_object_value_key(a)==canonical_runtime_object_value_key(b))
    compact=(compact_runtime_value_digest(a)==compact_runtime_value_digest(b))
    assert legacy is expected,(legacy,expected)
    assert compact is expected,(compact,expected)


def main():
    base=make_runtime_state(solver.State(
        turn=2,
        library=("Island","Sol Ring","Mystical Tutor"),
        hand=("Mana Drain",),
        battlefield=(solver.Perm("Sol Ring",instance_tag=4,knack_source="p"),),
        graveyard=("Mishra's Bauble",),
        blue=1,
        rng_root_seed=1234567890123456789012345,
        trace=("a",),
        interaction_seen=("Mana Drain",),
        urza_cast_turn=1,
    ))

    # Strategic value identity deliberately ignores exact hidden order and RNG.
    hidden_reordered=replace(
        base,
        true_state=replace(
            base.true_state,
            library=tuple(reversed(base.true_state.library)),
            rng_root_seed=999999999999999999999999,
        ),
    )
    relation(base,hidden_reordered,True)

    # Reporting/provenance and permanent execution tags are also ignored.
    provenance=replace(
        base,
        true_state=replace(
            base.true_state,
            trace=("b",),
            interaction_seen=(),
            urza_cast_turn=99,
            battlefield=tuple(
                replace(p,instance_tag=999,knack_source="q")
                for p in base.true_state.battlefield
            ),
        ),
    )
    relation(base,provenance,True)

    # construct/top_access are derived convenience flags and are absent from the
    # strategic-value state projection.
    derived=replace(
        base,
        true_state=replace(
            base.true_state,
            construct=not base.true_state.construct,
            top_access=not base.true_state.top_access,
        ),
    )
    relation(base,derived,True)

    visible=replace(
        base,
        true_state=replace(base.true_state,hand=("Force of Will",)),
    )
    relation(base,visible,False)

    public_mana=replace(
        base,
        true_state=replace(base.true_state,blue=2),
    )
    relation(base,public_mana,False)

    informed=replace(
        base,
        information=replace(
            base.information,
            known_top=("Island",),
            known_library_counts=(("Island",1),("Mystical Tutor",1),("Sol Ring",1)),
        ),
    )
    relation(base,informed,False)

    key=compact_runtime_value_digest(base)
    assert isinstance(key,bytes) and len(key)==32
    print("compact strategic runtime digest matches legacy Q equivalence: PASS")
    print("hidden order/RNG remain excluded from policy value identity: PASS")
    print("compact Q runtime identity is fixed 32 bytes: PASS")


if __name__=="__main__":
    main()
