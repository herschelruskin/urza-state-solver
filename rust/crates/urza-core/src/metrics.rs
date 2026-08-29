#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct TimingBreakdownNanos {
    pub value_key: u64,
    pub action_generation: u64,
    pub transition: u64,
    pub cache: u64,
    pub policy: u64,
    pub monte_carlo: u64,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct EngineCounters {
    pub states_visited: u64,
    pub decision_requests: u64,
    pub actions_generated_before_factoring: u64,
    pub actions_generated_after_factoring: u64,
    pub max_request_fanout: u64,
    pub state_clones: u64,
    pub cache_hits: u64,
    pub cache_misses: u64,
    pub cache_evictions: u64,
    pub trajectory_steps: u64,
    pub timings_ns: TimingBreakdownNanos,
}

impl EngineCounters {
    pub fn observe_request(&mut self, before: usize, after: usize) {
        self.decision_requests += 1;
        self.actions_generated_before_factoring += before as u64;
        self.actions_generated_after_factoring += after as u64;
        self.max_request_fanout = self.max_request_fanout.max(after as u64);
    }
}

#[cfg(test)]
mod tests {
    use super::EngineCounters;

    #[test]
    fn request_metrics_accumulate_and_track_maximum() {
        let mut counters = EngineCounters::default();
        counters.observe_request(100, 30);
        counters.observe_request(12, 12);
        assert_eq!(counters.decision_requests, 2);
        assert_eq!(counters.actions_generated_before_factoring, 112);
        assert_eq!(counters.actions_generated_after_factoring, 42);
        assert_eq!(counters.max_request_fanout, 30);
    }
}
