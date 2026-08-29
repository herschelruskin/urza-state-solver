const MANIFEST: &str = include_str!("../Cargo.toml");

#[test]
fn policy_has_no_direct_dependency_on_execution_state_crate() {
    assert!(
        !MANIFEST
            .lines()
            .map(str::trim)
            .any(|line| line.starts_with("urza-core")),
        "urza-policy must consume PolicyView/InformationState through urza-info, not urza-core"
    );
}
