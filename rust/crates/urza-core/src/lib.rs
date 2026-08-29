#![forbid(unsafe_code)]

pub const MODEL_VERSION: &str = "urza_model_r1_2026_08_29";

mod ids;
mod metrics;
mod state;

pub use ids::{AbilityId, CardDefId, ObjectId, PermissionId};
pub use metrics::{EngineCounters, TimingBreakdownNanos};
pub use state::{
    BattlefieldZone, CardZone, CommanderState, CommanderZone, CounterState, DelayedEvent,
    GenericCost, GrantedAbility, LibraryKnowledge, ManaPool, PendingDecision, PendingDecisionKind,
    PermanentMode, PermanentState, Phase, ReplayKey, SourceRef, StackObject, StateValidationError,
    TrueLibrary, TrueState, UrzaPermission, Window,
};
