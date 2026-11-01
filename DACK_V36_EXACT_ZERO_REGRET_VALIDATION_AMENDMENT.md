# DACK v36 — prespecified 124k zero-regret validation optimization (amendment)

**Timing:** Introduced AFTER the 123k model was frozen, but BEFORE
ANY 124k gameplay outcomes were generated. This amendment changes
only computational allocation for validation, NOT the v36 model,
training sources, seat/stage rules, action gate, candidate selection,
population, primary metric or action-value estimand.

The original protocol called for all 256 physical game IDs
124000..124255 at all actual early stages0..2: 768 total
randomly dealt stage states. It proposed 12 physical KEEP
futures per state. This would spend 9,216 strict-beam160
gameplay calls on KEEP outcomes, even on states where
frozen v27 and v36 choose the exact same action.

For a conditional **action-policy difference** at stage state i,

  D_i = [1(v36 KEEP)-1(v27 KEEP)] × [Q_i(KEEP)-C(seat_i,stage_i)].

If both policies choose KEEP or both MULL, the leading action
difference is exactly 0, so D_i=0 for **every possible
unobserved physical future**. No gameplay simulation is
needed to estimate this zero. This is not heuristic
state canonicalization, card equivalence, or outcome imputation;
it is an algebraic property of the *same-action* comparison.
The complete population denominator of 768 state rows
remains unchanged. It is improper to compute the average
only among changed states as the whole-deck improvement.

## Revised prospective-independent validation pipeline

1. With already frozen v36 model SHA, enumerate ALL 256
   held-out 124k physical game IDs and stage0,1,2 sevens.
   Compute original v27 and frozen v36 KEEP/MULL actions
   using only visible seven, known 92 multiset, seat,
   stage, pretrained model. Archive immutable complete
   **outcome-blind** 768-state census BEFORE any
   124k rollout is generated.
2. Take ONLY the action-disagreement states. Each
   receives **32 independent hidden92 physical shuffled
   KEEP outcomes**, same frozen v33b bottom, exact
   stable-dice beam160 physics. 16 deterministic
   game-ID shards, including archived empty shards
   if no disagreements occur in a shard.
3. Separately generate ALL 4-seat×3-stage 64-future
   full99 frozen-v27-plus-v33b downstream Q(MULL)
   cells = 768 independent full99 physical rollouts.
   No current rejected seven enters the future reshuffle.
4. For each of 768 original states, compute the
   action difference D_i. For unchanged actions,
   set D_i=0 *exactly*. Changed actions have
   direct physical 32-future Qkeep and independent
   shared C. Group-bootstrap 256 original game
   IDs, changed state physical 32-future outcomes
   and the same cell-wide C lottery ONCE per iteration.
5. Report cumulative T1, by-T2, by-T3 and per-stage
   population-average differences and two-source CI.
   Original acceptance gate remains: >=8 altered
   stages across 768, strictly positive lower 95%
   T2 bootstrap endpoint, and no convincing
   T1/T3 harm. No new parameter tuning or
   acceptance gate changes after seeing outcomes.
6. Only if gate passes, proceed with distinct
   125k N256 full-game paired v5/v27/v33b/v36
   benchmark to test Bellman policy feedback and
   runtime. If fails, stop without 125k run.

Expected physical cost = 768 shared C deployments
+ 32×[number of changed actions], rather than
768+9,216 deployments. The accuracy for each relevant
KEEP Q is INCREASED from 12 to 32 independent futures.
If the original 123k training action-change count
(8/768) carries over, validation will use only
1,024 beam160 gameplay outcomes, saving 8,960
simulations without losing any contribution to
the one-step action-value comparison.

**Critical limits:** This only preserves EXACT
one-step action regret under a frozen future v33b policy.
It does not make full-policy paths under different
early decisions identical, cannot be used to infer
an actual deck full-game winrate without prospective
replay, and does not imply different bottoms or
heuristically similar cards are equivalent. No
122k, 121k, 117k or original 115k inspected
outcomes used in the frozen v36 training.

This protocol amendment supersedes the 124k
all-hands KEEP-label collection instructions in
`DACK_V36_TARGETED_PHYSICAL_PROTOCOL.md`;
training selection and model remain as originally
predeclared. All project research branches remain
isolated and unapproved.
