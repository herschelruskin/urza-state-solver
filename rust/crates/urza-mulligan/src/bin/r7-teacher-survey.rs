use std::error::Error;

use urza_mulligan::{
    InterpretationCatalog, MulliganChoice, MulliganStage, TeacherKeepResolution,
    TeacherKeepUnresolved, r7_teacher_sidecar_survey_search_config, run_r7_teacher_sidecar_survey,
};

fn main() {
    if let Err(error) = run() {
        eprintln!("r7-teacher-survey failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn Error>> {
    let survey = run_r7_teacher_sidecar_survey()?;
    let interpretation = InterpretationCatalog::load()?;
    let search = r7_teacher_sidecar_survey_search_config();
    let source = &survey.generated;
    let stats = survey.stats;

    println!("R7_TEACHER_SURVEY\t{}", survey.survey_version);
    println!("PROFILE\t{}", survey.profile_version);
    println!("BOUNDARY\t{}", survey.boundary);
    println!("SOURCE_GENERATOR\t{}", source.provenance.generator_version);
    println!("SOURCE_CORPUS\t{}", source.provenance.corpus_version);
    println!("SOURCE_DECK\t{}", source.provenance.deck_version);
    println!("SOURCE_POLICY\t{}", source.provenance.policy_version);
    println!("SOURCE_DECISION\t{}", source.provenance.decision_version);
    println!(
        "SOURCE_WINDOW\tfirst_world={}\tworld_count={}",
        source.provenance.first_world.0, source.provenance.world_count
    );
    println!(
        "SOURCE_BUDGET\tr5_samples={}\tr5_steps={}\tr6_future_hands={}",
        source.provenance.evaluation.rollout.samples,
        source.provenance.evaluation.rollout.rollout_max_steps,
        source.provenance.evaluation.future_hand_samples
    );
    println!(
        "TEACHER_BUDGET\tfirst_world={}\tsamples={}\tchoice_depth={}\tsteps={}\tcandidate_cap={}\tleaf_steps={}",
        search.first_world.0,
        search.samples,
        search.max_choice_depth,
        search.max_teacher_steps,
        search.max_candidates_per_group,
        search.leaf_rollout_max_steps
    );
    println!(
        "SOURCE_STATS\tworlds={}\tdecisions={}\tkeep={}\tmull={}\tcache_hits={}\tcache_misses={}",
        source.stats.worlds_completed,
        source.stats.evaluated_decisions,
        source.stats.keep_decisions,
        source.stats.mulligan_decisions,
        source.stats.continuation_cache_hits,
        source.stats.continuation_cache_misses
    );
    println!(
        "SOURCE_STAGES\t{}",
        stage_counts(&source.stats.stage_decisions)
    );
    println!(
        "SURVEY_STATS\trecords={}\tresolved={}\tunresolved={}\tpositive={}\tzero={}\tsource_keep={}\tsource_mull={}",
        stats.records,
        stats.resolved_records,
        stats.unresolved_records,
        stats.resolved_positive_records,
        stats.resolved_zero_records,
        stats.source_keep_records,
        stats.source_mull_records
    );
    println!(
        "SOURCE_ACTION_CROSS_TAB\tpositive_keep={}\tpositive_mull={}\tzero_keep={}\tzero_mull={}\tunresolved_keep={}\tunresolved_mull={}",
        stats.positive_on_source_keep,
        stats.positive_on_source_mull,
        stats.zero_on_source_keep,
        stats.zero_on_source_mull,
        stats.unresolved_source_keep,
        stats.unresolved_source_mull
    );
    println!(
        "SURVEY_STAGES\trecords={}\tpositive={}\tunresolved={}",
        stage_counts(&stats.stage_records),
        stage_counts(&stats.stage_positive),
        stage_counts(&stats.stage_unresolved)
    );
    println!(
        "TEACHER_EFFORT\tsampled_worlds={}\tgroups={}\tactions={}\tforced_steps={}\ttruncated_groups={}\tincomplete_branches={}\tleaf_rollouts={}\tobservation_splits={}\tmax_full_candidates={}\tmax_retained_candidates={}",
        stats.teacher_sampled_worlds,
        stats.public_groups_evaluated,
        stats.public_actions_evaluated,
        stats.forced_public_steps,
        stats.truncated_public_groups,
        stats.incomplete_candidate_branches,
        stats.leaf_rollouts,
        stats.observation_splits,
        stats.max_full_candidate_count,
        stats.max_retained_candidate_count
    );

    for (sample, annotation) in survey.annotated.entries() {
        let record = source
            .corpus
            .get(*sample)
            .ok_or_else(|| format!("missing source corpus record for {sample:?}"))?;
        let kept_names = card_names(&interpretation, &annotation.kept_hand)?;
        let source_action = match &annotation.source_recommended_action {
            MulliganChoice::Keep { .. } => "KEEP",
            MulliganChoice::Mulligan => "MULLIGAN",
        };
        let keep_wins = record.best_keep_value.total_wins()?;
        let mull_value = record
            .mull_again_value
            .as_ref()
            .map(|value| {
                value
                    .total_wins()
                    .map(|wins| format!("{wins}/{}", value.denominator))
            })
            .transpose()?
            .unwrap_or_else(|| "NA".to_owned());

        match &annotation.resolution {
            TeacherKeepResolution::Resolved(result) => println!(
                "SURVEY_RECORD\tworld={}\tstage={:?}\tsource_action={}\tr6_best_keep={}/{}\tr6_mull_again={}\tteacher=resolved\tteacher_wins={}/{}\tdisagreement_candidate={}\tgroups={}\tactions={}\tforced={}\ttruncated={}\tincomplete={}\tleaves={}\tsplits={}\tkept={}",
                sample.opening_world.0,
                sample.stage,
                source_action,
                keep_wins,
                record.best_keep_value.denominator,
                mull_value,
                result.score.total_wins,
                result.stats.sampled_worlds,
                matches!(
                    annotation.source_recommended_action,
                    MulliganChoice::Mulligan
                ) && result.score.total_wins > 0,
                result.stats.public_groups_evaluated,
                result.stats.public_actions_evaluated,
                result.stats.forced_public_steps,
                result.stats.truncated_public_groups,
                result.stats.incomplete_candidate_branches,
                result.stats.leaf_rollouts,
                result.stats.observation_splits,
                join_escaped(&kept_names)
            ),
            TeacherKeepResolution::Unresolved(reason) => println!(
                "SURVEY_RECORD\tworld={}\tstage={:?}\tsource_action={}\tr6_best_keep={}/{}\tr6_mull_again={}\tteacher=unresolved\treason={}\tdisagreement_candidate=false\tkept={}",
                sample.opening_world.0,
                sample.stage,
                source_action,
                keep_wins,
                record.best_keep_value.denominator,
                mull_value,
                unresolved_name(*reason),
                join_escaped(&kept_names)
            ),
        }
    }

    println!(
        "INTERPRETATION\tpositive_on_source_mull means only that the bounded teacher found a positive value for the R6-selected best keep package of an R6 MULL record; no teacher mull-again value exists in this survey"
    );
    Ok(())
}

fn stage_counts(counts: &[u32; 6]) -> String {
    MulliganStage::ALL
        .into_iter()
        .zip(counts)
        .map(|(stage, count)| format!("{stage:?}:{count}"))
        .collect::<Vec<_>>()
        .join("|")
}

fn card_names(
    interpretation: &InterpretationCatalog,
    cards: &[urza_core::CardDefId],
) -> Result<Vec<String>, Box<dyn Error>> {
    cards
        .iter()
        .map(|card| {
            interpretation
                .card(*card)
                .map(|metadata| metadata.deck_name.clone())
                .ok_or_else(|| format!("unknown card {} in teacher survey", card.0).into())
        })
        .collect()
}

fn join_escaped(values: &[String]) -> String {
    values
        .iter()
        .map(|value| escape(value))
        .collect::<Vec<_>>()
        .join("|")
}

fn escape(value: &str) -> String {
    value
        .replace('\\', "\\\\")
        .replace('|', "\\|")
        .replace('\t', "\\t")
        .replace('\n', "\\n")
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
