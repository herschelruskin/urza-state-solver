use urza_cards::R4CardDatabase;
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

fn canonical_for(
    state: &TrueState,
    cards: &R4CardDatabase,
    name: &str,
) -> urza_info::CanonicalObjectId {
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
    let cost = cards.profile(card(cards, name)).unwrap().mana_cost.unwrap();
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
        assert!(
            !actions.is_empty(),
            "pending decision has no contingent action"
        );
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
    let state = match family {
        WinFamily::PowerArtifactGrim => {
            let grim = permanent(cards, base + 2, "Grim Monolith");
            let mut power = permanent(cards, base + 3, "Power Artifact");
            power.attached_to = Some(grim.object_id);
            make_state(
                cards,
                vec![urza, grim, power],
                &[],
                &[],
                ManaPool::default(),
            )
        }
        WinFamily::PowerArtifactBasalt => {
            let basalt = permanent(cards, base + 2, "Basalt Monolith");
            let mut power = permanent(cards, base + 3, "Power Artifact");
            power.attached_to = Some(basalt.object_id);
            make_state(
                cards,
                vec![urza, basalt, power],
                &[],
                &[],
                ManaPool::default(),
            )
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
        let urza_object = without_urza
            .battlefield
            .permanents()
            .iter()
            .find(|permanent| permanent.card == urza)
            .unwrap()
            .object_id;
        remove_card(&mut without_urza, urza);
        rewrite_battlefield(&mut without_urza, |permanent| {
            if permanent.attached_to == Some(urza_object) {
                permanent.attached_to = None;
                if permanent.mode == PermanentMode::RealityChipAttached {
                    permanent.mode = PermanentMode::RealityChipCreature;
                }
            }
        });
        without_urza.commander.zone = CommanderZone::CommandZone;
        assert_eq!(
            detected(&without_urza, &cards),
            None,
            "{family:?} without Urza"
        );

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
        assert!(
            blocked
                .battlefield
                .permanents()
                .iter()
                .any(|p| p.card == cage)
        );
        assert_eq!(
            detected(&blocked, &cards),
            None,
            "Cage must block {family:?}"
        );
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
        assert_eq!(
            detected(&state, &cards),
            Some(WinFamily::TopGadgeteerProducer)
        );
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
