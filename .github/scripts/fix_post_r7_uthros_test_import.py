#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().parents[2] / "rust/crates/urza-rules/src/lib.rs"
text = path.read_text()
old = "mod post_r7_uthros_tests {\n    use std::collections::BTreeMap;\n\n    use super::*;"
new = "mod post_r7_uthros_tests {\n    use std::collections::BTreeMap;\n\n    use super::*;\n    use urza_core::CardZone;"
if text.count(old) != 1:
    raise SystemExit(f"expected one Uthros test import anchor, found {text.count(old)}")
path.write_text(text.replace(old, new, 1))
