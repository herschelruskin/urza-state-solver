#!/usr/bin/env python3
"""Paired *full-replay* reference runner for the frozen physical-99 Dack deck.

Same game IDs and per-London-stage slot permutations across arms, independent
mulligan/beam decisions for every arm. Does NOT reuse baseline game results
when the changed card was unseen; that shortcut is not generally sound.

Important limitation (version 1): the legacy nested keep-EV sampler derives
randomness from card-name multisets; internal future sampling is therefore
not yet coupled by canonical slot across deck variants. Post-tutor shuffles
and deterministic Bucknard beam search inherit that historical limitation.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path

import dack_counterfactual_rules_v1_20261030 as rules
from dack_simulator.validation.audit_physical99_20261030 import audit as physical_audit

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "dack_simulator/configs/physical99_20261030.json"
SPEC_PATH = ROOT / "dack_simulator/configs/onekey_artifact_cut_screen_v1.json"
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf8"))
SPEC = json.loads(SPEC_PATH.read_text(encoding="utf8"))
sim, d, batch = rules.sim, rules.d, rules.sim.batch
SEED_STRIDE = 1000003
SLOTS = tuple(row["slot_id"] for row in MANIFEST["slots"])
PHYSICAL = {row["slot_id"]: row["card"] for row in MANIFEST["slots"]}
MAX_TURN = 3
RULES_VERSION = rules.RULES_VERSION
# Opt-in independent keep-policy identity for policy variants. Historical
# reference stays assertive unless an experimental entrypoint sets this.
MULLIGAN_POLICY_NAME = SPEC["gameplay_policy"]
MULLIGAN_SAMPLER_NAME = SPEC["internal_mulligan_sampling"]

def with_substitutions(slot_names, changes):
    result = dict(slot_names)
    for old, new in changes:
        matches = [slot for slot, name in result.items() if name == old]
        if len(matches) != 1:
            raise ValueError(f"expected exactly one {old!r}, found {len(matches)}")
        if new != "Plains" and new in result.values():
            raise ValueError(f"singleton already in deck: {new!r}")
        result[matches[0]] = new
    return result

BASE_SLOTS = with_substitutions(PHYSICAL, SPEC["baseline_swaps"])
SLOT_VARIANTS = {
    name: with_substitutions(BASE_SLOTS, changes)
    for name, changes in SPEC["variants"].items()
}
# Preserve *physical slot identity* internally; original simulator receives a
# 99-name sequence in stable slot order, independently of Monte Carlo shuffle.
VARIANTS = {
    name: tuple(slot_names[slot] for slot in SLOTS)
    for name, slot_names in SLOT_VARIANTS.items()
}
sim.configure_variants(VARIANTS)

def source_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def audit():
    physical = physical_audit()
    assert physical["status"] == "PASS"
    smoke = rules.rule_smoke()
    assert smoke["status"] == "PASS"
    assert SPEC["rng_scheme"] == "canonical_slots_fisher_yates_each_london_stage_v1"
    assert SPEC["gameplay_policy"] == sim.ACTIVE_POLICY == "assertive"
    assert SPEC["beam"] == sim.GAMEPLAY_BEAM == 160
    assert SPEC["max_turn"] == MAX_TURN
    assert SPEC["control"] in VARIANTS and len(VARIANTS) == 9
    assert len(SLOTS) == len(set(SLOTS)) == 99
    assert len(PHYSICAL) == 99 and len(SLOT_VARIANTS) == len(VARIANTS)
    assert PHYSICAL != BASE_SLOTS
    assert Counter(BASE_SLOTS.values()) == Counter(VARIANTS[SPEC["control"]])
    assert all(slot_names.keys() == PHYSICAL.keys()
               for slot_names in SLOT_VARIANTS.values())
    for name, cards in VARIANTS.items():
        assert len(cards) == 99 and set(sim.root.COMBO).issubset(cards), name
        assert all(x in d.CARD_ID for x in cards), (name, "unrecognized card")
        assert len([x for x in cards if x != "Plains"]) == len(
            set(x for x in cards if x != "Plains")), name
        assert "Treasure Vault" in cards and "Fomori Vault" not in cards
        assert cards.count("Voltaic Key") == 1 and "Tooth of Ramos" not in cards
        assert "Manifold Key" not in cards
        assert not {"Mana Crypt", "Jeweled Lotus"}.intersection(cards)
        assert {"Gleaming Splendor", "Hardlight Containment",
                "Lunarch Mantle"}.issubset(cards)
        land_count = sum(x in d.LANDS or x in
                         ("Emeria's Call", "Razorgrass Ambush") for x in cards)
        assert land_count == (34 if name == SPEC["control"] else 35), (name,land_count)
    return {
        "status": "PASS", "rules_version": RULES_VERSION, "variants": list(VARIANTS),
        "manifest_sha256": source_sha(MANIFEST_PATH),
        "spec_sha256": source_sha(SPEC_PATH),
        "paired_outer_slots": True,
        "legacy_nested_keep_ev_is_not_slot_paired": True,
        "cross_variant_reuse": False,
    }

def stage_slots(seed):
    """Canonical common random conditions, independent of deck card names."""
    rng = random.Random(seed)
    seat = rng.randrange(4)
    stages = []
    for _ in sim.STAGES:
        shuffled = list(SLOTS)
        rng.shuffle(shuffled)
        stages.append(tuple(shuffled))
    return seat, tuple(stages)

def selected_slots(seven_slots, seven_names, picked_names):
    """Preserve distinct identical Plains physical occurrences in the trace."""
    unused = list(zip(seven_slots, seven_names))
    out = []
    for wanted in picked_names:
        idx = next(i for i, pair in enumerate(unused) if pair[1] == wanted)
        out.append(unused.pop(idx)[0])
    return out

def choose_keep(deck_slots, seat, order_by_stage):
    history = []
    for stage, (keep_n, order) in enumerate(zip(sim.STAGES, order_by_stage)):
        seven = [deck_slots[slot] for slot in order[:7]]
        rest = [deck_slots[slot] for slot in order[7:]]
        raw, ev, struct, hand, bottom, unknown, ignored, refined = (
            batch.evaluate_keep(seven, keep_n, rest, seat)
        )
        if len(hand) != keep_n or len(unknown) != 92:
            raise AssertionError(("London invariant", stage, keep_n, len(unknown)))
        standard = (0.0 if keep_n == 1 else
                    batch.FROZEN_CONTINUATION[keep_n - 1])
        native_keep = keep_n == 1 or float(raw) >= standard
        t1 = float(ev["t1"])
        bump = sim.ASSERTIVE_BUMPS.get(keep_n, 0.0)
        cutoff = standard + (0.0 if native_keep and t1 > 0 else bump)
        keep = keep_n == 1 or float(raw) >= cutoff
        history.append({
            "stage": stage, "keep_n": keep_n, "kept": bool(keep),
            "raw": round(float(raw), 7), "sampled_t1": round(t1, 7),
            "threshold": round(cutoff, 7), "refined": bool(refined),
            "seven_slots": list(order[:7]),
            "seven": seven, "hand": list(hand), "bottom": list(bottom),
            "hand_slots": selected_slots(order[:7], seven, hand),
            "bottom_slots": selected_slots(order[:7], seven, bottom),
        })
        if keep:
            return d.State(1, tuple(hand), tuple(unknown) + tuple(bottom)), history
    raise AssertionError("London terminal keep not reached")

def t2_success(turn):
    return 0 < int(turn) <= 2

def game(name, game_id, seat=None, slots=None):
    if name not in VARIANTS:
        raise KeyError(name)
    seed = int(SPEC["seed_base"]) + int(game_id) * SEED_STRIDE
    if seat is None or slots is None:
        seat, slots = stage_slots(seed)
    # Ensure previous variant/previous game does not contaminate caches.
    sim.reset_caches()
    sim.root.install(name)
    sim.m.set_trial_seed(seed)
    state, history = choose_keep(SLOT_VARIANTS[name], seat, slots)
    # Mirror the validated active policy: discard mulligan evaluator's
    # speculative game outcomes before running this actual kept-hand trial.
    d._WIN_CACHE.clear()
    frontier_events = []
    original_frontier = d.search_turn_frontier_many
    def traced_frontier(turn_states, beam=160, depth=24):
        wins, survivors = original_frontier(turn_states, beam=beam, depth=depth)
        frontier_events.append({
            "turn": turn_states[0].turn if turn_states else None,
            "states_entering": len(turn_states),
            "terminal_candidates": len(wins),
            "survivors": len(survivors),
            "beam": beam, "depth": depth,
        })
        return wins, survivors
    # Scoped instrumentation; never leak monkeypatches between arms/games.
    d.search_turn_frontier_many = traced_frontier
    try:
        win = d._win_turn_from_unknown_order(
            state.hand, state.library, seat, beam=int(SPEC["beam"]), max_turn=MAX_TURN)
    finally:
        d.search_turn_frontier_many = original_frontier
    return {
        "game_id": int(game_id), "seed": seed, "seat": seat,
        "variant": name, "keep_n": history[-1]["keep_n"],
        "win_turn": int(win or 0), "hand": list(state.hand),
        "first3": list(state.library[:3]), "history": history,
        "frontier_events": frontier_events,
    }

def first_divergence(control, other):
    stages_a, stages_b = control["history"], other["history"]
    for i in range(max(len(stages_a), len(stages_b))):
        a = stages_a[i] if i < len(stages_a) else None
        b = stages_b[i] if i < len(stages_b) else None
        if a is None or b is None:
            return {"kind": "mulligan_stage_count", "stage": i}
        if a["seven"] != b["seven"]:
            return {"kind": "opening_seven_card_identity", "stage": i,
                    "different_slots": [
                        s for s, ac, bc in zip(a["seven_slots"], a["seven"], b["seven"])
                        if ac != bc]}
        if (a["kept"], a["bottom_slots"], a["hand_slots"]) != (
                b["kept"], b["bottom_slots"], b["hand_slots"]):
            return {"kind": "mulligan_decision_or_bottom", "stage": i}
    if control["first3"] != other["first3"]:
        return {"kind": "future_draw_order_or_contents", "stage": None}
    if control.get("frontier_events") != other.get("frontier_events"):
        return {"kind": "turn_frontier_or_action_search", "stage": None}
    if control["win_turn"] != other["win_turn"]:
        return {"kind": "gameplay_search_or_deeper_library", "stage": None}
    return {"kind": "no_observed_divergence", "stage": None}

def paired_game(game_id):
    seed = int(SPEC["seed_base"]) + int(game_id) * SEED_STRIDE
    seat, slots = stage_slots(seed)
    outputs = {}
    for name in VARIANTS:
        outputs[name] = game(name, game_id, seat, slots)
    base = outputs[SPEC["control"]]
    interesting = any(t2_success(x["win_turn"]) != t2_success(base["win_turn"])
                      for x in outputs.values())
    summary = {
        "game_id": game_id, "seat": seat,
        "arms": {name: {"win_turn": x["win_turn"], "keep_n": x["keep_n"]}
                 for name, x in outputs.items()},
    }
    if interesting:
        summary["discordant_trace"] = {
            name: {"first_divergence": first_divergence(base, x),
                   "hand": x["hand"], "first3": x["first3"],
                   "history": x["history"], "frontier_events": x["frontier_events"]}
            for name, x in outputs.items()
        }
    return summary

def metrics(rows):
    n = len(rows)
    if not n:
        raise ValueError("no paired games")
    control = SPEC["control"]
    result = {"n": n, "arms": {}, "paired_vs_control": {}}
    for name in VARIANTS:
        wins = [int(row["arms"][name]["win_turn"]) for row in rows]
        result["arms"][name] = {
            "T1_pct": round(100 * sum(w == 1 for w in wins) / n, 4),
            "T2_pct": round(100 * sum(w in (1, 2) for w in wins) / n, 4),
            "T3_pct": round(100 * sum(w in (1, 2, 3) for w in wins) / n, 4),
            "mean_keep": round(sum(row["arms"][name]["keep_n"] for row in rows)/n,4)
        }
        if name == control:
            continue
        result["paired_vs_control"][name] = {}
        for threshold in (1, 2, 3):
            outcomes = []
            for row in rows:
                left = row["arms"][control]["win_turn"]
                right = row["arms"][name]["win_turn"]
                new = int(right > 0 and right <= threshold)
                old = int(left > 0 and left <= threshold)
                outcomes.append(new - old)
            gains = outcomes.count(1)
            losses = outcomes.count(-1)
            delta = (gains - losses) / n
            se = math.sqrt(max(0.0, (
                (gains + losses) / n - delta * delta) / (n - 1))) if n > 1 else 0.0
            result["paired_vs_control"][name][f"T{threshold}"] = {
                "gains": gains, "losses": losses, "ties": n-gains-losses,
                "delta_pp": round(100 * delta, 4),
                "paired_normal_95_ci_pp": [
                    round(100*(delta - 1.96*se), 4),
                    round(100*(delta + 1.96*se), 4)
                ],
            }
    return result

def source_engine_manifest():
    # Hash actual imported Python sources, not just a version string. Includes
    # every repo-local imported Python file, inherited patch or experiment code.
    loaded = {}
    for module in list(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if not path or not path.endswith(".py"):
            continue
        path = Path(path).resolve()
        try:
            relative = path.relative_to(ROOT.resolve())
        except ValueError:
            continue
        if path.is_file():
            loaded[str(relative)] = source_sha(path)
    return {"rules_version": RULES_VERSION,
            "loaded_sources_sha256": dict(sorted(loaded.items())),
            "beam": int(SPEC["beam"]), "max_turn": MAX_TURN}

def persist(rows, db_path):
    # Shards write to separate SQLite files; merge later. Do not use the same
    # database from independent Actions workers.
    sys.path.insert(0, str(ROOT / "dack_simulator/src"))
    from dacksim.store import DackStore
    from dacksim.codec import Outcome
    from dacksim.canonical import deck_hash
    import zlib
    engine = source_engine_manifest()
    policy = {
        "policy": MULLIGAN_POLICY_NAME, "seed_base": SPEC["seed_base"],
        "stride": SEED_STRIDE, "rng_scheme": SPEC["rng_scheme"],
        "nested_sampler": MULLIGAN_SAMPLER_NAME,
        "source_spec_sha256": source_sha(SPEC_PATH),
    }
    ids = [row["game_id"] for row in rows]
    if ids != list(range(ids[0], ids[0] + len(ids))):
        raise ValueError("store requires contiguous unique game IDs")
    with DackStore(db_path) as store:
        hengine = store.register_engine(engine)
        hpolicy = store.register_policy(policy)
        hashes = {
            name: store.register_deck(cards, commander=MANIFEST["commander"])
            for name, cards in VARIANTS.items()
        }
        exp = store.register_experiment(hashes[SPEC["control"]], {
            "source_spec_sha256": source_sha(SPEC_PATH), "rng": policy,
            "rules_version": RULES_VERSION,
        })
        for name, changes in SPEC["variants"].items():
            store.add_experiment_variant(
                experiment_hash=exp, variant_deck_hash=hashes[name],
                label=name, delta={"swaps": changes})
        for name in VARIANTS:
            outcomes = [Outcome(
                seat=row["seat"],
                keep_n=row["arms"][name]["keep_n"],
                win_turn=row["arms"][name]["win_turn"])
                for row in rows]
            key = store.put_result_block(
                deck_hash_value=hashes[name], engine_hash=hengine,
                policy_hash=hpolicy, seed_start=ids[0], outcomes=outcomes)
            for offset, row in enumerate(rows):
                if "discordant_trace" in row:
                    payload = json.dumps(row["discordant_trace"][name],
                                         separators=(",", ":")).encode("utf8")
                    store.put_trace(
                        run_key_value=key, game_offset=offset,
                        trace_kind="discordant_T2", codec="zlib_json_v1",
                        payload=zlib.compress(payload, 6))
        return {"stats": store.stats(), "engine_hash": hengine,
                "policy_hash": hpolicy, "experiment_hash": exp}

def run(start, count, output, store_path=None):
    if start < 0 or count < 1:
        raise ValueError("start >= 0 and count > 0 required")
    stamp = time.monotonic()
    audit_result = audit()
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = target.with_name(target.name + ".checkpoint.jsonl")
    signature = {
        "spec_sha256": source_sha(SPEC_PATH),
        "manifest_sha256": source_sha(MANIFEST_PATH),
        "rules_version": RULES_VERSION,
        "seed_start": start, "games": count,
    }
    rows = []
    if checkpoint.exists():
        with checkpoint.open("rt", encoding="utf8") as fp:
            for line in fp:
                if not line.strip():
                    continue
                entry = json.loads(line)
                if entry["signature"] != signature:
                    raise RuntimeError("checkpoint spec/manifest mismatch")
                expected_gid = start + len(rows)
                if entry["row"]["game_id"] != expected_gid:
                    raise RuntimeError("checkpoint noncontiguous or duplicate game ID")
                rows.append(entry["row"])
        if len(rows) > count:
            raise RuntimeError("checkpoint longer than selected shard")
    for gid in range(start + len(rows), start + count):
        row = paired_game(gid)
        with checkpoint.open("at", encoding="utf8") as fp:
            fp.write(json.dumps({"signature": signature, "row": row},
                                separators=(",", ":")) + "\n")
            fp.flush()
            os.fsync(fp.fileno())
        rows.append(row)
        print("PAIRED_GAME", gid,
              {name: row["arms"][name]["win_turn"] for name in VARIANTS},
              flush=True)
    report = {
        "schema": "dack_paired_counterfactual_full_replay_v1",
        "status": "PASS", "seed_start": start,
        "games": count, "elapsed_seconds": round(time.monotonic()-stamp, 3),
        "audit": audit_result, "spec": SPEC,
        "summary": metrics(rows), "rows": rows
    }
    if store_path:
        report["sqlite"] = persist(rows, store_path)
    with gzip.open(target, "wt", encoding="utf8", compresslevel=6) as fp:
        json.dump(report, fp, separators=(",", ":"))
    print("PAIRED_RUN_PASS", target, count, report["elapsed_seconds"], flush=True)
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--games", type=int, default=1)
    parser.add_argument("--out", default="shards/counterfactual_v1_shard0.json.gz")
    parser.add_argument("--store", default=None)
    parser.add_argument("--single-variant", choices=list(VARIANTS), default=None,
                        help="One fresh E2E game, without launching nine arms")
    opt = parser.parse_args()
    if opt.audit:
        print(json.dumps(audit(), indent=2))
    elif opt.single_variant is not None:
        audit()
        print(json.dumps(game(opt.single_variant, opt.start), indent=2))
    else:
        run(opt.start, opt.games, opt.out, opt.store)
