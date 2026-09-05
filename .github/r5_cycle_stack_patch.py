from pathlib import Path

rollout = Path('rust/crates/urza-rollout/src/lib.rs')
text = rollout.read_text()
old = '''        if state.rng_occurrence_cursor == rng_cursor_before
            && decision_state.stack.is_empty()
            && matches!(decision_state.pending, PendingDecision::None)
'''
new = '''        if state.rng_occurrence_cursor == rng_cursor_before
            && matches!(decision_state.pending, PendingDecision::None)
'''
if old not in text:
    raise SystemExit('stack-restriction anchor missing')
text = text.replace(old, new, 1)

anchor = '''    #[test]
    fn same_seed_and_world_replay_random_search_exactly() {
'''
test = '''    #[test]
    fn deterministic_cycle_guard_escapes_with_underlying_stack_object() {
        let cards = cards();
        let basalt = cards.card_id_by_name("Basalt Monolith").expect("Basalt");
        let crypt = cards
            .card_id_by_name("Tormod's Crypt")
            .expect("Tormod's Crypt");
        let mut state = base_state(&cards, urza_rules::HORIZON_TURN);
        state.battlefield = BattlefieldZone::new(vec![permanent(20, basalt)]);
        state.stack.push(StackObject::Spell {
            object_id: ObjectId(900),
            card: crypt,
            x_value: None,
        });

        let result = rollout(state, &cards, &DeterministicPolicy, config(32)).unwrap();

        assert_eq!(result.stop, RolloutStop::Horizon);
        assert!(result.trace.len() < 16, "stacked cycle should exit before the step cap");
        assert!(
            result
                .final_state
                .battlefield
                .permanents()
                .iter()
                .any(|permanent| permanent.card == crypt)
        );
        assert!(
            result
                .trace
                .iter()
                .any(|step| step.class == PolicyActionClass::ProduceMana)
        );
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

'''
if anchor not in text:
    raise SystemExit('stack regression insertion anchor missing')
text = text.replace(anchor, test + anchor, 1)
rollout.write_text(text)

checkpoint = Path('rust/R5_DETERMINISTIC_ROLLOUT_CHECKPOINT.md')
data = checkpoint.read_text()
needle = 'Pass-priority and contingent decisions are never suppressed.'
replacement = (
    'Pass-priority and contingent decisions are never suppressed. Exact recurrence is valid '
    'whether the stack is empty or contains unresolved objects: the complete stack is already '
    'part of `TrueState`, so an identical full state plus an RNG-free ordinary action is a '
    'deterministic recurrence. This specifically prevents mana/untap loops from starving an '
    'underlying spell of resolution.'
)
if needle in data:
    data = data.replace(needle, replacement, 1)
checkpoint.write_text(data)

log = Path('rust/DEVELOPMENT_LOG.md')
data = log.read_text()
needle = '- Added direct Basalt-cycle escape and raw-ObjectId-renaming invariance regressions.'
replacement = (
    '- Added direct Basalt-cycle escape, nonempty-stack Basalt-cycle escape, and '
    'raw-ObjectId-renaming invariance regressions. The nonempty-stack fixture covers the '
    'artifact benchmark failure where a Basalt mana/untap loop repeatedly sat above an '
    'unresolved artifact spell.'
)
if needle in data:
    data = data.replace(needle, replacement, 1)
log.write_text(data)
