from pathlib import Path

path = Path("rust/crates/urza-policy-bridge/src/lib.rs")
text = path.read_text()
old = "        assert_eq!(ORDINARY_ACTION_FAMILY_COUNT, 26);\n"
new = "        assert_eq!(ORDINARY_ACTION_FAMILY_COUNT, 27);\n"
if new not in text:
    if old not in text:
        raise SystemExit("bridge ordinary-family audit anchor not found")
    text = text.replace(old, new, 1)
path.write_text(text)
