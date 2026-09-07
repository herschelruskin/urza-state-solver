#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "rust/crates/urza-rules/src/lib.rs"
CARDS = ROOT / "rust/crates/urza-cards/src/lib.rs"
BRIDGE = ROOT / "rust/crates/urza-policy-bridge/src/lib.rs"
COVERAGE = ROOT / "rust/data/card_coverage.r0.json"
DOC = ROOT / "rust/POST_R7_TEXT_SCRY_STACK_VALIDATION.md"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def patch_coverage() -> None:
    text = COVERAGE.read_text()
    replacements = [
        (
            '''    {
      "card_id": 3,
      "status": "INTENTIONALLY_UNMODELED",
      "reason": "R0 foundation: intrinsic card rules are intentionally not implemented yet"
    },''',
            '''    {
      "card_id": 3,
      "status": "RULES_ACTIVE",
      "reason": "Post-R7 rules-active: Artificer's Assistant is an ordinary {U} creature and its whenever-you-cast-a-historic-spell trigger stages a real scry 1; simultaneous controlled cast triggers use an explicit player trigger-order decision. Flying/combat is irrelevant to the goldfish objective."
    },''',
            "Assistant coverage",
        ),
        (
            '''    {
      "card_id": 19,
      "status": "INTENTIONALLY_UNMODELED",
      "reason": "R0 foundation: intrinsic card rules are intentionally not implemented yet"
    },''',
            '''    {
      "card_id": 19,
      "status": "ENVIRONMENT_DEFERRED",
      "reason": "Pinned Oracle text is validated. Faerie Mastermind's opponent-second-card draw trigger belongs to the explicit goldfish environment model; its real {3}{U} each-player-draw activation remains a future rules slice."
    },''',
            "Faerie coverage",
        ),
        (
            '''    {
      "card_id": 53,
      "status": "INTENTIONALLY_UNMODELED",
      "reason": "R0 foundation: intrinsic card rules are intentionally not implemented yet"
    },''',
            '''    {
      "card_id": 53,
      "status": "ENVIRONMENT_DEFERRED",
      "reason": "Pinned Oracle text is validated. Mystic Remora's opponent noncreature-spell draw rate and cumulative-upkeep survival belong to the explicit goldfish environment abstraction rather than hidden rules shortcuts."
    },''',
            "Remora coverage",
        ),
        (
            '''    {
      "card_id": 66,
      "status": "INTENTIONALLY_UNMODELED",
      "reason": "R0 foundation: intrinsic card rules are intentionally not implemented yet"
    },''',
            '''    {
      "card_id": 66,
      "status": "ENVIRONMENT_DEFERRED",
      "reason": "Pinned Oracle text is validated. Rhystic Study's opponent-spell tax/draw rate belongs to the explicit goldfish environment abstraction rather than the intrinsic rules engine."
    },''',
            "Rhystic coverage",
        ),
    ]
    for old, new, label in replacements:
        text = replace_once(text, old, new, label)
    COVERAGE.write_text(text)


def patch_rules() -> None:
    text = RULES.read_text()
    text = replace_once(
        text,
        'pub const POST_R7_RULES_VERSION: &str = "post_r7_card_advantage_v3_clue";',
        'pub const POST_R7_RULES_VERSION: &str = "post_r7_card_advantage_v4_assistant_scry_order";',
        "rules version",
    )
    text = replace_once(
        text,
        'pub const ABILITY_CLUE_DRAW: AbilityId = AbilityId(0x0412);',
        'pub const ABILITY_CLUE_DRAW: AbilityId = AbilityId(0x0412);\n'
        'pub const ABILITY_ARTIFICERS_ASSISTANT_SCRY: AbilityId = AbilityId(0x0413);',
        "Assistant ability id",
    )
    text = replace_once(
        text,
        '''    UthrosResearchCraft,
    GrafdiggersCage,''',
        '''    UthrosResearchCraft,
    ArtificersAssistant,
    GrafdiggersCage,''',
        "Assistant utility kind",
    )
    text = replace_once(
        text,
        '''    fn printed_power(&self, _card: CardDefId) -> Option<i16> {
        None
    }
}''',
        '''    fn printed_power(&self, _card: CardDefId) -> Option<i16> {
        None
    }

    /// Historic is a public characteristic of the spell being cast. Frozen
    /// databases need only artifact support; the current post-R7 database
    /// overrides this using the pinned R1 type-line metadata for legendary and
    /// Saga spells as well.
    fn is_historic_spell(&self, card: CardDefId) -> bool {
        self.profile(card).is_some_and(|profile| profile.is_artifact)
    }
}''',
        "historic card trait hook",
    )
    text = replace_once(
        text,
        '''    ChooseScry {
        top: Vec<CardDefId>,
        bottom: Vec<CardDefId>,
    },
    ChooseProducerUntap {''',
        '''    ChooseScry {
        top: Vec<CardDefId>,
        bottom: Vec<CardDefId>,
    },
    /// `order` is top-of-stack first and indexes the canonical trigger block
    /// already present at the top of the execution stack.
    ChooseTriggerOrder {
        order: Vec<u8>,
    },
    ChooseProducerUntap {''',
        "trigger order action",
    )
    text = replace_once(
        text,
        '    #[error("the requested top/scry ordering is not a permutation of the observed cards")]\n    InvalidObservedCardOrdering,',
        '    #[error("the requested top/scry ordering is not a permutation of the observed cards")]\n'
        '    InvalidObservedCardOrdering,\n'
        '    #[error("the requested trigger order is not a permutation of the pending trigger block")]\n'
        '    InvalidTriggerOrdering,',
        "trigger ordering error",
    )
    text = replace_once(
        text,
        '''        Action::ChooseTopOrder { order } => choose_top_order(state, order)?,
        Action::ChooseScry { top, bottom } => choose_scry(state, top, bottom)?,
        Action::ChooseProducerUntap { untap } => choose_producer_untap(state, untap)?,''',
        '''        Action::ChooseTopOrder { order } => choose_top_order(state, order)?,
        Action::ChooseScry { top, bottom } => choose_scry(state, top, bottom)?,
        Action::ChooseTriggerOrder { order } => choose_trigger_order(state, order)?,
        Action::ChooseProducerUntap { untap } => choose_producer_untap(state, untap)?,''',
        "apply trigger order",
    )
    text = replace_once(
        text,
        '''        ObservedPendingDecision::ScryChoice { looked_at, .. } => {
            let mut actions = Vec::new();
            for order in unique_permutations(looked_at) {
                for top_count in 0..=order.len() {
                    let action = Action::ChooseScry {
                        top: order[..top_count].to_vec(),
                        bottom: order[top_count..].to_vec(),
                    };
                    if !actions.contains(&action) {
                        actions.push(action);
                    }
                }
            }
            actions
        }
        _ => Vec::new(),''',
        '''        ObservedPendingDecision::ScryChoice { looked_at, .. } => {
            let mut actions = Vec::new();
            for order in unique_permutations(looked_at) {
                for top_count in 0..=order.len() {
                    let action = Action::ChooseScry {
                        top: order[..top_count].to_vec(),
                        bottom: order[top_count..].to_vec(),
                    };
                    if !actions.contains(&action) {
                        actions.push(action);
                    }
                }
            }
            actions
        }
        ObservedPendingDecision::TriggerOrder { trigger_count, .. } => {
            index_permutations(*trigger_count)
                .into_iter()
                .map(|order| Action::ChooseTriggerOrder { order })
                .collect()
        }
        _ => Vec::new(),''',
        "trigger order contingent actions",
    )
    text = replace_once(
        text,
        '''        StackObject::ControlledTrigger {
            source,
            ability: ABILITY_UTHROS_ARTIFACT_DRAW,
        } => {
            state.stack.pop();
            resolve_uthros_artifact_draw(state, cards, source)
        }
        StackObject::ActivatedAbility {''',
        '''        StackObject::ControlledTrigger {
            source,
            ability: ABILITY_UTHROS_ARTIFACT_DRAW,
        } => {
            state.stack.pop();
            resolve_uthros_artifact_draw(state, cards, source)
        }
        StackObject::ControlledTrigger {
            source,
            ability: ABILITY_ARTIFICERS_ASSISTANT_SCRY,
        } => {
            state.stack.pop();
            stage_scry(state, source, 1)
        }
        StackObject::ActivatedAbility {''',
        "Assistant resolver dispatch",
    )
    text = replace_once(
        text,
        '''    state.stack.push(StackObject::Spell {
        object_id,
        card: commander,
        x_value: None,
    });
    state.commander.zone = CommanderZone::Stack;''',
        '''    state.stack.push(StackObject::Spell {
        object_id,
        card: commander,
        x_value: None,
    });
    queue_cast_triggers(state, cards, commander);
    state.commander.zone = CommanderZone::Stack;''',
        "commander historic trigger queue",
    )

    choose_marker = '''fn resolve_top_draw(state: &mut TrueState, source: SourceRef) -> Result<Transition, RuleError> {'''
    choose_impl = '''fn choose_trigger_order(
    state: &mut TrueState,
    order: Vec<u8>,
) -> Result<Transition, RuleError> {
    let PendingDecision::TriggerOrder { trigger_count, .. } = state.pending.clone() else {
        return Err(RuleError::SearchDecisionMismatch);
    };
    let count = usize::from(trigger_count);
    if order.len() != count {
        return Err(RuleError::InvalidTriggerOrdering);
    }
    let mut sorted = order.clone();
    sorted.sort_unstable();
    let expected = (0..trigger_count).collect::<Vec<_>>();
    if sorted != expected || state.stack.len() < count {
        return Err(RuleError::InvalidTriggerOrdering);
    }
    let split = state.stack.len() - count;
    let block = state.stack[split..].to_vec();
    if block.iter().any(|object| {
        !matches!(
            object,
            StackObject::ControlledTrigger { .. } | StackObject::TargetedControlledTrigger { .. }
        )
    }) {
        return Err(RuleError::InvalidTriggerOrdering);
    }

    state.stack.truncate(split);
    // `order` is expressed top-first. Stack storage is bottom-first, so push
    // the chosen sequence in reverse.
    for index in order.iter().rev() {
        state.stack.push(block[usize::from(*index)].clone());
    }
    state.pending = PendingDecision::None;
    state.window = Window::Priority;
    Ok(Transition::default())
}

'''
    text = replace_once(text, choose_marker, choose_impl + choose_marker, "trigger order chooser")

    perm_marker = '''fn unique_permutations(cards: &[CardDefId]) -> Vec<Vec<CardDefId>> {'''
    perm_impl = '''fn index_permutations(count: u8) -> Vec<Vec<u8>> {
    fn visit(prefix: &mut Vec<u8>, rest: &mut Vec<u8>, out: &mut Vec<Vec<u8>>) {
        if rest.is_empty() {
            out.push(prefix.clone());
            return;
        }
        for index in 0..rest.len() {
            let value = rest.remove(index);
            prefix.push(value);
            visit(prefix, rest, out);
            prefix.pop();
            rest.insert(index, value);
        }
    }

    let mut rest = (0..count).collect::<Vec<_>>();
    let mut out = Vec::new();
    visit(&mut Vec::new(), &mut rest, &mut out);
    out
}

'''
    text = replace_once(text, perm_marker, perm_impl + perm_marker, "index permutations")

    old_queue = '''fn queue_cast_triggers<D: CardDatabase>(state: &mut TrueState, cards: &D, card: CardDefId) {
    let Some(cast_profile) = cards.profile(card) else {
        return;
    };
    let mut triggers = Vec::new();
    for permanent in state.battlefield.permanents() {
        let Some(profile) = cards.profile(permanent.card) else {
            continue;
        };
        if cast_profile.is_artifact && profile.engine == EngineKind::ForensicGadgeteer {
            triggers.push(StackObject::ControlledTrigger {
                source: SourceRef {
                    object_id: Some(permanent.object_id),
                    card: permanent.card,
                },
                ability: ABILITY_GADGETEER_INVESTIGATE,
            });
        }
        if cast_profile.is_artifact
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
        if !cast_profile.is_creature && profile.engine == EngineKind::ValleyFloodcaller {
            triggers.push(StackObject::ControlledTrigger {
                source: SourceRef {
                    object_id: Some(permanent.object_id),
                    card: permanent.card,
                },
                ability: ABILITY_FLOODCALLER_UNTAP,
            });
        }
    }
    state.stack.extend(triggers);
}'''
    new_queue = '''fn queue_cast_triggers<D: CardDatabase>(state: &mut TrueState, cards: &D, card: CardDefId) {
    let Some(cast_profile) = cards.profile(card) else {
        return;
    };
    let mut triggers = Vec::new();
    for permanent in state.battlefield.permanents() {
        let Some(profile) = cards.profile(permanent.card) else {
            continue;
        };
        if cast_profile.is_artifact && profile.engine == EngineKind::ForensicGadgeteer {
            triggers.push(StackObject::ControlledTrigger {
                source: SourceRef {
                    object_id: Some(permanent.object_id),
                    card: permanent.card,
                },
                ability: ABILITY_GADGETEER_INVESTIGATE,
            });
        }
        if cast_profile.is_artifact
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
        if profile.utility == UtilityKind::ArtificersAssistant && cards.is_historic_spell(card) {
            triggers.push(StackObject::ControlledTrigger {
                source: SourceRef {
                    object_id: Some(permanent.object_id),
                    card: permanent.card,
                },
                ability: ABILITY_ARTIFICERS_ASSISTANT_SCRY,
            });
        }
        if !cast_profile.is_creature && profile.engine == EngineKind::ValleyFloodcaller {
            triggers.push(StackObject::ControlledTrigger {
                source: SourceRef {
                    object_id: Some(permanent.object_id),
                    card: permanent.card,
                },
                ability: ABILITY_FLOODCALLER_UNTAP,
            });
        }
    }
    if triggers.len() > 1 {
        let trigger_count = u8::try_from(triggers.len())
            .expect("Commander goldfish cannot create more than 255 simultaneous cast triggers");
        state.pending = PendingDecision::TriggerOrder {
            source: SourceRef {
                object_id: None,
                card,
            },
            trigger_count,
        };
    }
    state.stack.extend(triggers);
}'''
    text = replace_once(text, old_queue, new_queue, "cast trigger queue")

    if "mod post_r7_assistant_scry_tests" in text:
        raise SystemExit("Assistant rules tests already present")
    text += r'''

#[cfg(test)]
mod post_r7_assistant_scry_tests {
    use std::collections::BTreeMap;

    use super::*;
    use urza_core::CardZone;

    const ASSISTANT: CardDefId = CardDefId(700);
    const UTHROS: CardDefId = CardDefId(701);
    const ARTIFACT: CardDefId = CardDefId(702);
    const BAD: CardDefId = CardDefId(703);
    const GOOD: CardDefId = CardDefId(704);
    const URZA_DUMMY: CardDefId = CardDefId(705);
    const CONSTRUCT_DUMMY: CardDefId = CardDefId(706);

    #[derive(Default)]
    struct AssistantCards {
        profiles: BTreeMap<CardDefId, CardProfile>,
    }

    impl AssistantCards {
        fn new() -> Self {
            let mut profiles = BTreeMap::new();
            profiles.insert(
                ASSISTANT,
                CardProfile {
                    card: ASSISTANT,
                    mana_cost: Some(ManaCost { blue: 1, ..ManaCost::default() }),
                    mana_value: 1,
                    role: R2CardRole::CreaturePermanent,
                    battlefield_face: CardFace::Front,
                    utility: UtilityKind::ArtificersAssistant,
                    is_creature: true,
                    ..CardProfile::default()
                },
            );
            profiles.insert(
                UTHROS,
                CardProfile {
                    card: UTHROS,
                    mana_cost: Some(ManaCost { generic: 3, ..ManaCost::default() }),
                    mana_value: 3,
                    role: R2CardRole::ArtifactPermanent,
                    battlefield_face: CardFace::Front,
                    utility: UtilityKind::UthrosResearchCraft,
                    is_artifact: true,
                    ..CardProfile::default()
                },
            );
            profiles.insert(
                ARTIFACT,
                CardProfile {
                    card: ARTIFACT,
                    mana_cost: Some(ManaCost { generic: 1, ..ManaCost::default() }),
                    mana_value: 1,
                    role: R2CardRole::ArtifactPermanent,
                    battlefield_face: CardFace::Front,
                    is_artifact: true,
                    ..CardProfile::default()
                },
            );
            Self { profiles }
        }
    }

    impl CardDatabase for AssistantCards {
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

    fn permanent(object: u32, card: CardDefId) -> PermanentState {
        PermanentState {
            object_id: ObjectId(object),
            card,
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

    fn setup() -> (AssistantCards, TrueState) {
        let cards = AssistantCards::new();
        let mut uthros = permanent(2, UTHROS);
        uthros.counters.charge = 3;
        let state = TrueState {
            turn: 3,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(vec![BAD, GOOD]),
            hand: CardZone::new(vec![ARTIFACT]),
            battlefield: BattlefieldZone::new(vec![permanent(1, ASSISTANT), uthros]),
            mana: ManaPool { colorless: 1, ..ManaPool::default() },
            ..TrueState::default()
        };
        (cards, state)
    }

    fn cast_artifact(state: &mut TrueState, cards: &AssistantCards) {
        apply_action(
            state,
            cards,
            Action::CastFromHand {
                card: ARTIFACT,
                payment: ManaPayment { colorless: 1, ..ManaPayment::default() },
            },
        )
        .unwrap();
    }

    #[test]
    fn assistant_and_uthros_stage_a_real_player_trigger_order_choice() {
        let (cards, mut state) = setup();
        cast_artifact(&mut state, &cards);
        assert!(matches!(
            state.pending,
            PendingDecision::TriggerOrder { trigger_count: 2, .. }
        ));
        assert_eq!(state.stack.len(), 3, "spell plus two controlled triggers");
        let information = urza_info::observe(&state).unwrap();
        let actions = legal_contingent_actions(&information, &cards);
        assert_eq!(actions.len(), 2);
        assert!(actions.contains(&Action::ChooseTriggerOrder { order: vec![0, 1] }));
        assert!(actions.contains(&Action::ChooseTriggerOrder { order: vec![1, 0] }));
    }

    #[test]
    fn scry_first_can_bottom_the_current_top_before_uthros_draws() {
        let (cards, mut state) = setup();
        cast_artifact(&mut state, &cards);

        // Canonical trigger block is Assistant then Uthros. `order` is top-first,
        // so [0,1] deliberately resolves Assistant's scry before Uthros's draw.
        apply_action(
            &mut state,
            &cards,
            Action::ChooseTriggerOrder { order: vec![0, 1] },
        )
        .unwrap();
        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert!(matches!(state.pending, PendingDecision::ScryChoice { .. }));
        apply_action(
            &mut state,
            &cards,
            Action::ChooseScry { top: vec![], bottom: vec![BAD] },
        )
        .unwrap();
        assert_eq!(state.library.cards(), &[GOOD, BAD]);

        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert!(state.hand.cards().contains(&GOOD));
        assert!(!state.hand.cards().contains(&BAD));
        let uthros = state.battlefield.get(ObjectId(2)).unwrap();
        assert_eq!(uthros.counters.charge, 4);
    }

    #[test]
    fn uthros_first_draws_before_assistant_sees_the_next_card() {
        let (cards, mut state) = setup();
        cast_artifact(&mut state, &cards);
        apply_action(
            &mut state,
            &cards,
            Action::ChooseTriggerOrder { order: vec![1, 0] },
        )
        .unwrap();
        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert!(state.hand.cards().contains(&BAD));
        assert_eq!(state.library.cards(), &[GOOD]);
        apply_action(&mut state, &cards, Action::PassPriority).unwrap();
        assert!(matches!(state.pending, PendingDecision::ScryChoice { .. }));
    }
}
'''
    RULES.write_text(text)


def patch_cards() -> None:
    text = CARDS.read_text()
    text = replace_once(
        text,
        'pub const POST_R7_ACCEPTED_ACTIVE_IDENTITY_COUNT: usize = 49;\n'
        'pub const POST_R7_CARD_DATABASE_VERSION: &str = "post_r7_card_advantage_v2_uthros";',
        'pub const POST_R7_ACCEPTED_ACTIVE_IDENTITY_COUNT: usize = 50;\n'
        'pub const POST_R7_CARD_DATABASE_VERSION: &str = "post_r7_card_advantage_v3_assistant_scry_order";',
        "post-R7 cards version/count",
    )
    text = replace_once(
        text,
        '''pub struct PostR7CardDatabase {
    cards: BTreeMap<CardDefId, urza_rules::CardProfile>,
    printed_powers: BTreeMap<CardDefId, i16>,
}''',
        '''pub struct PostR7CardDatabase {
    cards: BTreeMap<CardDefId, urza_rules::CardProfile>,
    printed_powers: BTreeMap<CardDefId, i16>,
    historic_cards: BTreeSet<CardDefId>,
}''',
        "historic card storage",
    )
    text = replace_once(
        text,
        '''        uthros_profile.role = urza_rules::R2CardRole::ArtifactPermanent;
        uthros_profile.utility = urza_rules::UtilityKind::UthrosResearchCraft;
        uthros_profile.is_artifact = true;

        // Public printed powers used by Station.''',
        '''        uthros_profile.role = urza_rules::R2CardRole::ArtifactPermanent;
        uthros_profile.utility = urza_rules::UtilityKind::UthrosResearchCraft;
        uthros_profile.is_artifact = true;

        let assistant = card_id_by_name_from_r1("Artificer's Assistant")?;
        let assistant_profile = cards.get_mut(&assistant).ok_or_else(|| {
            CatalogError::Invariant("missing post-R7 Artificer's Assistant profile".to_owned())
        })?;
        assistant_profile.role = urza_rules::R2CardRole::CreaturePermanent;
        assistant_profile.utility = urza_rules::UtilityKind::ArtificersAssistant;
        assistant_profile.is_creature = true;

        let catalog = load_r1_catalog()?;
        let historic_cards = catalog
            .cards
            .iter()
            .filter(|card| metadata_is_historic(card))
            .map(|card| CardDefId(card.id))
            .collect::<BTreeSet<_>>();

        // Public printed powers used by Station.''',
        "Assistant profile/historic set",
    )
    text = replace_once(
        text,
        '''        Ok(Self {
            cards,
            printed_powers,
        })''',
        '''        Ok(Self {
            cards,
            printed_powers,
            historic_cards,
        })''',
        "post-R7 database construction",
    )
    text = replace_once(
        text,
        '''    fn printed_power(&self, card: CardDefId) -> Option<i16> {
        self.printed_power(card)
    }
}''',
        '''    fn printed_power(&self, card: CardDefId) -> Option<i16> {
        self.printed_power(card)
    }

    fn is_historic_spell(&self, card: CardDefId) -> bool {
        self.historic_cards.contains(&card)
    }
}''',
        "post-R7 historic trait override",
    )
    helper_marker = '''fn card_id_by_name_from_r1(name: &str) -> Result<CardDefId, CatalogError> {'''
    helper = '''fn metadata_is_historic(card: &R1CardMetadata) -> bool {
    if card.feature_flags.is_artifact {
        return true;
    }
    let historic_type_line = |line: &str| {
        line.split(|ch: char| ch.is_whitespace() || ch == '—' || ch == '/')
            .any(|word| matches!(word, "Legendary" | "Saga"))
    };
    historic_type_line(&card.type_line)
        || card.faces.iter().any(|face| historic_type_line(&face.type_line))
}

'''
    text = replace_once(text, helper_marker, helper + helper_marker, "historic metadata helper")
    text = replace_once(
        text,
        '''    let ring = card_id_by_name_from_r1("The One Ring")?;
    let uthros = card_id_by_name_from_r1("Uthros Research Craft")?;
    if added != BTreeSet::from([ring, uthros]) {
        return Err(CatalogError::Invariant(format!(
            "post-R7 card-advantage surface must add exactly Ring and Uthros, got {added:?}"
        )));
    }''',
        '''    let ring = card_id_by_name_from_r1("The One Ring")?;
    let uthros = card_id_by_name_from_r1("Uthros Research Craft")?;
    let assistant = card_id_by_name_from_r1("Artificer's Assistant")?;
    if added != BTreeSet::from([ring, uthros, assistant]) {
        return Err(CatalogError::Invariant(format!(
            "post-R7 current surface must add exactly Ring, Uthros, and Artificer's Assistant, got {added:?}"
        )));
    }''',
        "post-R7 added set",
    )
    text = replace_once(
        text,
        '''    if !matches!(
        uthros_coverage.status,
        CoverageStatus::PrimitiveActive | CoverageStatus::RulesActive
    ) {
        return Err(CatalogError::Invariant(
            "Uthros Research Craft must be active in post-R7 coverage".to_owned(),
        ));
    }
    Ok(())''',
        '''    if !matches!(
        uthros_coverage.status,
        CoverageStatus::PrimitiveActive | CoverageStatus::RulesActive
    ) {
        return Err(CatalogError::Invariant(
            "Uthros Research Craft must be active in post-R7 coverage".to_owned(),
        ));
    }
    let assistant_coverage = coverage
        .entries
        .iter()
        .find(|entry| entry.card_id == assistant.0)
        .ok_or_else(|| CatalogError::Invariant("missing Artificer's Assistant coverage entry".to_owned()))?;
    if !matches!(
        assistant_coverage.status,
        CoverageStatus::PrimitiveActive | CoverageStatus::RulesActive
    ) {
        return Err(CatalogError::Invariant(
            "Artificer's Assistant must be active in post-R7 coverage".to_owned(),
        ));
    }
    Ok(())''',
        "Assistant coverage validation",
    )
    text = replace_once(
        text,
        '''        assert_eq!(current.supported_active_cards().len(), 49);''',
        '''        assert_eq!(current.supported_active_cards().len(), 50);''',
        "post-R7 test count",
    )

    test_marker = '''    #[test]
    fn r1_catalog_tracks_the_three_active_modal_dfcs() {'''
    test = r'''    #[test]
    fn post_r7_priority_card_text_hashes_are_explicitly_pinned() {
        let catalog = load_r1_catalog().unwrap();
        // These digests correspond to the exact pinned Oracle text documented
        // in POST_R7_TEXT_SCRY_STACK_VALIDATION.md. They are deliberately
        // checked without changing the frozen R1 metadata schema.
        for (name, expected) in [
            ("Artificer's Assistant", "4500992939e68bf5d0e9ccaae34745d9b5493891717d983002967d79a4d583f6"),
            ("Faerie Mastermind", "9057053fb56b1a7734ce8ae12241f7eb15814d48df0cd2dc3b13e4994333a438"),
            ("Mystic Remora", "4c1b24efecbfc96ef5aa572d00c124322ce5f061349ecbec21e3a0676021a00b"),
            ("Rhystic Study", "b01edb4edf239cd0b4116ab58ea2fb90152ed9b83b068b6ea34ccbe8d67fd03c"),
        ] {
            let card = catalog.cards.iter().find(|card| card.deck_name == name).unwrap();
            assert_eq!(card.oracle_text_sha256, expected, "Oracle text drift for {name}");
            assert_ne!(card.oracle_text_sha256, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "{name} must not have empty Oracle text");
        }
    }

'''
    text = replace_once(text, test_marker, test + test_marker, "Oracle text digest regression")

    # Add a focused Assistant profile assertion to the existing post-R7 database test.
    text = replace_once(
        text,
        '''        let ring = current.card_id_by_name("The One Ring").unwrap();''',
        '''        let assistant = current.card_id_by_name("Artificer's Assistant").unwrap();
        assert_eq!(
            current.profile(assistant).unwrap().utility,
            urza_rules::UtilityKind::ArtificersAssistant
        );
        let ring = current.card_id_by_name("The One Ring").unwrap();''',
        "Assistant current profile regression",
    )
    CARDS.write_text(text)


def patch_bridge() -> None:
    text = BRIDGE.read_text()
    text = replace_once(
        text,
        'pub const CANDIDATE_BRIDGE_VERSION: &str = "post_r7_public_candidate_bridge_v3_clue";\n'
        'pub const ORDINARY_ACTION_FAMILY_COUNT: usize = 29;\n'
        'pub const CONTINGENT_ACTION_FAMILY_COUNT: usize = 8;',
        'pub const CANDIDATE_BRIDGE_VERSION: &str = "post_r7_public_candidate_bridge_v4_trigger_order";\n'
        'pub const ORDINARY_ACTION_FAMILY_COUNT: usize = 29;\n'
        'pub const CONTINGENT_ACTION_FAMILY_COUNT: usize = 9;',
        "bridge version/count",
    )
    text = replace_once(
        text,
        'const KIND_CLUE_DRAW: u16 = 37;',
        'const KIND_CLUE_DRAW: u16 = 37;\nconst KIND_CHOOSE_TRIGGER_ORDER: u16 = 38;',
        "trigger order key kind",
    )
    text = replace_once(
        text,
        '''        | Action::ChooseTopOrder { .. }
        | Action::ChooseScry { .. }
        | Action::ChooseProducerUntap { .. }''',
        '''        | Action::ChooseTopOrder { .. }
        | Action::ChooseScry { .. }
        | Action::ChooseTriggerOrder { .. }
        | Action::ChooseProducerUntap { .. }''',
        "trigger order action classification",
    )
    text = replace_once(
        text,
        '''        Action::ChooseScry { top, bottom } => {
            let mut detail = Vec::with_capacity(2 + top.len() + bottom.len());
            detail.push(u16::try_from(top.len()).unwrap_or(u16::MAX));
            detail.extend(top.iter().map(|card| card.0));
            detail.push(u16::try_from(bottom.len()).unwrap_or(u16::MAX));
            detail.extend(bottom.iter().map(|card| card.0));
            PolicyPublicKey {
                kind: KIND_CHOOSE_SCRY,
                detail,
                ..PolicyPublicKey::default()
            }
        }
        Action::ChooseProducerUntap { untap } => PolicyPublicKey {''',
        '''        Action::ChooseScry { top, bottom } => {
            let mut detail = Vec::with_capacity(2 + top.len() + bottom.len());
            detail.push(u16::try_from(top.len()).unwrap_or(u16::MAX));
            detail.extend(top.iter().map(|card| card.0));
            detail.push(u16::try_from(bottom.len()).unwrap_or(u16::MAX));
            detail.extend(bottom.iter().map(|card| card.0));
            PolicyPublicKey {
                kind: KIND_CHOOSE_SCRY,
                detail,
                ..PolicyPublicKey::default()
            }
        }
        Action::ChooseTriggerOrder { order } => PolicyPublicKey {
            kind: KIND_CHOOSE_TRIGGER_ORDER,
            detail: order.iter().map(|index| u16::from(*index)).collect(),
            ..PolicyPublicKey::default()
        },
        Action::ChooseProducerUntap { untap } => PolicyPublicKey {''',
        "trigger order public key",
    )
    text = replace_once(
        text,
        '        assert_eq!(CONTINGENT_ACTION_FAMILY_COUNT, 8);',
        '        assert_eq!(CONTINGENT_ACTION_FAMILY_COUNT, 9);',
        "contingent family audit count",
    )

    if "post_r7_assistant_trigger_order_is_public_and_top_can_stack_afterward" in text:
        raise SystemExit("Assistant bridge regression already present")
    test_anchor = '''    #[test]
    fn real_r4_database_still_exposes_only_accepted_profiles_to_bridge() {'''
    test = r'''    #[test]
    fn post_r7_assistant_trigger_order_is_public_and_top_can_stack_afterward() {
        let cards = PostR7CardDatabase::load().unwrap();
        let assistant = cards.card_id_by_name("Artificer's Assistant").unwrap();
        let uthros = cards.card_id_by_name("Uthros Research Craft").unwrap();
        let top = cards.card_id_by_name("Sensei's Divining Top").unwrap();
        let sol_ring = cards.card_id_by_name("Sol Ring").unwrap();

        let mut uthros_perm = permanent(2, uthros);
        uthros_perm.counters.charge = 3;
        let mut state = priority_state();
        state.hand = CardZone::new(vec![sol_ring]);
        state.battlefield = BattlefieldZone::new(vec![
            permanent(1, assistant),
            uthros_perm,
            permanent(3, top),
        ]);
        state.mana = ManaPool { colorless: 2, ..ManaPool::default() };

        apply_action(
            &mut state,
            &cards,
            Action::CastFromHand {
                card: sol_ring,
                payment: ManaPayment { colorless: 1, ..ManaPayment::default() },
            },
        )
        .unwrap();
        assert!(matches!(
            state.pending,
            PendingDecision::TriggerOrder { trigger_count: 2, .. }
        ));

        let bridge = CandidateBridge::build(&state, &cards).unwrap();
        let order_actions = bridge
            .candidates()
            .iter()
            .filter(|candidate| candidate.key.kind == KIND_CHOOSE_TRIGGER_ORDER)
            .collect::<Vec<_>>();
        assert_eq!(order_actions.len(), 2);
        assert!(order_actions.iter().all(|candidate| candidate.class == PolicyActionClass::ContingentDecision));

        let chosen = order_actions
            .iter()
            .find(|candidate| candidate.key.detail == vec![0, 1])
            .unwrap();
        apply_action(
            &mut state,
            &cards,
            bridge.resolved_action(chosen.token).unwrap(),
        )
        .unwrap();

        // Once trigger order is fixed, priority returns. Top's look activation
        // is a legal public action that may be stacked above both triggers;
        // policy/value may decide later whether that is strategically useful.
        let bridge = CandidateBridge::build(&state, &cards).unwrap();
        assert!(bridge.candidates().iter().any(|candidate| {
            candidate.key.kind == KIND_TOP_LOOK
                && matches!(bridge.resolve(candidate.token), Some(Action::ActivateTopLook { .. }))
        }));
    }

'''
    text = replace_once(text, test_anchor, test + test_anchor, "Assistant trigger-order bridge test")
    BRIDGE.write_text(text)


def write_doc() -> None:
    DOC.write_text(r'''# Post-R7 Oracle-Text and Scry/Stack Validation

Status: **MECHANICS VALIDATION SLICE**

This checkpoint is intentionally narrow. It closes the remaining card-text and
scry/stack questions before returning to policy/value work.

## Pinned Oracle text validation

The frozen R1 catalog stores SHA-256 digests of Oracle text rather than copying
raw rules text into every runtime profile. The current regression pins the
following exact text/digest pairs:

- **Faerie Mastermind** — `9057053fb56b1a7734ce8ae12241f7eb15814d48df0cd2dc3b13e4994333a438`
  - `Flash`
  - `Flying`
  - `Whenever an opponent draws their second card each turn, you draw a card.`
  - `{3}{U}: Each player draws a card.`
- **Mystic Remora** — `4c1b24efecbfc96ef5aa572d00c124322ce5f061349ecbec21e3a0676021a00b`
  - `Cumulative upkeep {1} (At the beginning of your upkeep, put an age counter on this permanent, then sacrifice it unless you pay its upkeep cost for each age counter on it.)`
  - `Whenever an opponent casts a noncreature spell, you may draw a card unless that player pays {4}.`
- **Rhystic Study** — `b01edb4edf239cd0b4116ab58ea2fb90152ed9b83b068b6ea34ccbe8d67fd03c`
  - `Whenever an opponent casts a spell, you may draw a card unless that player pays {1}.`
- **Artificer's Assistant** — `4500992939e68bf5d0e9ccaae34745d9b5493891717d983002967d79a4d583f6`
  - `Flying`
  - `Whenever you cast a historic spell, scry 1. (Artifacts, legendaries, and Sagas are historic. To scry 1, look at the top card of your library, then you may put that card on the bottom.)`

These hashes are non-empty and are checked against the pinned R1 metadata.
Rhystic Study, Mystic Remora, and Faerie Mastermind remain **environment
deferred**: their opponent-driven trigger frequencies are not intrinsic rules
facts and must enter through an explicit goldfish environment contract. This
validation does not silently install the old Oracle's 2/2/1 rates.

## Artificer's Assistant / scry / trigger ordering

The existing Rust rules engine already had an exact scry primitive: it observes
the top cards, then exposes every legal top/bottom partition and ordering as a
post-observation contingent decision. It previously had no production card that
used it.

This slice activates Artificer's Assistant and connects its historic-cast
trigger to real `scry 1`.

When one cast creates multiple player-controlled triggers (for example an
artifact cast with Assistant and Uthros at 3+ charge), the triggers are first
placed in a deterministic canonical block and the player receives a real
`TriggerOrder` decision. The selected action names the desired **top-of-stack
first** ordering. This makes the strategically distinct lines explicit:

- Assistant scry resolves first -> the player may bottom the current top card ->
  Uthros draws the next card.
- Uthros resolves first -> it draws the current top card -> Assistant scries the
  following card.

After trigger order is chosen, priority returns normally. Sensei's Divining Top
may therefore be activated above those triggers, and its top-three reorder
resolves before them. The rules/bridge expose that choice; deciding when that
extra Top activation is valuable belongs to the upcoming policy/value pass.

Historic classification for the current database comes from pinned R1 public
type-line metadata: artifacts, legendary spells, and Sagas. Legendary lands do
not create Assistant triggers because lands are played rather than cast.
''')


if __name__ == "__main__":
    patch_coverage()
    patch_rules()
    patch_cards()
    patch_bridge()
    write_doc()
    print("post-R7 Assistant scry/trigger-order slice patched")
