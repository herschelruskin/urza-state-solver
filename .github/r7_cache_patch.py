from pathlib import Path


def replace_one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


path = Path("rust/crates/urza-mulligan/src/teacher_search.rs")
text = path.read_text()

text = replace_one(
    text,
    'pub const R7_TEACHER_SEARCH_VERSION: &str = "r7_public_belief_bounded_search_v4";',
    'pub const R7_TEACHER_SEARCH_VERSION: &str = "r7_public_belief_bounded_search_v5";',
    "search version",
)
text = replace_one(
    text,
    "Complete sampled-belief subtrees are memoized only after a finite value is known; cache identity includes the sampled exact-world support and RNG coordinates but never changes public action identity.",
    "Exact sampled-belief subtree outcomes are memoized after evaluation; complete values remain finite values, while incomplete leaves and all-incomplete decisions are cached only as the same explicit incomplete outcome and are never converted into losses or scores. Cache identity includes the sampled exact-world support and RNG coordinates but never changes public action identity.",
    "boundary cache text",
)

key_impl = '''impl TeacherBeliefSubtreeKey {
    fn new(worlds: &[TeacherWorld], choices_left: u8, steps_left: u16) -> Self {
        let mut worlds: Vec<_> = worlds
            .iter()
            .map(|world| TeacherBeliefWorldKey {
                world: world.world.0,
                state: ReplayKey::from(&world.state),
                logical_event: world.logical_event,
            })
            .collect();
        worlds.sort_unstable_by_key(|world| world.world);
        Self {
            choices_left,
            steps_left,
            worlds,
        }
    }
}
'''
outcome_impl = key_impl + '''
#[derive(Debug, Clone, PartialEq, Eq)]
enum TeacherBeliefSubtreeOutcome {
    Complete(WinDistribution),
    IncompleteLeaf { world: WorldId, stop: RolloutStop },
    AllCandidateBranchesIncomplete { candidate_count: usize },
}

impl TeacherBeliefSubtreeOutcome {
    fn from_result(result: &Result<WinDistribution, TeacherSearchError>) -> Option<Self> {
        match result {
            Ok(value) => Some(Self::Complete(value.clone())),
            Err(TeacherSearchError::IncompleteLeaf { world, stop }) => Some(Self::IncompleteLeaf {
                world: *world,
                stop: *stop,
            }),
            Err(TeacherSearchError::AllCandidateBranchesIncomplete { candidate_count }) => {
                Some(Self::AllCandidateBranchesIncomplete {
                    candidate_count: *candidate_count,
                })
            }
            Err(_) => None,
        }
    }

    fn as_result(&self) -> Result<WinDistribution, TeacherSearchError> {
        match self {
            Self::Complete(value) => Ok(value.clone()),
            Self::IncompleteLeaf { world, stop } => Err(TeacherSearchError::IncompleteLeaf {
                world: *world,
                stop: *stop,
            }),
            Self::AllCandidateBranchesIncomplete { candidate_count } => {
                Err(TeacherSearchError::AllCandidateBranchesIncomplete {
                    candidate_count: *candidate_count,
                })
            }
        }
    }
}
'''
text = replace_one(text, key_impl, outcome_impl, "cached outcome enum")
text = replace_one(
    text,
    "    subtree_cache: HashMap<TeacherBeliefSubtreeKey, WinDistribution>,",
    "    subtree_cache: HashMap<TeacherBeliefSubtreeKey, TeacherBeliefSubtreeOutcome>,",
    "cache value type",
)

old_wrapper = '''        if let Some(cached) = self.subtree_cache.get(&key) {
            self.stats.subtree_cache_hits = self.stats.subtree_cache_hits.saturating_add(1);
            return Ok(cached.clone());
        }

        let value = self.evaluate_partition_uncached(worlds, choices_left, steps_left)?;
        self.subtree_cache.insert(key, value.clone());
        self.stats.subtree_cache_inserts = self.stats.subtree_cache_inserts.saturating_add(1);
        Ok(value)
'''
new_wrapper = '''        if let Some(cached) = self.subtree_cache.get(&key) {
            self.stats.subtree_cache_hits = self.stats.subtree_cache_hits.saturating_add(1);
            return cached.as_result();
        }

        let result = self.evaluate_partition_uncached(worlds, choices_left, steps_left);
        if let Some(outcome) = TeacherBeliefSubtreeOutcome::from_result(&result) {
            self.subtree_cache.insert(key, outcome);
            self.stats.subtree_cache_inserts = self.stats.subtree_cache_inserts.saturating_add(1);
        }
        result
'''
text = replace_one(text, old_wrapper, new_wrapper, "cache wrapper")

marker = '''    #[test]
    fn candidate_cap_is_class_stratified_and_semantically_deterministic() {
'''
new_test = '''    #[test]
    fn incomplete_teacher_partition_is_reused_without_becoming_a_value() {
        let cards = R4CardDatabase::load().expect("R4 database");
        let config = TeacherSearchConfig {
            samples: 1,
            max_choice_depth: 0,
            leaf_rollout_max_steps: 1,
            ..TeacherSearchConfig::default()
        };
        let mut evaluator = TeacherEvaluator {
            cards: &cards,
            config,
            baseline_policy: DeterministicPolicy,
            subtree_cache: HashMap::new(),
            stats: TeacherSearchStats::default(),
        };
        let island = cards.card_id_by_name("Island").unwrap();
        let world = TeacherWorld {
            world: WorldId(78),
            state: TrueState {
                turn: 2,
                phase: Phase::PrecombatMain,
                window: Window::Priority,
                hand: CardZone::new(vec![island]),
                ..TrueState::default()
            },
            logical_event: 0,
        };

        let first = evaluator.evaluate_partition(vec![world.clone()], 0, 4);
        assert!(is_incomplete_subtree(first.as_ref().unwrap_err()));
        assert_eq!(evaluator.stats.subtree_cache_hits, 0);
        assert_eq!(evaluator.stats.subtree_cache_inserts, 1);

        let second = evaluator.evaluate_partition(vec![world], 0, 4);
        assert!(is_incomplete_subtree(second.as_ref().unwrap_err()));
        assert_eq!(evaluator.stats.subtree_cache_hits, 1);
        assert_eq!(evaluator.stats.subtree_cache_inserts, 1);
    }

'''
text = replace_one(text, marker, new_test + marker, "incomplete cache test")
path.write_text(text)
