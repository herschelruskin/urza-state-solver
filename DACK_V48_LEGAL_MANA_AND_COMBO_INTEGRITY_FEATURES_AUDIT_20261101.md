# DACK v48 — turn-aware physical mana feasibility and combo-integrity feature audit

**Experiment performed: November 1, 2026 America/Toronto / November 2 UTC.**
**Status: IMPLEMENTED and independently PHYSICALLY TESTED as a read-only feature system. NO POLICY PROMOTION.** 
Isolated branch `dack-v48-turn-aware-legal-mana-features-20261101` based on the prior independent v43 research branch. Original v5/v27/v43 solver, frozen model and actual deck/card rules unchanged. Sealed 155k never opened.

## What was implemented (verified source, not conjecture)

### v48: strict no-future-draw turn-aware legal resource search
`dack_turn_aware_legal_mana_features_v48_20261101.py`

Searches actual legal installed engine actions on a canonical *multiset-derived* unknown 92-card library, **without accessing the actual physical hidden order**. Enumerates legally playable lands, artifact casting, land abilities, modal mana, restrictions, imprints, replacement effects, repeated activation, untaps and selected utility actions. Uses an exact immutable physical state/payments/colored-mana engine and bounded beam search: default beam48 depth10 (empirical tests beam32 depth9). T1 and T2 legal states are tracked separately, including turn reset, untap, upkeep and T2 without a top-deck draw. All valid strict witnesses must preserve the library tuple exactly, thus excluding random top cards, topdeck tutors, searches and scry from v48.

Each stage records:
- Exact T1/T2 reachable Dack-cast resource witness (2 white plus up to 4 generic with legal reductions).
- Maximum white mana, generic *after allocating WW* and commander-usable mana, plus same-state joint resources. **Independent maxima must not be added as if simultaneous.**
- Restricted artifact, legendary, and Dack-specific white mana remain distinct; Mox Opal requires metalcraft, Mox Diamond an actual discardable land, Chrome Mox a valid imprint, LED discards hand, and Gemstone legal exile/seat is inherited from actual installed rules.
- A **positive** is an actual physical engine-reachable no-draw state satisfying `d.can_cast_dack`. A negative is **NOT** a proof of infeasibility: bounded search and excluded future draws/tutors can miss lines.

The resource budget matched the installed exact Dack-cast predicate for **8192** independent synthetic mana pool/white/artifact/legend/Dack-white/Pearl states; [Actions #41383862848](https://github.com/herschelruskin/urza-state-solver/actions/runs/41383862848). Four mixed-source constructed hand smoke/reversal checks passed, [#41383095875](https://github.com/herschelruskin/urza-state-solver/actions/runs/41383095875).

### v48b: source-verified, guaranteed search-to-hand/battlefield resource
`dack_turn_aware_mana_tutor_guaranteed_v48b_20261101.py`

A second independent read-only feature extractor permits **only** engine-produced and verified library-search actions: Moonsilver Key, Expedition Map, Urza's Cave, Tezzeret or Urza's Saga. Checks source identity, physical card removed from remaining library multiset, matching hand/battlefield target, and legal grave/activation conditions before considering a successor. Canonicalizes remaining library order **only in the no-future-draw feature world**. Does **NOT** treat Enlightened Tutor putting a card on top as immediately accessible mana, does not assume a future lucky draw and does not assume the simulator is a fully exhaustive rules oracle.

An initial recursion bug during monkeypatch development was caught by Actions [#41383612769](https://github.com/herschelruskin/urza-state-solver/actions/runs/41383612769), corrected without touching prior code, and source/hidden-order/tutor provenance smoke passed [#41383701340](https://github.com/herschelruskin/urza-state-solver/actions/runs/41383701340).

### v48c: combo-library integrity and unmodified natural top-draw exposure
`dack_turn_aware_combo_draw_integrity_v48c_20261101.py`

Separately models how many of the three required combo creatures are in the kept hand, intentionally bottomed, or in the **unseen 92**, and the exact probability of avoiding creature contamination during one or two *unmodified natural draws*. For all three in unseen 92, two-draw survival:

`(89/92)*(88/91)=0.93549928`, 6.4501% raw natural-draw contamination risk.

This is **not an overall win probability**: tutors, scry, repair, additional draws, planned topdeck tutoring and action decisions change real conditional exposure. Legal London bottoming of a combo creature reduces this natural risk. Constructed and real-game tests passed [#41384250953](https://github.com/herschelruskin/urza-state-solver/actions/runs/41384250953).

## Prospective original physical forced-seven screen — 512 independent groups

These are *first-seven forced-keep* conditional actual-turn physical labels using the original full99 shuffled physical deck, original chance seed and installed strict beam160 T1/T2/T3 gameplay. Source IDs 168000..168255 and 169000..169255 are mutually disjoint, unused before these two experiments. Feature extractors see only the visible seven, seat, structural stage and 92 multiset. Actual physical future ordering is revealed only to the **separate subsequent physical label**, never the decision/feature routine. A single physical future per independent opening seven does not calibrate each hand's true probability.

| Metric | 168k N256 | 169k N256 | combined N512 |
|---|---:|---:|---:|
| Actual first-seven deployment T1 | 4 | 1 | 5 |
| Actual byT2 | 44 | 43 | **87** |
| v48 no-draw T2 mana witnesses | 15 | 14 | 29 |
| v48 no-draw witnesses actually byT2 | 15 | 13 | 28 |
| v48b verified-tutor no-draw T2 witnesses | not tested in 168k | 16 | — |
| v48b T2 witnesses actually byT2 | not tested in 168k | 15 | — |
| Combined best feature layer (v48 in 168k; v48b in 169k) | 15 | 16 | **31** |
| Combined witness actual byT2 | 15 | 15 | **30** |

v48b found **two new legal tutor-resource witnesses** in 169k: GID **169036** (Moonsilver Key to guaranteed target), Q2=0.5594143, and GID **169227** (Tezzeret search), Q2=0.8927007. Both deployed Dack on T2. The source-visible legal feature overhead was measured about **0.024 s per hand** in 168k and **0.028 s** in 169k; the v48b tutor extension averaged **0.0316 s** on 169k, approximate Python worker timings rather than full policy rollout cost. Four smoke and 8 physical independent N32 shards per cohort succeeded.

[Actions #41383301505, 168k](https://github.com/herschelruskin/urza-state-solver/actions/runs/41383301505);
[Actions #41383790146, 169k](https://github.com/herschelruskin/urza-state-solver/actions/runs/41383790146).
All raw N32 shard rows and pooled N256 source traces were PERMANENTLY committed on the branch by [archive #41383936987](https://github.com/herschelruskin/urza-state-solver/actions/runs/41383936987).

## The sole mana-witness-versus-physical disagreement was investigated, NOT ignored

GID **169051**: first seven `Chrome Mox / City of Traitors / Mox Opal / Fellwar Stone / Super State / Touch the Spirit Realm / Blast Zone`. The no-draw turn2 witness produced **W2 + C3 + flexible1** in the same legal state (Chrome Mox, Blast Zone, Fellwar Stone, Mox Opal, City of Traitors tapped). It is feasible to cast Dack based on mana alone and all three creatures still in the library.

The actual physical game drew **Bound by Moonsilver on T1 and Boonweaver Giant on T2**. Boonweaver leaving the library prevented the combo gate. The actual outcome was turn0 for both beam160 and beam384. [Independent replay #41384079672](https://github.com/herschelruskin/urza-state-solver/actions/runs/41384079672). **This was not an invalid mana allocation; it demonstrates why legal mana witness is not equivalent to future success.**

Another positive 168k case, **168202**, drew Preston on T2 yet succeeded physically, showing that repairing an exposed creature is possible. Thus future combo exposure should be a **probabilistic conditioned feature**, not a categorical always-fail label.

Independent postmortem across both archived cohorts, [Actions #41384352317](https://github.com/herschelruskin/urza-state-solver/actions/runs/41384352317), showed:
- **31** T2 no-unknown-draw mana witnesses, **30** realized byT2.
- **29** of these 31 had no combo creatures in their two natural top cards and **29/29** achieved byT2.
- **2** had a required creature in their natural top two, one repaired/succeeded, one did not.
- These are selected observational outcomes, NOT a proven 100% sensitivity/precision guarantee for all unseen hands.

Archived postmortem JSON: `benchmark_results/v48c_168k_169k_n512_draw_integrity_decomposition.json`.

## Does this recover historical v5's early KEEP decisions? **No.**

A labeled read-only retrospective audit of **26 already analyzed 151k v5/v43 first-two-seven disagreements** explicitly was *not* used to train, calibrate or prospectively validate. There were **10** cases where the actual original v5 final kept hand deployed byT2 and v43's did not. The strict legal no-draw mana and the extra source-verified search witness identified **0/10** of these as provable two-turn no-draw Dack casts. Of the **five** v5-only successes where v5 kept the comparison seven and v43 mulled, **0** had a no-draw verified tutor witness. Only **1/26** disagreements of either outcome class had a strict/no-draw T2 witness at all.

This does NOT mean all v5 keeps were good decisions, because the outcomes after different mulligan continuations are not direct counterfactual per-hand value labels. It *does* show that this particular witness system cannot by itself explain the original v5 policy gap or justify immediate override of v43.

[Completed retrospective Actions #41384521344](https://github.com/herschelruskin/urza-state-solver/actions/runs/41384521344); archived `benchmark_results/v48_readonly_151k_early_v5_v43_witness_coverage.json`.

## Architecture recommendation / disposition

- **Keep frozen v43 unchanged**. This v48 branch is a physical feasibility FEATURE EXPERIMENT, not a policy or a new win-rate benchmark. Do not train a model on the 512 single-future physical labels and claim robust v5 matching; too few meaningful uncommon-hand examples and a substantial exposed-outcome selection problem.
- The turn-aware engine resource budget is usable as a **verified legality foundation**. It separates 'how much raw mana?' from 'how much can legally pay W W + generic for Dack in the same state?' and distinguishes artifact-only/legend-only/Dack-white pools. The expanded tutor search is a verified, limited resource access feature—not a substitute for physical tutor/draw timing.
- **Next needed feature mechanism**: a turn-aware *information-state transition evaluator*. Model at least first natural draw, guaranteed next draw after **Enlightened Tutor/Loyal Tutor**, topdeck manipulation (Giant's Boulder, Brainstone, Scroll Rack) and legal combo-creature repair without peeking at unknown order. Use explicit branches and conditional probabilities over the remaining deck multiset, not a single fictitious 'known draw' state.
- Separate T1, T2, T3 forecasts, legal mana reachability, combo integrity probability and continuation value. Generate a **large, group-disjoint multi-future physical teacher set** covering unusual *low predicted-Q2* first/second-seven hands, instead of exclusively training on high-Q2 high-mana hands or model-margin triggers.
- Only after this feature system demonstrates retrospective explanatory coverage (as a development diagnostic) should a calibrated policy be trained on separate data and benchmarked prospectively with real early hand KEEP-versus-MULL regret and unchanged chance, across T1/T2/T3 and runtime. No v5 copied outcomes, no 155k access, and no promotion without matching those gates.
- Model goldfish Dack deployment is **not real multiplayer cEDH win rate or proof of downstream combo completion**. Beam and rules-search coverage are bounded.

## Exact source and artifact links on this branch

Source modules:
- `dack_turn_aware_legal_mana_features_v48_20261101.py`
- `dack_turn_aware_mana_tutor_guaranteed_v48b_20261101.py`
- `dack_turn_aware_combo_draw_integrity_v48c_20261101.py`
- Verification scripts and workflows in `dack_simulator/validation/v48*` and `.github/workflows/dack_v48*`.
- Permanently preserved `benchmark_results/v48_168k_raw/` (8 shards), `benchmark_results/v48b_169k_raw/` (8 shards), and two N256 pooled JSON reports, 512-group decomposition JSON, and historical read-only coverage JSON.

**Verdict:** We have demonstrated physically valid, fast, interpretable mana feasibility features and pinpointed their strategic coverage gap. We have NOT yet learned a superior early-seven mulligan policy. This is productive foundational progress, not a v43 or v5 performance breakthrough.
