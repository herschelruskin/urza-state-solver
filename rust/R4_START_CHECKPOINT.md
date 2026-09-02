# R4 start checkpoint

## Scope

R4 begins from the accepted R3 head `83f314546b80e6ac23feb6463b0cdcc2e09ba63d`.

The audited R4 milestone is **engine cards and the win catalog**: broaden high-frequency engine mechanics and implement every prerequisite needed for the accepted terminal families. This checkpoint establishes the first coherent R4 engine slice. It is **not** the R4 acceptance gate.

Implemented here:

- a dedicated `R4CardDatabase` extending the frozen 32-identity R3 database;
- Basalt Monolith as an ordinary artifact cast with `{T}: add {C}{C}{C}`, no normal untap, and its native `{3}: untap Basalt Monolith` activated ability;
- Grim Monolith as an ordinary artifact cast with `{T}: add {C}{C}{C}`, no normal untap, and its native `{4}: untap Grim Monolith` activated ability;
- Monolith untap abilities use the ordinary stack/priority model rather than being treated as mana abilities;
- Forensic Gadgeteer as an ordinary creature cast plus its static one-generic reduction to artifact activated abilities;
- the audited **one-mana floor** for Forensic Gadgeteer reductions: an activation whose generic component is already `{1}` cannot be reduced to zero;
- the reduction is implemented at the shared artifact-activation cost boundary, so already-modeled artifact activations such as Top and Repurposing Bay use the same rule rather than card-specific shortcuts;
- untap-step handling is now card-profile aware, allowing Monoliths to remain tapped while ordinary permanents untap;
- the first typed terminal family, `Basalt + Gadgeteer`, detected from public `InformationState` only;
- the terminal predicate requires a ready Basalt Monolith, Forensic Gadgeteer, Urza on the battlefield, no unresolved stack object, and no contingent decision;
- a dedicated `r4-audit` CI gate;
- active primitive coverage increased from 32 to 35 identities by adding Basalt Monolith, Grim Monolith, and Forensic Gadgeteer.

Python gameplay logic was not ported. The historical Python win-catalog smoke was used only as a parity witness for the named terminal family and the requirement that pre-Urza infinite colorless is not automatically terminal.

## Historical milestone isolation

R4 coverage progression does not rewrite the accepted R3 surface.

- `R3CardDatabase` remains exactly 32 supported active identities.
- `r3-audit` reports the frozen R3 rules namespace `r3_search_complete_v4`.
- `R4CardDatabase` extends that surface to 35 identities.
- current R4 rules namespace is `r4_engine_start_v1`.

No `TrueState`, `InformationState`, or `ValueKey` schema field was added in this slice, so the accepted R3 model/information/value schemas remain current:

- model: `urza_model_r3b_2026_09_01`;
- information: `information_state_v4_r3`;
- ValueKey: `value_key_v4_r3`.

## Focused rules and terminal fixtures

The R4-start tests verify:

1. Basalt and Grim each tap for three colorless;
2. native Monolith untap is a stack-based activated ability and does not untap its source until resolution;
3. Basalt and Grim stay tapped during the normal untap step while an ordinary artifact untaps;
4. Forensic Gadgeteer reduces Basalt's native untap from `{3}` to `{2}`;
5. a one-generic artifact activation remains `{1}` under Gadgeteer rather than becoming free;
6. one Basalt/Gadgeteer tap/untap cycle nets exactly one colorless;
7. `Basalt + Gadgeteer` terminal detection succeeds only from a public ready-engine state with Urza present;
8. the same visible engine is not terminal before Urza is available, and a tapped Basalt is not prematurely classified terminal.

## Validation

Validated implementation commit: `d4f7a4033d8cef88c514ee094b9da8d5ca376d4d`.

GitHub Actions run `33586517441`: PASS.

- locked dependency graph: PASS;
- rustfmt: PASS;
- strict Clippy (`-D warnings`): PASS;
- workspace/all-target tests: **75 passed, 0 failed**;
- benchmark compilation: PASS;
- R0 audit: PASS;
- R1 catalog audit: PASS;
- R2 core audit: PASS;
- R3 staged-search audit: PASS;
- R4 engine/win audit: PASS;
- R4 audit reports 35 supported active identities, the three initial engine primitives, and the first terminal family `Basalt + Gadgeteer`.

## Remaining R4 work

R4 acceptance still requires broadening high-frequency engine mechanics and covering the remaining audited terminal families and their true prerequisites. In particular, later R4 slices must cover, as needed by the audited catalog:

- Power Artifact and its exact-object attachment/reduction interaction;
- Power Artifact + Grim Monolith;
- Power Artifact + Basalt Monolith;
- Reality Chip attachment/top-of-library play;
- Fortune Teller's Talent levels and top visibility/play permission;
- the Top + Chip / FTT terminal families;
- the Top + Gadgeteer + producer family;
- Chrome Dome copy behavior and its Station/Golem/PA-Gadgeteer-Vault families;
- Grinding Station and Battered Golem engine interactions;
- Banishing Knack / Retraction Helix exact-creature grants;
- Valley Floodcaller and Sewer-veillance Cam recurrence prerequisites;
- the remaining high-frequency mana/value engines and trigger sequencing required by deterministic rollouts;
- final terminal-family coverage fixtures proving that presence of a tutor or engine card alone is not treated as a win.

Hidden information and future choices must continue to cross the accepted R3 observation boundary explicitly. R4 must not gain performance by merging exact card identities or replacing executable prerequisites with optimistic terminal shortcuts.
