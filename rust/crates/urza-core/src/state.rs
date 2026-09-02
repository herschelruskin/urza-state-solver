use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Deserializer, Serialize};
use thiserror::Error;

use crate::{AbilityId, CardDefId, ObjectId, PermissionId};

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Phase {
    #[default]
    Untap,
    Upkeep,
    Draw,
    PrecombatMain,
    EndStep,
    OpponentCycle,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Window {
    #[default]
    None,
    Priority,
    Resolving,
    PostObservation,
    UpkeepDecision,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct ManaPool {
    pub white: u16,
    pub blue: u16,
    pub black: u16,
    pub red: u16,
    pub green: u16,
    pub colorless: u16,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[repr(transparent)]
pub struct GenericCost(pub u16);

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct CounterState {
    pub plus_one_plus_one: u16,
    pub charge: u16,
    pub burden: u16,
    pub lore: u16,
    pub age: u16,
    pub loyalty: i16,
    pub luck: u8,
}

#[derive(
    Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize,
)]
pub enum CardFace {
    #[default]
    Front,
    Back,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum PermanentMode {
    #[default]
    Normal,
    RealityChipCreature,
    RealityChipAttached,
    FortuneTellersTalentLevel1,
    FortuneTellersTalentLevel2,
    FortuneTellersTalentLevel3,
    UthrosStation,
    UthrosCreature,
    UrzasSaga,
    Other(u8),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum GrantedAbility {
    KnackBounceUntilEndOfTurn,
    SagaColorlessMana,
}

/// Canonicalized storage for zones whose physical card order is not game state.
#[derive(Debug, Clone, Default, PartialEq, Eq, Hash, Serialize)]
pub struct CardZone(Vec<CardDefId>);

impl CardZone {
    pub fn new(mut cards: Vec<CardDefId>) -> Self {
        cards.sort_unstable();
        Self(cards)
    }

    pub fn cards(&self) -> &[CardDefId] {
        &self.0
    }

    pub fn len(&self) -> usize {
        self.0.len()
    }

    pub fn is_empty(&self) -> bool {
        self.0.is_empty()
    }

    pub fn count(&self, card: CardDefId) -> usize {
        self.0
            .equal_range_by(|probe| probe.cmp(&card))
            .map_or(0, |range| range.end - range.start)
    }

    pub fn insert(&mut self, card: CardDefId) {
        let index = self.0.partition_point(|probe| *probe <= card);
        self.0.insert(index, card);
    }

    pub fn remove_one(&mut self, card: CardDefId) -> bool {
        if let Ok(index) = self.0.binary_search(&card) {
            self.0.remove(index);
            true
        } else {
            false
        }
    }
}

impl From<Vec<CardDefId>> for CardZone {
    fn from(cards: Vec<CardDefId>) -> Self {
        Self::new(cards)
    }
}

impl<'de> Deserialize<'de> for CardZone {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        Vec::<CardDefId>::deserialize(deserializer).map(Self::new)
    }
}

trait EqualRangeBy<T> {
    fn equal_range_by<F>(&self, compare: F) -> Option<std::ops::Range<usize>>
    where
        F: FnMut(&T) -> std::cmp::Ordering;
}

impl<T> EqualRangeBy<T> for [T] {
    fn equal_range_by<F>(&self, mut compare: F) -> Option<std::ops::Range<usize>>
    where
        F: FnMut(&T) -> std::cmp::Ordering,
    {
        let first = self.partition_point(|item| compare(item).is_lt());
        if first == self.len() || !compare(&self[first]).is_eq() {
            return None;
        }
        let width = self[first..].partition_point(|item| !compare(item).is_gt());
        Some(first..first + width)
    }
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct LibraryKnowledge {
    pub known_top: u8,
    pub known_bottom: u8,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct TrueLibrary {
    cards: Vec<CardDefId>,
    knowledge: LibraryKnowledge,
}

impl TrueLibrary {
    pub fn new(
        cards: Vec<CardDefId>,
        knowledge: LibraryKnowledge,
    ) -> Result<Self, StateValidationError> {
        let library = Self { cards, knowledge };
        library.validate()?;
        Ok(library)
    }

    pub fn unknown(cards: Vec<CardDefId>) -> Self {
        Self {
            cards,
            knowledge: LibraryKnowledge::default(),
        }
    }

    pub fn cards(&self) -> &[CardDefId] {
        &self.cards
    }

    pub fn cards_mut(&mut self) -> &mut [CardDefId] {
        &mut self.cards
    }

    pub fn knowledge(&self) -> LibraryKnowledge {
        self.knowledge
    }

    pub fn set_knowledge(
        &mut self,
        knowledge: LibraryKnowledge,
    ) -> Result<(), StateValidationError> {
        let prior = self.knowledge;
        self.knowledge = knowledge;
        if let Err(error) = self.validate() {
            self.knowledge = prior;
            return Err(error);
        }
        Ok(())
    }

    pub fn known_top(&self) -> &[CardDefId] {
        let count = usize::from(self.knowledge.known_top);
        &self.cards[..count]
    }

    /// Returns known bottom cards in the same top-to-bottom orientation they
    /// occupy in the exact true library.
    pub fn known_bottom(&self) -> &[CardDefId] {
        let count = usize::from(self.knowledge.known_bottom);
        &self.cards[self.cards.len() - count..]
    }

    pub fn unknown_middle(&self) -> &[CardDefId] {
        let top = usize::from(self.knowledge.known_top);
        let bottom = usize::from(self.knowledge.known_bottom);
        &self.cards[top..self.cards.len() - bottom]
    }

    pub fn validate(&self) -> Result<(), StateValidationError> {
        let known =
            usize::from(self.knowledge.known_top) + usize::from(self.knowledge.known_bottom);
        if known > self.cards.len() {
            return Err(StateValidationError::LibraryKnowledgeOutOfBounds {
                library_len: self.cards.len(),
                known_top: self.knowledge.known_top,
                known_bottom: self.knowledge.known_bottom,
            });
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct PermanentState {
    pub object_id: ObjectId,
    pub card: CardDefId,
    pub face: CardFace,
    pub tapped: bool,
    pub summoning_sick: bool,
    pub token: bool,
    pub counters: CounterState,
    pub mode: PermanentMode,
    pub attached_to: Option<ObjectId>,
    pub granted_ability: Option<GrantedAbility>,
}

/// Canonicalized storage for battlefield objects. ObjectId, not insertion
/// order, is the exact-world ordering key.
#[derive(Debug, Clone, Default, PartialEq, Eq, Hash, Serialize)]
pub struct BattlefieldZone(Vec<PermanentState>);

impl BattlefieldZone {
    pub fn new(mut permanents: Vec<PermanentState>) -> Self {
        permanents.sort_unstable_by_key(|permanent| permanent.object_id);
        Self(permanents)
    }

    pub fn permanents(&self) -> &[PermanentState] {
        &self.0
    }

    pub fn get(&self, object_id: ObjectId) -> Option<&PermanentState> {
        self.0
            .binary_search_by_key(&object_id, |permanent| permanent.object_id)
            .ok()
            .map(|index| &self.0[index])
    }

    pub fn len(&self) -> usize {
        self.0.len()
    }

    pub fn is_empty(&self) -> bool {
        self.0.is_empty()
    }
}

impl From<Vec<PermanentState>> for BattlefieldZone {
    fn from(permanents: Vec<PermanentState>) -> Self {
        Self::new(permanents)
    }
}

impl<'de> Deserialize<'de> for BattlefieldZone {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        Vec::<PermanentState>::deserialize(deserializer).map(Self::new)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct SourceRef {
    /// Present when the exact physical object is still useful to execution.
    /// Observation/value layers must not use this raw identity strategically.
    pub object_id: Option<ObjectId>,
    pub card: CardDefId,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum PendingDecisionKind {
    #[default]
    None,
    TutorTarget,
    ScryChoice,
    TopReorder,
    TransmuteSacrifice,
    TransmuteTarget,
    TransmuteDifferencePayment,
    WhirTarget,
    ReshapeTarget,
    BayTarget,
    SagaTarget,
    TezzeretTarget,
    TriggerOrder,
    ColiseumDiscard,
    CumulativeUpkeepPayment,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum PendingDecision {
    None,
    TutorTarget {
        source: SourceRef,
    },
    ScryChoice {
        source: SourceRef,
        looked_at: Vec<CardDefId>,
    },
    TopReorder {
        source: SourceRef,
        cards: Vec<CardDefId>,
    },
    TransmuteSacrifice {
        source: SourceRef,
    },
    TransmuteTarget {
        source: SourceRef,
        sacrificed_mana_value: u16,
    },
    TransmuteDifferencePayment {
        source: SourceRef,
        target: CardDefId,
        difference: GenericCost,
    },
    WhirTarget {
        source: SourceRef,
        x_value: u16,
    },
    ReshapeTarget {
        source: SourceRef,
        x_value: u16,
    },
    BayTarget {
        source: SourceRef,
        sacrificed_mana_value: u16,
    },
    SagaTarget {
        source: SourceRef,
    },
    TezzeretTarget {
        source: SourceRef,
    },
    TriggerOrder {
        source: SourceRef,
        trigger_count: u8,
    },
    ColiseumDiscard {
        source: SourceRef,
        count: u8,
    },
    CumulativeUpkeepPayment {
        source: SourceRef,
        age_counters: u16,
        generic_per_age: u16,
    },
}

impl Default for PendingDecision {
    fn default() -> Self {
        Self::None
    }
}

impl PendingDecision {
    pub fn kind(&self) -> PendingDecisionKind {
        match self {
            Self::None => PendingDecisionKind::None,
            Self::TutorTarget { .. } => PendingDecisionKind::TutorTarget,
            Self::ScryChoice { .. } => PendingDecisionKind::ScryChoice,
            Self::TopReorder { .. } => PendingDecisionKind::TopReorder,
            Self::TransmuteSacrifice { .. } => PendingDecisionKind::TransmuteSacrifice,
            Self::TransmuteTarget { .. } => PendingDecisionKind::TransmuteTarget,
            Self::TransmuteDifferencePayment { .. } => {
                PendingDecisionKind::TransmuteDifferencePayment
            }
            Self::WhirTarget { .. } => PendingDecisionKind::WhirTarget,
            Self::ReshapeTarget { .. } => PendingDecisionKind::ReshapeTarget,
            Self::BayTarget { .. } => PendingDecisionKind::BayTarget,
            Self::SagaTarget { .. } => PendingDecisionKind::SagaTarget,
            Self::TezzeretTarget { .. } => PendingDecisionKind::TezzeretTarget,
            Self::TriggerOrder { .. } => PendingDecisionKind::TriggerOrder,
            Self::ColiseumDiscard { .. } => PendingDecisionKind::ColiseumDiscard,
            Self::CumulativeUpkeepPayment { .. } => PendingDecisionKind::CumulativeUpkeepPayment,
        }
    }

    pub fn source(&self) -> Option<SourceRef> {
        match self {
            Self::None => None,
            Self::TutorTarget { source }
            | Self::ScryChoice { source, .. }
            | Self::TopReorder { source, .. }
            | Self::TransmuteSacrifice { source }
            | Self::TransmuteTarget { source, .. }
            | Self::TransmuteDifferencePayment { source, .. }
            | Self::WhirTarget { source, .. }
            | Self::ReshapeTarget { source, .. }
            | Self::BayTarget { source, .. }
            | Self::SagaTarget { source }
            | Self::TezzeretTarget { source }
            | Self::TriggerOrder { source, .. }
            | Self::ColiseumDiscard { source, .. }
            | Self::CumulativeUpkeepPayment { source, .. } => Some(*source),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum StackObject {
    Spell {
        object_id: ObjectId,
        card: CardDefId,
        x_value: Option<u16>,
    },
    AuraSpell {
        object_id: ObjectId,
        card: CardDefId,
        target: SourceRef,
    },
    ControlledTrigger {
        source: SourceRef,
        ability: AbilityId,
    },
    ActivatedAbility {
        source: SourceRef,
        ability: AbilityId,
        parameter: Option<u16>,
    },
    TargetedActivatedAbility {
        source: SourceRef,
        ability: AbilityId,
        target: SourceRef,
        parameter: Option<u16>,
    },
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum DelayedEvent {
    BaubleDraw {
        source: SourceRef,
        due_turn: u8,
    },
    ChromeCopySacrifice {
        object: ObjectId,
        card: CardDefId,
        due_turn: u8,
    },
    ManaDrainCredit {
        colorless: u16,
        due_turn: u8,
    },
    PermissionExpiry {
        permission: PermissionId,
        due_turn: u8,
    },
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct UrzaPermission {
    pub permission_id: PermissionId,
    pub card: CardDefId,
    pub expires_turn: u8,
    pub free_cast: bool,
    pub source: SourceRef,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum CommanderZone {
    #[default]
    CommandZone,
    Stack,
    Battlefield,
    Hand,
    Graveyard,
    Exile,
    Library,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct CommanderState {
    pub zone: CommanderZone,
    pub command_zone_casts: u8,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct TrueState {
    pub turn: u8,
    pub phase: Phase,
    pub window: Window,
    pub life: u16,
    pub library: TrueLibrary,
    pub hand: CardZone,
    pub battlefield: BattlefieldZone,
    pub graveyard: CardZone,
    pub exile: CardZone,
    pub mana: ManaPool,
    pub land_played_this_turn: bool,
    pub commander: CommanderState,
    pub stack: Vec<StackObject>,
    pub pending: PendingDecision,
    pub delayed_events: Vec<DelayedEvent>,
    pub urza_permissions: Vec<UrzaPermission>,
    pub spell_cast_this_turn: bool,
    pub rng_occurrence_cursor: u64,
}

impl Default for TrueState {
    fn default() -> Self {
        Self {
            turn: 0,
            phase: Phase::Untap,
            window: Window::None,
            life: 40,
            library: TrueLibrary::default(),
            hand: CardZone::default(),
            battlefield: BattlefieldZone::default(),
            graveyard: CardZone::default(),
            exile: CardZone::default(),
            mana: ManaPool::default(),
            land_played_this_turn: false,
            commander: CommanderState::default(),
            stack: Vec::new(),
            pending: PendingDecision::default(),
            delayed_events: Vec::new(),
            urza_permissions: Vec::new(),
            spell_cast_this_turn: false,
            rng_occurrence_cursor: 0,
        }
    }
}

impl TrueState {
    pub fn validate(&self) -> Result<(), StateValidationError> {
        self.library.validate()?;

        let mut live = BTreeMap::new();
        for permanent in self.battlefield.permanents() {
            if live.insert(permanent.object_id, permanent.card).is_some() {
                return Err(StateValidationError::DuplicateObjectId(permanent.object_id));
            }
        }

        let mut exact_objects: BTreeSet<ObjectId> = live.keys().copied().collect();
        for object in &self.stack {
            let object_id = match object {
                StackObject::Spell { object_id, .. } | StackObject::AuraSpell { object_id, .. } => {
                    *object_id
                }
                StackObject::ControlledTrigger { .. }
                | StackObject::ActivatedAbility { .. }
                | StackObject::TargetedActivatedAbility { .. } => continue,
            };
            if !exact_objects.insert(object_id) {
                return Err(StateValidationError::DuplicateObjectId(object_id));
            }
        }

        for permanent in self.battlefield.permanents() {
            if let Some(target) = permanent.attached_to {
                if target == permanent.object_id {
                    return Err(StateValidationError::SelfAttachment(permanent.object_id));
                }
                if !live.contains_key(&target) {
                    return Err(StateValidationError::MissingAttachmentTarget {
                        object: permanent.object_id,
                        target,
                    });
                }
            }
        }
        self.validate_attachment_cycles()?;

        for source in self.source_refs() {
            let Some(object_id) = source.object_id else {
                continue;
            };
            let Some(card) = live.get(&object_id) else {
                continue;
            };
            if *card != source.card {
                return Err(StateValidationError::SourceCardMismatch {
                    object: object_id,
                    expected: *card,
                    observed: source.card,
                });
            }
        }

        let mut permission_ids = BTreeSet::new();
        for permission in &self.urza_permissions {
            if !permission_ids.insert(permission.permission_id) {
                return Err(StateValidationError::DuplicatePermissionId(
                    permission.permission_id,
                ));
            }
        }

        for event in &self.delayed_events {
            match event {
                DelayedEvent::ChromeCopySacrifice { object, card, .. } => {
                    let Some(actual_card) = live.get(object) else {
                        return Err(StateValidationError::MissingDelayedObject(*object));
                    };
                    if actual_card != card {
                        return Err(StateValidationError::DelayedObjectCardMismatch {
                            object: *object,
                            expected: *actual_card,
                            observed: *card,
                        });
                    }
                }
                DelayedEvent::PermissionExpiry { permission, .. } => {
                    if !permission_ids.contains(permission) {
                        return Err(StateValidationError::UnknownPermissionExpiry(*permission));
                    }
                }
                DelayedEvent::BaubleDraw { .. } | DelayedEvent::ManaDrainCredit { .. } => {}
            }
        }

        Ok(())
    }

    fn source_refs(&self) -> impl Iterator<Item = SourceRef> + '_ {
        let stack = self.stack.iter().filter_map(|object| match object {
            StackObject::Spell { .. } => None,
            StackObject::AuraSpell { target, .. } => Some(*target),
            StackObject::ControlledTrigger { source, .. }
            | StackObject::ActivatedAbility { source, .. } => Some(*source),
            StackObject::TargetedActivatedAbility { source, .. } => Some(*source),
        });
        let stack_targets = self.stack.iter().filter_map(|object| match object {
            StackObject::TargetedActivatedAbility { target, .. } => Some(*target),
            _ => None,
        });
        let pending = self.pending.source().into_iter();
        let delayed = self.delayed_events.iter().filter_map(|event| match event {
            DelayedEvent::BaubleDraw { source, .. } => Some(*source),
            _ => None,
        });
        let permissions = self
            .urza_permissions
            .iter()
            .map(|permission| permission.source);
        stack
            .chain(stack_targets)
            .chain(pending)
            .chain(delayed)
            .chain(permissions)
    }

    fn validate_attachment_cycles(&self) -> Result<(), StateValidationError> {
        let targets: BTreeMap<_, _> = self
            .battlefield
            .permanents()
            .iter()
            .map(|permanent| (permanent.object_id, permanent.attached_to))
            .collect();

        for start in targets.keys().copied() {
            let mut seen = BTreeSet::new();
            let mut current = start;
            while let Some(Some(next)) = targets.get(&current) {
                if !seen.insert(current) {
                    return Err(StateValidationError::AttachmentCycle(start));
                }
                current = *next;
            }
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct ReplayKey(pub TrueState);

impl From<&TrueState> for ReplayKey {
    fn from(value: &TrueState) -> Self {
        Self(value.clone())
    }
}

#[derive(Debug, Clone, Error, PartialEq, Eq)]
pub enum StateValidationError {
    #[error(
        "library knowledge exceeds library length {library_len}: top={known_top}, bottom={known_bottom}"
    )]
    LibraryKnowledgeOutOfBounds {
        library_len: usize,
        known_top: u8,
        known_bottom: u8,
    },
    #[error("duplicate physical object id {0:?}")]
    DuplicateObjectId(ObjectId),
    #[error("object {0:?} cannot attach to itself")]
    SelfAttachment(ObjectId),
    #[error("object {object:?} attaches to missing target {target:?}")]
    MissingAttachmentTarget { object: ObjectId, target: ObjectId },
    #[error("attachment cycle reachable from {0:?}")]
    AttachmentCycle(ObjectId),
    #[error(
        "source {object:?} card mismatch: live object is {expected:?}, source reference is {observed:?}"
    )]
    SourceCardMismatch {
        object: ObjectId,
        expected: CardDefId,
        observed: CardDefId,
    },
    #[error("duplicate permission id {0:?}")]
    DuplicatePermissionId(PermissionId),
    #[error("permission expiry references unknown permission {0:?}")]
    UnknownPermissionExpiry(PermissionId),
    #[error("delayed event references missing live object {0:?}")]
    MissingDelayedObject(ObjectId),
    #[error(
        "delayed object {object:?} card mismatch: live object is {expected:?}, event says {observed:?}"
    )]
    DelayedObjectCardMismatch {
        object: ObjectId,
        expected: CardDefId,
        observed: CardDefId,
    },
}

#[cfg(test)]
mod tests {
    use super::{
        BattlefieldZone, CardFace, CardZone, CounterState, DelayedEvent, LibraryKnowledge,
        PermanentState, ReplayKey, StateValidationError, TrueLibrary, TrueState,
    };
    use crate::{CardDefId, ObjectId, PermissionId};

    fn permanent(object: u32, card: u16, attached_to: Option<u32>) -> PermanentState {
        PermanentState {
            object_id: ObjectId(object),
            card: CardDefId(card),
            face: CardFace::Front,
            tapped: false,
            summoning_sick: false,
            token: false,
            counters: CounterState::default(),
            mode: Default::default(),
            attached_to: attached_to.map(ObjectId),
            granted_ability: None,
        }
    }

    #[test]
    fn default_state_tracks_our_life_from_forty() {
        assert_eq!(TrueState::default().life, 40);
    }

    #[test]
    fn unordered_card_zones_and_battlefield_storage_are_normalized() {
        assert_eq!(
            CardZone::new(vec![CardDefId(3), CardDefId(1), CardDefId(1)]).cards(),
            &[CardDefId(1), CardDefId(1), CardDefId(3)]
        );
        let zone = BattlefieldZone::new(vec![permanent(9, 1, None), permanent(2, 2, None)]);
        assert_eq!(zone.permanents()[0].object_id, ObjectId(2));
        assert_eq!(zone.permanents()[1].object_id, ObjectId(9));
    }

    #[test]
    fn replay_identity_retains_hidden_order_and_rng_progression() {
        let a = TrueState {
            library: TrueLibrary::unknown(vec![CardDefId(1), CardDefId(2)]),
            ..TrueState::default()
        };

        let b = TrueState {
            library: TrueLibrary::unknown(vec![CardDefId(2), CardDefId(1)]),
            ..a.clone()
        };
        assert_ne!(ReplayKey::from(&a), ReplayKey::from(&b));

        let c = TrueState {
            rng_occurrence_cursor: 1,
            ..a.clone()
        };
        assert_ne!(ReplayKey::from(&a), ReplayKey::from(&c));
    }

    #[test]
    fn library_knowledge_bounds_are_structural_invariants() {
        assert_eq!(
            TrueLibrary::new(
                vec![CardDefId(1)],
                LibraryKnowledge {
                    known_top: 1,
                    known_bottom: 1,
                }
            ),
            Err(StateValidationError::LibraryKnowledgeOutOfBounds {
                library_len: 1,
                known_top: 1,
                known_bottom: 1,
            })
        );
    }

    #[test]
    fn attachment_targets_and_cycles_are_rejected() {
        let missing = TrueState {
            battlefield: BattlefieldZone::new(vec![permanent(1, 10, Some(99))]),
            ..TrueState::default()
        };
        assert!(matches!(
            missing.validate(),
            Err(StateValidationError::MissingAttachmentTarget { .. })
        ));

        let cycle = TrueState {
            battlefield: BattlefieldZone::new(vec![
                permanent(1, 10, Some(2)),
                permanent(2, 11, Some(1)),
            ]),
            ..TrueState::default()
        };
        assert!(matches!(
            cycle.validate(),
            Err(StateValidationError::AttachmentCycle(_))
        ));
    }

    #[test]
    fn delayed_object_and_permission_references_are_validated() {
        let bad_object = TrueState {
            delayed_events: vec![DelayedEvent::ChromeCopySacrifice {
                object: ObjectId(7),
                card: CardDefId(9),
                due_turn: 2,
            }],
            ..TrueState::default()
        };
        assert_eq!(
            bad_object.validate(),
            Err(StateValidationError::MissingDelayedObject(ObjectId(7)))
        );

        let bad_permission = TrueState {
            delayed_events: vec![DelayedEvent::PermissionExpiry {
                permission: PermissionId(8),
                due_turn: 2,
            }],
            ..TrueState::default()
        };
        assert_eq!(
            bad_permission.validate(),
            Err(StateValidationError::UnknownPermissionExpiry(PermissionId(
                8
            )))
        );
    }

    #[test]
    fn replay_key_json_round_trip_is_exact() {
        let state = TrueState {
            library: TrueLibrary::new(
                vec![CardDefId(1), CardDefId(2), CardDefId(3)],
                LibraryKnowledge {
                    known_top: 1,
                    known_bottom: 1,
                },
            )
            .unwrap(),
            hand: CardZone::new(vec![CardDefId(9), CardDefId(4)]),
            battlefield: BattlefieldZone::new(vec![
                permanent(2, 20, None),
                permanent(1, 21, Some(2)),
            ]),
            rng_occurrence_cursor: 17,
            ..TrueState::default()
        };
        state.validate().unwrap();
        let key = ReplayKey::from(&state);
        let encoded = serde_json::to_string(&key).unwrap();
        let decoded: ReplayKey = serde_json::from_str(&encoded).unwrap();
        assert_eq!(decoded, key);
    }
}
