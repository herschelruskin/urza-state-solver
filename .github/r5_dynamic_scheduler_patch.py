from pathlib import Path

path = Path("rust/crates/urza-mc/src/parallel.rs")
text = path.read_text()

text = text.replace(
    "use std::thread;\n",
    "use std::sync::atomic::{AtomicUsize, Ordering};\nuse std::thread;\n",
    1,
)
text = text.replace(
    'pub const PARALLEL_ROOT_EVAL_VERSION: &str = "r5_parallel_root_world_v1";',
    'pub const PARALLEL_ROOT_EVAL_VERSION: &str = "r5_parallel_root_world_v2";',
    1,
)

old = '''    if jobs.is_empty() {
        return Ok(Vec::new());
    }
    let active_workers = workers.min(jobs.len());
    let chunk_size = jobs.len().div_ceil(active_workers);

    thread::scope(|scope| {
        let mut handles = Vec::new();
        for chunk in jobs.chunks(chunk_size) {
            handles.push(scope.spawn(move || {
                let mut completed = Vec::with_capacity(chunk.len());
                for &(world_index, root_index) in chunk {
                    let world = &prepared[world_index];
                    let outcome = evaluate_sampled_root_world(
                        &world.sampled,
                        &world.bridge,
                        cards,
                        continuation_policy,
                        root,
                        rollout_max_steps,
                        world.world,
                        &roots[root_index],
                    )?;
                    completed.push((world_index, root_index, outcome));
                }
                Ok::<_, RootActionError>(completed)
            }));
        }

        let mut completed = Vec::with_capacity(jobs.len());
        for handle in handles {
            let mut worker = handle
                .join()
                .map_err(|_| ParallelRootError::WorkerPanic)??;
            completed.append(&mut worker);
        }
        completed.sort_unstable_by_key(|(world_index, root_index, _)| (*world_index, *root_index));
        Ok(completed)
    })
'''

new = '''    if jobs.is_empty() {
        return Ok(Vec::new());
    }
    let active_workers = workers.min(jobs.len());
    let next_job = AtomicUsize::new(0);

    thread::scope(|scope| {
        let mut handles = Vec::with_capacity(active_workers);
        for _ in 0..active_workers {
            let next_job = &next_job;
            handles.push(scope.spawn(move || {
                let mut attempted = Vec::with_capacity(jobs.len().div_ceil(active_workers));
                loop {
                    let job_index = next_job.fetch_add(1, Ordering::Relaxed);
                    if job_index >= jobs.len() {
                        break;
                    }
                    let (world_index, root_index) = jobs[job_index];
                    let world = &prepared[world_index];
                    let outcome = evaluate_sampled_root_world(
                        &world.sampled,
                        &world.bridge,
                        cards,
                        continuation_policy,
                        root,
                        rollout_max_steps,
                        world.world,
                        &roots[root_index],
                    );
                    attempted.push((job_index, outcome));
                }
                attempted
            }));
        }

        let mut attempted = Vec::with_capacity(jobs.len());
        for handle in handles {
            let mut worker = handle
                .join()
                .map_err(|_| ParallelRootError::WorkerPanic)?;
            attempted.append(&mut worker);
        }
        attempted.sort_unstable_by_key(|(job_index, _)| *job_index);

        let mut completed = Vec::with_capacity(jobs.len());
        for (job_index, outcome) in attempted {
            let (world_index, root_index) = jobs[job_index];
            completed.push((world_index, root_index, outcome?));
        }
        Ok(completed)
    })
'''

if old not in text:
    raise SystemExit("static scheduler anchor missing")
text = text.replace(old, new, 1)
path.write_text(text)
