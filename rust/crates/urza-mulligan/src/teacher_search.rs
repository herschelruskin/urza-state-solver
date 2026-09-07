use std::cmp::Ordering;
use std::collections::BTreeMap;
use std::fmt;

use urza_core::{PendingDecision, Phase, TrueState, Window};
use urza_info::{InformationState, ObservationError, observe};
use urza_mc::{MonteCarloError, sample_hidden_world};
use urza_policy::{DeterministicPolicy, PolicyActionClass, PolicyPublicKey};
use urza_policy_bridge::{BridgeError, CandidateBridge};
use urza_rng::{LogicalEventId, RootSeed, WorldId};
use urza_rollout::{RolloutConfig, RolloutError, RolloutStop, rollout_with_logical_event_offset};
use urza_rules::{
    CardDatabase, GameRngContext, HORIZON_TURN, RuleError, advance_automatic,
    apply_action_with_rng, detect_terminal_win,
};
use urza_value::{WinByHorizonScore, WinDistribution};

pub const R7_TEACHER_SEARCH_VERSION: &str = "r7_public_belief_bounded_search_v3";
pub const R7_TEACHER_POLICY_VERSION: &str = "r7_teacher_public_belief_v3";
pub const R7_TEACHER_SEARCH_BOUNDARY: &str = "R7 teacher search samples exact hidden worlds only to estimate public action values; every \
     teacher action is selected once per shared InformationState and is then applied uniformly to \
     every sampled world with that observation. Hidden-world identity, exact unknown library order, \
     interpretation roles, archetype features, and R7 grouping labels never participate in action \
     identity. Search depth, total teacher steps, and retained candidates are explicitly bounded; \
     leaves fall back to the frozen R5 deterministic public policy. When the stack is nonempty, \
     retained PassPriority candidates are evaluated before other teacher candidates so stack \
     resolution is tested first. Candidate siblings are skipped only after a complete branch reaches \
     the exact public-state ceiling of every sampled world winning on the current turn, which no \
     sibling can improve. An incomplete leaf is never scored as a loss: an unresolved candidate \
     subtree is excluded only when another candidate at the same public decision has a complete \
     finite value, while an all-incomplete decision fails explicitly. R5 and R6 behavior is unchanged.";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TeacherSearchConfig {
    pub root: RootSeed,
    pub first_world: WorldId,
    pub samples: u32,
    /// Maximum number of genuinely branching public choices explored on one
    /// teacher path. Single-candidate public states do not consume this budget.
    pub max_choice_depth: u8,
    /// Absolute teacher-action cap on one path, including forced public steps.
    /// This prevents long forced/cyclic trajectories from escaping the bound.
    pub max_teacher_steps: u16,
    /// Maximum retained semantic candidates at any one public decision group.
    /// Candidate classes are retained in deterministic round-robin strata and
    /// individual members are evenly spaced over semantic-key order.
    pub max_candidates_per_group: usize,
    /// Frozen R5 deterministic rollout budget used only after the teacher
    /// search reaches one of its explicit depth/step boundaries.
    pub leaf_rollout_max_steps: u32,
}

impl Default for TeacherSearchConfig {
    fn default() -> Self {
        Self {
            root: RootSeed::from_u64(0x5237_5445_4143_4801),
            first_world: WorldId(0),
            samples: 8,
            max_choice_depth: 4,
            max_teacher_steps: 16,
            max_candidates_per_group: 12,
            leaf_rollout_max_steps: urza_rollout::DEFAULT_MAX_STEPS,
        }
    }
}

impl TeacherSearchConfig {
    fn validate(self) -> Result<(), TeacherSearchError> {
        if self.samples == 0 {
            return Err(TeacherSearchError::InvalidConfig(
                "samples must be at least one",
            ));
        }
        if self.max_teacher_steps == 0 {
            return Err(TeacherSearchError::InvalidConfig(
                "max_teacher_steps must be at least one",
            ));
        }
        if self.max_candidates_per_group < ORDINARY_PUBLIC_CLASS_COUNT {
            return Err(TeacherSearchError::InvalidConfig(
                "max_candidates_per_group must be at least five so every ordinary public action class can retain a representative",
            ));
        }
        if self.leaf_rollout_max_steps == 0 {
            return Err(TeacherSearchError::InvalidConfig(
                "leaf_rollout_max_steps must be at least one",
            ));
        }
        Ok(())
    }
}

const ORDINARY_PUBLIC_CLASS_COUNT: usize = 5;

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct TeacherPublicAction {
    pub class: PolicyActionClass,
    pub key: PolicyPublicKey,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct TeacherSearchStats {
    pub sampled_worlds: u32,
    pub public_groups_evaluated: u64,
    pub public_actions_evaluated: u64,
    pub forced_public_steps: u64,
    pub truncated_public_groups: u64,
    pub incomplete_candidate_branches: u64,
    pub ceiling_pruned_public_actions: u64,
    pub leaf_rollouts: u64,
    pub observation_splits: u64,
    pub max_full_candidate_count: u32,
    pub max_retained_candidate_count: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TeacherSearchResult {
    pub search_version: &'static str,
    pub policy_version: &'static str,
    pub boundary: &'static str,
    pub win_distribution: WinDistribution,
    pub score: WinByHorizonScore,
    pub stats: TeacherSearchStats,
}

#[derive(Debug)]
pub enum TeacherSearchError {
    InvalidConfig(&'static str),
    WorldIdOverflow,
    LogicalEventOverflow,
    CounterOverflow(&'static str),
    CandidateSetDrift(WorldId),
    MissingPublicAction(WorldId),
    TerminalOutsideHorizon { world: WorldId, turn: u8 },
    IncompleteLeaf { world: WorldId, stop: RolloutStop },
    AllCandidateBranchesIncomplete { candidate_count: usize },
    MonteCarlo(MonteCarloError),
    Observation(ObservationError),
    Bridge(BridgeError),
    Rules(RuleError),
    Rollout(RolloutError),
}

impl fmt::Display for TeacherSearchError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidConfig(message) => {
                write!(formatter, "invalid R7 teacher config: {message}")
            }
            Self::WorldIdOverflow => {
                write!(formatter, "R7 teacher sampled-world range overflowed u64")
            }
            Self::LogicalEventOverflow => {
                write!(
                    formatter,
                    "R7 teacher logical-event coordinate overflowed u64"
                )
            }
            Self::CounterOverflow(context) => {
                write!(
                    formatter,
                    "R7 teacher aggregate counter overflow: {context}"
                )
            }
            Self::CandidateSetDrift(world) => write!(
                formatter,
                "sampled world {world:?} exposed a different public candidate set inside one InformationState group"
            ),
            Self::MissingPublicAction(world) => write!(
                formatter,
                "sampled world {world:?} could not remap the selected public teacher action"
            ),
            Self::TerminalOutsideHorizon { world, turn } => write!(
                formatter,
                "sampled world {world:?} reached a teacher terminal on out-of-horizon turn {turn}"
            ),
            Self::IncompleteLeaf { world, stop } => write!(
                formatter,
                "sampled world {world:?} reached incomplete frozen-R5 leaf stop {stop:?}"
            ),
            Self::AllCandidateBranchesIncomplete { candidate_count } => write!(
                formatter,
                "all {candidate_count} retained R7 teacher candidates were incomplete at one public decision"
            ),
            Self::MonteCarlo(error) => write!(
                formatter,
                "R7 teacher hidden-world sampling failed: {error}"
            ),
            Self::Observation(error) => write!(formatter, "R7 teacher observation failed: {error}"),
            Self::Bridge(error) => write!(formatter, "R7 teacher candidate bridge failed: {error}"),
            Self::Rules(error) => write!(formatter, "R7 teacher rules execution failed: {error}"),
            Self::Rollout(error) => write!(formatter, "R7 teacher leaf rollout failed: {error}"),
        }
    }
}

impl std::error::Error for TeacherSearchError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::MonteCarlo(error) => Some(error),
            Self::Observation(error) => Some(error),
            Self::Bridge(error) => Some(error),
            Self::Rules(error) => Some(error),
            Self::Rollout(error) => Some(error),
            _ => None,
        }
    }
}

impl From<MonteCarloError> for TeacherSearchError {
    fn from(value: MonteCarloError) -> Self {
        Self::MonteCarlo(value)
    }
}

impl From<ObservationError> for TeacherSearchError {
    fn from(value: ObservationError) -> Self {
        Self::Observation(value)
    }
}

impl From<BridgeError> for TeacherSearchError {
    fn from(value: BridgeError) -> Self {
        Self::Bridge(value)
    }
}

impl From<RuleError> for TeacherSearchError {
    fn from(value: RuleError) -> Self {
        Self::Rules(value)
    }
}

impl From<RolloutError> for TeacherSearchError {
    fn from(value: RolloutError) -> Self {
        Self::Rollout(value)
    }
}

#[derive(Debug, Clone)]
struct TeacherWorld {
    world: WorldId,
    state: TrueState,
    logical_event: u64,
}

#[derive(Debug)]
struct PublicWorldGroup {
    information: InformationState,
    worlds: Vec<TeacherWorld>,
}

enum PreparedWorld {
    Active(Box<InformationState>),
    Terminal(u8),
    Horizon,
}

/// Evaluate one public state with a small, explicitly bounded R7 strategic
/// teacher. The result is still a finite sampled WinByHorizon value; the only
/// policy change from R5 is the bounded public-belief action search before the
/// frozen deterministic R5 leaf continuation.
pub fn evaluate_teacher<D: CardDatabase>(
    template: &TrueState,
    cards: &D,
    config: TeacherSearchConfig,
) -> Result<TeacherSearchResult, TeacherSearchError> {
    config.validate()?;

    let mut worlds = Vec::with_capacity(config.samples as usize);
    for offset in 0..config.samples {
        let world = config
            .first_world
            .0
            .checked_add(u64::from(offset))
            .map(WorldId)
            .ok_or(TeacherSearchError::WorldIdOverflow)?;
        worlds.push(TeacherWorld {
            world,
            state: sample_hidden_world(template, config.root, world)?,
            logical_event: 0,
        });
    }

    let mut evaluator = TeacherEvaluator {
        cards,
        config,
        baseline_policy: DeterministicPolicy,
        stats: TeacherSearchStats {
            sampled_worlds: config.samples,
            ..TeacherSearchStats::default()
        },
    };
    let win_distribution =
        evaluator.evaluate_partition(worlds, config.max_choice_depth, config.max_teacher_steps)?;
    let score = WinByHorizonScore::from(&win_distribution);

    Ok(TeacherSearchResult {
        search_version: R7_TEACHER_SEARCH_VERSION,
        policy_version: R7_TEACHER_POLICY_VERSION,
        boundary: R7_TEACHER_SEARCH_BOUNDARY,
        win_distribution,
        score,
        stats: evaluator.stats,
    })
}

struct TeacherEvaluator<'a, D> {
    cards: &'a D,
    config: TeacherSearchConfig,
    baseline_policy: DeterministicPolicy,
    stats: TeacherSearchStats,
}

impl<D: CardDatabase> TeacherEvaluator<'_, D> {
    fn evaluate_partition(
        &mut self,
        worlds: Vec<TeacherWorld>,
        choices_left: u8,
        steps_left: u16,
    ) -> Result<WinDistribution, TeacherSearchError> {
        let mut aggregate = WinDistribution::default();
        let mut groups: Vec<PublicWorldGroup> = Vec::new();

        for mut world in worlds {
            match self.prepare_world(&mut world)? {
                PreparedWorld::Terminal(turn) => {
                    record_win(&mut aggregate, world.world, turn)?;
                }
                PreparedWorld::Horizon => record_loss(&mut aggregate)?,
                PreparedWorld::Active(information) => {
                    if let Some(group) = groups
                        .iter_mut()
                        .find(|group| group.information == *information)
                    {
                        group.worlds.push(world);
                    } else {
                        groups.push(PublicWorldGroup {
                            information: *information,
                            worlds: vec![world],
                        });
                    }
                }
            }
        }

        if groups.len() > 1 {
            self.stats.observation_splits = self
                .stats
                .observation_splits
                .saturating_add((groups.len() - 1) as u64);
        }

        for group in groups {
            let value = self.evaluate_group(group, choices_left, steps_left)?;
            add_distribution(&mut aggregate, &value)?;
        }
        Ok(aggregate)
    }

    fn prepare_world(&self, world: &mut TeacherWorld) -> Result<PreparedWorld, TeacherSearchError> {
        let information = observe(&world.state)?;
        if detect_terminal_win(&information, self.cards).is_some() {
            return Ok(PreparedWorld::Terminal(information.turn));
        }

        if needs_automatic_advance(&world.state) {
            match advance_automatic(&mut world.state, self.cards) {
                Ok(_) => {}
                Err(RuleError::HorizonReached) => return Ok(PreparedWorld::Horizon),
                Err(error) => return Err(error.into()),
            }

            let information = observe(&world.state)?;
            if detect_terminal_win(&information, self.cards).is_some() {
                return Ok(PreparedWorld::Terminal(information.turn));
            }
            return Ok(PreparedWorld::Active(Box::new(information)));
        }

        Ok(PreparedWorld::Active(Box::new(information)))
    }

    fn evaluate_group(
        &mut self,
        group: PublicWorldGroup,
        choices_left: u8,
        steps_left: u16,
    ) -> Result<WinDistribution, TeacherSearchError> {
        self.stats.public_groups_evaluated = self.stats.public_groups_evaluated.saturating_add(1);

        if steps_left == 0 {
            return self.evaluate_leaf(group.worlds);
        }

        let full_candidates = self.shared_public_candidates(&group)?;
        self.stats.max_full_candidate_count = self
            .stats
            .max_full_candidate_count
            .max(saturating_u32(full_candidates.len()));

        if full_candidates.is_empty() {
            return self.evaluate_leaf(group.worlds);
        }

        if full_candidates.len() == 1 {
            self.stats.forced_public_steps = self.stats.forced_public_steps.saturating_add(1);
            self.stats.public_actions_evaluated =
                self.stats.public_actions_evaluated.saturating_add(1);
            let children = self.apply_public_action(group.worlds, &full_candidates[0])?;
            return self.evaluate_partition(children, choices_left, steps_left - 1);
        }

        if choices_left == 0 {
            return self.evaluate_leaf(group.worlds);
        }

        let mut candidates =
            retain_bounded_candidates(&full_candidates, self.config.max_candidates_per_group);
        if candidates.len() < full_candidates.len() {
            self.stats.truncated_public_groups =
                self.stats.truncated_public_groups.saturating_add(1);
        }
        self.stats.max_retained_candidate_count = self
            .stats
            .max_retained_candidate_count
            .max(saturating_u32(candidates.len()));

        order_teacher_candidates(&mut candidates, !group.information.stack.is_empty());
        let candidate_count = candidates.len();
        let current_turn = group.information.turn;
        let world_count = saturating_u32(group.worlds.len());
        let mut best: Option<(TeacherPublicAction, WinDistribution, WinByHorizonScore)> = None;
        for (index, candidate) in candidates.into_iter().enumerate() {
            self.stats.public_actions_evaluated =
                self.stats.public_actions_evaluated.saturating_add(1);
            let children = self.apply_public_action(group.worlds.clone(), &candidate)?;
            let value = match self.evaluate_partition(children, choices_left - 1, steps_left - 1) {
                Ok(value) => value,
                Err(error) if is_incomplete_subtree(&error) => {
                    self.stats.incomplete_candidate_branches =
                        self.stats.incomplete_candidate_branches.saturating_add(1);
                    continue;
                }
                Err(error) => return Err(error),
            };
            let score = WinByHorizonScore::from(&value);

            let replace = match &best {
                None => true,
                Some((best_action, _, best_score)) => match score.cmp(best_score) {
                    Ordering::Greater => true,
                    Ordering::Less => false,
                    Ordering::Equal => candidate < *best_action,
                },
            };
            if replace {
                best = Some((candidate, value.clone(), score));
            }

            if is_current_turn_ceiling(&value, current_turn, world_count) {
                let pruned = candidate_count.saturating_sub(index + 1);
                self.stats.ceiling_pruned_public_actions = self
                    .stats
                    .ceiling_pruned_public_actions
                    .saturating_add(u64::try_from(pruned).unwrap_or(u64::MAX));
                return Ok(value);
            }
        }

        match best {
            Some((_, value, _)) => Ok(value),
            None => Err(TeacherSearchError::AllCandidateBranchesIncomplete { candidate_count }),
        }
    }

    fn shared_public_candidates(
        &self,
        group: &PublicWorldGroup,
    ) -> Result<Vec<TeacherPublicAction>, TeacherSearchError> {
        let representative = public_candidates(&group.worlds[0].state, self.cards)?;
        for world in group.worlds.iter().skip(1) {
            let candidate_set = public_candidates(&world.state, self.cards)?;
            if candidate_set != representative {
                return Err(TeacherSearchError::CandidateSetDrift(world.world));
            }
        }
        Ok(representative)
    }

    fn apply_public_action(
        &self,
        mut worlds: Vec<TeacherWorld>,
        selected: &TeacherPublicAction,
    ) -> Result<Vec<TeacherWorld>, TeacherSearchError> {
        for world in &mut worlds {
            let bridge = CandidateBridge::build(&world.state, self.cards)?;
            let candidate = bridge
                .candidates()
                .iter()
                .find(|candidate| {
                    candidate.class == selected.class && candidate.key == selected.key
                })
                .ok_or(TeacherSearchError::MissingPublicAction(world.world))?;
            let action = bridge
                .resolved_action(candidate.token)
                .ok_or(TeacherSearchError::MissingPublicAction(world.world))?;
            apply_action_with_rng(
                &mut world.state,
                self.cards,
                action,
                GameRngContext {
                    root: self.config.root,
                    world: world.world,
                    logical_event: LogicalEventId(world.logical_event),
                },
            )?;
            world.logical_event = world
                .logical_event
                .checked_add(1)
                .ok_or(TeacherSearchError::LogicalEventOverflow)?;
        }
        Ok(worlds)
    }

    fn evaluate_leaf(
        &mut self,
        worlds: Vec<TeacherWorld>,
    ) -> Result<WinDistribution, TeacherSearchError> {
        let mut aggregate = WinDistribution::default();
        for world in worlds {
            self.stats.leaf_rollouts = self.stats.leaf_rollouts.saturating_add(1);
            let result = rollout_with_logical_event_offset(
                world.state,
                self.cards,
                &self.baseline_policy,
                RolloutConfig {
                    root: self.config.root,
                    world: world.world,
                    max_steps: self.config.leaf_rollout_max_steps,
                },
                world.logical_event,
            )?;
            match result.stop {
                RolloutStop::Terminal(_) => {
                    record_win(&mut aggregate, world.world, result.final_information.turn)?;
                }
                RolloutStop::Horizon => record_loss(&mut aggregate)?,
                stop @ (RolloutStop::StepLimit | RolloutStop::NoCandidate) => {
                    return Err(TeacherSearchError::IncompleteLeaf {
                        world: world.world,
                        stop,
                    });
                }
            }
        }
        Ok(aggregate)
    }
}

fn is_incomplete_subtree(error: &TeacherSearchError) -> bool {
    matches!(
        error,
        TeacherSearchError::IncompleteLeaf { .. }
            | TeacherSearchError::AllCandidateBranchesIncomplete { .. }
    )
}

fn public_candidates<D: CardDatabase>(
    state: &TrueState,
    cards: &D,
) -> Result<Vec<TeacherPublicAction>, TeacherSearchError> {
    let bridge = CandidateBridge::build(state, cards)?;
    Ok(bridge
        .candidates()
        .iter()
        .map(|candidate| TeacherPublicAction {
            class: candidate.class,
            key: candidate.key.clone(),
        })
        .collect())
}

fn order_teacher_candidates(candidates: &mut [TeacherPublicAction], stack_nonempty: bool) {
    if !stack_nonempty {
        candidates.sort_unstable();
        return;
    }

    candidates.sort_unstable_by(|left, right| {
        resolution_priority(left)
            .cmp(&resolution_priority(right))
            .then_with(|| left.cmp(right))
    });
}

fn resolution_priority(candidate: &TeacherPublicAction) -> u8 {
    if candidate.class == PolicyActionClass::PassPriority {
        0
    } else {
        1
    }
}

fn is_current_turn_ceiling(
    distribution: &WinDistribution,
    current_turn: u8,
    world_count: u32,
) -> bool {
    if !(1..=HORIZON_TURN).contains(&current_turn) {
        return false;
    }
    let bucket = usize::from(current_turn - 1);
    distribution.losses == 0
        && distribution.wins() == world_count
        && distribution.t1_through_t6[bucket] == world_count
}

fn retain_bounded_candidates(
    candidates: &[TeacherPublicAction],
    cap: usize,
) -> Vec<TeacherPublicAction> {
    if candidates.len() <= cap {
        return candidates.to_vec();
    }

    let mut buckets: BTreeMap<PolicyActionClass, Vec<TeacherPublicAction>> = BTreeMap::new();
    for candidate in candidates {
        buckets
            .entry(candidate.class)
            .or_default()
            .push(candidate.clone());
    }

    let classes: Vec<_> = buckets.keys().copied().collect();
    if classes.len() > cap {
        // Current bridge invariants and validated config make this unreachable,
        // but keep the helper total if future policy classes are added.
        return evenly_spaced(candidates, cap);
    }

    let mut quotas: BTreeMap<PolicyActionClass, usize> =
        classes.iter().copied().map(|class| (class, 1)).collect();
    let mut remaining = cap - classes.len();
    while remaining > 0 {
        let mut progressed = false;
        for class in &classes {
            let current = quotas[class];
            let available = buckets[class].len();
            if current < available {
                quotas.insert(*class, current + 1);
                remaining -= 1;
                progressed = true;
                if remaining == 0 {
                    break;
                }
            }
        }
        if !progressed {
            break;
        }
    }

    let mut retained = Vec::new();
    for class in classes {
        retained.extend(evenly_spaced(&buckets[&class], quotas[&class]));
    }
    retained.sort_unstable();
    retained
}

fn evenly_spaced<T: Clone>(items: &[T], count: usize) -> Vec<T> {
    debug_assert!(count > 0);
    debug_assert!(count <= items.len());
    if count == items.len() {
        return items.to_vec();
    }
    if count == 1 {
        return vec![items[items.len() / 2].clone()];
    }

    let last = items.len() - 1;
    (0..count)
        .map(|index| items[index * last / (count - 1)].clone())
        .collect()
}

fn needs_automatic_advance(state: &TrueState) -> bool {
    state.stack.is_empty()
        && matches!(state.pending, PendingDecision::None)
        && matches!(
            (state.phase, state.window),
            (Phase::OpponentCycle, Window::None) | (Phase::Untap, Window::None)
        )
}

fn record_win(
    distribution: &mut WinDistribution,
    world: WorldId,
    turn: u8,
) -> Result<(), TeacherSearchError> {
    if !(1..=HORIZON_TURN).contains(&turn) {
        return Err(TeacherSearchError::TerminalOutsideHorizon { world, turn });
    }
    let bucket = usize::from(turn - 1);
    distribution.t1_through_t6[bucket] = distribution.t1_through_t6[bucket]
        .checked_add(1)
        .ok_or(TeacherSearchError::CounterOverflow("exact-turn wins"))?;
    Ok(())
}

fn record_loss(distribution: &mut WinDistribution) -> Result<(), TeacherSearchError> {
    distribution.losses = distribution
        .losses
        .checked_add(1)
        .ok_or(TeacherSearchError::CounterOverflow("losses"))?;
    Ok(())
}

fn add_distribution(
    target: &mut WinDistribution,
    source: &WinDistribution,
) -> Result<(), TeacherSearchError> {
    for (target_turn, source_turn) in target.t1_through_t6.iter_mut().zip(source.t1_through_t6) {
        *target_turn =
            target_turn
                .checked_add(source_turn)
                .ok_or(TeacherSearchError::CounterOverflow(
                    "aggregated exact-turn wins",
                ))?;
    }
    target.losses = target
        .losses
        .checked_add(source.losses)
        .ok_or(TeacherSearchError::CounterOverflow("aggregated losses"))?;
    Ok(())
}

fn saturating_u32(value: usize) -> u32 {
    u32::try_from(value).unwrap_or(u32::MAX)
}

#[cfg(test)]
mod tests {
    use super::*;
    use urza_cards::R4CardDatabase;
    use urza_core::{
        BattlefieldZone, CardDefId, CardFace, CardZone, CommanderState, CommanderZone,
        CounterState, ManaPool, ObjectId, PermanentMode, PermanentState, TrueLibrary,
    };

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

    fn power_artifact_basalt_state(
        cards: &R4CardDatabase,
        library_cards: Vec<CardDefId>,
    ) -> TrueState {
        let urza = cards.card_id_by_name("Urza, Lord High Artificer").unwrap();
        let basalt = cards.card_id_by_name("Basalt Monolith").unwrap();
        let power = cards.card_id_by_name("Power Artifact").unwrap();

        TrueState {
            turn: 2,
            phase: Phase::PrecombatMain,
            window: Window::Priority,
            library: TrueLibrary::unknown(library_cards),
            hand: CardZone::new(vec![power]),
            battlefield: BattlefieldZone::new(vec![permanent(1, urza), permanent(2, basalt)]),
            mana: ManaPool {
                blue: 2,
                ..ManaPool::default()
            },
            commander: CommanderState {
                zone: CommanderZone::Battlefield,
                command_zone_casts: 1,
            },
            ..TrueState::default()
        }
    }

    #[test]
    fn bounded_teacher_recovers_real_power_artifact_basalt_witness() {
        let cards = R4CardDatabase::load().expect("R4 database");
        let island = cards.card_id_by_name("Island").unwrap();
        let state = power_artifact_basalt_state(&cards, vec![island]);

        let result = evaluate_teacher(
            &state,
            &cards,
            TeacherSearchConfig {
                root: RootSeed::from_u64(0x5237_5749_544e_4553),
                first_world: WorldId(700),
                samples: 1,
                max_choice_depth: 2,
                max_teacher_steps: 4,
                max_candidates_per_group: 12,
                leaf_rollout_max_steps: 128,
            },
        )
        .expect("bounded teacher witness");

        assert_eq!(result.search_version, R7_TEACHER_SEARCH_VERSION);
        assert_eq!(result.policy_version, R7_TEACHER_POLICY_VERSION);
        assert_eq!(result.win_distribution.t1_through_t6[1], 1);
        assert_eq!(result.win_distribution.losses, 0);
        assert_eq!(result.score.total_wins, 1);
        assert!(result.stats.public_actions_evaluated >= 2);
        assert!(result.stats.ceiling_pruned_public_actions > 0);
    }

    #[test]
    fn teacher_sampling_is_invariant_to_preexisting_unknown_library_order() {
        let cards = R4CardDatabase::load().expect("R4 database");
        let island = cards.card_id_by_name("Island").unwrap();
        let sol_ring = cards.card_id_by_name("Sol Ring").unwrap();
        let mana_vault = cards.card_id_by_name("Mana Vault").unwrap();

        let left = power_artifact_basalt_state(&cards, vec![island, sol_ring, mana_vault]);
        let right = power_artifact_basalt_state(&cards, vec![mana_vault, island, sol_ring]);
        let config = TeacherSearchConfig {
            root: RootSeed::from_u64(0x5237_494e_5641_5201),
            first_world: WorldId(900),
            samples: 2,
            max_choice_depth: 2,
            max_teacher_steps: 4,
            max_candidates_per_group: 12,
            leaf_rollout_max_steps: 128,
        };

        let left_result = evaluate_teacher(&left, &cards, config).unwrap();
        let right_result = evaluate_teacher(&right, &cards, config).unwrap();
        assert_eq!(left_result.win_distribution, right_result.win_distribution);
        assert_eq!(left_result.score, right_result.score);
        assert_eq!(left_result.stats, right_result.stats);
    }

    #[test]
    fn candidate_cap_is_class_stratified_and_semantically_deterministic() {
        let candidate = |class, kind| TeacherPublicAction {
            class,
            key: PolicyPublicKey {
                kind,
                ..PolicyPublicKey::default()
            },
        };
        let candidates = vec![
            candidate(PolicyActionClass::PlayLand, 1),
            candidate(PolicyActionClass::PlayLand, 2),
            candidate(PolicyActionClass::ProduceMana, 3),
            candidate(PolicyActionClass::ProduceMana, 4),
            candidate(PolicyActionClass::CastSpell, 5),
            candidate(PolicyActionClass::CastSpell, 6),
            candidate(PolicyActionClass::ActivateAbility, 7),
            candidate(PolicyActionClass::ActivateAbility, 8),
            candidate(PolicyActionClass::PassPriority, 9),
        ];

        let retained = retain_bounded_candidates(&candidates, 5);
        assert_eq!(retained.len(), 5);
        for class in [
            PolicyActionClass::PlayLand,
            PolicyActionClass::ProduceMana,
            PolicyActionClass::CastSpell,
            PolicyActionClass::ActivateAbility,
            PolicyActionClass::PassPriority,
        ] {
            assert!(retained.iter().any(|candidate| candidate.class == class));
        }
    }

    #[test]
    fn resolution_order_prioritizes_pass_without_changing_membership() {
        let candidate = |class, kind| TeacherPublicAction {
            class,
            key: PolicyPublicKey {
                kind,
                ..PolicyPublicKey::default()
            },
        };
        let mut candidates = vec![
            candidate(PolicyActionClass::ActivateAbility, 7),
            candidate(PolicyActionClass::PassPriority, 9),
            candidate(PolicyActionClass::ProduceMana, 3),
        ];
        let mut expected = candidates.clone();
        expected.sort_unstable();

        order_teacher_candidates(&mut candidates, true);
        assert_eq!(candidates[0].class, PolicyActionClass::PassPriority);

        let mut actual_membership = candidates;
        actual_membership.sort_unstable();
        assert_eq!(actual_membership, expected);
    }

    #[test]
    fn current_turn_ceiling_requires_every_world_to_win_now() {
        let ceiling = WinDistribution {
            t1_through_t6: [0, 2, 0, 0, 0, 0],
            losses: 0,
        };
        assert!(is_current_turn_ceiling(&ceiling, 2, 2));

        let later = WinDistribution {
            t1_through_t6: [0, 0, 2, 0, 0, 0],
            losses: 0,
        };
        assert!(!is_current_turn_ceiling(&later, 2, 2));

        let partial = WinDistribution {
            t1_through_t6: [0, 1, 0, 0, 0, 0],
            losses: 1,
        };
        assert!(!is_current_turn_ceiling(&partial, 2, 2));
    }
}
