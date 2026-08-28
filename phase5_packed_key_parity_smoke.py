#!/usr/bin/env python3
"""Equivalence, reversibility, and size smoke for collision-free Phase-5 packed keys."""

from dataclasses import replace

import urza_solver as solver
from non_oracle_runtime import make_runtime_state
from non_oracle_runtime_value_key import (
    RuntimeDecisionWindow,
    WINDOW_PRIORITY,
    canonical_runtime_object_value_key,
)
from non_oracle_rules_adapter_v2 import rules_decision_request
from non_oracle_episode import legacy_episode_cycle_key
from phase5_packed_keys import (
    packed_action_strategic_key,
    packed_episode_cycle_key,
    packed_observation_key,
    packed_phase5_decision_cache_key,
    packed_runtime_value_key,
    unpack_packed_projection,
)


def same_relation(old_a,old_b,new_a,new_b,expected):
    assert (old_a==old_b) is expected
    assert (new_a==new_b) is expected


def main():
    base=make_runtime_state(solver.State(
        turn=2,
        library=("Island","Sol Ring","Mystical Tutor","Mana Drain"),
        hand=("Mystical Tutor","Island"),
        battlefield=(solver.Perm("Sol Ring",instance_tag=11,knack_source="trace"),),
        graveyard=("Mishra's Bauble",),
        blue=1,
        rng_root_seed=2**151+77,
        trace=("history-a",),
        interaction_seen=("Mana Drain",),
        urza_cast_turn=1,
    ))

    provenance=replace(
        base,
        true_state=replace(
            base.true_state,
            trace=("history-b",),
            interaction_seen=(),
            urza_cast_turn=99,
            battlefield=tuple(
                replace(p,instance_tag=999,knack_source="other")
                for p in base.true_state.battlefield
            ),
        ),
    )
    same_relation(
        legacy_episode_cycle_key(base),legacy_episode_cycle_key(provenance),
        packed_episode_cycle_key(base),packed_episode_cycle_key(provenance),
        True,
    )
    same_relation(
        canonical_runtime_object_value_key(base),canonical_runtime_object_value_key(provenance),
        packed_runtime_value_key(base),packed_runtime_value_key(provenance),
        True,
    )

    hidden=replace(
        base,
        true_state=replace(
            base.true_state,
            library=tuple(reversed(base.true_state.library)),
            rng_root_seed=2**173+123,
        ),
    )
    # Exact cycle identity sees hidden sampled-world changes.
    same_relation(
        legacy_episode_cycle_key(base),legacy_episode_cycle_key(hidden),
        packed_episode_cycle_key(base),packed_episode_cycle_key(hidden),
        False,
    )
    # Strategic Q identity must NOT see hidden order/RNG.
    same_relation(
        canonical_runtime_object_value_key(base),canonical_runtime_object_value_key(hidden),
        packed_runtime_value_key(base),packed_runtime_value_key(hidden),
        True,
    )

    visible=replace(
        base,
        true_state=replace(base.true_state,hand=("Force of Will","Island")),
    )
    same_relation(
        canonical_runtime_object_value_key(base),canonical_runtime_object_value_key(visible),
        packed_runtime_value_key(base),packed_runtime_value_key(visible),
        False,
    )

    priority=replace(base,window=RuntimeDecisionWindow(WINDOW_PRIORITY))
    same_relation(
        canonical_runtime_object_value_key(base),canonical_runtime_object_value_key(priority),
        packed_runtime_value_key(base),packed_runtime_value_key(priority),
        False,
    )

    request=rules_decision_request(base,horizon=6,policy_id="packed-parity")
    hidden_request=rules_decision_request(hidden,horizon=6,policy_id="packed-parity")
    assert request.observation.key()==hidden_request.observation.key()
    assert packed_observation_key(request.observation)==packed_observation_key(hidden_request.observation)

    legacy_action_map={a.strategic_key():a for a in request.actions}
    packed_action_map={packed_action_strategic_key(a):a for a in request.actions}
    assert len(legacy_action_map)==len(packed_action_map)

    candidate_keys=tuple(sorted(packed_action_map))
    cache_a=packed_phase5_decision_cache_key(
        runtime=base,
        candidate_action_keys=candidate_keys,
        rollout_count=2,
        mc_root_seed=20260826,
        horizon=6,
        objective="win_by_horizon_then_earlier-v1",
        policy_id="packed-parity",
        continuation_id="test-continuation",
        sample_namespace="screen",
        max_episode_steps=512,
        strict_terminal_reasons=True,
    )
    cache_hidden=packed_phase5_decision_cache_key(
        runtime=hidden,
        candidate_action_keys=candidate_keys,
        rollout_count=2,
        mc_root_seed=20260826,
        horizon=6,
        objective="win_by_horizon_then_earlier-v1",
        policy_id="packed-parity",
        continuation_id="test-continuation",
        sample_namespace="screen",
        max_episode_steps=512,
        strict_terminal_reasons=True,
    )
    assert cache_a==cache_hidden

    cycle_projection=unpack_packed_projection(packed_episode_cycle_key(base))
    q_projection=unpack_packed_projection(packed_runtime_value_key(base))
    obs_projection=unpack_packed_projection(packed_observation_key(request.observation))
    action_projection=unpack_packed_projection(candidate_keys[0])
    cache_projection=unpack_packed_projection(cache_a)
    assert cycle_projection[1]=="episode-cycle"
    assert q_projection[1]=="runtime-value"
    assert obs_projection[1]=="observation"
    assert action_projection[1]=="strategic-action"
    assert cache_projection[1]=="phase5-decision"

    old_cycle_size=len(repr(legacy_episode_cycle_key(base)).encode("utf-8"))
    new_cycle_size=len(packed_episode_cycle_key(base))
    old_q_size=len(repr(canonical_runtime_object_value_key(base)).encode("utf-8"))
    new_q_size=len(packed_runtime_value_key(base))

    assert new_cycle_size<old_cycle_size
    assert new_q_size<old_q_size

    print("packed Markov cycle equivalence matches legacy: PASS")
    print("packed strategic Q equivalence matches legacy: PASS")
    print("packed observation/action equivalence matches legacy: PASS")
    print("packed hidden-information boundary matches legacy: PASS")
    print("all packed hot keys decode to their canonical projection: PASS")
    print(f"cycle key: {new_cycle_size} packed bytes vs {old_cycle_size} legacy repr bytes")
    print(f"Q key: {new_q_size} packed bytes vs {old_q_size} legacy repr bytes")


if __name__=="__main__":
    main()
