#!/usr/bin/env python3
"""Parity tests for compact numeric Phase-5 episode-cycle identity."""

from dataclasses import replace

import urza_solver as solver
from non_oracle_episode import episode_cycle_key, legacy_episode_cycle_key
from non_oracle_runtime import NonOracleRuntimeState, make_runtime_state
from non_oracle_runtime_value_key import RuntimeDecisionWindow, WINDOW_PRIORITY
from phase5_compact_runtime_encoding import CARD_NAMES, CARD_TO_ID


def same_relation(a,b,expected):
    legacy=(legacy_episode_cycle_key(a)==legacy_episode_cycle_key(b))
    compact=(episode_cycle_key(a)==episode_cycle_key(b))
    assert legacy is expected,(legacy,expected)
    assert compact is expected,(compact,expected)


def main():
    assert len(CARD_NAMES)==len(CARD_TO_ID)
    assert len(CARD_NAMES)<255
    assert len(set(CARD_TO_ID.values()))==len(CARD_TO_ID)
    assert all(1<=value<255 for value in CARD_TO_ID.values())
    assert CARD_TO_ID["Urza, Lord High Artificer"]>0
    assert CARD_TO_ID["Island"]>0

    state=solver.State(
        turn=1,
        library=("Island","Sol Ring","Mystical Tutor"),
        hand=("Mana Drain",),
        battlefield=(solver.Perm("Sol Ring",instance_tag=7,knack_source="trace-a"),),
        graveyard=("Mishra's Bauble",),
        blue=1,
        rng_root_seed=77,
        trace=("provenance-a",),
        interaction_seen=("Mana Drain",),
        urza_cast_turn=1,
    )
    base=make_runtime_state(state)

    # These are explicitly excluded execution/reporting provenance in the legacy
    # Markov key and permanent projection.
    equivalent_state=replace(
        base.true_state,
        trace=("completely-different-trace",),
        interaction_seen=(),
        urza_cast_turn=99,
        battlefield=tuple(
            replace(perm,instance_tag=999,knack_source="other-provenance")
            for perm in base.true_state.battlefield
        ),
    )
    equivalent=replace(base,true_state=equivalent_state)
    same_relation(base,equivalent,True)

    # Exact hidden sampled-world order remains part of episode cycle identity.
    reordered=replace(
        base,
        true_state=replace(
            base.true_state,
            library=tuple(reversed(base.true_state.library)),
        ),
    )
    same_relation(base,reordered,False)

    # Root game randomness tape remains exact Markov state.
    rerooted=replace(
        base,
        true_state=replace(base.true_state,rng_root_seed=78),
    )
    same_relation(base,rerooted,False)

    # Runtime semantic sidecars remain part of the cycle.
    priority=replace(base,window=RuntimeDecisionWindow(WINDOW_PRIORITY))
    same_relation(base,priority,False)

    informed=replace(
        base,
        information=replace(
            base.information,
            known_top=("Island",),
            known_library_counts=(("Island",1),("Mystical Tutor",1),("Sol Ring",1)),
        ),
    )
    same_relation(base,informed,False)

    permissioned=replace(
        base,
        permissions=base.permissions.grant("Sol Ring",1),
    )
    same_relation(base,permissioned,False)

    key=episode_cycle_key(base)
    assert isinstance(key,bytes) and len(key)==32
    print("compact numeric cycle identity matches legacy equivalence relation: PASS")
    print("known deck card IDs fit in one byte: PASS")
    print("production cycle key is fixed 32 bytes: PASS")


if __name__=="__main__":
    main()
