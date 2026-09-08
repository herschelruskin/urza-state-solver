from pathlib import Path

path = Path("rust/crates/urza-policy/src/lib.rs")
text = path.read_text()
old = "            return match candidate.class {\n"
new = "            match candidate.class {\n"
if text.count(old) != 1:
    raise SystemExit(f"expected one v2 return-match marker, found {text.count(old)}")
text = text.replace(old, new, 1)
old_tail = "                PolicyActionClass::ContingentDecision => 6,\n            };\n        } else {\n"
new_tail = "                PolicyActionClass::ContingentDecision => 6,\n            }\n        } else {\n"
if text.count(old_tail) != 1:
    raise SystemExit(f"expected one v2 match-tail marker, found {text.count(old_tail)}")
path.write_text(text.replace(old_tail, new_tail, 1))
