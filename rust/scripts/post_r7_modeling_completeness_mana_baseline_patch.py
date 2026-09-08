from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "rust/data/goldfish_model_gate.v1.tsv"
GATE = ROOT / "rust/crates/urza-mulligan/src/bin/post-r7-modeling-completeness-gate.rs"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match in {path}: {old!r}; got {count}")
    path.write_text(text.replace(old, new, 1))


def promote(name: str, rationale: str) -> None:
    text = REGISTRY.read_text()
    prefix = f"{name}\tAUDIT_REQUIRED\t"
    matches = [line for line in text.splitlines() if line.startswith(prefix)]
    if len(matches) != 1:
        raise SystemExit(f"expected one AUDIT_REQUIRED row for {name}; got {len(matches)}")
    old = matches[0]
    new = f"{name}\tCOMPLETE\t{rationale}"
    replace_once(REGISTRY, old, new)


promote(
    "Ancient Tomb",
    "Goldfish-complete: ordinary untapped land play and intrinsic tap for two colorless with two self-damage are executed by the current rules engine; dedicated post-R7 mana-baseline fixture proves the exact resource and life transition.",
)
promote(
    "Island",
    "Goldfish-complete: ordinary untapped basic-land play and intrinsic blue mana are executed by the current rules engine; dedicated post-R7 mana-baseline fixture proves play, tap, and mana production.",
)
promote(
    "Seat of the Synod",
    "Goldfish-complete: ordinary artifact-land play, intrinsic blue mana, and artifact identity are represented by the current rules engine; dedicated post-R7 mana-baseline fixture proves land play, blue production, and artifact characteristic used by Urza/artifact effects.",
)
promote(
    "Sol Ring",
    "Goldfish-complete: zero-choice artifact spell resolution at printed {1} and intrinsic tap for two colorless are executed by the current rules engine; dedicated post-R7 mana-baseline fixture proves cast payment, battlefield entry, and mana production.",
)

replace_once(
    GATE,
    "assert_eq!(audit.count(Disposition::AuditRequired), 50);",
    "assert_eq!(audit.count(Disposition::AuditRequired), 46);",
)
replace_once(
    GATE,
    "assert_eq!(audit.count(Disposition::EnvironmentSplitRequired), 3);\n        assert_eq!(audit.resolved(), 0);\n        assert_eq!(audit.unresolved(), 95);",
    "assert_eq!(audit.count(Disposition::EnvironmentSplitRequired), 3);\n        assert_eq!(audit.count(Disposition::Complete), 4);\n        assert_eq!(audit.resolved(), 4);\n        assert_eq!(audit.unresolved(), 91);",
)
