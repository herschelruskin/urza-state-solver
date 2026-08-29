#![forbid(unsafe_code)]

pub const RNG_SCHEME_VERSION: &str = "rust_rng_v2_coordinate_prf";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct RootSeed(pub [u8; 32]);

impl RootSeed {
    pub fn from_u64(seed: u64) -> Self {
        let mut bytes = [0_u8; 32];
        bytes[..8].copy_from_slice(&seed.to_le_bytes());
        bytes[8..16].copy_from_slice(&(!seed).to_le_bytes());
        bytes[16..24].copy_from_slice(&seed.rotate_left(17).to_le_bytes());
        bytes[24..32].copy_from_slice(&seed.rotate_right(11).to_le_bytes());
        Self(bytes)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[repr(u8)]
pub enum RngDomain {
    Game = 1,
    OuterHiddenWorld = 2,
    Environment = 3,
    PolicyTie = 4,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
#[repr(transparent)]
pub struct WorldId(pub u64);

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
#[repr(transparent)]
pub struct EventType(pub u16);

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
#[repr(transparent)]
pub struct LogicalEventId(pub u64);

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
#[repr(transparent)]
pub struct EventOccurrence(pub u64);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct RngCoordinate {
    pub domain: RngDomain,
    pub world: WorldId,
    pub event_type: EventType,
    pub logical_event: LogicalEventId,
    pub occurrence: EventOccurrence,
    pub concrete_fingerprint: [u8; 16],
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct CommonRandomCoordinate(pub RngCoordinate);

pub fn derive_seed(root: RootSeed, coordinate: RngCoordinate) -> [u8; 32] {
    let mut hasher = blake3::Hasher::new_keyed(&root.0);
    hasher.update(RNG_SCHEME_VERSION.as_bytes());
    hasher.update(&[0]);
    hasher.update(&[coordinate.domain as u8]);
    hasher.update(&coordinate.world.0.to_le_bytes());
    hasher.update(&coordinate.event_type.0.to_le_bytes());
    hasher.update(&coordinate.logical_event.0.to_le_bytes());
    hasher.update(&coordinate.occurrence.0.to_le_bytes());
    hasher.update(&coordinate.concrete_fingerprint);
    *hasher.finalize().as_bytes()
}

impl CommonRandomCoordinate {
    pub fn search_event(
        world: WorldId,
        event_type: EventType,
        logical_event: LogicalEventId,
        occurrence: EventOccurrence,
        pre_target_fingerprint: [u8; 16],
    ) -> Self {
        Self(RngCoordinate {
            domain: RngDomain::Game,
            world,
            event_type,
            logical_event,
            occurrence,
            concrete_fingerprint: pre_target_fingerprint,
        })
    }

    pub fn seed(self, root: RootSeed) -> [u8; 32] {
        derive_seed(root, self.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn coordinate(domain: RngDomain, occurrence: u64) -> RngCoordinate {
        RngCoordinate {
            domain,
            world: WorldId(7),
            event_type: EventType(3),
            logical_event: LogicalEventId(44),
            occurrence: EventOccurrence(occurrence),
            concrete_fingerprint: [9; 16],
        }
    }

    #[test]
    fn repeated_physical_random_events_get_fresh_occurrence_seeds() {
        let root = RootSeed::from_u64(1234);
        assert_ne!(
            derive_seed(root, coordinate(RngDomain::Game, 0)),
            derive_seed(root, coordinate(RngDomain::Game, 1))
        );
    }

    #[test]
    fn rng_domains_are_independent_coordinates() {
        let root = RootSeed::from_u64(1234);
        assert_ne!(
            derive_seed(root, coordinate(RngDomain::Game, 0)),
            derive_seed(root, coordinate(RngDomain::OuterHiddenWorld, 0))
        );
    }

    #[test]
    fn search_crn_seed_is_pre_target_and_shared_by_candidate_branches() {
        let root = RootSeed::from_u64(999);
        let event = CommonRandomCoordinate::search_event(
            WorldId(2),
            EventType(17),
            LogicalEventId(88),
            EventOccurrence(4),
            [5; 16],
        );
        let candidate_a = event.seed(root);
        let candidate_b = event.seed(root);
        assert_eq!(candidate_a, candidate_b);
    }
}
