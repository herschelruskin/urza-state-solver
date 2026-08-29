use std::hint::black_box;

use criterion::{Criterion, criterion_group, criterion_main};
use urza_core::{CardDefId, ReplayKey, TrueState};

fn replay_key_clone(c: &mut Criterion) {
    let state = TrueState {
        library: (0..99).map(CardDefId).collect(),
        ..TrueState::default()
    };
    c.bench_function("r0/replay_key_clone_99_cards", |b| {
        b.iter(|| ReplayKey::from(black_box(&state)))
    });
}

criterion_group!(benches, replay_key_clone);
criterion_main!(benches);
