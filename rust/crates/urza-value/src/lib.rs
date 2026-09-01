#![forbid(unsafe_code)]

use std::collections::BTreeMap;

use thiserror::Error;
use urza_info::{CardCount, InformationState, ObservedDelayedEvent};

pub const VALUE_KEY_SCHEMA_VERSION: &str = "value_key_v3_r3";

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct ValueKey(InformationState);

#[derive(Debug, Error, PartialEq, Eq)]
pub enum ValueKeyError {
    #[error("duplicate observed permission slot {0}")]
    DuplicatePermissionSlot(u16),
    #[error("delayed permission expiry references unknown permission slot {0}")]
    UnknownPermissionSlot(u16),
    #[error("library count overflow while canonicalizing card {0:?}")]
    LibraryCountOverflow(urza_info::CardDefId),
}

impl ValueKey {
    pub fn try_from_information(info: &InformationState) -> Result<Self, ValueKeyError> {
        let mut normalized = info.clone();

        normalized.hand.sort_unstable();
        normalized.graveyard.sort_unstable();
        normalized.exile.sort_unstable();
        normalized.library.remaining_counts =
            canonical_library_counts(&normalized.library.remaining_counts)?;

        normalized
            .battlefield
            .sort_unstable_by_key(|permanent| permanent.canonical_id);

        let mut slot_map = BTreeMap::new();
        normalized
            .urza_permissions
            .sort_unstable_by_key(|permission| {
                (
                    permission.card,
                    permission.expires_turn,
                    permission.free_cast,
                    permission.source,
                    permission.permission_slot,
                )
            });
        for (canonical_slot, permission) in normalized.urza_permissions.iter_mut().enumerate() {
            let canonical_slot = canonical_slot as u16;
            if slot_map
                .insert(permission.permission_slot, canonical_slot)
                .is_some()
            {
                return Err(ValueKeyError::DuplicatePermissionSlot(
                    permission.permission_slot,
                ));
            }
            permission.permission_slot = canonical_slot;
        }

        for event in &mut normalized.delayed_events {
            if let ObservedDelayedEvent::PermissionExpiry {
                permission_slot, ..
            } = event
            {
                *permission_slot = *slot_map
                    .get(permission_slot)
                    .ok_or(ValueKeyError::UnknownPermissionSlot(*permission_slot))?;
            }
        }

        normalized.delayed_events.sort_unstable();

        Ok(Self(normalized))
    }
}

fn canonical_library_counts(counts: &[CardCount]) -> Result<Vec<CardCount>, ValueKeyError> {
    let mut merged: BTreeMap<_, u16> = BTreeMap::new();
    for entry in counts {
        if entry.count == 0 {
            continue;
        }
        let total = merged.entry(entry.card).or_default();
        *total = total
            .checked_add(u16::from(entry.count))
            .ok_or(ValueKeyError::LibraryCountOverflow(entry.card))?;
    }

    merged
        .into_iter()
        .map(|(card, count)| {
            let count =
                u8::try_from(count).map_err(|_| ValueKeyError::LibraryCountOverflow(card))?;
            Ok(CardCount { card, count })
        })
        .collect()
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
    pub model_version: String,
    pub policy_version: String,
    pub value_key_schema_version: String,
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
    use super::{ValueKey, ValueKeyError};
    use urza_info::CardDefId;
    use urza_info::{
        CanonicalObjectId, CardCount, InformationState, LibraryBelief, ObservedDelayedEvent,
        ObservedPermission, ObservedSourceRef,
    };

    #[test]
    fn strategic_key_ignores_unordered_zone_and_count_container_order() {
        let a = InformationState {
            hand: vec![CardDefId(3), CardDefId(1)],
            library: LibraryBelief {
                remaining_counts: vec![
                    CardCount {
                        card: CardDefId(7),
                        count: 1,
                    },
                    CardCount {
                        card: CardDefId(2),
                        count: 2,
                    },
                    CardCount {
                        card: CardDefId(7),
                        count: 2,
                    },
                ],
                ..LibraryBelief::default()
            },
            ..InformationState::default()
        };

        let b = InformationState {
            hand: vec![CardDefId(1), CardDefId(3)],
            library: LibraryBelief {
                remaining_counts: vec![
                    CardCount {
                        card: CardDefId(7),
                        count: 3,
                    },
                    CardCount {
                        card: CardDefId(2),
                        count: 2,
                    },
                ],
                ..LibraryBelief::default()
            },
            ..InformationState::default()
        };

        assert_eq!(
            ValueKey::try_from_information(&a).unwrap(),
            ValueKey::try_from_information(&b).unwrap()
        );
    }

    #[test]
    fn known_top_order_remains_strategically_distinct() {
        let a = InformationState {
            library: LibraryBelief {
                known_top: vec![CardDefId(1), CardDefId(2)],
                ..LibraryBelief::default()
            },
            ..InformationState::default()
        };
        let b = InformationState {
            library: LibraryBelief {
                known_top: vec![CardDefId(2), CardDefId(1)],
                ..LibraryBelief::default()
            },
            ..InformationState::default()
        };
        assert_ne!(
            ValueKey::try_from_information(&a).unwrap(),
            ValueKey::try_from_information(&b).unwrap()
        );
    }

    #[test]
    fn permission_sequence_ids_are_not_strategic_provenance() {
        let permission_a = ObservedPermission {
            permission_slot: 10,
            card: CardDefId(5),
            expires_turn: 3,
            free_cast: true,
            source: ObservedSourceRef {
                canonical_object: Some(CanonicalObjectId(1)),
                card: CardDefId(99),
            },
        };
        let permission_b = ObservedPermission {
            permission_slot: 77,
            ..permission_a.clone()
        };

        let a = InformationState {
            urza_permissions: vec![permission_a],
            delayed_events: vec![ObservedDelayedEvent::PermissionExpiry {
                permission_slot: 10,
                due_turn: 3,
            }],
            ..InformationState::default()
        };
        let b = InformationState {
            urza_permissions: vec![permission_b],
            delayed_events: vec![ObservedDelayedEvent::PermissionExpiry {
                permission_slot: 77,
                due_turn: 3,
            }],
            ..InformationState::default()
        };

        assert_eq!(
            ValueKey::try_from_information(&a).unwrap(),
            ValueKey::try_from_information(&b).unwrap()
        );
    }

    #[test]
    fn unknown_permission_expiry_reference_is_rejected() {
        let info = InformationState {
            delayed_events: vec![ObservedDelayedEvent::PermissionExpiry {
                permission_slot: 42,
                due_turn: 3,
            }],
            ..InformationState::default()
        };

        assert_eq!(
            ValueKey::try_from_information(&info),
            Err(ValueKeyError::UnknownPermissionSlot(42))
        );
    }

    #[test]
    fn stack_order_remains_strategically_distinct() {
        use urza_info::{ObservedStackKind, ObservedStackObject};

        let first = ObservedStackObject {
            kind: ObservedStackKind::Spell,
            card: Some(CardDefId(1)),
            source: None,
            ability: None,
            parameter: None,
        };
        let second = ObservedStackObject {
            kind: ObservedStackKind::Spell,
            card: Some(CardDefId(2)),
            source: None,
            ability: None,
            parameter: None,
        };
        let a = InformationState {
            stack: vec![first.clone(), second.clone()],
            ..InformationState::default()
        };
        let b = InformationState {
            stack: vec![second, first],
            ..InformationState::default()
        };

        assert_ne!(
            ValueKey::try_from_information(&a).unwrap(),
            ValueKey::try_from_information(&b).unwrap()
        );
    }

    #[test]
    fn stack_numeric_parameter_is_strategically_future_relevant() {
        use urza_info::{ObservedStackKind, ObservedStackObject};

        let make = |parameter| InformationState {
            stack: vec![ObservedStackObject {
                kind: ObservedStackKind::Spell,
                card: Some(CardDefId(93)),
                source: None,
                ability: None,
                parameter,
            }],
            ..InformationState::default()
        };
        assert_ne!(
            ValueKey::try_from_information(&make(Some(1))).unwrap(),
            ValueKey::try_from_information(&make(Some(2))).unwrap()
        );
    }
}
