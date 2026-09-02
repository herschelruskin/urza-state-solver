#![forbid(unsafe_code)]

pub const R2_MODEL_VERSION: &str = "urza_model_r2_2026_09_01";
pub const R3_MODEL_VERSION: &str = "urza_model_r3b_2026_09_01";
pub const MODEL_VERSION: &str = "urza_model_r4a_2026_09_01";

mod ids;
mod metrics;
mod state;

pub use ids::{AbilityId, CardDefId, ObjectId, PermissionId};
pub use metrics::{EngineCounters, TimingBreakdownNanos};
pub use state::{
    BattlefieldZone, CardFace, CardZone, CommanderState, CommanderZone, CounterState, DelayedEvent,
    GenericCost, GrantedAbility, LibraryKnowledge, ManaPool, PendingDecision, PendingDecisionKind,
    PermanentMode, PermanentState, Phase, ReplayKey, SourceRef, StackObject, StateValidationError,
    TrueLibrary, TrueState, UrzaPermission, Window,
};
