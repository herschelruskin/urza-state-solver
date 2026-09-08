from pathlib import Path


def replace_exact(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match in {path}, found {count}: {old[:100]!r}")
    file.write_text(text.replace(old, new, 1))


REGISTRY = "rust/data/goldfish_model_gate.v1.tsv"
GATE = "rust/crates/urza-mulligan/src/bin/post-r7-modeling-completeness-gate.rs"

replace_exact(
    REGISTRY,
    "Power Artifact\tAUDIT_REQUIRED\tCurrent engine exposes some rules surface, but this card has not yet passed the clause-level goldfish completeness audit; all relevant Oracle clauses need executable evidence or explicit exemptions.",
    "Power Artifact\tCOMPLETE\tGoldfish-complete: enchant-artifact targeting and attachment are executable; the enchanted artifact's activation costs are reduced by two, and the engine enforces the Oracle floor that a nonzero activation cost cannot be reduced below one mana. Dedicated post-R7 fixtures prove Basalt 3->1, Grim 4->2, stacked-reducer floor behavior, and public bridge visibility.",
)

replace_exact(
    GATE,
    """        assert_eq!(audit.count(Disposition::AuditRequired), 44);
        assert_eq!(audit.count(Disposition::ImplementationRequired), 40);
        assert_eq!(audit.count(Disposition::EnvironmentSplitRequired), 3);
        assert_eq!(audit.count(Disposition::Complete), 8);
        assert_eq!(audit.resolved(), 8);
        assert_eq!(audit.unresolved(), 87);""",
    """        assert_eq!(audit.count(Disposition::AuditRequired), 43);
        assert_eq!(audit.count(Disposition::ImplementationRequired), 40);
        assert_eq!(audit.count(Disposition::EnvironmentSplitRequired), 3);
        assert_eq!(audit.count(Disposition::Complete), 9);
        assert_eq!(audit.resolved(), 9);
        assert_eq!(audit.unresolved(), 86);""",
)
