# DACK v0.72 Patch A — semantic payment signature

Status: **implemented and validated; no pruning enabled**.

## Base
- Source: `dack_t3_solver_v0_68_color_canonicalization.py`
- Base SHA-256: `2742000fb450b7ab4c365bfbc1e9a8862873b580fa364d66041085ac7c17a132`

## Patch A
New source:
- `src/dack_t3_solver_v0_72_payment_signature.py`
- SHA-256 of the locally tested source: `16646d7e8551574cd7064de11423b2afe66b50562175d5a1b20ad57fcf3d43ee`

Patch A adds an observational frozen `PaymentSemanticSignature` containing:
- residual W, C, unrestricted colored, restricted legend, restricted artifact, restricted Dack-white;
- total and colored mana spent;
- per-pool spend amounts;
- a Pentad-Prism-sensitive spent-color class matching the current v0.68 Sunburst abstraction.

## Behavior guarantee for Patch A
The new signature is not consulted by:
- `pay_options` / payment generation;
- spell casting;
- state `key()`;
- scoring;
- frontier selection;
- beam pruning;
- any card rule or game action.

The v0.68-to-v0.72 Patch-A diff is additive only: signature code plus test assertions.

## Validation
The complete existing solver `--selftest` passes after Patch A.

New assertions also verify:
1. generic {1} from W+C still retains both legal residual payment states;
2. the two residual payment states receive different semantic signatures;
3. legacy `payment_tags` agrees with signature total/colored spent values;
4. Pentad Prism color class is 1 for W+W, 2 for W+any, and 2 for any+any under the existing abstraction;
5. restricted legend, artifact, and Dack-white pools remain independently visible.

No production simulation was run for this patch.
