#![forbid(unsafe_code)]

use serde::Deserialize;

const HUMAN_HANDS_JSON: &str = include_str!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../../benchmarks/human/human_mulligan_exact_hands.json"
));

#[derive(Debug, Clone, Deserialize, PartialEq, Eq)]
pub struct HumanHandFixture {
    pub hand_id: u16,
    pub mulligan_count: u8,
    pub keep_size: u8,
    pub drawn_seven: Vec<String>,
    pub cards_bottomed: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct HumanHandsFile {
    hands: Vec<HumanHandFixture>,
}

pub fn hand25_fixture() -> Result<HumanHandFixture, serde_json::Error> {
    let file: HumanHandsFile = serde_json::from_str(HUMAN_HANDS_JSON)?;
    Ok(file
        .hands
        .into_iter()
        .find(|hand| hand.hand_id == 25)
        .expect("audited human benchmark must contain Hand 25"))
}

#[cfg(test)]
mod tests {
    use super::hand25_fixture;

    #[test]
    fn hand25_reference_fixture_matches_audited_pathology() {
        let hand = hand25_fixture().unwrap();
        assert_eq!(hand.mulligan_count, 2);
        assert_eq!(hand.keep_size, 6);
        assert_eq!(
            hand.drawn_seven,
            vec![
                "Hydroelectric Specimen",
                "Minamo, School at Water's Edge",
                "Whir of Invention",
                "Sapphire Medallion",
                "Uthros Research Craft",
                "Voltaic Key",
                "Island",
            ]
        );
    }
}
