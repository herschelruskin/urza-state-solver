# Urza Simulator Rust rebuild

This workspace is the clean-room, non-oracle Rust rebuild. Python remains in the repository as a regression witness and fixture source, not as the normative architecture or rules source.

R0 establishes compact identifiers/state skeletons, the information boundary, replay versus strategic identities, deterministic RNG coordinates, the active-card coverage registry, instrumentation scaffolding, and benchmark fixture loading. Intrinsic card rules are intentionally not implemented in R0.

Foundation commands:

    cargo fmt --all -- --check
    cargo clippy --locked --workspace --all-targets --all-features -- -D warnings
    cargo test --locked --workspace --all-targets
    cargo check --locked --workspace --benches
    cargo run --locked -p urza-cli -- r0-audit
