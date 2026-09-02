# R3 acceptance checkpoint

## Authority and scope

R3 is the audited **staged hidden-information search, observation, ordering, and permission** milestone built on the closed R2 core sequencing kernel.

R3 accepts the full staged-search surface named by the R3 start checkpoint:

- Spellseeker;
- Merchant Scroll;
- Mystical Tutor;
- Whir of Invention;
- Reshape;
- Transmute Artifact;
- Repurposing Bay;
- Urza's Saga chapters I-III, including the chapter-III search;
- Tezzeret, Cruel Captain -3 search;
- Sensei's Divining Top look/reorder and draw ability;
- generic scry observation/choice;
- Urza, Lord High Artificer five-mana spin and persistent until-end-of-turn permission.

R3 does not claim complete Oracle-text modeling for every primitive-active identity. Coverage remains per-primitive and explicit in `data/card_coverage.r0.json`. Card-specific abilities outside the accepted R3 primitive are still deferred to later milestones.

Python gameplay implementation structures were not ported.

## Accepted information-boundary contract

All R3 hidden-information mechanics preserve a factored

**commit -> observation -> contingent decision**

boundary.

Accepted properties:

- costs, X values, sacrifice choices, taps, loyalty payments, and other pre-reveal commitments are fixed before hidden information is exposed;
- post-observation target/order choices are represented by typed `PendingDecision` state;
- policy-facing contingent actions are generated from `InformationState`, not from exact hidden `TrueState` library order;
- search candidate lists are canonicalized by card identity and do not leak physical library order;
- legal no-find branches are explicit where rules permit failure to find;
- shared search branches use one deterministic ranking of the exact **pre-target** library and delete the selected target from that ranking, retaining the common-random-number contract;
- search/shuffle operations consume occurrence-aware RNG coordinates and clear stale positional knowledge;
- future-relevant stack numeric parameters, pending-decision payloads, Saga mode/lore state, loyalty, known top/bottom order, and Urza permissions remain represented in observation/value state rather than being erased by canonicalization.

## Accepted search and observation mechanics

### Simple tutors

- Spellseeker resolves to the battlefield before its ETB search becomes a post-observation target choice.
- Merchant Scroll and Spellseeker put the selected card into hand.
- Mystical Tutor preserves instant timing and puts the selected card on a legally known library top.
- Exact active-catalog search classes constrain each tutor independently.

### Whir of Invention

- X and improvise sources are committed while casting.
- Improvise taps occur before the search observation.
- Resolution stages an artifact search restricted to mana value <= X.
- The selected artifact enters the battlefield.

### Reshape

- X, mana payment, and artifact sacrifice are committed as casting costs.
- The sacrifice occurs before the library search is observed.
- Resolution stages an artifact search restricted to mana value <= X.
- The selected artifact enters the battlefield.

### Transmute Artifact

- The spell resolves into a staged artifact-sacrifice choice before library search information is exposed.
- After the sacrifice, the artifact search is observed.
- If the selected target has greater mana value than the sacrificed artifact, a separate exact generic-difference payment decision is created.
- Mana abilities are legal during that resolution-payment window.
- Declining the difference payment sends the searched card to the graveyard; paying it puts the card onto the battlefield.

### Repurposing Bay

- Sorcery timing, {2} payment, tap, and sacrifice-another-artifact costs are committed before the activated ability resolves.
- Resolution stages a search for an artifact with mana value exactly one greater than the sacrificed artifact.
- The selected artifact enters the battlefield.

### Urza's Saga

- Saga state is explicit rather than treated as a one-shot tutor.
- Chapter I grants the modeled colorless mana ability.
- Chapter II creates the shared Construct token.
- Chapter III stages its search as an independent trigger.
- Eligibility uses the exact printed-cost class required by the card: artifact cards printed exactly {0} or {1}; mana value alone is not substituted for printed cost.
- The final-chapter Saga sacrifice occurs only after chapter III finishes resolving.

### Tezzeret, Cruel Captain

- The planeswalker enters with explicit starting loyalty.
- The -3 loyalty cost is paid before the search is observed.
- Resolution stages an artifact search restricted to mana value <= 1 and places the selected card into hand.
- Other Tezzeret loyalty abilities and unrelated card text remain deferred.

### Sensei's Divining Top and scry

- Top's {1} ability observes up to the top three cards, then creates a separate reorder decision.
- Reorder actions are permutations of only the observed cards.
- Top's tap ability resolves atomically as draw one, then put Top on top of its owner's library if it remains on the battlefield.
- Generic scry observes the looked-at cards before the top/bottom partition and ordering choice.
- Resulting known-top/known-bottom knowledge is explicit future-relevant information.

### Urza spin and permissions

- Urza's five-mana activation commits payment before resolution.
- Resolution uses an explicit occurrence-aware game RNG context, shuffles, exiles the top card, and emits the observed exile result.
- The exiled card receives a persistent free-play permission through the current turn.
- Permission execution uses canonical observed permission slots rather than raw execution IDs.
- Currently modeled legal card faces can be played through the permission, including modeled MDFC land backs.
- Permissions and their delayed expiry references are removed when the modeled end step closes.

## Schema and version boundary

R3 acceptance intentionally changes future-relevant execution and information state.

Accepted versions:

- model: `urza_model_r3b_2026_09_01`;
- information: `information_state_v4_r3`;
- ValueKey: `value_key_v4_r3`;
- rules: `r3_search_complete_v4`.

The frozen R2 audit namespace remains:

- model: `urza_model_r2_2026_09_01`;
- rules: `r2_core_kernel_v2`.

## Primitive-active coverage

R3 audit reports exactly **32 supported active card identities**.

The ten identities added beyond the 22-card R2 primitive surface are:

- Merchant Scroll;
- Mystical Tutor;
- Repurposing Bay;
- Reshape;
- Sensei's Divining Top;
- Spellseeker;
- Tezzeret, Cruel Captain;
- Transmute Artifact;
- Urza's Saga;
- Whir of Invention.

Urza, Lord High Artificer was already primitive-active in R2; R3 broadens that same identity with its five-mana spin and persistent permission behavior.

`PRIMITIVE_ACTIVE` remains a scoped claim. Deferred text for these and other identities is recorded explicitly in the coverage registry.

## Acceptance validation

Validated implementation commit before the acceptance-document-only closure: `3f2d269364809f6d01bfb0e04ce72b4d221ac9a8`.

GitHub Actions run: `33577801754` — PASS.

- locked dependency graph: PASS;
- rustfmt: PASS;
- strict Clippy (`-D warnings`): PASS;
- workspace/all-target tests: **71 passed, 0 failed**;
- benchmark compilation: PASS;
- R0 audit: PASS;
- R1 catalog audit: PASS;
- R2 core audit: PASS;
- R3 staged-search audit: PASS;
- R3 audit reports `urza_model_r3b_2026_09_01`, `r3_search_complete_v4`, T1-T6 horizon, the staged decision boundary, and 32 supported active identities.

## R4 boundary

R3 acceptance is closed at this checkpoint.

R4 may build broader engine-card interactions and remaining card-specific primitives on top of this state model, but it must preserve the accepted information boundary: hidden information may be observed only after all legally prior commitments are fixed, and subsequent choices must be represented as contingent actions over the resulting information state rather than clairvoyant root actions.
