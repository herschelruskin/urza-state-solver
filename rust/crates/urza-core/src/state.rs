use crate::{AbilityId, CardDefId, ObjectId, PermissionId};

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
pub enum Phase {
    #[default]
    Untap,
    Upkeep,
    Draw,
    PrecombatMain,
    EndStep,
    OpponentCycle,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
pub enum Window {
    #[default]
    None,
    Priority,
    Resolving,
    PostObservation,
    UpkeepDecision,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
pub struct ManaPool {
    pub white: u16,
    pub blue: u16,
    pub black: u16,
    pub red: u16,
    pub green: u16,
    pub colorless: u16,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
#[repr(transparent)]
pub struct GenericCost(pub u16);

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
pub struct CounterState {
    pub plus_one_plus_one: u16,
    pub charge: u16,
    pub burden: u16,
    pub lore: u16,
    pub loyalty: i16,
    pub luck: u8,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
pub enum PermanentMode {
    #[default]
    Normal,
    RealityChipCreature,
    RealityChipAttached,
    UthrosStation,
    UthrosCreature,
    Other(u8),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum GrantedAbility {
    KnackBounceUntilEndOfTurn,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct PermanentState {
    pub object_id: ObjectId,
    pub card: CardDefId,
    pub tapped: bool,
    pub summoning_sick: bool,
    pub token: bool,
    pub counters: CounterState,
    pub mode: PermanentMode,
    pub attached_to: Option<ObjectId>,
    pub granted_ability: Option<GrantedAbility>,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
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
    TriggerOrder,
    ColiseumDiscard,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
pub struct PendingDecision {
    pub kind: PendingDecisionKind,
    pub source: Option<ObjectId>,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum StackObject {
    Spell {
        object_id: ObjectId,
        card: CardDefId,
    },
    ControlledTrigger {
        source: ObjectId,
        ability: AbilityId,
    },
    ActivatedAbility {
        source: ObjectId,
        ability: AbilityId,
    },
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum DelayedEvent {
    BaubleDraw {
        source: ObjectId,
        due_turn: u8,
    },
    ChromeCopySacrifice {
        object: ObjectId,
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

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct UrzaPermission {
    pub permission_id: PermissionId,
    pub card: CardDefId,
    pub expires_turn: u8,
    pub free_cast: bool,
    pub source: ObjectId,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
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

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
pub struct CommanderState {
    pub zone: CommanderZone,
    pub command_zone_casts: u8,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct TrueState {
    pub turn: u8,
    pub phase: Phase,
    pub window: Window,
    pub life: u16,
    pub library: Vec<CardDefId>,
    pub hand: Vec<CardDefId>,
    pub battlefield: Vec<PermanentState>,
    pub graveyard: Vec<CardDefId>,
    pub exile: Vec<CardDefId>,
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
            library: Vec::new(),
            hand: Vec::new(),
            battlefield: Vec::new(),
            graveyard: Vec::new(),
            exile: Vec::new(),
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

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct ReplayKey(pub TrueState);

impl From<&TrueState> for ReplayKey {
    fn from(value: &TrueState) -> Self {
        Self(value.clone())
    }
}

#[cfg(test)]
mod tests {
    use super::{ReplayKey, TrueState};
    use crate::CardDefId;

    #[test]
    fn default_state_tracks_our_life_from_forty() {
        assert_eq!(TrueState::default().life, 40);
    }

    #[test]
    fn replay_identity_retains_hidden_order_and_rng_progression() {
        let a = TrueState {
            library: vec![CardDefId(1), CardDefId(2)],
            ..TrueState::default()
        };

        let mut b = a.clone();
        b.library.reverse();
        assert_ne!(ReplayKey::from(&a), ReplayKey::from(&b));

        let c = TrueState {
            rng_occurrence_cursor: 1,
            ..a.clone()
        };
        assert_ne!(ReplayKey::from(&a), ReplayKey::from(&c));
    }
}
