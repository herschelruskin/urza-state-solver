const MANIFEST: &str = include_str!("../Cargo.toml");

#[test]
fn policy_depends_on_public_information_not_execution_crates() {
    let dependencies: Vec<_> = MANIFEST.lines().map(str::trim).collect();

    assert!(
        !dependencies
            .iter()
            .any(|line| line.starts_with("urza-core")),
        "urza-policy must consume InformationState through urza-info, not urza-core"
    );
    assert!(
        !dependencies
            .iter()
            .any(|line| line.starts_with("urza-rules")),
        "urza-policy must not import execution Action/Rule types; the R5 bridge stays outside policy"
    );
}
