from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"{label} marker not found")
    return text.replace(old, new, 1)


policy = Path("rust/crates/urza-policy/src/lib.rs")
text = policy.read_text()
text = replace_once(
    text,
    "use std::collections::BTreeSet;\n",
    "use std::collections::{BTreeMap, BTreeSet};\n",
    "policy collections import",
)
text = replace_once(
    text,
    "use urza_info::{CanonicalObjectId, CardDefId, InformationState, PendingDecisionKind, Phase};\n",
    "use urza_info::{\n    AbilityId, CanonicalObjectId, CardDefId, InformationState, ObservedPendingDecision,\n    PendingDecisionKind, Phase,\n};\n",
    "policy information import",
)
marker = "fn validate_candidate_tokens(candidates: &[PolicyCandidate]) -> Result<(), PolicyError> {"
strategic = r'''
/// Explicit post-R7 policy namespace. The frozen R5 `DeterministicPolicy`
/// remains unchanged so historical rollout/cache identities do not silently
/// acquire strategic semantics.
pub const POST_R7_STRATEGIC_POLICY_VERSION: &str = "post_r7_strategic_value_v1";

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
        let selected = candidates
            .iter()
            .filter(|candidate| {
                !pending || candidate.class == PolicyActionClass::ContingentDecision
            })
            .min_by(|left, right| {
                self.action_bucket(information, left, drain_stack)
                    .cmp(&self.action_bucket(information, right, drain_stack))
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
            match candidate.class {
                PolicyActionClass::PlayLand => 0,
                PolicyActionClass::CastSpell | PolicyActionClass::ActivateAbility => 1,
                PolicyActionClass::ProduceMana => 2,
                PolicyActionClass::ManaSetup => 3,
                PolicyActionClass::PassPriority => 4,
                PolicyActionClass::ContingentDecision => 5,
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
            (PolicyActionClass::ActivateAbility, Some(card)) => i64::from(self.base_card_value(card)),
            _ => 0,
        };
        kind_value + card_value + self.stack_intervention_score(information, candidate)
    }

    fn contingent_score(
        &self,
        information: &InformationState,
        candidate: &PolicyCandidate,
        pending_kind: PendingDecisionKind,
    ) -> i64 {
        if is_search_target_pending(pending_kind) {
            return candidate
                .key
                .card
                .map_or(i64::MIN / 4, |card| self.acquisition_value(information, card));
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
        let delta = self.acquisition_value(information, top) - i64::from(self.config.unknown_card_value);
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
        if candidate.class != PolicyActionClass::ActivateAbility || information.library.known_top.len() >= 3 {
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
        present.extend(information.battlefield.iter().map(|permanent| permanent.card));
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

'''
text = replace_once(text, marker, strategic + marker, "strategic policy insertion")
policy.write_text(text)

rollout = Path("rust/crates/urza-rollout/src/lib.rs")
text = rollout.read_text()
text = replace_once(
    text,
    "use urza_policy::{\n    ActionToken, DeterministicPolicy, PolicyActionClass, PolicyError, PolicyPublicKey,\n};",
    "use urza_policy::{\n    ActionToken, DeterministicPolicy, PolicyActionClass, PolicyError, PolicyPublicKey, PolicySelector,\n};",
    "rollout policy import",
)
text = replace_once(
    text,
    'pub const ROLLOUT_VERSION: &str = "r5_deterministic_rollout_v3";\n',
    'pub const ROLLOUT_VERSION: &str = "r5_deterministic_rollout_v3";\npub const POST_R7_STRATEGIC_ROLLOUT_VERSION: &str = "post_r7_strategic_rollout_v1";\n',
    "rollout version",
)
rollout_marker = "pub fn rollout_with_logical_event_offset<D: CardDatabase>(\n"
generic_entry = '''/// Run the accepted rollout engine with an explicitly supplied public policy
/// selector. The historical `rollout` entrypoint remains pinned to
/// `DeterministicPolicy`.
pub fn rollout_with_selector<D: CardDatabase, P: PolicySelector>(
    initial: TrueState,
    cards: &D,
    policy: &P,
    config: RolloutConfig,
) -> Result<RolloutResult, RolloutError> {
    rollout_internal(initial, cards, policy, config, 0, &[])
}

'''
text = replace_once(text, rollout_marker, generic_entry + rollout_marker, "rollout selector insertion")
text = replace_once(
    text,
    "fn rollout_internal<D: CardDatabase>(\n    initial: TrueState,\n    cards: &D,\n    policy: &DeterministicPolicy,",
    "fn rollout_internal<D: CardDatabase, P: PolicySelector>(\n    initial: TrueState,\n    cards: &D,\n    policy: &P,",
    "rollout internal generic",
)
rollout.write_text(text)

liveness = Path("rust/crates/urza-rollout/src/liveness.rs")
text = liveness.read_text()
text = replace_once(
    text,
    "use urza_policy::{DeterministicPolicy, PolicyActionClass, PolicyPublicKey};",
    "use urza_policy::{PolicyActionClass, PolicyPublicKey, PolicySelector};",
    "liveness policy import",
)
text = replace_once(
    text,
    "pub(crate) fn cycle_stationary_through_budget<D: CardDatabase>(\n    initial: &TrueState,\n    cards: &D,\n    policy: &DeterministicPolicy,",
    "pub(crate) fn cycle_stationary_through_budget<D: CardDatabase, P: PolicySelector>(\n    initial: &TrueState,\n    cards: &D,\n    policy: &P,",
    "liveness generic",
)
liveness.write_text(text)

Path("rust/crates/urza-policy/tests").mkdir(parents=True, exist_ok=True)
Path("rust/crates/urza-policy/tests/strategic_value.rs").write_text(r'''use urza_info::{
    AbilityId, CanonicalObjectId, CardCount, CardDefId, CardFace, CounterState,
    InformationState, LibraryBelief, ObservedPendingDecision, ObservedPermanent,
    ObservedSourceRef, ObservedStackKind, ObservedStackObject, PermanentMode, Phase,
};
use urza_policy::{
    ActionToken, PolicyActionClass, PolicyCandidate, PolicyPublicKey, StrategicPolicy,
    StrategicPolicyConfig, TerminalRecipe,
};

const ASSISTANT: AbilityId = AbilityId(0x0413);
const UTHROS_DRAW: AbilityId = AbilityId(0x0411);

fn source(card: u16) -> ObservedSourceRef {
    ObservedSourceRef {
        canonical_object: None,
        card: CardDefId(card),
    }
}

fn candidate(token: u16, class: PolicyActionClass, kind: u16, card: Option<u16>) -> PolicyCandidate {
    PolicyCandidate::new(
        ActionToken(token),
        class,
        PolicyPublicKey {
            kind,
            card: card.map(CardDefId),
            ..PolicyPublicKey::default()
        },
    )
}

fn contingent(token: u16, detail: Vec<u16>, card: Option<u16>) -> PolicyCandidate {
    PolicyCandidate::new(
        ActionToken(token),
        PolicyActionClass::ContingentDecision,
        PolicyPublicKey {
            kind: 99,
            card: card.map(CardDefId),
            detail,
            ..PolicyPublicKey::default()
        },
    )
}

fn trigger(ability: AbilityId) -> ObservedStackObject {
    ObservedStackObject {
        kind: ObservedStackKind::ControlledTrigger,
        card: None,
        source: Some(source(7)),
        target: None,
        ability: Some(ability),
        parameter: None,
    }
}

fn permanent(card: u16, id: u16) -> ObservedPermanent {
    ObservedPermanent {
        canonical_id: CanonicalObjectId(id),
        card: CardDefId(card),
        face: CardFace::Front,
        tapped: false,
        summoning_sick: false,
        token: false,
        counters: CounterState::default(),
        mode: PermanentMode::Normal,
        attached_to: None,
        granted_ability: None,
    }
}

fn configured() -> StrategicPolicy {
    let mut config = StrategicPolicyConfig::default();
    config.card_values.insert(CardDefId(10), 120);
    config.card_values.insert(CardDefId(20), 110);
    config.card_values.insert(CardDefId(30), 0);
    config.assistant_scry_ability = Some(ASSISTANT);
    config.uthros_draw_ability = Some(UTHROS_DRAW);
    StrategicPolicy::new(config)
}

#[test]
fn tutor_chooses_terminal_completion_over_static_target_order() {
    let mut config = StrategicPolicyConfig::default();
    config.card_values.insert(CardDefId(10), 200);
    config.card_values.insert(CardDefId(20), 100);
    config
        .terminal_recipes
        .push(TerminalRecipe::new(vec![CardDefId(5), CardDefId(20)]));
    let policy = StrategicPolicy::new(config);
    let information = InformationState {
        hand: vec![CardDefId(5)],
        pending: ObservedPendingDecision::TutorTarget { source: source(80) },
        ..InformationState::default()
    };
    let flashy = contingent(1, Vec::new(), Some(10));
    let completion = contingent(9, Vec::new(), Some(20));
    let fail = contingent(0, Vec::new(), None);

    assert_eq!(
        policy
            .choose(&information, &[flashy, fail, completion])
            .unwrap(),
        Some(ActionToken(9))
    );
}

#[test]
fn scry_keeps_public_high_value_and_bottoms_public_low_value() {
    let policy = configured();
    let high_information = InformationState {
        pending: ObservedPendingDecision::ScryChoice {
            source: source(1),
            looked_at: vec![CardDefId(10)],
        },
        ..InformationState::default()
    };
    let keep_high = contingent(1, vec![1, 10, 0], None);
    let bottom_high = contingent(2, vec![0, 1, 10], None);
    assert_eq!(
        policy
            .choose(&high_information, &[bottom_high, keep_high])
            .unwrap(),
        Some(ActionToken(1))
    );

    let low_information = InformationState {
        pending: ObservedPendingDecision::ScryChoice {
            source: source(1),
            looked_at: vec![CardDefId(30)],
        },
        ..InformationState::default()
    };
    let keep_low = contingent(3, vec![1, 30, 0], None);
    let bottom_low = contingent(4, vec![0, 1, 30], None);
    assert_eq!(
        policy
            .choose(&low_information, &[keep_low, bottom_low])
            .unwrap(),
        Some(ActionToken(4))
    );
}

#[test]
fn top_reorder_places_best_observed_card_first() {
    let policy = configured();
    let information = InformationState {
        pending: ObservedPendingDecision::TopReorder {
            source: source(1),
            cards: vec![CardDefId(30), CardDefId(10), CardDefId(20)],
        },
        ..InformationState::default()
    };
    let bad_first = contingent(1, vec![30, 20, 10], None);
    let best_first = contingent(2, vec![10, 20, 30], None);
    assert_eq!(
        policy
            .choose(&information, &[bad_first, best_first])
            .unwrap(),
        Some(ActionToken(2))
    );
}

#[test]
fn trigger_order_draws_good_known_top_first_and_scries_bad_known_top_first() {
    let policy = configured();
    let base_stack = vec![trigger(ASSISTANT), trigger(UTHROS_DRAW)];
    let assistant_first = contingent(1, vec![0, 1], None);
    let uthros_first = contingent(2, vec![1, 0], None);

    let good = InformationState {
        library: LibraryBelief {
            known_top: vec![CardDefId(10)],
            ..LibraryBelief::default()
        },
        stack: base_stack.clone(),
        pending: ObservedPendingDecision::TriggerOrder {
            source: source(40),
            trigger_count: 2,
        },
        ..InformationState::default()
    };
    assert_eq!(
        policy
            .choose(&good, &[assistant_first.clone(), uthros_first.clone()])
            .unwrap(),
        Some(ActionToken(2))
    );

    let bad = InformationState {
        library: LibraryBelief {
            known_top: vec![CardDefId(30)],
            ..LibraryBelief::default()
        },
        stack: base_stack,
        pending: ObservedPendingDecision::TriggerOrder {
            source: source(40),
            trigger_count: 2,
        },
        ..InformationState::default()
    };
    assert_eq!(
        policy
            .choose(&bad, &[uthros_first, assistant_first])
            .unwrap(),
        Some(ActionToken(1))
    );
}

#[test]
fn unknown_library_multiset_cannot_change_trigger_order() {
    let policy = configured();
    let candidates = [
        contingent(1, vec![0, 1], None),
        contingent(2, vec![1, 0], None),
    ];
    let make = |remaining_counts| InformationState {
        library: LibraryBelief {
            remaining_counts,
            known_top: Vec::new(),
            known_bottom: Vec::new(),
        },
        stack: vec![trigger(ASSISTANT), trigger(UTHROS_DRAW)],
        pending: ObservedPendingDecision::TriggerOrder {
            source: source(40),
            trigger_count: 2,
        },
        ..InformationState::default()
    };
    let a = make(vec![CardCount {
        card: CardDefId(10),
        count: 1,
    }]);
    let b = make(vec![CardCount {
        card: CardDefId(30),
        count: 1,
    }]);
    assert_eq!(
        policy.choose(&a, &candidates).unwrap(),
        policy.choose(&b, &candidates).unwrap()
    );
}

#[test]
fn top_can_intervene_above_relevant_triggers_once_then_stack_drains() {
    let mut config = StrategicPolicyConfig::default();
    config.stack_intervention_kind_values.insert(15, 200);
    config
        .stack_intervention_trigger_abilities
        .insert(ASSISTANT);
    config
        .stack_intervention_trigger_abilities
        .insert(UTHROS_DRAW);
    let policy = StrategicPolicy::new(config);
    let pass = candidate(1, PolicyActionClass::PassPriority, 1, None);
    let top_look = candidate(2, PolicyActionClass::ActivateAbility, 15, Some(77));
    let information = InformationState {
        stack: vec![trigger(ASSISTANT), trigger(UTHROS_DRAW)],
        ..InformationState::default()
    };
    assert_eq!(
        policy
            .choose(&information, &[pass.clone(), top_look.clone()])
            .unwrap(),
        Some(ActionToken(2))
    );

    let already_known = InformationState {
        library: LibraryBelief {
            known_top: vec![CardDefId(10), CardDefId(20), CardDefId(30)],
            ..LibraryBelief::default()
        },
        stack: vec![trigger(ASSISTANT), trigger(UTHROS_DRAW)],
        ..InformationState::default()
    };
    assert_eq!(
        policy
            .choose(&already_known, &[top_look, pass])
            .unwrap(),
        Some(ActionToken(1))
    );
}

#[test]
fn engine_activation_value_competes_with_casts_inside_spend_bucket() {
    let mut config = StrategicPolicyConfig::default();
    config.card_values.insert(CardDefId(70), 100);
    config.action_kind_values.insert(35, 300);
    let policy = StrategicPolicy::new(config);
    let information = InformationState {
        phase: Phase::PrecombatMain,
        ..InformationState::default()
    };
    let cast = candidate(1, PolicyActionClass::CastSpell, 9, Some(60));
    let ring_draw = candidate(2, PolicyActionClass::ActivateAbility, 35, Some(70));
    assert_eq!(
        policy.choose(&information, &[cast, ring_draw]).unwrap(),
        Some(ActionToken(2))
    );
}

#[test]
fn cast_that_completes_public_terminal_recipe_beats_higher_base_card() {
    let mut config = StrategicPolicyConfig::default();
    config.card_values.insert(CardDefId(10), 100);
    config.card_values.insert(CardDefId(20), 220);
    config.card_values.insert(CardDefId(40), 90);
    config
        .terminal_recipes
        .push(TerminalRecipe::new(vec![CardDefId(10), CardDefId(40)]));
    let policy = StrategicPolicy::new(config);
    let information = InformationState {
        phase: Phase::PrecombatMain,
        battlefield: vec![permanent(10, 1)],
        ..InformationState::default()
    };
    let standalone = candidate(1, PolicyActionClass::CastSpell, 9, Some(20));
    let completion = candidate(2, PolicyActionClass::CastSpell, 9, Some(40));
    assert_eq!(
        policy
            .choose(&information, &[standalone, completion])
            .unwrap(),
        Some(ActionToken(2))
    );
}
''')

Path("rust/crates/urza-mulligan/src/bin/post-r7-strategic-value-smoke.rs").write_text(r'''use std::error::Error;
use std::io;

use urza_cards::CurrentCardDatabase;
use urza_mc::sample_hidden_world;
use urza_mulligan::{
    KeptHand, MulliganStage, bridge_kept_hand, draw_fresh_seven, load_commander_deck,
    r7_pilot_generation_config, sample_pregame_context,
};
use urza_policy::{
    DeterministicPolicy, StrategicPolicy, StrategicPolicyConfig, TerminalRecipe,
};
use urza_rng::WorldId;
use urza_rollout::{RolloutConfig, RolloutStop, rollout, rollout_with_selector};
use urza_rules::{ABILITY_ARTIFICERS_ASSISTANT_SCRY, ABILITY_UTHROS_ARTIFACT_DRAW};

const VERSION: &str = "post_r7_strategic_value_smoke_v1";
const KIND_TOP_LOOK: u16 = 15;
const KIND_TOP_DRAW: u16 = 16;
const KIND_REALITY_CHIP_RECONFIGURE: u16 = 19;
const KIND_FTT_LEVEL: u16 = 21;
const KIND_ONE_RING_DRAW: u16 = 35;
const KIND_UTHROS_STATION: u16 = 36;
const KIND_CLUE_DRAW: u16 = 37;
const KIND_TRIGGER_ORDER: u16 = 38;
const KIND_SEARCH_TARGET: u16 = 28;

fn main() {
    if let Err(error) = run() {
        eprintln!("post-R7 strategic value smoke failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn Error>> {
    let mut args = std::env::args().skip(1);
    let opening_offset = parse_u64(args.next(), "opening-offset")?;
    let hidden_start = parse_u64(args.next(), "hidden-start")?;
    let hidden_count = parse_u64(args.next(), "hidden-count")?;
    if args.next().is_some() || hidden_count == 0 {
        return Err(Box::new(io::Error::other(
            "usage: post-r7-strategic-value-smoke <opening-offset> <hidden-start> <hidden-count>",
        )));
    }

    let generation = r7_pilot_generation_config();
    let deck = load_commander_deck()?;
    let cards = CurrentCardDatabase::load()?;
    let policy = strategic_policy(&cards)?;
    let opening_world = WorldId(
        generation
            .first_world
            .0
            .checked_add(opening_offset)
            .ok_or_else(|| io::Error::other("opening world overflow"))?,
    );
    let stage = MulliganStage::InitialSeven;
    let hand = draw_fresh_seven(&deck, generation.opening_root, opening_world, stage);
    let kept = KeptHand {
        stage,
        hand,
        known_bottom: Vec::new(),
        pregame: sample_pregame_context(generation.opening_root, opening_world),
    };
    let opening = bridge_kept_hand(&kept, &deck, generation.opening_root, opening_world)?;

    let mut baseline_terminals = 0_u64;
    let mut strategic_terminals = 0_u64;
    let mut strategic_decisions = 0_u64;
    let mut top_looks = 0_u64;
    let mut tutor_targets = 0_u64;
    let mut trigger_orders = 0_u64;

    for hidden_offset in 0..hidden_count {
        let hidden_world = WorldId(
            hidden_start
                .checked_add(hidden_offset)
                .ok_or_else(|| io::Error::other("hidden world overflow"))?,
        );
        let config = RolloutConfig {
            root: generation.evaluation.rollout.root,
            world: hidden_world,
            max_steps: generation.evaluation.rollout.rollout_max_steps,
        };
        let exact = sample_hidden_world(opening.true_state(), config.root, hidden_world)?;
        let baseline = rollout(exact.clone(), &cards, &DeterministicPolicy, config)?;
        if matches!(baseline.stop, RolloutStop::StepLimit | RolloutStop::NoCandidate) {
            return Err(Box::new(io::Error::other(format!(
                "baseline hidden world {} stopped incompletely at {:?}",
                hidden_world.0, baseline.stop
            ))));
        }
        baseline_terminals += u64::from(matches!(baseline.stop, RolloutStop::Terminal(_)));

        let strategic = rollout_with_selector(exact, &cards, &policy, config)?;
        if matches!(strategic.stop, RolloutStop::StepLimit | RolloutStop::NoCandidate) {
            return Err(Box::new(io::Error::other(format!(
                "strategic hidden world {} stopped incompletely at {:?}",
                hidden_world.0, strategic.stop
            ))));
        }
        strategic_terminals += u64::from(matches!(strategic.stop, RolloutStop::Terminal(_)));
        strategic_decisions = strategic_decisions
            .saturating_add(u64::try_from(strategic.trace.len()).unwrap_or(u64::MAX));
        for step in strategic.trace {
            top_looks += u64::from(step.key.kind == KIND_TOP_LOOK);
            tutor_targets +=
                u64::from(step.key.kind == KIND_SEARCH_TARGET && step.key.card.is_some());
            trigger_orders += u64::from(step.key.kind == KIND_TRIGGER_ORDER);
        }
    }

    println!("STRATEGIC_VALUE_SMOKE\t{VERSION}");
    println!(
        "SUMMARY\topening={}\tworlds={}\tbaseline_terminals={}\tstrategic_terminals={}\tstrategic_decisions={}\ttop_looks={}\ttutor_targets={}\ttrigger_orders={}",
        opening_offset,
        hidden_count,
        baseline_terminals,
        strategic_terminals,
        strategic_decisions,
        top_looks,
        tutor_targets,
        trigger_orders,
    );
    Ok(())
}

fn strategic_policy(cards: &CurrentCardDatabase) -> Result<StrategicPolicy, Box<dyn Error>> {
    let mut config = StrategicPolicyConfig::default();
    for (name, value) in [
        ("Sensei's Divining Top", 130),
        ("The Reality Chip", 125),
        ("Fortune Teller's Talent", 120),
        ("Forensic Gadgeteer", 120),
        ("The One Ring", 115),
        ("Uthros Research Craft", 110),
        ("Power Artifact", 135),
        ("Basalt Monolith", 130),
        ("Grim Monolith", 125),
        ("Grinding Station", 115),
        ("Battered Golem", 105),
        ("Chrome Dome", 100),
        ("Mana Vault", 100),
        ("Banishing Knack", 105),
        ("Retraction Helix", 105),
        ("Sewer-veillance Cam", 100),
        ("Spellseeker", 90),
        ("Merchant Scroll", 90),
        ("Mystical Tutor", 95),
        ("Whir of Invention", 105),
        ("Reshape", 105),
        ("Transmute Artifact", 115),
        ("Repurposing Bay", 100),
        ("Urza's Saga", 105),
        ("Tezzeret, Cruel Captain", 100),
    ] {
        config.card_values.insert(cards.card_id_by_name(name)?, value);
    }

    config.action_kind_values.extend([
        (KIND_TOP_LOOK, 70),
        (KIND_TOP_DRAW, 110),
        (KIND_REALITY_CHIP_RECONFIGURE, 100),
        (KIND_FTT_LEVEL, 90),
        (KIND_ONE_RING_DRAW, 140),
        (KIND_UTHROS_STATION, 60),
        (KIND_CLUE_DRAW, 45),
    ]);
    config
        .stack_intervention_kind_values
        .insert(KIND_TOP_LOOK, 220);
    config
        .stack_intervention_trigger_abilities
        .extend([ABILITY_ARTIFICERS_ASSISTANT_SCRY, ABILITY_UTHROS_ARTIFACT_DRAW]);
    config.assistant_scry_ability = Some(ABILITY_ARTIFICERS_ASSISTANT_SCRY);
    config.uthros_draw_ability = Some(ABILITY_UTHROS_ARTIFACT_DRAW);

    for names in [
        vec!["Power Artifact", "Basalt Monolith"],
        vec!["Power Artifact", "Grim Monolith"],
        vec!["Sensei's Divining Top", "The Reality Chip"],
        vec!["Sensei's Divining Top", "Fortune Teller's Talent"],
        vec![
            "Sensei's Divining Top",
            "Forensic Gadgeteer",
            "Grinding Station",
        ],
        vec![
            "Sensei's Divining Top",
            "Forensic Gadgeteer",
            "Battered Golem",
        ],
        vec!["Banishing Knack", "Battered Golem", "Sewer-veillance Cam"],
        vec!["Retraction Helix", "Battered Golem", "Sewer-veillance Cam"],
    ] {
        let required = names
            .into_iter()
            .map(|name| cards.card_id_by_name(name))
            .collect::<Result<Vec<_>, _>>()?;
        config.terminal_recipes.push(TerminalRecipe::new(required));
    }

    Ok(StrategicPolicy::new(config))
}

fn parse_u64(value: Option<String>, name: &str) -> Result<u64, Box<dyn Error>> {
    value
        .ok_or_else(|| io::Error::other(format!("missing {name}")))?
        .parse::<u64>()
        .map_err(|error| Box::new(error) as Box<dyn Error>)
}
''')

Path("rust/POST_R7_STRATEGIC_VALUE_POLICY.md").write_text('''# Post-R7 strategic value policy

## Status

**IMPLEMENTATION CANDIDATE — acceptance requires green policy/rollout gate and 128-world smoke.**

This slice returns from the closed card-text/mechanics validation to the policy/value boundary. It does not change the frozen R5 deterministic selector or its cache/rollout identity. Instead it adds an explicitly versioned `StrategicPolicy` consuming only `InformationState` plus public candidate metadata.

## Value surface

The first strategic layer covers four deliberately narrow concerns:

- **engine value**: public cast/activation candidates can receive explicit values, so intrinsic engines such as Top, Ring, Reality Chip, FTT and Uthros are no longer selected only by structural card/action ordering;
- **tutor value**: legal real targets are ranked by public card value plus progress toward configured terminal recipes; fail-to-find remains below every legal real target;
- **library-selection value**: scry and Top reorder choices score only cards that have actually been observed, while unknown cards receive one anonymous baseline value;
- **terminal-precursor value**: public hand/battlefield progress toward explicit recipes receives a completion/proximity bonus without asserting a terminal win before the rules detector does.

Assistant/Uthros trigger ordering uses the already-public controlled-trigger block. With a known valuable top card the policy prefers Uthros first; with a known poor top card it prefers Assistant first. When the top is unknown, trigger order falls back deterministically and cannot inspect the unknown library multiset. A configured Top-look action may intervene above Assistant/Uthros triggers only while fewer than three top cards are already known; after Top resolves, normal stack draining resumes.

## Boundaries

- No `TrueState` or hidden library order is visible to policy.
- No Python gameplay or policy implementation is ported.
- Rhystic Study, Mystic Remora and Faerie Mastermind receive no fabricated opponent-event draw value; the environment-deferred boundary remains intact.
- Terminal recipes are precursor heuristics only. `detect_terminal_win` remains the sole terminal authority.
- The historical `DeterministicPolicy`, `POLICY_VERSION`, and `rollout` entrypoint are unchanged. The new selector uses `POST_R7_STRATEGIC_POLICY_VERSION` and `POST_R7_STRATEGIC_ROLLOUT_VERSION`.
''')

log = Path("rust/DEVELOPMENT_LOG.md")
log.write_text(
    log.read_text()
    + '''\n\n## 2026-09-07 — Post-R7 strategic value policy candidate\n\nClassification: `POLICY/VALUE`. No rules/card broadening and no Python gameplay-policy port.\n\nAdded an explicitly versioned public-information `StrategicPolicy` while preserving the frozen R5 `DeterministicPolicy` and historical rollout/cache identity. The new value layer ranks real tutor targets, observed scry/Top choices, Assistant/Uthros trigger order, intrinsic engine actions, and public terminal-precursor progress. Unknown library cards retain one anonymous value and cannot be identity-scored. Rollout now has a generic selector entrypoint; the existing `rollout` API remains deterministic-R5 compatible. Acceptance is contingent on the dedicated policy/rollout tests and 128-world strategic smoke.\n'''
)
