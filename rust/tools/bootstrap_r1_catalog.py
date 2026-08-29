#!/usr/bin/env python3
"""One-shot R1 catalog snapshot builder.

This is migration/build tooling only. Scryfall bulk Oracle data is the external
metadata source; this script does not encode gameplay rules or Python simulator
behavior.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import pathlib
import urllib.request


USER_AGENT = "urza-state-solver-r1-catalog/0.1 (https://github.com/herschelruskin/urza-state-solver)"
ACCEPT = "application/json;q=0.9,*/*;q=0.8"


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": ACCEPT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def download(url: str, output: pathlib.Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": ACCEPT})
    with urllib.request.urlopen(request, timeout=180) as response, output.open("wb") as target:
        while chunk := response.read(1024 * 1024):
            target.write(chunk)


def text_sha256(card: dict) -> str:
    if card.get("oracle_text") is not None:
        text = card.get("oracle_text", "")
    else:
        text = "\n//\n".join(face.get("oracle_text", "") for face in card.get("card_faces", []))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def face_record(face: dict) -> dict:
    return {
        "name": face["name"],
        "mana_cost": face.get("mana_cost", ""),
        "type_line": face.get("type_line", ""),
    }


def integer_mana_value(card: dict) -> int:
    value = card.get("cmc", 0)
    integer = int(value)
    if integer != value:
        raise RuntimeError(f"fractional mana value is unsupported in the active R1 catalog: {card['name']}={value}")
    return integer


def type_flags(type_lines: list[str]) -> dict:
    joined = " // ".join(type_lines)
    words = set(joined.replace("—", " ").replace("//", " ").split())
    return {
        "is_artifact": "Artifact" in words,
        "is_creature": "Creature" in words,
        "is_enchantment": "Enchantment" in words,
        "is_instant": "Instant" in words,
        "is_land": "Land" in words,
        "is_planeswalker": "Planeswalker" in words,
        "is_sorcery": "Sorcery" in words,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--r0-catalog", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--bulk-meta-url", default="https://api.scryfall.com/bulk-data")
    parser.add_argument("--cache-dir", type=pathlib.Path, default=pathlib.Path("/tmp/urza-r1-catalog"))
    args = parser.parse_args()

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    meta = fetch_json(args.bulk_meta_url)
    bulk = next(item for item in meta["data"] if item["type"] == "default_cards")
    download_uri = bulk.get("jsonl_download_uri") or bulk.get("download_uri")
    if not download_uri:
        raise RuntimeError("Scryfall default_cards bulk object has no download URI")

    bulk_path = args.cache_dir / ("oracle-cards.jsonl.gz" if download_uri.endswith(".gz") else "oracle-cards.json")
    download(download_uri, bulk_path)
    bulk_sha256 = hashlib.sha256(bulk_path.read_bytes()).hexdigest()

    if bulk_path.suffix == ".gz":
        source = gzip.open(bulk_path, "rt", encoding="utf-8")
        records = (json.loads(line) for line in source if line.strip())
    else:
        source = bulk_path.open("rt", encoding="utf-8")
        first = source.read(1)
        source.seek(0)
        if first == "[":
            records = iter(json.load(source))
        else:
            records = (json.loads(line) for line in source if line.strip())

    by_name: dict[str, list[tuple[dict, int | None]]] = {}
    with source:
        for card in records:
            if (
                not card.get("oracle_id")
                or card.get("layout") == "art_series"
                or card.get("lang", "en") != "en"
                or "paper" not in card.get("games", [])
            ):
                continue
            by_name.setdefault(card["name"], []).append((card, None))
            for index, face in enumerate(card.get("card_faces", [])):
                by_name.setdefault(face["name"], []).append((card, index))

    r0 = json.loads(args.r0_catalog.read_text(encoding="utf-8"))
    output_cards = []
    missing = []
    ambiguous = []

    for entry in r0["cards"]:
        matches = by_name.get(entry["name"], [])
        unique: dict[str, tuple[dict, int | None]] = {}
        for card, face_index in matches:
            prior = unique.get(card["oracle_id"])
            if prior is None or card.get("released_at", "") > prior[0].get("released_at", ""):
                unique[card["oracle_id"]] = (card, face_index)
        matches = list(unique.values())
        if not matches:
            missing.append(entry["name"])
            continue
        if len(matches) != 1:
            ambiguous.append({"name": entry["name"], "oracle_ids": sorted(unique)})
            continue

        card, face_index = matches[0]
        faces = [face_record(face) for face in card.get("card_faces", [])]
        type_lines = [card.get("type_line", "")] if not faces else [face["type_line"] for face in faces]
        costs = [card.get("mana_cost", "")] if not faces else [face["mana_cost"] for face in faces]
        output_cards.append(
            {
                "id": entry["id"],
                "deck_name": entry["name"],
                "oracle_name": card["name"],
                "deck_count": entry["deck_count"],
                "commander": entry["commander"],
                "oracle_id": card["oracle_id"],
                "source_scryfall_id": card["id"],
                "layout": card.get("layout", "normal"),
                "mana_cost": card.get("mana_cost", ""),
                "mana_value": integer_mana_value(card),
                "type_line": card.get("type_line", ""),
                "oracle_text_sha256": text_sha256(card),
                "faces": faces,
                "deck_face_index": face_index,
                "feature_flags": {
                    **type_flags(type_lines),
                    "is_multiface": bool(faces),
                    "is_modal_dfc": card.get("layout") == "modal_dfc",
                    "has_x_cost": any("{X}" in cost for cost in costs),
                },
            }
        )

    if missing or ambiguous:
        raise RuntimeError(json.dumps({"missing": missing, "ambiguous": ambiguous}, indent=2))

    output_cards.sort(key=lambda card: card["id"])
    snapshot = {
        "schema_version": 1,
        "catalog_version": "urza-active-r1-oracle-2026-08-29",
        "catalog_as_of_utc": bulk["updated_at"],
        "source": {
            "provider": "Scryfall bulk Default Cards; English paper printings grouped by Oracle ID",
            "bulk_api": args.bulk_meta_url,
            "bulk_type": "default_cards",
            "bulk_id": bulk["id"],
            "bulk_updated_at": bulk["updated_at"],
            "bulk_download_uri": download_uri,
            "bulk_file_sha256": bulk_sha256,
            "content_type": bulk.get("content_type"),
            "content_encoding": bulk.get("content_encoding"),
        },
        "r0_catalog_digest_blake3": "2ef2f7dd52b72af46d24a0183096803ef9fb9d65524b9e77f7d87da4e2809f21",
        "cards": output_cards,
    }
    args.output.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
