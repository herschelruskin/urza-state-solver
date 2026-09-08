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
    "Forensic Gadgeteer\tAUDIT_REQUIRED\tCurrent engine exposes some rules surface, but this card has not yet passed the clause-level goldfish completeness audit; all relevant Oracle clauses need executable evidence or explicit exemptions.",
    "Forensic Gadgeteer\tCOMPLETE\tGoldfish-complete: normal creature casting, artifact-spell investigate triggers, real Clue token creation and Clue draw execution, and the static {1} artifact-activation reduction are executable. Dedicated post-R7 fixtures prove the trigger does not fire for nonartifact spells, Basalt 3->2 reduction, the one-mana reduction floor on Top, and solver-visible reduced-cost and Clue actions.",
)

replace_exact(
    GATE,
    """        assert_eq!(audit.count(Disposition::AuditRequired), 43);
        assert_eq!(audit.count(Disposition::ImplementationRequired), 40);
        assert_eq!(audit.count(Disposition::EnvironmentSplitRequired), 3);
        assert_eq!(audit.count(Disposition::Complete), 9);
        assert_eq!(audit.resolved(), 9);
        assert_eq!(audit.unresolved(), 86);""",
    """        assert_eq!(audit.count(Disposition::AuditRequired), 42);
        assert_eq!(audit.count(Disposition::ImplementationRequired), 40);
        assert_eq!(audit.count(Disposition::EnvironmentSplitRequired), 3);
        assert_eq!(audit.count(Disposition::Complete), 10);
        assert_eq!(audit.resolved(), 10);
        assert_eq!(audit.unresolved(), 85);""",
)
