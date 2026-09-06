# R7 Real Corpus / Cluster Review Checkpoint

**Phase:** R7 human-readable hand archetypes  
**Baseline:** `3619deade3eab8961446f393e225a0ccf40eef33`  
**Scope:** real sequential R6 corpus generation, radius sweep, and unlabeled cluster-content review

## Architecture boundary

This slice remains strictly downstream of accepted R6 evaluation. R7 does not alter R5/R6 policy, RNG, hidden-world sampling, value comparison, or cache identity. A generated corpus is descriptive teacher data only.

The generator follows the actual sequential mulligan policy path for each fixed opening world:

1. sample pregame seat/Caverns facts and the current seven;
2. evaluate the visible stage through accepted R6 KEEP-vs-MULL;
3. build the accepted R6 report and insert the derived R7 record;
4. generate the next fresh seven only when the accepted R6 recommendation is MULLIGAN;
5. stop the world trajectory when R6 recommends KEEP.

No rejected-hand identity or actual unrevealed next seven is introduced into R6 continuation value identity.

## Reproducible generation

`r7_sequential_r6_corpus_v1` records full generation provenance:

- profile version;
- deck version/hash identity;
- opening root seed and contiguous world range;
- RNG scheme;
- R5 policy version;
- R6 decision/objective versions;
- horizon and experimental keep floor;
- R5 rollout root, first world, sample count, and rollout step budget;
- R6 continuation root, first future world, and future-hand sample count;
- continuation-cache hit/miss instrumentation.

Two fixed profiles exist:

- `r7_smoke_2_worlds_1x1_v1` for regression coverage;
- `r7_pilot_16_worlds_1x1_v1` for real cluster-shape inspection in CI.

The pilot is deliberately a structural inspection corpus, not label-quality teacher data. One rollout/future-hand sample is too small to claim stable recommendation accuracy; higher-budget held-out evaluation remains required before human archetype labels are accepted.

## Review surfaces

The slice adds:

- deterministic radius sweeps reporting cluster count, singleton count, largest cluster, and stage-local cluster counts;
- selected-radius cluster-content review;
- medoid hand card names;
- per-feature min/max ranges;
- most frequent cards by total copies and hands containing them;
- seat distribution and Caverns-eligible membership;
- existing KEEP/MULL/tie/floor counts from the unlabeled cluster summary.

No human-readable archetype name is assigned in this slice.

## Generated artifact

CI runs:

```text
cargo run --locked -p urza-mulligan --bin r7-corpus -- pilot
```

and uploads the emitted tab-separated corpus/review report as the `r7-pilot-corpus` workflow artifact. The output contains complete generation provenance, every sequential evaluated record, the radius sweep, and selected-radius cluster reviews.

## Remaining R7 work

1. inspect the real pilot output and choose/justify an interpretation radius or grouping refinement;
2. generate a higher-budget teacher corpus suitable for recommendation labels;
3. assign human-readable labels only after cluster inspection;
4. implement nearest-archetype + distance/confidence for new hands;
5. validate recommendations against held-out direct high-budget R6 evaluation;
6. add the cumulative R7 acceptance audit/gate.
