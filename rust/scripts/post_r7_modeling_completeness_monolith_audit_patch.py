from pathlib import Path


def replace_exact(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match in {path}, found {count}: {old[:80]!r}")
    file.write_text(text.replace(old, new, 1))


REGISTRY = "rust/data/goldfish_model_gate.v1.tsv"
GATE = "rust/crates/urza-mulligan/src/bin/post-r7-modeling-completeness-gate.rs"

old_audit = (
    "Current engine exposes some rules surface, but this card has not yet passed the "
    "clause-level goldfish completeness audit; all relevant Oracle clauses need "
    "executable evidence or explicit exemptions."
)

replace_exact(
    REGISTRY,
    f"Basalt Monolith\tAUDIT_REQUIRED\t{old_audit}",
    "Basalt Monolith\tCOMPLETE\tGoldfish-complete: printed {3} cast, untapped entry, {T} for three colorless, skipped normal untap, and {3} self-untap are executable; dedicated post-R7 Monolith fixtures also prove the intrinsic mana and native untap actions are solver-visible.",
)
replace_exact(
    REGISTRY,
    f"Grim Monolith\tAUDIT_REQUIRED\t{old_audit}",
    "Grim Monolith\tCOMPLETE\tGoldfish-complete: printed {2} cast, untapped entry, {T} for three colorless, skipped normal untap, and {4} self-untap are executable; dedicated post-R7 Monolith fixtures also prove the intrinsic mana and native untap actions are solver-visible.",
)

replace_exact(
    GATE,
    """        assert_eq!(audit.count(Disposition::AuditRequired), 46);
        assert_eq!(audit.count(Disposition::ImplementationRequired), 40);
        assert_eq!(audit.count(Disposition::EnvironmentSplitRequired), 3);
        assert_eq!(audit.count(Disposition::Complete), 6);
        assert_eq!(audit.resolved(), 6);
        assert_eq!(audit.unresolved(), 89);""",
    """        assert_eq!(audit.count(Disposition::AuditRequired), 44);
        assert_eq!(audit.count(Disposition::ImplementationRequired), 40);
        assert_eq!(audit.count(Disposition::EnvironmentSplitRequired), 3);
        assert_eq!(audit.count(Disposition::Complete), 8);
        assert_eq!(audit.resolved(), 8);
        assert_eq!(audit.unresolved(), 87);""",
)
