from pathlib import Path

parallel = Path("rust/crates/urza-mc/src/parallel.rs")
text = parallel.read_text()
old_import = (
    "    ADAPTIVE_ROOT_EVAL_VERSION, AdaptiveRootActionComparison, AdaptiveRootConfig, "
    "AdaptiveRootError,\n"
)
new_import = "    AdaptiveRootActionComparison, AdaptiveRootConfig, AdaptiveRootError,\n"
if old_import not in text:
    raise SystemExit("parallel unused-import repair anchor missing")
parallel.write_text(text.replace(old_import, new_import, 1))

lib = Path("rust/crates/urza-mc/src/lib.rs")
text = lib.read_text()
old = '''    hasher.update(&(library.known_top.len() as u64).to_le_bytes());
    for card in &library.known_top {
        hasher.update(&card.0.to_le_bytes());
    }
    hasher.update(&(library.remaining_counts.len() as u64).to_le_bytes());
    for (card, count) in &library.remaining_counts {
        hasher.update(&card.0.to_le_bytes());
        hasher.update(&count.to_le_bytes());
    }
    hasher.update(&(library.known_bottom.len() as u64).to_le_bytes());
    for card in &library.known_bottom {
        hasher.update(&card.0.to_le_bytes());
    }
'''
new = '''    hasher.update(&(library.known_top.len() as u32).to_le_bytes());
    for card in &library.known_top {
        hasher.update(&card.0.to_le_bytes());
    }

    hasher.update(&(library.remaining_counts.len() as u32).to_le_bytes());
    for count in &library.remaining_counts {
        hasher.update(&count.card.0.to_le_bytes());
        hasher.update(&[count.count]);
    }

    hasher.update(&(library.known_bottom.len() as u32).to_le_bytes());
    for card in &library.known_bottom {
        hasher.update(&card.0.to_le_bytes());
    }
'''
if old not in text:
    raise SystemExit("library fingerprint repair anchor missing")
lib.write_text(text.replace(old, new, 1))
