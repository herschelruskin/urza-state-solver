from pathlib import Path

policy = Path('rust/crates/urza-policy/src/lib.rs')
text = policy.read_text()
text = text.replace(
    'pub const POST_R7_STRATEGIC_POLICY_VERSION: &str = "post_r7_strategic_value_v2_resource_aware";',
    'pub const POST_R7_STRATEGIC_POLICY_VERSION: &str = "post_r7_strategic_value_v3_library_information";',
)
old = '''        let card_value = match (candidate.class, candidate.key.card) {
            (PolicyActionClass::CastSpell, Some(card)) => self.deployment_value(information, card),
            (PolicyActionClass::ActivateAbility, Some(card)) => {
                i64::from(self.base_card_value(card))
            }
            _ => 0,
        };
        kind_value + card_value + self.stack_intervention_score(information, candidate)
'''
new = '''        let card_value = match (candidate.class, candidate.key.card) {
            (PolicyActionClass::CastSpell, Some(card)) => self.deployment_value(information, card),
            (PolicyActionClass::ActivateAbility, Some(card)) => {
                i64::from(self.base_card_value(card))
            }
            _ => 0,
        };
        let library_information_value = if candidate.class == PolicyActionClass::ActivateAbility
            && Some(candidate.key.kind) == self.config.library_look_kind
            && information.library.known_top.len() < 3
        {
            i64::from(self.config.unknown_card_value).saturating_mul(3)
        } else {
            0
        };
        kind_value
            + card_value
            + library_information_value
            + self.stack_intervention_score(information, candidate)
'''
if old not in text:
    raise SystemExit('candidate_score anchor not found')
text = text.replace(old, new)
policy.write_text(text)

tests = Path('rust/crates/urza-policy/tests/strategic_value.rs')
t = tests.read_text()
append = r'''

#[test]
fn fresh_three_card_library_look_beats_medium_deployment_but_not_recipe_completion() {
    let mut config = StrategicPolicyConfig::default();
    config.unknown_card_value = 50;
    config.action_kind_values.insert(15, 70);
    config.library_look_kind = Some(15);
    config.card_values.insert(CardDefId(40), 90);
    config.card_values.insert(CardDefId(50), 100);
    config
        .terminal_recipes
        .push(TerminalRecipe::new(vec![CardDefId(10), CardDefId(50)]));
    let policy = StrategicPolicy::new(config);

    let fresh = InformationState {
        phase: Phase::PrecombatMain,
        ..InformationState::default()
    };
    let top = candidate(1, PolicyActionClass::ActivateAbility, 15, None);
    let medium_cast = candidate(2, PolicyActionClass::CastSpell, 9, Some(40));
    assert_eq!(
        policy.choose(&fresh, &[medium_cast, top.clone()]).unwrap(),
        Some(ActionToken(1))
    );

    let recipe_state = InformationState {
        phase: Phase::PrecombatMain,
        battlefield: vec![permanent(10, 1)],
        ..InformationState::default()
    };
    let completion = candidate(3, PolicyActionClass::CastSpell, 9, Some(50));
    assert_eq!(
        policy.choose(&recipe_state, &[top, completion]).unwrap(),
        Some(ActionToken(3))
    );
}
'''
if 'fresh_three_card_library_look_beats_medium_deployment_but_not_recipe_completion' not in t:
    tests.write_text(t + append)

smoke = Path('rust/crates/urza-mulligan/src/bin/post-r7-strategic-value-smoke.rs')
s = smoke.read_text().replace(
    'post_r7_strategic_value_smoke_v2_resource_aware',
    'post_r7_strategic_value_smoke_v3_library_information',
)
smoke.write_text(s)
