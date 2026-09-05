# R4 acceptance

## Status

R4 is accepted and closed once the validation gate below is green. This milestone freezes the rules-engine surface needed before deterministic R5 policy work begins; it does **not** claim that all 95 active card identities have complete Oracle text implemented.

## Accepted surface

R4 is an exact extension of the frozen R3 database:

- R3 accepted active identities: **32**;
- R4 accepted active identities: **47**;
- R4-only active identities: **15**;
- audited terminal families: **13**.

The exact R4-only extension is:

1. Basalt Monolith;
2. Grim Monolith;
3. Forensic Gadgeteer;
4. Power Artifact;
5. The Reality Chip;
6. Fortune Teller's Talent;
7. Grafdigger's Cage;
8. Grinding Station;
9. Battered Golem;
10. Chrome Dome;
11. Mana Vault;
12. Banishing Knack;
13. Retraction Helix;
14. Valley Floodcaller;
15. Sewer-veillance Cam.

The R4 validator checks this **set exactly**, not merely the total count, and requires an R4-specific coverage reason for every R4-only identity. The R4 audit is cumulative: R1 catalog, R2 database, and frozen R3 database validation are prerequisites of the R4 validator itself.

## Terminal-family gate

All 13 audited families have:

- a real-catalog positive witness;
- an executable final-step witness through the public rules transition API;
- a one-factor near miss;
- Urza-presence and unresolved-stack rejection;
- raw ObjectId renaming invariance;
- hidden-library permutation invariance where library order is not public;
- Grafdigger's Cage rejection for the Top/library-cast families.

Terminal recognition consumes `InformationState`, never `TrueState` hidden order.

## Decision / information boundary

R4-specific contingent decisions are accepted only when the policy-visible action surface can continue them from public information. Final acceptance exercises:

- Sensei's Divining Top reorder choices;
- Grinding Station / Battered Golem artifact-entry may-untap choices;
- Sewer-veillance Cam target selection and tap/untap/decline effect choice.

Ordinary action enumeration/ranking is intentionally **not** added here. R4 exposes typed execution actions and contingent public choices; deterministic policy construction and rollout selection remain R5 work.

## State / information / value contract

Final R4 namespaces are frozen as:

- rules: `r4_acceptance_v6`;
- model: `urza_model_r4c_2026_09_04`;
- information: `information_state_v7_r4`;
- ValueKey: `value_key_v7_r4`.

No final-acceptance state field was added. The acceptance tests instead verify that recurrence-relevant public state already introduced by R4—temporary granted abilities and Chrome Dome delayed sacrifice events—survives `TrueState -> InformationState -> ValueKey`, while unknown hidden-library permutations still merge.

## Coverage / deferred boundary

The active deck still contains **48 identities** whose R4 profile is `Unsupported`; each remains explicitly `INTENTIONALLY_UNMODELED` in the coverage registry. In addition, some of the 47 active identities are deliberately `PRIMITIVE_ACTIVE` and retain coverage-listed card text outside the accepted R4 engine surface.

Examples deliberately outside this R4 gate include Mana Vault upkeep/draw-step details, Sewer-veillance Cam sacrifice-draw text, Valley Floodcaller flash/combat sizing, Grafdigger's Cage effects beyond the accepted library-cast interaction, and older R2/R3 primitives whose unrelated activated/channel/combat text remains deferred. Those mechanics are not silently approximated.

## Acceptance validation

The closure gate is:

```text
cargo metadata --locked --format-version 1 --no-deps
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets --all-features -- -D warnings
cargo test --locked --workspace --all-targets
cargo check --locked --workspace --benches
cargo run --locked -p urza-cli -- r0-audit
cargo run --locked -p urza-cli -- r1-audit
cargo run --locked -p urza-cli -- r2-audit
cargo run --locked -p urza-cli -- r3-audit
cargo run --locked -p urza-cli -- r4-audit
```

R5 must start from a commit for which all of these commands pass. R5 may consume the accepted typed rules/information/value surface, but must not weaken hidden-information boundaries or reintroduce Python gameplay implementation structures.
