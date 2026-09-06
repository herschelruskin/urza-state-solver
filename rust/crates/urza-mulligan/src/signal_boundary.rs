use std::fmt;

use urza_cards::R4CardDatabase;
use urza_core::{
    BattlefieldZone, CardDefId, CardFace, CardZone, CommanderState, CommanderZone, CounterState,
    ManaPool, ObjectId, PermanentMode, PermanentState, Phase, SourceRef, StackObject, TrueLibrary,
    TrueState, Window,
};
use urza_info::{ObservationError, observe};
use urza_mc::{MonteCarloConfig, MonteCarloError, evaluate};
use urza_policy::DeterministicPolicy;
use urza_rng::{RootSeed, WorldId};
use urza_rules::{R2CardRole, WinFamily, detect_terminal_win};

use crate::{TeacherSearchConfig, TeacherSearchError, TeacherSearchResult, evaluate_teacher};

pub const R7_SIGNAL_BOUNDARY_VERSION: &str = "r7_signal_boundary_v1";
pub const R7_SIGNAL_BOUNDARY_STATE_VERSION: &str = "r7_three_family_four_tier_states_v1";
pub const R7_SIGNAL_BOUNDARY_R5_ROOT_SEED: u64 = 0x5237_424f_554e_0001;
pub const R7_SIGNAL_BOUNDARY_TEACHER_ROOT_SEED: u64 = 0x5237_424f_554e_0002;
pub const R7_SIGNAL_BOUNDARY_FIRST_WORLD: WorldId = WorldId(940_000);
pub const R7_SIGNAL_BOUNDARY_R5_SAMPLES: u32 = 1;
pub const R7_SIGNAL_BOUNDARY_TEACHER_SAMPLES: u32 = 1;
pub const R7_SIGNAL_BOUNDARY_TEACHER_STEPS: u16 = 12;
pub const R7_SIGNAL_BOUNDARY_TEACHER_CANDIDATES: usize = 12;
pub const R7_SIGNAL_BOUNDARY_BOUNDARY: &str = "R7 signal-boundary states are synthetic, public diagnostic states ordered from an already \
     recognized R4 terminal witness backward through stack resolution and one/two hand choices. \
     They are not claimed to be naturally reached opening states. R5 and the bounded R7 teacher \
     evaluate the same state independently with fixed finite budgets. The first zero after a \
     positive result is only an observed signal-loss boundary under these budgets, not proof that \
     the line is impossible. No result can alter R5/R6 policy, mulligan decisions, cache identity, \
     interpretation features, or gameplay rules.";

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum SignalBoundaryTier {
    TerminalWitness,
    StackResolution,
    OneCardInHand,
    TwoCardsInHand,
}

impl SignalBoundaryTier {
    pub const ALL: [Self; 4] = [
        Self::TerminalWitness,
        Self::StackResolution,
        Self::OneCardInHand,
        Self::TwoCardsInHand,
    ];

    pub const fn label(self) -> &'static str {
        match self {
            Self::TerminalWitness => "terminal-witness",
            Self::StackResolution => "stack-resolution",
            Self::OneCardInHand => "one-card-in-hand",
            Self::TwoCardsInHand => "two-cards-in-hand",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SignalBoundaryCase {
    pub case_name: &'static str,
    pub family: WinFamily,
    pub tier: SignalBoundaryTier,
    pub state: TrueState,
    pub involved_cards: Vec<CardDefId>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TeacherDepthProbe {
    pub max_choice_depth: u8,
    pub result: TeacherSearchResult,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SignalBoundaryProbe {
    pub case_name: &'static str,
    pub family: WinFamily,
    pub tier: SignalBoundaryTier,
    pub entry_terminal: Option<WinFamily>,
    pub unsupported_involved_cards: u32,
    pub hand_cards: u32,
    pub battlefield_permanents: u32,
    pub stack_objects: u32,
    pub r5_wins: u32,
    pub r5_samples: u32,
    pub teacher: Vec<TeacherDepthProbe>,
}

impl SignalBoundaryProbe {
    pub fn teacher_at_depth(&self, depth: u8) -> Option<&TeacherSearchResult> {
        self.teacher
            .iter()
            .find(|probe| probe.max_choice_depth == depth)
            .map(|probe| &probe.result)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SignalBoundaryReport {
    pub version: &'static str,
    pub state_version: &'static str,
    pub boundary: &'static str,
    pub probes: Vec<SignalBoundaryProbe>,
}

pub fn build_signal_boundary_cases(
    cards: &R4CardDatabase,
) -> Result<Vec<SignalBoundaryCase>, SignalBoundaryError> {
    let island = card(cards, "Island")?;
    let urza = card(cards, "Urza, Lord High Artificer")?;
    let power_artifact = card(cards, "Power Artifact")?;
    let basalt = card(cards, "Basalt Monolith")?;
    let gadgeteer = card(cards, "Forensic Gadgeteer")?;
    let top = card(cards, "Sensei's Divining Top")?;
    let reality_chip = card(cards, "The Reality Chip")?;
    let floodcaller = card(cards, "Valley Floodcaller")?;

    let mut cases = Vec::with_capacity(12);

    let mut terminal = base_state(island, urza);
    let mut aura = permanent(30, power_artifact);
    aura.attached_to = Some(ObjectId(20));
    terminal.battlefield = with_urza(urza, vec![permanent(20, basalt), aura]);
    cases.push(case(
        "pa-basalt-terminal",
        WinFamily::PowerArtifactBasalt,
        SignalBoundaryTier::TerminalWitness,
        terminal,
        vec![urza, power_artifact, basalt],
    ));

    let mut stack = base_state(island, urza);
    stack.battlefield = with_urza(urza, vec![permanent(20, basalt)]);
    stack.stack.push(StackObject::AuraSpell {
        object_id: ObjectId(900),
        card: power_artifact,
        target: SourceRef {
            object_id: Some(ObjectId(20)),
            card: basalt,
        },
    });
    cases.push(case(
        "pa-basalt-stack",
        WinFamily::PowerArtifactBasalt,
        SignalBoundaryTier::StackResolution,
        stack,
        vec![urza, power_artifact, basalt],
    ));

    let mut one_hand = base_state(island, urza);
    one_hand.battlefield = with_urza(urza, vec![permanent(20, basalt)]);
    one_hand.hand = CardZone::new(vec![power_artifact]);
    cases.push(case(
        "pa-basalt-one-hand",
        WinFamily::PowerArtifactBasalt,
        SignalBoundaryTier::OneCardInHand,
        one_hand,
        vec![urza, power_artifact, basalt],
    ));

    let mut two_hand = base_state(island, urza);
    two_hand.hand = CardZone::new(vec![power_artifact, basalt]);
    cases.push(case(
        "pa-basalt-two-hand",
        WinFamily::PowerArtifactBasalt,
        SignalBoundaryTier::TwoCardsInHand,
        two_hand,
        vec![urza, power_artifact, basalt],
    ));

    let mut terminal = base_state(island, urza);
    terminal.battlefield = with_urza(
        urza,
        vec![permanent(20, basalt), permanent(30, gadgeteer)],
    );
    cases.push(case(
        "basalt-gadgeteer-terminal",
        WinFamily::BasaltGadgeteer,
        SignalBoundaryTier::TerminalWitness,
        terminal,
        vec![urza, basalt, gadgeteer],
    ));

    let mut stack = base_state(island, urza);
    stack.battlefield = with_urza(urza, vec![permanent(20, basalt)]);
    stack.stack.push(StackObject::Spell {
        object_id: ObjectId(900),
        card: gadgeteer,
        x_value: None,
    });
    cases.push(case(
        "basalt-gadgeteer-stack",
        WinFamily::BasaltGadgeteer,
        SignalBoundaryTier::StackResolution,
        stack,
        vec![urza, basalt, gadgeteer],
    ));

    let mut one_hand = base_state(island, urza);
    one_hand.battlefield = with_urza(urza, vec![permanent(20, basalt)]);
    one_hand.hand = CardZone::new(vec![gadgeteer]);
    cases.push(case(
        "basalt-gadgeteer-one-hand",
        WinFamily::BasaltGadgeteer,
        SignalBoundaryTier::OneCardInHand,
        one_hand,
        vec![urza, basalt, gadgeteer],
    ));

    let mut two_hand = base_state(island, urza);
    two_hand.hand = CardZone::new(vec![basalt, gadgeteer]);
    cases.push(case(
        "basalt-gadgeteer-two-hand",
        WinFamily::BasaltGadgeteer,
        SignalBoundaryTier::TwoCardsInHand,
        two_hand,
        vec![urza, basalt, gadgeteer],
    ));

    let mut terminal = top_chip_base(island, urza, top, reality_chip, floodcaller);
    let mut permanents = terminal.battlefield.permanents().to_vec();
    permanents.push(permanent(40, gadgeteer));
    terminal.battlefield = BattlefieldZone::new(permanents);
    cases.push(case(
        "top-chip-terminal",
        WinFamily::TopRealityChip,
        SignalBoundaryTier::TerminalWitness,
        terminal,
        vec![urza, top, reality_chip, floodcaller, gadgeteer],
    ));

    let mut stack = top_chip_base(island, urza, top, reality_chip, floodcaller);
    stack.stack.push(StackObject::Spell {
        object_id: ObjectId(900),
        card: gadgeteer,
        x_value: None,
    });
    cases.push(case(
        "top-chip-stack",
        WinFamily::TopRealityChip,
        SignalBoundaryTier::StackResolution,
        stack,
        vec![urza, top, reality_chip, floodcaller, gadgeteer],
    ));

    let mut one_hand = top_chip_base(island, urza, top, reality_chip, floodcaller);
    one_hand.hand = CardZone::new(vec![gadgeteer]);
    cases.push(case(
        "top-chip-one-hand",
        WinFamily::TopRealityChip,
        SignalBoundaryTier::OneCardInHand,
        one_hand,
        vec![urza, top, reality_chip, floodcaller, gadgeteer],
    ));

    let mut two_hand = chip_attached_base(island, urza, reality_chip, floodcaller);
    two_hand.hand = CardZone::new(vec![top, gadgeteer]);
    cases.push(case(
        "top-chip-two-hand",
        WinFamily::TopRealityChip,
        SignalBoundaryTier::TwoCardsInHand,
        two_hand,
        vec![urza, top, reality_chip, floodcaller, gadgeteer],
    ));

    Ok(cases)
}

pub fn run_signal_boundary() -> Result<SignalBoundaryReport, SignalBoundaryError> {
    let cards = R4CardDatabase::load()
        .map_err(|error| SignalBoundaryError::Setup(format!("R4 card database failed: {error}")))?;
    let policy = DeterministicPolicy;
    let cases = build_signal_boundary_cases(&cards)?;
    let mut probes = Vec::with_capacity(cases.len());

    for (index, case) in cases.into_iter().enumerate() {
        case.state.validate().map_err(|error| {
            SignalBoundaryError::Setup(format!("{} is invalid: {error}", case.case_name))
        })?;
        let world_offset = u64::try_from(index).map_err(|_| SignalBoundaryError::WorldOverflow)?;
        let world = WorldId(
            R7_SIGNAL_BOUNDARY_FIRST_WORLD
                .0
                .checked_add(world_offset)
                .ok_or(SignalBoundaryError::WorldOverflow)?,
        );
        let information = observe(&case.state)?;
        let entry_terminal = detect_terminal_win(&information, &cards);
        let r5 = evaluate(
            &case.state,
            &cards,
            &policy,
            MonteCarloConfig {
                root: RootSeed::from_u64(R7_SIGNAL_BOUNDARY_R5_ROOT_SEED),
                first_world: world,
                samples: R7_SIGNAL_BOUNDARY_R5_SAMPLES,
                rollout_max_steps: urza_rollout::DEFAULT_MAX_STEPS,
            },
        )?;

        let mut teacher = Vec::with_capacity(3);
        for depth in [0_u8, 1, 2] {
            let result = evaluate_teacher(
                &case.state,
                &cards,
                TeacherSearchConfig {
                    root: RootSeed::from_u64(R7_SIGNAL_BOUNDARY_TEACHER_ROOT_SEED),
                    first_world: world,
                    samples: R7_SIGNAL_BOUNDARY_TEACHER_SAMPLES,
                    max_choice_depth: depth,
                    max_teacher_steps: R7_SIGNAL_BOUNDARY_TEACHER_STEPS,
                    max_candidates_per_group: R7_SIGNAL_BOUNDARY_TEACHER_CANDIDATES,
                    leaf_rollout_max_steps: urza_rollout::DEFAULT_MAX_STEPS,
                },
            )?;
            teacher.push(TeacherDepthProbe {
                max_choice_depth: depth,
                result,
            });
        }

        let unsupported_involved_cards = u32::try_from(
            case.involved_cards
                .iter()
                .filter(|card| {
                    cards
                        .profile(**card)
                        .is_none_or(|profile| profile.role == R2CardRole::Unsupported)
                })
                .count(),
        )
        .map_err(|_| SignalBoundaryError::CountOverflow)?;

        probes.push(SignalBoundaryProbe {
            case_name: case.case_name,
            family: case.family,
            tier: case.tier,
            entry_terminal,
            unsupported_involved_cards,
            hand_cards: u32::try_from(case.state.hand.len())
                .map_err(|_| SignalBoundaryError::CountOverflow)?,
            battlefield_permanents: u32::try_from(case.state.battlefield.len())
                .map_err(|_| SignalBoundaryError::CountOverflow)?,
            stack_objects: u32::try_from(case.state.stack.len())
                .map_err(|_| SignalBoundaryError::CountOverflow)?,
            r5_wins: r5.wins(),
            r5_samples: u32::try_from(r5.samples())
                .map_err(|_| SignalBoundaryError::CountOverflow)?,
            teacher,
        });
    }

    Ok(SignalBoundaryReport {
        version: R7_SIGNAL_BOUNDARY_VERSION,
        state_version: R7_SIGNAL_BOUNDARY_STATE_VERSION,
        boundary: R7_SIGNAL_BOUNDARY_BOUNDARY,
        probes,
    })
}

fn case(
    case_name: &'static str,
    family: WinFamily,
    tier: SignalBoundaryTier,
    state: TrueState,
    involved_cards: Vec<CardDefId>,
) -> SignalBoundaryCase {
    SignalBoundaryCase {
        case_name,
        family,
        tier,
        state,
        involved_cards,
    }
}

fn card(cards: &R4CardDatabase, name: &'static str) -> Result<CardDefId, SignalBoundaryError> {
    cards.card_id_by_name(name).map_err(|error| {
        SignalBoundaryError::Setup(format!("R4 card lookup for {name} failed: {error}"))
    })
}

fn base_state(island: CardDefId, urza: CardDefId) -> TrueState {
    TrueState {
        turn: 2,
        phase: Phase::PrecombatMain,
        window: Window::Priority,
        life: 40,
        library: TrueLibrary::unknown(vec![island]),
        battlefield: with_urza(urza, Vec::new()),
        mana: ManaPool {
            blue: 12,
            colorless: 12,
            ..ManaPool::default()
        },
        commander: CommanderState {
            zone: CommanderZone::Battlefield,
            command_zone_casts: 1,
        },
        ..TrueState::default()
    }
}

fn with_urza(urza: CardDefId, mut permanents: Vec<PermanentState>) -> BattlefieldZone {
    permanents.push(permanent(1, urza));
    BattlefieldZone::new(permanents)
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

fn chip_attached_base(
    island: CardDefId,
    urza: CardDefId,
    reality_chip: CardDefId,
    floodcaller: CardDefId,
) -> TrueState {
    let mut state = base_state(island, urza);
    let floodcaller_permanent = permanent(10, floodcaller);
    let mut chip = permanent(30, reality_chip);
    chip.mode = PermanentMode::RealityChipAttached;
    chip.attached_to = Some(floodcaller_permanent.object_id);
    state.battlefield = with_urza(urza, vec![floodcaller_permanent, chip]);
    state
}

fn top_chip_base(
    island: CardDefId,
    urza: CardDefId,
    top: CardDefId,
    reality_chip: CardDefId,
    floodcaller: CardDefId,
) -> TrueState {
    let mut state = chip_attached_base(island, urza, reality_chip, floodcaller);
    let mut permanents = state.battlefield.permanents().to_vec();
    permanents.push(permanent(20, top));
    state.battlefield = BattlefieldZone::new(permanents);
    state
}

#[derive(Debug)]
pub enum SignalBoundaryError {
    Setup(String),
    WorldOverflow,
    CountOverflow,
    Observation(ObservationError),
    MonteCarlo(MonteCarloError),
    Teacher(TeacherSearchError),
}

impl fmt::Display for SignalBoundaryError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Setup(message) => write!(formatter, "R7 signal boundary setup failed: {message}"),
            Self::WorldOverflow => write!(formatter, "R7 signal boundary world id overflow"),
            Self::CountOverflow => write!(formatter, "R7 signal boundary count exceeded u32"),
            Self::Observation(error) => {
                write!(formatter, "R7 signal boundary observation failed: {error}")
            }
            Self::MonteCarlo(error) => write!(
                formatter,
                "R7 signal boundary R5 evaluation failed: {error}"
            ),
            Self::Teacher(error) => write!(
                formatter,
                "R7 signal boundary teacher evaluation failed: {error}"
            ),
        }
    }
}

impl std::error::Error for SignalBoundaryError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Observation(error) => Some(error),
            Self::MonteCarlo(error) => Some(error),
            Self::Teacher(error) => Some(error),
            _ => None,
        }
    }
}

impl From<ObservationError> for SignalBoundaryError {
    fn from(value: ObservationError) -> Self {
        Self::Observation(value)
    }
}

impl From<MonteCarloError> for SignalBoundaryError {
    fn from(value: MonteCarloError) -> Self {
        Self::MonteCarlo(value)
    }
}

impl From<TeacherSearchError> for SignalBoundaryError {
    fn from(value: TeacherSearchError) -> Self {
        Self::Teacher(value)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ladders_cover_three_distinct_win_families_and_four_ordered_tiers() {
        let cards = R4CardDatabase::load().expect("R4 database");
        let cases = build_signal_boundary_cases(&cards).expect("diagnostic cases");
        assert_eq!(cases.len(), 12);

        for family in [
            WinFamily::PowerArtifactBasalt,
            WinFamily::BasaltGadgeteer,
            WinFamily::TopRealityChip,
        ] {
            let family_cases: Vec<_> = cases.iter().filter(|case| case.family == family).collect();
            assert_eq!(family_cases.len(), SignalBoundaryTier::ALL.len());
            for (case, tier) in family_cases.into_iter().zip(SignalBoundaryTier::ALL) {
                assert_eq!(case.tier, tier);
            }
        }
    }

    #[test]
    fn only_terminal_tier_enters_with_an_r4_terminal_witness() {
        let cards = R4CardDatabase::load().expect("R4 database");
        let cases = build_signal_boundary_cases(&cards).expect("diagnostic cases");
        for case in cases {
            case.state.validate().expect("valid diagnostic state");
            let information = observe(&case.state).expect("observable state");
            let detected = detect_terminal_win(&information, &cards);
            if case.tier == SignalBoundaryTier::TerminalWitness {
                assert_eq!(detected, Some(case.family), "{}", case.case_name);
            } else {
                assert_eq!(detected, None, "{}", case.case_name);
            }
        }
    }

    #[test]
    fn diagnostic_cards_are_all_inside_explicit_r4_rules_coverage() {
        let cards = R4CardDatabase::load().expect("R4 database");
        let cases = build_signal_boundary_cases(&cards).expect("diagnostic cases");
        for case in cases {
            for card in case.involved_cards {
                let profile = cards.profile(card).expect("R4 profile");
                assert_ne!(profile.role, R2CardRole::Unsupported, "{}", case.case_name);
            }
        }
    }
}
