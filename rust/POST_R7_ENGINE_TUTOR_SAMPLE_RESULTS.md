# Post-R7 Engine / Tutor Opportunity Sample Results

Diagnostic-only checkpoint. No gameplay or policy semantics are changed by this file.

## Provenance

- workflow: `Post-R7 engine tutor diagnostic`
- run: `34161448192`
- head: `fa9754e84be5465534d7fb1d60d7a8c1b7524968`
- opening offsets: 0..15
- hidden worlds per opening: `245632..245639`
- total natural frozen-policy rollouts: **128**
- total frozen-policy decisions replayed and audited: **5,422**
- terminal worlds: **0**
- incomplete rollouts: **0**

The sampler observes the exact production CandidateBridge at every frozen-policy decision. `visible_decisions` means an engine card was legally visible in hand, battlefield, or known top. `candidate_decisions` means at least one production policy candidate for that card existed at that decision.

## Aggregate engine results

| Engine | Visible decisions | Candidate decisions | Selected decisions | Cast candidate | Cast selected | Activation candidate | Activation selected |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| The Reality Chip | 452 | **0** | 0 | 0 | 0 | 0 | 0 |
| Forensic Gadgeteer | 110 | **0** | 0 | 0 | 0 | 0 | 0 |
| The One Ring | 585 | **0** | 0 | 0 | 0 | 0 | 0 |
| Fortune Teller's Talent | 804 | 18 | 17 | 18 | 17 | **0** | 0 |
| Uthros Research Craft | 920 | **0** | 0 | 0 | 0 | 0 | 0 |

### Interpretation

**The One Ring and Uthros**

The zero-candidate result is expected from the audited coverage registry: both are currently `INTENTIONALLY_UNMODELED`. Their large visible counts demonstrate how often the frozen policy carries or sees strategically valuable cards that cannot express their actual engine actions.

**Reality Chip**

Reality Chip is modeled, so 452 visible decisions with zero production candidates is especially important. Opening offset 12 begins with Reality Chip in the opening seven:

`Island | Flooded Strand | Hope of Ghirapur | Dramatic Reversal | The Reality Chip | Misty Rainforest | Sapphire Medallion`

Across its eight hidden worlds the Chip is visible for 308 audited decisions but never becomes a CandidateBridge action. This is consistent with the matched-trace phase-starvation diagnosis: reusable mana sources are tapped during upkeep, mana empties at phase advancement, and the main phase arrives with the sources tapped. A modeled two-mana engine can therefore remain visible but never become legally payable at the main-phase action window.

**Fortune Teller's Talent**

FTT is visible for 804 decisions. It produces 18 cast opportunities and the frozen policy takes 17 of them, so the problem is not primarily willingness to cast a one-mana FTT.

However, there are **zero FTT activation/level opportunities across all 128 rollouts**. The matched opening-6 trace showed the same pattern directly: FTT is cast, then reusable mana is harvested in upkeep and unavailable for main-phase leveling. The Oracle on that same physical world develops FTT to level 3 and wins with `Top + FTT L3`.

**Forensic Gadgeteer**

Gadgeteer is visible for 110 decisions but produces zero candidates in this population. The card is rules-active, so—as with Chip—this is compatible with mana-window starvation preventing its three-mana creature cast. Separately, even when Gadgeteer is deployed in other searched branches, the accepted CandidateBridge lacks the Clue `2, sacrifice: draw a card` action, so the modeled Gadgeteer remains an incomplete card-advantage engine.

## Tutor results

The 128-world sample reached **37 staged library-search resolutions**.

| Tutor source | Resolutions | Fail to find (`NONE`) | Real targets selected | Total candidate actions at those decisions |
| --- | ---: | ---: | ---: | ---: |
| Urza's Saga | 21 | **21** | 0 | 441 |
| Mystical Tutor | 14 | **14** | 0 | 311 |
| Whir of Invention | 2 | **2** | 0 | 22 |
| **Total** | **37** | **37** | **0** | **774** |

This is a population-level confirmation of the semantic-key audit:

- every staged tutor decision had real search targets available;
- the common bridge also supplied legal `ChooseSearchTarget { target: None }`;
- the deterministic selector chose `NONE` in **37/37** resolutions;
- **774** total candidate actions existed across those decisions, yet not one real card was selected.

Therefore the current baseline does not merely tutor poorly. For modeled staged tutors it systematically **fails to find** by construction.

### Concrete opening examples

- Opening 0: Urza's Saga resolved twice; both searches chose `NONE` despite 41 total candidates.
- Opening 4: Mystical Tutor resolved eight times; all eight chose `NONE` despite 175 total candidates.
- Opening 8: seven Saga searches, one Mystical Tutor, and one Whir search all chose `NONE`; 186 total candidates across those decisions.
- Opening 9: eight Saga searches all chose `NONE` despite 162 total candidates.

## Combined with matched Oracle traces

The sample should be interpreted together with run `34161117326`:

1. **FTT matched world** — Rust casts FTT but never levels it; corrected Oracle wins turn 5 through `Top + FTT L3`.
2. **Ring matched world** — Ring begins in Rust's opening hand, never appears as a Rust candidate, and remains in hand; corrected Oracle draws ten cards from Ring before its turn-6 terminal line.
3. **Positive-neighborhood matched world** — Rust ends with Merchant Scroll unused; corrected Oracle uses `Merchant Scroll -> Whir -> Uthros`, converts later artifact casts into Uthros card velocity, and wins turn 5.

These are structural comparisons, not production-policy instructions. Oracle is clairvoyant and remains an upper-bound diagnostic only.

## Diagnostic conclusion

The historical 524,288 all-Horizon natural sample cannot support a meaningful claim about the deck's real win probability. The frozen baseline is suppressing game development through multiple independent mechanisms:

1. **phase starvation:** reusable mana is produced in upkeep, then cleared before main phase while sources remain tapped;
2. **tutor degeneration:** 37/37 sampled staged tutors fail to find despite hundreds of real candidates;
3. **missing card-advantage surface:** Ring, Uthros, Remora, Rhystic, Mastermind, and several draw activations are absent;
4. **partial card-advantage surface:** Gadgeteer creates Clues but cannot sacrifice them to draw;
5. **non-strategic action ranking:** all spell casts outrank all engine activations when the stack is empty.

The clean next experiment is to repair the two policy-correctness defects that require **no expansion of Magic semantics**:

- preserve reusable mana sources through upkeep/draw unless a current decision actually needs mana;
- stop the deterministic tutor baseline from preferring legal fail-to-find over available real targets.

Then rerun the same matched worlds and this same opportunity sampler. Only after measuring that delta should Ring/Uthros/Clue and the remaining card-advantage rules be broadened, so policy defects and missing mechanics remain separately attributable.
