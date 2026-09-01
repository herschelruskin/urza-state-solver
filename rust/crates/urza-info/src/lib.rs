#![forbid(unsafe_code)]

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use thiserror::Error;

pub use urza_core::{
    AbilityId, CardDefId, CardFace, CommanderState, CommanderZone, CounterState, GenericCost,
    GrantedAbility, ManaPool, PendingDecisionKind, PermanentMode, Phase, Window,
};
use urza_core::{
    DelayedEvent, ObjectId, PendingDecision, SourceRef, StackObject, StateValidationError,
    TrueState,
};

pub const INFORMATION_SCHEMA_VERSION: &str = "information_state_v3_r3";

#[derive(
    Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize,
)]
#[repr(transparent)]
pub struct CanonicalObjectId(pub u16);

#[derive(
    Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize,
)]
pub struct CardCount {
    pub card: CardDefId,
    pub count: u8,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct LibraryBelief {
    /// Multiset of cards whose relative order is not currently known.
    pub remaining_counts: Vec<CardCount>,
    /// Exact known prefix, top card first.
    pub known_top: Vec<CardDefId>,
    /// Exact known suffix in true top-to-bottom library orientation.
    pub known_bottom: Vec<CardDefId>,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct ObservedPermanent {
    /// Structural equivalence-class label, not an execution ObjectId.
    pub canonical_id: CanonicalObjectId,
    pub card: CardDefId,
    pub face: CardFace,
    pub tapped: bool,
    pub summoning_sick: bool,
    pub token: bool,
    pub counters: CounterState,
    pub mode: PermanentMode,
    pub attached_to: Option<CanonicalObjectId>,
    pub granted_ability: Option<GrantedAbility>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct ObservedSourceRef {
    pub canonical_object: Option<CanonicalObjectId>,
    pub card: CardDefId,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub enum ObservedStackKind {
    Spell,
    ControlledTrigger,
    ActivatedAbility,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct ObservedStackObject {
    pub kind: ObservedStackKind,
    pub card: Option<CardDefId>,
    pub source: Option<ObservedSourceRef>,
    pub ability: Option<AbilityId>,
    pub parameter: Option<u16>,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ObservedPendingDecision {
    None,
    TutorTarget {
        source: ObservedSourceRef,
    },
    ScryChoice {
        source: ObservedSourceRef,
        looked_at: Vec<CardDefId>,
    },
    TopReorder {
        source: ObservedSourceRef,
        cards: Vec<CardDefId>,
    },
    TransmuteSacrifice {
        source: ObservedSourceRef,
    },
    TransmuteTarget {
        source: ObservedSourceRef,
        sacrificed_mana_value: u16,
    },
    TransmuteDifferencePayment {
        source: ObservedSourceRef,
        target: CardDefId,
        difference: GenericCost,
    },
    WhirTarget {
        source: ObservedSourceRef,
        x_value: u16,
    },
    ReshapeTarget {
        source: ObservedSourceRef,
        x_value: u16,
    },
    BayTarget {
        source: ObservedSourceRef,
        sacrificed_mana_value: u16,
    },
    TriggerOrder {
        source: ObservedSourceRef,
        trigger_count: u8,
    },
    ColiseumDiscard {
        source: ObservedSourceRef,
        count: u8,
    },
    CumulativeUpkeepPayment {
        source: ObservedSourceRef,
        age_counters: u16,
        generic_per_age: u16,
    },
}

impl ObservedPendingDecision {
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
            Self::TriggerOrder { .. } => PendingDecisionKind::TriggerOrder,
            Self::ColiseumDiscard { .. } => PendingDecisionKind::ColiseumDiscard,
            Self::CumulativeUpkeepPayment { .. } => PendingDecisionKind::CumulativeUpkeepPayment,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub enum ObservedDelayedEvent {
    BaubleDraw {
        source: ObservedSourceRef,
        due_turn: u8,
    },
    ChromeCopySacrifice {
        object: CanonicalObjectId,
        card: CardDefId,
        due_turn: u8,
    },
    ManaDrainCredit {
        colorless: u16,
        due_turn: u8,
    },
    PermissionExpiry {
        permission_slot: u16,
        due_turn: u8,
    },
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct ObservedPermission {
    pub permission_slot: u16,
    pub card: CardDefId,
    pub expires_turn: u8,
    pub free_cast: bool,
    pub source: ObservedSourceRef,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct InformationState {
    pub turn: u8,
    pub phase: Phase,
    pub window: Window,
    pub life: u16,
    pub library: LibraryBelief,
    pub hand: Vec<CardDefId>,
    pub battlefield: Vec<ObservedPermanent>,
    pub graveyard: Vec<CardDefId>,
    pub exile: Vec<CardDefId>,
    pub mana: ManaPool,
    pub land_played_this_turn: bool,
    pub commander: CommanderState,
    pub stack: Vec<ObservedStackObject>,
    pub pending: ObservedPendingDecision,
    pub delayed_events: Vec<ObservedDelayedEvent>,
    pub urza_permissions: Vec<ObservedPermission>,
    pub spell_cast_this_turn: bool,
}

impl Default for InformationState {
    fn default() -> Self {
        Self {
            turn: 0,
            phase: Phase::Untap,
            window: Window::None,
            life: 40,
            library: LibraryBelief::default(),
            hand: Vec::new(),
            battlefield: Vec::new(),
            graveyard: Vec::new(),
            exile: Vec::new(),
            mana: ManaPool::default(),
            land_played_this_turn: false,
            commander: CommanderState::default(),
            stack: Vec::new(),
            pending: ObservedPendingDecision::None,
            delayed_events: Vec::new(),
            urza_permissions: Vec::new(),
            spell_cast_this_turn: false,
        }
    }
}

#[derive(Debug, Clone, Error, PartialEq, Eq)]
pub enum ObservationError {
    #[error("cannot observe invalid execution state: {0}")]
    InvalidState(#[from] StateValidationError),
}

pub fn observe(state: &TrueState) -> Result<InformationState, ObservationError> {
    state.validate()?;
    let object_classes = canonical_object_classes(state);
    let library = observe_library(state);

    let mut battlefield: Vec<_> = state
        .battlefield
        .permanents()
        .iter()
        .map(|permanent| ObservedPermanent {
            canonical_id: object_classes[&permanent.object_id],
            card: permanent.card,
            face: permanent.face,
            tapped: permanent.tapped,
            summoning_sick: permanent.summoning_sick,
            token: permanent.token,
            counters: permanent.counters,
            mode: permanent.mode,
            attached_to: permanent
                .attached_to
                .and_then(|target| object_classes.get(&target).copied()),
            granted_ability: permanent.granted_ability,
        })
        .collect();
    battlefield.sort_unstable_by_key(|permanent| permanent.canonical_id);

    let stack = state
        .stack
        .iter()
        .map(|object| match object {
            StackObject::Spell { card, x_value, .. } => ObservedStackObject {
                kind: ObservedStackKind::Spell,
                card: Some(*card),
                source: None,
                ability: None,
                parameter: *x_value,
            },
            StackObject::ControlledTrigger { source, ability } => ObservedStackObject {
                kind: ObservedStackKind::ControlledTrigger,
                card: None,
                source: Some(observe_source(*source, &object_classes)),
                ability: Some(*ability),
                parameter: None,
            },
            StackObject::ActivatedAbility {
                source,
                ability,
                parameter,
            } => ObservedStackObject {
                kind: ObservedStackKind::ActivatedAbility,
                card: None,
                source: Some(observe_source(*source, &object_classes)),
                ability: Some(*ability),
                parameter: *parameter,
            },
        })
        .collect();

    let pending = observe_pending(&state.pending, &object_classes);
    let (urza_permissions, permission_slots) =
        observe_permissions(&state.urza_permissions, &object_classes);

    let mut delayed_events: Vec<_> = state
        .delayed_events
        .iter()
        .map(|event| match event {
            DelayedEvent::BaubleDraw { source, due_turn } => ObservedDelayedEvent::BaubleDraw {
                source: observe_source(*source, &object_classes),
                due_turn: *due_turn,
            },
            DelayedEvent::ChromeCopySacrifice {
                object,
                card,
                due_turn,
            } => ObservedDelayedEvent::ChromeCopySacrifice {
                object: object_classes[object],
                card: *card,
                due_turn: *due_turn,
            },
            DelayedEvent::ManaDrainCredit {
                colorless,
                due_turn,
            } => ObservedDelayedEvent::ManaDrainCredit {
                colorless: *colorless,
                due_turn: *due_turn,
            },
            DelayedEvent::PermissionExpiry {
                permission,
                due_turn,
            } => ObservedDelayedEvent::PermissionExpiry {
                permission_slot: permission_slots[permission],
                due_turn: *due_turn,
            },
        })
        .collect();
    delayed_events.sort_unstable();

    Ok(InformationState {
        turn: state.turn,
        phase: state.phase,
        window: state.window,
        life: state.life,
        library,
        hand: state.hand.cards().to_vec(),
        battlefield,
        graveyard: state.graveyard.cards().to_vec(),
        exile: state.exile.cards().to_vec(),
        mana: state.mana,
        land_played_this_turn: state.land_played_this_turn,
        commander: state.commander,
        stack,
        pending,
        delayed_events,
        urza_permissions,
        spell_cast_this_turn: state.spell_cast_this_turn,
    })
}

fn observe_library(state: &TrueState) -> LibraryBelief {
    let mut counts = BTreeMap::<CardDefId, u8>::new();
    for card in state.library.unknown_middle() {
        let entry = counts.entry(*card).or_default();
        *entry = entry
            .checked_add(1)
            .expect("Commander library multiplicity fits in u8");
    }
    LibraryBelief {
        remaining_counts: counts
            .into_iter()
            .map(|(card, count)| CardCount { card, count })
            .collect(),
        known_top: state.library.known_top().to_vec(),
        known_bottom: state.library.known_bottom().to_vec(),
    }
}

fn observe_source(
    source: SourceRef,
    object_classes: &BTreeMap<ObjectId, CanonicalObjectId>,
) -> ObservedSourceRef {
    ObservedSourceRef {
        canonical_object: source
            .object_id
            .and_then(|object| object_classes.get(&object).copied()),
        card: source.card,
    }
}

fn observe_pending(
    pending: &PendingDecision,
    object_classes: &BTreeMap<ObjectId, CanonicalObjectId>,
) -> ObservedPendingDecision {
    match pending {
        PendingDecision::None => ObservedPendingDecision::None,
        PendingDecision::TutorTarget { source } => ObservedPendingDecision::TutorTarget {
            source: observe_source(*source, object_classes),
        },
        PendingDecision::ScryChoice { source, looked_at } => ObservedPendingDecision::ScryChoice {
            source: observe_source(*source, object_classes),
            looked_at: looked_at.clone(),
        },
        PendingDecision::TopReorder { source, cards } => ObservedPendingDecision::TopReorder {
            source: observe_source(*source, object_classes),
            cards: cards.clone(),
        },
        PendingDecision::TransmuteSacrifice { source } => {
            ObservedPendingDecision::TransmuteSacrifice {
                source: observe_source(*source, object_classes),
            }
        }
        PendingDecision::TransmuteTarget {
            source,
            sacrificed_mana_value,
        } => ObservedPendingDecision::TransmuteTarget {
            source: observe_source(*source, object_classes),
            sacrificed_mana_value: *sacrificed_mana_value,
        },
        PendingDecision::TransmuteDifferencePayment {
            source,
            target,
            difference,
        } => ObservedPendingDecision::TransmuteDifferencePayment {
            source: observe_source(*source, object_classes),
            target: *target,
            difference: *difference,
        },
        PendingDecision::WhirTarget { source, x_value } => ObservedPendingDecision::WhirTarget {
            source: observe_source(*source, object_classes),
            x_value: *x_value,
        },
        PendingDecision::ReshapeTarget { source, x_value } => {
            ObservedPendingDecision::ReshapeTarget {
                source: observe_source(*source, object_classes),
                x_value: *x_value,
            }
        }
        PendingDecision::BayTarget {
            source,
            sacrificed_mana_value,
        } => ObservedPendingDecision::BayTarget {
            source: observe_source(*source, object_classes),
            sacrificed_mana_value: *sacrificed_mana_value,
        },
        PendingDecision::TriggerOrder {
            source,
            trigger_count,
        } => ObservedPendingDecision::TriggerOrder {
            source: observe_source(*source, object_classes),
            trigger_count: *trigger_count,
        },
        PendingDecision::ColiseumDiscard { source, count } => {
            ObservedPendingDecision::ColiseumDiscard {
                source: observe_source(*source, object_classes),
                count: *count,
            }
        }
        PendingDecision::CumulativeUpkeepPayment {
            source,
            age_counters,
            generic_per_age,
        } => ObservedPendingDecision::CumulativeUpkeepPayment {
            source: observe_source(*source, object_classes),
            age_counters: *age_counters,
            generic_per_age: *generic_per_age,
        },
    }
}

fn observe_permissions(
    permissions: &[urza_core::UrzaPermission],
    object_classes: &BTreeMap<ObjectId, CanonicalObjectId>,
) -> (
    Vec<ObservedPermission>,
    BTreeMap<urza_core::PermissionId, u16>,
) {
    let mut indexed: Vec<_> = permissions
        .iter()
        .map(|permission| {
            (
                permission,
                observe_source(permission.source, object_classes),
            )
        })
        .collect();
    indexed.sort_unstable_by_key(|(permission, source)| {
        (
            permission.card,
            permission.expires_turn,
            permission.free_cast,
            *source,
            permission.permission_id,
        )
    });

    let mut slot_map = BTreeMap::new();
    let observed = indexed
        .into_iter()
        .enumerate()
        .map(|(slot, (permission, source))| {
            let slot = u16::try_from(slot).expect("permission count fits in u16");
            slot_map.insert(permission.permission_id, slot);
            ObservedPermission {
                permission_slot: slot,
                card: permission.card,
                expires_turn: permission.expires_turn,
                free_cast: permission.free_cast,
                source,
            }
        })
        .collect();
    (observed, slot_map)
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
struct LocalSignature {
    card: CardDefId,
    face: CardFace,
    tapped: bool,
    summoning_sick: bool,
    token: bool,
    counters: (u16, u16, u16, u16, u16, i16, u8),
    mode: (u8, u8),
    granted_ability: u8,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
enum ExternalRole {
    Stack {
        position: u16,
        kind: u8,
        ability: AbilityId,
        parameter: Option<u16>,
    },
    Pending {
        kind: u8,
        numeric_a: u16,
        numeric_b: u16,
        cards: Vec<CardDefId>,
    },
    BaubleDraw {
        due_turn: u8,
    },
    ChromeSacrifice {
        card: CardDefId,
        due_turn: u8,
    },
    PermissionSource {
        card: CardDefId,
        expires_turn: u8,
        free_cast: bool,
    },
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
struct RefinementSignature {
    local: LocalSignature,
    roles: Vec<ExternalRole>,
    attached_to_class: Option<u16>,
    incoming_attachment_classes: Vec<u16>,
}

pub fn resolve_canonical_object(
    state: &TrueState,
    canonical: CanonicalObjectId,
) -> Result<Option<ObjectId>, ObservationError> {
    state.validate()?;
    Ok(canonical_object_classes(state)
        .into_iter()
        .filter_map(|(object, class)| (class == canonical).then_some(object))
        .min())
}

fn canonical_object_classes(state: &TrueState) -> BTreeMap<ObjectId, CanonicalObjectId> {
    let permanents = state.battlefield.permanents();
    if permanents.is_empty() {
        return BTreeMap::new();
    }

    let roles = external_roles(state);
    let locals: BTreeMap<_, _> = permanents
        .iter()
        .map(|permanent| (permanent.object_id, local_signature(permanent)))
        .collect();

    let initial: Vec<_> = permanents
        .iter()
        .map(|permanent| {
            (
                permanent.object_id,
                (
                    locals[&permanent.object_id].clone(),
                    roles.get(&permanent.object_id).cloned().unwrap_or_default(),
                ),
            )
        })
        .collect();
    let mut labels = dense_labels(initial);

    for _ in 0..=permanents.len() {
        let mut incoming: BTreeMap<ObjectId, Vec<u16>> = BTreeMap::new();
        for permanent in permanents {
            if let Some(target) = permanent.attached_to {
                incoming
                    .entry(target)
                    .or_default()
                    .push(labels[&permanent.object_id]);
            }
        }
        for values in incoming.values_mut() {
            values.sort_unstable();
        }

        let descriptors: Vec<_> = permanents
            .iter()
            .map(|permanent| {
                (
                    permanent.object_id,
                    RefinementSignature {
                        local: locals[&permanent.object_id].clone(),
                        roles: roles.get(&permanent.object_id).cloned().unwrap_or_default(),
                        attached_to_class: permanent.attached_to.map(|target| labels[&target]),
                        incoming_attachment_classes: incoming
                            .get(&permanent.object_id)
                            .cloned()
                            .unwrap_or_default(),
                    },
                )
            })
            .collect();
        let next = dense_labels(descriptors);
        if next == labels {
            break;
        }
        labels = next;
    }

    labels
        .into_iter()
        .map(|(object, label)| (object, CanonicalObjectId(label)))
        .collect()
}

fn dense_labels<T: Ord + Clone>(items: Vec<(ObjectId, T)>) -> BTreeMap<ObjectId, u16> {
    let mut unique: Vec<_> = items
        .iter()
        .map(|(_, signature)| signature.clone())
        .collect();
    unique.sort_unstable();
    unique.dedup();
    items
        .into_iter()
        .map(|(object, signature)| {
            let label = unique
                .binary_search(&signature)
                .expect("signature is present in unique set");
            (
                object,
                u16::try_from(label).expect("battlefield class count fits in u16"),
            )
        })
        .collect()
}

fn local_signature(permanent: &urza_core::PermanentState) -> LocalSignature {
    LocalSignature {
        card: permanent.card,
        face: permanent.face,
        tapped: permanent.tapped,
        summoning_sick: permanent.summoning_sick,
        token: permanent.token,
        counters: (
            permanent.counters.plus_one_plus_one,
            permanent.counters.charge,
            permanent.counters.burden,
            permanent.counters.lore,
            permanent.counters.age,
            permanent.counters.loyalty,
            permanent.counters.luck,
        ),
        mode: match permanent.mode {
            PermanentMode::Normal => (0, 0),
            PermanentMode::RealityChipCreature => (1, 0),
            PermanentMode::RealityChipAttached => (2, 0),
            PermanentMode::UthrosStation => (3, 0),
            PermanentMode::UthrosCreature => (4, 0),
            PermanentMode::Other(value) => (5, value),
        },
        granted_ability: match permanent.granted_ability {
            None => 0,
            Some(GrantedAbility::KnackBounceUntilEndOfTurn) => 1,
        },
    }
}

fn external_roles(state: &TrueState) -> BTreeMap<ObjectId, Vec<ExternalRole>> {
    let mut roles = BTreeMap::<ObjectId, Vec<ExternalRole>>::new();

    for (position, object) in state.stack.iter().enumerate() {
        let (source, kind, ability, parameter) = match object {
            StackObject::Spell { .. } => continue,
            StackObject::ControlledTrigger { source, ability } => (source, 1, *ability, None),
            StackObject::ActivatedAbility {
                source,
                ability,
                parameter,
            } => (source, 2, *ability, *parameter),
        };
        push_source_role(
            &mut roles,
            *source,
            ExternalRole::Stack {
                position: u16::try_from(position).expect("stack depth fits in u16"),
                kind,
                ability,
                parameter,
            },
        );
    }

    if let Some(source) = state.pending.source() {
        push_source_role(&mut roles, source, pending_role(&state.pending));
    }

    for event in &state.delayed_events {
        match event {
            DelayedEvent::BaubleDraw { source, due_turn } => push_source_role(
                &mut roles,
                *source,
                ExternalRole::BaubleDraw {
                    due_turn: *due_turn,
                },
            ),
            DelayedEvent::ChromeCopySacrifice {
                object,
                card,
                due_turn,
            } => roles
                .entry(*object)
                .or_default()
                .push(ExternalRole::ChromeSacrifice {
                    card: *card,
                    due_turn: *due_turn,
                }),
            DelayedEvent::ManaDrainCredit { .. } | DelayedEvent::PermissionExpiry { .. } => {}
        }
    }

    for permission in &state.urza_permissions {
        push_source_role(
            &mut roles,
            permission.source,
            ExternalRole::PermissionSource {
                card: permission.card,
                expires_turn: permission.expires_turn,
                free_cast: permission.free_cast,
            },
        );
    }

    for values in roles.values_mut() {
        values.sort_unstable();
    }
    roles
}

fn push_source_role(
    roles: &mut BTreeMap<ObjectId, Vec<ExternalRole>>,
    source: SourceRef,
    role: ExternalRole,
) {
    if let Some(object) = source.object_id {
        roles.entry(object).or_default().push(role);
    }
}

fn pending_role(pending: &PendingDecision) -> ExternalRole {
    let (kind, numeric_a, numeric_b, cards) = match pending {
        PendingDecision::None => (0, 0, 0, Vec::new()),
        PendingDecision::TutorTarget { .. } => (1, 0, 0, Vec::new()),
        PendingDecision::ScryChoice { looked_at, .. } => (2, 0, 0, looked_at.clone()),
        PendingDecision::TopReorder { cards, .. } => (3, 0, 0, cards.clone()),
        PendingDecision::TransmuteSacrifice { .. } => (4, 0, 0, Vec::new()),
        PendingDecision::TransmuteTarget {
            sacrificed_mana_value,
            ..
        } => (5, *sacrificed_mana_value, 0, Vec::new()),
        PendingDecision::TransmuteDifferencePayment { difference, .. } => {
            (6, difference.0, 0, Vec::new())
        }
        PendingDecision::WhirTarget { x_value, .. } => (7, *x_value, 0, Vec::new()),
        PendingDecision::ReshapeTarget { x_value, .. } => (8, *x_value, 0, Vec::new()),
        PendingDecision::BayTarget {
            sacrificed_mana_value,
            ..
        } => (9, *sacrificed_mana_value, 0, Vec::new()),
        PendingDecision::TriggerOrder { trigger_count, .. } => {
            (10, u16::from(*trigger_count), 0, Vec::new())
        }
        PendingDecision::ColiseumDiscard { count, .. } => (11, u16::from(*count), 0, Vec::new()),
        PendingDecision::CumulativeUpkeepPayment {
            age_counters,
            generic_per_age,
            ..
        } => (12, *age_counters, *generic_per_age, Vec::new()),
    };
    ExternalRole::Pending {
        kind,
        numeric_a,
        numeric_b,
        cards,
    }
}

#[derive(Debug, Clone, Copy)]
pub struct PolicyView<'a> {
    info: &'a InformationState,
}

impl<'a> PolicyView<'a> {
    pub fn new(info: &'a InformationState) -> Self {
        Self { info }
    }

    pub fn turn(self) -> u8 {
        self.info.turn
    }

    pub fn life(self) -> u16 {
        self.info.life
    }

    pub fn hand(self) -> &'a [CardDefId] {
        &self.info.hand
    }

    pub fn library_belief(self) -> &'a LibraryBelief {
        &self.info.library
    }

    pub fn information_state(self) -> &'a InformationState {
        self.info
    }
}

#[cfg(test)]
mod tests {
    use super::{CanonicalObjectId, CardCount, InformationState, PolicyView, observe};
    use urza_core::{
        BattlefieldZone, CardDefId, CardFace, CounterState, LibraryKnowledge, ObjectId,
        PermanentState, ReplayKey, SourceRef, StackObject, TrueLibrary, TrueState,
    };

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
    fn policy_view_exposes_belief_not_true_library_order() {
        let state = TrueState {
            library: TrueLibrary::new(
                vec![
                    CardDefId(9),
                    CardDefId(7),
                    CardDefId(7),
                    CardDefId(4),
                    CardDefId(2),
                ],
                LibraryKnowledge {
                    known_top: 1,
                    known_bottom: 1,
                },
            )
            .unwrap(),
            ..TrueState::default()
        };
        let info = observe(&state).unwrap();
        let view = PolicyView::new(&info);
        assert_eq!(view.library_belief().known_top, vec![CardDefId(9)]);
        assert_eq!(view.library_belief().known_bottom, vec![CardDefId(2)]);
        assert_eq!(
            view.library_belief().remaining_counts,
            vec![
                CardCount {
                    card: CardDefId(4),
                    count: 1,
                },
                CardCount {
                    card: CardDefId(7),
                    count: 2,
                },
            ]
        );
    }

    #[test]
    fn unknown_middle_order_does_not_leak_into_information_state() {
        let a = TrueState {
            library: TrueLibrary::new(
                vec![
                    CardDefId(1),
                    CardDefId(2),
                    CardDefId(3),
                    CardDefId(4),
                    CardDefId(5),
                ],
                LibraryKnowledge {
                    known_top: 1,
                    known_bottom: 1,
                },
            )
            .unwrap(),
            ..TrueState::default()
        };
        let b = TrueState {
            library: TrueLibrary::new(
                vec![
                    CardDefId(1),
                    CardDefId(4),
                    CardDefId(2),
                    CardDefId(3),
                    CardDefId(5),
                ],
                LibraryKnowledge {
                    known_top: 1,
                    known_bottom: 1,
                },
            )
            .unwrap(),
            ..a.clone()
        };
        assert_ne!(ReplayKey::from(&a), ReplayKey::from(&b));
        assert_eq!(observe(&a).unwrap(), observe(&b).unwrap());
    }

    #[test]
    fn known_top_order_remains_observable() {
        let a = TrueState {
            library: TrueLibrary::new(
                vec![CardDefId(1), CardDefId(2), CardDefId(3)],
                LibraryKnowledge {
                    known_top: 2,
                    known_bottom: 0,
                },
            )
            .unwrap(),
            ..TrueState::default()
        };
        let b = TrueState {
            library: TrueLibrary::new(
                vec![CardDefId(2), CardDefId(1), CardDefId(3)],
                LibraryKnowledge {
                    known_top: 2,
                    known_bottom: 0,
                },
            )
            .unwrap(),
            ..a.clone()
        };
        assert_ne!(observe(&a).unwrap(), observe(&b).unwrap());
    }

    #[test]
    fn raw_object_id_renaming_does_not_change_observation() {
        let a = TrueState {
            battlefield: BattlefieldZone::new(vec![
                permanent(10, 1, None),
                permanent(20, 2, Some(10)),
            ]),
            stack: vec![StackObject::ActivatedAbility {
                source: SourceRef {
                    object_id: Some(ObjectId(20)),
                    card: CardDefId(2),
                },
                ability: urza_core::AbilityId(3),
            }],
            ..TrueState::default()
        };
        let b = TrueState {
            battlefield: BattlefieldZone::new(vec![
                permanent(700, 2, Some(900)),
                permanent(900, 1, None),
            ]),
            stack: vec![StackObject::ActivatedAbility {
                source: SourceRef {
                    object_id: Some(ObjectId(700)),
                    card: CardDefId(2),
                },
                ability: urza_core::AbilityId(3),
            }],
            ..TrueState::default()
        };
        assert_eq!(observe(&a).unwrap(), observe(&b).unwrap());
    }

    #[test]
    fn attachment_relationships_survive_structural_projection() {
        let state = TrueState {
            battlefield: BattlefieldZone::new(vec![
                permanent(1, 10, None),
                permanent(2, 11, Some(1)),
            ]),
            ..TrueState::default()
        };
        let info = observe(&state).unwrap();
        let child = info
            .battlefield
            .iter()
            .find(|permanent| permanent.card == CardDefId(11))
            .unwrap();
        let parent = info
            .battlefield
            .iter()
            .find(|permanent| permanent.card == CardDefId(10))
            .unwrap();
        assert_eq!(child.attached_to, Some(parent.canonical_id));
        assert_ne!(child.canonical_id, parent.canonical_id);
    }

    #[test]
    fn symmetric_duplicate_objects_share_a_structural_class() {
        let state = TrueState {
            battlefield: BattlefieldZone::new(vec![
                permanent(100, 12, None),
                permanent(900, 12, None),
            ]),
            ..TrueState::default()
        };
        let info = observe(&state).unwrap();
        assert_eq!(info.battlefield.len(), 2);
        assert_eq!(info.battlefield[0].canonical_id, CanonicalObjectId(0));
        assert_eq!(info.battlefield[0], info.battlefield[1]);
    }

    #[test]
    fn known_bottom_order_remains_observable() {
        let a = TrueState {
            library: TrueLibrary::new(
                vec![CardDefId(9), CardDefId(3), CardDefId(1), CardDefId(2)],
                LibraryKnowledge {
                    known_top: 0,
                    known_bottom: 2,
                },
            )
            .unwrap(),
            ..TrueState::default()
        };
        let b = TrueState {
            library: TrueLibrary::new(
                vec![CardDefId(9), CardDefId(3), CardDefId(2), CardDefId(1)],
                LibraryKnowledge {
                    known_top: 0,
                    known_bottom: 2,
                },
            )
            .unwrap(),
            ..a.clone()
        };
        assert_ne!(observe(&a).unwrap(), observe(&b).unwrap());
    }

    #[test]
    fn permission_execution_ids_are_canonicalized_out_of_observation() {
        use urza_core::{DelayedEvent, PermissionId, UrzaPermission};

        fn world(permission_id: u32) -> TrueState {
            TrueState {
                urza_permissions: vec![UrzaPermission {
                    permission_id: PermissionId(permission_id),
                    card: CardDefId(40),
                    expires_turn: 3,
                    free_cast: true,
                    source: SourceRef {
                        object_id: None,
                        card: CardDefId(94),
                    },
                }],
                delayed_events: vec![DelayedEvent::PermissionExpiry {
                    permission: PermissionId(permission_id),
                    due_turn: 3,
                }],
                ..TrueState::default()
            }
        }

        assert_ne!(ReplayKey::from(&world(10)), ReplayKey::from(&world(99)));
        assert_eq!(observe(&world(10)).unwrap(), observe(&world(99)).unwrap());
    }

    #[test]
    fn future_relevant_payloads_survive_projection() {
        use urza_core::{
            DelayedEvent, ManaPool, PendingDecision, PermissionId, UrzaPermission, Window,
        };

        let mut source_permanent = permanent(55, 22, None);
        source_permanent.tapped = true;
        source_permanent.counters.age = 2;
        source_permanent.counters.lore = 3;

        let source = SourceRef {
            object_id: Some(ObjectId(55)),
            card: CardDefId(22),
        };
        let state = TrueState {
            turn: 3,
            window: Window::UpkeepDecision,
            life: 33,
            battlefield: BattlefieldZone::new(vec![source_permanent]),
            mana: ManaPool {
                blue: 2,
                colorless: 1,
                ..ManaPool::default()
            },
            pending: PendingDecision::CumulativeUpkeepPayment {
                source,
                age_counters: 2,
                generic_per_age: 1,
            },
            delayed_events: vec![
                DelayedEvent::ManaDrainCredit {
                    colorless: 4,
                    due_turn: 4,
                },
                DelayedEvent::PermissionExpiry {
                    permission: PermissionId(7),
                    due_turn: 3,
                },
            ],
            urza_permissions: vec![UrzaPermission {
                permission_id: PermissionId(7),
                card: CardDefId(8),
                expires_turn: 3,
                free_cast: true,
                source,
            }],
            spell_cast_this_turn: true,
            ..TrueState::default()
        };

        let info = observe(&state).unwrap();
        assert_eq!(info.turn, 3);
        assert_eq!(info.window, Window::UpkeepDecision);
        assert_eq!(info.life, 33);
        assert_eq!(info.mana.blue, 2);
        assert_eq!(info.mana.colorless, 1);
        assert!(info.spell_cast_this_turn);
        assert_eq!(info.battlefield[0].counters.age, 2);
        assert_eq!(info.battlefield[0].counters.lore, 3);
        assert!(matches!(
            info.pending,
            super::ObservedPendingDecision::CumulativeUpkeepPayment {
                age_counters: 2,
                generic_per_age: 1,
                ..
            }
        ));
        assert!(info.delayed_events.iter().any(|event| matches!(
            event,
            super::ObservedDelayedEvent::ManaDrainCredit {
                colorless: 4,
                due_turn: 4
            }
        )));
        assert!(info.delayed_events.iter().any(|event| matches!(
            event,
            super::ObservedDelayedEvent::PermissionExpiry {
                permission_slot: 0,
                due_turn: 3
            }
        )));
        assert_eq!(info.urza_permissions.len(), 1);
        assert_eq!(info.urza_permissions[0].permission_slot, 0);
        assert!(info.urza_permissions[0].free_cast);
    }

    #[test]
    fn information_state_json_round_trip_is_exact() {
        let state = TrueState {
            library: TrueLibrary::new(
                vec![CardDefId(1), CardDefId(2), CardDefId(3)],
                LibraryKnowledge {
                    known_top: 1,
                    known_bottom: 1,
                },
            )
            .unwrap(),
            battlefield: BattlefieldZone::new(vec![permanent(5, 8, None)]),
            ..TrueState::default()
        };
        let info = observe(&state).unwrap();
        let encoded = serde_json::to_string(&info).unwrap();
        let decoded: InformationState = serde_json::from_str(&encoded).unwrap();
        assert_eq!(decoded, info);
    }

    #[test]
    fn permanent_face_is_future_relevant_to_observation() {
        let front = TrueState {
            battlefield: BattlefieldZone::new(vec![permanent(1, 34, None)]),
            ..TrueState::default()
        };
        let mut back_permanent = permanent(1, 34, None);
        back_permanent.face = CardFace::Back;
        let back = TrueState {
            battlefield: BattlefieldZone::new(vec![back_permanent]),
            ..TrueState::default()
        };

        assert_ne!(observe(&front).unwrap(), observe(&back).unwrap());
        assert_eq!(observe(&back).unwrap().battlefield[0].face, CardFace::Back);
    }
}
