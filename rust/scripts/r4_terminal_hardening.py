from pathlib import Path


def replace(path: str, old: str, new: str, count: int = 1) -> None:
    p = Path(path)
    text = p.read_text()
    found = text.count(old)
    if found < count:
        raise SystemExit(f"{path}: expected at least {count} occurrence(s), found {found}: {old[:120]!r}")
    p.write_text(text.replace(old, new, count))


# Rules namespace and terminal registry hardening.
replace(
    "rust/crates/urza-rules/src/lib.rs",
    'pub const RULES_VERSION: &str = "r4_recurrence_v4";',
    'pub const RULES_VERSION: &str = "r4_terminal_acceptance_v5";',
)

replace(
    "rust/crates/urza-rules/src/lib.rs",
    "impl WinFamily {\n    pub fn label(self) -> &'static str {",
    """impl WinFamily {
    pub const ALL: [Self; 13] = [
        Self::PowerArtifactGrim,
        Self::PowerArtifactBasalt,
        Self::TopRealityChip,
        Self::TopFttLevelThree,
        Self::TopFttLevelTwoProducer,
        Self::BasaltGadgeteer,
        Self::TopGadgeteerProducer,
        Self::ChromeDomeGrindingStation,
        Self::ChromeDomeBatteredGolem,
        Self::ChromeDomePaGadgeteerManaVault,
        Self::KnackHelixValleyFloodcaller,
        Self::KnackHelixBatteredGolem,
        Self::KnackHelixCam,
    ];

    pub fn label(self) -> &'static str {""",
)

replace(
    "rust/crates/urza-rules/src/lib.rs",
    """        .filter(|permanent| {
            permanent.granted_ability == Some(urza_core::GrantedAbility::KnackBounceUntilEndOfTurn)
                && !permanent.tapped
                && !permanent.summoning_sick
        })""",
    """        .filter(|permanent| {
            permanent.granted_ability == Some(urza_core::GrantedAbility::KnackBounceUntilEndOfTurn)
                && !permanent.tapped
                && !permanent.summoning_sick
                && cards.profile(permanent.card).is_some_and(|profile| {
                    profile.is_creature
                        && !(profile.utility == UtilityKind::RealityChip
                            && permanent.mode == PermanentMode::RealityChipAttached)
                })
        })""",
)

# Real-catalog acceptance tests need the observation crate directly as a dev dependency.
cargo = Path("rust/crates/urza-cards/Cargo.toml")
text = cargo.read_text()
if "[dev-dependencies]" not in text:
    text = text.rstrip() + '\n\n[dev-dependencies]\nurza-info = { path = "../urza-info" }\n'
elif 'urza-info = { path = "../urza-info" }' not in text:
    text = text.replace("[dev-dependencies]\n", '[dev-dependencies]\nurza-info = { path = "../urza-info" }\n', 1)
cargo.write_text(text)

# Keep the R4 audit derived from the single terminal registry instead of a stale hand-maintained list.
replace(
    "rust/crates/urza-cli/src/main.rs",
    """    let report = json!({
        \"phase\": \"R4-top-access\",""",
    """    let terminal_families: Vec<_> = WinFamily::ALL
        .into_iter()
        .map(WinFamily::label)
        .collect();
    let terminal_family_count = terminal_families.len();

    let report = json!({
        \"phase\": \"R4-terminal-acceptance\",""",
)

replace(
    "rust/crates/urza-cli/src/main.rs",
    """        \"active_engine_primitives\": [
            \"Basalt Monolith\",
            \"Grim Monolith\",
            \"Forensic Gadgeteer\",
            \"Power Artifact\",
            \"The Reality Chip\",
            \"Fortune Teller's Talent\",
            \"Grafdigger's Cage\",
            \"Grinding Station\",
            \"Battered Golem\"
        ],
        \"terminal_families\": [
            WinFamily::PowerArtifactGrim.label(),
            WinFamily::PowerArtifactBasalt.label(),
            WinFamily::TopRealityChip.label(),
            WinFamily::TopFttLevelThree.label(),
            WinFamily::TopFttLevelTwoProducer.label(),
            WinFamily::BasaltGadgeteer.label(),
            WinFamily::TopGadgeteerProducer.label()
        ],
        \"terminal_detection_boundary\": \"public InformationState only; exact attachments/modes preserved; Cage blocks library-cast families; no hidden library order\",
        \"scope\": \"R4 broadened through Power Artifact and Top-access engine families; producer trigger execution and remaining terminal families stay in R4\"""",
    """        \"active_engine_primitives\": [
            \"Basalt Monolith\",
            \"Grim Monolith\",
            \"Forensic Gadgeteer\",
            \"Power Artifact\",
            \"The Reality Chip\",
            \"Fortune Teller's Talent\",
            \"Grafdigger's Cage\",
            \"Grinding Station\",
            \"Battered Golem\",
            \"Chrome Dome\",
            \"Mana Vault\",
            \"Banishing Knack\",
            \"Retraction Helix\",
            \"Valley Floodcaller\",
            \"Sewer-veillance Cam\"
        ],
        \"terminal_family_count\": terminal_family_count,
        \"terminal_families\": terminal_families,
        \"terminal_detection_boundary\": \"public InformationState only; exact attachments/modes/grants preserved; stack and pending decisions block terminal recognition; Cage blocks library-cast families; hidden library order and raw ObjectId identity are irrelevant\",
        \"scope\": \"R4 terminal-family acceptance hardened across all 13 audited families; remaining deferred card text is outside these accepted terminal witnesses\"""",
)

# Add real-catalog integration acceptance tests.
tests = r'''use urza_cards::R4CardDatabase;
use urza_core::{
    BattlefieldZone, CardDefId, CardZone, CommanderState, CommanderZone, CounterState,
    GrantedAbility, ManaPool, ObjectId, PendingDecision, PermanentMode, PermanentState, Phase,
    StackObject, TrueLibrary, TrueState, Window,
};
use urza_info::observe;
use urza_rules::{
    Action, ManaPayment, R2CardRole, UtilityKind, WinFamily, apply_action, detect_terminal_win,
    legal_contingent_actions,
};

fn card(cards: &R4CardDatabase, name: &str) -> CardDefId {
    cards.card_id_by_name(name).unwrap()
}

fn permanent(cards: &R4CardDatabase, object: u32, name: &str) -> PermanentState {
    let card = card(cards, name);
    let profile = cards.profile(card).unwrap();
    let mode = match profile.utility {
        UtilityKind::RealityChip => PermanentMode::RealityChipCreature,
        UtilityKind::FortuneTellersTalent => PermanentMode::FortuneTellersTalentLevel1,
        _ => PermanentMode::Normal,
    };
    PermanentState {
        object_id: ObjectId(object),
        card,
        face: profile.battlefield_face,
        tapped: false,
        summoning_sick: false,
        token: false,
        counters: CounterState {
            loyalty: profile.starting_loyalty,
            ..CounterState::default()
        },
        mode,
        attached_to: None,
        granted_ability: None,
    }
}

fn named_cards(cards: &R4CardDatabase, names: &[&str]) -> Vec<CardDefId> {
    names.iter().map(|name| card(cards, name)).collect()
}

fn make_state(
    cards: &R4CardDatabase,
    permanents: Vec<PermanentState>,
    hand: &[&str],
    library: &[&str],
    mana: ManaPool,
) -> TrueState {
    let urza_present = permanents.iter().any(|permanent| {
        cards
            .profile(permanent.card)
            .is_some_and(|profile| profile.role == R2CardRole::UrzaCommander)
    });
    let state = TrueState {
        turn: 4,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        hand: CardZone::new(named_cards(cards, hand)),
        library: TrueLibrary::unknown(named_cards(cards, library)),
        battlefield: BattlefieldZone::new(permanents),
        mana,
        commander: CommanderState {
            zone: if urza_present {
                CommanderZone::Battlefield
            } else {
                CommanderZone::CommandZone
            },
            command_zone_casts: 1,
        },
        ..TrueState::default()
    };
    state.validate().unwrap();
    state
}

fn detected(state: &TrueState, cards: &R4CardDatabase) -> Option<WinFamily> {
    detect_terminal_win(&observe(state).unwrap(), cards)
}

fn canonical_for(state: &TrueState, cards: &R4CardDatabase, name: &str) -> urza_info::CanonicalObjectId {
    let wanted = card(cards, name);
    observe(state)
        .unwrap()
        .battlefield
        .into_iter()
        .find(|permanent| permanent.card == wanted)
        .unwrap()
        .canonical_id
}

fn payment_for_card(cards: &R4CardDatabase, name: &str) -> ManaPayment {
    let cost = cards
        .profile(card(cards, name))
        .unwrap()
        .mana_cost
        .unwrap();
    ManaPayment {
        white: cost.white,
        blue: cost.blue,
        black: cost.black,
        red: cost.red,
        green: cost.green,
        colorless: cost.colorless + cost.generic,
    }
}

fn pool_for(payment: ManaPayment) -> ManaPool {
    ManaPool {
        white: payment.white,
        blue: payment.blue,
        black: payment.black,
        red: payment.red,
        green: payment.green,
        colorless: payment.colorless,
    }
}

fn settle(state: &mut TrueState, cards: &R4CardDatabase) {
    for _ in 0..64 {
        state.validate().unwrap();
        if state.stack.is_empty() && matches!(state.pending, PendingDecision::None) {
            return;
        }
        if matches!(state.pending, PendingDecision::None) {
            apply_action(state, cards, Action::PassPriority).unwrap();
            continue;
        }

        let information = observe(state).unwrap();
        let actions = legal_contingent_actions(&information, cards);
        assert!(!actions.is_empty(), "pending decision has no contingent action");
        let chosen = actions
            .iter()
            .find(|action| matches!(action, Action::ChooseProducerUntap { untap: false }))
            .or_else(|| {
                actions.iter().find(|action| {
                    matches!(
                        action,
                        Action::ChooseCamEffect {
                            choice: urza_rules::CamEffectChoice::Decline
                        }
                    )
                })
            })
            .unwrap_or(&actions[0])
            .clone();
        apply_action(state, cards, chosen).unwrap();
    }
    panic!("stack/pending state did not settle within acceptance bound");
}

fn snapshot(cards: &R4CardDatabase, family: WinFamily, base: u32) -> TrueState {
    let urza = permanent(cards, base + 1, "Urza, Lord High Artificer");
    let mut state = match family {
        WinFamily::PowerArtifactGrim => {
            let grim = permanent(cards, base + 2, "Grim Monolith");
            let mut power = permanent(cards, base + 3, "Power Artifact");
            power.attached_to = Some(grim.object_id);
            make_state(cards, vec![urza, grim, power], &[], &[], ManaPool::default())
        }
        WinFamily::PowerArtifactBasalt => {
            let basalt = permanent(cards, base + 2, "Basalt Monolith");
            let mut power = permanent(cards, base + 3, "Power Artifact");
            power.attached_to = Some(basalt.object_id);
            make_state(cards, vec![urza, basalt, power], &[], &[], ManaPool::default())
        }
        WinFamily::TopRealityChip => {
            let top = permanent(cards, base + 2, "Sensei's Divining Top");
            let station = permanent(cards, base + 3, "Grinding Station");
            let mut chip = permanent(cards, base + 4, "The Reality Chip");
            chip.mode = PermanentMode::RealityChipAttached;
            chip.attached_to = Some(urza.object_id);
            make_state(
                cards,
                vec![urza, top, station, chip],
                &[],
                &["Island", "Tormod's Crypt", "Sol Ring"],
                ManaPool::default(),
            )
        }
        WinFamily::TopFttLevelThree => {
            let top = permanent(cards, base + 2, "Sensei's Divining Top");
            let mut ftt = permanent(cards, base + 3, "Fortune Teller's Talent");
            ftt.mode = PermanentMode::FortuneTellersTalentLevel3;
            let mut state = make_state(
                cards,
                vec![urza, top, ftt],
                &[],
                &["Island", "Tormod's Crypt", "Sol Ring"],
                ManaPool::default(),
            );
            state.spell_cast_this_turn = true;
            state
        }
        WinFamily::TopFttLevelTwoProducer => {
            let top = permanent(cards, base + 2, "Sensei's Divining Top");
            let station = permanent(cards, base + 3, "Grinding Station");
            let mut ftt = permanent(cards, base + 4, "Fortune Teller's Talent");
            ftt.mode = PermanentMode::FortuneTellersTalentLevel2;
            let mut state = make_state(
                cards,
                vec![urza, top, station, ftt],
                &[],
                &["Island", "Tormod's Crypt", "Sol Ring"],
                ManaPool::default(),
            );
            state.spell_cast_this_turn = true;
            state
        }
        WinFamily::BasaltGadgeteer => make_state(
            cards,
            vec![
                urza,
                permanent(cards, base + 2, "Basalt Monolith"),
                permanent(cards, base + 3, "Forensic Gadgeteer"),
            ],
            &[],
            &[],
            ManaPool::default(),
        ),
        WinFamily::TopGadgeteerProducer => make_state(
            cards,
            vec![
                urza,
                permanent(cards, base + 2, "Sensei's Divining Top"),
                permanent(cards, base + 3, "Forensic Gadgeteer"),
                permanent(cards, base + 4, "Grinding Station"),
            ],
            &[],
            &["Island", "Tormod's Crypt", "Sol Ring"],
            ManaPool::default(),
        ),
        WinFamily::ChromeDomeGrindingStation => make_state(
            cards,
            vec![
                urza,
                permanent(cards, base + 2, "Chrome Dome"),
                permanent(cards, base + 3, "Grinding Station"),
            ],
            &[],
            &[],
            ManaPool {
                colorless: 5,
                ..ManaPool::default()
            },
        ),
        WinFamily::ChromeDomeBatteredGolem => make_state(
            cards,
            vec![
                urza,
                permanent(cards, base + 2, "Chrome Dome"),
                permanent(cards, base + 3, "Battered Golem"),
            ],
            &[],
            &[],
            ManaPool {
                colorless: 5,
                ..ManaPool::default()
            },
        ),
        WinFamily::ChromeDomePaGadgeteerManaVault => {
            let chrome = permanent(cards, base + 2, "Chrome Dome");
            let mut power = permanent(cards, base + 3, "Power Artifact");
            power.attached_to = Some(chrome.object_id);
            make_state(
                cards,
                vec![
                    urza,
                    chrome,
                    power,
                    permanent(cards, base + 4, "Forensic Gadgeteer"),
                    permanent(cards, base + 5, "Mana Vault"),
                ],
                &[],
                &[],
                ManaPool::default(),
            )
        }
        WinFamily::KnackHelixValleyFloodcaller => {
            let mut floodcaller = permanent(cards, base + 2, "Valley Floodcaller");
            floodcaller.granted_ability = Some(GrantedAbility::KnackBounceUntilEndOfTurn);
            make_state(
                cards,
                vec![urza, floodcaller],
                &["Tormod's Crypt"],
                &[],
                ManaPool::default(),
            )
        }
        WinFamily::KnackHelixBatteredGolem => {
            let mut golem = permanent(cards, base + 2, "Battered Golem");
            golem.granted_ability = Some(GrantedAbility::KnackBounceUntilEndOfTurn);
            make_state(
                cards,
                vec![urza, golem],
                &["Tormod's Crypt"],
                &[],
                ManaPool::default(),
            )
        }
        WinFamily::KnackHelixCam => {
            let mut golem = permanent(cards, base + 2, "Battered Golem");
            golem.granted_ability = Some(GrantedAbility::KnackBounceUntilEndOfTurn);
            make_state(
                cards,
                vec![
                    urza,
                    golem,
                    permanent(cards, base + 3, "Sewer-veillance Cam"),
                ],
                &[],
                &[],
                ManaPool::default(),
            )
        }
    };
    state.validate().unwrap();
    state
}

fn rewrite_battlefield<F>(state: &mut TrueState, mut edit: F)
where
    F: FnMut(&mut PermanentState),
{
    let mut permanents = state.battlefield.permanents().to_vec();
    for permanent in &mut permanents {
        edit(permanent);
    }
    state.battlefield = BattlefieldZone::new(permanents);
}

fn remove_card(state: &mut TrueState, wanted: CardDefId) {
    state.battlefield = BattlefieldZone::new(
        state
            .battlefield
            .permanents()
            .iter()
            .filter(|permanent| permanent.card != wanted)
            .cloned()
            .collect(),
    );
}

#[test]
fn all_thirteen_terminal_families_have_real_catalog_positive_snapshots() {
    let cards = R4CardDatabase::load().unwrap();
    assert_eq!(WinFamily::ALL.len(), 13);
    let mut labels: Vec<_> = WinFamily::ALL.into_iter().map(WinFamily::label).collect();
    labels.sort_unstable();
    labels.dedup();
    assert_eq!(labels.len(), 13, "terminal labels must remain unique");

    for (index, family) in WinFamily::ALL.into_iter().enumerate() {
        let state = snapshot(&cards, family, 100 * index as u32);
        assert_eq!(detected(&state, &cards), Some(family), "{family:?}");
    }
}

#[test]
fn every_terminal_family_rejects_a_missing_urza_and_any_unresolved_stack() {
    let cards = R4CardDatabase::load().unwrap();
    let urza = card(&cards, "Urza, Lord High Artificer");
    let crypt = card(&cards, "Tormod's Crypt");

    for (index, family) in WinFamily::ALL.into_iter().enumerate() {
        let mut without_urza = snapshot(&cards, family, 100 * index as u32);
        remove_card(&mut without_urza, urza);
        without_urza.commander.zone = CommanderZone::CommandZone;
        assert_eq!(detected(&without_urza, &cards), None, "{family:?} without Urza");

        let mut with_stack = snapshot(&cards, family, 2000 + 100 * index as u32);
        with_stack.stack.push(StackObject::Spell {
            object_id: ObjectId(9000 + index as u32),
            card: crypt,
            x_value: None,
        });
        assert_eq!(detected(&with_stack, &cards), None, "{family:?} with stack");
    }
}

#[test]
fn each_terminal_family_has_a_one_factor_near_miss() {
    let cards = R4CardDatabase::load().unwrap();

    for (index, family) in WinFamily::ALL.into_iter().enumerate() {
        let mut state = snapshot(&cards, family, 4000 + 100 * index as u32);
        match family {
            WinFamily::PowerArtifactGrim => {
                let wanted = card(&cards, "Grim Monolith");
                rewrite_battlefield(&mut state, |permanent| {
                    if permanent.card == wanted {
                        permanent.tapped = true;
                    }
                });
            }
            WinFamily::PowerArtifactBasalt | WinFamily::BasaltGadgeteer => {
                let wanted = card(&cards, "Basalt Monolith");
                rewrite_battlefield(&mut state, |permanent| {
                    if permanent.card == wanted {
                        permanent.tapped = true;
                    }
                });
            }
            WinFamily::TopRealityChip => {
                let wanted = card(&cards, "The Reality Chip");
                rewrite_battlefield(&mut state, |permanent| {
                    if permanent.card == wanted {
                        permanent.mode = PermanentMode::RealityChipCreature;
                        permanent.attached_to = None;
                    }
                });
            }
            WinFamily::TopFttLevelThree => state.spell_cast_this_turn = false,
            WinFamily::TopFttLevelTwoProducer => {
                remove_card(&mut state, card(&cards, "Grinding Station"));
            }
            WinFamily::TopGadgeteerProducer => {
                remove_card(&mut state, card(&cards, "Forensic Gadgeteer"));
            }
            WinFamily::ChromeDomeGrindingStation | WinFamily::ChromeDomeBatteredGolem => {
                state.mana = ManaPool {
                    colorless: 4,
                    ..ManaPool::default()
                };
            }
            WinFamily::ChromeDomePaGadgeteerManaVault => {
                let wanted = card(&cards, "Mana Vault");
                rewrite_battlefield(&mut state, |permanent| {
                    if permanent.card == wanted {
                        permanent.tapped = true;
                    }
                });
            }
            WinFamily::KnackHelixValleyFloodcaller | WinFamily::KnackHelixBatteredGolem => {
                state.hand = CardZone::default();
            }
            WinFamily::KnackHelixCam => {
                let wanted = card(&cards, "Sewer-veillance Cam");
                rewrite_battlefield(&mut state, |permanent| {
                    if permanent.card == wanted {
                        permanent.tapped = true;
                    }
                });
            }
        }
        state.validate().unwrap();
        assert_eq!(detected(&state, &cards), None, "near miss for {family:?}");
    }
}

#[test]
fn top_families_are_hidden_order_invariant_and_cage_blocked() {
    let cards = R4CardDatabase::load().unwrap();
    let cage = card(&cards, "Grafdigger's Cage");
    for family in [
        WinFamily::TopRealityChip,
        WinFamily::TopFttLevelThree,
        WinFamily::TopFttLevelTwoProducer,
        WinFamily::TopGadgeteerProducer,
    ] {
        let first = snapshot(&cards, family, 7000);
        let mut second = snapshot(&cards, family, 8000);
        second.library = TrueLibrary::unknown(named_cards(
            &cards,
            &["Sol Ring", "Tormod's Crypt", "Island"],
        ));
        assert_eq!(detected(&first, &cards), Some(family));
        assert_eq!(detected(&second, &cards), Some(family));

        let mut blocked = first;
        let next = blocked
            .battlefield
            .permanents()
            .iter()
            .map(|permanent| permanent.object_id.0)
            .max()
            .unwrap()
            + 1;
        let mut permanents = blocked.battlefield.permanents().to_vec();
        permanents.push(permanent(&cards, next, "Grafdigger's Cage"));
        blocked.battlefield = BattlefieldZone::new(permanents);
        assert!(blocked.battlefield.permanents().iter().any(|p| p.card == cage));
        assert_eq!(detected(&blocked, &cards), None, "Cage must block {family:?}");
    }
}

#[test]
fn terminal_detection_is_raw_object_id_rename_invariant() {
    let cards = R4CardDatabase::load().unwrap();
    for family in WinFamily::ALL {
        let first = snapshot(&cards, family, 10);
        let second = snapshot(&cards, family, 10_000);
        assert_eq!(detected(&first, &cards), Some(family));
        assert_eq!(detected(&second, &cards), Some(family));
    }
}

#[test]
fn knack_cam_rejects_a_grant_on_a_noncreature_permanent() {
    let cards = R4CardDatabase::load().unwrap();
    let mut ring = permanent(&cards, 2, "Sol Ring");
    ring.granted_ability = Some(GrantedAbility::KnackBounceUntilEndOfTurn);
    let state = make_state(
        &cards,
        vec![
            permanent(&cards, 1, "Urza, Lord High Artificer"),
            ring,
            permanent(&cards, 3, "Sewer-veillance Cam"),
        ],
        &[],
        &[],
        ManaPool::default(),
    );
    assert_eq!(detected(&state, &cards), None);
}

#[test]
fn all_thirteen_families_have_executable_final_witness_steps() {
    let cards = R4CardDatabase::load().unwrap();

    for (rock_name, family) in [
        ("Grim Monolith", WinFamily::PowerArtifactGrim),
        ("Basalt Monolith", WinFamily::PowerArtifactBasalt),
    ] {
        let payment = payment_for_card(&cards, "Power Artifact");
        let mut state = make_state(
            &cards,
            vec![
                permanent(&cards, 1, "Urza, Lord High Artificer"),
                permanent(&cards, 2, rock_name),
            ],
            &["Power Artifact"],
            &[],
            pool_for(payment),
        );
        let target = canonical_for(&state, &cards, rock_name);
        apply_action(
            &mut state,
            &cards,
            Action::CastAuraFromHand {
                card: card(&cards, "Power Artifact"),
                target,
                payment,
            },
        )
        .unwrap();
        assert_eq!(detected(&state, &cards), None);
        settle(&mut state, &cards);
        assert_eq!(detected(&state, &cards), Some(family));
    }

    {
        let mut chip = permanent(&cards, 4, "The Reality Chip");
        chip.mode = PermanentMode::RealityChipCreature;
        let mut state = make_state(
            &cards,
            vec![
                permanent(&cards, 1, "Urza, Lord High Artificer"),
                permanent(&cards, 2, "Sensei's Divining Top"),
                permanent(&cards, 3, "Grinding Station"),
                chip,
            ],
            &[],
            &["Island", "Tormod's Crypt"],
            ManaPool {
                blue: 1,
                colorless: 2,
                ..ManaPool::default()
            },
        );
        let target = canonical_for(&state, &cards, "Urza, Lord High Artificer");
        apply_action(
            &mut state,
            &cards,
            Action::ActivateRealityChipReconfigure {
                source: ObjectId(4),
                target,
                payment: ManaPayment {
                    blue: 1,
                    colorless: 2,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap();
        assert_eq!(detected(&state, &cards), None);
        settle(&mut state, &cards);
        assert_eq!(detected(&state, &cards), Some(WinFamily::TopRealityChip));
    }

    for (mode, producer, family) in [
        (
            PermanentMode::FortuneTellersTalentLevel3,
            false,
            WinFamily::TopFttLevelThree,
        ),
        (
            PermanentMode::FortuneTellersTalentLevel2,
            true,
            WinFamily::TopFttLevelTwoProducer,
        ),
    ] {
        let mut ftt = permanent(&cards, 3, "Fortune Teller's Talent");
        ftt.mode = mode;
        let mut permanents = vec![
            permanent(&cards, 1, "Urza, Lord High Artificer"),
            permanent(&cards, 2, "Sensei's Divining Top"),
            ftt,
        ];
        if producer {
            permanents.push(permanent(&cards, 4, "Grinding Station"));
        }
        let mut state = make_state(
            &cards,
            permanents,
            &["Tormod's Crypt"],
            &["Island", "Sol Ring"],
            ManaPool::default(),
        );
        apply_action(
            &mut state,
            &cards,
            Action::CastFromHand {
                card: card(&cards, "Tormod's Crypt"),
                payment: ManaPayment::default(),
            },
        )
        .unwrap();
        assert_eq!(detected(&state, &cards), None);
        settle(&mut state, &cards);
        assert_eq!(detected(&state, &cards), Some(family));
    }

    {
        let mut basalt = permanent(&cards, 2, "Basalt Monolith");
        basalt.tapped = true;
        let mut state = make_state(
            &cards,
            vec![
                permanent(&cards, 1, "Urza, Lord High Artificer"),
                basalt,
                permanent(&cards, 3, "Forensic Gadgeteer"),
            ],
            &[],
            &[],
            ManaPool {
                colorless: 2,
                ..ManaPool::default()
            },
        );
        apply_action(
            &mut state,
            &cards,
            Action::ActivateNativeArtifactUntap {
                source: ObjectId(2),
                payment: ManaPayment {
                    colorless: 2,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap();
        assert_eq!(detected(&state, &cards), None);
        settle(&mut state, &cards);
        assert_eq!(detected(&state, &cards), Some(WinFamily::BasaltGadgeteer));
    }

    {
        let mut state = make_state(
            &cards,
            vec![
                permanent(&cards, 1, "Urza, Lord High Artificer"),
                permanent(&cards, 2, "Forensic Gadgeteer"),
                permanent(&cards, 3, "Grinding Station"),
            ],
            &["Sensei's Divining Top"],
            &["Island", "Sol Ring"],
            ManaPool {
                colorless: 1,
                ..ManaPool::default()
            },
        );
        apply_action(
            &mut state,
            &cards,
            Action::CastFromHand {
                card: card(&cards, "Sensei's Divining Top"),
                payment: ManaPayment {
                    colorless: 1,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap();
        assert_eq!(detected(&state, &cards), None);
        settle(&mut state, &cards);
        assert_eq!(detected(&state, &cards), Some(WinFamily::TopGadgeteerProducer));
    }

    for (producer_name, family) in [
        ("Grinding Station", WinFamily::ChromeDomeGrindingStation),
        ("Battered Golem", WinFamily::ChromeDomeBatteredGolem),
    ] {
        let mut state = make_state(
            &cards,
            vec![
                permanent(&cards, 1, "Urza, Lord High Artificer"),
                permanent(&cards, 2, "Chrome Dome"),
                permanent(&cards, 3, producer_name),
                permanent(&cards, 4, "Mana Vault"),
            ],
            &[],
            &[],
            ManaPool {
                colorless: 2,
                ..ManaPool::default()
            },
        );
        assert_eq!(detected(&state, &cards), None);
        apply_action(
            &mut state,
            &cards,
            Action::ActivateManaAbility {
                source: ObjectId(4),
            },
        )
        .unwrap();
        assert_eq!(detected(&state, &cards), Some(family));
    }

    {
        let chrome = permanent(&cards, 2, "Chrome Dome");
        let mut power = permanent(&cards, 3, "Power Artifact");
        power.attached_to = Some(chrome.object_id);
        let mut state = make_state(
            &cards,
            vec![
                permanent(&cards, 1, "Urza, Lord High Artificer"),
                chrome,
                power,
                permanent(&cards, 4, "Forensic Gadgeteer"),
            ],
            &["Mana Vault"],
            &[],
            ManaPool {
                colorless: 1,
                ..ManaPool::default()
            },
        );
        apply_action(
            &mut state,
            &cards,
            Action::CastFromHand {
                card: card(&cards, "Mana Vault"),
                payment: ManaPayment {
                    colorless: 1,
                    ..ManaPayment::default()
                },
            },
        )
        .unwrap();
        assert_eq!(detected(&state, &cards), None);
        settle(&mut state, &cards);
        assert_eq!(
            detected(&state, &cards),
            Some(WinFamily::ChromeDomePaGadgeteerManaVault)
        );
    }

    for (source_name, spell_name, include_cam, family) in [
        (
            "Valley Floodcaller",
            "Banishing Knack",
            false,
            WinFamily::KnackHelixValleyFloodcaller,
        ),
        (
            "Battered Golem",
            "Retraction Helix",
            false,
            WinFamily::KnackHelixBatteredGolem,
        ),
        (
            "Battered Golem",
            "Banishing Knack",
            true,
            WinFamily::KnackHelixCam,
        ),
    ] {
        let mut permanents = vec![
            permanent(&cards, 1, "Urza, Lord High Artificer"),
            permanent(&cards, 2, source_name),
        ];
        if include_cam {
            permanents.push(permanent(&cards, 3, "Sewer-veillance Cam"));
        }
        let payment = payment_for_card(&cards, spell_name);
        let hand = if include_cam {
            vec![spell_name]
        } else {
            vec![spell_name, "Tormod's Crypt"]
        };
        let mut state = make_state(&cards, permanents, &hand, &[], pool_for(payment));
        let target = canonical_for(&state, &cards, source_name);
        apply_action(
            &mut state,
            &cards,
            Action::CastTargetedFromHand {
                card: card(&cards, spell_name),
                target,
                payment,
            },
        )
        .unwrap();
        assert_eq!(detected(&state, &cards), None);
        settle(&mut state, &cards);
        assert_eq!(detected(&state, &cards), Some(family));
    }
}
'''

test_path = Path("rust/crates/urza-cards/tests/r4_terminal_acceptance.rs")
test_path.parent.mkdir(parents=True, exist_ok=True)
test_path.write_text(tests)

# Append the acceptance checkpoint only once; the generated change is committed only after all gates pass.
log = Path("rust/DEVELOPMENT_LOG.md")
text = log.read_text()
heading = "## 2026-09-04 — R4 terminal-family acceptance hardening"
if heading not in text:
    text = text.rstrip() + r'''


## 2026-09-04 — R4 terminal-family acceptance hardening

Classification: RULE/MODEL acceptance hardening plus PARITY/real-catalog witnesses. No POLICY implementation and no Python gameplay-logic port.

This pass closes the terminal-family acceptance surface without broadening into unrelated card text:

- centralizes the audited 13-family registry in `WinFamily::ALL`, eliminating the stale seven-family CLI audit list;
- hardens Knack/Helix + Cam recognition so the temporary grant must still be on a creature permanent, including Reality Chip's attached noncreature mode;
- adds real R4-catalog positive snapshots for all 13 terminal families;
- adds one-factor near-miss rejection for every family, plus universal Urza-presence and unresolved-stack rejection;
- verifies terminal recognition is invariant to raw ObjectId renaming and, for Top families, hidden library permutation;
- verifies Grafdigger's Cage blocks every Top/library-cast terminal family;
- adds executable final-step witnesses for all 13 families using the actual rules transitions: Power Artifact attachment, Reality Chip reconfigure, FTT cast enablement, Basalt untap, Top/Gadgeteer producer execution, Chrome mana/Vault enablement, and Knack/Helix targeted-grant resolution;
- updates `r4-audit` to report all 13 families and the full current recurrence primitive set from the single registry.

Acceptance boundary: these witnesses validate the terminal-family contracts and the modeled recurrence mechanisms they depend on. Deferred card text already called out by R4 coverage (for example Mana Vault upkeep/damage, Cam sacrifice-draw, and Floodcaller combat sizing) remains outside this terminal-family gate rather than being approximated.
'''
    log.write_text(text + "\n")
