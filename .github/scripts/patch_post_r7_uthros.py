#!/usr/bin/env python3
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "rust/crates/urza-rules/src/lib.rs"
CARDS = ROOT / "rust/crates/urza-cards/src/lib.rs"
BRIDGE = ROOT / "rust/crates/urza-policy-bridge/src/lib.rs"
COVERAGE = ROOT / "rust/data/card_coverage.r0.json"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def patch_rules() -> None:
    text = RULES.read_text()
    text = replace_once(
        text,
        'pub const POST_R7_RULES_VERSION: &str = "post_r7_card_advantage_v1_ring";',
        'pub const POST_R7_RULES_VERSION: &str = "post_r7_card_advantage_v2_uthros";',
        "rules version",
    )
    text = replace_once(
        text,
        'pub const ABILITY_ONE_RING_UPKEEP: AbilityId = AbilityId(0x040f);',
        'pub const ABILITY_ONE_RING_UPKEEP: AbilityId = AbilityId(0x040f);\n'
        'pub const ABILITY_UTHROS_STATION: AbilityId = AbilityId(0x0410);\n'
        'pub const ABILITY_UTHROS_ARTIFACT_DRAW: AbilityId = AbilityId(0x0411);',
        "Uthros ability ids",
    )
    text = replace_once(
        text,
        '    TheOneRing,\n    GrafdiggersCage,',
        '    TheOneRing,\n    UthrosResearchCraft,\n    GrafdiggersCage,',
        "Uthros utility kind",
    )
    text = replace_once(
        text,
        '    fn clue_token_card(&self) -> Option<CardDefId> {\n        None\n    }\n}',
        '    fn clue_token_card(&self) -> Option<CardDefId> {\n        None\n    }\n\n'
        '    /// Printed/base power data is kept outside CardProfile so frozen R4\n'
        '    /// profile construction remains untouched. Post-R7 mechanics that\n'
        '    /// genuinely need power may opt into this public card-data surface.\n'
        '    fn printed_power(&self, _card: CardDefId) -> Option<i16> {\n'
        '        None\n'
        '    }\n'
        '}',
        "CardDatabase printed power",
    )
    text = replace_once(
        text,
        '    ActivateOneRingDraw {\n        source: ObjectId,\n    },\n    ActivateUrzaSpin {',
        '    ActivateOneRingDraw {\n        source: ObjectId,\n    },\n'
        '    ActivateUthrosStation {\n'
        '        source: ObjectId,\n'
        '        creature: CanonicalObjectId,\n'
        '    },\n'
        '    ActivateUrzaSpin {',
        "Uthros action enum",
    )
    text = replace_once(
        text,
        '        Action::ActivateOneRingDraw { source } => {\n            activate_one_ring_draw(state, cards, source)?;\n            Transition::default()\n        }\n        Action::ActivateUrzaSpin { source, payment } => {',
        '        Action::ActivateOneRingDraw { source } => {\n            activate_one_ring_draw(state, cards, source)?;\n            Transition::default()\n        }\n'
        '        Action::ActivateUthrosStation { source, creature } => {\n'
        '            activate_uthros_station(state, cards, source, creature)?;\n'
        '            Transition::default()\n'
        '        }\n'
        '        Action::ActivateUrzaSpin { source, payment } => {',
        "Uthros apply action",
    )
    ring_fn = '''fn activate_one_ring_draw<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    source: ObjectId,
) -> Result<(), RuleError> {
    ensure_priority(state)?;
    ensure_no_pending_decision(state)?;
    let permanent = battlefield_permanent(state, source)?.clone();
    let profile = card_profile(cards, permanent.card)?;
    if profile.utility != UtilityKind::TheOneRing {
        return Err(RuleError::UnsupportedCardMechanic(permanent.card));
    }
    if permanent.tapped {
        return Err(RuleError::PermanentTapped(source));
    }
    set_tapped(state, source)?;
    state.stack.push(StackObject::ActivatedAbility {
        source: SourceRef {
            object_id: Some(source),
            card: permanent.card,
        },
        ability: ABILITY_ONE_RING_DRAW,
        // Snapshot supports the ordinary leave-before-resolution LKI case.
        // More exotic interleavings that change burden before the source
        // leaves are explicitly outside this primitive slice.
        parameter: Some(permanent.counters.burden),
    });
    state.window = Window::Priority;
    Ok(())
}
'''
    uthros_activate = ring_fn + '''
fn activate_uthros_station<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    source: ObjectId,
    creature: CanonicalObjectId,
) -> Result<(), RuleError> {
    ensure_sorcery_window(state)?;
    let craft = battlefield_permanent(state, source)?.clone();
    if card_profile(cards, craft.card)?.utility != UtilityKind::UthrosResearchCraft {
        return Err(RuleError::UnsupportedCardMechanic(craft.card));
    }
    let creature_id = resolve_canonical_object(state, creature)
        .map_err(|error| match error {
            urza_info::ObservationError::InvalidState(error) => RuleError::InvalidState(error),
        })?
        .ok_or(RuleError::MissingCanonicalPermanent(creature))?;
    if creature_id == source {
        return Err(RuleError::InvalidPermanentTarget);
    }
    let tapped_creature = battlefield_permanent(state, creature_id)?.clone();
    if !permanent_is_creature(cards, &tapped_creature)? {
        return Err(RuleError::InvalidPermanentTarget);
    }
    if tapped_creature.tapped {
        return Err(RuleError::PermanentTapped(creature_id));
    }
    let power_snapshot = current_creature_power(state, cards, &tapped_creature)?.max(0);
    let power_snapshot = u16::try_from(power_snapshot).map_err(|_| RuleError::ArithmeticOverflow)?;
    set_tapped(state, creature_id)?;
    state.stack.push(StackObject::TargetedActivatedAbility {
        source: SourceRef {
            object_id: Some(source),
            card: craft.card,
        },
        ability: ABILITY_UTHROS_STATION,
        target: SourceRef {
            object_id: Some(creature_id),
            card: tapped_creature.card,
        },
        // Station reads power on resolution. This snapshot is used only if the
        // tapped creature leaves first, matching the official LKI rule for station.
        parameter: Some(power_snapshot),
    });
    state.window = Window::Priority;
    Ok(())
}
'''
    text = replace_once(text, ring_fn, uthros_activate, "Uthros activation function")

    text = replace_once(
        text,
        '''        StackObject::ActivatedAbility {
            source,
            ability: ABILITY_ONE_RING_UPKEEP,
            parameter,
        } => {
            state.stack.pop();
            resolve_one_ring_upkeep(state, cards, source, parameter)
        }
        StackObject::ActivatedAbility {
            source,
            ability: ABILITY_URZA_SPIN,
''',
        '''        StackObject::ActivatedAbility {
            source,
            ability: ABILITY_ONE_RING_UPKEEP,
            parameter,
        } => {
            state.stack.pop();
            resolve_one_ring_upkeep(state, cards, source, parameter)
        }
        StackObject::TargetedActivatedAbility {
            source,
            ability: ABILITY_UTHROS_STATION,
            target,
            parameter,
        } => {
            state.stack.pop();
            resolve_uthros_station(state, cards, source, target, parameter)
        }
        StackObject::ControlledTrigger {
            source,
            ability: ABILITY_UTHROS_ARTIFACT_DRAW,
        } => {
            state.stack.pop();
            resolve_uthros_artifact_draw(state, cards, source)
        }
        StackObject::ActivatedAbility {
            source,
            ability: ABILITY_URZA_SPIN,
''',
        "Uthros resolver dispatch",
    )

    ring_upkeep_fn = '''fn resolve_one_ring_upkeep<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    source: SourceRef,
    snapshot: Option<u16>,
) -> Result<Transition, RuleError> {
    let burden = if let Some(source_id) = source.object_id
        && let Some(permanent) = state.battlefield.get(source_id)
        && permanent.card == source.card
        && card_profile(cards, permanent.card)?.utility == UtilityKind::TheOneRing
    {
        permanent.counters.burden
    } else {
        snapshot.unwrap_or(0)
    };
    state.life = state.life.saturating_sub(burden);
    state.window = Window::Priority;
    Ok(Transition::default())
}
'''
    uthros_resolve = ring_upkeep_fn + '''
fn resolve_uthros_station<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    source: SourceRef,
    target: SourceRef,
    snapshot: Option<u16>,
) -> Result<Transition, RuleError> {
    let power = if let Some(target_id) = target.object_id
        && let Some(permanent) = state.battlefield.get(target_id).cloned()
        && permanent.card == target.card
        && permanent_is_creature(cards, &permanent)?
    {
        current_creature_power(state, cards, &permanent)?.max(0)
    } else {
        i16::try_from(snapshot.unwrap_or(0)).map_err(|_| RuleError::ArithmeticOverflow)?
    };
    let counters = u16::try_from(power).map_err(|_| RuleError::ArithmeticOverflow)?;

    if let Some(source_id) = source.object_id
        && let Some(permanent) = state.battlefield.get(source_id).cloned()
        && permanent.card == source.card
        && card_profile(cards, permanent.card)?.utility == UtilityKind::UthrosResearchCraft
    {
        let next = permanent
            .counters
            .charge
            .checked_add(counters)
            .ok_or(RuleError::ArithmeticOverflow)?;
        let mut permanents = state.battlefield.permanents().to_vec();
        let live = permanents
            .iter_mut()
            .find(|candidate| candidate.object_id == source_id)
            .ok_or(RuleError::MissingPermanent(source_id))?;
        live.counters.charge = next;
        state.battlefield = BattlefieldZone::new(permanents);
    }
    state.window = Window::Priority;
    Ok(Transition::default())
}

fn resolve_uthros_artifact_draw<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    source: SourceRef,
) -> Result<Transition, RuleError> {
    let drawn = draw_cards(state, 1)?;
    if let Some(source_id) = source.object_id
        && let Some(permanent) = state.battlefield.get(source_id).cloned()
        && permanent.card == source.card
        && card_profile(cards, permanent.card)?.utility == UtilityKind::UthrosResearchCraft
    {
        let next = permanent
            .counters
            .charge
            .checked_add(1)
            .ok_or(RuleError::ArithmeticOverflow)?;
        let mut permanents = state.battlefield.permanents().to_vec();
        let live = permanents
            .iter_mut()
            .find(|candidate| candidate.object_id == source_id)
            .ok_or(RuleError::MissingPermanent(source_id))?;
        live.counters.charge = next;
        state.battlefield = BattlefieldZone::new(permanents);
    }
    state.window = Window::Priority;
    Ok(Transition {
        observations: if drawn.is_empty() {
            Vec::new()
        } else {
            vec![RulesObservation::CardsDrawn(drawn)]
        },
    })
}
'''
    text = replace_once(text, ring_upkeep_fn, uthros_resolve, "Uthros resolution functions")

    queue_anchor = '''        if cast_profile.is_artifact && profile.engine == EngineKind::ForensicGadgeteer {
            triggers.push(StackObject::ControlledTrigger {
                source: SourceRef {
                    object_id: Some(permanent.object_id),
                    card: permanent.card,
                },
                ability: ABILITY_GADGETEER_INVESTIGATE,
            });
        }
'''
    queue_new = queue_anchor + '''        if cast_profile.is_artifact
            && profile.utility == UtilityKind::UthrosResearchCraft
            && permanent.counters.charge >= 3
        {
            triggers.push(StackObject::ControlledTrigger {
                source: SourceRef {
                    object_id: Some(permanent.object_id),
                    card: permanent.card,
                },
                ability: ABILITY_UTHROS_ARTIFACT_DRAW,
            });
        }
'''
    text = replace_once(text, queue_anchor, queue_new, "Uthros cast trigger")

    text = replace_once(
        text,
        '''fn initial_permanent_mode(profile: CardProfile) -> PermanentMode {
    match profile.utility {
        UtilityKind::RealityChip => PermanentMode::RealityChipCreature,
        UtilityKind::FortuneTellersTalent => PermanentMode::FortuneTellersTalentLevel1,
        _ => PermanentMode::Normal,
    }
}
''',
        '''fn initial_permanent_mode(profile: CardProfile) -> PermanentMode {
    match profile.utility {
        UtilityKind::RealityChip => PermanentMode::RealityChipCreature,
        UtilityKind::FortuneTellersTalent => PermanentMode::FortuneTellersTalentLevel1,
        UtilityKind::UthrosResearchCraft => PermanentMode::UthrosStation,
        _ => PermanentMode::Normal,
    }
}
''',
        "Uthros initial mode",
    )

    creature_helper = '''fn permanent_is_creature<D: CardDatabase>(
    cards: &D,
    permanent: &PermanentState,
) -> Result<bool, RuleError> {
    let profile = card_profile(cards, permanent.card)?;
    if profile.utility == UtilityKind::RealityChip
        && permanent.mode == PermanentMode::RealityChipAttached
    {
        return Ok(false);
    }
    Ok(profile.is_creature)
}
'''
    power_helper = creature_helper + '''
fn current_creature_power<D: CardDatabase>(
    state: &TrueState,
    cards: &D,
    permanent: &PermanentState,
) -> Result<i16, RuleError> {
    if !permanent_is_creature(cards, permanent)? {
        return Err(RuleError::InvalidPermanentTarget);
    }
    let base = if permanent.card == cards.urza_construct_token_card() {
        let artifacts = state
            .battlefield
            .permanents()
            .iter()
            .filter(|candidate| {
                cards
                    .profile(candidate.card)
                    .is_some_and(|profile| profile.is_artifact)
            })
            .count();
        i16::try_from(artifacts).map_err(|_| RuleError::ArithmeticOverflow)?
    } else {
        cards
            .printed_power(permanent.card)
            .ok_or(RuleError::UnsupportedCardMechanic(permanent.card))?
    };
    let counters = i16::try_from(permanent.counters.plus_one_plus_one)
        .map_err(|_| RuleError::ArithmeticOverflow)?;
    base.checked_add(counters)
        .ok_or(RuleError::ArithmeticOverflow)
}
'''
    text = replace_once(text, creature_helper, power_helper, "creature power helper")

    # Append focused Uthros rules tests after the Ring module.
    uthros_tests = r'''

#[cfg(test)]
mod post_r7_uthros_tests {
    use std::collections::BTreeMap;

    use super::*;

    const UTHROS: CardDefId = CardDefId(520);
    const CREATURE: CardDefId = CardDefId(521);
    const ARTIFACT: CardDefId = CardDefId(522);
    const DRAW_A: CardDefId = CardDefId(523);
    const DRAW_B: CardDefId = CardDefId(524);
    const URZA_DUMMY: CardDefId = CardDefId(525);
    const CONSTRUCT: CardDefId = CardDefId(526);

    #[derive(Default)]
    struct UthrosCards {
        profiles: BTreeMap<CardDefId, CardProfile>,
    }

    impl UthrosCards {
        fn new() -> Self {
            let mut profiles = BTreeMap::new();
            profiles.insert(
                UTHROS,
                CardProfile {
                    card: UTHROS,
                    mana_cost: Some(ManaCost {
                        generic: 2,
                        blue: 1,
                        ..ManaCost::default()
                    }),
                    mana_value: 3,
                    role: R2CardRole::ArtifactPermanent,
                    battlefield_face: CardFace::Front,
                    utility: UtilityKind::UthrosResearchCraft,
                    is_artifact: true,
                    ..CardProfile::default()
                },
            );
            profiles.insert(
                CREATURE,
                CardProfile {
                    card: CREATURE,
                    role: R2CardRole::CreaturePermanent,
                    battlefield_face: CardFace::Front,
                    is_creature: true,
                    ..CardProfile::default()
                },
            );
            profiles.insert(
                ARTIFACT,
                CardProfile {
                    card: ARTIFACT,
                    mana_cost: Some(ManaCost::default()),
                    mana_value: 0,
                    role: R2CardRole::ArtifactPermanent,
                    battlefield_face: CardFace::Front,
                    is_artifact: true,
                    ..CardProfile::default()
                },
            );
            profiles.insert(
                CONSTRUCT,
                CardProfile {
                    card: CONSTRUCT,
                    role: R2CardRole::UrzaConstructToken,
                    battlefield_face: CardFace::Front,
                    is_artifact: true,
                    is_creature: true,
                    ..CardProfile::default()
                },
            );
            Self { profiles }
        }
    }

    impl CardDatabase for UthrosCards {
        fn profile(&self, card: CardDefId) -> Option<CardProfile> {
            self.profiles.get(&card).copied()
        }

        fn commander_card(&self) -> CardDefId {
            URZA_DUMMY
        }

        fn urza_construct_token_card(&self) -> CardDefId {
            CONSTRUCT
        }

        fn printed_power(&self, card: CardDefId) -> Option<i16> {
            (card == CREATURE).then_some(3)
        }
    }

    fn permanent(object: u32, card: CardDefId) -> PermanentState {
        PermanentState {
            object_id: ObjectId(object),
            card,
            face: CardFace::Front,
            tapped: false,
            summoning_sick: false,
            token: false,
            counters: CounterState::default(),
            mode: if card == UTHROS {
                PermanentMode::UthrosStation
            } else {
                PermanentMode::Normal
            },
            attached_to: None,
            granted_ability: None,
        }
    }

    #[test]
    fn uthros_station_taps_another_creature_and_adds_power_on_resolution() {
        let cards = UthrosCards::new();
        let mut state = TrueState {
            turn: 2,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            battlefield: BattlefieldZone::new(vec![
                permanent(1, UTHROS),
                permanent(2, CREATURE),
            ]),
            ..TrueState::default()
        };
        let creature = urza_info::observe(&state)
            .unwrap()
            .battlefield
            .iter()
            .find(|permanent| permanent.card == CREATURE)
            .unwrap()
            .canonical_id;

        apply_action(
            &mut state,
            &cards,
            Action::ActivateUthrosStation {
                source: ObjectId(1),
                creature,
            },
        )
        .unwrap();
        assert!(state.battlefield.get(ObjectId(2)).unwrap().tapped);
        assert_eq!(state.battlefield.get(ObjectId(1)).unwrap().counters.charge, 0);
        assert!(matches!(
            state.stack.last(),
            Some(StackObject::TargetedActivatedAbility {
                ability: ABILITY_UTHROS_STATION,
                parameter: Some(3),
                ..
            })
        ));

        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(state.battlefield.get(ObjectId(1)).unwrap().counters.charge, 3);
    }

    #[test]
    fn uthros_three_plus_artifact_cast_draws_then_adds_charge_before_spell_resolves() {
        let cards = UthrosCards::new();
        let mut uthros = permanent(1, UTHROS);
        uthros.counters.charge = 3;
        let mut state = TrueState {
            turn: 2,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(vec![DRAW_A, DRAW_B]),
            hand: CardZone::new(vec![ARTIFACT]),
            battlefield: BattlefieldZone::new(vec![uthros]),
            ..TrueState::default()
        };

        apply_action(
            &mut state,
            &cards,
            Action::CastFromHand {
                card: ARTIFACT,
                payment: ManaPayment::default(),
            },
        )
        .unwrap();
        assert_eq!(state.stack.len(), 2);
        assert!(matches!(
            state.stack.last(),
            Some(StackObject::ControlledTrigger {
                ability: ABILITY_UTHROS_ARTIFACT_DRAW,
                ..
            })
        ));

        let draw = apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(draw.observations, vec![RulesObservation::CardsDrawn(vec![DRAW_A])]);
        assert_eq!(state.hand.cards(), &[DRAW_A]);
        assert_eq!(state.battlefield.get(ObjectId(1)).unwrap().counters.charge, 4);
        assert_eq!(state.stack.len(), 1, "artifact spell remains below Uthros trigger");

        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert!(state
            .battlefield
            .permanents()
            .iter()
            .any(|permanent| permanent.card == ARTIFACT));
    }

    #[test]
    fn uthros_below_three_does_not_trigger_on_artifact_cast() {
        let cards = UthrosCards::new();
        let mut uthros = permanent(1, UTHROS);
        uthros.counters.charge = 2;
        let mut state = TrueState {
            turn: 2,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(vec![DRAW_A]),
            hand: CardZone::new(vec![ARTIFACT]),
            battlefield: BattlefieldZone::new(vec![uthros]),
            ..TrueState::default()
        };
        apply_action(
            &mut state,
            &cards,
            Action::CastFromHand {
                card: ARTIFACT,
                payment: ManaPayment::default(),
            },
        )
        .unwrap();
        assert_eq!(state.stack.len(), 1);
        assert!(matches!(state.stack.last(), Some(StackObject::Spell { .. })));
    }
}
'''
    if "mod post_r7_uthros_tests" not in text:
        text = text.rstrip() + uthros_tests + "\n"
    RULES.write_text(text)


def patch_cards() -> None:
    text = CARDS.read_text()
    text = replace_once(
        text,
        'pub const POST_R7_ACCEPTED_ACTIVE_IDENTITY_COUNT: usize = 48;\n'
        'pub const POST_R7_CARD_DATABASE_VERSION: &str = "post_r7_card_advantage_v1_ring";',
        'pub const POST_R7_ACCEPTED_ACTIVE_IDENTITY_COUNT: usize = 49;\n'
        'pub const POST_R7_CARD_DATABASE_VERSION: &str = "post_r7_card_advantage_v2_uthros";',
        "post-R7 cards version/count",
    )
    text = replace_once(
        text,
        '''#[derive(Debug, Clone)]
pub struct PostR7CardDatabase {
    cards: BTreeMap<CardDefId, urza_rules::CardProfile>,
}
''',
        '''#[derive(Debug, Clone)]
pub struct PostR7CardDatabase {
    cards: BTreeMap<CardDefId, urza_rules::CardProfile>,
    printed_powers: BTreeMap<CardDefId, i16>,
}
''',
        "post-R7 database power field",
    )
    text = replace_once(
        text,
        '''        profile.role = urza_rules::R2CardRole::ArtifactPermanent;
        profile.utility = urza_rules::UtilityKind::TheOneRing;
        profile.is_artifact = true;
        Ok(Self { cards })
    }
''',
        '''        profile.role = urza_rules::R2CardRole::ArtifactPermanent;
        profile.utility = urza_rules::UtilityKind::TheOneRing;
        profile.is_artifact = true;

        let uthros = card_id_by_name_from_r1("Uthros Research Craft")?;
        let uthros_profile = cards.get_mut(&uthros).ok_or_else(|| {
            CatalogError::Invariant("missing post-R7 Uthros Research Craft profile".to_owned())
        })?;
        uthros_profile.role = urza_rules::R2CardRole::ArtifactPermanent;
        uthros_profile.utility = urza_rules::UtilityKind::UthrosResearchCraft;
        uthros_profile.is_artifact = true;

        // Public printed powers used by Station. Keeping this table in the
        // current database avoids mutating the frozen R1 metadata schema/digest.
        // Dynamic Construct power is computed by urza-rules instead.
        let mut printed_powers = BTreeMap::new();
        for (name, power) in [
            ("Artificer's Assistant", 1_i16),
            ("Battered Golem", 3),
            ("Chrome Dome", 1),
            ("Faerie Mastermind", 2),
            ("Forensic Gadgeteer", 2),
            ("Hope of Ghirapur", 1),
            ("Hydroelectric Specimen", 1),
            ("Spellseeker", 1),
            ("Spellskite", 0),
            ("The Reality Chip", 0),
            ("Urza, Lord High Artificer", 1),
            ("Valley Floodcaller", 2),
        ] {
            printed_powers.insert(card_id_by_name_from_r1(name)?, power);
        }
        Ok(Self {
            cards,
            printed_powers,
        })
    }
''',
        "activate Uthros and power data",
    )
    text = replace_once(
        text,
        '''    pub fn supported_active_cards(&self) -> Vec<CardDefId> {
        self.cards
            .iter()
            .filter_map(|(card, profile)| {
                (card.0 < URZA_CONSTRUCT_TOKEN_CARD_ID.0
                    && profile.role != urza_rules::R2CardRole::Unsupported)
                    .then_some(*card)
            })
            .collect()
    }
}

impl urza_rules::CardDatabase for PostR7CardDatabase {
''',
        '''    pub fn supported_active_cards(&self) -> Vec<CardDefId> {
        self.cards
            .iter()
            .filter_map(|(card, profile)| {
                (card.0 < URZA_CONSTRUCT_TOKEN_CARD_ID.0
                    && profile.role != urza_rules::R2CardRole::Unsupported)
                    .then_some(*card)
            })
            .collect()
    }

    pub fn printed_power(&self, card: CardDefId) -> Option<i16> {
        self.printed_powers.get(&card).copied()
    }
}

impl urza_rules::CardDatabase for PostR7CardDatabase {
''',
        "post-R7 inherent printed power",
    )
    text = replace_once(
        text,
        '''    fn clue_token_card(&self) -> Option<CardDefId> {
        Some(CLUE_TOKEN_CARD_ID)
    }
}

fn card_id_by_name_from_r1''',
        '''    fn clue_token_card(&self) -> Option<CardDefId> {
        Some(CLUE_TOKEN_CARD_ID)
    }

    fn printed_power(&self, card: CardDefId) -> Option<i16> {
        self.printed_power(card)
    }
}

fn card_id_by_name_from_r1''',
        "post-R7 trait printed power",
    )
    text = replace_once(
        text,
        '''    let added: BTreeSet<_> = supported.difference(&r4_supported).copied().collect();
    let ring = card_id_by_name_from_r1("The One Ring")?;
    if added != BTreeSet::from([ring]) {
        return Err(CatalogError::Invariant(format!(
            "first post-R7 slice must add only The One Ring, got {added:?}"
        )));
    }
''',
        '''    let added: BTreeSet<_> = supported.difference(&r4_supported).copied().collect();
    let ring = card_id_by_name_from_r1("The One Ring")?;
    let uthros = card_id_by_name_from_r1("Uthros Research Craft")?;
    if added != BTreeSet::from([ring, uthros]) {
        return Err(CatalogError::Invariant(format!(
            "post-R7 card-advantage surface must add exactly Ring and Uthros, got {added:?}"
        )));
    }
''',
        "post-R7 added identities",
    )
    text = replace_once(
        text,
        '''    if !matches!(
        ring_coverage.status,
        CoverageStatus::PrimitiveActive | CoverageStatus::RulesActive
    ) {
        return Err(CatalogError::Invariant(
            "The One Ring must be active in post-R7 coverage".to_owned(),
        ));
    }
    Ok(())
}
''',
        '''    if !matches!(
        ring_coverage.status,
        CoverageStatus::PrimitiveActive | CoverageStatus::RulesActive
    ) {
        return Err(CatalogError::Invariant(
            "The One Ring must be active in post-R7 coverage".to_owned(),
        ));
    }
    let uthros_coverage = coverage
        .entries
        .iter()
        .find(|entry| entry.card_id == uthros.0)
        .ok_or_else(|| CatalogError::Invariant("missing Uthros coverage entry".to_owned()))?;
    if !matches!(
        uthros_coverage.status,
        CoverageStatus::PrimitiveActive | CoverageStatus::RulesActive
    ) {
        return Err(CatalogError::Invariant(
            "Uthros Research Craft must be active in post-R7 coverage".to_owned(),
        ));
    }
    Ok(())
}
''',
        "Uthros coverage validation",
    )
    text = replace_once(
        text,
        '''    #[test]
    fn post_r7_database_extends_frozen_r4_with_only_the_one_ring() {
        validate_post_r7_database().unwrap();
        let r4 = R4CardDatabase::load().unwrap();
        let current = PostR7CardDatabase::load().unwrap();
        assert_eq!(r4.supported_active_cards().len(), 47);
        assert_eq!(current.supported_active_cards().len(), 48);
        let ring = current.card_id_by_name("The One Ring").unwrap();
        assert_eq!(
            r4.profile(ring).unwrap().role,
            urza_rules::R2CardRole::Unsupported
        );
        let profile = current.profile(ring).unwrap();
        assert_eq!(profile.role, urza_rules::R2CardRole::ArtifactPermanent);
        assert_eq!(profile.utility, urza_rules::UtilityKind::TheOneRing);
        assert!(profile.is_artifact);
        assert_eq!(profile.mana_value, 4);
    }
''',
        '''    #[test]
    fn post_r7_database_extends_frozen_r4_with_ring_and_uthros() {
        validate_post_r7_database().unwrap();
        let r4 = R4CardDatabase::load().unwrap();
        let current = PostR7CardDatabase::load().unwrap();
        assert_eq!(r4.supported_active_cards().len(), 47);
        assert_eq!(current.supported_active_cards().len(), 49);
        let ring = current.card_id_by_name("The One Ring").unwrap();
        assert_eq!(
            r4.profile(ring).unwrap().role,
            urza_rules::R2CardRole::Unsupported
        );
        let profile = current.profile(ring).unwrap();
        assert_eq!(profile.role, urza_rules::R2CardRole::ArtifactPermanent);
        assert_eq!(profile.utility, urza_rules::UtilityKind::TheOneRing);
        assert!(profile.is_artifact);
        assert_eq!(profile.mana_value, 4);

        let uthros = current.card_id_by_name("Uthros Research Craft").unwrap();
        assert_eq!(
            r4.profile(uthros).unwrap().role,
            urza_rules::R2CardRole::Unsupported
        );
        let uthros_profile = current.profile(uthros).unwrap();
        assert_eq!(uthros_profile.role, urza_rules::R2CardRole::ArtifactPermanent);
        assert_eq!(
            uthros_profile.utility,
            urza_rules::UtilityKind::UthrosResearchCraft
        );
        assert!(uthros_profile.is_artifact);
        assert_eq!(uthros_profile.mana_value, 3);
        let gadgeteer = current.card_id_by_name("Forensic Gadgeteer").unwrap();
        assert_eq!(current.printed_power(gadgeteer), Some(2));
    }
''',
        "post-R7 database test",
    )
    CARDS.write_text(text)


def patch_bridge() -> None:
    text = BRIDGE.read_text()
    text = replace_once(
        text,
        'pub const CANDIDATE_BRIDGE_VERSION: &str = "post_r7_public_candidate_bridge_v1_ring";\n'
        'pub const ORDINARY_ACTION_FAMILY_COUNT: usize = 27;',
        'pub const CANDIDATE_BRIDGE_VERSION: &str = "post_r7_public_candidate_bridge_v2_uthros";\n'
        'pub const ORDINARY_ACTION_FAMILY_COUNT: usize = 28;',
        "bridge version/count",
    )
    text = replace_once(
        text,
        'const KIND_ONE_RING_DRAW: u16 = 35;',
        'const KIND_ONE_RING_DRAW: u16 = 35;\nconst KIND_UTHROS_STATION: u16 = 36;',
        "Uthros policy key",
    )
    text = replace_once(
        text,
        '''            UtilityKind::TheOneRing => {
                actions.push(Action::ActivateOneRingDraw {
                    source: representative,
                });
            }
            _ => {}
''',
        '''            UtilityKind::TheOneRing => {
                actions.push(Action::ActivateOneRingDraw {
                    source: representative,
                });
            }
            UtilityKind::UthrosResearchCraft => {
                for creature in &creature_targets {
                    actions.push(Action::ActivateUthrosStation {
                        source: representative,
                        creature: *creature,
                    });
                }
            }
            _ => {}
''',
        "generate Uthros station candidates",
    )
    text = replace_once(
        text,
        '''        | Action::ActivateFortuneTellersTalentLevel { .. }
        | Action::ActivateOneRingDraw { .. } => PolicyActionClass::ActivateAbility,
''',
        '''        | Action::ActivateFortuneTellersTalentLevel { .. }
        | Action::ActivateOneRingDraw { .. }
        | Action::ActivateUthrosStation { .. } => PolicyActionClass::ActivateAbility,
''',
        "classify Uthros",
    )
    text = replace_once(
        text,
        '''        Action::ActivateOneRingDraw { source } => source_key(
            KIND_ONE_RING_DRAW,
            *source,
            state,
            object_classes,
            Vec::new(),
        )?,
''',
        '''        Action::ActivateOneRingDraw { source } => source_key(
            KIND_ONE_RING_DRAW,
            *source,
            state,
            object_classes,
            Vec::new(),
        )?,
        Action::ActivateUthrosStation { source, creature } => {
            let mut out = source_key(
                KIND_UTHROS_STATION,
                *source,
                state,
                object_classes,
                Vec::new(),
            )?;
            out.target = Some(*creature);
            out
        }
''',
        "Uthros public key",
    )
    text = replace_once(
        text,
        '''    fn bridge_surface_counts_match_the_exhaustive_action_mapping() {
        assert_eq!(ORDINARY_ACTION_FAMILY_COUNT, 27);
        assert_eq!(CONTINGENT_ACTION_FAMILY_COUNT, 8);
    }
''',
        '''    fn bridge_surface_counts_match_the_exhaustive_action_mapping() {
        assert_eq!(ORDINARY_ACTION_FAMILY_COUNT, 28);
        assert_eq!(CONTINGENT_ACTION_FAMILY_COUNT, 8);
    }
''',
        "bridge family count test",
    )
    ring_test_end = '''    #[test]
    fn real_r4_database_still_exposes_only_accepted_profiles_to_bridge() {
'''
    uthros_test = '''    #[test]
    fn post_r7_uthros_station_is_exposed_for_an_untapped_creature() {
        let cards = PostR7CardDatabase::load().unwrap();
        let uthros = cards.card_id_by_name("Uthros Research Craft").unwrap();
        let gadgeteer = cards.card_id_by_name("Forensic Gadgeteer").unwrap();
        let mut state = priority_state();
        state.battlefield = BattlefieldZone::new(vec![
            permanent(7, uthros),
            permanent(8, gadgeteer),
        ]);

        let bridge = CandidateBridge::build(&state, &cards).unwrap();
        let actions = bridge
            .candidates()
            .iter()
            .filter(|candidate| candidate.key.kind == KIND_UTHROS_STATION)
            .collect::<Vec<_>>();
        assert_eq!(actions.len(), 1);
        assert_eq!(actions[0].class, PolicyActionClass::ActivateAbility);
        assert!(matches!(
            bridge.resolve(actions[0].token),
            Some(Action::ActivateUthrosStation { .. })
        ));

        let mut permanents = state.battlefield.permanents().to_vec();
        permanents
            .iter_mut()
            .find(|permanent| permanent.card == gadgeteer)
            .unwrap()
            .tapped = true;
        state.battlefield = BattlefieldZone::new(permanents);
        let tapped_bridge = CandidateBridge::build(&state, &cards).unwrap();
        assert!(tapped_bridge
            .candidates()
            .iter()
            .all(|candidate| candidate.key.kind != KIND_UTHROS_STATION));
    }

'''
    text = replace_once(text, ring_test_end, uthros_test + ring_test_end, "Uthros bridge test")
    BRIDGE.write_text(text)


def patch_coverage() -> None:
    data = json.loads(COVERAGE.read_text())
    entry = next(item for item in data["entries"] if item["card_id"] == 88)
    entry["status"] = "PRIMITIVE_ACTIVE"
    entry["reason"] = (
        "Post-R7 second-pass Uthros primitive: normal artifact cast, sorcery-speed station by "
        "tapping another untapped creature, charge counters from current modeled power with the "
        "official leave-before-resolution LKI fallback, and the 3+ artifact-cast draw-then-charge "
        "trigger are modeled. The 12+ creature/flying/power striation and otherwise unmodeled "
        "temporary/static power modifiers remain deferred."
    )
    COVERAGE.write_text(json.dumps(data, indent=2) + "\n")


patch_rules()
patch_cards()
patch_bridge()
patch_coverage()
print("post-R7 Uthros card-advantage slice patched")
