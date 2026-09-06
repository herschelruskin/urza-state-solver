use std::error::Error;

use urza_mulligan::{
    R7_TEACHER_KEEP_ANNOTATION_BOUNDARY, R7_TEACHER_KEEP_ANNOTATION_VERSION,
    TeacherKeepResolution, TeacherKeepUnresolved, annotate_r6_keep_packages,
    generate_evaluated_hand_corpus, r7_smoke_generation_config,
    r7_teacher_sidecar_smoke_search_config,
};

fn main() {
    if let Err(error) = run() {
        eprintln!("r7-teacher-sidecar failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn Error>> {
    let mut generation = r7_smoke_generation_config();
    generation.world_count = 1;
    let generated = generate_evaluated_hand_corpus(&generation)?;
    let search = r7_teacher_sidecar_smoke_search_config();
    let annotated = annotate_r6_keep_packages(&generated.corpus, search)?;

    println!("R7_TEACHER_SIDECAR\t{R7_TEACHER_KEEP_ANNOTATION_VERSION}");
    println!("BOUNDARY\t{R7_TEACHER_KEEP_ANNOTATION_BOUNDARY}");
    println!(
        "SEARCH\tsamples={}\tchoice_depth={}\tsteps={}\tcandidate_cap={}",
        search.samples,
        search.max_choice_depth,
        search.max_teacher_steps,
        search.max_candidates_per_group,
    );
    println!(
        "STATS\trecords={}\tresolved={}\tunresolved={}\tpositive={}\tzero={}\tteacher_worlds={}",
        annotated.stats.records_attempted,
        annotated.stats.resolved_records,
        annotated.stats.unresolved_records,
        annotated.stats.resolved_positive_records,
        annotated.stats.resolved_zero_records,
        annotated.stats.allocated_teacher_worlds,
    );

    for (sample, annotation) in annotated.entries() {
        match &annotation.resolution {
            TeacherKeepResolution::Resolved(result) => println!(
                "ANNOTATION\tworld={}\tstage={:?}\tsource_action={:?}\tresolution=resolved\twins={}/{}\tgroups={}\tactions={}\tincomplete_branches={}",
                sample.opening_world.0,
                sample.stage,
                annotation.source_recommended_action,
                result.score.total_wins,
                result.stats.sampled_worlds,
                result.stats.public_groups_evaluated,
                result.stats.public_actions_evaluated,
                result.stats.incomplete_candidate_branches,
            ),
            TeacherKeepResolution::Unresolved(reason) => println!(
                "ANNOTATION\tworld={}\tstage={:?}\tsource_action={:?}\tresolution=unresolved\treason={}",
                sample.opening_world.0,
                sample.stage,
                annotation.source_recommended_action,
                unresolved_name(*reason),
            ),
        }
    }

    Ok(())
}

const fn unresolved_name(reason: TeacherKeepUnresolved) -> &'static str {
    match reason {
        TeacherKeepUnresolved::LeafStepLimit { .. } => "leaf-step-limit",
        TeacherKeepUnresolved::LeafNoCandidate { .. } => "leaf-no-candidate",
        TeacherKeepUnresolved::AllCandidateBranchesIncomplete { .. } => {
            "all-candidate-branches-incomplete"
        }
    }
}
