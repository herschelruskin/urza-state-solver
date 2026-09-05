#![forbid(unsafe_code)]

use std::collections::{BTreeMap, BTreeSet};

use thiserror::Error;
use urza_core::{
    CardDefId, CardFace, GrantedAbility, ManaPool, ObjectId, PendingDecisionKind, TrueState,
};
use urza_info::{
    CanonicalObjectId, InformationState, ObservationError, ObservedPendingDecision, observe,
    resolve_canonical_objects,
};
use urza_policy::{ActionToken, PolicyActionClass, PolicyCandidate, PolicyPublicKey};
use urza_rng::{LogicalEventId, RootSeed, WorldId};
use urza_rules::{
    Action, AuraTargetKind, CamEffectChoice, CardDatabase, EngineKind, GameRngContext,
    LandEntryChoice, ManaPayment, R2CardRole, SpecialSearchKind, SpellEffectKind, UtilityKind,
    apply_action_with_rng, enumerate_payments, legal_contingent_actions,
};

pub const CANDIDATE_BRIDGE_VERSION: &str = "r5_public_candidate_bridge_v1";
pub const ORDINARY_ACTION_FAMILY_COUNT: usize = 26;
pub const CONTINGENT_ACTION_FAMILY_COUNT: usize = 8;

const KIND_PASS_PRIORITY: u16 = 1;
const KIND_PLAY_LAND: u16 = 2;
const KIND_ACTIVATE_MANA: u16 = 3;
const KIND_NATIVE_ARTIFACT_UNTAP: u16 = 4;
const KIND_URZA_ARTIFACT_MANA: u16 = 5;
const KIND_GRINDING_STATION: u16 = 6;
const KIND_CHROME_DOME: u16 = 7;
const KIND_KNACK_BOUNCE: u16 = 8;
const KIND_CAST_FROM_HAND: u16 = 9;
const KIND_CAST_AURA_FROM_HAND: u16 = 10;
const KIND_CAST_TARGETED_FROM_HAND: u16 = 11;
const KIND_CAST_WHIR: u16 = 12;
const KIND_CAST_RESHAPE: u16 = 13;
const KIND_REPURPOSING_BAY: u16 = 14;
const KIND_TOP_LOOK: u16 = 15;
const KIND_TOP_DRAW: u16 = 16;
const KIND_URZA_SPIN: u16 = 17;
const KIND_TEZZERET_MINUS_THREE: u16 = 18;
const KIND_REALITY_CHIP_RECONFIGURE: u16 = 19;
const KIND_REALITY_CHIP_DETACH: u16 = 20;
const KIND_FTT_LEVEL: u16 = 21;
const KIND_PLAY_LIBRARY_TOP_LAND: u16 = 22;
const KIND_CAST_LIBRARY_TOP: u16 = 23;
const KIND_PLAY_URZA_PERMISSION: u16 = 24;
const KIND_PLAY_URZA_PERMISSION_AURA: u16 = 25;
const KIND_CAST_COMMANDER: u16 = 26;
const KIND_CHOOSE_TRANSMUTE_SACRIFICE: u16 = 27;
const KIND_CHOOSE_SEARCH_TARGET: u16 = 28;
const KIND_PAY_TRANSMUTE_DIFFERENCE: u16 = 29;
const KIND_CHOOSE_TOP_ORDER: u16 = 30;
const KIND_CHOOSE_SCRY: u16 = 31;
const KIND_CHOOSE_PRODUCER_UNTAP: u16 = 32;
const KIND_CHOOSE_CAM_TARGET: u16 = 33;
const KIND_CHOOSE_CAM_EFFECT: u16 = 34;

#[derive(Debug, Error)]
pub enum BridgeError {
    #[error("cannot build candidates from invalid execution state: {0}")]
    Observation(#[from] ObservationError),
    #[error("public pending decision {0:?} has no legal candidate on the accepted bridge surface")]
    PendingDecisionHasNoCandidate(PendingDecisionKind),
    #[error("canonical battlefield class {0:?} has no execution representative")]
    MissingExecutionClass(CanonicalObjectId),
    #[error("execution object {0:?} has no canonical public class")]
    MissingCanonicalClass(ObjectId),
    #[error("observed Urza permission slot {0} is missing")]
    MissingPermissionSlot(u16),
    #[error("candidate set has {0} entries, exceeding u16 ActionToken capacity")]
    TooManyCandidates(usize),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CandidateBridge {
    information: InformationState,
    candidates: Vec<PolicyCandidate>,
    actions: Vec<Action>,
}

impl CandidateBridge {
    pub fn build<D: CardDatabase>(state: &TrueState, cards: &D) -> Result<Self, BridgeError> {
        let information = observe(state)?;
        let classes = permanent_classes(state, &information)?;
        let object_classes = execution_object_classes(&classes);
        let pending = information.pending.kind() != PendingDecisionKind::None;

        let mut actions = if pending {
            let mut actions = legal_contingent_actions(&information, cards);
            if matches!(
                information.pending,
                ObservedPendingDecision::TransmuteDifferencePayment { .. }
            ) {
                actions.extend(generate_mana_actions(state, cards, &classes));
            }
            actions
        } else {
            generate_ordinary_actions(state, &information, cards, &classes)
        };

        if pending {
            actions.retain(|action| action_is_legal(state, cards, action));
        }

        let mut semantic = BTreeMap::<(PolicyActionClass, PolicyPublicKey), Action>::new();
        for action in actions {
            let class = classify_action(&action, &information, cards, pending)?;
            let key = public_key_for_action(
                &action,
                state,
                &information,
                cards,
                &object_classes,
            )?;
            semantic.entry((class, key)).or_insert(action);
        }

        if pending && semantic.is_empty() {
            return Err(BridgeError::PendingDecisionHasNoCandidate(
                information.pending.kind(),
            ));
        }
        if semantic.len() > usize::from(u16::MAX) + 1 {
            return Err(BridgeError::TooManyCandidates(semantic.len()));
        }

        let mut candidates = Vec::with_capacity(semantic.len());
        let mut resolved_actions = Vec::with_capacity(semantic.len());
        for (index, ((class, key), action)) in semantic.into_iter().enumerate() {
            let token = ActionToken(
                u16::try_from(index).map_err(|_| BridgeError::TooManyCandidates(index + 1))?,
            );
            candidates.push(PolicyCandidate::new(token, class, key));
            resolved_actions.push(action);
        }

        Ok(Self {
            information,
            candidates,
            actions: resolved_actions,
        })
    }

    pub fn information(&self) -> &InformationState {
        &self.information
    }

    pub fn candidates(&self) -> &[PolicyCandidate] {
        &self.candidates
    }

    pub fn resolve(&self, token: ActionToken) -> Option<&Action> {
        let index = usize::from(token.0);
        self.candidates
            .get(index)
            .filter(|candidate| candidate.token == token)
            .and_then(|_| self.actions.get(index))
    }

    pub fn resolved_action(&self, token: ActionToken) -> Option<Action> {
        self.resolve(token).cloned()
    }
}

#[derive(Debug, Clone)]
struct PermanentClass {
    canonical: CanonicalObjectId,
    card: CardDefId,
    tapped: bool,
    granted_ability: Option<GrantedAbility>,
    objects: Vec<ObjectId>,
}

fn permanent_classes(
    state: &TrueState,
    information: &InformationState,
) -> Result<Vec<PermanentClass>, BridgeError> {
    let mut canonical_ids = BTreeSet::new();
    for permanent in &information.battlefield {
        canonical_ids.insert(permanent.canonical_id);
    }

    let mut classes = Vec::with_capacity(canonical_ids.len());
    for canonical in canonical_ids {
        let observed = information
            .battlefield
            .iter()
            .find(|permanent| permanent.canonical_id == canonical)
            .expect("canonical id originated in observed battlefield");
        let objects = resolve_canonical_objects(state, canonical)?;
        if objects.is_empty() {
            return Err(BridgeError::MissingExecutionClass(canonical));
        }
        classes.push(PermanentClass {
            canonical,
            card: observed.card,
            tapped: observed.tapped,
            granted_ability: observed.granted_ability,
            objects,
        });
    }
    Ok(classes)
}

fn execution_object_classes(classes: &[PermanentClass]) -> BTreeMap<ObjectId, CanonicalObjectId> {
    let mut out = BTreeMap::new();
    for class in classes {
        for object in &class.objects {
            out.insert(*object, class.canonical);
        }
    }
    out
}

fn generate_ordinary_actions<D: CardDatabase>(
    state: &TrueState,
    information: &InformationState,
    cards: &D,
    classes: &[PermanentClass],
) -> Vec<Action> {
    let mut actions = vec![Action::PassPriority];
    let all_payments = available_payments(information.mana);
    let canonical_targets: Vec<_> = classes.iter().map(|class| class.canonical).collect();
    let artifact_classes: Vec<_> = classes
        .iter()
        .filter(|class| {
            cards
                .profile(class.card)
                .is_some_and(|profile| profile.is_artifact)
        })
        .collect();
    let creature_targets: Vec<_> = classes
        .iter()
        .filter(|class| {
            cards
                .profile(class.card)
                .is_some_and(|profile| profile.is_creature)
        })
        .map(|class| class.canonical)
        .collect();

    let hand_cards: BTreeSet<_> = information.hand.iter().copied().collect();
    for card in hand_cards {
        let Some(profile) = cards.profile(card) else {
            continue;
        };

        if profile.role == R2CardRole::Land {
            actions.push(Action::PlayLand {
                card,
                entry: LandEntryChoice::Default,
            });
            actions.push(Action::PlayLand {
                card,
                entry: LandEntryChoice::PayLife,
            });
        }

        if let Some(cost) = profile.mana_cost {
            let payments = enumerate_payments(information.mana, cost);
            for payment in &payments {
                actions.push(Action::CastFromHand {
                    card,
                    payment: *payment,
                });
                if profile.aura_target != AuraTargetKind::None {
                    for target in &canonical_targets {
                        actions.push(Action::CastAuraFromHand {
                            card,
                            target: *target,
                            payment: *payment,
                        });
                    }
                }
                if profile.spell_effect != SpellEffectKind::None {
                    for target in &canonical_targets {
                        actions.push(Action::CastTargetedFromHand {
                            card,
                            target: *target,
                            payment: *payment,
                        });
                    }
                }
            }
        }

        match profile.special_search {
            SpecialSearchKind::Whir => {
                generate_whir_actions(
                    &mut actions,
                    card,
                    information,
                    cards,
                    classes,
                    &all_payments,
                );
            }
            SpecialSearchKind::Reshape => {
                let max_x = pool_total_u16(information.mana);
                for x_value in 0..=max_x {
                    for sacrifice in &artifact_classes {
                        let representative = sacrifice.objects[0];
                        for payment in &all_payments {
                            actions.push(Action::CastReshape {
                                card,
                                x_value,
                                sacrifice: representative,
                                payment: *payment,
                            });
                        }
                    }
                }
            }
            _ => {}
        }
    }

    for class in classes {
        let representative = class.objects[0];
        let Some(profile) = cards.profile(class.card) else {
            continue;
        };

        actions.push(Action::ActivateManaAbility {
            source: representative,
        });
        if profile.native_untap_generic.is_some() {
            for payment in &all_payments {
                actions.push(Action::ActivateNativeArtifactUntap {
                    source: representative,
                    payment: *payment,
                });
            }
        }
        if profile.is_artifact {
            actions.push(Action::ActivateUrzaArtifactMana {
                artifact: representative,
            });
        }

        if profile.engine == EngineKind::GrindingStation {
            for sacrifice in &artifact_classes {
                actions.push(Action::ActivateGrindingStation {
                    source: representative,
                    sacrifice: sacrifice.canonical,
                });
            }
        }
        if profile.engine == EngineKind::ChromeDome {
            for target in &artifact_classes {
                for payment in &all_payments {
                    actions.push(Action::ActivateChromeDome {
                        source: representative,
                        target: target.canonical,
                        payment: *payment,
                    });
                }
            }
        }
        if class.granted_ability == Some(GrantedAbility::KnackBounceUntilEndOfTurn) {
            for target in &canonical_targets {
                actions.push(Action::ActivateGrantedKnackBounce {
                    source: representative,
                    target: *target,
                });
            }
        }

        if profile.special_search == SpecialSearchKind::RepurposingBay {
            for sacrifice in &artifact_classes {
                for payment in &all_payments {
                    actions.push(Action::ActivateRepurposingBay {
                        source: representative,
                        sacrifice: sacrifice.objects[0],
                        payment: *payment,
                    });
                }
            }
        }

        match profile.utility {
            UtilityKind::SenseisDiviningTop => {
                for payment in &all_payments {
                    actions.push(Action::ActivateTopLook {
                        source: representative,
                        payment: *payment,
                    });
                }
                actions.push(Action::ActivateTopDraw {
                    source: representative,
                });
            }
            UtilityKind::TezzeretCruelCaptain => {
                actions.push(Action::ActivateTezzeretMinusThree {
                    source: representative,
                });
            }
            UtilityKind::RealityChip => {
                for target in &creature_targets {
                    for payment in &all_payments {
                        actions.push(Action::ActivateRealityChipReconfigure {
                            source: representative,
                            target: *target,
                            payment: *payment,
                        });
                    }
                }
                for payment in &all_payments {
                    actions.push(Action::ActivateRealityChipDetach {
                        source: representative,
                        payment: *payment,
                    });
                }
            }
            UtilityKind::FortuneTellersTalent => {
                for payment in &all_payments {
                    actions.push(Action::ActivateFortuneTellersTalentLevel {
                        source: representative,
                        payment: *payment,
                    });
                }
            }
            _ => {}
        }

        if class.card == cards.commander_card() {
            for payment in &all_payments {
                actions.push(Action::ActivateUrzaSpin {
                    source: representative,
                    payment: *payment,
                });
            }
        }
    }

    if let Some(card) = information.library.known_top.first().copied()
        && let Some(profile) = cards.profile(card)
    {
        if profile.role == R2CardRole::Land {
            actions.push(Action::PlayLibraryTopLand {
                card,
                entry: LandEntryChoice::Default,
            });
            actions.push(Action::PlayLibraryTopLand {
                card,
                entry: LandEntryChoice::PayLife,
            });
        }
        if let Some(cost) = profile.mana_cost {
            for payment in enumerate_payments(information.mana, cost) {
                actions.push(Action::CastLibraryTop { card, payment });
            }
        }
    }

    for permission in &information.urza_permissions {
        for face in [CardFace::Front, CardFace::Back] {
            actions.push(Action::PlayUrzaPermission {
                permission_slot: permission.permission_slot,
                face,
            });
        }
        for target in &canonical_targets {
            actions.push(Action::PlayUrzaPermissionAura {
                permission_slot: permission.permission_slot,
                target: *target,
            });
        }
    }

    for payment in &all_payments {
        actions.push(Action::CastCommander { payment: *payment });
    }

    actions.retain(|action| action_is_legal(state, cards, action));
    actions
}

fn generate_mana_actions<D: CardDatabase>(
    state: &TrueState,
    cards: &D,
    classes: &[PermanentClass],
) -> Vec<Action> {
    let mut actions = Vec::new();
    for class in classes {
        let representative = class.objects[0];
        actions.push(Action::ActivateManaAbility {
            source: representative,
        });
        if cards
            .profile(class.card)
            .is_some_and(|profile| profile.is_artifact)
        {
            actions.push(Action::ActivateUrzaArtifactMana {
                artifact: representative,
            });
        }
    }
    actions.retain(|action| action_is_legal(state, cards, action));
    actions
}

fn generate_whir_actions<D: CardDatabase>(
    actions: &mut Vec<Action>,
    card: CardDefId,
    information: &InformationState,
    cards: &D,
    classes: &[PermanentClass],
    all_payments: &[ManaPayment],
) {
    let improvise_classes: Vec<_> = classes
        .iter()
        .filter(|class| {
            !class.tapped
                && cards
                    .profile(class.card)
                    .is_some_and(|profile| profile.is_artifact)
        })
        .collect();
    let selections = improvise_selections(&improvise_classes);
    let eligible_count: usize = improvise_classes.iter().map(|class| class.objects.len()).sum();
    let max_x = u16::try_from(
        u32::from(pool_total_u16(information.mana))
            .saturating_add(u32::try_from(eligible_count).unwrap_or(u32::MAX))
            .min(u32::from(u16::MAX)),
    )
    .expect("value was clamped to u16");

    for sources in selections {
        let used = u16::try_from(sources.len()).unwrap_or(u16::MAX);
        if used > max_x {
            continue;
        }
        for x_value in used..=max_x {
            for payment in all_payments {
                actions.push(Action::CastWhir {
                    card,
                    x_value,
                    payment: *payment,
                    improvise_sources: sources.clone(),
                });
            }
        }
    }
}

fn improvise_selections(classes: &[&PermanentClass]) -> Vec<Vec<ObjectId>> {
    fn recurse(
        classes: &[&PermanentClass],
        index: usize,
        current: &mut Vec<ObjectId>,
        out: &mut Vec<Vec<ObjectId>>,
    ) {
        if index == classes.len() {
            out.push(current.clone());
            return;
        }
        let class = classes[index];
        let base = current.len();
        for count in 0..=class.objects.len() {
            current.extend(class.objects.iter().take(count).copied());
            recurse(classes, index + 1, current, out);
            current.truncate(base);
        }
    }

    let mut out = Vec::new();
    recurse(classes, 0, &mut Vec::new(), &mut out);
    out
}

fn available_payments(pool: ManaPool) -> Vec<ManaPayment> {
    let mut out = Vec::new();
    for white in 0..=pool.white {
        for blue in 0..=pool.blue {
            for black in 0..=pool.black {
                for red in 0..=pool.red {
                    for green in 0..=pool.green {
                        for colorless in 0..=pool.colorless {
                            out.push(ManaPayment {
                                white,
                                blue,
                                black,
                                red,
                                green,
                                colorless,
                            });
                        }
                    }
                }
            }
        }
    }
    out
}

fn pool_total_u16(pool: ManaPool) -> u16 {
    let total = u32::from(pool.white)
        + u32::from(pool.blue)
        + u32::from(pool.black)
        + u32::from(pool.red)
        + u32::from(pool.green)
        + u32::from(pool.colorless);
    u16::try_from(total.min(u32::from(u16::MAX))).expect("value was clamped to u16")
}

fn action_is_legal<D: CardDatabase>(state: &TrueState, cards: &D, action: &Action) -> bool {
    let mut trial = state.clone();
    apply_action_with_rng(
        &mut trial,
        cards,
        action.clone(),
        GameRngContext {
            root: RootSeed::from_u64(0x5235_4252_4944_4745),
            world: WorldId(0),
            logical_event: LogicalEventId(0),
        },
    )
    .is_ok()
}

fn classify_action<D: CardDatabase>(
    action: &Action,
    information: &InformationState,
    cards: &D,
    pending: bool,
) -> Result<PolicyActionClass, BridgeError> {
    if pending {
        return Ok(PolicyActionClass::ContingentDecision);
    }

    Ok(match action {
        Action::PassPriority => PolicyActionClass::PassPriority,
        Action::PlayLand { .. } | Action::PlayLibraryTopLand { .. } => {
            PolicyActionClass::PlayLand
        }
        Action::ActivateManaAbility { .. } | Action::ActivateUrzaArtifactMana { .. } => {
            PolicyActionClass::ProduceMana
        }
        Action::CastFromHand { .. }
        | Action::CastAuraFromHand { .. }
        | Action::CastTargetedFromHand { .. }
        | Action::CastWhir { .. }
        | Action::CastReshape { .. }
        | Action::CastLibraryTop { .. }
        | Action::PlayUrzaPermissionAura { .. }
        | Action::CastCommander { .. } => PolicyActionClass::CastSpell,
        Action::PlayUrzaPermission {
            permission_slot, ..
        } => {
            let card = permission_card(information, *permission_slot)?;
            if cards
                .profile(card)
                .is_some_and(|profile| profile.role == R2CardRole::Land)
            {
                PolicyActionClass::PlayLand
            } else {
                PolicyActionClass::CastSpell
            }
        }
        Action::ActivateNativeArtifactUntap { .. }
        | Action::ActivateGrindingStation { .. }
        | Action::ActivateChromeDome { .. }
        | Action::ActivateGrantedKnackBounce { .. }
        | Action::ActivateRepurposingBay { .. }
        | Action::ActivateTopLook { .. }
        | Action::ActivateTopDraw { .. }
        | Action::ActivateUrzaSpin { .. }
        | Action::ActivateTezzeretMinusThree { .. }
        | Action::ActivateRealityChipReconfigure { .. }
        | Action::ActivateRealityChipDetach { .. }
        | Action::ActivateFortuneTellersTalentLevel { .. } => PolicyActionClass::ActivateAbility,
        Action::ChooseTransmuteSacrifice { .. }
        | Action::ChooseSearchTarget { .. }
        | Action::PayTransmuteDifference { .. }
        | Action::ChooseTopOrder { .. }
        | Action::ChooseScry { .. }
        | Action::ChooseProducerUntap { .. }
        | Action::ChooseCamTarget { .. }
        | Action::ChooseCamEffect { .. } => PolicyActionClass::ContingentDecision,
    })
}

fn public_key_for_action<D: CardDatabase>(
    action: &Action,
    state: &TrueState,
    information: &InformationState,
    cards: &D,
    object_classes: &BTreeMap<ObjectId, CanonicalObjectId>,
) -> Result<PolicyPublicKey, BridgeError> {
    let key = match action {
        Action::PassPriority => key(KIND_PASS_PRIORITY),
        Action::PlayLand { card, entry } => PolicyPublicKey {
            kind: KIND_PLAY_LAND,
            card: Some(*card),
            secondary: land_entry_code(*entry),
            ..PolicyPublicKey::default()
        },
        Action::ActivateManaAbility { source } => source_key(
            KIND_ACTIVATE_MANA,
            *source,
            state,
            object_classes,
            Vec::new(),
        )?,
        Action::ActivateNativeArtifactUntap { source, payment } => source_key(
            KIND_NATIVE_ARTIFACT_UNTAP,
            *source,
            state,
            object_classes,
            payment_detail(*payment),
        )?,
        Action::ActivateUrzaArtifactMana { artifact } => source_key(
            KIND_URZA_ARTIFACT_MANA,
            *artifact,
            state,
            object_classes,
            Vec::new(),
        )?,
        Action::ActivateGrindingStation { source, sacrifice } => {
            let mut out = source_key(
                KIND_GRINDING_STATION,
                *source,
                state,
                object_classes,
                Vec::new(),
            )?;
            out.target = Some(*sacrifice);
            out
        }
        Action::ActivateChromeDome {
            source,
            target,
            payment,
        } => {
            let mut out = source_key(
                KIND_CHROME_DOME,
                *source,
                state,
                object_classes,
                payment_detail(*payment),
            )?;
            out.target = Some(*target);
            out
        }
        Action::ActivateGrantedKnackBounce { source, target } => {
            let mut out = source_key(
                KIND_KNACK_BOUNCE,
                *source,
                state,
                object_classes,
                Vec::new(),
            )?;
            out.target = Some(*target);
            out
        }
        Action::CastFromHand { card, payment } => spell_key(
            KIND_CAST_FROM_HAND,
            *card,
            None,
            None,
            payment_detail(*payment),
        ),
        Action::CastAuraFromHand {
            card,
            target,
            payment,
        } => spell_key(
            KIND_CAST_AURA_FROM_HAND,
            *card,
            Some(*target),
            None,
            payment_detail(*payment),
        ),
        Action::CastTargetedFromHand {
            card,
            target,
            payment,
        } => spell_key(
            KIND_CAST_TARGETED_FROM_HAND,
            *card,
            Some(*target),
            None,
            payment_detail(*payment),
        ),
        Action::CastWhir {
            card,
            x_value,
            payment,
            improvise_sources,
        } => {
            let mut detail = payment_detail(*payment);
            let mut canonical_sources = Vec::with_capacity(improvise_sources.len());
            for source in improvise_sources {
                canonical_sources.push(canonical_for_object(object_classes, *source)?.0);
            }
            canonical_sources.sort_unstable();
            detail.push(
                u16::try_from(canonical_sources.len()).unwrap_or(u16::MAX),
            );
            detail.extend(canonical_sources);
            spell_key(KIND_CAST_WHIR, *card, None, Some(*x_value), detail)
        }
        Action::CastReshape {
            card,
            x_value,
            sacrifice,
            payment,
        } => {
            let mut out = spell_key(
                KIND_CAST_RESHAPE,
                *card,
                None,
                Some(*x_value),
                payment_detail(*payment),
            );
            out.source = Some(canonical_for_object(object_classes, *sacrifice)?);
            out
        }
        Action::ActivateRepurposingBay {
            source,
            sacrifice,
            payment,
        } => {
            let mut out = source_key(
                KIND_REPURPOSING_BAY,
                *source,
                state,
                object_classes,
                payment_detail(*payment),
            )?;
            out.target = Some(canonical_for_object(object_classes, *sacrifice)?);
            out
        }
        Action::ActivateTopLook { source, payment } => source_key(
            KIND_TOP_LOOK,
            *source,
            state,
            object_classes,
            payment_detail(*payment),
        )?,
        Action::ActivateTopDraw { source } => source_key(
            KIND_TOP_DRAW,
            *source,
            state,
            object_classes,
            Vec::new(),
        )?,
        Action::ActivateUrzaSpin { source, payment } => source_key(
            KIND_URZA_SPIN,
            *source,
            state,
            object_classes,
            payment_detail(*payment),
        )?,
        Action::ActivateTezzeretMinusThree { source } => source_key(
            KIND_TEZZERET_MINUS_THREE,
            *source,
            state,
            object_classes,
            Vec::new(),
        )?,
        Action::ActivateRealityChipReconfigure {
            source,
            target,
            payment,
        } => {
            let mut out = source_key(
                KIND_REALITY_CHIP_RECONFIGURE,
                *source,
                state,
                object_classes,
                payment_detail(*payment),
            )?;
            out.target = Some(*target);
            out
        }
        Action::ActivateRealityChipDetach { source, payment } => source_key(
            KIND_REALITY_CHIP_DETACH,
            *source,
            state,
            object_classes,
            payment_detail(*payment),
        )?,
        Action::ActivateFortuneTellersTalentLevel { source, payment } => source_key(
            KIND_FTT_LEVEL,
            *source,
            state,
            object_classes,
            payment_detail(*payment),
        )?,
        Action::PlayLibraryTopLand { card, entry } => PolicyPublicKey {
            kind: KIND_PLAY_LIBRARY_TOP_LAND,
            card: Some(*card),
            secondary: land_entry_code(*entry),
            ..PolicyPublicKey::default()
        },
        Action::CastLibraryTop { card, payment } => spell_key(
            KIND_CAST_LIBRARY_TOP,
            *card,
            None,
            None,
            payment_detail(*payment),
        ),
        Action::PlayUrzaPermission {
            permission_slot,
            face,
        } => PolicyPublicKey {
            kind: KIND_PLAY_URZA_PERMISSION,
            card: Some(permission_card(information, *permission_slot)?),
            parameter: Some(*permission_slot),
            secondary: face_code(*face),
            ..PolicyPublicKey::default()
        },
        Action::PlayUrzaPermissionAura {
            permission_slot,
            target,
        } => PolicyPublicKey {
            kind: KIND_PLAY_URZA_PERMISSION_AURA,
            card: Some(permission_card(information, *permission_slot)?),
            target: Some(*target),
            parameter: Some(*permission_slot),
            ..PolicyPublicKey::default()
        },
        Action::CastCommander { payment } => spell_key(
            KIND_CAST_COMMANDER,
            cards.commander_card(),
            None,
            None,
            payment_detail(*payment),
        ),
        Action::ChooseTransmuteSacrifice { artifact } => PolicyPublicKey {
            kind: KIND_CHOOSE_TRANSMUTE_SACRIFICE,
            target: Some(*artifact),
            ..PolicyPublicKey::default()
        },
        Action::ChooseSearchTarget { target } => PolicyPublicKey {
            kind: KIND_CHOOSE_SEARCH_TARGET,
            card: *target,
            secondary: u16::from(target.is_some()),
            ..PolicyPublicKey::default()
        },
        Action::PayTransmuteDifference { payment } => PolicyPublicKey {
            kind: KIND_PAY_TRANSMUTE_DIFFERENCE,
            detail: optional_payment_detail(*payment),
            ..PolicyPublicKey::default()
        },
        Action::ChooseTopOrder { order } => PolicyPublicKey {
            kind: KIND_CHOOSE_TOP_ORDER,
            detail: card_sequence(order),
            ..PolicyPublicKey::default()
        },
        Action::ChooseScry { top, bottom } => {
            let mut detail = Vec::with_capacity(top.len() + bottom.len() + 2);
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
        Action::ChooseProducerUntap { untap } => PolicyPublicKey {
            kind: KIND_CHOOSE_PRODUCER_UNTAP,
            secondary: u16::from(*untap),
            ..PolicyPublicKey::default()
        },
        Action::ChooseCamTarget { target } => PolicyPublicKey {
            kind: KIND_CHOOSE_CAM_TARGET,
            target: Some(*target),
            ..PolicyPublicKey::default()
        },
        Action::ChooseCamEffect { choice } => PolicyPublicKey {
            kind: KIND_CHOOSE_CAM_EFFECT,
            secondary: cam_choice_code(*choice),
            ..PolicyPublicKey::default()
        },
    };
    Ok(key)
}

fn key(kind: u16) -> PolicyPublicKey {
    PolicyPublicKey {
        kind,
        ..PolicyPublicKey::default()
    }
}

fn spell_key(
    kind: u16,
    card: CardDefId,
    target: Option<CanonicalObjectId>,
    parameter: Option<u16>,
    detail: Vec<u16>,
) -> PolicyPublicKey {
    PolicyPublicKey {
        kind,
        card: Some(card),
        target,
        parameter,
        detail,
        ..PolicyPublicKey::default()
    }
}

fn source_key(
    kind: u16,
    source: ObjectId,
    state: &TrueState,
    object_classes: &BTreeMap<ObjectId, CanonicalObjectId>,
    detail: Vec<u16>,
) -> Result<PolicyPublicKey, BridgeError> {
    let permanent = state
        .battlefield
        .get(source)
        .ok_or(BridgeError::MissingCanonicalClass(source))?;
    Ok(PolicyPublicKey {
        kind,
        card: Some(permanent.card),
        source: Some(canonical_for_object(object_classes, source)?),
        detail,
        ..PolicyPublicKey::default()
    })
}

fn canonical_for_object(
    object_classes: &BTreeMap<ObjectId, CanonicalObjectId>,
    object: ObjectId,
) -> Result<CanonicalObjectId, BridgeError> {
    object_classes
        .get(&object)
        .copied()
        .ok_or(BridgeError::MissingCanonicalClass(object))
}

fn permission_card(
    information: &InformationState,
    permission_slot: u16,
) -> Result<CardDefId, BridgeError> {
    information
        .urza_permissions
        .iter()
        .find(|permission| permission.permission_slot == permission_slot)
        .map(|permission| permission.card)
        .ok_or(BridgeError::MissingPermissionSlot(permission_slot))
}

fn payment_detail(payment: ManaPayment) -> Vec<u16> {
    vec![
        payment.white,
        payment.blue,
        payment.black,
        payment.red,
        payment.green,
        payment.colorless,
    ]
}

fn optional_payment_detail(payment: Option<ManaPayment>) -> Vec<u16> {
    match payment {
        Some(payment) => {
            let mut detail = vec![1];
            detail.extend(payment_detail(payment));
            detail
        }
        None => vec![0],
    }
}

fn card_sequence(cards: &[CardDefId]) -> Vec<u16> {
    cards.iter().map(|card| card.0).collect()
}

const fn land_entry_code(entry: LandEntryChoice) -> u16 {
    match entry {
        LandEntryChoice::Default => 0,
        LandEntryChoice::PayLife => 1,
    }
}

const fn face_code(face: CardFace) -> u16 {
    match face {
        CardFace::Front => 0,
        CardFace::Back => 1,
    }
}

const fn cam_choice_code(choice: CamEffectChoice) -> u16 {
    match choice {
        CamEffectChoice::Decline => 0,
        CamEffectChoice::Tap => 1,
        CamEffectChoice::Untap => 2,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use urza_cards::R4CardDatabase;
    use urza_core::{
        BattlefieldZone, CardFace, CardZone, CounterState, GenericCost, ManaPool, PendingDecision,
        PermanentMode, PermanentState, Phase, SourceRef, TrueLibrary, Window,
    };
    use urza_policy::DeterministicPolicy;
    use urza_rules::{CardDatabase, apply_action};

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

    fn priority_state() -> TrueState {
        TrueState {
            turn: 1,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            ..TrueState::default()
        }
    }

    #[test]
    fn distinct_legal_mana_payments_survive_as_distinct_public_candidates() {
        let cards = R4CardDatabase::load().unwrap();
        let sol_ring = cards.card_id_by_name("Sol Ring").unwrap();
        let mut state = priority_state();
        state.hand = CardZone::new(vec![sol_ring]);
        state.mana = ManaPool {
            blue: 1,
            colorless: 1,
            ..ManaPool::default()
        };

        let bridge = CandidateBridge::build(&state, &cards).unwrap();
        let cast_tokens: Vec<_> = bridge
            .candidates()
            .iter()
            .filter_map(|candidate| {
                let action = bridge.resolve(candidate.token)?;
                matches!(action, Action::CastFromHand { card, .. } if *card == sol_ring)
                    .then_some(candidate.token)
            })
            .collect();
        assert_eq!(cast_tokens.len(), 2);

        let payments: BTreeSet<_> = cast_tokens
            .iter()
            .filter_map(|token| match bridge.resolve(*token) {
                Some(Action::CastFromHand { payment, .. }) => Some((payment.blue, payment.colorless)),
                _ => None,
            })
            .collect();
        assert_eq!(payments, BTreeSet::from([(0, 1), (1, 0)]));
    }

    #[test]
    fn raw_object_id_renaming_preserves_candidates_and_selected_observed_result() {
        let cards = R4CardDatabase::load().unwrap();
        let sol_ring = cards.card_id_by_name("Sol Ring").unwrap();
        let mut left = priority_state();
        left.battlefield = BattlefieldZone::new(vec![permanent(7, sol_ring)]);
        let mut right = priority_state();
        right.battlefield = BattlefieldZone::new(vec![permanent(91, sol_ring)]);

        let left_bridge = CandidateBridge::build(&left, &cards).unwrap();
        let right_bridge = CandidateBridge::build(&right, &cards).unwrap();
        assert_eq!(left_bridge.information(), right_bridge.information());
        assert_eq!(left_bridge.candidates(), right_bridge.candidates());

        let policy = DeterministicPolicy;
        let left_token = policy
            .choose(left_bridge.information(), left_bridge.candidates())
            .unwrap()
            .unwrap();
        let right_token = policy
            .choose(right_bridge.information(), right_bridge.candidates())
            .unwrap()
            .unwrap();
        assert_eq!(left_token, right_token);

        let left_action = left_bridge.resolved_action(left_token).unwrap();
        let right_action = right_bridge.resolved_action(right_token).unwrap();
        assert_ne!(left_action, right_action);
        apply_action(&mut left, &cards, left_action).unwrap();
        apply_action(&mut right, &cards, right_action).unwrap();
        assert_eq!(observe(&left).unwrap(), observe(&right).unwrap());
    }

    #[test]
    fn hidden_library_permutation_cannot_change_candidate_identity() {
        let cards = R4CardDatabase::load().unwrap();
        let sol_ring = cards.card_id_by_name("Sol Ring").unwrap();
        let island = cards.card_id_by_name("Island").unwrap();
        let basalt = cards.card_id_by_name("Basalt Monolith").unwrap();
        let mut left = priority_state();
        left.library = TrueLibrary::unknown(vec![sol_ring, island, basalt]);
        left.hand = CardZone::new(vec![island]);
        let mut right = left.clone();
        right.library = TrueLibrary::unknown(vec![basalt, sol_ring, island]);

        let left_bridge = CandidateBridge::build(&left, &cards).unwrap();
        let right_bridge = CandidateBridge::build(&right, &cards).unwrap();
        assert_eq!(left_bridge.information(), right_bridge.information());
        assert_eq!(left_bridge.candidates(), right_bridge.candidates());
    }

    #[test]
    fn whir_x_and_improvise_multiset_are_preserved_in_round_trip() {
        let cards = R4CardDatabase::load().unwrap();
        let whir = cards.card_id_by_name("Whir of Invention").unwrap();
        let sol_ring = cards.card_id_by_name("Sol Ring").unwrap();
        let mana_vault = cards.card_id_by_name("Mana Vault").unwrap();
        let mut state = priority_state();
        state.hand = CardZone::new(vec![whir]);
        state.battlefield = BattlefieldZone::new(vec![
            permanent(11, sol_ring),
            permanent(29, mana_vault),
        ]);
        state.mana = ManaPool {
            blue: 3,
            ..ManaPool::default()
        };

        let bridge = CandidateBridge::build(&state, &cards).unwrap();
        let whir_actions: Vec<_> = bridge
            .candidates()
            .iter()
            .filter_map(|candidate| match bridge.resolve(candidate.token) {
                Some(action @ Action::CastWhir { .. }) => Some((candidate, action)),
                _ => None,
            })
            .collect();
        assert!(whir_actions.iter().any(|(_, action)| matches!(
            action,
            Action::CastWhir { x_value: 1, improvise_sources, .. } if improvise_sources.len() == 1
        )));
        assert!(whir_actions.iter().any(|(_, action)| matches!(
            action,
            Action::CastWhir { x_value: 2, improvise_sources, .. } if improvise_sources.len() == 2
        )));
        let semantic_keys: BTreeSet<_> = whir_actions
            .iter()
            .map(|(candidate, _)| candidate.key.clone())
            .collect();
        assert_eq!(semantic_keys.len(), whir_actions.len());
    }

    #[test]
    fn equivalent_source_objects_collapse_to_one_public_mana_choice() {
        let cards = R4CardDatabase::load().unwrap();
        let island = cards.card_id_by_name("Island").unwrap();
        let mut state = priority_state();
        state.battlefield = BattlefieldZone::new(vec![permanent(4, island), permanent(40, island)]);

        let bridge = CandidateBridge::build(&state, &cards).unwrap();
        let mana_actions: Vec<_> = bridge
            .candidates()
            .iter()
            .filter(|candidate| {
                matches!(
                    bridge.resolve(candidate.token),
                    Some(Action::ActivateManaAbility { .. })
                )
            })
            .collect();
        assert_eq!(mana_actions.len(), 1);
    }

    #[test]
    fn transmute_difference_pending_keeps_mana_abilities_in_contingent_set() {
        let cards = R4CardDatabase::load().unwrap();
        let transmute = cards.card_id_by_name("Transmute Artifact").unwrap();
        let basalt = cards.card_id_by_name("Basalt Monolith").unwrap();
        let sol_ring = cards.card_id_by_name("Sol Ring").unwrap();
        let mut state = priority_state();
        state.window = Window::Resolving;
        state.battlefield = BattlefieldZone::new(vec![permanent(8, sol_ring)]);
        state.pending = PendingDecision::TransmuteDifferencePayment {
            source: SourceRef {
                object_id: None,
                card: transmute,
            },
            target: basalt,
            difference: GenericCost(2),
        };

        let bridge = CandidateBridge::build(&state, &cards).unwrap();
        assert!(bridge.candidates().iter().all(|candidate| {
            candidate.class == PolicyActionClass::ContingentDecision
        }));
        assert!(bridge.candidates().iter().any(|candidate| matches!(
            bridge.resolve(candidate.token),
            Some(Action::ActivateManaAbility { .. })
        )));
        assert!(bridge.candidates().iter().any(|candidate| matches!(
            bridge.resolve(candidate.token),
            Some(Action::PayTransmuteDifference { payment: None })
        )));
    }

    #[test]
    fn bridge_surface_counts_match_the_exhaustive_action_mapping() {
        assert_eq!(ORDINARY_ACTION_FAMILY_COUNT, 26);
        assert_eq!(CONTINGENT_ACTION_FAMILY_COUNT, 8);
    }

    #[test]
    fn real_r4_database_still_exposes_only_accepted_profiles_to_bridge() {
        let cards = R4CardDatabase::load().unwrap();
        let chrome = cards.card_id_by_name("Chrome Dome").unwrap();
        assert_eq!(cards.profile(chrome).unwrap().engine, EngineKind::ChromeDome);
    }
}
