use std::collections::{BTreeMap, BTreeSet};
use std::error::Error;

use urza_cards::{CoverageStatus, CurrentCardDatabase, load_coverage, load_r1_catalog};
use urza_rules::R2CardRole;

const REGISTRY: &str = include_str!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../data/goldfish_model_gate.v1.tsv"
));

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
enum Disposition {
    Complete,
    GoldfishIrrelevant,
    EnvironmentDeferred,
    AuditRequired,
    ImplementationRequired,
    EnvironmentSplitRequired,
}

impl Disposition {
    fn parse(value: &str) -> Result<Self, String> {
        match value {
            "COMPLETE" => Ok(Self::Complete),
            "GOLDFISH_IRRELEVANT" => Ok(Self::GoldfishIrrelevant),
            "ENVIRONMENT_DEFERRED" => Ok(Self::EnvironmentDeferred),
            "AUDIT_REQUIRED" => Ok(Self::AuditRequired),
            "IMPLEMENTATION_REQUIRED" => Ok(Self::ImplementationRequired),
            "ENVIRONMENT_SPLIT_REQUIRED" => Ok(Self::EnvironmentSplitRequired),
            _ => Err(format!("unknown modeling disposition {value}")),
        }
    }

    fn as_str(self) -> &'static str {
        match self {
            Self::Complete => "COMPLETE",
            Self::GoldfishIrrelevant => "GOLDFISH_IRRELEVANT",
            Self::EnvironmentDeferred => "ENVIRONMENT_DEFERRED",
            Self::AuditRequired => "AUDIT_REQUIRED",
            Self::ImplementationRequired => "IMPLEMENTATION_REQUIRED",
            Self::EnvironmentSplitRequired => "ENVIRONMENT_SPLIT_REQUIRED",
        }
    }

    fn is_resolved(self) -> bool {
        matches!(
            self,
            Self::Complete | Self::GoldfishIrrelevant | Self::EnvironmentDeferred
        )
    }
}

#[derive(Debug, Clone)]
struct RegistryEntry {
    disposition: Disposition,
    rationale: String,
}

#[derive(Debug, Clone)]
struct AuditRow {
    card_name: String,
    disposition: Disposition,
    runtime_supported: bool,
    coverage: CoverageStatus,
    rationale: String,
}

#[derive(Debug)]
struct Audit {
    rows: Vec<AuditRow>,
}

impl Audit {
    fn count(&self, disposition: Disposition) -> usize {
        self.rows
            .iter()
            .filter(|row| row.disposition == disposition)
            .count()
    }

    fn resolved(&self) -> usize {
        self.rows
            .iter()
            .filter(|row| row.disposition.is_resolved())
            .count()
    }

    fn unresolved(&self) -> usize {
        self.rows.len() - self.resolved()
    }

    fn runtime_supported(&self) -> usize {
        self.rows.iter().filter(|row| row.runtime_supported).count()
    }
}

fn main() {
    if let Err(error) = run() {
        eprintln!("post-R7 modeling completeness gate failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn Error>> {
    let mode = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "--inventory".to_owned());
    let audit = inspect()?;

    match mode.as_str() {
        "--inventory" => {
            print_inventory(&audit);
            Ok(())
        }
        "--enforce" => {
            println!(
                "MODELING_COMPLETENESS_GATE\ttotal={}\tresolved={}\tunresolved={}",
                audit.rows.len(),
                audit.resolved(),
                audit.unresolved()
            );
            if audit.unresolved() == 0 {
                println!("MODELING_COMPLETENESS_GATE_GREEN");
                Ok(())
            } else {
                Err(format!(
                    "MODELING_COMPLETENESS_GATE_RED: {} unresolved active identities remain",
                    audit.unresolved()
                )
                .into())
            }
        }
        other => Err(format!("unknown mode {other}; expected --inventory or --enforce").into()),
    }
}

fn inspect() -> Result<Audit, Box<dyn Error>> {
    let registry = parse_registry()?;
    let catalog = load_r1_catalog()?;
    let coverage = load_coverage()?;
    let database = CurrentCardDatabase::load()?;

    let catalog_names = catalog
        .cards
        .iter()
        .map(|card| card.deck_name.clone())
        .collect::<BTreeSet<_>>();
    let registry_names = registry.keys().cloned().collect::<BTreeSet<_>>();

    if catalog.cards.len() != 95 {
        return Err(format!(
            "modeling gate expects the pinned 95-identity catalog, got {}",
            catalog.cards.len()
        )
        .into());
    }
    if registry_names != catalog_names {
        let missing = catalog_names
            .difference(&registry_names)
            .cloned()
            .collect::<Vec<_>>();
        let unknown = registry_names
            .difference(&catalog_names)
            .cloned()
            .collect::<Vec<_>>();
        return Err(format!(
            "modeling registry/catalog mismatch; missing={missing:?} unknown={unknown:?}"
        )
        .into());
    }

    let coverage_by_id = coverage
        .entries
        .iter()
        .map(|entry| (entry.card_id, entry.status))
        .collect::<BTreeMap<_, _>>();

    let mut rows = Vec::with_capacity(catalog.cards.len());
    for card in &catalog.cards {
        let entry = registry
            .get(&card.deck_name)
            .ok_or_else(|| format!("missing modeling entry for {}", card.deck_name))?;
        if entry.rationale.trim().is_empty() {
            return Err(format!("empty modeling rationale for {}", card.deck_name).into());
        }

        let profile = database
            .profile(card.card_def_id())
            .ok_or_else(|| format!("missing current database profile for {}", card.deck_name))?;
        let runtime_supported = profile.role != R2CardRole::Unsupported;
        let coverage_status = *coverage_by_id
            .get(&card.id)
            .ok_or_else(|| format!("missing coverage status for {}", card.deck_name))?;

        match entry.disposition {
            Disposition::Complete if !runtime_supported => {
                return Err(format!(
                    "{} is marked COMPLETE but has no runtime-supported rules role",
                    card.deck_name
                )
                .into());
            }
            Disposition::AuditRequired if !runtime_supported => {
                return Err(format!(
                    "{} is marked AUDIT_REQUIRED but is runtime-unsupported; use IMPLEMENTATION_REQUIRED or an audited exemption",
                    card.deck_name
                )
                .into());
            }
            Disposition::ImplementationRequired if runtime_supported => {
                return Err(format!(
                    "{} is marked IMPLEMENTATION_REQUIRED but is now runtime-supported; update the registry to AUDIT_REQUIRED or a resolved disposition",
                    card.deck_name
                )
                .into());
            }
            Disposition::EnvironmentSplitRequired
                if coverage_status != CoverageStatus::EnvironmentDeferred =>
            {
                return Err(format!(
                    "{} is marked ENVIRONMENT_SPLIT_REQUIRED but coverage is {:?}",
                    card.deck_name, coverage_status
                )
                .into());
            }
            _ => {}
        }

        rows.push(AuditRow {
            card_name: card.deck_name.clone(),
            disposition: entry.disposition,
            runtime_supported,
            coverage: coverage_status,
            rationale: entry.rationale.clone(),
        });
    }

    Ok(Audit { rows })
}

fn parse_registry() -> Result<BTreeMap<String, RegistryEntry>, Box<dyn Error>> {
    let mut lines = REGISTRY.lines();
    let header = lines.next().ok_or("empty modeling registry")?;
    if header != "card_name\tdisposition\trationale" {
        return Err(format!("unexpected modeling registry header {header:?}").into());
    }

    let mut entries = BTreeMap::new();
    for (offset, line) in lines.enumerate() {
        if line.trim().is_empty() {
            continue;
        }
        let line_number = offset + 2;
        let mut parts = line.splitn(3, '\t');
        let card_name = parts
            .next()
            .ok_or_else(|| format!("missing card name on registry line {line_number}"))?;
        let disposition = parts
            .next()
            .ok_or_else(|| format!("missing disposition on registry line {line_number}"))?;
        let rationale = parts
            .next()
            .ok_or_else(|| format!("missing rationale on registry line {line_number}"))?;

        if card_name.trim().is_empty() || rationale.trim().is_empty() {
            return Err(format!("blank field on modeling registry line {line_number}").into());
        }
        let entry = RegistryEntry {
            disposition: Disposition::parse(disposition)?,
            rationale: rationale.to_owned(),
        };
        if entries.insert(card_name.to_owned(), entry).is_some() {
            return Err(format!("duplicate modeling registry entry for {card_name}").into());
        }
    }
    Ok(entries)
}

fn print_inventory(audit: &Audit) {
    let state = if audit.unresolved() == 0 {
        "GREEN"
    } else {
        "RED"
    };
    println!("# Post-R7 modeling completeness gate result");
    println!();
    println!("- Gate state: **{state}**");
    println!("- Active catalog identities: **{}**", audit.rows.len());
    println!(
        "- Current runtime-supported identities: **{}**",
        audit.runtime_supported()
    );
    println!("- Resolved dispositions: **{}**", audit.resolved());
    println!("- Unresolved dispositions: **{}**", audit.unresolved());
    println!(
        "- `AUDIT_REQUIRED`: **{}**",
        audit.count(Disposition::AuditRequired)
    );
    println!(
        "- `IMPLEMENTATION_REQUIRED`: **{}**",
        audit.count(Disposition::ImplementationRequired)
    );
    println!(
        "- `ENVIRONMENT_SPLIT_REQUIRED`: **{}**",
        audit.count(Disposition::EnvironmentSplitRequired)
    );
    println!("- `COMPLETE`: **{}**", audit.count(Disposition::Complete));
    println!(
        "- `GOLDFISH_IRRELEVANT`: **{}**",
        audit.count(Disposition::GoldfishIrrelevant)
    );
    println!(
        "- `ENVIRONMENT_DEFERRED`: **{}**",
        audit.count(Disposition::EnvironmentDeferred)
    );
    println!();
    println!(
        "The gate remains RED until every active identity is explicitly resolved as `COMPLETE`, `GOLDFISH_IRRELEVANT`, or `ENVIRONMENT_DEFERRED`. Historical coverage labels do not bypass this gate."
    );
    println!();
    println!("## Unresolved identities");
    println!();
    println!("| Card | Disposition | Runtime supported | Coverage | Rationale |");
    println!("| --- | --- | --- | --- | --- |");
    for row in audit
        .rows
        .iter()
        .filter(|row| !row.disposition.is_resolved())
    {
        println!(
            "| {} | `{}` | {} | `{:?}` | {} |",
            escape_markdown(&row.card_name),
            row.disposition.as_str(),
            row.runtime_supported,
            row.coverage,
            escape_markdown(&row.rationale)
        );
    }

    let resolved = audit
        .rows
        .iter()
        .filter(|row| row.disposition.is_resolved())
        .collect::<Vec<_>>();
    if !resolved.is_empty() {
        println!();
        println!("## Resolved identities");
        println!();
        println!("| Card | Disposition | Runtime supported | Coverage | Rationale |");
        println!("| --- | --- | --- | --- | --- |");
        for row in resolved {
            println!(
                "| {} | `{}` | {} | `{:?}` | {} |",
                escape_markdown(&row.card_name),
                row.disposition.as_str(),
                row.runtime_supported,
                row.coverage,
                escape_markdown(&row.rationale)
            );
        }
    }
}

fn escape_markdown(value: &str) -> String {
    value.replace('|', "\\|")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn v1_registry_is_total_and_backlog_is_explicit() {
        let audit = inspect().unwrap();
        assert_eq!(audit.rows.len(), 95);
        assert_eq!(audit.count(Disposition::AuditRequired), 46);
        assert_eq!(audit.count(Disposition::ImplementationRequired), 42);
        assert_eq!(audit.count(Disposition::EnvironmentSplitRequired), 3);
        assert_eq!(audit.count(Disposition::Complete), 4);
        assert_eq!(audit.resolved(), 4);
        assert_eq!(audit.unresolved(), 91);
    }
}
