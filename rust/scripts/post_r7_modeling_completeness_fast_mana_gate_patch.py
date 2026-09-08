from pathlib import Path


path = Path("rust/crates/urza-mulligan/src/bin/post-r7-modeling-completeness-gate.rs")
text = path.read_text()
old = """        assert_eq!(audit.count(Disposition::AuditRequired), 46);
        assert_eq!(audit.count(Disposition::ImplementationRequired), 42);
        assert_eq!(audit.count(Disposition::EnvironmentSplitRequired), 3);
        assert_eq!(audit.count(Disposition::Complete), 4);
        assert_eq!(audit.resolved(), 4);
        assert_eq!(audit.unresolved(), 91);"""
new = """        assert_eq!(audit.count(Disposition::AuditRequired), 46);
        assert_eq!(audit.count(Disposition::ImplementationRequired), 40);
        assert_eq!(audit.count(Disposition::EnvironmentSplitRequired), 3);
        assert_eq!(audit.count(Disposition::Complete), 6);
        assert_eq!(audit.resolved(), 6);
        assert_eq!(audit.unresolved(), 89);"""
if text.count(old) != 1:
    raise SystemExit(f"expected exactly one modeling-gate count block, found {text.count(old)}")
path.write_text(text.replace(old, new, 1))
