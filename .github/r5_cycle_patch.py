from pathlib import Path
import os
import textwrap

ROLLOUT = Path('rust/crates/urza-rollout/src/lib.rs')
text = ROLLOUT.read_text()

import_anchor = 'use thiserror::Error;\n'
if import_anchor not in text:
    raise SystemExit('rollout import anchor missing')
text = text.replace(
    import_anchor,
    'use std::collections::{BTreeSet, HashMap};\n\nuse thiserror::Error;\n',
    1,
)

old_version = 'pub const ROLLOUT_VERSION: &str = "r5_deterministic_rollout_v1";'
new_version = 'pub const ROLLOUT_VERSION: &str = "r5_deterministic_rollout_v2";'
if old_version not in text:
    raise SystemExit('rollout version anchor missing')
text = text.replace(old_version, new_version, 1)

init_anchor = '    let mut state = initial;\n    let mut trace = Vec::new();\n\n    loop {'
if init_anchor not in text:
    raise SystemExit('rollout loop init anchor missing')
text = text.replace(
    init_anchor,
    textwrap.dedent('''\
        let mut state = initial;
        let mut trace = Vec::new();
        let mut deterministic_attempts: HashMap<
            TrueState,
            BTreeSet<(PolicyActionClass, PolicyPublicKey)>,
        > = HashMap::new();

        loop {'''),
    1,
)

choose_anchor = textwrap.dedent('''\
        let bridge = CandidateBridge::build(&state, cards)?;
        let Some(token) = policy.choose(bridge.information(), bridge.candidates())? else {
            return finish(state, RolloutStop::NoCandidate, trace);
        };
''')
if choose_anchor not in text:
    raise SystemExit('rollout choose anchor missing')
text = text.replace(
    choose_anchor,
    textwrap.dedent('''\
        let bridge = CandidateBridge::build(&state, cards)?;
        let rejected = deterministic_attempts.get(&state);
        let available: Vec<_> = bridge
            .candidates()
            .iter()
            .filter(|candidate| {
                !rejected.is_some_and(|attempts| {
                    attempts.contains(&(candidate.class, candidate.key.clone()))
                })
            })
            .cloned()
            .collect();
        let Some(token) = policy.choose(bridge.information(), &available)? else {
            return finish(state, RolloutStop::NoCandidate, trace);
        };
'''),
    1,
)

pre_trace_anchor = textwrap.dedent('''\
        let index = u32::try_from(trace.len()).map_err(|_| RolloutError::StepIndexOverflow)?;

        trace.push(RolloutStep {
''')
if pre_trace_anchor not in text:
    raise SystemExit('pre-trace anchor missing')
text = text.replace(
    pre_trace_anchor,
    textwrap.dedent('''\
        let index = u32::try_from(trace.len()).map_err(|_| RolloutError::StepIndexOverflow)?;
        let selected_class = selected.class;
        let selected_semantics = (selected_class, selected.key.clone());
        let decision_state = state.clone();
        let rng_cursor_before = state.rng_occurrence_cursor;

        trace.push(RolloutStep {
'''),
    1,
)

execute_anchor = textwrap.dedent('''\
        execute(
            &mut state,
            cards,
            action,
            config,
            logical_event_id(logical_event_offset, index)?,
        )?;
''')
if execute_anchor not in text:
    raise SystemExit('rollout execute anchor missing')
text = text.replace(
    execute_anchor,
    textwrap.dedent('''\
        execute(
            &mut state,
            cards,
            action,
            config,
            logical_event_id(logical_event_offset, index)?,
        )?;

        // If the exact same decision state is encountered again, replaying an
        // already-executed non-random ordinary action would deterministically
        // reproduce the same trajectory. Suppress only that semantic action
        // on recurrence so the memoryless policy can choose its next-ranked
        // legal exit. Pass and contingent decisions are never suppressed.
        if state.rng_occurrence_cursor == rng_cursor_before
            && decision_state.stack.is_empty()
            && matches!(decision_state.pending, PendingDecision::None)
            && !matches!(
                selected_class,
                PolicyActionClass::PassPriority | PolicyActionClass::ContingentDecision
            )
        {
            deterministic_attempts
                .entry(decision_state)
                .or_default()
                .insert(selected_semantics);
        }
'''),
    1,
)

test_anchor = textwrap.dedent('''\
    #[test]
    fn same_seed_and_world_replay_random_search_exactly() {
''')
if test_anchor not in text:
    raise SystemExit('rollout test anchor missing')
tests = textwrap.dedent('''\
    #[test]
    fn deterministic_basalt_tap_untap_cycle_escapes_to_pass() {
        let cards = cards();
        let basalt = cards.card_id_by_name("Basalt Monolith").expect("Basalt");
        let mut state = base_state(&cards, urza_rules::HORIZON_TURN);
        state.battlefield = BattlefieldZone::new(vec![permanent(20, basalt)]);

        let result = rollout(state, &cards, &DeterministicPolicy, config(32)).unwrap();

        assert_eq!(result.stop, RolloutStop::Horizon);
        assert!(result.trace.len() < 16, "cycle guard should avoid the step cap");
        assert_eq!(result.trace[0].class, PolicyActionClass::ProduceMana);
        assert!(
            result
                .trace
                .iter()
                .any(|step| step.class == PolicyActionClass::ActivateAbility)
        );
        assert!(
            result
                .trace
                .iter()
                .any(|step| step.class == PolicyActionClass::PassPriority)
        );
    }

    #[test]
    fn deterministic_cycle_guard_preserves_raw_object_id_invariance() {
        let cards = cards();
        let basalt = cards.card_id_by_name("Basalt Monolith").expect("Basalt");
        let mut left = base_state(&cards, urza_rules::HORIZON_TURN);
        left.battlefield = BattlefieldZone::new(vec![permanent(20, basalt)]);
        let mut right = base_state(&cards, urza_rules::HORIZON_TURN);
        right.battlefield = BattlefieldZone::new(vec![permanent(20_020, basalt)]);

        let left_result = rollout(left, &cards, &DeterministicPolicy, config(32)).unwrap();
        let right_result = rollout(right, &cards, &DeterministicPolicy, config(32)).unwrap();

        assert_eq!(left_result.stop, RolloutStop::Horizon);
        assert_eq!(left_result.stop, right_result.stop);
        assert_eq!(left_result.trace, right_result.trace);
        assert_eq!(left_result.final_information, right_result.final_information);
    }

''')
text = text.replace(test_anchor, tests + test_anchor, 1)
ROLLOUT.write_text(text)

# Move Rust hard-coded namespace assertions/snapshots with the rollout version.
for rs in Path('rust').rglob('*.rs'):
    data = rs.read_text()
    updated = data.replace('r5_deterministic_rollout_v1', 'r5_deterministic_rollout_v2')
    if updated != data:
        rs.write_text(updated)

# Keep current R5 namespace tables aligned with the already-accepted bridge v2
# repair and the new rollout v2 behavior. Historical commit/run records remain.
for path in Path('rust').glob('R5_*CHECKPOINT.md'):
    data = path.read_text()
    data = data.replace('r5_public_candidate_bridge_v1', 'r5_public_candidate_bridge_v2')
    data = data.replace('r5_deterministic_rollout_v1', 'r5_deterministic_rollout_v2')
    path.write_text(data)

run_id = os.environ.get('GITHUB_RUN_ID', 'local-validation')
rollout = Path('rust/R5_DETERMINISTIC_ROLLOUT_CHECKPOINT.md')
data = rollout.read_text()
marker = '## V2 deterministic cycle escape'
if marker not in data:
    data += f'''\n\n{marker}\n\nThe rollout now keeps execution-local history of exact decision states and semantic actions already executed from them. If an identical exact decision state recurs and the previously selected ordinary non-pass action consumed no game RNG, that action is suppressed only at that recurring state and the unchanged deterministic policy selects the next-ranked legal public candidate. Pass-priority and contingent decisions are never suppressed. Rejected candidates do not consume a trace index or logical RNG event. This converts proven deterministic voluntary loops such as Basalt Monolith tap -> pay 3 to untap -> resolve -> repeat into a canonical exit through pass priority without changing R4 rules legality or policy visibility.\n\nThe guard keys recurrence on exact `TrueState` only within one sampled world, but stores blocked choices by public `(PolicyActionClass, PolicyPublicKey)` semantics. Raw `ObjectId` renaming therefore cannot change the public trace. Actions that advance `rng_occurrence_cursor` are not blocked on recurrence, so genuinely stochastic retries remain eligible under their later logical-event coordinates.\n\nRollout namespace is now `r5_deterministic_rollout_v2`; cache continuation identity therefore invalidates v1 outcomes automatically. Validation run: GitHub Actions `{run_id}`.\n'''
rollout.write_text(data)

bridge = Path('rust/R5_CANDIDATE_BRIDGE_CHECKPOINT.md')
data = bridge.read_text()
marker = '## V2 staged-choice viability repair'
if marker not in data:
    data += '''\n\n## V2 staged-choice viability repair\n\nCandidate bridge v2 rejects a `Transmute Artifact` cast candidate when the public battlefield contains no artifact that can satisfy the mandatory staged sacrifice choice. Rules legality remains authoritative; this is a public candidate viability condition preventing a root from entering an accepted pending decision with zero contingent candidates. A Transmute cast remains exposed when at least one public artifact sacrifice exists. Validation of the repair completed in GitHub Actions `33946481397`; implementation commit `60030a84c7ddae37c5d97e8fd83ba39dad13e79a`.\n'''
bridge.write_text(data)

log = Path('rust/DEVELOPMENT_LOG.md')
data = log.read_text()
marker = '## R5 deterministic rollout cycle guard'
if marker not in data:
    data += f'''\n\n{marker}\n\n- Classification: `ENGINE-SEQUENCING/PERFORMANCE-CORRECTNESS`.\n- Profiling exposed a deterministic Basalt Monolith tap / native untap / pass-resolution loop that reached both 4,096 and 8,192 step caps in sampled world 20487 under one CastCommander root.\n- `urza-rollout` now remembers exact repeated decision states and suppresses only previously executed ordinary non-pass semantic actions that consumed no game RNG. The next public policy-ranked legal candidate becomes the canonical loop exit; pass and contingent choices are never suppressed.\n- Rejected retries consume neither trace indexes nor logical RNG event IDs. Stochastic actions are not suppressed because a changed `rng_occurrence_cursor` prevents them from entering the deterministic-attempt set.\n- Added direct Basalt-cycle escape and raw-ObjectId-renaming invariance regressions.\n- Rollout namespace bumped to `r5_deterministic_rollout_v2`; linked R5 checkpoint namespace references updated.\n- Full strict Clippy, workspace tests, bench compilation, cumulative R0-R5 audits, and representative release performance matrix must pass in GitHub Actions `{run_id}` before this helper's changes are committed.\n'''
log.write_text(data)
