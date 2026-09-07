#![forbid(unsafe_code)]

use std::collections::BTreeSet;

use thiserror::Error;
use urza_info::{CanonicalObjectId, CardDefId, InformationState, PendingDecisionKind, Phase};

/// R5 deterministic policy layer on top of the frozen R4
/// rules/information/value contract.
pub const POLICY_PHASE: &str = "R5";
pub const POLICY_VERSION: &str = "r5_candidate_contract_v5_resource_setup";

/// Opaque decision-local handle supplied by the execution bridge.
///
/// The token is deliberately not part of the semantic policy key. It maps the
/// selected public choice back to an execution action outside this crate.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct ActionToken(pub u16);

/// Coarse public action class used by the baseline deterministic R5 selector.
///
/// This is policy metadata, not rules legality. The execution bridge supplies
/// only legal candidates and may classify a mana activation as contingent when
/// rules explicitly allow that mana ability while paying a pending cost.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum PolicyActionClass {
    ContingentDecision,
    PlayLand,
    ProduceMana,
    ManaSetup,
    CastSpell,
    ActivateAbility,
    PassPriority,
}

/// Stable, policy-visible semantic key for deterministic tie-breaking.
///
/// Every field is public information. Canonical object identifiers are
/// structural observation identifiers from `urza-info`, never execution
/// `ObjectId`s. `detail` is an exact, collision-free sequence of additional
/// public u16 fields used for payments, ordered card choices, and source
/// multisets that cannot be represented by the fixed scalar slots.
#[derive(Debug, Clone, Default, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct PolicyPublicKey {
    /// Bridge-defined public action-kind code. Different execution action
    /// families must use different codes even when their other fields match.
    pub kind: u16,
    pub card: Option<CardDefId>,
    pub source: Option<CanonicalObjectId>,
    pub target: Option<CanonicalObjectId>,
    pub parameter: Option<u16>,
    pub secondary: u16,
    pub detail: Vec<u16>,
}

/// One legal, policy-visible candidate supplied by the execution bridge.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct PolicyCandidate {
    pub token: ActionToken,
    pub class: PolicyActionClass,
    pub key: PolicyPublicKey,
}

impl PolicyCandidate {
    pub fn new(token: ActionToken, class: PolicyActionClass, key: PolicyPublicKey) -> Self {
        Self { token, class, key }
    }
}

#[derive(Debug, Clone, Error, PartialEq, Eq)]
pub enum PolicyError {
    #[error("duplicate decision-local action token {0:?}")]
    DuplicateActionToken(ActionToken),
    #[error("a contingent candidate was supplied while no public decision is pending")]
    ContingentCandidateWithoutPending,
    #[error("a public contingent decision is pending but no contingent candidate was supplied")]
    MissingContingentCandidate,
}

/// Deterministic R5 selector.
///
/// The policy consumes only public information and public candidate metadata.
/// It guarantees stable selection independent of candidate enumeration order,
/// prevents ordinary actions from skipping a pending rules decision, drains an
/// already-nonempty public stack before adding more optional actions, preserves
/// reusable mana sources outside the main phase, and avoids deterministic
/// fail-to-find when a staged modeled tutor has at least one real target.
#[derive(Debug, Clone, Copy, Default)]
pub struct DeterministicPolicy;

impl DeterministicPolicy {
    pub fn choose(
        &self,
        information: &InformationState,
        candidates: &[PolicyCandidate],
    ) -> Result<Option<ActionToken>, PolicyError> {
        validate_candidate_tokens(candidates)?;

        let pending_kind = information.pending.kind();
        let pending = pending_kind != PendingDecisionKind::None;
        let drain_stack = !pending && !information.stack.is_empty();
        let has_contingent = candidates
            .iter()
            .any(|candidate| candidate.class == PolicyActionClass::ContingentDecision);
        let prefer_real_search_target = is_search_target_pending(pending_kind)
            && candidates.iter().any(|candidate| {
                candidate.class == PolicyActionClass::ContingentDecision
                    && candidate.key.card.is_some()
            });

        if pending && !has_contingent {
            return Err(PolicyError::MissingContingentCandidate);
        }
        if !pending && has_contingent {
            return Err(PolicyError::ContingentCandidateWithoutPending);
        }

        let selected = candidates
            .iter()
            .filter(|candidate| {
                !pending || candidate.class == PolicyActionClass::ContingentDecision
            })
            .min_by(|left, right| {
                semantic_rank(
                    left,
                    drain_stack,
                    information.phase,
                    prefer_real_search_target,
                )
                .cmp(&semantic_rank(
                    right,
                    drain_stack,
                    information.phase,
                    prefer_real_search_target,
                ))
            });

        Ok(selected.map(|candidate| candidate.token))
    }
}

fn validate_candidate_tokens(candidates: &[PolicyCandidate]) -> Result<(), PolicyError> {
    let mut seen = BTreeSet::new();
    for candidate in candidates {
        if !seen.insert(candidate.token) {
            return Err(PolicyError::DuplicateActionToken(candidate.token));
        }
    }
    Ok(())
}

fn semantic_rank(
    candidate: &PolicyCandidate,
    drain_stack: bool,
    phase: Phase,
    prefer_real_search_target: bool,
) -> (u8, u8, &PolicyPublicKey, ActionToken) {
    (
        class_rank(candidate.class, drain_stack, phase),
        search_target_rank(candidate, prefer_real_search_target),
        &candidate.key,
        candidate.token,
    )
}

fn search_target_rank(candidate: &PolicyCandidate, prefer_real_search_target: bool) -> u8 {
    if prefer_real_search_target
        && candidate.class == PolicyActionClass::ContingentDecision
        && candidate.key.card.is_none()
    {
        1
    } else {
        0
    }
}

const fn is_search_target_pending(kind: PendingDecisionKind) -> bool {
    matches!(
        kind,
        PendingDecisionKind::TutorTarget
            | PendingDecisionKind::TransmuteTarget
            | PendingDecisionKind::WhirTarget
            | PendingDecisionKind::ReshapeTarget
            | PendingDecisionKind::BayTarget
            | PendingDecisionKind::SagaTarget
            | PendingDecisionKind::TezzeretTarget
    )
}

const fn class_rank(class: PolicyActionClass, drain_stack: bool, phase: Phase) -> u8 {
    if drain_stack {
        match class {
            PolicyActionClass::ContingentDecision => 0,
            PolicyActionClass::PassPriority => 1,
            PolicyActionClass::PlayLand => 2,
            PolicyActionClass::CastSpell => 3,
            PolicyActionClass::ActivateAbility => 4,
            PolicyActionClass::ProduceMana => 5,
            PolicyActionClass::ManaSetup => 6,
        }
    } else if matches!(phase, Phase::PrecombatMain) {
        // Demand-driven main-phase mana: use an already-legal action before
        // tapping more resources. If nothing spendable is legal yet, produce
        // mana and re-evaluate on the next public decision.
        match class {
            PolicyActionClass::ContingentDecision => 0,
            PolicyActionClass::PlayLand => 1,
            PolicyActionClass::CastSpell => 2,
            PolicyActionClass::ActivateAbility => 3,
            PolicyActionClass::ProduceMana => 4,
            PolicyActionClass::ManaSetup => 5,
            PolicyActionClass::PassPriority => 6,
        }
    } else {
        // Outside the main phase, do not pre-emptively tap reusable sources
        // merely because a mana action is legal. Already-affordable public
        // spells/activations may still be taken; otherwise preserve resources
        // and advance the phase.
        match class {
            PolicyActionClass::ContingentDecision => 0,
            PolicyActionClass::PlayLand => 1,
            PolicyActionClass::CastSpell => 2,
            PolicyActionClass::ActivateAbility => 3,
            PolicyActionClass::PassPriority => 4,
            PolicyActionClass::ProduceMana => 5,
            PolicyActionClass::ManaSetup => 6,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use urza_info::{ObservedPendingDecision, ObservedSourceRef};

    fn candidate(token: u16, class: PolicyActionClass, card: u16, source: u16) -> PolicyCandidate {
        PolicyCandidate::new(
            ActionToken(token),
            class,
            PolicyPublicKey {
                card: Some(CardDefId(card)),
                source: Some(CanonicalObjectId(source)),
                ..PolicyPublicKey::default()
            },
        )
    }

    #[test]
    fn candidate_enumeration_order_cannot_change_the_choice() {
        let information = InformationState::default();
        let policy = DeterministicPolicy;
        let a = candidate(8, PolicyActionClass::CastSpell, 20, 3);
        let b = candidate(2, PolicyActionClass::PlayLand, 40, 5);
        let c = candidate(7, PolicyActionClass::PassPriority, 0, 0);

        let forward = policy
            .choose(&information, &[a.clone(), b.clone(), c.clone()])
            .unwrap();
        let reversed = policy.choose(&information, &[c, b, a]).unwrap();

        assert_eq!(forward, Some(ActionToken(2)));
        assert_eq!(forward, reversed);
    }

    #[test]
    fn nonempty_stack_prefers_pass_before_optional_actions() {
        let information = InformationState {
            stack: vec![urza_info::ObservedStackObject {
                kind: urza_info::ObservedStackKind::ActivatedAbility,
                card: None,
                source: None,
                target: None,
                ability: None,
                parameter: None,
            }],
            ..InformationState::default()
        };
        let policy = DeterministicPolicy;
        let mana = candidate(2, PolicyActionClass::ProduceMana, 10, 1);
        let spell = candidate(3, PolicyActionClass::CastSpell, 20, 2);
        let activation = candidate(4, PolicyActionClass::ActivateAbility, 30, 3);
        let pass = candidate(9, PolicyActionClass::PassPriority, 0, 0);

        let forward = policy
            .choose(
                &information,
                &[
                    mana.clone(),
                    spell.clone(),
                    activation.clone(),
                    pass.clone(),
                ],
            )
            .unwrap();
        let reversed = policy
            .choose(&information, &[pass, activation, spell, mana])
            .unwrap();

        assert_eq!(forward, Some(ActionToken(9)));
        assert_eq!(forward, reversed);
    }

    #[test]
    fn main_phase_spends_before_producing_more_mana() {
        let information = InformationState {
            phase: Phase::PrecombatMain,
            ..InformationState::default()
        };
        let policy = DeterministicPolicy;
        let mana = candidate(2, PolicyActionClass::ProduceMana, 10, 1);
        let spell = candidate(3, PolicyActionClass::CastSpell, 20, 2);
        let pass = candidate(9, PolicyActionClass::PassPriority, 0, 0);

        assert_eq!(
            policy.choose(&information, &[mana, spell, pass]).unwrap(),
            Some(ActionToken(3))
        );
    }

    #[test]
    fn main_phase_produces_mana_when_no_spend_action_is_legal() {
        let information = InformationState {
            phase: Phase::PrecombatMain,
            ..InformationState::default()
        };
        let policy = DeterministicPolicy;
        let mana = candidate(2, PolicyActionClass::ProduceMana, 10, 1);
        let pass = candidate(9, PolicyActionClass::PassPriority, 0, 0);

        assert_eq!(
            policy.choose(&information, &[mana, pass]).unwrap(),
            Some(ActionToken(2))
        );
    }

    #[test]
    fn upkeep_preserves_reusable_mana_source_when_no_spend_action_is_legal() {
        let information = InformationState {
            phase: Phase::Upkeep,
            ..InformationState::default()
        };
        let policy = DeterministicPolicy;
        let mana = candidate(2, PolicyActionClass::ProduceMana, 10, 1);
        let pass = candidate(9, PolicyActionClass::PassPriority, 0, 0);

        assert_eq!(
            policy.choose(&information, &[mana, pass]).unwrap(),
            Some(ActionToken(9))
        );
    }

    #[test]
    fn tutor_target_prefers_a_real_card_over_fail_to_find() {
        let information = InformationState {
            pending: ObservedPendingDecision::TutorTarget {
                source: ObservedSourceRef {
                    canonical_object: None,
                    card: CardDefId(44),
                },
            },
            ..InformationState::default()
        };
        let policy = DeterministicPolicy;
        let fail_to_find = PolicyCandidate::new(
            ActionToken(1),
            PolicyActionClass::ContingentDecision,
            PolicyPublicKey {
                kind: 28,
                card: None,
                ..PolicyPublicKey::default()
            },
        );
        let real_target = PolicyCandidate::new(
            ActionToken(9),
            PolicyActionClass::ContingentDecision,
            PolicyPublicKey {
                kind: 28,
                card: Some(CardDefId(79)),
                ..PolicyPublicKey::default()
            },
        );

        assert_eq!(
            policy
                .choose(&information, &[fail_to_find, real_target])
                .unwrap(),
            Some(ActionToken(9))
        );
    }

    #[test]
    fn tutor_target_can_fail_to_find_when_no_real_target_exists() {
        let information = InformationState {
            pending: ObservedPendingDecision::TutorTarget {
                source: ObservedSourceRef {
                    canonical_object: None,
                    card: CardDefId(44),
                },
            },
            ..InformationState::default()
        };
        let policy = DeterministicPolicy;
        let fail_to_find = PolicyCandidate::new(
            ActionToken(1),
            PolicyActionClass::ContingentDecision,
            PolicyPublicKey {
                kind: 28,
                card: None,
                ..PolicyPublicKey::default()
            },
        );

        assert_eq!(
            policy.choose(&information, &[fail_to_find]).unwrap(),
            Some(ActionToken(1))
        );
    }

    #[test]
    fn semantic_key_precedes_opaque_token_tie_break() {
        let information = InformationState::default();
        let policy = DeterministicPolicy;
        let lower_token_but_later_card = candidate(1, PolicyActionClass::CastSpell, 90, 1);
        let higher_token_but_earlier_card = candidate(9, PolicyActionClass::CastSpell, 10, 1);

        assert_eq!(
            policy
                .choose(
                    &information,
                    &[lower_token_but_later_card, higher_token_but_earlier_card]
                )
                .unwrap(),
            Some(ActionToken(9))
        );
    }

    #[test]
    fn variable_detail_is_part_of_public_semantic_identity() {
        let information = InformationState::default();
        let policy = DeterministicPolicy;
        let mut later = candidate(1, PolicyActionClass::CastSpell, 10, 0);
        later.key.detail = vec![1, 0, 0, 0, 0, 0];
        let mut earlier = candidate(9, PolicyActionClass::CastSpell, 10, 0);
        earlier.key.detail = vec![0, 0, 0, 0, 0, 1];

        assert_eq!(
            policy.choose(&information, &[later, earlier]).unwrap(),
            Some(ActionToken(9))
        );
    }

    #[test]
    fn pending_public_decision_cannot_be_skipped_by_ordinary_actions() {
        let information = InformationState {
            pending: ObservedPendingDecision::ProducerUntapChoice {
                source: ObservedSourceRef {
                    canonical_object: Some(CanonicalObjectId(4)),
                    card: CardDefId(32),
                },
            },
            ..InformationState::default()
        };
        let policy = DeterministicPolicy;
        let contingent = candidate(5, PolicyActionClass::ContingentDecision, 32, 4);
        let ordinary = candidate(1, PolicyActionClass::CastSpell, 2, 0);

        assert_eq!(
            policy
                .choose(&information, &[ordinary.clone(), contingent])
                .unwrap(),
            Some(ActionToken(5))
        );
        assert_eq!(
            policy.choose(&information, &[ordinary]),
            Err(PolicyError::MissingContingentCandidate)
        );
    }

    #[test]
    fn contingent_candidate_without_pending_decision_is_rejected() {
        let information = InformationState::default();
        let policy = DeterministicPolicy;
        let contingent = candidate(5, PolicyActionClass::ContingentDecision, 32, 4);

        assert_eq!(
            policy.choose(&information, &[contingent]),
            Err(PolicyError::ContingentCandidateWithoutPending)
        );
    }

    #[test]
    fn duplicate_execution_tokens_are_rejected() {
        let information = InformationState::default();
        let policy = DeterministicPolicy;
        let a = candidate(3, PolicyActionClass::CastSpell, 4, 1);
        let b = candidate(3, PolicyActionClass::ActivateAbility, 8, 2);

        assert_eq!(
            policy.choose(&information, &[a, b]),
            Err(PolicyError::DuplicateActionToken(ActionToken(3)))
        );
    }
}
