# R7 Evaluated-Hand Corpus / Distance Checkpoint

**Phase:** R7 human-readable hand archetypes  
**Baseline:** `ac0bbb2cceb3b6dc00d06017ddc48a50be44555e`  
**Scope:** downstream corpus, normalization, distance, and first unlabeled grouping only

## Architecture boundary

R7 remains interpretation-only. The R7 corpus consumes completed R6 mulligan reports / evaluated-hand records after policy/value evaluation. No R7 role, feature, distance, grouping, cluster, or future label is permitted to participate in R5/R6 policy choice, rollout RNG, hidden-world sampling, value comparison, or cache identity.

This slice does not broaden R4 card/rules coverage and does not port Python gameplay or policy logic.

## Implemented in this slice

- `EvaluatedHandSampleId`
  - explicit opening `RootSeed`, `WorldId`, and mulligan stage provenance;
  - deterministic total ordering for corpus storage;
  - dataset identity only, never strategic policy/value identity.
- `EvaluatedHandCorpus`
  - deterministic `BTreeMap` storage;
  - records RNG scheme/version;
  - rejects duplicate sample identities;
  - requires one homogeneous teacher configuration (record/role/feature/report versions, policy, horizon, environment);
  - revalidates imported records by recomputing features from card identities through the accepted `InterpretationCatalog`;
  - validates current-seven and recommended-kept-hand sizes.
- Integer feature normalization
  - `r7_per_card_milli_v1`;
  - 15 explicitly ordered axes in thousandths per card;
  - no floating-point dependence;
  - omits `r4_rules_supported_count` from the distance axes because it is exactly redundant with `unmodeled_by_r4_count` for valid feature vectors.
- Transparent feature distance
  - `r7_unweighted_l1_v1`;
  - unweighted Manhattan/L1 distance over the versioned normalized axes;
  - reports total distance plus count of differing axes.
- First unlabeled grouping reference
  - `r7_stage_single_link_v1`;
  - same-stage connected components under an explicit L1 radius;
  - deterministic sample ordering and deterministic medoid selection;
  - summaries expose membership, medoid, maximum medoid distance, KEEP/MULL counts, exact-sample ties, and forced keep-floor counts;
  - no human-readable archetype names are assigned.

## Focused regressions

The module tests cover:

- stable seed/world/stage corpus ordering;
- duplicate rejection;
- mixed teacher-configuration rejection;
- exact integer normalization and symmetric L1 distance;
- transparent grouping of nearby versus distant hand shapes;
- version/RNG provenance.

## Deliberately deferred

R7 is not accepted by this checkpoint. Still required:

1. produce a meaningful evaluated-hand corpus from accepted R6 runs rather than only data-model fixtures;
2. inspect grouping behavior over multiple radius choices and stage populations;
3. add cluster-content summaries useful for human review (representative card identities / feature ranges as appropriate);
4. assign human-readable archetype labels only after inspecting real cluster contents;
5. implement nearest-archetype + distance/confidence for new human-entered hands;
6. validate archetype recommendation accuracy against held-out direct R6 DP/MC evaluations;
7. add an R7 cumulative acceptance audit/gate.

## Interpretation rule

A cluster is descriptive evidence about already-evaluated hands. It is not a replacement for R6 value evaluation and must not become a hidden heuristic controlling KEEP/MULL decisions.
