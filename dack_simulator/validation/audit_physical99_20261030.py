#!/usr/bin/env python3
"""Audit the Oct 30 physical 99 without importing the mutable legacy solver."""
from __future__ import annotations
import ast
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "dack_simulator/configs/physical99_20261030.json"
SOURCE = ROOT / "dack_boonweaver_exact99_20261016.py"
MANDATORY = {
    "Boonweaver Giant", "Preston, the Vanisher", "Roaming Throne",
    "Hardlight Containment", "Lunarch Mantle", "Gleaming Splendor",
}
BANNED = {"Mana Crypt", "Jeweled Lotus"}
LITERAL_LANDS = {
    "Ancient Den", "Ancient Tomb", "Blast Zone", "Cavern of Souls",
    "City of Traitors", "Command Beacon", "Crystal Vein",
    "Eiganjo, Seat of the Empire", "Emergence Zone", "Gemstone Caverns",
    "Great Hall of the Citadel", "Homeward Path", "Mishra's Workshop",
    "Petrified Hamlet", "Plains", "Remote Farm", "Ruins of Trokair",
    "Talon Gates of Madara", "The Mycosynth Gardens", "Treasure Vault",
    "Untaidake, the Cloud Keeper", "Urza's Cave", "Urza's Saga",
}
MDFCS = {"Emeria's Call", "Razorgrass Ambush"}
RECONSTRUCTION = (
    ("Fomori Vault", "Treasure Vault"),
    ("World Map", "Giant's Boulder"),
    ("Smothering Tithe", "Bucknard's Everfull Purse"),
    ("United Battlefront", "Coalition Relic"),
)

def original_99():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    raw = next(
        ast.literal_eval(stmt.value)
        for stmt in tree.body
        if isinstance(stmt, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "DECK_TEXT"
            for t in stmt.targets
        )
    )
    cards = []
    for line in raw.splitlines():
        if line.strip():
            qty, name = line.split(" ", 1)
            cards.extend([name] * int(qty))
    return tuple(cards)

def content_hash(cards):
    return hashlib.sha256(
        ("\\n".join(sorted(cards)) + "\\n").encode("utf-8")
    ).hexdigest()

def audit():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["schema"] == "dack_physical_99_slots_v1"
    assert data["commander"] == "Dack Fayden, Helping Hand"
    slots = data["slots"]
    assert [s["slot_id"] for s in slots] == [
        "slot_%03d" % i for i in range(1, 100)
    ]
    cards = [s["card"] for s in slots]
    assert cards == sorted(cards) and len(cards) == 99
    counts = Counter(cards)
    assert counts["Plains"] == data["plains_count"] == 10
    assert set(counts) >= MANDATORY
    assert not BANNED.intersection(counts)
    assert {c: n for c, n in counts.items() if n > 1} == {"Plains": 10}
    assert sum(x in LITERAL_LANDS for x in cards) == data["literal_land_count"] == 32
    assert sum(x in MDFCS for x in cards) == data["mdfc_land_count"] == 2
    assert sum(x in (LITERAL_LANDS | MDFCS) for x in cards) == data["land_access_count"] == 34
    assert counts["Treasure Vault"] == 1 and not counts["Fomori Vault"]
    assert counts["Mind Stone"] == counts["The Mind Stone"] == 1
    old = list(original_99())
    assert len(old) == 99
    for removed, added in RECONSTRUCTION:
        assert old.count(removed) == 1 and added not in old, (removed, added)
        old[old.index(removed)] = added
    assert Counter(old) == counts, "physical deck differs from source + recorded changes"
    assert data["reconstruction_delta_from_oct16"] == [list(x) for x in RECONSTRUCTION]
    assert counts["Tooth of Ramos"] == 1 and not counts["Voltaic Key"]
    one_key = cards.copy()
    one_key[one_key.index("Tooth of Ramos")] = "Voltaic Key"
    assert len(one_key) == 99 and len(MANDATORY.intersection(one_key)) == len(MANDATORY)
    assert sum(x in (LITERAL_LANDS | MDFCS) for x in one_key) == 34
    result = {
        "status": "PASS",
        "physical_99": len(cards),
        "unique_card_names": len(counts),
        "literal_lands": 32,
        "mdfc_lands": 2,
        "land_access": 34,
        "plains": 10,
        "physical_unordered_content_sha256_v1": content_hash(cards),
        "one_key_unordered_content_sha256_v1": content_hash(one_key),
        "treasure_vault_engine_rules_certified": False,
    }
    return result

if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
