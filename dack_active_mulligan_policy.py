#!/usr/bin/env python3
"""Active Dack London mulligan policy (October 26, 2026).

Assertive is the DEFAULT for NEW speed and card-swap experiments. The old
Standard policy is preserved byte-for-byte in historical benchmark modules.
This module exposes both policies without monkeypatching the archived solver.

Exact reference trial: held-out n=10,000 on the frozen Boonweaver current 99.
Reference: benchmark_results/dack_assertive_heldout_n10000_report.json

Goldfish Dack cast conditional on combo eligible, not multiplayer victory.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import random
from typing import Mapping, Sequence

# Importing the frozen reference establishes the frozen Oct-25 current deck
# and already audited post-Prism rules. Historical modules remain unmodified.
import dack_t1_assertive_heldout_n10000_20261026 as reference

root, d, m, batch = reference.root, reference.d, reference.m, reference.batch

ACTIVE_POLICY = "assertive"
SUPPORTED_POLICIES = ("assertive", "standard")
GAMEPLAY_BEAM = 160
DEFAULT_SEED_BASE = 99142610261318
STAGES = (7, 7, 6, 5, 4, 3, 2, 1)
ASSERTIVE_BUMPS = {7: 0.200, 6: 0.120, 5: 0.055, 4: 0.015}
FROZEN_DECK = tuple(reference.DECK)
FROZEN_DECK_HASH = reference.HASH
CURRENT_VARIANTS = {"current": FROZEN_DECK}


def deck_hash(deck: Sequence[str]) -> str:
    return hashlib.sha256("\n".join(deck).encode()).hexdigest()


def configure_variants(variants: Mapping[str, Sequence[str]]) -> None:
    """Set 99-card variants for paired future card comparisons.

    Every supplied deck must have the same 99-card count, combo eligibility,
    banned-card restriction, and recognized card names. Names are preserved
    in iteration order; do not sort decks differently across paired arms.
    """
    global CURRENT_VARIANTS
    proposed = {name: tuple(deck) for name, deck in variants.items()}
    assert proposed, "at least one variant required"
    for name, deck in proposed.items():
        assert name and len(deck) == 99, name
        assert root.COMBO.issubset(deck), ("missing required Boonweaver combo pieces", name)
        assert not {"Mana Crypt", "Jeweled Lotus"}.intersection(deck), name
        assert len(set(x for x in deck if x != "Plains")) == len([x for x in deck if x != "Plains"]), name
        assert all(card in d.CARD_ID for card in deck), ("unknown card", name)
    CURRENT_VARIANTS = proposed
    root.VARIANTS = proposed
    batch.build_deck = lambda name: CURRENT_VARIANTS[name]


def audit():
    reference.audit()
    assert ACTIVE_POLICY == "assertive"
    assert ASSERTIVE_BUMPS == reference.POLICIES["assertive"]
    assert STAGES == reference.STAGES
    assert GAMEPLAY_BEAM == reference.BEAM
    assert FROZEN_DECK_HASH == reference.base.EXPECTED_HASH
    assert all(abs(batch.FROZEN_CONTINUATION[k-1] -
                   reference.batch.FROZEN_CONTINUATION[k-1]) < 1e-12
                   for k in range(2,8))
    assert batch.CONFIG["lambda"] == 0.5
    configure_variants({"current": FROZEN_DECK})
    assert tuple(d.DECK) == FROZEN_DECK or root.install("current") == FROZEN_DECK
    print("ACTIVE_ASSERTIVE_AUDIT_PASS", json.dumps({
        "default_policy": ACTIVE_POLICY, "standard_retained": True,
        "deck_hash": FROZEN_DECK_HASH, "gameplay_beam": GAMEPLAY_BEAM,
        "assertive_bumps": ASSERTIVE_BUMPS}), flush=True)


def choose_hand_with_free(rng: random.Random, seat: int, policy: str = ACTIVE_POLICY):
    """Same bottom/keep evaluator and one-free-London rules as held-out trial.

    Only the threshold differs. If sampled t1 is positive AND Standard would
    keep this hand, preserve Standard's threshold for the Assertive option.
    This is an estimated signal, not a guarantee of winning on turn 1.
    """
    if policy not in SUPPORTED_POLICIES:
        raise ValueError(f"Unknown policy {policy!r}: {SUPPORTED_POLICIES}")
    history = []
    for stage, keep_n in enumerate(STAGES):
        cards = list(d.DECK)
        rng.shuffle(cards)
        seven, rest = cards[:7], cards[7:]
        raw, ev, struct, hand, bottom, unknown, _, refined = batch.evaluate_keep(
            seven, keep_n, rest, seat)
        assert len(hand) == keep_n and len(unknown) == 92
        standard_threshold = 0.0 if keep_n == 1 else batch.FROZEN_CONTINUATION[keep_n-1]
        native_keep = keep_n == 1 or float(raw) >= standard_threshold
        sampled_t1 = float(ev["t1"])
        bump = ASSERTIVE_BUMPS.get(keep_n, 0.0) if policy == "assertive" else 0.0
        threshold = standard_threshold + (
            0.0 if (policy == "assertive" and native_keep and sampled_t1 > 0)
            else bump)
        keep = keep_n == 1 or float(raw) >= threshold
        history.append({
            "stage": stage, "keep_n": keep_n, "raw": round(float(raw), 6),
            "sampled_t1": round(sampled_t1, 6),
            "standard_threshold": standard_threshold,
            "effective_threshold": round(threshold, 6),
            "native_keep": native_keep,
            "kept": keep, "refined": bool(refined)})
        if keep:
            return d.State(1, tuple(hand), tuple(unknown)+tuple(bottom)), keep_n, history
    raise AssertionError("unreachable: terminal London keep")


def simulate(variant: str = "current", game_id: int = 0,
             policy: str = ACTIVE_POLICY, seed_base: int = DEFAULT_SEED_BASE,
             beam: int = GAMEPLAY_BEAM) -> dict:
    """Active default = Assertive. Pass policy='standard' for historical control.

    Paired card comparisons should use the SAME game IDs, seed base and policy
    for both variants; reset caches between games to avoid stale state.
    """
    assert variant in CURRENT_VARIANTS, variant
    root.install(variant)
    seed = int(seed_base) + int(game_id) * 1000003
    m.set_trial_seed(seed)
    rng = random.Random(seed)
    seat = rng.randrange(4)
    state, keep_n, history = choose_hand_with_free(rng, seat, policy=policy)
    d._WIN_CACHE.clear()
    win = d._win_turn_from_unknown_order(
        state.hand, state.library, seat, beam=beam, max_turn=3)
    return {
        "game_id": int(game_id), "seed": seed, "seat": seat,
        "variant": variant, "deck_hash": deck_hash(CURRENT_VARIANTS[variant]),
        "policy": policy, "keep_n": keep_n,
        "hand": list(state.hand), "first3": list(state.library[:3]),
        "win_turn": int(win or 0), "audit": history}


def reset_caches():
    reference.reset_caches()


def parity_check(game_ids=(0, 1, 8, 23)):
    """Replay independently frozen N10000 data with both policy selections."""
    import gzip
    from pathlib import Path
    path = Path("benchmark_results/dack_assertive_heldout_n10000_report.raw.json.gz")
    assert path.is_file(), f"Missing frozen independent parity records: {path}"
    with gzip.open(path, "rt", encoding="utf8") as f:
        previous = json.load(f)
    assert previous["deck_hash"] == FROZEN_DECK_HASH
    assert previous["seed_base"] == DEFAULT_SEED_BASE
    assert previous["schema"] == reference.SCHEMA
    rows = previous["rows"]
    assert len(rows) == 10000
    configure_variants({"current": FROZEN_DECK})
    for gid in game_ids:
        for policy, archived in (("standard", "native"), ("assertive", "assertive")):
            reset_caches()
            actual = simulate("current", gid, policy=policy)
            expected = rows[gid]["results"][archived]
            for key in ("seed", "seat", "keep_n", "hand", "first3", "win_turn"):
                assert actual[key] == expected[key], (gid, policy, key, actual[key], expected[key])
            print("ACTIVE_PARITY_PASS", gid, policy, actual["win_turn"], flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--parity", action="store_true")
    ap.add_argument("--game-id", type=int, default=0)
    ap.add_argument("--policy", choices=SUPPORTED_POLICIES, default=ACTIVE_POLICY)
    ap.add_argument("--seed-base", type=int, default=DEFAULT_SEED_BASE)
    opts = ap.parse_args()
    if opts.audit:
        audit()
    elif opts.parity:
        audit()
        parity_check()
    else:
        configure_variants({"current": FROZEN_DECK})
        reset_caches()
        print(json.dumps(simulate("current", opts.game_id, policy=opts.policy,
                                  seed_base=opts.seed_base), indent=2))
