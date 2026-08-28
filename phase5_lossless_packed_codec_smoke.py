#!/usr/bin/env python3
"""Round-trip and size smoke for the lossless packed state codec."""

from dataclasses import asdict, replace
from pathlib import Path

import urza_solver as solver
from decision_observation import ActionIntent, PendingDecisionSpec
from non_oracle_runtime import (
    NonOracleRuntimeState,
    RuntimePendingDecision,
    RuntimeStack,
    RuntimeStackObject,
    STACK_TRIGGER,
)
from non_oracle_runtime_value_key import RuntimeDecisionWindow, WINDOW_POST_OBSERVATION
from solver_architecture import InformationState, canonical_true_state_key
from urza_permission_adapter import UrzaPermissionState
from phase5_lossless_packed_codec import (
    CARD_TO_ID,
    PACKED_SCHEMA_DIGEST,
    lossless_roundtrip,
    pack_lossless,
    unpack_lossless,
)


def assert_exact_dataclass(a,b):
    assert type(a) is type(b),(type(a),type(b))
    assert asdict(a)==asdict(b),(asdict(a),asdict(b))
    assert pack_lossless(a)==pack_lossless(b)


def main():
    deck=solver.load_deck(Path("decklist.txt"))
    assert len(deck)==99
    assert len(CARD_TO_ID)<255

    # Deliberately exercise fields excluded from strategic/Markov keys. The
    # LOSSLESS codec must preserve them anyway.
    state=solver.State(
        turn=4,
        library=tuple(deck),
        hand=("Force of Will","Island","Reshape"),
        battlefield=(
            solver.Perm(
                "Grinding Station",
                tapped=True,
                sick=False,
                counters=2,
                mode="station-special",
                knack_granted=True,
                knack_source="Banishing Knack",
                producer_urza_ready=True,
                instance_tag=123456,
            ),
            solver.Perm(
                "Urza, Lord High Artificer",
                sick=False,
                instance_tag=654321,
            ),
        ),
        graveyard=("Mishra's Bauble","Lotus Petal"),
        exile=("Sol Ring",),
        blue=3,
        colorless=7,
        land_played=True,
        drain_bank=2,
        bauble_draws=1,
        remora_age=3,
        remora_upkeep_pending=True,
        saga3_pending=True,
        ring_counters=4,
        ftt_level=3,
        uthros_counters=5,
        urza=True,
        construct=True,
        top_access=True,
        chip_attached=True,
        chip_target="Urza, Lord High Artificer",
        spell_cast_this_turn=True,
        pa_target="Grim Monolith",
        vfc_pumps=2,
        urza_cast_turn=2,
        commander_in_command_zone=False,
        commander_casts_from_zone=1,
        interaction_seen=("Force of Will","Mana Drain"),
        won=False,
        win_family="",
        rng_root_seed=2**173+123456789,
        trace=("exact trace entry","another trace"),
    )
    state_roundtrip=lossless_roundtrip(state)
    assert_exact_dataclass(state,state_roundtrip)

    info=InformationState(
        known_top=("Mystical Tutor","Island"),
        known_bottom=("Mox Opal",),
        known_library_counts=(("Island",6),("Sol Ring",1)),
        shuffle_epoch=17,
    )
    permissions=UrzaPermissionState().grant("Sol Ring",4)
    stack_obj=RuntimeStackObject(
        object_id="runtime-stack:42",
        object_type=STACK_TRIGGER,
        kind="station_untap",
        source="Grinding Station",
        card="Sol Ring",
        payload=(("source_tag",123456),("note","exact execution payload")),
        public_payload=(("source_state",("Grinding Station",True,False,2,"station-special",True,True)),),
        strategic_payload=(("source_state",("Grinding Station",True,False,2,"station-special",True,True)),),
    )
    stack=RuntimeStack(objects=(stack_obj,),next_sequence=43)
    spec=PendingDecisionSpec(
        decision_id="pending:exact:99",
        kind="runtime_stack_order",
        source="Grinding Station",
        decision_stage="post_observation",
        contingent_on="trigger:42",
    )
    pending=RuntimePendingDecision(
        spec=spec,
        kind="runtime_stack_order",
        payload=(
            ("object_ids",("runtime-stack:42",)),
            ("source_tag",123456),
            ("semantic","keep-this-too"),
        ),
    )
    runtime=NonOracleRuntimeState(
        true_state=state,
        information=info,
        permissions=permissions,
        stack=stack,
        window=RuntimeDecisionWindow(WINDOW_POST_OBSERVATION),
        pending=pending,
    )
    runtime_roundtrip=lossless_roundtrip(runtime)
    assert_exact_dataclass(runtime,runtime_roundtrip)

    policy_view=runtime.policy_view(caverns_live=True)
    assert_exact_dataclass(policy_view,lossless_roundtrip(policy_view))

    action=ActionIntent(
        action_id="reshape.x2.station",
        kind="cast_reshape",
        parameters=(("card","Reshape"),("target","Grinding Station"),("x_value",2)),
        equivalence_key=("cast_reshape","Grinding Station",2),
        label="Reshape X=2 -> Grinding Station",
        decision_stage="commit",
        source="Reshape",
        contingent_on="",
    )
    assert_exact_dataclass(action,lossless_roundtrip(action))

    packed_state=pack_lossless(state)
    packed_runtime=pack_lossless(runtime)
    legacy_state_text=repr(canonical_true_state_key(state)).encode("utf-8")

    # The exact binary representation should be materially smaller than the
    # existing nested tagged/repr form while retaining MORE provenance fields.
    assert len(packed_state)<len(legacy_state_text),(len(packed_state),len(legacy_state_text))

    # Byte corruption / schema mismatch must not silently decode.
    corrupted=bytearray(packed_state)
    corrupted[37]^=1
    try:
        unpack_lossless(bytes(corrupted))
    except ValueError:
        pass
    else:
        raise AssertionError("corrupted schema fingerprint decoded silently")

    print(f"lossless State round-trip: PASS ({len(packed_state)} packed bytes)")
    print(f"lossless Runtime round-trip: PASS ({len(packed_runtime)} packed bytes)")
    print(f"legacy canonical true-state repr: {len(legacy_state_text)} bytes")
    print(f"exact packed/legacy size ratio: {len(packed_state)/len(legacy_state_text):.3f}")
    print("stack/pending/permissions/provenance/RNG/library order preserved: PASS")
    print(f"schema fingerprint: {PACKED_SCHEMA_DIGEST.hex()[:16]}...")


if __name__=="__main__":
    main()
