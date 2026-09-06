use std::error::Error;
use std::fmt::Write as _;

use urza_mulligan::{
    DISTANCE_AXIS_NAMES, InterpretationCatalog, MulliganChoice, MulliganStage, build_corpus_review,
    feature_axis_ranges_with_names, generate_evaluated_hand_corpus, normalize_hand_features,
    r7_pilot_generation_config, r7_smoke_generation_config, r7_teacher_generation_config,
};

const REVIEW_RADII: [u32; 7] = [0, 300, 600, 900, 1_200, 1_800, 2_400];
const DEFAULT_REVIEW_RADIUS: u32 = 900;
const TEACHER_REVIEW_RADIUS: u32 = 600;
const TOP_CARD_LIMIT: usize = 8;

fn main() {
    if let Err(error) = run() {
        eprintln!("r7-corpus failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn Error>> {
    let profile = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "smoke".to_owned());
    let (config, selected_review_radius) = match profile.as_str() {
        "smoke" => (r7_smoke_generation_config(), DEFAULT_REVIEW_RADIUS),
        "pilot" => (r7_pilot_generation_config(), DEFAULT_REVIEW_RADIUS),
        "teacher" => (r7_teacher_generation_config(), TEACHER_REVIEW_RADIUS),
        _ => {
            return Err(format!("usage: r7-corpus [smoke|pilot|teacher], got {profile:?}").into());
        }
    };

    let generated = generate_evaluated_hand_corpus(&config)?;
    let interpretation = InterpretationCatalog::load()?;
    let review = build_corpus_review(
        &generated.corpus,
        &interpretation,
        &REVIEW_RADII,
        selected_review_radius,
        TOP_CARD_LIMIT,
    )?;

    println!("R7_CORPUS\t{}", generated.provenance.generator_version);
    println!("PROFILE\t{}", generated.provenance.profile_version);
    println!("CORPUS_VERSION\t{}", generated.provenance.corpus_version);
    println!("DECK_VERSION\t{}", generated.provenance.deck_version);
    println!("RNG_SCHEME\t{}", generated.provenance.rng_scheme_version);
    println!("POLICY_VERSION\t{}", generated.provenance.policy_version);
    println!(
        "DECISION_VERSION\t{}",
        generated.provenance.decision_version
    );
    println!(
        "OBJECTIVE_VERSION\t{}",
        generated.provenance.objective_version
    );
    println!("HORIZON\t{}", generated.provenance.horizon);
    println!(
        "KEEP_FLOOR\t{}",
        generated.provenance.experimental_keep_floor
    );
    println!(
        "OPENING_ROOT\t{}",
        root_hex(generated.provenance.opening_root.0)
    );
    println!("FIRST_WORLD\t{}", generated.provenance.first_world.0);
    println!("WORLD_COUNT\t{}", generated.provenance.world_count);
    println!(
        "R5_ROLLOUT\troot={}\tfirst_world={}\tsamples={}\tmax_steps={}",
        root_hex(generated.provenance.evaluation.rollout.root.0),
        generated.provenance.evaluation.rollout.first_world.0,
        generated.provenance.evaluation.rollout.samples,
        generated.provenance.evaluation.rollout.rollout_max_steps
    );
    println!(
        "R6_CONTINUATION\troot={}\tfirst_world={}\tfuture_hand_samples={}",
        root_hex(generated.provenance.evaluation.continuation_root.0),
        generated.provenance.evaluation.first_future_world.0,
        generated.provenance.evaluation.future_hand_samples
    );
    println!(
        "STATS\tworlds={}\tdecisions={}\tkeep={}\tmull={}\tcache_hits={}\tcache_misses={}",
        generated.stats.worlds_completed,
        generated.stats.evaluated_decisions,
        generated.stats.keep_decisions,
        generated.stats.mulligan_decisions,
        generated.stats.continuation_cache_hits,
        generated.stats.continuation_cache_misses
    );
    println!(
        "STAGE_POPULATIONS\t{}",
        stage_counts(&review.stage_populations)
    );

    for (sample, record) in generated.corpus.entries() {
        let normalized = normalize_hand_features(&record.current_features)?;
        let action = match &record.recommended_action {
            MulliganChoice::Keep { bottom_indices } => {
                format!("KEEP:{}", join_usize(bottom_indices))
            }
            MulliganChoice::Mulligan => "MULLIGAN".to_owned(),
        };
        let current_names = card_names(&interpretation, &record.current_seven)?;
        let kept_names = card_names(&interpretation, &record.recommended_kept_hand)?;
        let total_wins = record.best_keep_value.total_wins()?;
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
        println!(
            "RECORD\tworld={}\tstage={:?}\tseat={}\tcaverns={}\taction={}\tbest_keep={}/{}\tmull_again={}\tcurrent={}\tkept={}\tfeatures={}",
            sample.opening_world.0,
            sample.stage,
            record.pregame.seat,
            record.pregame.gemstone_caverns_eligible,
            action,
            total_wins,
            record.best_keep_value.denominator,
            mull_value,
            join_escaped(&current_names),
            join_escaped(&kept_names),
            join_u16(&normalized.per_card_milli)
        );
    }

    for point in &review.radius_sweep {
        println!(
            "RADIUS\tr={}\tclusters={}\tsingletons={}\tlargest={}\tstage_clusters={}",
            point.radius_l1_milli,
            point.cluster_count,
            point.singleton_count,
            point.largest_cluster,
            stage_counts(&point.stage_cluster_counts)
        );
    }

    println!("SELECTED_RADIUS\t{}", review.selected_radius_l1_milli);
    for cluster in &review.clusters {
        let medoid_names: Vec<_> = cluster
            .medoid_cards
            .iter()
            .map(|card| card.deck_name.clone())
            .collect();
        let top_cards: Vec<_> = cluster
            .top_cards
            .iter()
            .map(|card| {
                format!(
                    "{}:{}copies:{}hands",
                    escape(&card.deck_name),
                    card.copies_across_hands,
                    card.hands_containing
                )
            })
            .collect();
        let ranges: Vec<_> = feature_axis_ranges_with_names(cluster)
            .map(|(name, range)| format!("{name}:{}-{}", range.min_milli, range.max_milli))
            .collect();
        println!(
            "CLUSTER\tid={}\tstage={:?}\tmembers={}\tkeep={}\tmull={}\tmax_medoid_distance={}\tmedoid_world={}\tmedoid={}\ttop_cards={}\tfeature_ranges={}\tseats={:?}\tcaverns_members={}",
            cluster.cluster.cluster_ordinal,
            cluster.cluster.stage,
            cluster.cluster.member_count,
            cluster.cluster.keep_recommendations,
            cluster.cluster.mulligan_recommendations,
            cluster.cluster.max_distance_to_medoid.l1_milli,
            cluster.cluster.medoid.opening_world.0,
            join_escaped(&medoid_names),
            top_cards.join("|"),
            ranges.join("|"),
            cluster.seat_counts,
            cluster.caverns_eligible_members
        );
    }

    println!("FEATURE_AXES\t{}", DISTANCE_AXIS_NAMES.join("|"));
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
                .ok_or_else(|| format!("unknown card {} in generated corpus", card.0).into())
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

fn join_usize(values: &[usize]) -> String {
    values
        .iter()
        .map(usize::to_string)
        .collect::<Vec<_>>()
        .join(",")
}

fn join_u16<const N: usize>(values: &[u16; N]) -> String {
    values
        .iter()
        .map(u16::to_string)
        .collect::<Vec<_>>()
        .join(",")
}

fn escape(value: &str) -> String {
    value
        .replace('\\', "\\\\")
        .replace('|', "\\|")
        .replace('\t', "\\t")
        .replace('\n', "\\n")
}

fn root_hex(bytes: [u8; 32]) -> String {
    let mut output = String::with_capacity(64);
    for byte in bytes {
        write!(&mut output, "{byte:02x}").expect("write to string");
    }
    output
}
