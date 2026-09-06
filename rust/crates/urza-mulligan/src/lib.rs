#![forbid(unsafe_code)]

// The decision layer deliberately exposes orchestration functions that bind the
// visible mulligan state to the accepted deck, R5 evaluator, policy, RNG sample,
// and continuation cache. Keep that boundary explicit rather than hiding inputs
// in mutable ambient context merely to satisfy an argument-count heuristic.
#[cfg(test)]
mod acceptance;
mod corpus_dataset;
mod corpus_generation;
mod corpus_review;
#[allow(clippy::too_many_arguments)]
mod decision;
mod engine;
#[cfg(test)]
mod future_invariance;
mod interpretation;
mod report;
mod teacher_corpus;
mod trace;

pub use corpus_dataset::*;
pub use corpus_generation::*;
pub use corpus_review::*;
pub use decision::*;
pub use engine::*;
pub use interpretation::*;
pub use report::*;
pub use teacher_corpus::*;
pub use trace::*;
