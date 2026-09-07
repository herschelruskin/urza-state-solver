# Post-R7 Engine and Tutor Structural Diagnostic

Status: diagnostic checkpoint after the repaired depth-2 surface and the clean depth-3 probe. This document does **not** change R4 rules semantics or the R5 deterministic policy. It records why the current frozen policy is not yet a competent Urza gameplay policy.

## Search / liveness checkpoint

- Natural R5 search previously produced 524,288 all-Horizon rollouts.
- Exact two-deviation search proved a natural sampled positive at opening world 100013 / hidden world 245416 (`ChromeDomeBatteredGolem`, turn 6).
- Attachment lifecycle and Transmute dead-end defects found by bounded deviations were repaired.
- Two post-repair depth-2 blocks completed clean.
- A depth-3 probe over depth-2-clean worlds completed 16/16 opening jobs successfully with compact negative artifacts and no `NoCandidate` / StepLimit break.

The current diagnostic question is therefore no longer only liveness. It is whether the accepted Rust surface and frozen policy can build realistic winning states from legal information.

## Information boundary

The production Rust policy remains information-faithful:

- policy decisions receive `InformationState` / public candidate metadata;
- exact unknown library order remains in `TrueState` for execution only;
- Oracle comparisons are diagnostic upper bounds and must not become the production continuation policy.

Matched Oracle probes use the same physical 99-card order only to compare structural plans. The corrected Oracle remains clairvoyant.

## Finding 1: major card-advantage engines are outside the accepted Rust surface

The current coverage registry explicitly marks several strategically central card-advantage cards as `INTENTIONALLY_UNMODELED`:

| Card | CardDefId | Current coverage | Consequence |
| --- | ---: | --- | --- |
| The One Ring | 81 | INTENTIONALLY_UNMODELED | Ring's activated draw engine is unavailable to the Rust player surface. |
| Uthros Research Craft | 88 | INTENTIONALLY_UNMODELED | Uthros activation / artifact-cast draw engine is unavailable. |
| Faerie Mastermind | 19 | INTENTIONALLY_UNMODELED | Mastermind card-advantage behavior is unavailable. |
| Mystic Remora | 53 | INTENTIONALLY_UNMODELED | Remora card feed / upkeep behavior is unavailable. |
| Rhystic Study | 66 | INTENTIONALLY_UNMODELED | Rhystic card feed is unavailable. |
| Witching Well | 94 | INTENTIONALLY_UNMODELED | Well draw activation is unavailable on the accepted surface. |

Other important partial cases:

- **Forensic Gadgeteer (25)** is rules-active for investigate and artifact-activation reduction, but the CandidateBridge has no Clue sacrifice-to-draw action. Gadgeteer currently creates useful artifacts / Urza mana but not the full card-advantage engine a player expects.
- **Sewer-veillance Cam (74)** is rules-active for recurrence entry/leave interactions, while its sacrifice-to-draw ability remains deferred.
- **Mishra's Bauble (47)** and **Urza's Bauble (86)** have ordinary artifact primitives while their delayed-draw activations remain deferred.

By contrast, two core library-access engines are present:

- **The Reality Chip (82)**: continuous top look, reconfigure/detach, and attached top-play permission are modeled.
- **Fortune Teller's Talent (26)**: level progression, continuous top look, top-play gate, and level-3 reduction are modeled.

Therefore a large fraction of the deck's real card-velocity package simply cannot contribute its intended gameplay value in the current Rust policy evaluation.

## Finding 2: Gadgeteer is not yet a complete card-advantage engine

R4 exposes `ABILITY_GADGETEER_INVESTIGATE` and creates Clue tokens through the common artifact-entry path. However, the accepted `Action` / CandidateBridge surface contains no Clue `2, sacrifice: draw a card` activation.

Diagnostic implication: counting Gadgeteer as a modeled card-advantage engine would overstate the current engine. It is presently closer to artifact/token generation plus activation-cost reduction.

## Finding 3: frozen policy structurally undervalues engine activations

With no pending decision and an empty stack, R5 class ranking is:

1. PlayLand
2. ProduceMana
3. CastSpell
4. ActivateAbility
5. PassPriority

This is deterministic infrastructure ranking, not Urza strategic value.

Consequences:

- a legal spell cast outranks a legal Top / FTT / Reality Chip activation solely by action class;
- engine development is not compared against terminal progress, cards seen, or future resource value;
- within an action class, the semantic public key is used as the stable tie-break rather than a gameplay value estimate.

This behavior is appropriate as a deterministic R5 plumbing baseline but is not adequate as the teacher / gameplay policy.

## Finding 4: staged tutors are structurally biased toward fail-to-find

`legal_contingent_actions()` builds all eligible `ChooseSearchTarget { target: Some(card) }` actions and then appends the legal `ChooseSearchTarget { target: None }` fail-to-find action.

The CandidateBridge maps these to the same contingent action class and `PolicyPublicKey.kind = 28`, with:

- a real target represented as `card = Some(CardDefId)`;
- fail-to-find represented as `card = None`.

`PolicyPublicKey` derives ordinary lexicographic ordering, and the frozen deterministic policy chooses the minimum semantic key. For equal action kind, Rust `Option` ordering places `None` before `Some(...)`.

Therefore the frozen policy has a structural preference for **fail-to-find** at staged search decisions. This is more severe than choosing a strategically weak tutor target: the baseline can decline modeled tutors by construction.

This applies to the common staged search-target bridge used by modeled simple and artifact tutor families unless another rule removes the no-find candidate.

## Finding 5: important tutor families are also missing

Current coverage includes substantial tutor infrastructure:

- Merchant Scroll (44): active staged blue-instant search to hand.
- Mystical Tutor (54): active staged instant/sorcery search to library top.
- Spellseeker (77): active staged MV<=2 instant/sorcery search to hand.
- Repurposing Bay (63): active exact sacrificed-MV+1 artifact search.
- Reshape (64): active MV<=X artifact search.
- Transmute Artifact (84): active sacrifice / target / difference-payment sequence.
- Tezzeret, Cruel Captain (80): active -3 artifact MV<=1 tutor.
- Urza's Saga (87): active chapter-III printed-{0}/{1} artifact search.
- Whir of Invention (93): active MV<=X artifact search with committed improvise sources.

But several strategically important tutor functions remain outside the accepted surface:

- Dizzy Spell (16): INTENTIONALLY_UNMODELED (transmute absent).
- Muddle the Mixture (52): INTENTIONALLY_UNMODELED (transmute absent).
- Scour for Scrap (70): INTENTIONALLY_UNMODELED.

So tutor diagnosis must distinguish two failures:

1. a tutor/mechanic is not modeled at all;
2. the tutor is modeled but frozen policy declines or chooses targets without strategic value.

## Active matched-trace diagnostic

The post-R7 structural comparison harness exports exact Rust physical worlds and runs the corrected `oracle-ceiling-permissions-trigger-order` branch on the same 99-card order.

Initial matched cases:

- opening 13 / hidden 245416: known exact two-deviation positive neighborhood;
- opening 1 / hidden 245323: Top / lifecycle-rich case;
- opening 6 / hidden 245406: Power Artifact / attachment-rich case.

The Rust export now records, for every baseline decision:

- selected action;
- every decision where one of the tracked engine cards had a legal candidate;
- whether the selected action was that engine candidate;
- every staged tutor decision;
- tutor source;
- full legal target set;
- selected target.

The Oracle half is diagnostic only and is explicitly labeled clairvoyant. Trace steps are not treated as information-set-aligned decisions.

## Required next diagnostics before teacher/policy work

1. Complete matched Rust/Oracle traces and classify structural differences in engine timing and tutor usage.
2. Run a broader Rust-only opportunity sample to quantify engine candidate exposure vs selection and tutor source/target frequencies.
3. Separate missing gameplay surface from bad policy:
   - missing engine actions require audited R4/R-next rules/candidate additions;
   - modeled actions skipped for semantic ordering require policy/value work.
4. Do not train or accept a mulligan teacher while central draw engines are absent or staged tutors systematically fail-to-find.
5. Preserve the legal-information boundary: Oracle lines may propose hypotheses but must not become hidden-order-dependent production decisions.
