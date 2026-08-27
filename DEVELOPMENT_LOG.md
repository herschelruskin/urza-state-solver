# Urza Solver Development Log

This file is the persistent checkpoint for architecture, validation, and next work.
Update it whenever a phase changes the model materially.

## Current target

**Phase 5H — adaptive confidence-gated selective Q**

Goal: preserve the clear gain from selective Q while preventing noisy Monte Carlo
overrides and allowing bounded contingent lookahead only when paired evidence
supports it.

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
| Confidence-gated Q | **in progress** | Phase 5H. |

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
12. Phase 5H adaptive confidence-gated selective Q — **current branch**

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

Corrected tutor-rich held-out benchmark: **10 hands x 4 paired worlds = 40 worlds**.

| Policy | T6 wins | Rate |
|---|---:|---:|
| rollout-v6 | 5 / 40 | 12.5% |
| one-step selective Q | 11 / 40 | 27.5% |
| bounded contingent Q | 10 / 40 | 25.0% |

Interpretation:

- selective Q is materially better than v6 on tutor-rich states;
- unconditional contingent depth is not yet a net improvement at the tiny MC budget;
- real contingent gains exist (notably hand 24 Reshape sacrifice -> target);
- noisy overrides also exist, so confidence/adaptive sampling is the next bottleneck.

Notable controls:

- hand 12 false Saga Top -> Vexing Bauble override disappeared after independent confirmation;
- hand 1: v6 1/4, one-step 2/4, two-step 2/4 — Q gain, no depth gain;
- hand 24: v6 0/4, one-step 0/4, two-step 1/4 — genuine candidate depth gain;
- hand 30 earlier apparent Q gain did not survive confirmation.

## Phase 5H acceptance target

1. Screening remains cheap.
2. Confirmation proceeds in fresh paired-world batches only when needed.
3. Candidate-vs-v6 evidence is measured per identical hidden world.
4. Weak or conflicting evidence falls back to v6.
5. Strong evidence may stop early.
6. Nested contingent Q uses the same gate, so weak child evidence collapses naturally to v6.
7. Existing bounded depth and information-safety regressions remain green.
8. Re-run the 40-world paired benchmark after implementation.
9. Prefer >= one-step-Q aggregate performance with fewer harmful paired-world regressions.

## After 5H

1. Freeze gameplay-policy architecture if confidence-gated Q validates.
2. Plug the final gameplay policy back into London mulligan valuation.
3. Re-run the 35 exact human mulligan benchmark hands.
4. Run the first full end-to-end 250 / 1,000+ deck simulations.
5. Compare win-turn distribution to the historical 250-goldfish baseline.
6. Add protection / interaction probability.
7. Add paired card-swap evaluator.
