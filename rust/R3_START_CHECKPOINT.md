# R3 start checkpoint

## Scope

R3 begins from the validated R2 acceptance head `7d01f098fa32d2df453d828b8cba509e4f950814`.

This checkpoint establishes the shared **decision -> observation -> contingent decision** search contract before adding the larger R3 mechanics. It is not the R3 acceptance gate.

Implemented here:

- staged Spellseeker, Merchant Scroll, and Mystical Tutor;
- instant-speed timing for Mystical Tutor while the other two retain sorcery/main timing;
- Spellseeker resolves as a creature permanent before its ETB search becomes a post-observation decision;
- typed `SearchAvailable` and `SearchCompleted` observations;
- `Window::PostObservation` plus existing `PendingDecision::TutorTarget` as the execution boundary;
- policy-facing contingent target generation from `InformationState` only, without a `TrueState` argument;
- explicit legal no-find action, including the zero-target case as a single forced continuation;
- exact target placement: Spellseeker/Merchant to hand, Mystical Tutor to known library top;
- search shuffles clear stale positional knowledge;
- the tutor target branches share one deterministic permutation of the exact **pre-target** library and delete their selected target from that shared ranking, preserving the audited common-random-number contract;
- exact active-catalog search-class indexes for Spellseeker, Merchant Scroll, and Mystical Tutor;
- an R3 database layer extending the frozen R2 database without changing the R2 audit surface;
- an `r3-audit` CI gate.

The active-deck coverage registry now has 25 supported identities: the 22 R2 identities plus Spellseeker, Merchant Scroll, and Mystical Tutor. Their status is `PRIMITIVE_ACTIVE`; this checkpoint claims the staged tutor/search behavior, not broader combat or later engine mechanics.

## Information-boundary fixtures

The focused tests verify:

1. changing exact hidden library permutation while holding the same multiset produces the same search observation;
2. the resulting `InformationState` and policy-visible contingent action list are identical across those hidden permutations;
3. zero legal targets produces exactly one legal no-find continuation and does not deadlock;
4. Spellseeker is on the battlefield before its search target decision;
5. two target branches from the same pending search consume the same RNG occurrence and preserve the relative order of cards common to both branches, proving they delete from one shared pre-target shuffle ranking;
6. Mystical Tutor places the selected target on a legally known top position.

## Versions

- current rules: `r3_search_staging_v1`;
- preserved R2 rules namespace: `r2_core_kernel_v2`;
- model remains `urza_model_r2_2026_09_01` because this slice does not change `TrueState` schema;
- RNG scheme remains unchanged; R3 adds a dedicated search-shuffle event type inside the existing occurrence-aware game RNG domain.

## Validation

Implementation checkpoint: `9834759df176aca4809c74d959a9f5f9fc2ed0d5`.

GitHub Actions run `33567546432`: PASS.

- locked dependency graph: PASS;
- rustfmt: PASS;
- strict Clippy (`-D warnings`): PASS;
- workspace/all-target tests: PASS; 56 passed, 0 failed;
- benchmark compilation: PASS;
- R0 audit: PASS;
- R1 catalog audit: PASS;
- R2 core audit: PASS;
- R3 staged-search audit: PASS;
- R3 audit reports 25 supported active identities and the explicit commit -> observation -> target/no-find -> shared-pre-target-shuffle boundary.

## Remaining R3 work

Before R3 acceptance, broaden this same staged architecture to:

- Whir of Invention;
- Reshape;
- Transmute Artifact;
- Repurposing Bay;
- Urza's Saga chapter III;
- Tezzeret, Cruel Captain search;
- Sensei's Divining Top and scry;
- Urza spin and persistent permission handling.

These mechanics must reuse the information boundary rather than introduce combined clairvoyant actions.
