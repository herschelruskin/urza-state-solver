#![forbid(unsafe_code)]

mod adaptive;
pub use adaptive::*;
mod parallel;
pub use parallel::*;
mod root;
pub use root::*;

use thiserror::Error;
use urza_core::{TrueLibrary, TrueState};
use urza_info::{LibraryBelief, ObservationError, observe};
use urza_policy::DeterministicPolicy;
use urza_rng::{
    EventOccurrence, EventType, LogicalEventId, RngCoordinate, RngDomain, RootSeed, WorldId,
    shuffle,
};
use urza_rollout::{RolloutConfig, RolloutError, RolloutStop, rollout};
use urza_rules::{CardDatabase, HORIZON_TURN, WinFamily};
use urza_value::WinDistribution;

pub const MONTE_CARLO_VERSION: &str = "r5_hidden_world_mc_v1";
pub const HIDDEN_WORLD_EVENT_TYPE: EventType = EventType(0x0501);
const HIDDEN_WORLD_LOGICAL_EVENT: LogicalEventId = LogicalEventId(0);

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct MonteCarloConfig {
    pub root: RootSeed,
    pub first_world: WorldId,
    pub samples: u32,
    pub rollout_max_steps: u32,
}

impl Default for MonteCarloConfig {
    fn default() -> Self {
        Self {
            root: RootSeed::from_u64(0x5235_4d4f_4e54_4501),
            first_world: WorldId(0),
            samples: 256,
            rollout_max_steps: urza_rollout::DEFAULT_MAX_STEPS,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum SampleOutcome {
    Win { family: WinFamily, turn: u8 },
    LossByHorizon,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct WorldOutcome {
    pub world: WorldId,
    pub outcome: SampleOutcome,
    pub rollout_steps: u32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct FamilyWinCount {
    pub family: WinFamily,
    pub wins: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MonteCarloResult {
    pub outcomes: Vec<WorldOutcome>,
    pub win_distribution: WinDistribution,
    pub family_wins: Vec<FamilyWinCount>,
}

impl MonteCarloResult {
    pub fn samples(&self) -> usize {
        self.outcomes.len()
    }

    pub fn wins(&self) -> u32 {
        self.win_distribution.wins()
    }

    pub fn losses(&self) -> u32 {
        self.win_distribution.losses
    }
}

#[derive(Debug, Error)]
pub enum MonteCarloError {
    #[error(transparent)]
    Observation(#[from] ObservationError),
    #[error("Monte Carlo evaluation requires at least one sampled world")]
    NoSamples,
    #[error("sampled world id range overflowed u64")]
    WorldIdOverflow,
    #[error("sampled world id {0:?} appears more than once")]
    DuplicateWorld(WorldId),
    #[error("hidden-world sampling changed public information for world {0:?}")]
    PublicStateDrift(WorldId),
    #[error("rollout failed for sampled world {world:?}: {source}")]
    WorldRollout {
        world: WorldId,
        #[source]
        source: RolloutError,
    },
    #[error("sampled world {world:?} stopped incompletely at {stop:?}")]
    IncompleteWorld { world: WorldId, stop: RolloutStop },
    #[error("sampled world {world:?} reached a terminal win on out-of-horizon turn {turn}")]
    TerminalOutsideHorizon { world: WorldId, turn: u8 },
    #[error("rollout trace length exceeded u32")]
    TraceLengthOverflow,
    #[error("Monte Carlo aggregate counter overflow")]
    CounterOverflow,
    #[error("sampled library reconstruction was invalid: {0}")]
    InvalidSampledLibrary(#[from] urza_core::StateValidationError),
}

pub fn sample_hidden_world(
    template: &TrueState,
    root: RootSeed,
    world: WorldId,
) -> Result<TrueState, MonteCarloError> {
    let public = observe(template)?;
    let knowledge = template.library.knowledge();
    let known_top = template.library.known_top().to_vec();
    let known_bottom = template.library.known_bottom().to_vec();
    let mut unknown_middle = template.library.unknown_middle().to_vec();

    unknown_middle.sort_unstable();
    shuffle(
        &mut unknown_middle,
        root,
        hidden_world_coordinate(&public.library, world),
    );

    let mut cards = Vec::with_capacity(template.library.cards().len());
    cards.extend(known_top);
    cards.extend(unknown_middle);
    cards.extend(known_bottom);

    let mut sampled = template.clone();
    sampled.library = TrueLibrary::new(cards, knowledge)?;
    if observe(&sampled)? != public {
        return Err(MonteCarloError::PublicStateDrift(world));
    }
    Ok(sampled)
}

pub fn evaluate<D: CardDatabase>(
    template: &TrueState,
    cards: &D,
    policy: &DeterministicPolicy,
    config: MonteCarloConfig,
) -> Result<MonteCarloResult, MonteCarloError> {
    if config.samples == 0 {
        return Err(MonteCarloError::NoSamples);
    }

    let mut worlds = Vec::with_capacity(config.samples as usize);
    for offset in 0..config.samples {
        let world = config
            .first_world
            .0
            .checked_add(u64::from(offset))
            .ok_or(MonteCarloError::WorldIdOverflow)?;
        worlds.push(WorldId(world));
    }

    evaluate_world_ids(
        template,
        cards,
        policy,
        config.root,
        config.rollout_max_steps,
        &worlds,
    )
}

pub fn evaluate_world_ids<D: CardDatabase>(
    template: &TrueState,
    cards: &D,
    policy: &DeterministicPolicy,
    root: RootSeed,
    rollout_max_steps: u32,
    world_ids: &[WorldId],
) -> Result<MonteCarloResult, MonteCarloError> {
    if world_ids.is_empty() {
        return Err(MonteCarloError::NoSamples);
    }
    let mut worlds = world_ids.to_vec();
    worlds.sort_unstable_by_key(|world| world.0);
    for pair in worlds.windows(2) {
        if pair[0] == pair[1] {
            return Err(MonteCarloError::DuplicateWorld(pair[0]));
        }
    }

    let mut result = MonteCarloResult {
        outcomes: Vec::with_capacity(worlds.len()),
        win_distribution: WinDistribution::default(),
        family_wins: WinFamily::ALL
            .into_iter()
            .map(|family| FamilyWinCount { family, wins: 0 })
            .collect(),
    };

    for world in worlds {
        let sampled = sample_hidden_world(template, root, world)?;
        let rollout = rollout(
            sampled,
            cards,
            policy,
            RolloutConfig {
                root,
                world,
                max_steps: rollout_max_steps,
            },
        )
        .map_err(|source| MonteCarloError::WorldRollout { world, source })?;
        let steps = u32::try_from(rollout.trace.len())
            .map_err(|_| MonteCarloError::TraceLengthOverflow)?;
        let outcome = match rollout.stop {
            RolloutStop::Terminal(family) => {
                let turn = rollout.final_information.turn;
                if !(1..=HORIZON_TURN).contains(&turn) {
                    return Err(MonteCarloError::TerminalOutsideHorizon { world, turn });
                }
                let bucket = usize::from(turn - 1);
                result.win_distribution.t1_through_t6[bucket] = result.win_distribution
                    .t1_through_t6[bucket]
                    .checked_add(1)
                    .ok_or(MonteCarloError::CounterOverflow)?;
                let entry = result
                    .family_wins
                    .iter_mut()
                    .find(|entry| entry.family == family)
                    .expect("WinFamily::ALL contains every terminal family");
                entry.wins = entry
                    .wins
                    .checked_add(1)
                    .ok_or(MonteCarloError::CounterOverflow)?;
                SampleOutcome::Win { family, turn }
            }
            RolloutStop::Horizon => {
                result.win_distribution.losses = result
                    .win_distribution
                    .losses
                    .checked_add(1)
                    .ok_or(MonteCarloError::CounterOverflow)?;
                SampleOutcome::LossByHorizon
            }
            stop @ (RolloutStop::StepLimit | RolloutStop::NoCandidate) => {
                return Err(MonteCarloError::IncompleteWorld { world, stop });
            }
        };
        result.outcomes.push(WorldOutcome {
            world,
            outcome,
            rollout_steps: steps,
        });
    }

    Ok(result)
}

fn hidden_world_coordinate(library: &LibraryBelief, world: WorldId) -> RngCoordinate {
    RngCoordinate {
        domain: RngDomain::OuterHiddenWorld,
        world,
        event_type: HIDDEN_WORLD_EVENT_TYPE,
        logical_event: HIDDEN_WORLD_LOGICAL_EVENT,
        occurrence: EventOccurrence(0),
        concrete_fingerprint: library_belief_fingerprint(library),
    }
}

fn library_belief_fingerprint(library: &LibraryBelief) -> [u8; 16] {
    let mut hasher = blake3::Hasher::new();
    hasher.update(b"r5-hidden-world-library-belief-v1");
    hasher.update(&(library.known_top.len() as u64).to_le_bytes());
    for card in &library.known_top {
        hasher.update(&card.0.to_le_bytes());
    }
    hasher.update(&(library.remaining_counts.len() as u64).to_le_bytes());
    for (card, count) in &library.remaining_counts {
        hasher.update(&card.0.to_le_bytes());
        hasher.update(&count.to_le_bytes());
    }
    hasher.update(&(library.known_bottom.len() as u64).to_le_bytes());
    for card in &library.known_bottom {
        hasher.update(&card.0.to_le_bytes());
    }
    let digest = hasher.finalize();
    let mut fingerprint = [0_u8; 16];
    fingerprint.copy_from_slice(&digest.as_bytes()[..16]);
    fingerprint
}

#[cfg(test)]
mod tests {
    use super::*;
    use urza_cards::R4CardDatabase;
    use urza_core::{
        AttachmentState, BattlefieldZone, CardFace, CardZone, CommanderZone, CounterState,
        LibraryKnowledge, ObjectId, PermanentMode, PermanentState, Phase, TrueLibrary, Window,
    };
    use urza_rules::CardDatabase;

    fn cards() -> R4CardDatabase {
        R4CardDatabase::load().expect("R4 database")
    }

    fn base_state(cards: &R4CardDatabase, library: Vec<urza_core::CardDefId>) -> TrueState {
        let island = cards.card_id_by_name("Island").expect("Island");
        TrueState {
            turn: 2,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(library),
            hand: CardZone::new(vec![island]),
            ..TrueState::default()
        }
    }

    #[test]
    fn sampled_world_preserves_public_information_and_known_edges() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let crypt = cards.card_id_by_name("Tormod's Crypt").expect("Crypt");
        let basalt = cards.card_id_by_name("Basalt Monolith").expect("Basalt");
        let power = cards.card_id_by_name("Power Artifact").expect("Power Artifact");
        let library = TrueLibrary::new(
            vec![island, crypt, basalt, power],
            LibraryKnowledge {
                known_top: 1,
                known_bottom: 1,
            },
        )
        .unwrap();
        let state = TrueState {
            library,
            ..base_state(&cards, Vec::new())
        };
        let sampled = sample_hidden_world(&state, RootSeed::from_u64(7), WorldId(9)).unwrap();
        assert_eq!(sampled.library.known_top(), &[island]);
        assert_eq!(sampled.library.known_bottom(), &[power]);
        assert_eq!(observe(&sampled).unwrap(), observe(&state).unwrap());
    }

    #[test]
    fn preexisting_hidden_order_is_not_a_sampling_input() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let crypt = cards.card_id_by_name("Tormod's Crypt").expect("Crypt");
        let basalt = cards.card_id_by_name("Basalt Monolith").expect("Basalt");
        let left = base_state(&cards, vec![island, crypt, basalt]);
        let right = base_state(&cards, vec![basalt, island, crypt]);
        let root = RootSeed::from_u64(11);
        let left_sample = sample_hidden_world(&left, root, WorldId(4)).unwrap();
        let right_sample = sample_hidden_world(&right, root, WorldId(4)).unwrap();
        assert_eq!(left_sample.library.cards(), right_sample.library.cards());
    }

    #[test]
    fn sampler_uses_outer_hidden_world_rng_domain() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let state = base_state(&cards, vec![island]);
        let public = observe(&state).unwrap();
        let coordinate = hidden_world_coordinate(&public.library, WorldId(5));
        assert_eq!(coordinate.domain, RngDomain::OuterHiddenWorld);
        assert_eq!(coordinate.world, WorldId(5));
        assert_eq!(coordinate.event_type, HIDDEN_WORLD_EVENT_TYPE);
        assert_eq!(coordinate.logical_event, HIDDEN_WORLD_LOGICAL_EVENT);
        assert_eq!(coordinate.occurrence, EventOccurrence(0));
    }

    #[test]
    fn terminal_samples_aggregate_by_turn_and_family() {
        let cards = cards();
        let urza = cards.card_id_by_name("Urza, Lord High Artificer").expect("Urza");
        let basalt = cards.card_id_by_name("Basalt Monolith").expect("Basalt");
        let power = cards.card_id_by_name("Power Artifact").expect("Power Artifact");
        let state = TrueState {
            turn: 2,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            battlefield: BattlefieldZone::new(vec![
                PermanentState {
                    id: ObjectId(1),
                    card: urza,
                    face: CardFace::Front,
                    tapped: false,
                    summoning_sick: false,
                    counters: CounterState::default(),
                    mode: PermanentMode::Urza,
                    attachment: None,
                },
                PermanentState {
                    id: ObjectId(2),
                    card: basalt,
                    face: CardFace::Front,
                    tapped: false,
                    summoning_sick: false,
                    counters: CounterState::default(),
                    mode: PermanentMode::None,
                    attachment: None,
                },
                PermanentState {
                    id: ObjectId(3),
                    card: power,
                    face: CardFace::Front,
                    tapped: false,
                    summoning_sick: false,
                    counters: CounterState::default(),
                    mode: PermanentMode::None,
                    attachment: Some(AttachmentState { target: ObjectId(2) }),
                },
            ]),
            commander: CommanderZone::default(),
            ..TrueState::default()
        };
        let result = evaluate(
            &state,
            &cards,
            &DeterministicPolicy,
            MonteCarloConfig {
                root: RootSeed::from_u64(21),
                first_world: WorldId(0),
                samples: 4,
                rollout_max_steps: 8,
            },
        )
        .unwrap();
        assert_eq!(result.win_distribution.t1_through_t6, [0, 4, 0, 0, 0, 0]);
        assert_eq!(result.losses(), 0);
    }

    #[test]
    fn horizon_samples_are_losses() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let state = TrueState {
            turn: HORIZON_TURN,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(vec![island]),
            ..TrueState::default()
        };
        let result = evaluate(
            &state,
            &cards,
            &DeterministicPolicy,
            MonteCarloConfig {
                root: RootSeed::from_u64(22),
                first_world: WorldId(0),
                samples: 3,
                rollout_max_steps: 16,
            },
        )
        .unwrap();
        assert_eq!(result.losses(), 3);
    }

    #[test]
    fn evaluation_is_repeatable_and_world_order_independent() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let state = base_state(&cards, vec![island]);
        let root = RootSeed::from_u64(23);
        let left = evaluate_world_ids(
            &state,
            &cards,
            &DeterministicPolicy,
            root,
            32,
            &[WorldId(14), WorldId(2), WorldId(9), WorldId(5)],
        )
        .unwrap();
        let right = evaluate_world_ids(
            &state,
            &cards,
            &DeterministicPolicy,
            root,
            32,
            &[WorldId(5), WorldId(9), WorldId(2), WorldId(14)],
        )
        .unwrap();
        assert_eq!(left, right);
        assert_eq!(
            left.outcomes.iter().map(|outcome| outcome.world).collect::<Vec<_>>(),
            vec![WorldId(2), WorldId(5), WorldId(9), WorldId(14)]
        );
    }

    #[test]
    fn monte_carlo_ignores_template_hidden_order() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let crypt = cards.card_id_by_name("Tormod's Crypt").expect("Crypt");
        let basalt = cards.card_id_by_name("Basalt Monolith").expect("Basalt");
        let left = base_state(&cards, vec![island, crypt, basalt]);
        let right = base_state(&cards, vec![basalt, island, crypt]);
        let config = MonteCarloConfig {
            root: RootSeed::from_u64(24),
            first_world: WorldId(10),
            samples: 6,
            rollout_max_steps: 32,
        };
        assert_eq!(
            evaluate(&left, &cards, &DeterministicPolicy, config).unwrap(),
            evaluate(&right, &cards, &DeterministicPolicy, config).unwrap()
        );
    }

    #[test]
    fn incomplete_rollout_is_not_silently_recorded_as_a_loss() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let state = base_state(&cards, vec![island]);
        let error = evaluate(
            &state,
            &cards,
            &DeterministicPolicy,
            MonteCarloConfig {
                root: RootSeed::from_u64(25),
                first_world: WorldId(0),
                samples: 1,
                rollout_max_steps: 0,
            },
        )
        .unwrap_err();
        assert!(matches!(
            error,
            MonteCarloError::IncompleteWorld {
                stop: RolloutStop::StepLimit,
                ..
            }
        ));
    }

    #[test]
    fn duplicate_world_ids_are_rejected() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let state = base_state(&cards, vec![island]);
        let error = evaluate_world_ids(
            &state,
            &cards,
            &DeterministicPolicy,
            RootSeed::from_u64(26),
            32,
            &[WorldId(1), WorldId(1)],
        )
        .unwrap_err();
        assert!(matches!(error, MonteCarloError::DuplicateWorld(WorldId(1))));
    }
}
