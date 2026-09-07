# Audited Rust milestone map

This file is the repo-local naming bridge for the audited v2 rebuild specification supplied for `rust-engine-rebuild`.

The formal milestone names are the audited specification's names. Historical Rust identifiers and workflow names are retained when renaming them would break provenance, but they must not be used to redefine the formal roadmap.

## Formal audited roadmap

| Formal milestone | Audited scope | Formal gate |
| --- | --- | --- |
| R0 | Bootstrap and benchmark harness | stable seed/registry and benchmark artifacts |
| R1 | Compact normalized state + RNG + information model | round-trip fixture and information-leakage tests |
| R2 | Core sequencing/rules kernel | simple deterministic trajectory parity |
| R3 | Search/tutor staging | observation-boundary audit fixtures |
| R4 | Engine cards and win catalog | full win-catalog parity and representative rules smokes |
| R5 | Deterministic rollout policy | action-choice parity on curated visible states |
| R6 | Hidden worlds and Monte Carlo Q | Phase 5H paired quality corpus |
| R7 | London mulligan DP | human-hand evaluation parity and Stage 5I fixtures |
| R8 | Native performance hardening | Hand 25 performance plus no semantic regression |
| R9 | Final analysis layer | stable analysis outputs over the accepted engine |

## Historical Rust naming bridge

The implementation sequence drifted numerically after R5. Preserve the historical symbols for artifact compatibility, but interpret them as follows:

- historical Rust R5 contains the deterministic rollout plus substantial hidden-world/Monte-Carlo machinery from formal R5 and R6;
- historical `r6_*` mulligan code and `rust/R6_ACCEPTANCE.md` implement the core of formal audited R7 (London mulligan DP);
- historical `r7_teacher_*`, `r7_signal_boundary_*`, and `rust-r7-*` diagnostics are **POST_R7_VALIDATION**, not the formal audited R7 milestone;
- do not invent a formal R8 meaning from those historical R7 labels: formal R8 remains native performance hardening;
- formal R9 remains the final analysis layer.

Stable version strings, file names, artifact names, and old workflow names do not need cosmetic renumbering. New documentation and new work must use the formal milestone names above and explicitly label legacy names when they appear.

## Formal R7 closure rule

Formal R7 means London mulligan DP, not teacher search. Close it only against both halves of the audited gate:

1. the exact human-hand evaluation corpus/witness; and
2. the accepted Phase 5I/Stage 5I fixtures.

Human decisions remain held-out evaluation labels. "Parity" does not mean tuning Rust to imitate human choices. Python finite-sample outputs are PARITY witnesses and must be interpreted through the audited source hierarchy; intentional Rust RNG/life/model corrections are classified rather than silently forced back to Python.

## Post-R7 validation contract

After formal R7 closure, teacher/signal-boundary work is an unnumbered validation phase before formal R8.

The teacher is a **read-only oracle/sidecar**:

- it may evaluate already-created public game states or already-selected keep packages;
- it may not rerank London bottoms or replace the production keep/mull decision;
- it may not mutate R5/R6 policy, formal-R7 mulligan behavior, production cache identity, interpretation features, rules legality, or gameplay merely because it finds a better line;
- incomplete, timeout, StepLimit, and NoCandidate are diagnostic statuses, never automatic losses;
- a teacher win at greater depth is evidence of a planning/search-depth boundary, not by itself a rules defect.

## Backward real-state ladder

The next post-R7 diagnostic ladder must move backward through **actual sampled game states**, not synthetic abundant-mana states.

Preferred tiers, derived from one replayable frozen-production trajectory:

1. late real decision state;
2. real turn-2 main-phase decision state;
3. real turn-1 main-phase decision state;
4. real kept opening state.

Each tier must retain replay provenance: opening root/world/stage/kept package, true sampled execution state, policy/RNG versions, rollout coordinate, and teacher configuration. The teacher evaluates the public belief induced by that state; hidden order is never admitted into teacher action identity.

Report every channel separately as complete positive, complete zero, incomplete with stop reason, or timeout. Do not collapse incomplete or timeout into zero.

## Production repair threshold

Do not repair production merely because R5 disagrees with the teacher, teacher needs more depth, a cache has few hits, or a bounded search is incomplete.

A production repair requires a reproducible correctness defect such as:

- a supported legal action is missing;
- an illegal action is generated or accepted;
- a transition, cost, target, stack resolution, trigger, terminal witness, or timing window violates the accepted RULE/MODEL contract;
- an observation leaks hidden information or withholds legally known information;
- RNG/replay/CRN identity violates its versioned contract;
- a strategic/cycle/cache identity merges states that are not equivalent under the accepted model.

If the legal action exists and the teacher can find the line while frozen production cannot, classify it as POLICY/planning evidence and leave production unchanged until a separate policy-performance decision is made.

## Sequence from here

1. close formal audited R7 with explicit evidence;
2. run the post-R7 backward real-state ladder with the teacher as a sidecar;
3. repair only demonstrated correctness defects;
4. begin formal R8 performance hardening, led by deterministic profiling and Hand 25;
5. begin formal R9 analysis only after the engine/performance baseline is accepted.
