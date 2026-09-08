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
    "Battered Golem\tAUDIT_REQUIRED\tCurrent engine exposes some rules surface, but this card has not yet passed the clause-level goldfish completeness audit; all relevant Oracle clauses need executable evidence or explicit exemptions.",
    "Battered Golem\tCOMPLETE\tGoldfish-complete: normal artifact-creature casting, the restriction that it does not untap during the normal untap step, and its optional artifact-entry untap trigger are executable. Dedicated post-R7 fixtures prove artifact versus nonartifact entry behavior, both accept/decline outcomes, self-entry handling, and the public two-choice contingent bridge.",
)

replace_exact(
    GATE,
    """        assert_eq!(audit.count(Disposition::AuditRequired), 42);
        assert_eq!(audit.count(Disposition::ImplementationRequired), 40);
        assert_eq!(audit.count(Disposition::EnvironmentSplitRequired), 3);
        assert_eq!(audit.count(Disposition::Complete), 10);
        assert_eq!(audit.resolved(), 10);
        assert_eq!(audit.unresolved(), 85);""",
    """        assert_eq!(audit.count(Disposition::AuditRequired), 41);
        assert_eq!(audit.count(Disposition::ImplementationRequired), 40);
        assert_eq!(audit.count(Disposition::EnvironmentSplitRequired), 3);
        assert_eq!(audit.count(Disposition::Complete), 11);
        assert_eq!(audit.resolved(), 11);
        assert_eq!(audit.unresolved(), 84);""",
)
