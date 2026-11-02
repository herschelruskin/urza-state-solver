# DACK v43 — independent source audit, model-consistency diagnosis, and strict physical sensitivity

**Audit completed 2026-11-01 America/Toronto / 2026-11-02 UTC.**
**Disposition: retain frozen v43 as the strongest confirmed fast challenger. No new policy promoted.**
This is a goldfish Dack-deployment simulator audit, not a cEDH multiplayer win-rate estimate.
Audit branch: `dack-v43-independent-audit-20261101`, based on `dack-v46-early-seven-physical-calibration-20261101`; historical solver/model files unchanged. The sealed 155k cohort was not used. This report clearly separates implementation facts, matched physical outcomes, model-only measurements, and open hypotheses.

## Actual source and archive reviewed

- `dack_paired_counterfactual_v43_v27_max_Q2_20261101.py`, `dack_paired_counterfactual_v27_T2_only_DP_20261101.py`, `dack_paired_counterfactual_v22_all_stage_real_keep_DP_20261101.py`, `dack_simulator/validation/collect_teacher_london_v13.py`, `dack_simulator/validation/derive_T2_only_continuation_v23.py`, `dack_simulator/validation/train_v27_T2_only_expanded.py`, `dack_mulligan_teacher_features_v13_20261031.py`, `dack_paired_counterfactual_v1_20261030.py`, `dack_boonweaver_aura_exile_guard_20261029.py`, `dack_counterfactual_rules_v1_20261030.py`, and actual installed rules/pregame patch stack.
- Frozen `models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json` and `models/dack_v27_T2_only_continuations_EXPERIMENTAL.json`. The former was trained on v14-selected bottom alternatives, 2048 source stage states from 256 original groups and 4 real physical futures/state, not thousands of independent hands.
- Archived v43/v45/v46 postmortems and matched physical result files; no historical cohort reused as a new acceptance test.

## Confirmed mechanical facts and new reproducible tests

**London mechanics**: `STAGES=(7,7,6,5,4,3,2,1)`, first multiplayer London mulligan is free, each stage constructs a fresh seven from its own full canonical 99-slot permutation, exactly 92 unseen slots remain, kept hand plus unknown92 plus ordered bottom reconstructs 99 physical cards. The v43 policy observes seven, seat, deck multiset and stage but not actual unknown92 order. Its selected hand and bottom are legal, and the decision compares *that selected candidate's* frozen v27 Q2 to the archived seat-stage continuation. This fixes v27's candidate/keep scoring inconsistency.

**New deterministic audit**, [Actions #41374177634](https://github.com/herschelruskin/urza-state-solver/actions/runs/41374177634): development GIDs 162400–162411 (12 distinct physical decks), 96 stage-state whole-99 checks, 1,536 legal candidates checked by exhaustive enumeration, 12 hidden92 permutation invariance tests, and exact candidate/threshold/decision parity on 33 naturally reached stage decisions. All passed. This does not prove downstream strategy search completeness.

**Colored mana / executable-combo gate**, [Actions #41375444909](https://github.com/herschelruskin/urza-state-solver/actions/runs/41375444909): explicit two-white-plus-generic regression, colored/restricted-source negative controls, all three mandatory combo creatures in library, protected Aura and Gleaming Splendor exile rejection. Strict beam160 terminal states captured and rechecked for all 24 independent development goldfish GIDs 162700–162723 (1 T1, 13 byT2, 21 byT3); no unwitnessed terminal deployment. This demonstrates the *modeled Dack cast gate*, not execution of the whole downstream combo in real cEDH. Beam160 can miss legal lines.

**Gemstone Caverns apparent issue resolved without changing rules**: the older underlying engine selects one deterministic imprint, but the installed inherited pregame rules already enumerate the alternative safe exiles. Our initial assay incorrectly assumed the older one-choice code remained active, and [run #41374623645](https://github.com/herschelruskin/urza-state-solver/actions/runs/41374623645) failed that test assumption. The corrected [run #41374724725](https://github.com/herschelruskin/urza-state-solver/actions/runs/41374724725) passed: the installed runtime and independent safe-exile enumeration both expose 3 choices in a deterministically constructed protected-Aura witness. Across four deliberately selected development Gemstone+protected-Aura sevens, each with 24 strict blind physical futures, exactly 12/96 byT2 outcomes in each arm and zero discordant outcomes. **No Gemstone legal-exile defect established.**

## Candidate screening — genuine but limited physical issue

The structural top-12 candidates are legal, but they exclude the frozen Q2 model's own full-search maximizer on hypothetical keep-five (3/12), keep-four (2/12) and keep-three (1/12) stages in the small GID 162400–162411 audit. No such omission exists on either seven-card London stage (one legal candidate) or six-card keeps (seven legal candidates).

Example: GID 162403, hypothetical keep-four from Urza's Saga, Great Hall of the Citadel, Enlightened Tutor, Gemstone Caverns, Fellwar Stone, Giant's Boulder, Jeweled Amulet. Original top12 bottom (Urza's Saga, Great Hall, Jeweled Amulet): predicted Q2 .45200. Full-legal excluded bottom (Urza's Saga, Giant's Boulder, Jeweled Amulet): Q2 .50892. [Strict independently sampled beam160 physical comparison #41374418888](https://github.com/herschelruskin/urza-state-solver/actions/runs/41374418888), 32 matched hidden92/chance futures: excluded candidate was **+4 unique T2, 0 losses** vs original top12. This was an explicitly chosen *hypothetical stage not actually reached* by normal v43 for that GID: not a causal, population-wide, or full-policy benefit.

On naturally reached keep-four stages 162408 and 162409, v43's chosen max-Q2 top12 candidate beat the structural-first candidate by 14 and 3 unique T2 deployments respectively in 32 matched futures per state (0 alternative-only wins). A simple structural bottom rule is not a viable replacement.

## Continuation-value architectural mismatch — confirmed, quantified

v43 evaluates `max_{c in structural_top12} Q27(c)` to KEEP but compares it to the **frozen v27/v14-bottom-policy continuation DP**. The formal optimal continuation comparison for a candidate-max policy is `max_c Q(c) >= E[max(max_c Q(c_next), C_next)]` under the *same* policy, seat, deck and stage, subject to correct calibration of Q. The existing DP violates this policy consistency, not a game-rule legality constraint.

[Run #41375264582](https://github.com/herschelruskin/urza-state-solver/actions/runs/41375264582): on 1,024 independent model-only development outer physical groups 163700–164723, same groups and seats for frozen v27 bottom selection versus v43 Q2-max, all stages evaluated in a leave-the-frozen-estimator-unchanged fashion, with 500 outer-group bootstrap samples per seat. The within-sample v43 minus v27 model-implied *first seven* continuation cutoff was:

| Seat | v27 recalculated C7 | v43 max-Q2 C7 | paired delta | group-bootstrap 95% delta CI |
|---|---:|---:|---:|---:|
| 0 | .36463 | .41059 | +.04597 | [.03879,.05413] |
| 1 | .38696 | .43747 | +.05051 | [.04203,.05948] |
| 2 | .42401 | .46827 | +.04426 | [.03681,.05299] |
| 3 | .38947 | .43906 | +.04959 | [.04166,.05793] |

The within-sample second-seven v43-minus-v27 C6 differences were +.05674, +.06173, +.05697, +.06163 for seats 0–3. The bootstrap intervals measure **model-based DP sampling uncertainty**, not real-world truth, especially given candidate max and out-of-distribution v27 predictions.

The archived frozen v27 thresholds differed somewhat from recalculated same-sample v27 cutoffs (sampling cohort drift); using this matched control isolates the effect of candidate-selection architecture. Revised cutoffs are generally higher, consistent with increased value of the option to mulligan and choose a better future hand. **Do not simply deploy this revised DP; predicted maxima can be overoptimistic.**

## Strict physical sensitivity: frozen v43 vs model-only self-consistent DP

[Actions #41375350434](https://github.com/herschelruskin/urza-state-solver/actions/runs/41375350434) rederived every v43-model-consistent DP stage/seat cutoff on 163700–164723 and compared an alternative differing **only in cutoff table** against frozen v43 on independent source GIDs 164800–164863 (N=64). Both arms used the same 99-slot deals, seat, strict original beam160 and stateless game chance; no fitted model or card list was modified. Unchanged retained hands enforced exact outcome/future-order parity.

| Metric | Frozen v43 | Recomputed model-only DP |
|---|---:|---:|
| T1 | 4/64 | 4/64 |
| byT2 | 32/64 | 34/64 |
| byT3 | 53/64 | 52/64 |
| mean cards kept | 5.4375 | 5.0000 |

Sixteen games changed final hand/stage. byT2 had 3 alternative-only games and 1 v43-only game: **+2/64 = +3.125 pp**, paired bootstrap 95% CI **[-3.125,+9.375] pp**; byT3 -1/64, CI [-9.375,+6.25] pp, and T1 unchanged with no discordant outcomes. This is **small-N diagnostic sensitivity only**; the positive T2 direction is not statistically persuasive, and 0 discordant T1 does not establish T1 equivalence. No policy promoted.

## What is known about original v5's remaining gap

Original archived matched 151k 128-deal cohort: v5 byT2 73/128, v43 65/128, 13 v5-only and 5 v43-only, net +8, exact two-sided paired McNemar p approximately .096. It is a suggestion, not a conventionally established v5 superiority on this small matched set. In the same archive, 44/128 different kept London stages yielded +9 net v5 T2, 30 same-stage different bottoms yielded -1 net, and 54 identical retained hands had exact gameplay parity. The 34 earliest conflicts in stages0–2 yielded +10 net T2 to v5. Stage-selection gaps dominate this **descriptive decomposition**.

The archived v45 deliberately selected 44 first action conflicts and used 1,408 new conditional physical KEEP futures and 960 shared full99 post-MULL continuations; conditional v5 action advantage +8.416pp T2 with 95% two-source CI [-.249,+16.406] pp. This cannot be expanded into a full-population claim and does not show v5 decisions are always superior. v46 average early-seven physical residual forest corrected almost no real decisions: new 161k N256 T2 parity 121/256 each, 3 changed final stages.

Other archived first-disagreement examples illustrating *candidate classes, not proving specific mechanisms*:
- 151009: v43 predicted first-seven Q2 .0938 vs its .3642 cutoff and mulled; original v5 kept (sample U .8125) and physically deployed T2, while v43's later hand did not. Gemstone Caverns + Mox Diamond + Coalition Relic and two Plains appear; conceivable under-recognized staged mana.
- 151022: v43 mulled at stage0 (Q2 .3017 <.3796) a Grim Monolith/Mishra's Workshop/Moonsilver Key/Mycosynth Gardens hand; original v5 kept and deployed T2, v43 later deployed T3. Candidate for unusual sequencing feasibility tracing.
- 151012: v43 kept an initial seven containing Preston, the Vanisher + Brainstone + Lion's Eye Diamond at Q2 .4409 >.3642; original v5 mulled and deployed T2, v43 did not by T3. This is consistent with overvaluation of an awkward combo-component hand but does not prove causality.

These examples are retrospective, selected from already inspected 151k; original-v5 U and v43 Q2 are **different utilities** and cannot be subtracted as comparable probability estimates.

## Priority-ranked residual risks and actions

1. **High severity, proven architectural mismatch, moderate correction cost:** Current v43 KEEP/Q2 maximizer uses continuation fitted to v14-bottom v27 policy. New matched DP and strict N64 sensitivity confirm substantive changes in keeping policy. Do not patch frozen baseline or promote on N64; require substantially larger independently frozen prospective physical evaluation, ideally with original v5 paired on the same deals, plus calibration with actual physical KEEP and MULL futures under exact downstream policy.
2. **High potential severity, partial evidence, moderate engineering cost:** Rare real early-seven hands with sequencing/colored-mana/tutor/combo-state interactions may be misranked by v27 RF (only four physical futures per training state, fitted to a different bottom distribution). Build bounded **visible-hand, legality-first T1/T2 reachability witnesses** with no hidden draws, and only invoke more expensive bounded search/future sampling on *observable* ambiguous or high-regret-risk hands. Measure actual action regret and full-game frequency, not agreement with v5 labels.
3. **Moderate severity, physically observed selected-case defect:** Structural top12 can exclude higher-valued and occasionally physically stronger bottom alternatives for keep3–5. Before broadening all calls, test selective candidate expansion on naturally **reached** stages and evaluate costs and full-policy outcomes. It cannot alone explain the first/second seven gap.
4. **Moderate/high external-validity uncertainty:** beam160 and search heuristic are not an exact proof of all possible legal lines. Recheck a sample of misses using deeper beam/bounded exhaustive witnesses. Current deployment gate enforces modeled Dack cast and protected cards, not verified completion of the entire combo under multiplayer interactions.
5. **Moderate measurement/power risk:** N256 can support a sizable paired difference (v43 vs v27 initial +11/256 was supported) but generally underpowers rare 1–2pp effects; repeated development cohorts are not untouched. Treat outer physical deal as independent unit; resampled futures share source seven and shared MULL-continuation cells and must be clustered/grouped, not counted as separate independent hands.
6. **Objective caveat:** v43's fitted/optimized reward is P(byT2), which assigns equal incremental weight to T1 and exact T2. If T1 is especially valuable, predeclare an explicitly T1-weighted objective (and appropriate T3 weight) before training or threshold adjustment. Goldfish success does not estimate actual four-player cEDH win probability.

## Decision

**Keep frozen v43 unchanged.** It genuinely fixes v27's self-inconsistent candidate/KEEP action and had a fresh paired +4.30pp byT2 advantage on 151k N256. Its main confirmed defect is **policy-inconsistent offline continuation**. A physically evaluated, self-consistent continuation architecture, augmented by selective bounded line feasibility for rare early-seven combinations, is the most grounded next direction—not a generic new forest or v5 imitation. The isolated N64 DP test is encouraging but far too uncertain for promotion. Preserve 155k and all historical reference models.

### Reproducibility and artifacts

All new files are confined to this isolated branch:
- `dack_simulator/validation/v43_readonly_candidate_invariants_20261101.py`
- `dack_simulator/validation/v43_conditional_candidate_physical_20261101.py`
- `dack_simulator/validation/v43_gemstone_pregame_physical_audit_20261101.py`
- `dack_simulator/validation/v43_independent_continuation_selfconsistency_20261101.py`
- `dack_simulator/validation/v43_model_only_DP_physical_sensitivity_20261101.py`
- `dack_simulator/validation/v43_terminal_witness_audit_20261101.py`
- Matching six `.github/workflows/dack_v43_*_20261101.yml` files and GitHub Actions job outputs.
- Raw full conditional gameplay turns, model-only DP seat/stage confidence intervals, physical N64 paired game histories, and actual terminal witness states were uploaded by successful workflows as GitHub Actions artifacts. They remain subject to GitHub Actions artifact retention; this Markdown report and source/tests are committed permanently to the audit branch. The reproducibility seeds and sample IDs are in source.
