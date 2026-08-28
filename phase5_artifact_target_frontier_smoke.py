#!/usr/bin/env python3
"""Smoke tests for the objective-aware Whir target frontier."""

from types import SimpleNamespace

from decision_observation import ActionIntent, DECISION_POST_OBSERVATION
from phase5_artifact_target_frontier import whir_target_frontier


def obs(*, urza=False, hand=(), battlefield=()):
    base = SimpleNamespace(
        hand=tuple(hand),
        graveyard=(),
        battlefield=tuple(battlefield),
        urza=bool(urza),
        chip_attached=False,
        top_access=False,
    )
    return SimpleNamespace(base=base)


def perm(name, tapped=False, mode=""):
    return SimpleNamespace(name=name, tapped=bool(tapped), mode=mode)


def target(card, serial):
    return ActionIntent(
        action_id=f"whir.target.{serial}",
        kind="x_artifact_search_target",
        parameters=(("target", card), ("x", 3)),
        equivalence_key=("Whir of Invention", "target", card, 3),
        label=("Find no card" if not card else f"Find {card}"),
        decision_stage=DECISION_POST_OBSERVATION,
        source="Whir of Invention",
    )


def names(result):
    return {dict(a.parameters).get("target", "") for a in result.actions}


def main():
    actions = (
        target("", 0),
        target("Pithing Needle", 1),
        target("Grafdigger's Cage", 2),
        target("Defense Grid", 3),
        target("Mana Vault", 4),
        target("Sensei's Divining Top", 5),
        target("Battered Golem", 6),
    )
    result = whir_target_frontier(
        obs(hand=("Retraction Helix",)),
        actions,
        objective="win_by_horizon",
    )
    kept = names(result)
    assert "" in kept
    assert "Defense Grid" in kept
    assert "Mana Vault" in kept
    assert "Sensei's Divining Top" in kept
    assert "Battered Golem" in kept
    assert "Pithing Needle" not in kept
    assert "Grafdigger's Cage" not in kept

    # Singleton card identity is strategically relevant even for otherwise
    # generic artifacts because removing a specific target changes the remaining
    # library before later shuffle/draw sampling. Do not signature-collapse them.
    identity_actions = (
        target("", 0),
        target("Generic Artifact A", 1),
        target("Generic Artifact B", 2),
        target("Pithing Needle", 3),
    )
    identity_result = whir_target_frontier(
        obs(),
        identity_actions,
        objective="win_by_horizon",
    )
    identity_kept = names(identity_result)
    assert "Generic Artifact A" in identity_kept
    assert "Generic Artifact B" in identity_kept
    assert "Pithing Needle" not in identity_kept
    assert identity_result.collapsed_signature_count == 0

    needle = actions[1]
    retained = whir_target_frontier(
        obs(),
        actions,
        objective="win_by_horizon",
        must_retain=(needle,),
    )
    assert "Pithing Needle" in names(retained)

    unchanged = whir_target_frontier(
        obs(),
        actions,
        objective="protected_win",
    )
    assert tuple(a.strategic_key() for a in unchanged.actions) == tuple(
        a.strategic_key() for a in actions
    )

    key_actions = (
        target("", 0),
        target("Voltaic Key", 1),
        target("Mana Vault", 2),
    )
    no_payoff = whir_target_frontier(
        obs(),
        key_actions,
        objective="win_by_horizon",
    )
    # With no tapped payoff, Key should not create a unique untap-value dimension.
    assert "Mana Vault" in names(no_payoff)

    with_payoff = whir_target_frontier(
        obs(battlefield=(perm("The One Ring", tapped=True),)),
        key_actions,
        objective="win_by_horizon",
    )
    assert "Voltaic Key" in names(with_payoff)

    print("PHASE5 ARTIFACT TARGET FRONTIER SMOKE: ALL PASS")
    print(
        "FRONTIER_EXAMPLE "
        f"legal={result.legal_target_count} retained={result.retained_target_count} "
        f"dominated={result.dominated_target_count} collapsed={result.collapsed_signature_count} "
        f"targets={result.retained_targets!r}"
    )


if __name__ == "__main__":
    main()
