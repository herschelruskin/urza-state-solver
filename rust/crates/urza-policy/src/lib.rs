#![forbid(unsafe_code)]

use std::collections::BTreeSet;

use thiserror::Error;
use urza_info::{CanonicalObjectId, CardDefId, InformationState, PendingDecisionKind};

/// R5 begins the deterministic policy layer on top of the frozen R4
/// rules/information/value contract.
pub const POLICY_PHASE: &str = "R5";
pub const POLICY_VERSION: &str = "r5_deterministic_start_v1";

/// Opaque decision-local handle supplied by the execution bridge.
///
/// The token is deliberately not part of the semantic policy key. It is used
/// only as a final deterministic tie-break between otherwise equivalent public
/// candidates and to map the selected public choice back to an execution
/// action outside this crate.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct ActionToken(pub u16);

/// Coarse public action class used by the baseline deterministic R5 selector.
///
/// This is POLICY metadata, not rules legality. The rules/execution bridge is
/// responsible for supplying only legal candidates and for classifying mana
/// abilities separately from other activated abilities.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum PolicyActionClass {
    ContingentDecision,
    PlayLand,
    ProduceMana,
    CastSpell,
    ActivateAbility,
    PassPriority,
}

/// Stable, policy-visible semantic key for deterministic tie-breaking.
///
/// Every field is public information. Canonical object identifiers are
/// structural observation identifiers from `urza-info`, never execution
/// `ObjectId`s. Additional action-specific public distinctions can be encoded
/// in `parameter` and `secondary` without exposing hidden state.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct PolicyPublicKey {
    pub card: Option<CardDefId>,
    pub source: Option<CanonicalObjectId>,
    pub target: Option<CanonicalObjectId>,
    pub parameter: Option<u16>,
    pub secondary: u16,
}

/// One legal, policy-visible candidate supplied by the execution bridge.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct PolicyCandidate {
    pub token: ActionToken,
    pub class: PolicyActionClass,
    pub key: PolicyPublicKey,
}

impl PolicyCandidate {
    pub const fn new(
        token: ActionToken,
        class: PolicyActionClass,
        key: PolicyPublicKey,
    ) -> Self {
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

/// Deterministic R5-start selector.
///
/// This is intentionally a small policy kernel rather than the final rollout
/// strategy. It guarantees deterministic selection from public information,
/// prevents ordinary actions from skipping a pending rules decision, and uses
/// a stable semantic order independent of candidate enumeration order.
#[derive(Debug, Clone, Copy, Default)]
pub struct DeterministicPolicy;

impl DeterministicPolicy {
    pub fn choose(
        &self,
        information: &InformationState,
        candidates: &[PolicyCandidate],
    ) -> Result<Option<ActionToken>, PolicyError> {
        validate_candidate_tokens(candidates)?;

        let pending = information.pending.kind() != PendingDecisionKind::None;
        let has_contingent = candidates
            .iter()
            .any(|candidate| candidate.class == PolicyActionClass::ContingentDecision);

        if pending && !has_contingent {
            return Err(PolicyError::MissingContingentCandidate);
        }
        if !pending && has_contingent {
            return Err(PolicyError::ContingentCandidateWithoutPending);
        }

        let selected = candidates
            .iter()
            .filter(|candidate| !pending || candidate.class == PolicyActionClass::ContingentDecision)
            .min_by_key(|candidate| semantic_rank(**candidate));

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

fn semantic_rank(candidate: PolicyCandidate) -> (u8, PolicyPublicKey, ActionToken) {
    (
        class_rank(candidate.class),
        candidate.key,
        candidate.token,
    )
}

const fn class_rank(class: PolicyActionClass) -> u8 {
    match class {
        PolicyActionClass::ContingentDecision => 0,
        PolicyActionClass::PlayLand => 1,
        PolicyActionClass::ProduceMana => 2,
        PolicyActionClass::CastSpell => 3,
        PolicyActionClass::ActivateAbility => 4,
        PolicyActionClass::PassPriority => 5,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use urza_info::{ObservedPendingDecision, ObservedSourceRef};

    fn candidate(
        token: u16,
        class: PolicyActionClass,
        card: u16,
        source: u16,
    ) -> PolicyCandidate {
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

        let forward = policy.choose(&information, &[a, b, c]).unwrap();
        let reversed = policy.choose(&information, &[c, b, a]).unwrap();

        assert_eq!(forward, Some(ActionToken(2)));
        assert_eq!(forward, reversed);
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
    fn pending_public_decision_cannot_be_skipped_by_ordinary_actions() {
        let mut information = InformationState::default();
        information.pending = ObservedPendingDecision::ProducerUntapChoice {
            source: ObservedSourceRef {
                canonical_object: Some(CanonicalObjectId(4)),
                card: CardDefId(32),
            },
        };
        let policy = DeterministicPolicy;
        let contingent = candidate(5, PolicyActionClass::ContingentDecision, 32, 4);
        let ordinary = candidate(1, PolicyActionClass::CastSpell, 2, 0);

        assert_eq!(
            policy.choose(&information, &[ordinary, contingent]).unwrap(),
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
