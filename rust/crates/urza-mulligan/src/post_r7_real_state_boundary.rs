use std::error::Error;
use std::io;

use urza_cards::R4CardDatabase;
use urza_core::{CardDefId, Phase, TrueState};
use urza_mc::sample_hidden_world;
use urza_policy::DeterministicPolicy;
use urza_rng::WorldId;
use urza_rollout::{RolloutConfig, RolloutStop, replay_trace, rollout};

use crate::{
    KeptHand, MulliganStage, bridge_kept_hand, draw_fresh_seven, load_commander_deck,
    r7_pilot_generation_config, sample_pregame_context,
};

pub const POST_R7_REAL_STATE_BOUNDARY_VERSION: &str = "post_r7_real_state_boundary_v1";
pub const POST_R7_REAL_STATE_SOURCE_VERSION: &str =
    "accepted_r7_pilot_world_100005_r5_world_200000_v1";
pub const POST_R7_REAL_STATE_SOURCE_OPENING_WORLD: WorldId = WorldId(100_005);
pub const POST_R7_REAL_STATE_R5_ROOT_SEED: u64 = 0x5052_3752_4541_0001;
pub const POST_R7_REAL_STATE_TEACHER_ROOT_SEED: u64 = 0x5052_3754_4541_0001;
pub const POST_R7_REAL_STATE_FIRST_PROBE_WORLD: WorldId = WorldId(960_000);
pub const POST_R7_REAL_STATE_R5_SAMPLES: u32 = 1;
pub const POST_R7_REAL_STATE_TEACHER_SAMPLES: u32 = 1;
pub const POST_R7_REAL_STATE_TEACHER_STEPS: u16 = 12;
pub const POST_R7_REAL_STATE_TEACHER_CANDIDATES: usize = 12;
pub const POST_R7_REAL_STATE_BOUNDARY: &str = "Post-R7 real-state boundary cases are replayed from one actual accepted pilot keep and one \
     frozen-production hidden-world rollout. They are not synthetic abundant-mana states. The four \
     tiers are the exact sampled kept opening state, the state after the first frozen-R5 action at \
     the first turn-1 main-phase decision, the state after the first frozen-R5 action at the first \
     turn-2 main-phase decision, and a late state after the penultimate frozen-R5 action. R5 and \
     bounded teacher probes independently resample only from each tier's legal public library belief. \
     Teacher results are a read-only oracle/sidecar and cannot alter mulligan decisions, production \
     policy, cache identity, interpretation features, or gameplay. Incomplete and timeout outcomes \
     are diagnostic statuses, never losses.";

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum PostR7RealStateTier {
    KeptOpening,
    Turn1Main,
    Turn2Main,
    LateRealState,
}

impl PostR7RealStateTier {
    pub const ALL: [Self; 4] = [
        Self::KeptOpening,
        Self::Turn1Main,
        Self::Turn2Main,
        Self::LateRealState,
    ];

    pub const fn label(self) -> &'static str {
        match self {
            Self::KeptOpening => "kept-opening",
            Self::Turn1Main => "turn-1-main",
            Self::Turn2Main => "turn-2-main",
            Self::LateRealState => "late-real-state",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PostR7RealStateCase {
    pub tier: PostR7RealStateTier,
    pub state: TrueState,
    /// Number of frozen-production source actions replayed to construct this state.
    pub source_action_prefix_len: usize,
    pub source_trace_len: usize,
    pub source_stop: RolloutStop,
    pub source_opening_world: WorldId,
    pub source_hidden_world: WorldId,
}

pub fn build_post_r7_real_state_cases(
    cards: &R4CardDatabase,
) -> Result<Vec<PostR7RealStateCase>, Box<dyn Error>> {
    let generation = r7_pilot_generation_config();
    let deck = load_commander_deck()?;
    let opening_world = POST_R7_REAL_STATE_SOURCE_OPENING_WORLD;
    let stage = MulliganStage::InitialSeven;
    let hand = draw_fresh_seven(&deck, generation.opening_root, opening_world, stage);
    assert_expected_source_hand(cards, &hand)?;

    let pregame = sample_pregame_context(generation.opening_root, opening_world);
    if pregame.seat != 1 || pregame.gemstone_caverns_eligible {
        return Err(Box::new(io::Error::other(format!(
            "accepted pilot world 100005 pregame drifted: seat={}, caverns_eligible={}",
            pregame.seat, pregame.gemstone_caverns_eligible
        ))));
    }

    let kept = KeptHand {
        stage,
        hand,
        known_bottom: Vec::new(),
        pregame,
    };
    let opening = bridge_kept_hand(
        &kept,
        &deck,
        generation.opening_root,
        opening_world,
    )?;

    let source_hidden_world = generation.evaluation.rollout.first_world;
    let exact_opening = sample_hidden_world(
        opening.true_state(),
        generation.evaluation.rollout.root,
        source_hidden_world,
    )?;
    let source_config = RolloutConfig {
        root: generation.evaluation.rollout.root,
        world: source_hidden_world,
        max_steps: generation.evaluation.rollout.rollout_max_steps,
    };
    let source = rollout(
        exact_opening.clone(),
        cards,
        &DeterministicPolicy,
        source_config,
    )?;
    if source.trace.len() < 3 {
        return Err(Box::new(io::Error::other(format!(
            "accepted pilot source trajectory is too short for a backward ladder: {} actions",
            source.trace.len()
        ))));
    }

    let t1_index = source
        .trace
        .iter()
        .position(|step| step.turn == 1 && step.phase == Phase::PrecombatMain)
        .ok_or_else(|| io::Error::other("source trajectory has no turn-1 main-phase decision"))?;
    let t2_index = source
        .trace
        .iter()
        .position(|step| step.turn == 2 && step.phase == Phase::PrecombatMain)
        .ok_or_else(|| io::Error::other("source trajectory has no turn-2 main-phase decision"))?;
    let late_index = source.trace.len() - 2;
    if late_index <= t2_index {
        return Err(Box::new(io::Error::other(
            "source trajectory does not extend beyond the turn-2 ladder tier",
        )));
    }

    let t1 = replay_after_action(
        &exact_opening,
        cards,
        source_config,
        &source.trace,
        t1_index,
    )?;
    let t2 = replay_after_action(
        &exact_opening,
        cards,
        source_config,
        &source.trace,
        t2_index,
    )?;
    let late = replay_after_action(
        &exact_opening,
        cards,
        source_config,
        &source.trace,
        late_index,
    )?;

    let cases = vec![
        PostR7RealStateCase {
            tier: PostR7RealStateTier::KeptOpening,
            state: exact_opening,
            source_action_prefix_len: 0,
            source_trace_len: source.trace.len(),
            source_stop: source.stop,
            source_opening_world: opening_world,
            source_hidden_world,
        },
        PostR7RealStateCase {
            tier: PostR7RealStateTier::Turn1Main,
            state: t1,
            source_action_prefix_len: t1_index + 1,
            source_trace_len: source.trace.len(),
            source_stop: source.stop,
            source_opening_world: opening_world,
            source_hidden_world,
        },
        PostR7RealStateCase {
            tier: PostR7RealStateTier::Turn2Main,
            state: t2,
            source_action_prefix_len: t2_index + 1,
            source_trace_len: source.trace.len(),
            source_stop: source.stop,
            source_opening_world: opening_world,
            source_hidden_world,
        },
        PostR7RealStateCase {
            tier: PostR7RealStateTier::LateRealState,
            state: late,
            source_action_prefix_len: late_index + 1,
            source_trace_len: source.trace.len(),
            source_stop: source.stop,
            source_opening_world: opening_world,
            source_hidden_world,
        },
    ];

    for case in &cases {
        case.state.validate()?;
    }
    Ok(cases)
}

fn replay_after_action(
    initial: &TrueState,
    cards: &R4CardDatabase,
    config: RolloutConfig,
    trace: &[urza_rollout::RolloutStep],
    index: usize,
) -> Result<TrueState, Box<dyn Error>> {
    let end = index
        .checked_add(1)
        .ok_or_else(|| io::Error::other("source trace prefix overflow"))?;
    Ok(replay_trace(
        initial.clone(),
        cards,
        config,
        &trace[..end],
    )?)
}

fn assert_expected_source_hand(
    cards: &R4CardDatabase,
    actual: &[CardDefId],
) -> Result<(), Box<dyn Error>> {
    let names = [
        "Mental Misstep",
        "Island",
        "Mana Drain",
        "Fortune Teller's Talent",
        "Valley Floodcaller",
        "Basalt Monolith",
        "Urza's Bauble",
    ];
    let mut expected = Vec::with_capacity(names.len());
    for name in names {
        expected.push(
            cards
                .card_id_by_name(name)
                .ok_or_else(|| io::Error::other(format!("missing source card {name}")))?,
        );
    }
    expected.sort_unstable();
    let mut actual = actual.to_vec();
    actual.sort_unstable();
    if actual != expected {
        return Err(Box::new(io::Error::other(
            "accepted R7 pilot world 100005 opening-hand identity drifted",
        )));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use urza_info::observe;

    #[test]
    fn real_state_ladder_is_replayed_from_one_accepted_pilot_trajectory() {
        let cards = R4CardDatabase::load().unwrap();
        let cases = build_post_r7_real_state_cases(&cards).unwrap();

        assert_eq!(cases.len(), PostR7RealStateTier::ALL.len());
        assert_eq!(cases[0].tier, PostR7RealStateTier::KeptOpening);
        assert_eq!(cases[0].source_action_prefix_len, 0);
        assert!(cases[1].source_action_prefix_len > 0);
        assert!(cases[2].source_action_prefix_len > cases[1].source_action_prefix_len);
        assert!(cases[3].source_action_prefix_len > cases[2].source_action_prefix_len);
        assert!(cases.iter().all(|case| {
            case.source_opening_world == POST_R7_REAL_STATE_SOURCE_OPENING_WORLD
                && case.source_hidden_world == cases[0].source_hidden_world
                && case.source_trace_len == cases[0].source_trace_len
                && case.source_stop == cases[0].source_stop
        }));

        let opening = observe(&cases[0].state).unwrap();
        assert_eq!(opening.turn, 1);
        assert_eq!(opening.phase, Phase::Untap);
        let turn1 = observe(&cases[1].state).unwrap();
        assert_eq!(turn1.turn, 1);
        assert_eq!(turn1.phase, Phase::PrecombatMain);
        let turn2 = observe(&cases[2].state).unwrap();
        assert_eq!(turn2.turn, 2);
        assert_eq!(turn2.phase, Phase::PrecombatMain);
    }
}
