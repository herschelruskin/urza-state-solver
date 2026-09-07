from pathlib import Path

path = Path("rust/crates/urza-rules/src/lib.rs")
text = path.read_text()
old = 'pub const RULES_VERSION: &str = "post_r7_card_advantage_v1_ring";\n'
new = (
    'pub const RULES_VERSION: &str = "r4_acceptance_v6";\n'
    'pub const POST_R7_RULES_VERSION: &str = "post_r7_card_advantage_v1_ring";\n'
)
if new not in text:
    if old not in text:
        raise SystemExit("post-R7 Ring rules-version anchor not found")
    text = text.replace(old, new, 1)
path.write_text(text)
