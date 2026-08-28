#!/usr/bin/env python3
"""Parity for compact observation/action identities used by Phase-5 MC."""

from dataclasses import replace

import urza_solver as solver
from decision_observation import ActionIntent
from non_oracle_rules_adapter_v2 import rules_decision_request
from non_oracle_runtime import make_runtime_state
from phase5_compact_runtime_encoding import (
    compact_action_strategic_digest,
    compact_observation_digest,
)


def main():
    base=make_runtime_state(solver.State(
        turn=1,
        library=("Island","Sol Ring","Mystical Tutor"),
        hand=("Mystical Tutor",),
        battlefield=(),
        blue=1,
        rng_root_seed=17,
    ))
    reordered=replace(
        base,
        true_state=replace(
            base.true_state,
            library=tuple(reversed(base.true_state.library)),
        ),
    )
    a=rules_decision_request(base,horizon=2,policy_id="parity")
    b=rules_decision_request(reordered,horizon=2,policy_id="parity")

    assert a.observation.key()==b.observation.key()
    assert compact_observation_digest(a.observation)==compact_observation_digest(b.observation)

    changed=replace(
        base,
        true_state=replace(base.true_state,hand=("Mana Drain",)),
    )
    c=rules_decision_request(changed,horizon=2,policy_id="parity")
    assert a.observation.key()!=c.observation.key()
    assert compact_observation_digest(a.observation)!=compact_observation_digest(c.observation)

    legacy_to_compact={}
    compact_to_legacy={}
    for action in a.actions:
        legacy=action.strategic_key()
        compact=compact_action_strategic_digest(action)
        prior=legacy_to_compact.setdefault(legacy,compact)
        assert prior==compact
        prior_legacy=compact_to_legacy.setdefault(compact,legacy)
        assert prior_legacy==legacy
        assert isinstance(compact,bytes) and len(compact)==32

    x=ActionIntent(
        action_id="exec-a",
        kind="test",
        equivalence_key=("same-strategy","Island"),
        label="A",
    )
    y=ActionIntent(
        action_id="exec-b",
        kind="test",
        equivalence_key=("same-strategy","Island"),
        label="B",
    )
    assert x.strategic_key()==y.strategic_key()
    assert compact_action_strategic_digest(x)==compact_action_strategic_digest(y)

    print("compact observation identity preserves PolicyView equivalence: PASS")
    print("compact strategic action identity preserves ActionIntent equivalence: PASS")


if __name__=="__main__":
    main()
