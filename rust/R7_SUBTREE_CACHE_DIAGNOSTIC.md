# R7 Teacher Subtree Cache Diagnostic

This R7-only diagnostic records the conservative sampled-belief transposition cache used by the bounded teacher search.

The cache key includes the remaining teacher choice/step budgets and a canonical world-id ordering of the sampled exact-world support. Each world key includes its exact replay state and logical-event coordinate. This cache identity is an execution optimization only; it does not participate in public action identity, candidate generation, R5 policy behavior, or R6 mulligan behavior.

The first complete-only cache experiment (`r7_public_belief_bounded_search_v4`) preserved the Top/Reality-Chip two-card depth-3 result at `1/1`, with 106 public groups, 105 public actions, 4 truncated groups, 99 incomplete candidate branches, and 26 ceiling-pruned sibling actions. It inserted 4 complete subtree values and observed 0 cache hits. Depth 1 and depth 2 remained explicitly incomplete.

The retained `r7_public_belief_bounded_search_v5` cache also memoizes exact incomplete outcomes (`IncompleteLeaf` and `AllCandidateBranchesIncomplete`), but only as the same explicit incomplete outcome. They are never converted into losses, finite values, or scores. The exact state, sampled world id, RNG/logical-event coordinate, and remaining teacher budgets remain part of cache identity, so future-semantic belief states are not merged merely to increase hit rate.

On the controlled `top-chip-two-hand` depth-3 probe, v5 preserved the `1/1` result and the same 105 public candidate actions, 4 truncated groups, 99 incomplete candidate branches, and 26 ceiling-pruned sibling actions. It recorded 19 exact cache hits and 87 inserts, reducing actual public-group evaluations from 106 to 87 (17.9%). The corresponding measured stage time was 22.873 seconds versus 26.462 seconds for v4 on one controlled runner pair; wall-clock timing is treated as noisy, while cache hits and group counts are the primary efficiency evidence.

Depth 1 remained `incomplete:all-candidates:12` and depth 2 remained `incomplete:all-candidates:12`, so subtree reuse did not move the observed teacher depth boundary. The cache therefore removes repeated downstream evaluation without altering public candidate generation, action count, teacher value, or the R5/R6 production boundary.

Empirical conclusion: exact future-semantic transpositions exist primarily among incomplete/dead teacher subtrees in this probe. The v5 cache is retained because it demonstrates real deterministic reuse while preserving explicit incomplete semantics and the established depth boundary.
