use urza_cards::CurrentCardDatabase;
use urza_core::{
    BattlefieldZone, CardZone, CounterState, ManaPool, ObjectId, PermanentMode, PermanentState,
    Phase, TrueLibrary, TrueState, Window,
};
use urza_info::observe;
use urza_rules::{
    Action, AuraTargetKind, EngineKind, ManaPayment, R2CardRole, apply_action,
};

fn card(cards: &CurrentCardDatabase, name: &str) -> urza_core::CardDefId {
    cards.card_id_by_name(name).unwrap()
}

fn permanent(
    cards: &CurrentCardDatabase,
    object: u32,
    name: &str,
    tapped: bool,
) -> PermanentState {
    let card = card(cards, name);
    let profile = cards.profile(card).unwrap();
    PermanentState {
        object_id: ObjectId(object),
        card,
        face: profile.battlefield_face,
        tapped,
        summoning_sick: false,
        token: false,
        counters: CounterState::default(),
        mode: PermanentMode::Normal,
        attached_to: None,
        granted_ability: None,
    }
}

fn state_with(
    cards: &CurrentCardDatabase,
    permanents: Vec<PermanentState>,
    hand: &[&str],
    mana: ManaPool,
) -> TrueState {
    let state = TrueState {
        turn: 1,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        hand: CardZone::new(hand.iter().map(|name| card(cards, name)).collect()),
        library: TrueLibrary::unknown(Vec::new()),
        battlefield: BattlefieldZone::new(permanents),
        mana,
        ..TrueState::default()
    };
    state.validate().unwrap();
    state
}

fn canonical_for(
    state: &TrueState,
    cards: &CurrentCardDatabase,
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

fn cast_power_artifact(
    state: &mut TrueState,
    cards: &CurrentCardDatabase,
    target_name: &str,
) {
    let power = card(cards, "Power Artifact");
    let target = canonical_for(state, cards, target_name);
    apply_action(
        state,
        cards,
        Action::CastAuraFromHand {
            card: power,
            target,
            payment: ManaPayment {
                blue: 2,
                ..ManaPayment::default()
            },
        },
    )
    .unwrap();
    apply_action(state, cards, Action::PassPriority).unwrap();
}

fn audit_reduced_untap(rock_name: &str, reduced_cost: u16) {
    let cards = CurrentCardDatabase::load().unwrap();
    let power = card(&cards, "Power Artifact");
    let power_profile = cards.profile(power).unwrap();
    assert_eq!(power_profile.role, R2CardRole::EnchantmentPermanent);
    assert_eq!(power_profile.engine, EngineKind::PowerArtifact);
    assert_eq!(power_profile.aura_target, AuraTargetKind::Artifact);
    assert_eq!(power_profile.attached_artifact_activation_reduction, 2);

    let mut state = state_with(
        &cards,
        vec![permanent(&cards, 1, rock_name, true)],
        &["Power Artifact"],
        ManaPool {
            blue: 2,
            ..ManaPool::default()
        },
    );
    cast_power_artifact(&mut state, &cards, rock_name);

    let rock = card(&cards, rock_name);
    let rock_object = state
        .battlefield
        .permanents()
        .iter()
        .find(|permanent| permanent.card == rock)
        .unwrap()
        .object_id;
    let aura = state
        .battlefield
        .permanents()
        .iter()
        .find(|permanent| permanent.card == power)
        .unwrap();
    assert_eq!(aura.attached_to, Some(rock_object));

    state.mana = ManaPool {
        colorless: reduced_cost,
        ..ManaPool::default()
    };
    apply_action(
        &mut state,
        &cards,
        Action::ActivateNativeArtifactUntap {
            source: rock_object,
            payment: ManaPayment {
                colorless: reduced_cost,
                ..ManaPayment::default()
            },
        },
    )
    .unwrap();
    assert!(state.battlefield.get(rock_object).unwrap().tapped);
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    assert!(!state.battlefield.get(rock_object).unwrap().tapped);
}

#[test]
fn power_artifact_reduces_basalt_and_grim_native_untap_costs() {
    audit_reduced_untap("Basalt Monolith", 1);
    audit_reduced_untap("Grim Monolith", 2);
}

#[test]
fn power_artifact_and_other_reducers_cannot_reduce_a_nonzero_cost_below_one() {
    let cards = CurrentCardDatabase::load().unwrap();
    let mut state = state_with(
        &cards,
        vec![
            permanent(&cards, 1, "Basalt Monolith", true),
            permanent(&cards, 2, "Forensic Gadgeteer", false),
        ],
        &["Power Artifact"],
        ManaPool {
            blue: 2,
            ..ManaPool::default()
        },
    );
    cast_power_artifact(&mut state, &cards, "Basalt Monolith");

    let basalt = state
        .battlefield
        .permanents()
        .iter()
        .find(|permanent| permanent.card == card(&cards, "Basalt Monolith"))
        .unwrap()
        .object_id;
    state.mana = ManaPool {
        colorless: 1,
        ..ManaPool::default()
    };

    let mut zero_payment = state.clone();
    assert!(
        apply_action(
            &mut zero_payment,
            &cards,
            Action::ActivateNativeArtifactUntap {
                source: basalt,
                payment: ManaPayment::default(),
            },
        )
        .is_err()
    );

    apply_action(
        &mut state,
        &cards,
        Action::ActivateNativeArtifactUntap {
            source: basalt,
            payment: ManaPayment {
                colorless: 1,
                ..ManaPayment::default()
            },
        },
    )
    .unwrap();
    apply_action(&mut state, &cards, Action::PassPriority).unwrap();
    assert!(!state.battlefield.get(basalt).unwrap().tapped);
}

#[test]
fn power_artifact_cannot_enchant_a_nonartifact() {
    let cards = CurrentCardDatabase::load().unwrap();
    let mut state = state_with(
        &cards,
        vec![permanent(&cards, 1, "Spellseeker", false)],
        &["Power Artifact"],
        ManaPool {
            blue: 2,
            ..ManaPool::default()
        },
    );
    let target = canonical_for(&state, &cards, "Spellseeker");
    assert!(
        apply_action(
            &mut state,
            &cards,
            Action::CastAuraFromHand {
                card: card(&cards, "Power Artifact"),
                target,
                payment: ManaPayment {
                    blue: 2,
                    ..ManaPayment::default()
                },
            },
        )
        .is_err()
    );
}
