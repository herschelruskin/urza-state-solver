# Post-R5 zero-positive diagnostic ladder

## Status

This checkpoint records the response to the frozen R5 natural-terminal search producing no positive trajectory. It is diagnostic work only: no R4 rules/card semantics, terminal definitions, R5 deterministic policy identity, rollout-v3 semantics, RNG contract, or `max_steps = 4096` setting may change unless a reproducible correctness defect is isolated.

Fresh negative evidence before this ladder:

- hidden worlds `228928..245311`, 16 accepted pilot openings: 262,144 rollouts;
- hidden worlds `245312..261695`, 16 accepted pilot openings: 262,144 rollouts;
- combined: **524,288 fresh rollouts**;
- result: every rollout stopped at `Horizon`; zero natural terminals, zero `StepLimit`, zero `NoCandidate`.

This is sufficient to stop blind hidden-world widening and diagnose reachability/policy separation instead.

## Five-step ladder

1. **Freeze the negative checkpoint.** Preserve the 524,288-rollout result and frozen semantics above. **DONE.**
2. **Revalidate terminal reachability.** Re-run the accepted R4 terminal-family gate: all 13 registered families must retain a real-catalog positive witness and an executable final-step transition through the public Rust rules API. Any failure is a concrete rules/terminal defect and stops policy broadening. **IN PROGRESS.**
3. **One-deviation natural-state search.** On real frozen-policy Horizon worlds, replay the exact baseline prefix, enumerate legal public candidates through `CandidateBridge`, force exactly one alternate semantic action, then return to accepted deterministic rollout with the same root/world and logical RNG coordinates. Stop on the first positive or incomplete diagnostic. **IN PROGRESS.**
4. **Two/three-deviation search with state deduplication.** Only if step 3 is clean and negative. This remains diagnostic POLICY/search work, not production-policy replacement. **PENDING.**
5. **Policy-independent legal trajectory search.** Only if bounded deviations remain negative. Use a diagnostic best-first/beam search over the accepted Rust candidate bridge and rules engine to answer whether a legal positive path exists; never port Python gameplay logic or silently install the diagnostic search as production policy. **PENDING.**

## Decision boundary

- R4 final acceptance already states that all 13 audited terminal families have a real-catalog positive witness and an executable final-step witness through the public rules transition API. Step 2 revalidates that accepted contract at the current head; it does not invent synthetic teacher positives.
- If terminal revalidation fails, isolate and repair only the reproducible correctness defect before continuing.
- If one deviation produces a natural terminal, record the opening world, hidden world, decision index, baseline semantic action, forced semantic action, terminal family/turn, and complete semantic trace. That proves terminal/engine viability on a naturally sampled state and identifies a concrete deterministic-policy miss.
- If a one-deviation continuation produces `StepLimit` or `NoCandidate`, stop expansion and isolate that exact opening/hidden world/deviation.
- If bounded deviations are negative but policy-independent search wins, classify the gap as POLICY/search evidence rather than permission to mutate rules.
- An all-Horizon teacher is not adequate evidence for R7 mulligan-value separation; positive reachability/density must be established before relying on that signal for learning.
