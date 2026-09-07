# R7 Teacher Subtree Cache Diagnostic

This R7-only diagnostic records the conservative sampled-belief transposition cache used by the bounded teacher search.

The cache key includes the remaining teacher choice/step budgets and a canonical world-id ordering of the sampled exact-world support. Each world key includes its exact replay state and logical-event coordinate. This cache identity is an execution optimization only; it does not participate in public action identity, candidate generation, R5 policy behavior, or R6 mulligan behavior.

Only complete finite `WinDistribution` results are inserted. Incomplete leaves and all-candidate-incomplete subtrees are never cached as finite values.

Empirical Top/Reality-Chip boundary measurements are produced by the opt-in R7 signal-boundary workflow and will be recorded after the controlled d1/d2/d3 run completes.
