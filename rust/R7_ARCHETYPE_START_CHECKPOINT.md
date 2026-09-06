# R7 Hand-Archetype Start Checkpoint

**Phase:** R7 — human-readable hand archetypes  
**Baseline:** accepted R6 head `ea16186d0f5b43fd1dbb3bb3865ec268d8fd7a5b`  
**Roadmap source:** `NON_ORACLE_IMPLEMENTATION_ROADMAP.md`, Phase 6

## Scope rule

R7 is an interpretation/data layer downstream of trustworthy R6 evaluation.

The hard boundary is:

> hand roles, feature vectors, clusters, labels, nearest-archetype distances, and confidence are descriptive outputs only; they do not participate in R5/R6 policy, value, RNG, or cache identity.

This launch slice does **not** port Python gameplay or policy logic and does **not** broaden the accepted R4 card/rules surface.

## Implemented in the launch slice

- Added versioned R7 interpretation constants:
  - `ARCHETYPE_LAYER_VERSION = r7_hand_interpretation_v1`
  - `INTERPRETATION_ROLE_VERSION = r7_card_roles_v1`
  - `HAND_FEATURE_SCHEMA_VERSION = r7_hand_features_v1`
  - `EVALUATED_HAND_RECORD_VERSION = r7_evaluated_hand_record_v1`
- Added a total `InterpretationCatalog` over the pinned 95 active card identities.
- Interpretation metadata is derived only from:
  - pinned R1 printed/type feature flags; and
  - already accepted R4 `CardProfile` semantics.
- Unsupported R4 cards are **not** guessed into tutor/engine/mana/utility roles.
- Added transparent `HandFeatureVector` counts for:
  - land-capable identities;
  - printed artifacts/creatures/instants/sorceries;
  - modal DFCs and X-cost identities;
  - recognized mana, blue-mana, and multi-mana sources;
  - recognized search sources;
  - recognized engine/utility/targeted-effect pieces;
  - R4-supported versus currently unmodeled identities.
- Added `EvaluatedHandRecord` extraction from a completed `MulliganReport`.
  - Features are computed from card identities first.
  - R6 recommendation/value fields are copied afterward as teacher labels.
  - The record retains stage, mulligan depth, seat/Caverns facts, policy version, horizon, environment, recommendation, values, value gap, and sampled-decision confidence.
- Added focused tests for metadata totality, representative role derivation, unsupported-card non-guessing, and deterministic card-only feature extraction.

## Deliberately not claimed yet

R7 is **started, not accepted**. This slice does not yet claim the remaining Phase 6 checklist:

- no evaluated-hand corpus/export pipeline yet;
- no clustering/grouping algorithm yet;
- no human-readable archetype labels yet;
- no held-out recommendation-accuracy validation yet;
- no nearest-archetype distance/confidence API yet;
- no ANN/CNN or learned value approximation.

In particular, labels will not be invented before cluster contents are inspected.

## Next R7 slice

1. Build a reproducible evaluated-hand corpus from R6 reports with explicit provenance.
2. Define deterministic feature normalization/distance semantics.
3. Implement the first transparent grouping/clustering method over those records.
4. Produce cluster summaries for inspection **without naming them yet**.
5. Add regressions proving clustering/labels cannot alter the underlying R6 recommendation/value for the same report.

Only after cluster contents are stable and interpretable should human-readable labels be assigned and held-out accuracy measured.
