from pathlib import Path


def patch_root() -> None:
    p = Path("rust/crates/urza-mc/src/root.rs")
    s = p.read_text()
    old = '''        for evaluation in &mut evaluations {
            let action = resolve_root_action(&sampled_bridge, &evaluation.action, *world)?;
            let mut branch = sampled.clone();
            apply_action_with_rng(
                &mut branch,
                cards,
                action,
                GameRngContext {
                    root,
                    world: *world,
                    logical_event: LogicalEventId(0),
                },
            )
            .map_err(|source| RootActionError::RootActionApply {
                world: *world,
                source,
            })?;

            let continuation = rollout_with_logical_event_offset(
                branch,
                cards,
                continuation_policy,
                RolloutConfig {
                    root,
                    world: *world,
                    max_steps: rollout_max_steps - 1,
                },
                1,
            )
            .map_err(|source| RootActionError::WorldRollout {
                world: *world,
                source,
            })?;
            record_world(&mut evaluation.result, *world, continuation)?;
        }
'''
    new = '''        for evaluation in &mut evaluations {
            let outcome = evaluate_sampled_root_world(
                &sampled,
                &sampled_bridge,
                cards,
                continuation_policy,
                root,
                rollout_max_steps,
                *world,
                &evaluation.action,
            )?;
            record_outcome(&mut evaluation.result, outcome)?;
        }
'''
    if old not in s:
        raise SystemExit("fixed root-world loop pattern not found")
    s = s.replace(old, new, 1)
    s = s.replace("fn canonical_worlds(", "pub(crate) fn canonical_worlds(", 1)
    s = s.replace("fn public_root_actions(", "pub(crate) fn public_root_actions(", 1)
    s = s.replace("fn empty_result()", "pub(crate) fn empty_result()", 1)

    insertion = '''

pub(crate) fn evaluate_sampled_root_world<D: CardDatabase>(
    sampled: &TrueState,
    sampled_bridge: &CandidateBridge,
    cards: &D,
    continuation_policy: &DeterministicPolicy,
    root: RootSeed,
    rollout_max_steps: u32,
    world: WorldId,
    root_action: &RootActionKey,
) -> Result<WorldOutcome, RootActionError> {
    let action = resolve_root_action(sampled_bridge, root_action, world)?;
    let mut branch = sampled.clone();
    apply_action_with_rng(
        &mut branch,
        cards,
        action,
        GameRngContext {
            root,
            world,
            logical_event: LogicalEventId(0),
        },
    )
    .map_err(|source| RootActionError::RootActionApply { world, source })?;

    let continuation = rollout_with_logical_event_offset(
        branch,
        cards,
        continuation_policy,
        RolloutConfig {
            root,
            world,
            max_steps: rollout_max_steps - 1,
        },
        1,
    )
    .map_err(|source| RootActionError::WorldRollout { world, source })?;
    world_outcome(world, continuation)
}
'''
    marker = "\npub(crate) fn empty_result()"
    if marker not in s:
        raise SystemExit("empty_result marker not found")
    s = s.replace(marker, insertion + marker, 1)

    start = s.index("fn record_world(\n")
    stop = s.index("\n#[cfg(test)]", start)
    replacement = '''pub(crate) fn record_outcome(
    aggregate: &mut MonteCarloResult,
    outcome: WorldOutcome,
) -> Result<(), RootActionError> {
    match outcome.outcome {
        SampleOutcome::Win { family, turn } => {
            if !(1..=HORIZON_TURN).contains(&turn) {
                return Err(RootActionError::TerminalOutsideHorizon {
                    world: outcome.world,
                    turn,
                });
            }
            let bucket = usize::from(turn - 1);
            aggregate.win_distribution.t1_through_t6[bucket] =
                aggregate.win_distribution.t1_through_t6[bucket]
                    .checked_add(1)
                    .ok_or(RootActionError::CounterOverflow)?;
            let entry = aggregate
                .family_wins
                .iter_mut()
                .find(|entry| entry.family == family)
                .expect("WinFamily::ALL contains every terminal family");
            entry.wins = entry
                .wins
                .checked_add(1)
                .ok_or(RootActionError::CounterOverflow)?;
        }
        SampleOutcome::LossByHorizon => {
            aggregate.win_distribution.losses = aggregate
                .win_distribution
                .losses
                .checked_add(1)
                .ok_or(RootActionError::CounterOverflow)?;
        }
    }
    aggregate.outcomes.push(outcome);
    Ok(())
}

fn world_outcome(world: WorldId, result: RolloutResult) -> Result<WorldOutcome, RootActionError> {
    let continuation_steps =
        u32::try_from(result.trace.len()).map_err(|_| RootActionError::TraceLengthOverflow)?;
    let rollout_steps = continuation_steps
        .checked_add(1)
        .ok_or(RootActionError::TraceLengthOverflow)?;

    let outcome = match result.stop {
        RolloutStop::Terminal(family) => {
            let turn = result.final_information.turn;
            if !(1..=HORIZON_TURN).contains(&turn) {
                return Err(RootActionError::TerminalOutsideHorizon { world, turn });
            }
            SampleOutcome::Win { family, turn }
        }
        RolloutStop::Horizon => SampleOutcome::LossByHorizon,
        stop @ (RolloutStop::StepLimit | RolloutStop::NoCandidate) => {
            return Err(RootActionError::IncompleteWorld { world, stop });
        }
    };

    Ok(WorldOutcome {
        world,
        outcome,
        rollout_steps,
    })
}
'''
    s = s[:start] + replacement + s[stop:]
    p.write_text(s)


def patch_lib() -> None:
    p = Path("rust/crates/urza-mc/src/lib.rs")
    s = p.read_text()
    if "mod adaptive;" not in s:
        s = s.replace("mod root;\n", "mod adaptive;\nmod root;\n", 1)
    export = '''pub use adaptive::{
    ADAPTIVE_ROOT_EVAL_VERSION, ROOT_WORLD_CACHE_VERSION, AdaptiveRootActionComparison,
    AdaptiveRootConfig, AdaptiveRootError, AdaptiveSearchStats, AdaptiveStopReason,
    InMemoryRootOutcomeCache, NoopRootOutcomeCache, RootOutcomeCache, RootWorldCacheKey,
    compare_root_actions_adaptive, compare_root_actions_adaptive_world_ids,
    current_r5_evaluation_namespace,
};
'''
    if "pub use adaptive::{" not in s:
        s = s.replace("pub use root::{\n", export + "pub use root::{\n", 1)
    p.write_text(s)


def patch_cli() -> None:
    p = Path("rust/crates/urza-cli/src/main.rs")
    s = p.read_text()
    s = s.replace(
        "use urza_mc::{MONTE_CARLO_VERSION, ROOT_ACTION_EVAL_VERSION};",
        "use urza_mc::{\n    ADAPTIVE_ROOT_EVAL_VERSION, MONTE_CARLO_VERSION, ROOT_ACTION_EVAL_VERSION,\n    ROOT_WORLD_CACHE_VERSION,\n};",
        1,
    )
    s = s.replace('"phase": "R5-root-action-value",', '"phase": "R5-adaptive-cache-performance",', 1)
    s = s.replace(
        '"root_action_eval_version": ROOT_ACTION_EVAL_VERSION,',
        '"root_action_eval_version": ROOT_ACTION_EVAL_VERSION,\n        "adaptive_root_eval_version": ADAPTIVE_ROOT_EVAL_VERSION,\n        "root_world_cache_version": ROOT_WORLD_CACHE_VERSION,',
        1,
    )
    old = '''        "current_scope": "fixed-budget common-world root-action comparison and deterministic WinByHorizon value selection complete over the frozen R4/R5 candidate, rollout, and hidden-world surfaces",
        "next_r5_work": "add adaptive-confidence stopping, value/result caching, and performance instrumentation only after preserving the common-world and public-semantic comparison contract",
'''
    new = '''        "adaptive_contract": "adaptive evaluation consumes common WorldIds in canonical batches and stops early only when the complete configured fixed-budget root ranking is mathematically unable to change under any remaining outcomes; this is exact finite-budget certification rather than a probabilistic confidence interval",
        "cache_contract": "root-world outcomes are keyed by canonical ValueKey, complete EvaluationNamespace, RootSeed, public RootActionKey, WorldId, and cache schema version; namespace validation covers linked rules/model/policy/value/RNG plus information/MC sampling and bridge/rollout/root continuation identities",
        "instrumentation_contract": "deterministic counters report worlds, root-world requests, cache hits/misses, actual rollouts, and executed/avoided rollout steps; instrumentation does not participate in value ranking or cache identity",
        "current_scope": "fixed-budget root evaluation remains the correctness oracle; exact adaptive ranking certification, in-memory root-world caching, and deterministic performance counters are complete around that reference contract",
        "next_r5_work": "benchmark representative hands and consider parallel root/world execution or optional statistical stopping only if they preserve fixed-budget parity, common-world pairing, and cache namespace safety",
'''
    if old not in s:
        raise SystemExit("R5 audit tail pattern not found")
    s = s.replace(old, new, 1)
    p.write_text(s)


def patch_log() -> None:
    p = Path("rust/DEVELOPMENT_LOG.md")
    s = p.read_text()
    marker = "## 2026-09-05 — R5 exact adaptive evaluation, cache, and instrumentation"
    if marker in s:
        return
    s += '''

## 2026-09-05 — R5 exact adaptive evaluation, cache, and instrumentation

- Kept fixed-budget common-world root-action comparison as the reference correctness path.
- Added exact finite-budget adaptive ranking certification. Early stopping is permitted only when the complete final configured-budget ranking cannot change even under maximally favorable remaining outcomes for every trailing root.
- Added a validated `EvaluationNamespace` builder for the linked R4/R5 rules/model/information/policy/value/RNG/sampling/bridge/rollout/root stack plus caller-supplied catalog digest and environment identity.
- Added an in-memory per-root/per-world outcome cache keyed by public `ValueKey`, full evaluation namespace, root seed, semantic root action, world identity, and cache schema version.
- Added deterministic performance counters for sampling, root-world work, cache behavior, and rollout steps executed/avoided. Metrics are observational only.
- Refactored fixed and adaptive evaluation to share the same sampled-root execution and outcome aggregation path; no second gameplay implementation was introduced.
- Added parity/cache/hidden-order/namespace/certification acceptance tests. Python gameplay/policy logic remains out of scope.
'''
    p.write_text(s)


patch_root()
patch_lib()
patch_cli()
patch_log()
