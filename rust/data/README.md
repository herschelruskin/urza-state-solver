# R0 data artifacts

card_catalog.r0.json is intentionally identity/count-only. It pins stable R0 CardDefId assignments for the active branch decklist but does not claim that Oracle text or intrinsic card rules are implemented.

card_coverage.r0.json classifies every active card as INTENTIONALLY_UNMODELED during R0. R1/R2 promotions must change statuses only alongside the corresponding metadata/rules implementation and focused fixtures.

The catalog digest reported by urza-cli r0-audit is BLAKE3 over the exact catalog JSON bytes.
