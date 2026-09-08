#![forbid(unsafe_code)]

use std::collections::{BTreeMap, BTreeSet};

use thiserror::Error;
use urza_info::{
    AbilityId, CanonicalObjectId, CardDefId, InformationState, ObservedPendingDecision,
    PendingDecisionKind, Phase,
};

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

/// Explicit post-R7 policy namespace. The frozen R5 `DeterministicPolicy`
/// remains unchanged so historical rollout/cache identities do not silently
/// acquire strategic semantics.
pub const POST_R7_STRATEGIC_POLICY_VERSION: &str = "post_r7_strategic_value_v3_library_information";

/// Common selector contract used by rollout. Implementations receive only the
/// public `InformationState` and bridge-produced public candidates.
pub trait PolicySelector {
    fn choose(
        &self,
        information: &InformationState,
        candidates: &[PolicyCandidate],
    ) -> Result<Option<ActionToken>, PolicyError>;
}

impl PolicySelector for DeterministicPolicy {
    fn choose(
        &self,
        information: &InformationState,
        candidates: &[PolicyCandidate],
    ) -> Result<Option<ActionToken>, PolicyError> {
        DeterministicPolicy::choose(self, information, candidates)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TerminalRecipe {
    required: Vec<CardDefId>,
}

impl TerminalRecipe {
    pub fn new(mut required: Vec<CardDefId>) -> Self {
        required.sort_unstable();
        required.dedup();
        Self { required }
    }

    pub fn required(&self) -> &[CardDefId] {
        &self.required
    }
}

/// Public, caller-supplied strategic metadata. Card identities and bridge kind
/// codes are public catalog/bridge facts; no execution object IDs or hidden
/// library order enter this configuration.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StrategicPolicyConfig {
    pub default_card_value: i32,
    pub unknown_card_value: i32,
    pub card_values: BTreeMap<CardDefId, i32>,
    pub action_kind_values: BTreeMap<u16, i32>,
    pub stack_intervention_kind_values: BTreeMap<u16, i32>,
    pub stack_intervention_trigger_abilities: BTreeSet<AbilityId>,
    pub terminal_recipes: Vec<TerminalRecipe>,
    pub assistant_scry_ability: Option<AbilityId>,
    pub uthros_draw_ability: Option<AbilityId>,
    pub library_look_kind: Option<u16>,
}

impl Default for StrategicPolicyConfig {
    fn default() -> Self {
        Self {
            default_card_value: 50,
            unknown_card_value: 50,
            card_values: BTreeMap::new(),
            action_kind_values: BTreeMap::new(),
            stack_intervention_kind_values: BTreeMap::new(),
            stack_intervention_trigger_abilities: BTreeSet::new(),
            terminal_recipes: Vec::new(),
            assistant_scry_ability: None,
            uthros_draw_ability: None,
            library_look_kind: None,
        }
    }
}

/// Information-faithful post-R7 selector for engine, tutor, library-selection,
/// and terminal-precursor choices.
///
/// This is deliberately a compact deterministic value layer, not a Python
/// gameplay-policy port. Unknown cards receive only `unknown_card_value`;
/// identities are scored only after they are public in hand/battlefield,
/// observed by scry/Top, or exposed as legal tutor candidates.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StrategicPolicy {
    config: StrategicPolicyConfig,
}

impl StrategicPolicy {
    pub fn new(config: StrategicPolicyConfig) -> Self {
        Self { config }
    }

    pub fn config(&self) -> &StrategicPolicyConfig {
        &self.config
    }

    pub fn choose(
        &self,
        information: &InformationState,
        candidates: &[PolicyCandidate],
    ) -> Result<Option<ActionToken>, PolicyError> {
        validate_candidate_tokens(candidates)?;

        let pending_kind = information.pending.kind();
        let pending = pending_kind != PendingDecisionKind::None;
        let has_contingent = candidates
            .iter()
            .any(|candidate| candidate.class == PolicyActionClass::ContingentDecision);
        if pending && !has_contingent {
            return Err(PolicyError::MissingContingentCandidate);
        }
        if !pending && has_contingent {
            return Err(PolicyError::ContingentCandidateWithoutPending);
        }

        let drain_stack = !pending && !information.stack.is_empty();
        let protected_activation_sources = candidates
            .iter()
            .filter(|candidate| {
                candidate.class == PolicyActionClass::ActivateAbility
                    && self.activation_is_live(information, candidate)
            })
            .filter_map(|candidate| candidate.key.source)
            .collect::<BTreeSet<_>>();
        let selected = candidates
            .iter()
            .filter(|candidate| {
                !pending || candidate.class == PolicyActionClass::ContingentDecision
            })
            .min_by(|left, right| {
                self.action_bucket(
                    information,
                    left,
                    drain_stack,
                    &protected_activation_sources,
                )
                .cmp(&self.action_bucket(
                    information,
                    right,
                    drain_stack,
                    &protected_activation_sources,
                ))
                .then_with(|| {
                    self.candidate_score(information, right)
                        .cmp(&self.candidate_score(information, left))
                })
                .then_with(|| left.key.cmp(&right.key))
                .then_with(|| left.token.cmp(&right.token))
            });

        Ok(selected.map(|candidate| candidate.token))
    }

    fn action_bucket(
        &self,
        information: &InformationState,
        candidate: &PolicyCandidate,
        drain_stack: bool,
        protected_activation_sources: &BTreeSet<CanonicalObjectId>,
    ) -> u8 {
        if information.pending.kind() != PendingDecisionKind::None {
            return 0;
        }
        if drain_stack {
            if self.stack_intervention_score(information, candidate) > 0 {
                return 0;
            }
            return match candidate.class {
                PolicyActionClass::PassPriority => 1,
                PolicyActionClass::ActivateAbility => 2,
                PolicyActionClass::CastSpell => 3,
                PolicyActionClass::PlayLand => 4,
                PolicyActionClass::ProduceMana => 5,
                PolicyActionClass::ManaSetup => 6,
                PolicyActionClass::ContingentDecision => 7,
            };
        }

        if matches!(information.phase, Phase::PrecombatMain) {
            if self.is_redundant_library_look(information, candidate) {
                return 7;
            }
            match candidate.class {
                PolicyActionClass::PlayLand => 0,
                PolicyActionClass::ProduceMana
                    if !candidate
                        .key
                        .source
                        .is_some_and(|source| protected_activation_sources.contains(&source)) =>
                {
                    1
                }
                PolicyActionClass::CastSpell | PolicyActionClass::ActivateAbility => 2,
                PolicyActionClass::ManaSetup => 3,
                PolicyActionClass::ProduceMana => 4,
                PolicyActionClass::PassPriority => 5,
                PolicyActionClass::ContingentDecision => 6,
            }
        } else {
            match candidate.class {
                PolicyActionClass::PlayLand => 0,
                PolicyActionClass::CastSpell | PolicyActionClass::ActivateAbility => 1,
                PolicyActionClass::PassPriority => 2,
                PolicyActionClass::ProduceMana => 3,
                PolicyActionClass::ManaSetup => 4,
                PolicyActionClass::ContingentDecision => 5,
            }
        }
    }

    fn activation_is_live(
        &self,
        information: &InformationState,
        candidate: &PolicyCandidate,
    ) -> bool {
        candidate.class == PolicyActionClass::ActivateAbility
            && !self.is_redundant_library_look(information, candidate)
            && (self
                .config
                .action_kind_values
                .get(&candidate.key.kind)
                .copied()
                .unwrap_or_default()
                > 0
                || self.stack_intervention_score(information, candidate) > 0)
    }

    fn is_redundant_library_look(
        &self,
        information: &InformationState,
        candidate: &PolicyCandidate,
    ) -> bool {
        candidate.class == PolicyActionClass::ActivateAbility
            && Some(candidate.key.kind) == self.config.library_look_kind
            && information.library.known_top.len() >= 3
    }

    fn candidate_score(&self, information: &InformationState, candidate: &PolicyCandidate) -> i64 {
        let pending_kind = information.pending.kind();
        if pending_kind != PendingDecisionKind::None {
            return self.contingent_score(information, candidate, pending_kind);
        }

        let kind_value = i64::from(
            self.config
                .action_kind_values
                .get(&candidate.key.kind)
                .copied()
                .unwrap_or_default(),
        );
        let card_value = match (candidate.class, candidate.key.card) {
            (PolicyActionClass::CastSpell, Some(card)) => self.deployment_value(information, card),
            (PolicyActionClass::ActivateAbility, Some(card)) => {
                i64::from(self.base_card_value(card))
            }
            _ => 0,
        };
        let library_information_value = if candidate.class == PolicyActionClass::ActivateAbility
            && Some(candidate.key.kind) == self.config.library_look_kind
            && information.library.known_top.len() < 3
        {
            i64::from(self.config.unknown_card_value).saturating_mul(3)
        } else {
            0
        };
        kind_value
            + card_value
            + library_information_value
            + self.stack_intervention_score(information, candidate)
    }

    fn contingent_score(
        &self,
        information: &InformationState,
        candidate: &PolicyCandidate,
        pending_kind: PendingDecisionKind,
    ) -> i64 {
        if is_search_target_pending(pending_kind) {
            return candidate.key.card.map_or(i64::MIN / 4, |card| {
                self.acquisition_value(information, card)
            });
        }

        match &information.pending {
            ObservedPendingDecision::ScryChoice { .. } => {
                self.scry_choice_value(information, &candidate.key.detail)
            }
            ObservedPendingDecision::TopReorder { .. } => {
                self.top_order_value(information, &candidate.key.detail)
            }
            ObservedPendingDecision::TriggerOrder { trigger_count, .. } => {
                self.trigger_order_value(information, *trigger_count, &candidate.key.detail)
            }
            _ => candidate
                .key
                .card
                .map_or(0, |card| self.acquisition_value(information, card)),
        }
    }

    fn scry_choice_value(&self, information: &InformationState, detail: &[u16]) -> i64 {
        let Some((&top_len, rest)) = detail.split_first() else {
            return 0;
        };
        let top_len = usize::from(top_len);
        if top_len > rest.len() {
            return 0;
        }
        if top_len == 0 {
            return i64::from(self.config.unknown_card_value) * 100;
        }
        let card = CardDefId(rest[0]);
        let value = self.acquisition_value(information, card);
        let keep_observed_tie_break = i64::from(value >= i64::from(self.config.unknown_card_value));
        value * 100 + keep_observed_tie_break
    }

    fn top_order_value(&self, information: &InformationState, detail: &[u16]) -> i64 {
        detail
            .iter()
            .take(8)
            .enumerate()
            .map(|(index, card)| {
                let shift = 7_u32.saturating_sub(u32::try_from(index).unwrap_or(7));
                self.acquisition_value(information, CardDefId(*card)) * (1_i64 << shift)
            })
            .sum()
    }

    fn trigger_order_value(
        &self,
        information: &InformationState,
        trigger_count: u8,
        detail: &[u16],
    ) -> i64 {
        let count = usize::from(trigger_count);
        if count == 0 || detail.len() != count || information.stack.len() < count {
            return 0;
        }
        let Some(first_index) = detail.first().map(|index| usize::from(*index)) else {
            return 0;
        };
        if first_index >= count {
            return 0;
        }
        let block = &information.stack[information.stack.len() - count..];
        let first_ability = block[first_index].ability;
        let Some(top) = information.library.known_top.first().copied() else {
            return 0;
        };
        let delta =
            self.acquisition_value(information, top) - i64::from(self.config.unknown_card_value);
        if delta > 0 && first_ability == self.config.uthros_draw_ability {
            10_000 + delta
        } else if delta < 0 && first_ability == self.config.assistant_scry_ability {
            10_000 - delta
        } else {
            0
        }
    }

    fn stack_intervention_score(
        &self,
        information: &InformationState,
        candidate: &PolicyCandidate,
    ) -> i64 {
        if candidate.class != PolicyActionClass::ActivateAbility
            || information.library.known_top.len() >= 3
        {
            return 0;
        }
        let Some(value) = self
            .config
            .stack_intervention_kind_values
            .get(&candidate.key.kind)
            .copied()
        else {
            return 0;
        };
        let relevant_trigger = information.stack.iter().any(|object| {
            object.ability.is_some_and(|ability| {
                self.config
                    .stack_intervention_trigger_abilities
                    .contains(&ability)
            })
        });
        i64::from(value) * i64::from(relevant_trigger)
    }

    fn acquisition_value(&self, information: &InformationState, card: CardDefId) -> i64 {
        let mut present = BTreeSet::new();
        present.extend(information.hand.iter().copied());
        present.extend(
            information
                .battlefield
                .iter()
                .map(|permanent| permanent.card),
        );
        let base = i64::from(self.base_card_value(card));
        if present.contains(&card) {
            return base.saturating_sub(20);
        }
        base + self.recipe_gain(card, &present)
    }

    fn deployment_value(&self, information: &InformationState, card: CardDefId) -> i64 {
        let present = information
            .battlefield
            .iter()
            .map(|permanent| permanent.card)
            .collect::<BTreeSet<_>>();
        i64::from(self.base_card_value(card)) + self.recipe_gain(card, &present)
    }

    fn recipe_gain(&self, card: CardDefId, present: &BTreeSet<CardDefId>) -> i64 {
        self.config
            .terminal_recipes
            .iter()
            .filter(|recipe| recipe.required.contains(&card) && !present.contains(&card))
            .map(|recipe| {
                let missing = recipe
                    .required
                    .iter()
                    .filter(|required| !present.contains(required))
                    .count();
                match missing {
                    0 => 0,
                    1 => 1_200,
                    2 => 300,
                    _ => 80,
                }
            })
            .max()
            .unwrap_or_default()
    }

    fn base_card_value(&self, card: CardDefId) -> i32 {
        self.config
            .card_values
            .get(&card)
            .copied()
            .unwrap_or(self.config.default_card_value)
    }
}

impl PolicySelector for StrategicPolicy {
    fn choose(
        &self,
        information: &InformationState,
        candidates: &[PolicyCandidate],
    ) -> Result<Option<ActionToken>, PolicyError> {
        StrategicPolicy::choose(self, information, candidates)
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
