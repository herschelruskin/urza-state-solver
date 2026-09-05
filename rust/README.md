# Urza Simulator Rust rebuild

This workspace is the clean-room, non-oracle Rust rebuild. Python remains in the repository as a regression witness and fixture source, not as the normative architecture or rules source.

Milestone status:

- R0 foundation: accepted;
- R1 catalog/state/information foundation: accepted;
- R2 core sequencing primitives: accepted;
- R3 staged search/top/permission mechanics: accepted;
- R4 engine interactions and 13-family terminal catalog: accepted;
- R5 deterministic policy/rollout work: next.

R4 closes with 47 active card identities, an exact 15-card extension over frozen R3, while unsupported identities and deferred primitive text remain explicitly classified rather than approximated. See `R4_ACCEPTANCE.md` for the boundary.

Foundation/acceptance commands:

    cargo fmt --all -- --check
    cargo clippy --locked --workspace --all-targets --all-features -- -D warnings
    cargo test --locked --workspace --all-targets
    cargo check --locked --workspace --benches
    cargo run --locked -p urza-cli -- r0-audit
    cargo run --locked -p urza-cli -- r1-audit
    cargo run --locked -p urza-cli -- r2-audit
    cargo run --locked -p urza-cli -- r3-audit
    cargo run --locked -p urza-cli -- r4-audit
