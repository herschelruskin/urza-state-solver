# R7 Teacher Keep-Value Sidecar Checkpoint

## Status

R7 remains in progress. This checkpoint does **not** accept human-readable hand archetypes and does **not** replace the accepted R6 mulligan policy.

## Baseline

The bounded public-belief teacher was validated before this sidecar was introduced:

- search: `r7_public_belief_bounded_search_v2`
- policy: `r7_teacher_public_belief_v2`
- exact green baseline: `6f588cdaa28acb8b6f34603958514956bee3e085`
- cumulative workflow: `34009418829`
- the real R4 `Power Artifact + Basalt Monolith + Urza` witness is recovered as a terminal win
- permuting the pre-existing unknown library order does not change that teacher result

The natural-opening viability probe is intentionally not overclaimed. Two selected teacher-profile openings still produced `0/2` teacher wins under the tiny probe budget, so the teacher has not earned authority to replace R6 KEEP/MULL labels.

## Sidecar version

`r7_teacher_keep_annotation_v1`

The sidecar is downstream of the existing `r7_sequential_r6_corpus_v1` dataset. For every R6 corpus record it may evaluate only the keep package that R6 already selected as its best keep package.

It explicitly does **not**:

- re-rank London bottom subsets;
- evaluate or replace the R6 mull-again continuation value;
- change the recorded R6 KEEP/MULL recommendation;
- use R7 interpretation roles, feature vectors, clusters, or future archetype labels as gameplay inputs;
- participate in R5/R6 policy or cache identity.

## Kept-hand reconstruction

A corpus record stores the visible current seven and the R6-selected kept hand. The sidecar reconstructs London bottoms as an exact card multiset subtraction:

`current seven - selected kept multiset = known bottom multiset`

This is validated against the stage bottom count and then passed through the accepted `bridge_kept_hand` path. Repeated identities such as multiple `Island` copies are handled by multiplicity rather than set membership.

## Teacher RNG provenance

Sidecar records receive deterministic, non-overlapping teacher hidden-world ranges. If the base search uses `S` samples and a corpus record has deterministic ordinal `i`, its first teacher world is:

`base_first_world + i * S`

No opening-world identity is reused as teacher hidden-world identity by implication.

## Resolved versus unresolved

Teacher evaluation is not allowed to turn incompleteness into a loss.

A sidecar annotation is either:

- **Resolved** — contains the bounded teacher `WinDistribution`, score, and search statistics; or
- **Unresolved** — explicitly identifies a leaf step limit, leaf no-candidate stop, or an all-retained-candidates-incomplete public decision.

Other structural/search failures remain hard errors.

## CI smoke

The cumulative Rust gate runs a tiny `r7-teacher-sidecar` probe after the teacher viability probe. It generates one actual R6 smoke-corpus record, annotates its R6-selected keep package, and prints source action plus resolved/zero/positive or unresolved teacher status.

This is a plumbing and boundary gate, not representative archetype evidence.

## Before teacher values may affect mulligan recommendations

A later, separately versioned slice must provide evidence that the teacher adds useful signal on a meaningful evaluated sample. Any move from read-only annotation to decision authority must explicitly model and validate all newly compared quantities (for example alternate London bottoms and mull-again continuation) rather than mixing a teacher keep value with an R6 continuation value by accident.

Human-readable archetype labels remain deferred until trustworthy evaluated-hand contents can be inspected. Labels remain explanatory output, never a value-function input.
