# DACK v0.72 Patch B — exact semantic payment deduplication

Status: **implemented and validated; no dominance pruning enabled**.

## Base
Patch B branches from validated Patch A:
- `src/dack_t3_solver_v0_72_payment_signature.py`
- Patch-A SHA-256: `16646d7e8551574cd7064de11423b2afe66b50562175d5a1b20ad57fcf3d43ee`

## Patch B
New source:
- `src/dack_t3_solver_v0_72_exact_payment_dedup.py`
- locally tested SHA-256: `fa2cf128a6e63cecbaeba7c021c718b4de536372f790a4947cb55200dbca928f`

`pay_options()` still generates the same legal raw residual payment states from
`_pay_pool_options()`. The only added step is `exact_dedupe_payment_outcomes()`.

A branch is removed only when both are equal:
1. the complete frozen post-payment `State`;
2. the `PaymentSemanticSignature`.

Input order is preserved. There is no score comparison, resource dominance,
subset/superset test, or frontier pruning in Patch B.

## Validation

### Full inherited self-test
`--selftest`: **PASS**

### Patch-B regressions
- a deliberately duplicated identical payment state collapses to one;
- W-vs-C residual alternatives remain distinct;
- exact dedup is idempotent;
- restricted legend/artifact alternatives remain distinct when their states differ.

### Exhaustive small-pool equivalence audit
Patch A and Patch B were compared branch-for-branch over **94,464** combinations of:
- W/C/unrestricted-colored starting pools;
- restricted legend/artifact pools;
- generic, white, and colorless costs;
- legend/artifact payment permissions.

Result:
- payment-output mismatches: **0**
- exact duplicates removed by Patch B across this grid: **0**
- maximum legal residual branches observed: **81**

The zero-removal result is expected: v0.68's low-level `_pay_pool_options`
already stores residual resource tuples in a set. Patch B therefore establishes
a reusable semantic-dedup boundary without claiming a performance improvement.

## Production status
No production simulation was run.
No payment dominance is enabled.
No frontier/state dominance is enabled.
