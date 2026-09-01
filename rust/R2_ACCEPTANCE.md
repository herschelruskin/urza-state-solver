# R2 acceptance checkpoint

## Authority and scope

R2 is the audited **core sequencing/rules kernel** milestone. Its required surface is turn phases/horizon, land play, mana activation/payment, ordinary artifact cast/entry, Urza cast/Construct/artifact mana, stack/priority/pass, draws/shuffles, and a hidden-order-safe search observation framework.

R2 does **not** absorb R3 search/tutor staging or R4 engine-card interactions. In particular, simple tutors, Whir, Reshape, Transmute, Repurposing Bay search, Saga III, Tezzeret search, Top/scry, and Urza spin permission remain later milestones.

Python gameplay implementation structures were not ported. Accepted Python non-oracle smokes were used only as parity witnesses for two sequencing expectations: an ordinary artifact is on the stack before it enters the battlefield, and the natural draw is revealed only after the turn progression that commits to it.

## Accepted kernel contracts

- T1-T6 phase/horizon progression is explicit and horizon failure does not mutate the state.
- Priority/pass is explicit; a spell is a stack object before resolution.
- Normal draw emits a typed observation and updates known-top/known-bottom information.
- Shuffle uses the occurrence-aware deterministic RNG contract and clears stale positional knowledge.
- Search observations are independent of exact unknown library order and collapse duplicate physical copies to card-identity choices.
- Mana costs/payments preserve colored/generic payment distinctions.
- Land play and land-drop use are explicit.
- MDFC battlefield face is explicit future-relevant state; the three active MDFC land backs are not represented as their front spell face.
- Our life total remains authoritative for modeled life payments/self-damage.
- Urza command-zone casts track commander tax/cast count, resolve through the stack, create a Construct, and enable tapping untapped artifacts for blue.
- Unsupported mechanics fail explicitly; no difficult card is silently treated as a generic permanent.

Schema/version changes at R2 acceptance:

- model: `urza_model_r2_2026_09_01`;
- information: `information_state_v2_r2`;
- ValueKey: `value_key_v2_r2`;
- rules: `r2_core_kernel_v2`.

## Primitive-active coverage

Exactly 22 active card identities have an R2 primitive. `PRIMITIVE_ACTIVE` means only the listed primitive behavior is supported; it does not claim full Oracle-text coverage.

### Land/mana primitives

- Ancient Tomb — land play; tap for two colorless with 2 self-damage.
- Cephalid Coliseum — land play; tap for blue with 1 self-damage. Threshold loot remains deferred.
- Crystal Vein — land play; tap for one colorless. Sacrifice mana mode remains deferred.
- Hydroelectric Specimen — Hydroelectric Laboratory back face; pay 3 life or enter tapped; tap for blue. Front spell remains deferred.
- Island — land play; tap for blue.
- Minamo, School at Water's Edge — land play; tap for blue. Untap ability remains deferred.
- Oboro, Palace in the Clouds — land play; tap for blue. Bounce ability remains deferred.
- Otawara, Soaring City — land play; tap for blue. Channel remains deferred.
- Sea Gate Restoration — Sea Gate, Reborn back face; pay 3 life or enter tapped; tap for blue. Front spell remains deferred.
- Seat of the Synod — artifact-land play; tap for blue; is eligible for Urza artifact mana.
- Sink into Stupor — Soporific Springs back face; pay 3 life or enter tapped; tap for blue. Front spell remains deferred.

### Ordinary artifact primitives

The following support normal mana-cost payment, cast-to-stack, resolution to battlefield, creature summoning sickness where applicable, and later Urza artifact-mana eligibility. Their card-specific activations/static/combat effects remain deferred unless separately named below:

- Aether Spellbomb;
- Codex Shredder;
- Hope of Ghirapur;
- Manifold Key;
- Mishra's Bauble;
- Tormod's Crypt;
- Urza's Bauble;
- Voltaic Key;
- Welding Jar.

Sol Ring additionally supports its intrinsic `{T}: add {C}{C}` mana ability.

### Commander primitive

Urza, Lord High Artificer supports command-zone casting/tax, stack resolution, Construct creation, and the artifact-to-blue mana ability. Urza's five-mana spin is R3.

The Construct uses synthetic execution/catalog identity `CardDefId(95)`, outside the pinned active deck identities `0..=94`.

## Deterministic acceptance trajectory

The real R1 catalog fixture executes the following deterministic line:

1. T1 precombat main: hand Island + Sol Ring, next library card Island, Urza in command zone.
2. Play Island and tap it for blue.
3. Cast Sol Ring with that blue; verify Sol Ring is on stack and not yet on battlefield.
4. Pass priority; verify Sol Ring enters and emits a typed permanent-entry observation.
5. Tap Sol Ring for two colorless.
6. Pass through main/end and automatically advance opponent-cycle/untap to T2 upkeep.
7. Pass upkeep; draw the known physical next Island and emit the typed draw observation.
8. Enter T2 main, play the second Island, produce UU from the two Islands and CC from Sol Ring.
9. Cast Urza for exactly `{2}{U}{U}`; verify commander zone is Stack.
10. Pass priority; verify Urza and a Construct enter, commander cast count is one, and commander zone is Battlefield.
11. Tap the summoning-sick Construct through Urza's ability for blue; this is legal because the tap is the cost of Urza's ability, not a tap ability of the Construct.

This covers every audited R2 kernel category in one deterministic path while retaining separate focused tests for MDFC face/life entry, Ancient Tomb mana/self-damage, search observation invariance, draw knowledge, shuffle occurrence use, payment enumeration, and horizon behavior.

## Acceptance validation

Validated implementation commit: `841b2f32d9054dcaebfaf37b8893e67959f201d6`.

GitHub Actions run: `33554550014` — PASS.

- locked dependency graph: PASS;
- rustfmt: PASS;
- strict Clippy (`-D warnings`): PASS;
- workspace/all-target tests: 50 passed, 0 failed;
- benchmark compilation: PASS;
- R0 audit: PASS;
- R1 catalog audit: PASS;
- R2 core audit: PASS;
- R2 audit reports 22 supported active identities and T1-T6 horizon.

## R3 boundary

R2 acceptance is closed at this checkpoint. R3 may begin from here with factored decision -> observation -> contingent-decision staging for tutors/search, Whir/Reshape/Transmute/Bay, Saga III, Tezzeret, Top/scry, and Urza spin permission. No R3 implementation should collapse a hidden-information reveal and subsequent target/order choice into one clairvoyant root action.
