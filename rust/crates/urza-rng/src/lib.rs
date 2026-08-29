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

/// Deterministic stream scoped to one explicit RNG coordinate.
///
/// The stream is local to a single logical occurrence. Callers obtain a fresh
/// coordinate for a repeated physical random event rather than continuing this
/// stream across occurrences.
#[derive(Debug, Clone)]
pub struct CoordinateStream {
    key: [u8; 32],
    draw_index: u64,
}

impl CoordinateStream {
    pub fn new(root: RootSeed, coordinate: RngCoordinate) -> Self {
        Self {
            key: derive_seed(root, coordinate),
            draw_index: 0,
        }
    }

    pub fn next_u64(&mut self) -> u64 {
        let mut hasher = blake3::Hasher::new_keyed(&self.key);
        hasher.update(b"coordinate-stream-v1");
        hasher.update(&self.draw_index.to_le_bytes());
        self.draw_index = self
            .draw_index
            .checked_add(1)
            .expect("coordinate stream draw counter exhausted");
        let digest = hasher.finalize();
        let mut bytes = [0_u8; 8];
        bytes.copy_from_slice(&digest.as_bytes()[..8]);
        u64::from_le_bytes(bytes)
    }

    pub fn uniform_below(&mut self, upper_exclusive: u64) -> u64 {
        assert!(upper_exclusive > 0, "uniform bound must be positive");
        let threshold = upper_exclusive.wrapping_neg() % upper_exclusive;
        loop {
            let sample = self.next_u64();
            if sample >= threshold {
                return sample % upper_exclusive;
            }
        }
    }
}

pub fn shuffle<T>(values: &mut [T], root: RootSeed, coordinate: RngCoordinate) {
    let mut stream = CoordinateStream::new(root, coordinate);
    for index in (1..values.len()).rev() {
        let swap_with = stream.uniform_below((index + 1) as u64) as usize;
        values.swap(index, swap_with);
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
    fn logical_events_are_independent_coordinates() {
        let root = RootSeed::from_u64(1234);
        let a = coordinate(RngDomain::Game, 0);
        let b = RngCoordinate {
            logical_event: LogicalEventId(a.logical_event.0 + 1),
            ..a
        };
        assert_ne!(derive_seed(root, a), derive_seed(root, b));
    }

    #[test]
    fn root_seeds_are_independent() {
        let coordinate = coordinate(RngDomain::Game, 0);
        assert_ne!(
            derive_seed(RootSeed::from_u64(1), coordinate),
            derive_seed(RootSeed::from_u64(2), coordinate)
        );
    }

    #[test]
    fn search_crn_is_shared_only_for_the_same_logical_occurrence() {
        let root = RootSeed::from_u64(999);
        let shared = CommonRandomCoordinate::search_event(
            WorldId(2),
            EventType(17),
            LogicalEventId(88),
            EventOccurrence(4),
            [5; 16],
        );
        let same_event_candidate_a = shared.seed(root);
        let same_event_candidate_b = shared.seed(root);
        assert_eq!(same_event_candidate_a, same_event_candidate_b);

        let next_occurrence = CommonRandomCoordinate::search_event(
            WorldId(2),
            EventType(17),
            LogicalEventId(88),
            EventOccurrence(5),
            [5; 16],
        );
        assert_ne!(same_event_candidate_a, next_occurrence.seed(root));
    }

    #[test]
    fn shuffle_is_reproducible_and_preserves_the_multiset() {
        let root = RootSeed::from_u64(42);
        let coordinate = coordinate(RngDomain::Game, 3);
        let mut first: Vec<_> = (0..32).collect();
        let mut second = first.clone();
        shuffle(&mut first, root, coordinate);
        shuffle(&mut second, root, coordinate);
        assert_eq!(first, second);

        let mut sorted = first.clone();
        sorted.sort_unstable();
        assert_eq!(sorted, (0..32).collect::<Vec<_>>());
    }

    #[test]
    fn shuffle_changes_with_occurrence_coordinate() {
        let root = RootSeed::from_u64(42);
        let mut first: Vec<_> = (0..32).collect();
        let mut second = first.clone();
        shuffle(&mut first, root, coordinate(RngDomain::Game, 3));
        shuffle(&mut second, root, coordinate(RngDomain::Game, 4));
        assert_ne!(first, second);
    }

    #[test]
    fn bounded_draws_are_inside_the_requested_range() {
        let mut stream = CoordinateStream::new(
            RootSeed::from_u64(123),
            coordinate(RngDomain::Environment, 0),
        );
        for upper in 1..64 {
            for _ in 0..100 {
                assert!(stream.uniform_below(upper) < upper);
            }
        }
    }
}
