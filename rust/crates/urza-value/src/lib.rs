#![forbid(unsafe_code)]

use urza_info::{InformationState, ObservedDelayedEvent};

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct ValueKey(InformationState);

impl ValueKey {
    pub fn from_information(info: &InformationState) -> Self {
        let mut normalized = info.clone();
        normalized.hand.sort_unstable();
        normalized.graveyard.sort_unstable();
        normalized.exile.sort_unstable();
        normalized
            .library
            .remaining_counts
            .sort_unstable_by_key(|x| x.card);
        normalized
            .battlefield
            .sort_unstable_by_key(|x| x.canonical_id);
        normalized
            .urza_permissions
            .sort_unstable_by_key(|x| x.permission_slot);
        normalized
            .delayed_events
            .sort_unstable_by_key(delayed_event_sort_key);
        Self(normalized)
    }
}

fn delayed_event_sort_key(event: &ObservedDelayedEvent) -> (u8, u16, u8) {
    match event {
        ObservedDelayedEvent::BaubleDraw { source, due_turn } => (0, source.0, *due_turn),
        ObservedDelayedEvent::ChromeCopySacrifice { object, due_turn } => (1, object.0, *due_turn),
        ObservedDelayedEvent::ManaDrainCredit {
            colorless,
            due_turn,
        } => (2, *colorless, *due_turn),
        ObservedDelayedEvent::PermissionExpiry {
            permission_slot,
            due_turn,
        } => (3, *permission_slot, *due_turn),
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum Objective {
    WinByHorizon,
    ProtectionAwareWinByHorizon,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct EvaluationNamespace {
    pub rules_version: String,
    pub catalog_digest: String,
    pub policy_version: String,
    pub objective: Objective,
    pub horizon: u8,
    pub environment_version: String,
    pub rng_scheme_version: String,
    pub sample_namespace: String,
    pub rollout_budget: u32,
    pub continuation_identity: String,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct WinDistribution {
    pub t1_through_t6: [u32; 6],
    pub losses: u32,
}

impl WinDistribution {
    pub fn wins(&self) -> u32 {
        self.t1_through_t6.iter().sum()
    }
}

#[cfg(test)]
mod tests {
    use super::ValueKey;
    use urza_core::CardDefId;
    use urza_info::{CardCount, InformationState};

    #[test]
    fn strategic_key_ignores_unordered_zone_container_order() {
        let mut a = InformationState::default();
        a.hand = vec![CardDefId(3), CardDefId(1)];
        a.library.remaining_counts = vec![
            CardCount {
                card: CardDefId(7),
                count: 1,
            },
            CardCount {
                card: CardDefId(2),
                count: 2,
            },
        ];

        let mut b = a.clone();
        b.hand.reverse();
        b.library.remaining_counts.reverse();

        assert_eq!(
            ValueKey::from_information(&a),
            ValueKey::from_information(&b)
        );
    }
}
