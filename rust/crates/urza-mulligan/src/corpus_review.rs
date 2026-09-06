use std::collections::{BTreeMap, BTreeSet};
use std::error::Error;
use std::fmt;

use urza_core::CardDefId;

use crate::{
    CorpusError, DISTANCE_AXIS_COUNT, DISTANCE_AXIS_NAMES, EvaluatedHandCorpus,
    EvaluatedHandSampleId, FeatureDistance, InterpretationCatalog, MulliganStage,
    NormalizedHandFeatures, UnlabeledClusterSummary, UnlabeledGroupingConfig,
    hand_feature_distance, normalize_hand_features,
};

pub const RADIUS_SWEEP_VERSION: &str = "r7_radius_sweep_v1";
pub const CLUSTER_REVIEW_VERSION: &str = "r7_cluster_content_review_v1";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RadiusSweepPoint {
    pub radius_l1_milli: u32,
    pub cluster_count: u32,
    pub singleton_count: u32,
    pub largest_cluster: u32,
    pub stage_cluster_counts: [u32; 6],
}

pub fn sweep_grouping_radii(
    corpus: &EvaluatedHandCorpus,
    radii: &[u32],
) -> Result<Vec<RadiusSweepPoint>, CorpusReviewError> {
    let mut output = Vec::with_capacity(radii.len());
    for radius in radii {
        let clusters = corpus.unlabeled_clusters(UnlabeledGroupingConfig {
            max_l1_milli: *radius,
        })?;
        let mut point = RadiusSweepPoint {
            radius_l1_milli: *radius,
            cluster_count: u32::try_from(clusters.len())
                .map_err(|_| CorpusReviewError::CountOverflow("cluster count"))?,
            singleton_count: 0,
            largest_cluster: 0,
            stage_cluster_counts: [0; 6],
        };
        for cluster in &clusters {
            point.largest_cluster = point.largest_cluster.max(cluster.member_count);
            point.singleton_count += u32::from(cluster.member_count == 1);
            let index = stage_index(cluster.stage);
            point.stage_cluster_counts[index] = point.stage_cluster_counts[index]
                .checked_add(1)
                .ok_or(CorpusReviewError::CountOverflow("stage cluster count"))?;
        }
        output.push(point);
    }
    Ok(output)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct FeatureRange {
    pub min_milli: u16,
    pub max_milli: u16,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ReviewedCard {
    pub card: CardDefId,
    pub deck_name: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ClusterCardFrequency {
    pub card: CardDefId,
    pub deck_name: String,
    pub copies_across_hands: u32,
    pub hands_containing: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UnlabeledClusterReview {
    pub review_version: &'static str,
    pub cluster: UnlabeledClusterSummary,
    pub medoid_cards: Vec<ReviewedCard>,
    pub feature_ranges: [FeatureRange; DISTANCE_AXIS_COUNT],
    pub top_cards: Vec<ClusterCardFrequency>,
    pub seat_counts: [u32; 4],
    pub caverns_eligible_members: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CorpusReviewReport {
    pub review_version: &'static str,
    pub radius_sweep_version: &'static str,
    pub corpus_entries: u32,
    pub stage_populations: [u32; 6],
    pub radius_sweep: Vec<RadiusSweepPoint>,
    pub selected_radius_l1_milli: u32,
    pub clusters: Vec<UnlabeledClusterReview>,
}

pub fn build_corpus_review(
    corpus: &EvaluatedHandCorpus,
    interpretation: &InterpretationCatalog,
    radii: &[u32],
    selected_radius_l1_milli: u32,
    top_card_limit: usize,
) -> Result<CorpusReviewReport, CorpusReviewError> {
    let radius_sweep = sweep_grouping_radii(corpus, radii)?;
    let clusters = corpus.unlabeled_clusters(UnlabeledGroupingConfig {
        max_l1_milli: selected_radius_l1_milli,
    })?;
    let mut reviewed = Vec::with_capacity(clusters.len());
    for cluster in clusters {
        reviewed.push(review_cluster(
            corpus,
            interpretation,
            cluster,
            top_card_limit,
        )?);
    }

    let mut stage_populations = [0_u32; 6];
    for (_, record) in corpus.entries() {
        let index = stage_index(record.stage);
        stage_populations[index] = stage_populations[index]
            .checked_add(1)
            .ok_or(CorpusReviewError::CountOverflow("stage population"))?;
    }

    Ok(CorpusReviewReport {
        review_version: CLUSTER_REVIEW_VERSION,
        radius_sweep_version: RADIUS_SWEEP_VERSION,
        corpus_entries: u32::try_from(corpus.len())
            .map_err(|_| CorpusReviewError::CountOverflow("corpus entries"))?,
        stage_populations,
        radius_sweep,
        selected_radius_l1_milli,
        clusters: reviewed,
    })
}

fn review_cluster(
    corpus: &EvaluatedHandCorpus,
    interpretation: &InterpretationCatalog,
    cluster: UnlabeledClusterSummary,
    top_card_limit: usize,
) -> Result<UnlabeledClusterReview, CorpusReviewError> {
    let mut feature_ranges = [FeatureRange {
        min_milli: u16::MAX,
        max_milli: 0,
    }; DISTANCE_AXIS_COUNT];
    let mut copy_counts: BTreeMap<CardDefId, u32> = BTreeMap::new();
    let mut hand_counts: BTreeMap<CardDefId, u32> = BTreeMap::new();
    let mut seat_counts = [0_u32; 4];
    let mut caverns_eligible_members = 0_u32;

    for sample in &cluster.members {
        let record = corpus
            .get(*sample)
            .ok_or(CorpusReviewError::MissingSample(*sample))?;
        let normalized = normalize_hand_features(&record.current_features)?;
        update_ranges(&mut feature_ranges, normalized);

        let seat_index = usize::from(record.pregame.seat.saturating_sub(1));
        if seat_index >= seat_counts.len() {
            return Err(CorpusReviewError::InvalidSeat(record.pregame.seat));
        }
        seat_counts[seat_index] = seat_counts[seat_index]
            .checked_add(1)
            .ok_or(CorpusReviewError::CountOverflow("seat count"))?;
        caverns_eligible_members = caverns_eligible_members
            .checked_add(u32::from(record.pregame.gemstone_caverns_eligible))
            .ok_or(CorpusReviewError::CountOverflow("Caverns count"))?;

        let mut seen_in_hand = BTreeSet::new();
        for card in &record.current_seven {
            let copies = copy_counts.entry(*card).or_default();
            *copies = copies
                .checked_add(1)
                .ok_or(CorpusReviewError::CountOverflow("card copy count"))?;
            seen_in_hand.insert(*card);
        }
        for card in seen_in_hand {
            let hands = hand_counts.entry(card).or_default();
            *hands = hands
                .checked_add(1)
                .ok_or(CorpusReviewError::CountOverflow("card hand count"))?;
        }
    }

    let medoid_record = corpus
        .get(cluster.medoid)
        .ok_or(CorpusReviewError::MissingSample(cluster.medoid))?;
    let mut medoid_cards = Vec::with_capacity(medoid_record.current_seven.len());
    for card in &medoid_record.current_seven {
        medoid_cards.push(reviewed_card(interpretation, *card)?);
    }
    medoid_cards.sort_by_key(|card| card.card);

    let mut top_cards = Vec::with_capacity(copy_counts.len());
    for (card, copies_across_hands) in copy_counts {
        let metadata = interpretation
            .card(card)
            .ok_or(CorpusReviewError::UnknownCard(card))?;
        top_cards.push(ClusterCardFrequency {
            card,
            deck_name: metadata.deck_name.clone(),
            copies_across_hands,
            hands_containing: *hand_counts.get(&card).unwrap_or(&0),
        });
    }
    top_cards.sort_by(|left, right| {
        right
            .copies_across_hands
            .cmp(&left.copies_across_hands)
            .then_with(|| right.hands_containing.cmp(&left.hands_containing))
            .then_with(|| left.card.cmp(&right.card))
    });
    top_cards.truncate(top_card_limit);

    Ok(UnlabeledClusterReview {
        review_version: CLUSTER_REVIEW_VERSION,
        cluster,
        medoid_cards,
        feature_ranges,
        top_cards,
        seat_counts,
        caverns_eligible_members,
    })
}

fn reviewed_card(
    interpretation: &InterpretationCatalog,
    card: CardDefId,
) -> Result<ReviewedCard, CorpusReviewError> {
    let metadata = interpretation
        .card(card)
        .ok_or(CorpusReviewError::UnknownCard(card))?;
    Ok(ReviewedCard {
        card,
        deck_name: metadata.deck_name.clone(),
    })
}

fn update_ranges(
    ranges: &mut [FeatureRange; DISTANCE_AXIS_COUNT],
    normalized: NormalizedHandFeatures,
) {
    for (range, value) in ranges.iter_mut().zip(normalized.per_card_milli) {
        range.min_milli = range.min_milli.min(value);
        range.max_milli = range.max_milli.max(value);
    }
}

pub fn cluster_medoid_distance_sum(
    corpus: &EvaluatedHandCorpus,
    cluster: &UnlabeledClusterSummary,
) -> Result<u64, CorpusReviewError> {
    let medoid = corpus
        .get(cluster.medoid)
        .ok_or(CorpusReviewError::MissingSample(cluster.medoid))?;
    let medoid_features = normalize_hand_features(&medoid.current_features)?;
    cluster.members.iter().try_fold(0_u64, |total, sample| {
        let record = corpus
            .get(*sample)
            .ok_or(CorpusReviewError::MissingSample(*sample))?;
        let features = normalize_hand_features(&record.current_features)?;
        total
            .checked_add(u64::from(
                hand_feature_distance(medoid_features, features).l1_milli,
            ))
            .ok_or(CorpusReviewError::CountOverflow("medoid distance sum"))
    })
}

pub fn feature_axis_ranges_with_names(
    review: &UnlabeledClusterReview,
) -> impl Iterator<Item = (&'static str, FeatureRange)> + '_ {
    DISTANCE_AXIS_NAMES
        .into_iter()
        .zip(review.feature_ranges.iter().copied())
}

const fn stage_index(stage: MulliganStage) -> usize {
    match stage {
        MulliganStage::InitialSeven => 0,
        MulliganStage::FreeSeven => 1,
        MulliganStage::Six => 2,
        MulliganStage::Five => 3,
        MulliganStage::Four => 4,
        MulliganStage::Three => 5,
    }
}

#[derive(Debug)]
pub enum CorpusReviewError {
    Corpus(CorpusError),
    MissingSample(EvaluatedHandSampleId),
    UnknownCard(CardDefId),
    InvalidSeat(u8),
    CountOverflow(&'static str),
}

impl fmt::Display for CorpusReviewError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Corpus(error) => write!(formatter, "R7 corpus review failed: {error}"),
            Self::MissingSample(sample) => {
                write!(
                    formatter,
                    "cluster references missing corpus sample {sample:?}"
                )
            }
            Self::UnknownCard(card) => write!(
                formatter,
                "review card {} is not in interpretation catalog",
                card.0
            ),
            Self::InvalidSeat(seat) => write!(formatter, "pregame seat {seat} is outside 1..=4"),
            Self::CountOverflow(context) => {
                write!(formatter, "R7 review count overflow: {context}")
            }
        }
    }
}

impl Error for CorpusReviewError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            Self::Corpus(error) => Some(error),
            _ => None,
        }
    }
}

impl From<CorpusError> for CorpusReviewError {
    fn from(value: CorpusError) -> Self {
        Self::Corpus(value)
    }
}

#[cfg(test)]
mod tests {
    use urza_cards::R4CardDatabase;
    use urza_rng::{RootSeed, WorldId};

    use super::*;
    use crate::{
        EVALUATED_HAND_RECORD_VERSION, EvaluatedHandRecord, ExactWinRate,
        HAND_FEATURE_SCHEMA_VERSION, INTERPRETATION_ONLY_CONTRACT, INTERPRETATION_ROLE_VERSION,
        MULLIGAN_REPORT_VERSION, MulliganChoice, ObjectivePreference, PregameContext,
        SampledDecisionConfidence,
    };

    fn record(
        interpretation: &InterpretationCatalog,
        cards: Vec<CardDefId>,
        world: u64,
    ) -> (EvaluatedHandSampleId, EvaluatedHandRecord) {
        let features = interpretation.features_for_cards(&cards).unwrap();
        let value = ExactWinRate {
            denominator: 1,
            t1_through_t6: [0; 6],
            losses: 1,
        };
        (
            EvaluatedHandSampleId::new(
                RootSeed::from_u64(5),
                WorldId(world),
                MulliganStage::InitialSeven,
            ),
            EvaluatedHandRecord {
                record_version: EVALUATED_HAND_RECORD_VERSION,
                role_metadata_version: INTERPRETATION_ROLE_VERSION,
                feature_schema_version: HAND_FEATURE_SCHEMA_VERSION,
                interpretation_contract: INTERPRETATION_ONLY_CONTRACT,
                source_report_version: MULLIGAN_REPORT_VERSION,
                stage: MulliganStage::InitialSeven,
                mulligan_depth: 0,
                pregame: PregameContext {
                    seat: u8::try_from(world % 4 + 1).unwrap(),
                    gemstone_caverns_eligible: world % 4 != 0,
                },
                policy_version: "review-test-policy",
                horizon: 6,
                environment_version: "review-test".to_owned(),
                current_seven: cards.clone(),
                current_features: features,
                recommended_kept_hand: cards,
                recommended_keep_features: features,
                recommended_action: MulliganChoice::Keep {
                    bottom_indices: Vec::new(),
                },
                best_keep_value: value.clone(),
                mull_again_value: Some(value),
                objective_preference: ObjectivePreference::Equal,
                primary_win_rate_gap: None,
                sampled_decision_confidence: SampledDecisionConfidence::ExactSampleTie,
            },
        )
    }

    #[test]
    fn radius_sweep_reports_fragmentation_and_stage_counts() {
        let interpretation = InterpretationCatalog::load().unwrap();
        let cards = R4CardDatabase::load().unwrap();
        let island = cards.card_id_by_name("Island").unwrap();
        let tomb = cards.card_id_by_name("Ancient Tomb").unwrap();
        let pact = cards.card_id_by_name("Pact of Negation").unwrap();
        let mut near = vec![island; 6];
        near.push(tomb);

        let mut corpus = EvaluatedHandCorpus::new();
        for (sample, record) in [
            record(&interpretation, vec![island; 7], 0),
            record(&interpretation, near, 1),
            record(&interpretation, vec![pact; 7], 2),
        ] {
            corpus
                .insert_record(sample, record, &interpretation)
                .unwrap();
        }

        let sweep = sweep_grouping_radii(&corpus, &[0, 300]).unwrap();
        assert_eq!(sweep[0].cluster_count, 3);
        assert_eq!(sweep[0].singleton_count, 3);
        assert_eq!(sweep[1].cluster_count, 2);
        assert_eq!(sweep[1].largest_cluster, 2);
        assert_eq!(sweep[1].stage_cluster_counts[0], 2);
    }

    #[test]
    fn cluster_review_exposes_medoid_cards_ranges_and_frequencies_without_labels() {
        let interpretation = InterpretationCatalog::load().unwrap();
        let cards = R4CardDatabase::load().unwrap();
        let island = cards.card_id_by_name("Island").unwrap();
        let tomb = cards.card_id_by_name("Ancient Tomb").unwrap();
        let mut near = vec![island; 6];
        near.push(tomb);

        let mut corpus = EvaluatedHandCorpus::new();
        for (sample, record) in [
            record(&interpretation, vec![island; 7], 0),
            record(&interpretation, near, 1),
        ] {
            corpus
                .insert_record(sample, record, &interpretation)
                .unwrap();
        }

        let review = build_corpus_review(&corpus, &interpretation, &[0, 300], 300, 5).unwrap();
        assert_eq!(review.corpus_entries, 2);
        assert_eq!(review.clusters.len(), 1);
        let cluster = &review.clusters[0];
        assert_eq!(cluster.review_version, CLUSTER_REVIEW_VERSION);
        assert_eq!(cluster.cluster.member_count, 2);
        assert!(
            cluster
                .medoid_cards
                .iter()
                .all(|card| !card.deck_name.is_empty())
        );
        assert_eq!(cluster.top_cards[0].deck_name, "Island");
        assert_eq!(cluster.top_cards[0].copies_across_hands, 13);
        assert_eq!(cluster.top_cards[0].hands_containing, 2);
        assert!(cluster.feature_ranges[0].min_milli <= cluster.feature_ranges[0].max_milli);
        assert_eq!(
            cluster_medoid_distance_sum(&corpus, &cluster.cluster).unwrap(),
            286
        );
        assert_eq!(
            feature_axis_ranges_with_names(cluster).count(),
            DISTANCE_AXIS_COUNT
        );
    }
}
