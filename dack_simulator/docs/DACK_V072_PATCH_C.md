# DACK v0.72 Patch C — conservative payment dominance

Status: **implemented and validated; no frontier/state dominance enabled**.

## Base
Patch C branches from validated Patch B:
- `src/dack_t3_solver_v0_72_exact_payment_dedup.py`

## New solver
- `src/dack_t3_solver_v0_72_payment_dominance.py`
- tested SHA-256: `31a7b0672b4415c87af2cde12000a083d58b920c93ce59b34eb0ba944ab3a068`
- source length: 148,274 characters / 2,780 lines

## Scope

Raw `pay_options()` remains exact and unchanged in meaning.

Dominance is applied only inside ranked/simple `pay_simple()` calls. Pentad Prism's
special cast path calls raw `pay_options()` directly and therefore bypasses dominance.

A payment outcome may dominate another only when:
1. payment-history-sensitive semantic tags match:
   - total mana spent;
   - colored mana spent;
   - Prism-sensitive color class;
2. the retained residual mana multiset is proven to be a capability superset by
   unit-for-unit matching over the modeled pools.

The proof relation is conservative:
- unrestricted colored (`any`) can replace W, legend-restricted, artifact-restricted,
  or Dack-white-restricted mana;
- W can replace W, legend-restricted, artifact-restricted, or Dack-white-restricted mana;
- C can replace C, legend-restricted, or artifact-restricted mana;
- W/any and C remain incomparable because true colorless versus white costs differ;
- restricted legend/artifact/Dack-white pools remain mutually distinct unless replaced
  by a provably more general unrestricted unit.

No score comparison or heuristic is used.

## Critical implementation safeguard

An initial pre-commit implementation pruned the option list before indexing
`payment_rank`. Cast-level validation caught that this compressed rank numbers and could
expose a legal branch at a different global rank, producing cast outputs not present in
Patch B.

That implementation was discarded before commit.

The final Patch C preserves Patch-B payment-rank identities exactly:
- sort the full raw option list;
- select the original rank;
- suppress that branch only if it is dominated;
- never renumber the surviving alternatives.

Therefore Patch C may delete ranked payment branches but cannot introduce a new ranked
branch merely by shifting indices.

## Validation

### Full inherited self-test
`--selftest`: **PASS**

### Targeted Patch-C regressions
- unrestricted any-color residual mana dominates W when payment history matches;
- W and C remain incomparable;
- unrestricted C dominates legend-restricted generic mana when history matches;
- differing colored-payment history blocks pruning;
- Pentad Prism raw payment alternatives remain available.

### Dense payment-grid audit
6,912 resource/cost/permission combinations were checked.

Results:
- raw Patch-C `pay_options()` vs Patch B mismatches: **0**
- dominated payment branches removed: **4,145**
- maximum raw payment branches in the grid: **25**
- every removed branch had a retained explicit capability-superset witness;
- retained branches formed an undominated antichain under the Patch-C relation.

### Cast-level audit
1,944 cast states were compared across:
- artifact and nonartifact costs;
- white and generic costs;
- variable Everflowing Chalice payments;
- Pentad Prism;
- Void Mirror and Vexing Bauble contexts.

Results:
- cast outputs invented by Patch C: **0**
- Patch-B cast outputs removed: **1,412**
- every removed cast output had a retained same-action outcome with matching payment-history
  semantics and provably stronger residual mana capability.

### Search-level A/B fixture check
8 deterministic Patch-B vs Patch-C fixtures were compared at identical beam/order/seat.

Result:
- earliest win-turn mismatches: **0**
- included T1 wins, T2 wins, and misses.

Observed runtime was generally modestly lower in Patch C fixtures, but this is not treated
as a benchmark or production estimate.

## Production status

No production Monte Carlo was run.
No frontier/state dominance is enabled.
Patch C is not yet promoted to the production engine.
