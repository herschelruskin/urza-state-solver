# R7 Teacher Subtree Cache Diagnostic

This R7-only diagnostic records the conservative sampled-belief transposition cache used by the bounded teacher search.

The cache key includes the remaining teacher choice/step budgets and a canonical world-id ordering of the sampled exact-world support. Each world key includes its exact replay state and logical-event coordinate. This cache identity is an execution optimization only; it does not participate in public action identity, candidate generation, R5 policy behavior, or R6 mulligan behavior.

The first complete-only cache experiment (`r7_public_belief_bounded_search_v4`) preserved the Top/Reality-Chip two-card depth-3 result at `1/1`, with 106 public groups, 105 public actions, 4 truncated groups, 99 incomplete candidate branches, and 26 ceiling-pruned sibling actions. It inserted 4 complete subtree values and observed 0 cache hits. Depth 1 and depth 2 remained explicitly incomplete.

The follow-up `v5` experiment also permits exact incomplete outcomes (`IncompleteLeaf` and `AllCandidateBranchesIncomplete`) to be memoized, but only as the same explicit incomplete outcome. They are never converted into losses, finite values, or scores. This tests whether the large incomplete portion of the depth-3 tree contains exact future-semantic transpositions without weakening cache identity.

The controlled depth-1/depth-2/depth-3 measurement for v5 is triggered by this revision. The cache is retained as an optimization only if empirical reuse justifies its hashing and memory cost.
