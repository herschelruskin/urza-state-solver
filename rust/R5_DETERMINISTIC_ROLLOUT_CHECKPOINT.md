# R5 deterministic multi-step rollout checkpoint

## Scope

This checkpoint adds deterministic multi-step execution on top of the accepted public candidate bridge. It does not broaden R4 card/rules coverage and does not start Monte Carlo sampling.

## Architecture

The new `urza-rollout` crate owns sequencing. `urza-policy` remains public-state-only and has no dependency on execution `TrueState` or `urza-rules`. `urza-policy-bridge` remains the only action-enumeration/canonicalization boundary.

A rollout iteration is:

1. recognize an already-terminal public state;
2. perform engine automatic advancement only in true automatic windows;
3. rebuild `CandidateBridge` from the current exact world;
4. let `DeterministicPolicy` select one public semantic candidate;
5. resolve the opaque token to one exact legal `Action`;
6. apply the action with explicit deterministic RNG coordinates;
7. repeat.

Normal rollout stops are terminal win family, T6 horizon, configured step limit, or an explicit no-candidate boundary. Unexpected bridge/policy/rules failures remain typed errors rather than being silently converted into losses.

## Decision safety

`advance_automatic` is invoked only when the exact state is `OpponentCycle` or `Untap` with `Window::None`, an empty stack, and `PendingDecision::None`. Public tutor/reorder/may/payment decisions therefore cannot be skipped by phase automation.

Stack resolution and contingent decisions are ordinary rollout steps: after each selected action the candidate bridge is rebuilt from the resulting state.

## RNG and replay

`RolloutConfig` explicitly carries `RootSeed`, `WorldId`, and a maximum step count. Each selected public action receives `LogicalEventId(step_index)`. The existing rules occurrence cursor still supplies repeated physical-event identity.

`RolloutStep` records only public decision-point metadata plus `PolicyActionClass` and the exact collision-free `PolicyPublicKey`. Replay does not persist or match raw execution `ObjectId`s or decision-local tokens. `replay_trace` rebuilds candidates and requires the recorded semantic action to exist uniquely at the same public phase/window/turn before executing it with the same RNG coordinate.

## Acceptance fixtures

Acceptance covers:

- terminal recognition before any unnecessary policy action;
- deterministic multi-phase progression to the T6 horizon;
- stack resolution followed by fresh candidate rebuilding;
- exact same-seed/same-world replay across a randomized staged tutor search;
- raw `ObjectId` renaming invariance of the public multi-step trace;
- semantic replay onto a raw-ID-renamed world;
- explicit replay rejection when a recorded public action key drifts;
- strict Clippy, full workspace tests, benchmark compilation, and cumulative R0-R5 audits.

Validated implementation commit: `fcaa22bff246da3cbf91dab7118a9f9bcd9f2641` (`Build R5 deterministic multi-step rollout`). Dedicated acceptance run: GitHub Actions `33943111284`, result PASS. The gate passed locked dependency metadata, formatting, strict all-target/all-feature Clippy, full workspace tests, benchmark compilation, and cumulative R0-R5 audits. The temporary rollout workflow removed itself in the validated commit.

## Namespaces

- rules: `r4_acceptance_v6`;
- model: `urza_model_r4c_2026_09_04`;
- information: `information_state_v7_r4`;
- ValueKey: `value_key_v7_r4`;
- policy: `r5_candidate_contract_v2`;
- candidate bridge: `r5_public_candidate_bridge_v2`;
- rollout: `r5_deterministic_rollout_v2`.

No frozen R4 namespace changes in this block.

## Next R5 block

Connect sampled hidden worlds and Monte Carlo root evaluation to this deterministic rollout API. `urza-mc` remains unchanged until this checkpoint passes.

Python gameplay/policy logic remains out of scope.


## V2 deterministic cycle escape

The rollout now keeps execution-local history of exact decision states and semantic actions already executed from them. If an identical exact decision state recurs and the previously selected ordinary non-pass action consumed no game RNG, that action is suppressed only at that recurring state and the unchanged deterministic policy selects the next-ranked legal public candidate. Pass-priority and contingent decisions are never suppressed. Exact recurrence is valid whether the stack is empty or contains unresolved objects: the complete stack is already part of `TrueState`, so an identical full state plus an RNG-free ordinary action is a deterministic recurrence. This specifically prevents mana/untap loops from starving an underlying spell of resolution. Rejected candidates do not consume a trace index or logical RNG event. This converts proven deterministic voluntary loops such as Basalt Monolith tap -> pay 3 to untap -> resolve -> repeat into a canonical exit through pass priority without changing R4 rules legality or policy visibility.

The guard keys recurrence on exact `TrueState` only within one sampled world, but stores blocked choices by public `(PolicyActionClass, PolicyPublicKey)` semantics. Raw `ObjectId` renaming therefore cannot change the public trace. Actions that advance `rng_occurrence_cursor` are not blocked on recurrence, so genuinely stochastic retries remain eligible under their later logical-event coordinates.

Rollout namespace is now `r5_deterministic_rollout_v2`; cache continuation identity therefore invalidates v1 outcomes automatically. Validation run: GitHub Actions `33948188923`.
