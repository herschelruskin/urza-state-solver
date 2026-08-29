#![forbid(unsafe_code)]

use urza_core::{
    AbilityId, CardDefId, CommanderState, CounterState, GrantedAbility, ManaPool,
    PendingDecisionKind, PermanentMode, Phase, Window,
};

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord, Hash)]
#[repr(transparent)]
pub struct CanonicalObjectId(pub u16);

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
pub struct CardCount {
    pub card: CardDefId,
    pub count: u8,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Hash)]
pub struct LibraryBelief {
    pub remaining_counts: Vec<CardCount>,
    pub known_top: Vec<CardDefId>,
    pub known_bottom: Vec<CardDefId>,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct ObservedPermanent {
    pub canonical_id: CanonicalObjectId,
    pub card: CardDefId,
    pub tapped: bool,
    pub summoning_sick: bool,
    pub token: bool,
    pub counters: CounterState,
    pub mode: PermanentMode,
    pub attached_to: Option<CanonicalObjectId>,
    pub granted_ability: Option<GrantedAbility>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ObservedStackKind {
    Spell,
    ControlledTrigger,
    ActivatedAbility,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct ObservedStackObject {
    pub kind: ObservedStackKind,
    pub card: Option<CardDefId>,
    pub source: Option<CanonicalObjectId>,
    pub ability: Option<AbilityId>,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum ObservedDelayedEvent {
    BaubleDraw {
        source: CanonicalObjectId,
        due_turn: u8,
    },
    ChromeCopySacrifice {
        object: CanonicalObjectId,
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

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct ObservedPermission {
    pub permission_slot: u16,
    pub card: CardDefId,
    pub expires_turn: u8,
    pub free_cast: bool,
    pub source: CanonicalObjectId,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
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
    pub pending: PendingDecisionKind,
    pub delayed_events: Vec<ObservedDelayedEvent>,
    pub urza_permissions: Vec<ObservedPermission>,
    pub spell_cast_this_turn: bool,
    pub saga_iii_pending: bool,
    pub remora_age: u8,
    pub remora_upkeep_pending: bool,
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
            pending: PendingDecisionKind::None,
            delayed_events: Vec::new(),
            urza_permissions: Vec::new(),
            spell_cast_this_turn: false,
            saga_iii_pending: false,
            remora_age: 0,
            remora_upkeep_pending: false,
        }
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
    use super::{CardCount, InformationState, PolicyView};
    use urza_core::CardDefId;

    #[test]
    fn policy_view_exposes_belief_not_true_library_order() {
        let mut info = InformationState::default();
        info.library.remaining_counts = vec![CardCount {
            card: CardDefId(7),
            count: 2,
        }];
        info.library.known_top = vec![CardDefId(9)];
        let view = PolicyView::new(&info);
        assert_eq!(view.library_belief().known_top, vec![CardDefId(9)]);
        assert_eq!(view.library_belief().remaining_counts[0].count, 2);
    }
}
