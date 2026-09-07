# Post-R7 Matched Rust / Oracle Trace Findings

Diagnostic-only checkpoint. The Oracle is clairvoyant and is used only to expose strategic hypotheses. Production Rust remains information-faithful.

## Provenance

- Rust branch: `rust-engine-rebuild`
- matched harness commit: `43e4c6857d83383823849ecc58d27dffe08927d4`
- workflow: `Post-R7 Oracle structural comparison`
- workflow run: `34161117326`
- result: green
- Oracle branch: `oracle-ceiling-permissions-trigger-order`
- Oracle probe: beam 120, action cap 60, per-turn depth 40
- physical-world matching: the same Rust-exported 99-card order is supplied to the Oracle `search_hand()` entry point
- interpretation limit: Oracle width is diagnostic, not a convergence claim

## Case A — opening 6 / hidden 245406: FTT is deployed but not developed

Opening:

`Polluted Delta | Mox Diamond | Vexing Bauble | Oboro, Palace in the Clouds | Fortune Teller's Talent | Force of Negation | Hydroelectric Specimen`

Rust frozen policy:

- Horizon, turn 6, trace length 45.
- Cast Fortune Teller's Talent on turn 2.
- Never activated an FTT level ability afterward.
- First cast Sensei's Divining Top on turn 5.
- Used Top's draw ability once on turn 5.
- Final battlefield still contains Fortune Teller's Talent at the horizon.
- Final hand contains Power Artifact and Sensei's Divining Top, among other cards.

Corrected Oracle diagnostic on the same physical order:

- wins turn 5;
- terminal family: `Top + FTT L3`;
- sees/casts Top from turn 1;
- casts FTT and develops the Top/FTT library-access line rather than leaving FTT static.

Interpretation:

This is direct evidence for **engine-development failure**, not merely missing terminal recognition. The Rust rules surface can cast FTT and operate Top, but the frozen policy does not plan toward FTT level 3.

## Case B — opening 1 / hidden 245323: The One Ring is not on the Rust action surface

Opening:

`Swan Song | Sensei's Divining Top | The One Ring | Island | Chain of Vapor | Chrome Dome | Island`

Rust frozen policy:

- Horizon, turn 6, trace length 60.
- The One Ring starts in the opening hand and is still in the final hand.
- No Rust Ring action appears in the trace.
- No Ring engine candidate appears in any recorded decision opportunity.
- Top is used repeatedly, but the first turn-1 Top cast opportunity is skipped in favor of Chrome Dome because the frozen semantic ordering chooses the lower-key cast.

Corrected Oracle diagnostic on the same physical order:

- wins turn 6 via `Chrome Dome`;
- casts The One Ring on turn 4;
- Ring draws 1 on turn 4;
- Ring draws 2 on turn 5;
- Voltaic Key untaps Ring;
- Ring draws 3 more on turn 5;
- Ring draws 4 on turn 6;
- total explicit Ring draws in the matched trace: 10 cards before the terminal line;
- later finds Transmute Artifact via Gitaxian Probe and converts Construct into Battered Golem as part of the winning development.

Interpretation:

This is not a policy-value miss alone. The coverage registry marks The One Ring `INTENTIONALLY_UNMODELED`, so the Rust player literally cannot reproduce the Oracle's major card-velocity engine.

## Case C — opening 13 / hidden 245416: Oracle builds Uthros + tutor infrastructure

Opening:

`Welding Jar | Island | An Offer You Can't Refuse | Ancient Tomb | Tormod's Crypt | Island | Battered Golem`

Rust frozen policy:

- Horizon, turn 6, trace length 63.
- final hand includes Merchant Scroll;
- no tutor decision is reached;
- no tracked card-advantage engine opportunity is reached;
- this same physical neighborhood is known to contain the exact two-deviation Rust terminal witness found earlier, proving the rules/terminal boundary itself is reachable.

Corrected Oracle diagnostic on the same physical order:

- wins turn 5 via `Chrome Dome`;
- turn 3: `Merchant Scroll -> Whir of Invention`;
- `Whir X=3 -> Uthros Research Craft`;
- immediately uses Uthros station activations;
- turn 4 onward, artifact casts repeatedly trigger Uthros draws;
- uses Urza spin to access Sensei's Divining Top;
- uses Top, Cam, Grinding Station, Battered Golem, mana artifacts, and repeated Uthros draws to build a much denser state before the turn-5 Chrome Dome terminal.

Interpretation:

This matched world demonstrates both feared gaps at once:

1. tutor sequencing can create a coherent engine (`Merchant Scroll -> Whir -> Uthros`);
2. the engine then converts subsequent artifact casts into card velocity.

Current Rust cannot reproduce this structural line because Uthros itself is `INTENTIONALLY_UNMODELED`, and the baseline never meaningfully deploys the Merchant Scroll sitting in its final hand.

## Cross-cutting finding — frozen policy spends reusable mana in upkeep

The matched Rust traces repeatedly show actions such as:

- turn 3 upkeep: tap Hydroelectric Specimen for mana;
- turn 3 upkeep: tap Oboro for mana;
- pass upkeep;
- pass draw;
- reach precombat main with those sources already tapped.

R4 `advance_phase()` explicitly resets `state.mana = ManaPool::default()` at phase advancement.

Therefore mana produced in upkeep is cleared before the precombat main phase while the sources remain tapped.

This follows directly from the frozen R5 class priority:

`PlayLand -> ProduceMana -> CastSpell -> ActivateAbility -> PassPriority`

Because `ProduceMana` outranks `PassPriority` in any ordinary priority window, the deterministic policy harvests reusable mana sources during upkeep even when there is no upkeep expenditure to make.

Consequences:

- existing lands/rocks are frequently unavailable during main phase;
- FTT cannot be leveled even when its permanent is already deployed;
- tutors and engines can remain stranded in hand;
- commander and combo development is delayed or prevented;
- this failure is global, not limited to one terminal family.

This is a policy defect, not a rules defect: the rules correctly clear mana between phases.

## Cross-cutting finding — modeled tutors prefer fail-to-find

The common staged search decision emits all eligible real targets and also the legal no-find action.

The policy bridge key is:

- real target: `kind=28, card=Some(CardDefId)`;
- fail to find: `kind=28, card=None`.

The frozen deterministic selector minimizes the semantic key. Rust `Option` ordering places `None` before `Some`, so fail-to-find is structurally preferred whenever it survives legality filtering.

Thus even after a tutor is successfully cast/resolved, the baseline selector can decline the search by construction.

## Cross-cutting finding — central card advantage is absent or partial

Confirmed missing intrinsic engines in current coverage:

- The One Ring — intentionally unmodeled.
- Uthros Research Craft — intentionally unmodeled.
- Mystic Remora — intentionally unmodeled.
- Rhystic Study — intentionally unmodeled.
- Faerie Mastermind — intentionally unmodeled.
- Witching Well draw engine — intentionally unmodeled.

Partial engine:

- Forensic Gadgeteer creates Clues and supplies activation reduction, but the CandidateBridge has no Clue sacrifice-to-draw action.

Modeled top/library engines:

- Fortune Teller's Talent.
- The Reality Chip.
- Sensei's Divining Top.

The matched FTT case proves that modeling the rules action is not enough: the policy must also value developing and using it.

## Diagnostic conclusion

The earlier 524,288 all-Horizon natural result should **not** be interpreted as evidence that real Urza openings rarely win in this model horizon.

At least four independent mechanisms strongly suppress natural wins before any sophisticated value model is considered:

1. major card-advantage engines are absent from the accepted rules/candidate surface;
2. Gadgeteer's Clues cannot perform their draw role;
3. modeled staged tutors are biased toward fail-to-find;
4. the frozen policy taps reusable mana during upkeep and starves its own main phase.

Additionally, modeled engine activations rank below all spell casts without terminal/engine-progress valuation.

The correct next phase is therefore not broader blind search. It is an audited gameplay-surface and baseline-policy repair gate, followed by a rerun of the same matched worlds and natural population before teacher/value conclusions are trusted.
