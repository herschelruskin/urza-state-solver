from __future__ import annotations

import json
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"{path}: replacement anchor not found:\n{old[:240]}")
    path.write_text(text.replace(old, new, 1))


def insert_before(path: Path, anchor: str, addition: str) -> None:
    text = path.read_text()
    if addition in text:
        return
    if anchor not in text:
        raise SystemExit(f"{path}: insertion anchor not found: {anchor!r}")
    path.write_text(text.replace(anchor, addition + anchor, 1))


rules = Path("rust/crates/urza-rules/src/lib.rs")
cards = Path("rust/crates/urza-cards/src/lib.rs")
bridge = Path("rust/crates/urza-policy-bridge/src/lib.rs")
coverage = Path("rust/data/card_coverage.r0.json")

# ---- Rules surface ---------------------------------------------------------
replace_once(
    rules,
    'pub const RULES_VERSION: &str = "r4_acceptance_v6";',
    'pub const RULES_VERSION: &str = "post_r7_card_advantage_v1_ring";',
)
replace_once(
    rules,
    'pub const ABILITY_KNACK_BOUNCE: AbilityId = AbilityId(0x040d);\n',
    'pub const ABILITY_KNACK_BOUNCE: AbilityId = AbilityId(0x040d);\n'
    'pub const ABILITY_ONE_RING_DRAW: AbilityId = AbilityId(0x040e);\n'
    'pub const ABILITY_ONE_RING_UPKEEP: AbilityId = AbilityId(0x040f);\n',
)
replace_once(
    rules,
    '    FortuneTellersTalent,\n    GrafdiggersCage,\n',
    '    FortuneTellersTalent,\n    TheOneRing,\n    GrafdiggersCage,\n',
)
replace_once(
    rules,
    '    ActivateTopDraw {\n        source: ObjectId,\n    },\n    ActivateUrzaSpin {\n',
    '    ActivateTopDraw {\n        source: ObjectId,\n    },\n'
    '    ActivateOneRingDraw {\n        source: ObjectId,\n    },\n'
    '    ActivateUrzaSpin {\n',
)
replace_once(
    rules,
    '        Action::ActivateTopDraw { source } => {\n            activate_top_draw(state, cards, source)?;\n            Transition::default()\n        }\n        Action::ActivateUrzaSpin { source, payment } => {\n',
    '        Action::ActivateTopDraw { source } => {\n            activate_top_draw(state, cards, source)?;\n            Transition::default()\n        }\n'
    '        Action::ActivateOneRingDraw { source } => {\n            activate_one_ring_draw(state, cards, source)?;\n            Transition::default()\n        }\n'
    '        Action::ActivateUrzaSpin { source, payment } => {\n',
)

insert_before(
    rules,
    'fn activate_urza_spin<D: CardDatabase>(\n',
    '''fn activate_one_ring_draw<D: CardDatabase>(
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

''',
)

replace_once(
    rules,
    '''        StackObject::ActivatedAbility {
            source,
            ability: ABILITY_TOP_DRAW,
            ..
        } => {
            state.stack.pop();
            resolve_top_draw(state, source)
        }
        StackObject::ActivatedAbility {
            source,
            ability: ABILITY_URZA_SPIN,
''',
    '''        StackObject::ActivatedAbility {
            source,
            ability: ABILITY_TOP_DRAW,
            ..
        } => {
            state.stack.pop();
            resolve_top_draw(state, source)
        }
        StackObject::ActivatedAbility {
            source,
            ability: ABILITY_ONE_RING_DRAW,
            parameter,
        } => {
            state.stack.pop();
            resolve_one_ring_draw(state, cards, source, parameter)
        }
        StackObject::ActivatedAbility {
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
)

insert_before(
    rules,
    'fn resolve_reality_chip_reconfigure<D: CardDatabase>(\n',
    '''fn resolve_one_ring_draw<D: CardDatabase>(
    state: &mut TrueState,
    cards: &D,
    source: SourceRef,
    snapshot: Option<u16>,
) -> Result<Transition, RuleError> {
    let mut draw_count = snapshot.unwrap_or(0);
    if let Some(source_id) = source.object_id
        && let Some(permanent) = state.battlefield.get(source_id).cloned()
        && permanent.card == source.card
        && card_profile(cards, permanent.card)?.utility == UtilityKind::TheOneRing
    {
        let next = permanent
            .counters
            .burden
            .checked_add(1)
            .ok_or(RuleError::ArithmeticOverflow)?;
        let mut permanents = state.battlefield.permanents().to_vec();
        let live = permanents
            .iter_mut()
            .find(|candidate| candidate.object_id == source_id)
            .ok_or(RuleError::MissingPermanent(source_id))?;
        live.counters.burden = next;
        state.battlefield = BattlefieldZone::new(permanents);
        draw_count = next;
    }

    let drawn = draw_cards(state, usize::from(draw_count))?;
    state.window = Window::Priority;
    Ok(Transition {
        observations: if drawn.is_empty() {
            Vec::new()
        } else {
            vec![RulesObservation::CardsDrawn(drawn)]
        },
    })
}

fn resolve_one_ring_upkeep<D: CardDatabase>(
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

''',
)

replace_once(
    rules,
    '''            state.battlefield = BattlefieldZone::new(permanents);
            state.phase = Phase::Upkeep;
            state.window = Window::Priority;
''',
    '''            state.battlefield = BattlefieldZone::new(permanents);
            state.phase = Phase::Upkeep;
            queue_one_ring_upkeep_triggers(state, cards);
            state.window = Window::Priority;
''',
)

insert_before(
    rules,
    'fn queue_due_chrome_end_step_triggers(state: &mut TrueState) {\n',
    '''fn queue_one_ring_upkeep_triggers<D: CardDatabase>(state: &mut TrueState, cards: &D) {
    let triggers = state
        .battlefield
        .permanents()
        .iter()
        .filter_map(|permanent| {
            cards.profile(permanent.card).and_then(|profile| {
                (profile.utility == UtilityKind::TheOneRing).then_some(
                    StackObject::ActivatedAbility {
                        source: SourceRef {
                            object_id: Some(permanent.object_id),
                            card: permanent.card,
                        },
                        ability: ABILITY_ONE_RING_UPKEEP,
                        parameter: Some(permanent.counters.burden),
                    },
                )
            })
        })
        .collect::<Vec<_>>();
    state.stack.extend(triggers);
}

''',
)

# Add a self-contained rules regression module without disturbing historical R4 fixtures.
ring_rules_tests = r'''

#[cfg(test)]
mod post_r7_one_ring_tests {
    use std::collections::BTreeMap;

    use super::*;

    const RING: CardDefId = CardDefId(500);
    const DRAW_A: CardDefId = CardDefId(501);
    const DRAW_B: CardDefId = CardDefId(502);
    const DRAW_C: CardDefId = CardDefId(503);
    const URZA_DUMMY: CardDefId = CardDefId(504);
    const CONSTRUCT_DUMMY: CardDefId = CardDefId(505);

    #[derive(Default)]
    struct RingCards {
        profiles: BTreeMap<CardDefId, CardProfile>,
    }

    impl RingCards {
        fn new() -> Self {
            let mut profiles = BTreeMap::new();
            profiles.insert(
                RING,
                CardProfile {
                    card: RING,
                    mana_cost: Some(ManaCost {
                        generic: 4,
                        ..ManaCost::default()
                    }),
                    mana_value: 4,
                    role: R2CardRole::ArtifactPermanent,
                    battlefield_face: CardFace::Front,
                    utility: UtilityKind::TheOneRing,
                    is_artifact: true,
                    ..CardProfile::default()
                },
            );
            Self { profiles }
        }
    }

    impl CardDatabase for RingCards {
        fn profile(&self, card: CardDefId) -> Option<CardProfile> {
            self.profiles.get(&card).copied()
        }

        fn commander_card(&self) -> CardDefId {
            URZA_DUMMY
        }

        fn urza_construct_token_card(&self) -> CardDefId {
            CONSTRUCT_DUMMY
        }
    }

    fn ring_permanent(burden: u16, tapped: bool) -> PermanentState {
        PermanentState {
            object_id: ObjectId(1),
            card: RING,
            face: CardFace::Front,
            tapped,
            summoning_sick: false,
            token: false,
            counters: CounterState {
                burden,
                ..CounterState::default()
            },
            mode: PermanentMode::Normal,
            attached_to: None,
            granted_ability: None,
        }
    }

    #[test]
    fn one_ring_draw_adds_burden_on_resolution_and_draws_new_total() {
        let cards = RingCards::new();
        let mut state = TrueState {
            turn: 2,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(vec![DRAW_A, DRAW_B, DRAW_C]),
            battlefield: BattlefieldZone::new(vec![ring_permanent(0, false)]),
            ..TrueState::default()
        };

        apply_action(
            &mut state,
            &cards,
            Action::ActivateOneRingDraw {
                source: ObjectId(1),
            },
        )
        .unwrap();
        assert!(state.battlefield.get(ObjectId(1)).unwrap().tapped);
        assert_eq!(state.battlefield.get(ObjectId(1)).unwrap().counters.burden, 0);

        let first = apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(state.battlefield.get(ObjectId(1)).unwrap().counters.burden, 1);
        assert_eq!(state.hand.cards(), &[DRAW_A]);
        assert_eq!(first.observations, vec![RulesObservation::CardsDrawn(vec![DRAW_A])]);

        set_untapped(&mut state, ObjectId(1)).unwrap();
        apply_action(
            &mut state,
            &cards,
            Action::ActivateOneRingDraw {
                source: ObjectId(1),
            },
        )
        .unwrap();
        let second = apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(state.battlefield.get(ObjectId(1)).unwrap().counters.burden, 2);
        assert_eq!(state.hand.cards(), &[DRAW_A, DRAW_B, DRAW_C]);
        assert_eq!(
            second.observations,
            vec![RulesObservation::CardsDrawn(vec![DRAW_B, DRAW_C])]
        );
    }

    #[test]
    fn one_ring_upkeep_loss_is_stacked_before_normal_draw_step() {
        let cards = RingCards::new();
        let mut state = TrueState {
            turn: 2,
            phase: Phase::Untap,
            window: Window::None,
            life: 40,
            library: TrueLibrary::unknown(vec![DRAW_A]),
            battlefield: BattlefieldZone::new(vec![ring_permanent(2, true)]),
            ..TrueState::default()
        };

        advance_automatic(&mut state, &cards).unwrap();
        assert_eq!(state.phase, Phase::Upkeep);
        assert_eq!(state.stack.len(), 1);
        assert_eq!(state.life, 40);
        assert!(!state.battlefield.get(ObjectId(1)).unwrap().tapped);

        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(state.life, 38);
        assert_eq!(state.phase, Phase::Upkeep);
        assert!(state.hand.is_empty());

        let draw = apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert_eq!(state.phase, Phase::Draw);
        assert_eq!(draw.observations, vec![RulesObservation::CardsDrawn(vec![DRAW_A])]);
    }
}
'''
if "mod post_r7_one_ring_tests" not in rules.read_text():
    rules.write_text(rules.read_text() + ring_rules_tests)

# ---- Current card database layer ------------------------------------------
replace_once(
    cards,
    'pub const R4_ACCEPTED_ACTIVE_IDENTITY_COUNT: usize = 47;\n',
    'pub const R4_ACCEPTED_ACTIVE_IDENTITY_COUNT: usize = 47;\n'
    'pub const POST_R7_ACCEPTED_ACTIVE_IDENTITY_COUNT: usize = 48;\n'
    'pub const POST_R7_CARD_DATABASE_VERSION: &str = "post_r7_card_advantage_v1_ring";\n',
)

post_r7_db = r'''
#[derive(Debug, Clone)]
pub struct PostR7CardDatabase {
    cards: BTreeMap<CardDefId, urza_rules::CardProfile>,
}

pub type CurrentCardDatabase = PostR7CardDatabase;

impl PostR7CardDatabase {
    pub fn load() -> Result<Self, CatalogError> {
        let mut cards = R4CardDatabase::load()?.cards;
        let ring = card_id_by_name_from_r1("The One Ring")?;
        let profile = cards
            .get_mut(&ring)
            .ok_or_else(|| CatalogError::Invariant("missing post-R7 One Ring profile".to_owned()))?;
        profile.role = urza_rules::R2CardRole::ArtifactPermanent;
        profile.utility = urza_rules::UtilityKind::TheOneRing;
        profile.is_artifact = true;
        Ok(Self { cards })
    }

    pub fn profile(&self, card: CardDefId) -> Option<urza_rules::CardProfile> {
        self.cards.get(&card).copied()
    }

    pub fn card_id_by_name(&self, name: &str) -> Result<CardDefId, CatalogError> {
        card_id_by_name_from_r1(name)
    }

    pub fn supported_active_cards(&self) -> Vec<CardDefId> {
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
    fn profile(&self, card: CardDefId) -> Option<urza_rules::CardProfile> {
        self.profile(card)
    }

    fn commander_card(&self) -> CardDefId {
        self.cards
            .values()
            .find(|profile| profile.role == urza_rules::R2CardRole::UrzaCommander)
            .map(|profile| profile.card)
            .expect("validated post-R7 database contains Urza")
    }

    fn urza_construct_token_card(&self) -> CardDefId {
        URZA_CONSTRUCT_TOKEN_CARD_ID
    }

    fn clue_token_card(&self) -> Option<CardDefId> {
        Some(CLUE_TOKEN_CARD_ID)
    }
}

'''
insert_before(cards, 'fn card_id_by_name_from_r1(name: &str) -> Result<CardDefId, CatalogError> {\n', post_r7_db)

# Historical R4 is pinned by its exact count and exact R4-only set. Current
# coverage may legitimately mark later cards active, so unsupported R4 cards
# no longer require the *current* registry to say INTENTIONALLY_UNMODELED.
replace_once(
    cards,
    '''        if profile.role == urza_rules::R2CardRole::Unsupported {
            if status != CoverageStatus::IntentionallyUnmodeled {
                return Err(CatalogError::Invariant(format!(
                    "{} is unsupported by current R4 slice but coverage says {:?}",
                    card.deck_name, status
                )));
            }
        } else if !matches!(
            status,
            CoverageStatus::PrimitiveActive | CoverageStatus::RulesActive
        ) {
            return Err(CatalogError::Invariant(format!(
                "{} has an R4-visible rules primitive but coverage says {:?}",
                card.deck_name, status
            )));
        }
''',
    '''        if profile.role != urza_rules::R2CardRole::Unsupported
            && !matches!(
                status,
                CoverageStatus::PrimitiveActive | CoverageStatus::RulesActive
            )
        {
            return Err(CatalogError::Invariant(format!(
                "{} has an R4-visible rules primitive but coverage says {:?}",
                card.deck_name, status
            )));
        }
''',
)

post_r7_validator = r'''
pub fn validate_post_r7_database() -> Result<(), CatalogError> {
    validate_r4_database()?;
    let coverage = load_coverage()?;
    let database = PostR7CardDatabase::load()?;
    let supported: BTreeSet<_> = database.supported_active_cards().into_iter().collect();
    if supported.len() != POST_R7_ACCEPTED_ACTIVE_IDENTITY_COUNT {
        return Err(CatalogError::Invariant(format!(
            "post-R7 database must expose exactly {POST_R7_ACCEPTED_ACTIVE_IDENTITY_COUNT} active identities"
        )));
    }

    let r4 = R4CardDatabase::load()?;
    let r4_supported: BTreeSet<_> = r4.supported_active_cards().into_iter().collect();
    if !r4_supported.is_subset(&supported) {
        return Err(CatalogError::Invariant(
            "post-R7 database must extend the frozen R4 surface".to_owned(),
        ));
    }
    let added: BTreeSet<_> = supported.difference(&r4_supported).copied().collect();
    let ring = card_id_by_name_from_r1("The One Ring")?;
    if added != BTreeSet::from([ring]) {
        return Err(CatalogError::Invariant(format!(
            "first post-R7 slice must add only The One Ring, got {added:?}"
        )));
    }
    let ring_coverage = coverage
        .entries
        .iter()
        .find(|entry| entry.card_id == ring.0)
        .ok_or_else(|| CatalogError::Invariant("missing One Ring coverage entry".to_owned()))?;
    if !matches!(
        ring_coverage.status,
        CoverageStatus::PrimitiveActive | CoverageStatus::RulesActive
    ) {
        return Err(CatalogError::Invariant(
            "The One Ring must be active in post-R7 coverage".to_owned(),
        ));
    }
    Ok(())
}

'''
insert_before(cards, 'fn r2_primitive_shape(\n', post_r7_validator)

card_test = r'''

#[cfg(test)]
mod post_r7_database_tests {
    use super::*;

    #[test]
    fn post_r7_database_extends_frozen_r4_with_only_the_one_ring() {
        validate_post_r7_database().unwrap();
        let r4 = R4CardDatabase::load().unwrap();
        let current = PostR7CardDatabase::load().unwrap();
        assert_eq!(r4.supported_active_cards().len(), 47);
        assert_eq!(current.supported_active_cards().len(), 48);
        let ring = current.card_id_by_name("The One Ring").unwrap();
        assert_eq!(r4.profile(ring).unwrap().role, urza_rules::R2CardRole::Unsupported);
        let profile = current.profile(ring).unwrap();
        assert_eq!(profile.role, urza_rules::R2CardRole::ArtifactPermanent);
        assert_eq!(profile.utility, urza_rules::UtilityKind::TheOneRing);
        assert!(profile.is_artifact);
        assert_eq!(profile.mana_value, 4);
    }
}
'''
if "mod post_r7_database_tests" not in cards.read_text():
    cards.write_text(cards.read_text() + card_test)

# Update current coverage without mutating the frozen R4 active set.
data = json.loads(coverage.read_text())
for entry in data["entries"]:
    if entry["card_id"] == 81:
        entry["status"] = "PRIMITIVE_ACTIVE"
        entry["reason"] = (
            "Post-R7 second-pass One Ring primitive: normal artifact cast, burden upkeep life loss, "
            "and tap-to-add-burden/draw are modeled on the production stack. Cast protection, "
            "indestructible, and exotic LKI interleavings after intervening burden changes remain deferred."
        )
        break
else:
    raise SystemExit("coverage: The One Ring card_id 81 not found")
coverage.write_text(json.dumps(data, indent=2) + "\n")

# ---- Candidate bridge ------------------------------------------------------
replace_once(
    bridge,
    'pub const CANDIDATE_BRIDGE_VERSION: &str = "r5_public_candidate_bridge_v3_resource_setup";\n'
    'pub const ORDINARY_ACTION_FAMILY_COUNT: usize = 26;\n',
    'pub const CANDIDATE_BRIDGE_VERSION: &str = "post_r7_public_candidate_bridge_v1_ring";\n'
    'pub const ORDINARY_ACTION_FAMILY_COUNT: usize = 27;\n',
)
replace_once(
    bridge,
    'const KIND_CHOOSE_CAM_EFFECT: u16 = 34;\n',
    'const KIND_CHOOSE_CAM_EFFECT: u16 = 34;\nconst KIND_ONE_RING_DRAW: u16 = 35;\n',
)
replace_once(
    bridge,
    '''            UtilityKind::FortuneTellersTalent => {
                for payment in &all_payments {
                    actions.push(Action::ActivateFortuneTellersTalentLevel {
                        source: representative,
                        payment: *payment,
                    });
                }
            }
            _ => {}
''',
    '''            UtilityKind::FortuneTellersTalent => {
                for payment in &all_payments {
                    actions.push(Action::ActivateFortuneTellersTalentLevel {
                        source: representative,
                        payment: *payment,
                    });
                }
            }
            UtilityKind::TheOneRing => {
                actions.push(Action::ActivateOneRingDraw {
                    source: representative,
                });
            }
            _ => {}
''',
)
replace_once(
    bridge,
    '        | Action::ActivateFortuneTellersTalentLevel { .. } => PolicyActionClass::ActivateAbility,\n',
    '        | Action::ActivateFortuneTellersTalentLevel { .. }\n'
    '        | Action::ActivateOneRingDraw { .. } => PolicyActionClass::ActivateAbility,\n',
)
replace_once(
    bridge,
    '''        Action::ActivateFortuneTellersTalentLevel { source, payment } => source_key(
            KIND_FTT_LEVEL,
            *source,
            state,
            object_classes,
            payment_detail(*payment),
        )?,
        Action::PlayLibraryTopLand { card, entry } => PolicyPublicKey {
''',
    '''        Action::ActivateFortuneTellersTalentLevel { source, payment } => source_key(
            KIND_FTT_LEVEL,
            *source,
            state,
            object_classes,
            payment_detail(*payment),
        )?,
        Action::ActivateOneRingDraw { source } => source_key(
            KIND_ONE_RING_DRAW,
            *source,
            state,
            object_classes,
            Vec::new(),
        )?,
        Action::PlayLibraryTopLand { card, entry } => PolicyPublicKey {
''',
)
replace_once(
    bridge,
    '    use urza_cards::R4CardDatabase;\n',
    '    use urza_cards::{PostR7CardDatabase, R4CardDatabase};\n',
)
ring_bridge_test = r'''    #[test]
    fn post_r7_ring_draw_is_exposed_only_while_ring_is_untapped() {
        let cards = PostR7CardDatabase::load().unwrap();
        let ring = cards.card_id_by_name("The One Ring").unwrap();
        let mut state = priority_state();
        state.battlefield = BattlefieldZone::new(vec![permanent(7, ring)]);

        let bridge = CandidateBridge::build(&state, &cards).unwrap();
        let ring_actions = bridge
            .candidates()
            .iter()
            .filter(|candidate| candidate.key.kind == KIND_ONE_RING_DRAW)
            .collect::<Vec<_>>();
        assert_eq!(ring_actions.len(), 1);
        assert_eq!(ring_actions[0].class, PolicyActionClass::ActivateAbility);

        let mut tapped = state;
        let mut permanents = tapped.battlefield.permanents().to_vec();
        permanents[0].tapped = true;
        tapped.battlefield = BattlefieldZone::new(permanents);
        let tapped_bridge = CandidateBridge::build(&tapped, &cards).unwrap();
        assert!(
            tapped_bridge
                .candidates()
                .iter()
                .all(|candidate| candidate.key.kind != KIND_ONE_RING_DRAW)
        );
    }

'''
insert_before(
    bridge,
    '    #[test]\n    fn real_r4_database_still_exposes_only_accepted_profiles_to_bridge() {\n',
    ring_bridge_test,
)

# Migrate the two post-R7 diagnostics immediately; the broader runtime migration
# is handled separately after the database-construction surface audit.
for relative in [
    "rust/crates/urza-mulligan/src/bin/post-r7-engine-tutor-diagnostic.rs",
    "rust/crates/urza-mulligan/src/bin/post-r7-oracle-comparison-export.rs",
]:
    path = Path(relative)
    if not path.exists():
        continue
    text = path.read_text()
    text = text.replace("R4CardDatabase", "CurrentCardDatabase")
    path.write_text(text)
