use std::fmt;

use urza_core::CardDefId;
use urza_rng::{RootSeed, WorldId};

use crate::{
    CommanderDeck, KeptHand, MulliganDecision, MulliganError, MulliganStage, OpeningError,
    PregameContext, draw_fresh_seven, start_mulligan_game,
};

pub const MULLIGAN_TRACE_VERSION: &str = "r6_fixed_seed_sequential_trace_v1";

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MulliganTraceEvent {
    PregameSampled(PregameContext),
    SevenVisible {
        stage: MulliganStage,
        cards: Vec<CardDefId>,
    },
    DecisionMade {
        stage: MulliganStage,
        decision: MulliganDecision,
    },
    FreshSevenGenerated {
        stage: MulliganStage,
    },
    Kept {
        stage: MulliganStage,
        hand: Vec<CardDefId>,
        known_bottom: Vec<CardDefId>,
    },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SequentialMulliganTrace {
    pub trace_version: &'static str,
    pub root: RootSeed,
    pub world: WorldId,
    pub events: Vec<MulliganTraceEvent>,
    pub generated_fresh_sevens: u8,
    pub kept: KeptHand<CardDefId>,
}

#[derive(Debug)]
pub enum MulliganTraceError {
    Opening(OpeningError),
    Mulligan(MulliganError),
    ScriptEndedWithoutKeep,
}

impl fmt::Display for MulliganTraceError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Opening(error) => write!(formatter, "trace opening failed: {error}"),
            Self::Mulligan(error) => write!(formatter, "trace mulligan failed: {error}"),
            Self::ScriptEndedWithoutKeep => {
                write!(formatter, "fixed-seed mulligan script ended without a keep")
            }
        }
    }
}

impl std::error::Error for MulliganTraceError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Opening(error) => Some(error),
            Self::Mulligan(error) => Some(error),
            Self::ScriptEndedWithoutKeep => None,
        }
    }
}

impl From<OpeningError> for MulliganTraceError {
    fn from(value: OpeningError) -> Self {
        Self::Opening(value)
    }
}

impl From<MulliganError> for MulliganTraceError {
    fn from(value: MulliganError) -> Self {
        Self::Mulligan(value)
    }
}

/// Execute a deterministic scripted mulligan sequence and record exactly when
/// each future seven becomes generated/visible.
///
/// A `FreshSevenGenerated` event can only appear after the corresponding
/// `DecisionMade { Mulligan }` event because generation happens inside the
/// lazy `MulliganState::mulligan` callback.
pub fn trace_mulligan_script(
    deck: &CommanderDeck,
    root: RootSeed,
    world: WorldId,
    script: &[MulliganDecision],
) -> Result<SequentialMulliganTrace, MulliganTraceError> {
    let mut state = start_mulligan_game(deck, root, world)?;
    let mut events = vec![
        MulliganTraceEvent::PregameSampled(state.pregame()),
        MulliganTraceEvent::SevenVisible {
            stage: state.stage(),
            cards: state.current_seven().to_vec(),
        },
    ];
    let mut generated_fresh_sevens = 0_u8;

    for decision in script {
        let stage = state.stage();
        events.push(MulliganTraceEvent::DecisionMade {
            stage,
            decision: decision.clone(),
        });
        match decision {
            MulliganDecision::Keep { bottom_indices } => {
                let kept = state.keep(bottom_indices)?;
                events.push(MulliganTraceEvent::Kept {
                    stage: kept.stage,
                    hand: kept.hand.clone(),
                    known_bottom: kept.known_bottom.clone(),
                });
                return Ok(SequentialMulliganTrace {
                    trace_version: MULLIGAN_TRACE_VERSION,
                    root,
                    world,
                    events,
                    generated_fresh_sevens,
                    kept,
                });
            }
            MulliganDecision::Mulligan => {
                state = state.mulligan(|next_stage, _pregame| {
                    generated_fresh_sevens = generated_fresh_sevens.saturating_add(1);
                    events.push(MulliganTraceEvent::FreshSevenGenerated { stage: next_stage });
                    let seven = draw_fresh_seven(deck, root, world, next_stage);
                    events.push(MulliganTraceEvent::SevenVisible {
                        stage: next_stage,
                        cards: seven.clone(),
                    });
                    seven
                })?;
            }
        }
    }

    Err(MulliganTraceError::ScriptEndedWithoutKeep)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::load_commander_deck;

    #[test]
    fn fixed_seed_trace_generates_future_seven_only_after_mulligan_decision() {
        let deck = load_commander_deck().unwrap();
        let root = RootSeed::from_u64(0x5236_5452_4143_0001);
        let world = WorldId(808);
        let trace = trace_mulligan_script(
            &deck,
            root,
            world,
            &[
                MulliganDecision::Mulligan,
                MulliganDecision::Keep {
                    bottom_indices: Vec::new(),
                },
            ],
        )
        .unwrap();

        assert_eq!(trace.generated_fresh_sevens, 1);
        assert_eq!(trace.kept.stage, MulliganStage::FreeSeven);
        assert!(matches!(
            trace.events.as_slice(),
            [
                MulliganTraceEvent::PregameSampled(_),
                MulliganTraceEvent::SevenVisible {
                    stage: MulliganStage::InitialSeven,
                    ..
                },
                MulliganTraceEvent::DecisionMade {
                    stage: MulliganStage::InitialSeven,
                    decision: MulliganDecision::Mulligan,
                },
                MulliganTraceEvent::FreshSevenGenerated {
                    stage: MulliganStage::FreeSeven,
                },
                MulliganTraceEvent::SevenVisible {
                    stage: MulliganStage::FreeSeven,
                    ..
                },
                MulliganTraceEvent::DecisionMade {
                    stage: MulliganStage::FreeSeven,
                    decision: MulliganDecision::Keep { .. },
                },
                MulliganTraceEvent::Kept {
                    stage: MulliganStage::FreeSeven,
                    ..
                },
            ]
        ));
        assert!(!trace.events.iter().any(|event| matches!(
            event,
            MulliganTraceEvent::FreshSevenGenerated {
                stage: MulliganStage::Six
            }
        )));
    }

    #[test]
    fn keeping_initial_seven_generates_no_future_hand() {
        let deck = load_commander_deck().unwrap();
        let trace = trace_mulligan_script(
            &deck,
            RootSeed::from_u64(0x5236_5452_4143_0002),
            WorldId(809),
            &[MulliganDecision::Keep {
                bottom_indices: Vec::new(),
            }],
        )
        .unwrap();
        assert_eq!(trace.generated_fresh_sevens, 0);
        assert_eq!(trace.kept.stage, MulliganStage::InitialSeven);
        assert_eq!(
            trace
                .events
                .iter()
                .filter(|event| matches!(event, MulliganTraceEvent::FreshSevenGenerated { .. }))
                .count(),
            0
        );
    }
}
