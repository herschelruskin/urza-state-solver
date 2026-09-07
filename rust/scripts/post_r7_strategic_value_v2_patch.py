from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"{label} marker not found")
    return text.replace(old, new, 1)


policy = Path("rust/crates/urza-policy/src/lib.rs")
text = policy.read_text()
text = replace_once(
    text,
    'pub const POST_R7_STRATEGIC_POLICY_VERSION: &str = "post_r7_strategic_value_v1";',
    'pub const POST_R7_STRATEGIC_POLICY_VERSION: &str = "post_r7_strategic_value_v2_resource_aware";',
    "strategic policy version",
)
text = replace_once(
    text,
    "    pub uthros_draw_ability: Option<AbilityId>,\n",
    "    pub uthros_draw_ability: Option<AbilityId>,\n    pub library_look_kind: Option<u16>,\n",
    "config library look field",
)
text = replace_once(
    text,
    "            uthros_draw_ability: None,\n",
    "            uthros_draw_ability: None,\n            library_look_kind: None,\n",
    "config library look default",
)
old_choose = '''        let drain_stack = !pending && !information.stack.is_empty();
        let selected = candidates
            .iter()
            .filter(|candidate| {
                !pending || candidate.class == PolicyActionClass::ContingentDecision
            })
            .min_by(|left, right| {
                self.action_bucket(information, left, drain_stack)
                    .cmp(&self.action_bucket(information, right, drain_stack))
'''
new_choose = '''        let drain_stack = !pending && !information.stack.is_empty();
        let protected_activation_sources = candidates
            .iter()
            .filter(|candidate| {
                candidate.class == PolicyActionClass::ActivateAbility
                    && self.activation_is_live(information, candidate)
            })
            .filter_map(|candidate| candidate.key.source)
            .collect::<BTreeSet<_>>();
        let selected = candidates
            .iter()
            .filter(|candidate| {
                !pending || candidate.class == PolicyActionClass::ContingentDecision
            })
            .min_by(|left, right| {
                self.action_bucket(
                    information,
                    left,
                    drain_stack,
                    &protected_activation_sources,
                )
                .cmp(&self.action_bucket(
                    information,
                    right,
                    drain_stack,
                    &protected_activation_sources,
                ))
'''
text = replace_once(text, old_choose, new_choose, "choose resource-aware bucket")
old_sig = '''    fn action_bucket(
        &self,
        information: &InformationState,
        candidate: &PolicyCandidate,
        drain_stack: bool,
    ) -> u8 {
'''
new_sig = '''    fn action_bucket(
        &self,
        information: &InformationState,
        candidate: &PolicyCandidate,
        drain_stack: bool,
        protected_activation_sources: &BTreeSet<CanonicalObjectId>,
    ) -> u8 {
'''
text = replace_once(text, old_sig, new_sig, "action bucket signature")
old_main = '''        if matches!(information.phase, Phase::PrecombatMain) {
            match candidate.class {
                PolicyActionClass::PlayLand => 0,
                PolicyActionClass::CastSpell | PolicyActionClass::ActivateAbility => 1,
                PolicyActionClass::ProduceMana => 2,
                PolicyActionClass::ManaSetup => 3,
                PolicyActionClass::PassPriority => 4,
                PolicyActionClass::ContingentDecision => 5,
            }
        } else {
'''
new_main = '''        if matches!(information.phase, Phase::PrecombatMain) {
            if self.is_redundant_library_look(information, candidate) {
                return 7;
            }
            return match candidate.class {
                PolicyActionClass::PlayLand => 0,
                PolicyActionClass::ProduceMana
                    if !candidate
                        .key
                        .source
                        .is_some_and(|source| protected_activation_sources.contains(&source)) =>
                {
                    1
                }
                PolicyActionClass::CastSpell | PolicyActionClass::ActivateAbility => 2,
                PolicyActionClass::ManaSetup => 3,
                PolicyActionClass::ProduceMana => 4,
                PolicyActionClass::PassPriority => 5,
                PolicyActionClass::ContingentDecision => 6,
            };
        } else {
'''
text = replace_once(text, old_main, new_main, "main resource ordering")
marker = '''    fn candidate_score(&self, information: &InformationState, candidate: &PolicyCandidate) -> i64 {
'''
helpers = '''    fn activation_is_live(
        &self,
        information: &InformationState,
        candidate: &PolicyCandidate,
    ) -> bool {
        candidate.class == PolicyActionClass::ActivateAbility
            && !self.is_redundant_library_look(information, candidate)
            && (self
                .config
                .action_kind_values
                .get(&candidate.key.kind)
                .copied()
                .unwrap_or_default()
                > 0
                || self.stack_intervention_score(information, candidate) > 0)
    }

    fn is_redundant_library_look(
        &self,
        information: &InformationState,
        candidate: &PolicyCandidate,
    ) -> bool {
        candidate.class == PolicyActionClass::ActivateAbility
            && Some(candidate.key.kind) == self.config.library_look_kind
            && information.library.known_top.len() >= 3
    }

'''
text = replace_once(text, marker, helpers + marker, "resource helper insertion")
policy.write_text(text)

rollout = Path("rust/crates/urza-rollout/src/lib.rs")
text = rollout.read_text()
text = replace_once(
    text,
    'pub const POST_R7_STRATEGIC_ROLLOUT_VERSION: &str = "post_r7_strategic_rollout_v1";',
    'pub const POST_R7_STRATEGIC_ROLLOUT_VERSION: &str = "post_r7_strategic_rollout_v2_resource_aware";',
    "strategic rollout version",
)
rollout.write_text(text)

smoke = Path("rust/crates/urza-mulligan/src/bin/post-r7-strategic-value-smoke.rs")
text = smoke.read_text()
text = replace_once(
    text,
    'const VERSION: &str = "post_r7_strategic_value_smoke_v1";',
    'const VERSION: &str = "post_r7_strategic_value_smoke_v2_resource_aware";',
    "smoke version",
)
text = replace_once(
    text,
    "    config.uthros_draw_ability = Some(ABILITY_UTHROS_ARTIFACT_DRAW);\n",
    "    config.uthros_draw_ability = Some(ABILITY_UTHROS_ARTIFACT_DRAW);\n    config.library_look_kind = Some(KIND_TOP_LOOK);\n",
    "smoke library look config",
)
smoke.write_text(text)

tests = Path("rust/crates/urza-policy/tests/strategic_value.rs")
text = tests.read_text()
text = replace_once(
    text,
    "    config.uthros_draw_ability = Some(UTHROS_DRAW);\n",
    "    config.uthros_draw_ability = Some(UTHROS_DRAW);\n    config.library_look_kind = Some(15);\n",
    "test library look config",
)
append = r'''

#[test]
fn unprotected_mana_production_precedes_low_value_spend_in_main_phase() {
    let policy = configured();
    let information = InformationState {
        phase: Phase::PrecombatMain,
        ..InformationState::default()
    };
    let mana = PolicyCandidate::new(
        ActionToken(1),
        PolicyActionClass::ProduceMana,
        PolicyPublicKey {
            kind: 3,
            source: Some(CanonicalObjectId(1)),
            card: Some(CardDefId(2)),
            ..PolicyPublicKey::default()
        },
    );
    let cast = candidate(2, PolicyActionClass::CastSpell, 9, Some(30));
    assert_eq!(policy.choose(&information, &[cast, mana]).unwrap(), Some(ActionToken(1)));
}

#[test]
fn live_engine_activation_protects_same_source_from_urza_mana() {
    let mut config = StrategicPolicyConfig::default();
    config.action_kind_values.insert(35, 140);
    let policy = StrategicPolicy::new(config);
    let information = InformationState {
        phase: Phase::PrecombatMain,
        ..InformationState::default()
    };
    let mana = PolicyCandidate::new(
        ActionToken(1),
        PolicyActionClass::ProduceMana,
        PolicyPublicKey {
            kind: 5,
            source: Some(CanonicalObjectId(7)),
            card: Some(CardDefId(81)),
            ..PolicyPublicKey::default()
        },
    );
    let draw = PolicyCandidate::new(
        ActionToken(2),
        PolicyActionClass::ActivateAbility,
        PolicyPublicKey {
            kind: 35,
            source: Some(CanonicalObjectId(7)),
            card: Some(CardDefId(81)),
            ..PolicyPublicKey::default()
        },
    );
    assert_eq!(policy.choose(&information, &[mana, draw]).unwrap(), Some(ActionToken(2)));
}

#[test]
fn redundant_top_look_loses_to_passing_after_three_cards_are_known() {
    let mut config = StrategicPolicyConfig::default();
    config.action_kind_values.insert(15, 70);
    config.library_look_kind = Some(15);
    let policy = StrategicPolicy::new(config);
    let information = InformationState {
        phase: Phase::PrecombatMain,
        library: LibraryBelief {
            known_top: vec![CardDefId(10), CardDefId(20), CardDefId(30)],
            ..LibraryBelief::default()
        },
        ..InformationState::default()
    };
    let top = candidate(1, PolicyActionClass::ActivateAbility, 15, Some(77));
    let pass = candidate(2, PolicyActionClass::PassPriority, 1, None);
    assert_eq!(policy.choose(&information, &[top, pass]).unwrap(), Some(ActionToken(2)));
}
'''
if "unprotected_mana_production_precedes_low_value_spend_in_main_phase" in text:
    raise SystemExit("v2 strategic tests already present")
tests.write_text(text + append)

doc = Path("rust/POST_R7_STRATEGIC_VALUE_POLICY.md")
text = doc.read_text()
text += '''\n## v2 resource-aware repair\n\nThe first 128-world v1 smoke was liveness-clean but produced 0 strategic terminals, 0 Top-look selections, 81 real tutor-target selections and 1 trigger-order decision. The selector had made cast/activation spending outrank mana production, which encouraged spending the first affordable mana instead of accumulating resources for stronger engines and precursor pieces.\n\nv2 restores main-phase resource accumulation from unprotected sources before spending. A mana source is protected when the same public canonical source has a currently live configured strategic activation, preventing Urza artifact mana from automatically tapping that engine before its activation is compared against casts. Redundant Sensei Top looks are explicitly deprioritized once three top cards are already known.\n'''
doc.write_text(text)

log = Path("rust/DEVELOPMENT_LOG.md")
log.write_text(
    log.read_text()
    + '''\n\n## 2026-09-07 — Post-R7 strategic value v2 resource-aware repair candidate\n\nThe v1 128-world smoke was clean but strategically negative: 0 terminals, 0 Top looks, 81 real tutor targets, 1 trigger-order decision. Root cause in policy ordering: v1 spent legal mana on the first cast/activation before exhausting ordinary mana production, suppressing access to more expensive engines/precursors. v2 makes precombat resource production precede spending while protecting canonical sources that have live configured strategic activations, and suppresses redundant Top looks after three cards are known. Frozen R5 deterministic policy remains unchanged.\n'''
)
