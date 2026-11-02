# DACK v46 — physically calibrated first/second seven-card KEEP policy

**Predeclared 2026-11-01. Research only; no policy promoted.** Branch `dack-v46-early-seven-physical-calibration-20261101` isolates the experiment; v43 is the frozen baseline. 155k and all previous experiments untouched.

## Exact intervention and why

The old v43 coupled candidate-max rule improved early goldfish deployment compared with v27, but on the original v5-v43 *matched* 151k N128 games, v5's +8 net T2 advantage was entirely in 44 different London stopping-stage histories (+9), not 30 same-stage different-bottom histories (−1). Thirty-four of those 44 had first actual different KEEP/MULL at stage0, stage1 or stage2. v45's new independent physical futures at those 44 selected conflicts measured +8.42pp mean v5-action T2 advantage under frozen v43 future MULL continuation (95% two-source bootstrap −0.25 to +16.41 pp). These were **selected retrospective groups**, not unbiased hands.

v46 tests a very narrow new *real physical* T2 candidate: **only original London stage0 and stage1**, where all seven cards are kept or none are. These are the first and second 7-card hands, not the six-card stage. Stage0 is always seen; stage1 is seen **only after stage0 MULL**, so a full-policy outcome test must preserve that reachability. All bottom selection and KEEP after stage1 remain exactly frozen v43.

## Independent physical source design

- Train source independent physical 99-slot deal IDs `160000..160127` (N128). Development `160128..160191` (N64). Each supplies two *hypothetical* London seven-card states, stage0 and stage1, for source-group weighting. Dev and training group identifiers disjoint.
- For each group and stage, KEEP means **retain full seven, no bottom cards**. Draw all 92 other cards in 24 independently shuffled hidden future orders and strict 160-beam original rules, capturing physical deployment turn 0,1,2,3. N total 384 source group-stage states ×24 = **9,216 KEEP gameplay futures**. These are nested within 192 independent outer source groups, NOT 9,216 independent initial hands.
- For each seat in 0..3 and stage in 0..1, sample 128 separate, fully restored 99-card **MULL** continuations; each future London seven is independently re-dealt, and all subsequent KEEP/bottom decisions use immutable v43. Eight seat-stage cells ×128=**1,024 C gameplay futures**, shared correctly across source groups.
- **Important anti-leakage split:** the first 64 C futures per cell estimate the fixed physical MULL baseline used by the model at deployment. The last 64 C futures, independently sampled, are never used to fit/choose and are reserved solely for evaluation. The development-stage estimates are bootstrapped by physical source group, within-group K trial and shared 64 C-eval futures.

## Frozen experimental fit

Model is a compact 80-tree depth7 minleaf8 random forest on physically estimated `PbyT2(KEEP) - frozen_v43_Q2`, with canonical v13 line-aware features excluding literal `seven:<card>` and `bottom:<card>` one-hot columns. Includes original frozen v43 Q2 as predictor. No v5 teacher actions or labels.

For eligible stages, corrected physical QKEEP = clip(original v43 Q2 + 0.5 × clip(learned T2 residual,−.25,.25),0,1). Compare to physical C value from **C-train64**; override v43 only if corrected-Q minus C is at least 6pp in magnitude. Otherwise leave frozen v43 action. This is a fixed policy, no threshold search on dev.

Dev gate was fixed before outcomes: nonzero changes, mean physically observed conditional byT2 one-step delta (v46 minus v43) **strictly positive** over the two stages equally weighted, and byT3 at least −2pp. This is merely permission to perform fresh whole-policy follow-up; it is **not** a promotion gate or a statistically powered proof.

## Full policy evaluation if dev passes, never otherwise

The full-policy follow-up is already coded for independent never-before-used physical deals `161000..161255` (N256): separate interpreter per frozen v43 or v46, exactly matched starting 99 slots, seat, original stable dice and strict beam160 game engine, no v5 mulligan lookahead. Report exact T1/byT2/byT3, card count at KEEP, actual number of stage1 visits in each policy, paired bootstrap 95% interval, and changes to London stopping stages. Do not claim parity with v5 unless original v5 is evaluated on same physical hands. Do not open 161k if dev directional gate fails.

## Mandatory caveats

- Stage1 is a *hypothetical* observed state for every training source group, but is naturally reached in actual gameplay only after stage0 mulligan. Development stage-level T2 improvement is **not** a full-game win-rate gain.
- Shared C is one seat-stage lottery, not 128 independent hand-specific values. Group/KEEP/C resampling avoids false precision.
- Physical beam160 goldfish Dack deployment is not actual multiplayer cEDH match win probability.
- Optimizing against stage0/1 outcomes can overfit low sample N128 training groups; forest is regularized/shrunk and corrections are deadband-limited, not assumed accurate. Even if development passes, N256 is required to check actual policy gain and the CI will still be broad.
- One- or two-card deck substitution transfer not established.
- Original v5, v27, v33b and v43 benchmark outputs, feature schema, and selected cohort histories stay immutable.
