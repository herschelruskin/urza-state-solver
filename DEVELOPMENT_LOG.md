# Urza Solver Development Log

This file is the persistent checkpoint for architecture, validation, and next work.
Update it whenever a phase changes the model materially.

## Current target

**Phase 5I — production Phase-5H Q inside London mulligan valuation**

Goal: value keep/mull and London-bottom choices under the exact frozen Phase-5H
gameplay policy, learn continuation thresholds only from fresh random deck hands,
then compare all 35 exact human benchmark sevens without using their labels for
solver selection.

## Architecture status

| Layer | Status | Notes |
|---|---|---|
| Rules / true state | mature | Explicit mechanics and terminal families remain authoritative. |
| Observation boundary | mature | True state and player observation are separated. |
| Hidden-world MC | mature | Common random worlds; explicit reproducible seeds. |
| Value model | mature | T1..T6 distribution-valued V/Q objective. |
| London mulligan DP | implemented | Sequential keep/mull + bottoming, floor at keep 2. |
| Opening context | implemented | Commander seat context + Gemstone Caverns pregame decision. |
| Library knowledge | implemented | Exact remaining multiset is logically deduced; order remains hidden. |
| Selective tutor Q | implemented | Tutor/search states only; deterministic v6 remains leaf policy. |
| Bounded contingent Q | implemented | Dependent post-commit choices only; Transmute sacrifice -> target bounded chain. |
| MC confirmation | implemented | Screen and confirmation use disjoint hidden-world namespaces. |
| Confidence-gated Q | **validated / frozen** | Phase 5H passes paired held-out validation. |
| Mulligan + frozen Q integration | **in progress** | Phase 5I uses one identical production gameplay policy in bottom screen and confirmation. |

## Branch / PR stack

1. Phase 2 non-Oracle runtime — PR #10
2. Phase 3 distribution-valued V/Q + human baselines — PR #11
3. Phase 4A hidden-world sampler — PR #12
4. Phase 4B root Monte Carlo — PR #13
5. Phase 5A mulligan DP — PR #14
6. Phase 5B runtime parity + selective tutor-Q — PR #15
7. Phase 5C adaptive mulligan / tutor-Q diagnostics — PR #16
8. Phase 5D Commander seat + Gemstone Caverns — PR #17
9. Phase 5E bounded contingent two-step tutor-Q — PR #18
10. Phase 5F deduced library membership — PR #19
11. Phase 5G independent MC confirmation — PR #20
12. Phase 5H adaptive confidence-gated selective Q — PR #21
13. Phase 5I production-Q London mulligan integration — **current branch**

## Locked design principles

- Never expose exact hidden library order before a legal observation.
- Exact remaining-card membership in our own library is logically deducible.
- Q improves policy; it does not replace the rules engine or broad deterministic leaf.
- Common hidden worlds compare candidate actions fairly.
- v6 wins exact ties.
- Dependent lookahead is legal only after information becomes observable.
- Do not expand Q depth merely because more search is possible.
- T6 is inclusive search horizon; T7 is not expanded as a win.
- Protection and speed are separate eventual outputs; a fast naked win may still be valid.

## Latest evaluation checkpoint

The authoritative gameplay-policy checkpoint is the completed Phase-5H validation
below. The earlier independent-confirmation 40-world result is retained in PR #20
history but is no longer the production policy benchmark.

## Phase 5H validation — COMPLETE

Final corrected tutor-rich held-out benchmark: **10 hands x 4 paired worlds = 40 worlds**.

| Policy | T6 wins | Rate |
|---|---:|---:|
| rollout-v6 | 5 / 40 | 12.5% |
| Phase 5H one-step Q | 12 / 40 | 30.0% |
| Phase 5H bounded contingent Q | 14 / 40 | 35.0% |

Paired-world quality comparisons:

| Comparison | Better | Tie | Worse |
|---|---:|---:|---:|
| 5H one-step vs v6 | 8 | 32 | **0** |
| 5H contingent vs v6 | 10 | 30 | **0** |
| 5H contingent vs 5H one-step | 2 | 38 | **0** |

Interpretation:

- confidence gating improves aggregate selective-Q performance beyond the previous
  independent-confirmation controller;
- bounded contingent lookahead is now a net positive rather than a net negative;
- no observed paired held-out world regressed relative to v6;
- no observed paired held-out world regressed from one-step to contingent Q;
- the prior hand-24 Reshape gain was rejected as insufficiently supported;
- new robust contingent-only gains appear on hands 21 and 29;
- hand 20 improved strongly from v6 1/4 to 5H Q 4/4;
- hand 25 rerun after the Chain/Offer stack fix completed cleanly at 2/4 for all
  policies, with Q still better on distributional timing in one paired world.

Phase 5H also exposed and fixed a typed-runtime parity defect: Chain of Vapor /
An Offer You Can't Refuse stack objects now resolve only on an actual priority pass
rather than intercepting every legal priority action above them. Production CI is
green including a typed priority-activation regression.

**Decision:** freeze the gameplay-policy architecture at Phase 5H. Do not add deeper
Q before end-to-end mulligan and deck-level validation demonstrates a need.

## Phase 5I acceptance target

1. Production tutor-Q configuration is explicit and immutable.
2. Bottom screening and confirmation use the same Phase-5H gameplay policy.
3. Only the outer hidden-world budget differs between bottom screen/confirmation.
4. Stage continuation values are trained from fresh random sevens with no human labels.
5. All 35 usable exact human sevens are evaluated at their recorded London stage.
6. Human labels are comparison-only and never alter solver choice or shortlist.
7. Report keep/mull agreement, stage-specific disagreement, human-bottom exact match,
   human-bottom shortlist rate, and value deltas.
8. Inspect disagreement classes before changing strategy or training on labels.
9. Existing Phase-5H, information-safety, and London-mulligan regressions remain green.

## Roadmap after Phase 5I

1. Re-run the 35 exact human mulligan benchmark hands.
2. Inspect disagreement classes without training on the labels.
3. Run the first full end-to-end 250 / 1,000+ deck simulations.
4. Compare win-turn distribution to the historical 250-goldfish baseline.
5. Add protection / interaction probability.
6. Add paired card-swap evaluator.
