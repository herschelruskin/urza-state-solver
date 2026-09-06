#![forbid(unsafe_code)]

// The decision layer deliberately exposes orchestration functions that bind the
// visible mulligan state to the accepted deck, R5 evaluator, policy, RNG sample,
// and continuation cache. Keep that boundary explicit rather than hiding inputs
// in mutable ambient context merely to satisfy an argument-count heuristic.
#[allow(clippy::too_many_arguments)]
mod decision;
mod engine;
mod report;

pub use decision::*;
pub use engine::*;
pub use report::*;
