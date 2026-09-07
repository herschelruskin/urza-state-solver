use std::collections::{BTreeSet, HashMap};

use urza_core::{ManaPool, PendingDecision, TrueState};
use urza_policy::{DeterministicPolicy, PolicyActionClass, PolicyPublicKey};
use urza_policy_bridge::CandidateBridge;
use urza_rules::CardDatabase;

use crate::{
    RolloutConfig, RolloutError, RolloutStep, execute, logical_event_id, prepare_for_policy,
};

pub(crate) type SemanticAction = (PolicyActionClass, PolicyPublicKey);
pub(crate) type AttemptMap = HashMap<TrueState, BTreeSet<SemanticAction>>;
pub(crate) type ManaObservationMap = HashMap<TrueState, ManaRecurrenceObservation>;

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct ManaRecurrenceObservation {
    pub(crate) mana: ManaPool,
    pub(crate) semantics: SemanticAction,
    pub(crate) trace_index: usize,
}

pub(crate) fn mana_agnostic_state(state: &TrueState) -> TrueState {
    let mut normalized = state.clone();
    normalized.mana = ManaPool::default();
    normalized
}

pub(crate) const fn suppressible_ordinary(class: PolicyActionClass) -> bool {
    !matches!(
        class,
        PolicyActionClass::PassPriority | PolicyActionClass::ContingentDecision
    )
}

pub(crate) fn mana_strictly_dominates(current: ManaPool, previous: ManaPool) -> bool {
    let current = mana_amounts(current);
    let previous = mana_amounts(previous);
    current
        .iter()
        .zip(previous.iter())
        .all(|(current, previous)| current >= previous)
        && current
            .iter()
            .zip(previous.iter())
            .any(|(current, previous)| current > previous)
}

fn mana_amounts(pool: ManaPool) -> [u16; 6] {
    [
        pool.white,
        pool.blue,
        pool.black,
        pool.red,
        pool.green,
        pool.colorless,
    ]
}

/// Prove that a previously observed deterministic semantic cycle remains
/// unchanged for every policy action still available under this rollout's
/// configured step budget.
///
/// The shadow execution is deliberately exact except that it does not emit
/// trace entries or mutate the caller. If additional floating mana would
/// unlock a different policy choice before the old step cap, the proof fails
/// and the real rollout is allowed to continue generating that resource.
/// Any RNG occurrence advance also fails the proof so stochastic retries are
/// never converted into liveness suppressions.
#[allow(clippy::too_many_arguments)]
pub(crate) fn cycle_stationary_through_budget<D: CardDatabase>(
    initial: &TrueState,
    cards: &D,
    policy: &DeterministicPolicy,
    config: RolloutConfig,
    logical_event_offset: u64,
    start_index: usize,
    pattern: &[RolloutStep],
    deterministic_attempts: &AttemptMap,
    monotone_attempts: &AttemptMap,
) -> Result<bool, RolloutError> {
    if pattern.is_empty()
        || pattern
            .iter()
            .any(|step| step.class == PolicyActionClass::ContingentDecision)
    {
        return Ok(false);
    }

    let max_steps = config.max_steps as usize;
    if start_index >= max_steps {
        return Ok(false);
    }

    let mut state = initial.clone();
    let mut shadow_attempts = deterministic_attempts.clone();

    for offset in 0..(max_steps - start_index) {
        if prepare_for_policy(&mut state, cards)?.is_some() {
            return Ok(false);
        }

        let bridge = CandidateBridge::build(&state, cards)?;
        let resource_key = mana_agnostic_state(&state);
        let exact_rejected = shadow_attempts.get(&state);
        let monotone_rejected = monotone_attempts.get(&resource_key);
        let available: Vec<_> = bridge
            .candidates()
            .iter()
            .filter(|candidate| {
                let semantics = (candidate.class, candidate.key.clone());
                !exact_rejected.is_some_and(|attempts| attempts.contains(&semantics))
                    && !monotone_rejected.is_some_and(|attempts| attempts.contains(&semantics))
            })
            .cloned()
            .collect();
        let Some(token) = policy.choose(bridge.information(), &available)? else {
            return Ok(false);
        };
        let selected = bridge
            .candidates()
            .iter()
            .find(|candidate| candidate.token == token)
            .cloned()
            .ok_or(RolloutError::MissingResolvedAction(token))?;
        let expected = &pattern[offset % pattern.len()];
        let information = bridge.information();
        if information.turn != expected.turn
            || information.phase != expected.phase
            || information.window != expected.window
            || selected.class != expected.class
            || selected.key != expected.key
        {
            return Ok(false);
        }

        let action = bridge
            .resolved_action(token)
            .ok_or(RolloutError::MissingResolvedAction(token))?;
        let decision_state = state.clone();
        let rng_cursor_before = state.rng_occurrence_cursor;
        let absolute_index = start_index
            .checked_add(offset)
            .ok_or(RolloutError::StepIndexOverflow)?;
        let absolute_index =
            u32::try_from(absolute_index).map_err(|_| RolloutError::StepIndexOverflow)?;
        execute(
            &mut state,
            cards,
            action,
            config,
            logical_event_id(logical_event_offset, absolute_index)?,
        )?;

        if state.rng_occurrence_cursor != rng_cursor_before {
            return Ok(false);
        }

        if matches!(decision_state.pending, PendingDecision::None)
            && suppressible_ordinary(selected.class)
        {
            shadow_attempts
                .entry(decision_state)
                .or_default()
                .insert((selected.class, selected.key));
        }
    }

    Ok(true)
}
