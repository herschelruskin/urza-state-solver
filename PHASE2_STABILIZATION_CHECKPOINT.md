# Phase 2 Stabilization Checkpoint

**Date:** 2026-08-22  
**Branch:** `phase2-non-oracle-runtime`  
**Checkpoint head before this document:** `8e262e349d9ed6fe0a66b461c13ea3b22d25824f`  
**PR:** #10 — Phase 2: non-Oracle runtime kernel  
**Status at checkpoint:** Phase 2 runtime smoke GREEN; Oracle stack priority smoke GREEN.

---

## 1. Why this checkpoint exists

Phase 2 successfully established important infrastructure for an information-faithful non-Oracle solver, but implementation expanded rapidly into many card-specific runtime surfaces. That created a real risk of turning the project into a second independent Magic rules engine rather than the intended Markov/DP/Monte-Carlo policy and evaluation system.

This checkpoint freezes that expansion and restores a disciplined development loop.

The project goal is **not** to implement every possible Commander rules interaction. The goal is to implement enough correct, information-faithful game mechanics to evaluate this Urza deck's mulligan policy, tutor decisions, win-turn distribution, interaction sensitivity, and card-swap effects.

---

## 2. What remains unquestionably in scope

The following work is foundational and should be preserved:

- strict separation of true game state from policy-visible information;
- no hidden-library or future-information leakage into policy decisions;
- explicit deterministic RNG / reproducible seeds;
- canonical strategic state/value identity;
- replayable deterministic trajectories;
- staged search/tutor observations so targets become visible only when legally known;
- policy interfaces independent of raw hidden state;
- complete win-turn recording through the T6 horizon;
- action-equivalence / memoization foundations needed for future `V(I)` / `Q(I,a)` work;
- enough legal runtime mechanics to produce representative real-deck trajectories.

These are directly connected to the final non-Oracle analysis goals.

---

## 3. Grafdigger's Cage decision

The recent Grafdigger's Cage work is considered a **legitimate rules correction**, not scope creep.

The relevant invariant is:

> If Grafdigger's Cage is on the battlefield, creature cards in libraries cannot enter the battlefield.

This matters to real deck actions that put artifacts directly from the library onto the battlefield, including Urza's Saga III, Reshape, Whir of Invention, and Transmute Artifact. The correction is retained and regression-tested.

The implementation regression introduced while making that correction — accidental removal of `apply_x_artifact_stack_action` — was repaired in `8e262e3`. This is an example of the integration risk created by excessive simultaneous runtime expansion and is one reason for this stabilization checkpoint.

---

## 4. Scope freeze from this point forward

**Do not add a new card-specific mechanic or rules surface merely because it can be imagined, noticed in the deck list, or appears in a horizon state.**

A new mechanic may be implemented during stabilization only when at least one of these conditions is met:

1. It causes a reproducible hard runtime blocker on representative trajectories.
2. It produces an illegal game state or materially incorrect zone/resource transition.
3. It leaks hidden information across the policy boundary.
4. It appears often enough in seeded real-deck trajectories to materially distort mulligan, tutor, or win-turn estimates.
5. It blocks a specifically required final-product capability from `NON_ORACLE_IMPLEMENTATION_ROADMAP.md`.

Otherwise the mechanic should be documented as deferred rather than implemented immediately.

Rare hypothetical interactions are **not** blockers by default.

---

## 5. Evidence rule for future fixes

Every proposed implementation change should begin with evidence, not speculation.

Before changing production behavior, record:

- the deterministic seed or focused fixture that demonstrates the issue;
- whether the issue is rules correctness, information leakage, policy quality, runtime coverage, or architecture;
- the expected effect on final analysis outputs;
- the smallest coherent code surface that needs to change.

After the patch:

- run the focused smoke;
- run the full Phase 2 runtime smoke;
- preserve the Phase 1 regression gate;
- keep the Oracle regression/priority smoke green where applicable;
- do not continue to the next feature while the branch is red.

---

## 6. Checkpoint discipline

Going forward, development should use explicit checkpoints rather than long chains of exploratory edits.

### Checkpoint rule

A checkpoint is created when:

- the branch is green;
- the currently intended capability is complete enough to evaluate;
- unresolved issues are documented;
- the next task is clearly bounded.

Each checkpoint should record:

- commit SHA;
- CI status;
- what changed since the previous checkpoint;
- observed blockers or limitations;
- whether those limitations matter to the final research questions;
- exact next step.

### Known useful historical checkpoint

`68e11ca585bb9389c19e635bf7be7b7bfc32cbe4` was an earlier known-green Phase 2 point before the subsequent large expansion of card-specific runtime modules. It is retained as a comparison/recovery reference, **not** as an automatic rollback target.

### Current stabilization checkpoint

`8e262e349d9ed6fe0a66b461c13ea3b22d25824f` is the current code checkpoint:

- Grafdigger's Cage library-to-battlefield restriction work retained;
- accidentally removed X-artifact stack resolver restored;
- Phase 2 runtime smoke green;
- Oracle stack priority smoke green.

---

## 7. Immediate next sequence

No additional card mechanic should be added before this sequence is completed.

1. Treat the current code as frozen except for genuine stabilization defects.
2. Run/review the existing 250-seed representative trajectory diagnostics from this checkpoint.
3. Classify every observed problem into:
   - **BLOCKER** — must fix before statistical evaluation;
   - **MATERIAL MODEL GAP** — likely to bias outputs and needs evidence-based prioritization;
   - **POLICY QUALITY** — rules work, but deterministic base policy makes a poor choice;
   - **DEFERRED EDGE CASE** — real but unlikely to materially affect analysis;
   - **ARCHITECTURE DUPLICATION** — code works but should eventually be consolidated rather than expanded.
4. Fix only BLOCKER items first, one at a time with green CI between them.
5. Once blocker-free again, stop rules expansion and begin the actual value/Monte-Carlo/mulligan analysis layer.

---

## 8. Architectural direction

The long-term target remains:

- one authoritative mechanical game transition model wherever practical;
- a separate legal-information projection for the non-Oracle policy;
- a policy that chooses only from legally visible observations/actions;
- DP/memoization and Monte Carlo operating on strategic information states;
- Oracle Mode retained as a perfect-information ceiling/diagnostic, not copied feature-for-feature into a second rules implementation.

Card-specific runtime bridges may remain where necessary, but new duplication must justify itself against the final product goals.

---

## 9. Final-product reminder

The project is considered successful when it can reliably answer questions such as:

- What opening-hand archetypes should be kept or mulliganed at each London mulligan depth?
- What should be bottomed from kept hands?
- How quickly does a hand/deck win probabilistically by T1–T6?
- What tutor choices emerge from broad strategic states?
- How does explicit interaction change those probabilities?
- Does swapping one or more cards materially change win timing, keep rate, or resilience?

Completeness as a general Magic rules engine is **not** a project success criterion.

---

## 10. Development rule adopted at this checkpoint

> **Evidence -> bounded patch -> focused test -> full green gate -> checkpoint/document -> next task.**

If a proposed change cannot be tied to an observed correctness failure or one of the final analysis goals, defer it rather than expanding the runtime.