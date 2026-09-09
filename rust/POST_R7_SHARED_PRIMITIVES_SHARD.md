# Post-R7 shared-primitives shard record

Status: ACTIVE / NOT ACCEPTED

This file records provenance and validation for the dependency-blocking Wave 0 shard. It is not an acceptance ledger and does not modify authoritative modeling-completeness counts.

## Provenance

- Shard: `rust-modeling/shared-primitives`
- Exact integration base SHA: `df19087b828dcf9b2a116a4dbe6ee65b55196a8e`
- Last accepted completeness promotion before this shard: Battered Golem at `3716b84d719fe651a6fee442e45275b5e4b52483`
- Accepted completeness baseline at shard creation: 11/95 resolved, 84 unresolved
- First direct-source materialization commit: `c26b57f8c7443c95156ff8b49e9c0acee6ca36a6`
- Bootstrap/materialization CI: Actions run `34260160146` (GREEN)
- Direct committed-source validation CI: Actions run `34260670834` (GREEN)

The one-time materialization workflow was removed after the intended Rust/test changes were committed. The temporary compile-fix helper modification was restored to the exact base-tree content. Further implementation on this shard must modify committed Rust source and fixtures directly rather than depending on generated patch scripts.

## Direct-source validation at c26b57f

The direct validator checked out exact commit `c26b57f8c7443c95156ff8b49e9c0acee6ca36a6` and passed:

- `cargo fmt --all -- --check`
- workspace `cargo check --locked --workspace --all-targets`
- focused shared-repair card fixtures
- policy-bridge visibility fixtures
- Forensic Gadgeteer cross-regression
- `urza-rules` regression suite
- frozen R4 card acceptance
- frozen R4 terminal acceptance
- modeling-gate unit regression
- strict Clippy `-D warnings`

The validator also asserted that the authoritative modeling gate remained intentionally RED at exactly 95 total / 11 resolved / 84 unresolved. No TSV or generated gate count was changed.

## Mechanics presently materialized but not accepted

- temporary creature power boost state with end-of-turn expiration
- Valley Floodcaller intrinsic flash and noncreature flash permission
- Valley Floodcaller untap/+1-power-until-EOT trigger behavior
- Chrome Dome copy-token haste-equivalent tap readiness
- Chrome Dome static +1/+0 contribution to other artifact creatures
- common artifact-activation reduction helper with one-mana floor, including Clue activation
- targeted Knack/Helix hand-cast action and granted bounce resolution
- attachment-aware cleanup in several existing leave paths

These are candidate mechanics only. No card is promoted by this shard record.

## Remaining Wave 0 blockers found by direct audit

1. Targeted Knack/Helix casting is still hand-only. Reality Chip / Fortune Teller's Talent library-top permissions and Urza exile permissions do not expose the targeted spell path.
2. Permanent-leave handling is duplicated across sacrifice, bounce, and Top-to-library paths rather than centralized.
3. Clue sacrifice still rejects an attached Clue via `AttachedSacrificeDeferred`, contradicting the Wave 0 generic attachment-lifecycle requirement.
4. Sewer-veillance Cam leave triggers are queued manually in only some leave paths. Sacrifice callers such as Grinding Station, Reshape, Repurposing Bay, and Transmute Artifact can miss the LTB trigger.
5. Trigger staging during casting costs and multi-step resolution must preserve correct stack placement/order; Cam LTB must not be naively pushed beneath a spell/ability or resolved during an in-progress Transmute resolution.
6. Generic attachment cleanup must distinguish Aura state-based cleanup from non-Aura attached permanents (for example Reality Chip detach behavior) rather than treating every incoming attachment as a card that goes to the graveyard.
7. Chrome Dome copied-characteristic coverage still requires a clause-level audit beyond haste/static-power behavior.

## Next shared-primitives work

- centralize permanent-leaves-battlefield lifecycle (attachments, Chrome delayed-event cleanup, token disappearance, LTB trigger production)
- provide trigger-block staging that callers can place only after the spell/ability or resolution boundary is correct
- remove attached-Clue sacrifice deferral and add Aura/non-Aura attachment fixtures
- generalize targeted spell casting across hand, top-of-library permissions, and Urza exile permissions with policy-bridge visibility
- rerun direct-source validation plus prior COMPLETE regressions

Only a later integration wave on `rust-engine-rebuild`, followed by the complete modeling gate and successful integration CI, may update authoritative dispositions/counts or the parallel tracker acceptance history.
