# R7 Teacher Sidecar Survey Checkpoint

This checkpoint freezes the first bounded survey of the R7 public-belief teacher over a meaningful R6-labeled opening corpus. It remains diagnostic only and does not promote the teacher into the mulligan policy.

## Versioned survey

- survey: `r7_teacher_sidecar_survey_v1`
- profile: `r7_teacher_sidecar_survey_16w_r6_16x8_teacher_1x2_v1`
- source corpus generator: `r7_sequential_r6_corpus_v1`
- teacher keep annotation: `r7_teacher_keep_annotation_v1`

## Source corpus

The survey source is an exact 16-world slice of the existing high-budget R7/R6 teacher profile rather than the 1x1 pilot corpus:

- opening root: unchanged from `r7_teacher_256_worlds_16x8_v1`
- opening worlds: `500080..=500095`
- R5 hidden-world samples per keep package: 16
- R5 rollout maximum: 4096 steps
- R6 future-hand samples per continuation: 8
- R6 continuation root/world namespace: unchanged from the full teacher profile
- R6 policy, decision, objective, horizon, deck, and environment versions: unchanged

This keeps the source KEEP/MULL labels on the materially higher-budget R6 configuration while making the survey small enough to run as a dedicated evidence job.

## Bounded teacher annotation

Each visited R6 decision record is annotated only on the best keep package already selected by R6:

- teacher samples: 1
- maximum branching choice depth: 2
- maximum teacher actions per path: 6
- retained candidates per public group: 6
- leaf rollout maximum: 4096 steps
- deterministic teacher hidden-world ranges beginning at world `930000`, non-overlapping by record

The survey reports resolved-positive, resolved-zero, and unresolved records separately. It also reports aggregate teacher groups/actions/forced steps/truncations/incomplete branches/leaves/observation splits and per-stage counts.

## Disagreement interpretation

`positive_on_source_mull` is intentionally named as evidence, not policy. It means only:

1. R6 recommended MULL at that visible decision stage under the accepted R6 value model; and
2. the bounded R7 teacher found at least one terminal win in its finite hidden-world sample for R6's already-selected best keep package.

It does **not** mean the teacher recommends KEEP. The survey does not evaluate the teacher value of the mull-again continuation, does not re-rank London bottoms, and cannot compare teacher keep value against an R6 continuation value as though they were the same model.

Before any future teacher-driven mulligan recommendation, both KEEP and MULL continuations must be evaluated under one explicitly versioned teacher decision model with the accepted public-information/future-invariance contracts preserved.

## CI boundary

The one-record teacher sidecar smoke remains in the cumulative Rust foundation gate. The 16-world survey runs in the dedicated `R7 teacher sidecar survey` workflow and uploads a TSV artifact. Push execution is intentionally opt-in via a `[r7-survey]` commit prefix (or manual workflow dispatch), so the evidence run does not become a permanent cost on every Rust commit.

## Still deferred

- teacher-valued mull-again continuation
- teacher re-ranking of London bottom subsets
- teacher control of KEEP/MULL recommendations
- larger survey windows or deeper teacher budgets until this survey's signal/truncation profile is inspected
- human archetype labels
- held-out archetype recommendation validation

R7 remains open after this checkpoint.
