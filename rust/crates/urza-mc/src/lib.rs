#![forbid(unsafe_code)]

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

    // The preexisting exact hidden order is not a Monte Carlo input.
    // Start from the canonical public multiset, then sample one exact order.
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

    let mut outcomes = Vec::with_capacity(worlds.len());
    let mut win_distribution = WinDistribution::default();
    let mut family_wins: Vec<_> = WinFamily::ALL
        .into_iter()
        .map(|family| FamilyWinCount { family, wins: 0 })
        .collect();

    for world in worlds {
        let sampled = sample_hidden_world(template, root, world)?;
        let result = rollout(
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
        let rollout_steps =
            u32::try_from(result.trace.len()).map_err(|_| MonteCarloError::TraceLengthOverflow)?;

        let outcome = match result.stop {
            RolloutStop::Terminal(family) => {
                let turn = result.final_information.turn;
                if !(1..=HORIZON_TURN).contains(&turn) {
                    return Err(MonteCarloError::TerminalOutsideHorizon { world, turn });
                }
                let bucket = usize::from(turn - 1);
                win_distribution.t1_through_t6[bucket] = win_distribution.t1_through_t6[bucket]
                    .checked_add(1)
                    .ok_or(MonteCarloError::CounterOverflow)?;
                let entry = family_wins
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
                win_distribution.losses = win_distribution
                    .losses
                    .checked_add(1)
                    .ok_or(MonteCarloError::CounterOverflow)?;
                SampleOutcome::LossByHorizon
            }
            stop @ (RolloutStop::StepLimit | RolloutStop::NoCandidate) => {
                return Err(MonteCarloError::IncompleteWorld { world, stop });
            }
        };

        outcomes.push(WorldOutcome {
            world,
            outcome,
            rollout_steps,
        });
    }

    Ok(MonteCarloResult {
        outcomes,
        win_distribution,
        family_wins,
    })
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

    hasher.update(&(library.known_top.len() as u32).to_le_bytes());
    for card in &library.known_top {
        hasher.update(&card.0.to_le_bytes());
    }

    hasher.update(&(library.remaining_counts.len() as u32).to_le_bytes());
    for count in &library.remaining_counts {
        hasher.update(&count.card.0.to_le_bytes());
        hasher.update(&[count.count]);
    }

    hasher.update(&(library.known_bottom.len() as u32).to_le_bytes());
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
        BattlefieldZone, CardFace, CommanderZone, CounterState, LibraryKnowledge, ObjectId,
        PermanentMode, PermanentState, Phase, Window,
    };

    fn cards() -> R4CardDatabase {
        R4CardDatabase::load().expect("R4 database")
    }

    fn base_state(
        cards: &R4CardDatabase,
        turn: u8,
        library_cards: Vec<urza_core::CardDefId>,
    ) -> TrueState {
        let library = if library_cards.is_empty() {
            vec![cards.card_id_by_name("Island").expect("Island")]
        } else {
            library_cards
        };
        TrueState {
            turn,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(library),
            ..TrueState::default()
        }
    }

    fn permanent(object: u32, card: urza_core::CardDefId) -> PermanentState {
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

    fn config(samples: u32, max_steps: u32) -> MonteCarloConfig {
        MonteCarloConfig {
            root: RootSeed::from_u64(0x4d43_5f52_355f_0001),
            first_world: WorldId(10),
            samples,
            rollout_max_steps: max_steps,
        }
    }

    #[test]
    fn sampled_world_preserves_public_information_and_known_edges() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let crypt = cards
            .card_id_by_name("Tormod's Crypt")
            .expect("Tormod's Crypt");
        let basalt = cards.card_id_by_name("Basalt Monolith").expect("Basalt");
        let power = cards
            .card_id_by_name("Power Artifact")
            .expect("Power Artifact");
        let top = cards
            .card_id_by_name("Sensei's Divining Top")
            .expect("Top");
        let gadgeteer = cards
            .card_id_by_name("Forensic Gadgeteer")
            .expect("Gadgeteer");
        let mut state = base_state(
            &cards,
            2,
            vec![island, basalt, power, top, gadgeteer, crypt],
        );
        state
            .library
            .set_knowledge(LibraryKnowledge {
                known_top: 1,
                known_bottom: 1,
            })
            .unwrap();

        let sampled = sample_hidden_world(&state, RootSeed::from_u64(91), WorldId(4)).unwrap();
        assert_eq!(observe(&sampled).unwrap(), observe(&state).unwrap());
        assert_eq!(sampled.library.known_top(), &[island]);
        assert_eq!(sampled.library.known_bottom(), &[crypt]);
        assert_eq!(sampled.library.knowledge(), state.library.knowledge());
    }

    #[test]
    fn preexisting_hidden_order_is_not_a_sampling_input() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let basalt = cards.card_id_by_name("Basalt Monolith").expect("Basalt");
        let power = cards
            .card_id_by_name("Power Artifact")
            .expect("Power Artifact");
        let top = cards
            .card_id_by_name("Sensei's Divining Top")
            .expect("Top");
        let crypt = cards
            .card_id_by_name("Tormod's Crypt")
            .expect("Tormod's Crypt");
        let left = base_state(&cards, 3, vec![island, basalt, power, top, crypt]);
        let right = base_state(&cards, 3, vec![crypt, top, power, basalt, island]);
        assert_eq!(observe(&left).unwrap(), observe(&right).unwrap());

        let root = RootSeed::from_u64(12345);
        let world = WorldId(88);
        let sampled_left = sample_hidden_world(&left, root, world).unwrap();
        let sampled_right = sample_hidden_world(&right, root, world).unwrap();
        assert_eq!(sampled_left.library.cards(), sampled_right.library.cards());
    }

    #[test]
    fn sampler_uses_outer_hidden_world_rng_domain() {
        let cards = cards();
        let state = base_state(&cards, 2, Vec::new());
        let info = observe(&state).unwrap();
        let coordinate = hidden_world_coordinate(&info.library, WorldId(7));
        assert_eq!(coordinate.domain, RngDomain::OuterHiddenWorld);
        assert_eq!(coordinate.event_type, HIDDEN_WORLD_EVENT_TYPE);
    }

    #[test]
    fn terminal_samples_aggregate_by_turn_and_family() {
        let cards = cards();
        let urza = cards
            .card_id_by_name("Urza, Lord High Artificer")
            .expect("Urza");
        let basalt = cards.card_id_by_name("Basalt Monolith").expect("Basalt");
        let power = cards
            .card_id_by_name("Power Artifact")
            .expect("Power Artifact");
        let mut state = base_state(&cards, 2, Vec::new());
        state.commander.zone = CommanderZone::Battlefield;
        let mut aura = permanent(30, power);
        aura.attached_to = Some(ObjectId(20));
        state.battlefield = BattlefieldZone::new(vec![
            permanent(10, urza),
            permanent(20, basalt),
            aura,
        ]);

        let result = evaluate(&state, &cards, &DeterministicPolicy, config(4, 32)).unwrap();
        assert_eq!(result.samples(), 4);
        assert_eq!(result.win_distribution.t1_through_t6, [0, 4, 0, 0, 0, 0]);
        assert_eq!(result.win_distribution.losses, 0);
        assert_eq!(result.wins(), 4);
        assert_eq!(
            result
                .family_wins
                .iter()
                .find(|entry| entry.family == WinFamily::PowerArtifactBasalt)
                .unwrap()
                .wins,
            4
        );
    }

    #[test]
    fn horizon_samples_are_losses() {
        let cards = cards();
        let state = base_state(&cards, HORIZON_TURN, Vec::new());
        let result = evaluate(&state, &cards, &DeterministicPolicy, config(3, 16)).unwrap();
        assert_eq!(result.wins(), 0);
        assert_eq!(result.losses(), 3);
        assert!(
            result
                .outcomes
                .iter()
                .all(|outcome| outcome.outcome == SampleOutcome::LossByHorizon)
        );
    }

    #[test]
    fn evaluation_is_repeatable_and_world_order_independent() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let basalt = cards.card_id_by_name("Basalt Monolith").expect("Basalt");
        let power = cards
            .card_id_by_name("Power Artifact")
            .expect("Power Artifact");
        let crypt = cards
            .card_id_by_name("Tormod's Crypt")
            .expect("Tormod's Crypt");
        let state = base_state(
            &cards,
            HORIZON_TURN,
            vec![island, basalt, power, crypt],
        );
        let root = RootSeed::from_u64(777);
        let worlds = [WorldId(9), WorldId(2), WorldId(14), WorldId(5)];
        let reversed = [WorldId(5), WorldId(14), WorldId(2), WorldId(9)];

        let first = evaluate_world_ids(
            &state,
            &cards,
            &DeterministicPolicy,
            root,
            16,
            &worlds,
        )
        .unwrap();
        let second = evaluate_world_ids(
            &state,
            &cards,
            &DeterministicPolicy,
            root,
            16,
            &worlds,
        )
        .unwrap();
        let reordered = evaluate_world_ids(
            &state,
            &cards,
            &DeterministicPolicy,
            root,
            16,
            &reversed,
        )
        .unwrap();
        assert_eq!(first, second);
        assert_eq!(first, reordered);
        assert_eq!(
            first
                .outcomes
                .iter()
                .map(|outcome| outcome.world.0)
                .collect::<Vec<_>>(),
            vec![2, 5, 9, 14]
        );
    }

    #[test]
    fn monte_carlo_ignores_template_hidden_order() {
        let cards = cards();
        let island = cards.card_id_by_name("Island").expect("Island");
        let basalt = cards.card_id_by_name("Basalt Monolith").expect("Basalt");
        let power = cards
            .card_id_by_name("Power Artifact")
            .expect("Power Artifact");
        let crypt = cards
            .card_id_by_name("Tormod's Crypt")
            .expect("Tormod's Crypt");
        let left = base_state(
            &cards,
            HORIZON_TURN,
            vec![island, basalt, power, crypt],
        );
        let right = base_state(
            &cards,
            HORIZON_TURN,
            vec![crypt, power, basalt, island],
        );
        assert_eq!(observe(&left).unwrap(), observe(&right).unwrap());

        let cfg = config(6, 16);
        let left_result = evaluate(&left, &cards, &DeterministicPolicy, cfg).unwrap();
        let right_result = evaluate(&right, &cards, &DeterministicPolicy, cfg).unwrap();
        assert_eq!(left_result, right_result);
    }

    #[test]
    fn incomplete_rollout_is_not_silently_recorded_as_a_loss() {
        let cards = cards();
        let state = base_state(&cards, HORIZON_TURN, Vec::new());
        let error = evaluate(&state, &cards, &DeterministicPolicy, config(1, 0)).unwrap_err();
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
        let state = base_state(&cards, HORIZON_TURN, Vec::new());
        let error = evaluate_world_ids(
            &state,
            &cards,
            &DeterministicPolicy,
            RootSeed::from_u64(1),
            16,
            &[WorldId(3), WorldId(3)],
        )
        .unwrap_err();
        assert!(matches!(
            error,
            MonteCarloError::DuplicateWorld(WorldId(3))
        ));
    }
}
