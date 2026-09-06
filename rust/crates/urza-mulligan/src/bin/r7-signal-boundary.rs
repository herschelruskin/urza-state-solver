use std::error::Error;

use urza_mulligan::{
    R7_SIGNAL_BOUNDARY_FIRST_WORLD, R7_SIGNAL_BOUNDARY_R5_SAMPLES,
    R7_SIGNAL_BOUNDARY_TEACHER_CANDIDATES, R7_SIGNAL_BOUNDARY_TEACHER_SAMPLES,
    R7_SIGNAL_BOUNDARY_TEACHER_STEPS, SignalBoundaryProbe, SignalBoundaryTier,
    run_signal_boundary,
};
use urza_rules::WinFamily;

fn main() {
    if let Err(error) = run() {
        eprintln!("r7-signal-boundary failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn Error>> {
    let report = run_signal_boundary()?;
    println!("R7_SIGNAL_BOUNDARY\t{}", report.version);
    println!("STATE_VERSION\t{}", report.state_version);
    println!("BOUNDARY\t{}", report.boundary);
    println!(
        "BUDGET\tfirst_world={}\tr5_samples={}\tteacher_samples={}\tteacher_steps={}\tteacher_candidates={}\tteacher_depths=0,1,2",
        R7_SIGNAL_BOUNDARY_FIRST_WORLD.0,
        R7_SIGNAL_BOUNDARY_R5_SAMPLES,
        R7_SIGNAL_BOUNDARY_TEACHER_SAMPLES,
        R7_SIGNAL_BOUNDARY_TEACHER_STEPS,
        R7_SIGNAL_BOUNDARY_TEACHER_CANDIDATES
    );

    for probe in &report.probes {
        let d0 = probe
            .teacher_at_depth(0)
            .ok_or("missing teacher depth-zero probe")?;
        let d1 = probe
            .teacher_at_depth(1)
            .ok_or("missing teacher depth-one probe")?;
        let d2 = probe
            .teacher_at_depth(2)
            .ok_or("missing teacher depth-two probe")?;
        println!(
            "BOUNDARY_ROW\tcase={}\tfamily={}\ttier={}\tentry_terminal={}\tunsupported={}\thand={}\tbattlefield={}\tstack={}\tr5={}/{}\tteacher_d0={}/{}\tteacher_d1={}/{}\tteacher_d2={}/{}\td0_groups={}\td1_groups={}\td2_groups={}\td0_actions={}\td1_actions={}\td2_actions={}\td0_truncated={}\td1_truncated={}\td2_truncated={}\td0_incomplete={}\td1_incomplete={}\td2_incomplete={}",
            probe.case_name,
            probe.family.label(),
            probe.tier.label(),
            probe.entry_terminal.map_or("none", WinFamily::label),
            probe.unsupported_involved_cards,
            probe.hand_cards,
            probe.battlefield_permanents,
            probe.stack_objects,
            probe.r5_wins,
            probe.r5_samples,
            d0.score.total_wins,
            d0.stats.sampled_worlds,
            d1.score.total_wins,
            d1.stats.sampled_worlds,
            d2.score.total_wins,
            d2.stats.sampled_worlds,
            d0.stats.public_groups_evaluated,
            d1.stats.public_groups_evaluated,
            d2.stats.public_groups_evaluated,
            d0.stats.public_actions_evaluated,
            d1.stats.public_actions_evaluated,
            d2.stats.public_actions_evaluated,
            d0.stats.truncated_public_groups,
            d1.stats.truncated_public_groups,
            d2.stats.truncated_public_groups,
            d0.stats.incomplete_candidate_branches,
            d1.stats.incomplete_candidate_branches,
            d2.stats.incomplete_candidate_branches
        );
    }

    for family in [
        WinFamily::PowerArtifactBasalt,
        WinFamily::BasaltGadgeteer,
        WinFamily::TopRealityChip,
    ] {
        let family_probes: Vec<_> = report
            .probes
            .iter()
            .filter(|probe| probe.family == family)
            .collect();
        println!(
            "BOUNDARY_SUMMARY\tfamily={}\tr5_first_zero={}\tteacher_d0_first_zero={}\tteacher_d1_first_zero={}\tteacher_d2_first_zero={}\tr5_pattern={}\td0_pattern={}\td1_pattern={}\td2_pattern={}",
            family.label(),
            first_zero_tier(&family_probes, ProbeChannel::R5),
            first_zero_tier(&family_probes, ProbeChannel::Teacher(0)),
            first_zero_tier(&family_probes, ProbeChannel::Teacher(1)),
            first_zero_tier(&family_probes, ProbeChannel::Teacher(2)),
            signal_pattern(&family_probes, ProbeChannel::R5),
            signal_pattern(&family_probes, ProbeChannel::Teacher(0)),
            signal_pattern(&family_probes, ProbeChannel::Teacher(1)),
            signal_pattern(&family_probes, ProbeChannel::Teacher(2))
        );
    }

    println!(
        "INTERPRETATION\tfirst_zero is the first observed zero after ordering terminal-witness -> stack-resolution -> one-card-in-hand -> two-cards-in-hand; synthetic mana is intentionally abundant, so this slice isolates action-selection/search distance before resource acquisition realism"
    );
    Ok(())
}

#[derive(Debug, Clone, Copy)]
enum ProbeChannel {
    R5,
    Teacher(u8),
}

fn has_signal(probe: &SignalBoundaryProbe, channel: ProbeChannel) -> bool {
    match channel {
        ProbeChannel::R5 => probe.r5_wins > 0,
        ProbeChannel::Teacher(depth) => probe
            .teacher_at_depth(depth)
            .is_some_and(|result| result.score.total_wins > 0),
    }
}

fn first_zero_tier(probes: &[&SignalBoundaryProbe], channel: ProbeChannel) -> &'static str {
    probes
        .iter()
        .find(|probe| !has_signal(probe, channel))
        .map_or("none", |probe| probe.tier.label())
}

fn signal_pattern(probes: &[&SignalBoundaryProbe], channel: ProbeChannel) -> String {
    SignalBoundaryTier::ALL
        .into_iter()
        .map(|tier| {
            probes
                .iter()
                .find(|probe| probe.tier == tier)
                .map_or('?', |probe| if has_signal(probe, channel) { '+' } else { '0' })
        })
        .collect()
}
