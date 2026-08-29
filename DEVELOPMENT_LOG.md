# Urza Solver Development Log

This file is the persistent checkpoint for architecture, validation, and next work.
Update it whenever a phase changes the model materially.

## Current target

**Phase 5I — London mulligan valuation under the frozen Phase 5H player**

Goal: evaluate keep/mull and London-bottom decisions using the validated gameplay
policy without training or tuning against the human labels.

## Architecture status

| Layer | Status | Notes |
|---|---|---|
| Rules / true state | mature | Explicit mechanics and terminal families remain authoritative. |
| Observation boundary | mature | True state and player observation are separated. |
| Hidden-world MC | mature | Common random worlds; explicit reproducible seeds. |
| Value model | mature | T1..T6 distribution-valued V/Q objective. |
| London mulligan DP | **Phase 5I integration active** | Sequential keep/mull + bottoming, floor at keep 2, now valued by frozen 5H player. |
| Opening context | implemented | Commander seat context + Gemstone Caverns pregame decision. |
| Library knowledge | implemented | Exact remaining multiset is logically deduced; order remains hidden. |
| Selective tutor Q | implemented | Tutor/search states only; deterministic v6 remains leaf policy. |
| Bounded contingent Q | implemented | Dependent post-commit choices only; Transmute sacrifice -> target bounded chain. |
| MC confirmation | implemented | Screen and confirmation use disjoint hidden-world namespaces. |
| Confidence-gated Q | **validated / frozen** | Phase 5H passes paired held-out validation. |
| Frozen production player | **implemented** | Named Phase-5H configuration used by downstream evaluators. |
| Human mulligan validation | **running** | 35 exact usable hands; human labels held out from scoring. |

## Branch / PR stack

1. Phase 2 non-Oracle runtime — PR #10
2. Phase 3 distribution-valued V/Q + human baselines — PR #11
3. Phase 4A hidden-world sampler — PR #12
4. Phase 4B root Monte Carlo — PR #13
5. Phase 5A mulligan DP — PR #14
6. Phase 5B runtime parity + selective tutor-Q — PR #15
7. Phase 5C adaptive mulligan / tutor-Q diagnostics — PR #16
8. Phase 5D Commander seat + Gemstone Caverns — PR #17
9. Phase 5E bounded contingent two-step tutor-Q — PR #18
10. Phase 5F deduced library membership — PR #19
11. Phase 5G independent MC confirmation — PR #20
12. Phase 5H adaptive confidence-gated selective Q — PR #21 / frozen gameplay architecture
13. Phase 5I frozen-Q London mulligan — branch `phase5i-mulligan-frozen-q` (**current**)

## Locked design principles

- Never expose exact hidden library order before a legal observation.
- Exact remaining-card membership in our own library is logically deducible.
- Q improves policy; it does not replace the rules engine or broad deterministic leaf.
- Common hidden worlds compare candidate actions fairly.
- v6 wins exact ties.
- Dependent lookahead is legal only after information becomes observable.
- Do not expand Q depth merely because more search is possible.
- T6 is inclusive search horizon; T7 is not expanded as a win.
- Protection and speed are separate eventual outputs; a fast naked win may still be valid.
- Human mulligan labels are evaluation data, not policy inputs.
- Commander seat must be conditioned before optimization; do not average Caverns-live and Caverns-dead states before choosing a bottom/keep line.

## Phase 5H validation — COMPLETE

Final corrected tutor-rich held-out benchmark: **10 hands x 4 paired worlds = 40 worlds**.

| Policy | T6 wins | Rate |
|---|---:|---:|
| rollout-v6 | 5 / 40 | 12.5% |
| Phase 5H one-step Q | 12 / 40 | 30.0% |
| Phase 5H bounded contingent Q | 14 / 40 | 35.0% |

Paired-world quality comparisons:

| Comparison | Better | Tie | Worse |
|---|---:|---:|---:|
| 5H one-step vs v6 | 8 | 32 | **0** |
| 5H contingent vs v6 | 10 | 30 | **0** |
| 5H contingent vs 5H one-step | 2 | 38 | **0** |

Interpretation:

- confidence gating improves aggregate selective-Q performance beyond the previous
  independent-confirmation controller;
- bounded contingent lookahead is now a net positive rather than a net negative;
- no observed paired held-out world regressed relative to v6;
- no observed paired held-out world regressed from one-step to contingent Q;
- the prior hand-24 Reshape gain was rejected as insufficiently supported;
- robust contingent-only gains appear on hands 21 and 29;
- hand 20 improved strongly from v6 1/4 to 5H Q 4/4;
- hand 25 rerun after the Chain/Offer stack fix completed cleanly at 2/4 for all
  policies, with Q still better on distributional timing in one paired world.

Phase 5H also exposed and fixed a typed-runtime parity defect: Chain of Vapor /
An Offer You Can't Refuse stack objects now resolve only on an actual priority pass
rather than intercepting every legal priority action above them. Production CI is
green including a typed priority-activation regression.

**Decision:** gameplay-policy architecture is frozen at Phase 5H. Do not add deeper
Q before end-to-end mulligan and deck-level validation demonstrates a need.

## Frozen Phase 5H production player

`phase5_production_policy.py` defines the exact downstream player instead of relying
on constructor defaults:

- tutor-Q screen rollouts: 1;
- independent confirmation rollouts: 2;
- shortlist size: 3;
- bounded contingent lookahead: enabled;
- paired confidence gate: enabled;
- adaptive validation: 2 -> 4 -> 8 cumulative worlds;
- one-sided paired sign threshold: alpha = 0.25;
- deterministic rollout-v6 remains the leaf/fallback policy.

Production identity: `urza-phase5h-production-policy-v1`.

## Phase 5I implementation checkpoint

### Production London evaluator

`phase5i_mulligan.py` adds a new production path and leaves the historical
`phase5_adaptive_mulligan.py` experiment unchanged for provenance.

Properties:

- bottom screening and confirmation both use the exact same frozen 5H player;
- screen/confirmation outer hidden-world windows are disjoint;
- exact finite-sample screen ties survive the shortlist cutoff;
- shared strategic Q cache is reused across equivalent opening evaluations;
- London keep-two floor remains stage 6;
- backward stage DP compares K_s(hand) against independently estimated V_{s+1}.

Phase 5I integration regression suite passed before benchmark launch, including
Phase-5H Q, parent mulligan, Caverns/seat, Chain/Offer, information-state, strategic
state, human fixture, and Phase-1 acceptance checks. The full benchmark toolchain
is also included in production compile CI.

### Human hand benchmark — active

Evaluation branch: `phase5i-human-hand-eval`
Workflow run: **33122937057**

Scope: all 35 reconstructable exact human hands (hand 10 remains permanently
excluded because the stored seven/bottom annotation cannot be reconciled).

Per-hand budgets:

- outer bottom screen: 1 world;
- outer bottom confirmation: 3 fresh worlds;
- bottom shortlist: 4 plus all exact screen ties;
- frozen internal Phase-5H Q budgets as listed above;
- horizon: T6 inclusive.

The solver selects its own bottom before the human bottom is used. If the recorded
human bottom was pruned, it is evaluated afterwards on the identical confirmation
outer worlds only for diagnostic rank/regret; it cannot change the solver choice.

Because the human source does not record Commander seat:

- hands containing Gemstone Caverns are valued separately as seat 1 / Caverns dead
  (25% ex ante) and representative seat 2 / Caverns live (75% ex ante for seats 2-4);
- non-Gemstone current hands share the same K_s under current mechanics;
- keep-vs-mull can STILL differ by seat even for a non-Gemstone current hand because
  the continuation V_{s+1} can draw Gemstone. Final decision scoring therefore keeps
  separate dead/live continuation thresholds.

Early sanity-check outputs (not final probabilities; confirm n=3 is deliberately
coarse):

- hand 1: K_s T6 estimate 0/3, human Keep, stage 1;
- hand 2: 0/3, human Mulligan, stage 1;
- hand 3: 0/3, human Mulligan, stage 0;
- hand 4: 0/3, human Mulligan, stage 1;
- hand 7: 0/3, human Keep, stage 0;
- hand 22: 1/3, human Mulligan, stage 0;
- hand 30: 2/3, human Keep, stage 1;
- hand 34: solver bottoms Mana Drain, human-bottom diagnostic rank 3, best K_s 1/3;
  human decision Keep, stage 2.

Do not interpret 0/3, 1/3, 2/3 as precise deck probabilities. These per-hand values
are primarily paired action-ranking evidence at this budget.

A display-only keep-size bug in the first human evaluation branch used `7-stage`
in one context metadata field. It does not affect simulation or action selection;
the base Phase-5I script now uses `keep_size_for_stage`, and aggregation uses the
authoritative fixture keep size.

### Independent continuation thresholds — active

Evaluation branch: `phase5i-stage-model-eval`
Workflow run: **33123014572**

Four independent jobs are being fit:

- Caverns-dead / seat 1, replicate 0;
- Caverns-dead / seat 1, replicate 1;
- Caverns-live / representative seat 2, replicate 0;
- Caverns-live / representative seat 2, replicate 1.

Each replicate currently uses:

- 2 fresh sampled sevens per London stage;
- bottom screen 1 outer world;
- bottom confirmation 2 fresh outer worlds;
- shortlist 4;
- frozen Phase-5H player;
- no human labels.

This is intentionally a pilot threshold estimate. Replicate disagreement will be
checked before keep/mull agreement is treated as meaningful. If stage decisions are
unstable, increase independent stage sampling rather than tuning toward human labels.

### Aggregation

`phase5i_benchmark_aggregate.py` is implemented. Once both evaluation families are
complete it will report:

- overall 25/75 seat-weighted keep/mull agreement;
- dead/live seat-conditioned decisions;
- per-stage agreement;
- replicate-level threshold decision stability;
- bottom exact-match rate;
- human-bottom diagnostic rank;
- bottom value regret;
- per-hand disagreement rows.

## Phase 5I acceptance criteria

1. Production 5H policy/config remains frozen throughout validation.
2. Human labels never enter value estimates or continuation thresholds.
3. All 35 exact usable human hands evaluate without runtime blockers.
4. Independent continuation replications are inspected for stability.
5. Bottom disagreements are inspected by value regret/rank, not exact-match alone.
6. Keep/mull disagreements are classified before any human-supervised policy change.
7. If the model remains substantially below human gameplay after mulligan integration,
   proceed to broad end-to-end trajectory gap analysis rather than blindly adding Q depth.

## Roadmap after Phase 5I

1. Finalize 35-hand human benchmark summary and inspect disagreement classes.
2. Run the first full end-to-end 250 / 1,000+ deck simulations.
3. Compare win-turn distribution to the historical 250-goldfish baseline.
4. Diagnose residual policy/rules coverage gaps from trajectory failures.
5. Add protection / interaction probability to winning trajectories.
6. Add paired card-swap evaluator using common random worlds.


## Phase 5I repair checkpoint — August 27/28, 2026

The first full benchmark launch exposed four incomplete inputs:

- hand 12: GitHub-hosted runner shutdown; no solver traceback;
- hand 14: wall-clock cancellation at the original 120-minute ceiling;
- hand 26: genuine typed-runtime Spellseeker lifecycle bug;
- continuation sample dead / stage 3 / sample 1: wall-clock cancellation at the
  original 120-minute ceiling.

### Spellseeker fix

Hand 26 exposed a rules error in the staged tutor resolver. The code required an
"unused" Spellseeker permanent to still be on the battlefield when the already
created ETB search target resolved.

Correct rule now implemented:

- once Spellseeker's ETB trigger exists, its search resolves independently of the
  source permanent;
- if Spellseeker is still present, the legacy Oracle compatibility path may mark
  that simplified permanent mode="used";
- if it has left the battlefield, the trigger/search still resolves normally.

Regressions added at both the Phase-1 tutor adapter and typed Phase-2 runtime levels,
including an explicit source-leaves-before-trigger-resolution case.

Production Phase-5I CI is green at commit **dab572bb** with both tutor lifecycle
smokes now run explicitly.

### Deterministic repair run

Repair branch: `phase5i-benchmark-repairs`
Workflow run: **33133641811**

The repair run reuses the exact original evaluator scripts, seeds, Q configuration,
bottom budgets, and continuation sample coordinates. Only the wall-clock ceiling is
raised to 240 minutes.

Repair outputs:

- human hands 12, 14, 26;
- continuation sample dead / stage 3 / sample 1.

No successful benchmark result is rerun or replaced.

### Full matrix audit

A full 100-job-page audit found two additional incomplete inputs that were hidden
beyond the first 30 convenience API results:

- human hand 25: original 120-minute wall-clock cancellation;
- continuation sample live / stage 4 / sample 3: same Spellseeker lifecycle bug.

Second repair branch: `phase5i-benchmark-repairs-extra`
Workflow run: **33133729255**

It reruns only hand 25 and live/stage 4/sample 3 from the fixed production runtime,
with identical seeds/budgets and a 240-minute wall-clock ceiling.

No successful original artifact is replaced.

### Final aggregate source lock

The final manual aggregate now consumes exactly:

- main human-hand run: **33122937057**;
- repair run A: **33133641811**;
- repair run B: **33133729255**;
- factorized hand-12 run: **33135996901**;
- main factorized continuation run (sample IDs 0-3): **33123595522**;
- continuation expansion run (sample IDs 4-7): **33135871407**.

Before aggregation it requires exactly 35 unique human-hand artifacts and the full
2 contexts x 7 stages x 8 sample IDs = **112 continuation samples**.

The aggregate now also emits `phase5i_disagreement_report.json`, classifying
stable/unstable/seat-dependent keep-mull calls and material versus timing-only
bottom differences.


### Hand 12 isolated final rerun

The first repair-A attempt for hand 12 was again terminated by a GitHub-hosted
runner shutdown signal after approximately eight minutes, with no solver traceback.
Because GitHub will not rerun a single failed job while the parent matrix run remains
active, hand 12 was moved to an isolated identical-seed rerun.

Branch: `phase5i-hand12-final-rerun`
Workflow run: **33135490121**

No evaluation parameters changed. The final aggregate consumes hand 12 only from this
isolated run; repair-A remains the source for hands 14/26 and dead-stage3-sample1.


### Continuation-threshold expansion after stability audit

A preliminary reduction using the first four K_s samples per stage exposed large
threshold variance. In the Caverns-live context, the two disjoint two-hand
pseudo-replicates produced stage-0 continuation win probabilities of approximately
0.47 versus 0.88. Preliminary keep/mull agreement on the 31 already-completed
human hands was therefore not treated as a valid model score.

This triggers the predeclared Phase-5I rule: increase independent stage sampling;
do not tune toward human labels.

Expansion branch: `phase5i-stage-factorized-expansion8`
Workflow run: **33135871407**

It adds sample IDs 4-7 for every context/stage using the exact same frozen Phase-5H
player and K_s budgets. Final continuation models will therefore use:

- 8 fresh hands per stage/context;
- 2 contexts x 7 stages x 8 = 112 independent K_s artifacts;
- stability replicate A = sample IDs 0-3;
- stability replicate B = sample IDs 4-7.

The final human-hand evaluation budgets remain unchanged. The aggregate workflow now
requires all 112 continuation artifacts before it will score keep/mull agreement.


### Hand 12 exact factorization

A second isolated monolithic hand-12 attempt (run 33135490121) was also terminated by
a hosted-runner shutdown after approximately eight minutes with no solver exception.
Rather than retrying the same infrastructure-sensitive job again, hand 12 was
factorized exactly.

Branch: `phase5i-hand12-factorized`
Workflow run: **33135996901**

Hand 12 is London stage 1, so there is only one legal bottom action: the empty set.
The original K_s estimate is therefore exactly the equal-weight mixture of outer
confirmation sample IDs 0, 1, and 2. The factorized workflow evaluates those three
worlds independently with identical MC/Q seeds and then reduces them into the same
`phase5i_human_hand_12.json` schema.

No policy, world coordinate, rollout budget, or action set changes. The final
aggregate consumes hand 12 only from run 33135996901. Monolithic hand-12 runs are
retained only as infrastructure provenance.


### Phase 5I PR and uncertainty-report checkpoint

Current Phase 5I draft: **PR #23** from `phase5i-mulligan-frozen-q` onto
`phase5-adaptive-confidence-q`.

Older divergent draft PR #22 is closed as superseded. It modified historical
adaptive-mulligan/Q modules directly; the current architecture intentionally leaves
those experiments unchanged and isolates production behavior behind the frozen
Phase-5H policy wrapper.

Final benchmark reporting now separates:

- point-estimate keep/mull agreement;
- agreement restricted to hands whose continuation decision is stable across the
  two disjoint 4-hand threshold models;
- threshold-only bootstrap keep probability from 1,000 deterministic resamples of
  the 8 independent K_s training hands per stage;
- joint bootstrap keep probability that also resamples each held-out human hand's
  finite outer-world K_s outcomes;
- bottom exact match, diagnostic rank, p(win) regret, and timing/family-only
  disagreements.

These bootstrap diagnostics are evaluation-only. They do not alter the frozen
gameplay policy, bottom choice, London threshold point estimate, or human labels.


## Phase 5I symbolic action-space / memory checkpoint — August 28, 2026

Hand 12 was confirmed to be a real memory/action-space failure rather than a random
hosted-runner shutdown. Earlier runs reached roughly 15-16 GB RSS plus full swap.

### Lossless packed state

The rules engine remains readable, but retained hot-path identities/checkpoints now
have lossless/reversible packed encodings.

Representative exact-state sizes:

- full State: 454 packed bytes versus 3,362 bytes for the old tagged canonical repr;
- full runtime with stack/pending/permissions: about 907 packed bytes;
- cycle key: about 295 packed bytes versus 6,085 legacy repr bytes;
- strategic Q key: about 286 packed bytes versus 2,411 legacy repr bytes.

Exact library order, arbitrary RNG seeds, stack objects, pending decisions,
permissions, permanent execution identity and provenance remain round-trippable.
Strategic Q/policy projections still deliberately exclude hidden information exactly
where the legacy non-Oracle equivalence excluded it.

### Symbolic action-space implementation

Branch: `phase5i-symbolic-action-dag`

Implemented:

- integer bitsets for subset state;
- reduced cardinality ZDDs with shared suffix nodes;
- generic factored action DAG primitives;
- conservative Pareto frontier primitives;
- exact finite-sample branch-and-bound in Phase-5 MC;
- symbolic Whir payment commitment before search observation.

Whir no longer materializes every X/payment/improvise powerset as root actions.
The symbolic runtime commits X, then traverses a bitset/ZDD payment DAG without
revealing new information, then exposes the search target only on resolution.

Exact parity results:

- fixture historical useful Whir payment plans: 303;
- symbolic main-phase Whir root actions: 5;
- every useful historical payment plan has exactly one symbolic path;
- every symbolic leaf produces the same post-payment cast state as the historical
  monolithic Phase-2 commitment;
- dominated X values above the maximum deck artifact mana value are removed only
  after verifying they add no legal target or modeled mana-spent trigger value;
- hidden library order cannot affect X/improvise commitment actions;
- contingent Q depth covers every payment choice plus the eventual observed target.

ZDD compression example:

- 20 choose 7 = 77,520 represented subsets;
- reduced ZDD nodes = 98.

Exact Q branch-bound parity example:

- full continuation evaluations: 24;
- branch-bound continuation evaluations: 21;
- branch-pruned actions: 4;
- Pareto-proven pruned actions: 4;
- best action/value identical to the unpruned fixed-sample evaluation;
- designated v6 baseline remains fully paired.

### Hand-12 resource result

Before symbolic action-space reduction:

- pathological maximum request: 4,131 actions;
- 4,097 were X-artifact-tutor commitments;
- packed-state-only 3-minute RSS: about 7.26 GB.

After symbolic Whir + packed hot state:

- observed Hand-12 maximum request in the 3-minute probe: 181 actions;
- 3-minute RSS: 57,052 KB (about 56 MB);
- swap used: 0.

This identifies action materialization as the dominant prior memory multiplier.
Remaining large X-tutor requests are primarily Reshape X x sacrifice choices, but
current memory is already within the local-machine target.

### Current gate

The exhaustive symbolic parity/Q regression suite is green on the symbolic branch.
A fresh full exact Hand-12 world-0 proof is running from the green symbolic commit,
followed in parallel by final symbolic reruns of pathological human hands 14 and 25.
Do not promote the symbolic branch into frozen Phase-5I production until those exact
benchmark artifacts complete successfully.


## Phase 5I staged Reshape checkpoint — August 28, 2026

Branch: `phase5i-symbolic-reshape-dag`

Reshape now uses the same factored-action principle as Whir, without requiring a
subset ZDD:

`choose X -> choose additional-cost artifact sacrifice -> cast -> resolve/search`

No observation or priority window is inserted between X and sacrifice. The library
is unchanged and no hidden information becomes available between those two public
commitments.

Exact parity gate:

- historical useful X+sacrifice root commitments in fixture: 60;
- staged main-phase Reshape X roots: 5;
- every historical useful commitment maps to exactly one staged path;
- every staged path produces exactly the same Phase-2 runtime/stack state as the
  historical monolithic commitment;
- hidden library order cannot affect the X root or sacrifice action set;
- bounded contingent Q follows sacrifice and then the eventual observed target;
- existing X-tutor, Whir, contingent-Q, adaptive-Q and mulligan regressions remain
  green.

Hand-12 two-minute resource/fanout probe on this branch:

- prior symbolic Whir-only maximum request: 181 actions;
- staged-Reshape maximum observed request: 127 actions;
- largest observed request no longer contains the X-artifact Cartesian family;
- peak RSS: 56,820 KB (about 55.5 MB);
- no memory-growth/OOM signature.

Action-space architecture is now frozen for the next homogeneous Phase-5I benchmark.
Transmute is already staged (cast -> sacrifice -> observed target -> payment) and Bay
is linear in sacrifice choices, so neither is being refactored before the benchmark.


## Phase 5I Whir target-frontier experiment — August 28, 2026

Branch: `phase5i-whir-target-frontier`

Motivation: Hand 25 proved that the symbolic Whir-payment/ZDD work fixed the
catastrophic memory multiplier, but some engine-rich worlds still issue tens or
hundreds of thousands of decision requests.  The post-resolution Whir search was
still exposing every legal artifact with mana value <= X as a bounded-Q candidate,
including opponent-facing goldfish-irrelevant targets such as Pithing Needle.

Implementation:

- rules/search legality is unchanged: Whir still reveals every legal target;
- bounded Q applies an information-safe, objective-specific target frontier only
  after the legal search set is observed;
- target roles are encoded as an integer bitmask with compact numeric features;
- every combo, producer, mana, value, draw, untap, tutor, or protection role is
  retained in the conservative version;
- Defense Grid is explicitly retained as the strongest current protected-line
  representative, although Phase 5I still optimizes win timing rather than
  protection probability;
- opponent-facing low-information targets (Pithing Needle, Grafdigger's Cage,
  Tormod's Crypt, Disruptor Flute) may be removed from `win_by_horizon` Q unless
  rollout-v6 itself selected them;
- identical low-information generic feature signatures may collapse to one
  deterministic representative;
- non-goldfish objectives bypass this filter entirely.

This is not claimed as lossless rules equivalence: singleton card identity can
technically alter future shuffled draws.  It is therefore versioned as an
objective-specific policy approximation and is not yet promoted into the frozen
Phase-5H/5I production identity.

Validation:

- frontier semantic smoke PASS;
- existing selective-Q, contingent-Q, adaptive-confidence-Q, symbolic action-space,
  branch-bound, staged Whir, staged Reshape, and Phase-5I mulligan regressions PASS;
- synthetic frontier example: 6 legal artifact targets -> 4 retained while keeping
  Battered Golem, Mana Vault, Sensei's Divining Top, and Defense Grid;
- Hand-25 baseline diagnostic established a CPU/search-time rather than RAM
  pathology (e.g. Island/sample0: 242,712 decision requests, 713 s, same low
  action fanout);
- conservative frontier Island/sample0: 239,290 requests, 546 s, exact same
  174-step trajectory and same Q-cache counts;
- several other conservative probe worlds preserve exact trajectories/Q-cache
  counts with modest request reductions; finite-run wall time is noisy on hosted
  runners;
- an earlier more aggressive Pareto version changed a Sapphire sequencing line
  and was rejected for promotion in favor of the conservative role-preserving
  frontier.

Promotion gates still running from the conservative frontier:

1. exact full Hand-25 evaluator;
2. frozen Phase-5H 10-hand x 4-world paired quality benchmark;
3. no held-out quality degradation versus the frozen bounded confidence-Q player.

Do not mix artifacts from this experimental branch into the authoritative
homogeneous Phase-5I benchmark unless the frontier is explicitly promoted and
Phase 5I is rerun from one new frozen source commit.


## Phase 5H final frozen player checkpoint — August 28, 2026

Frozen source commit: `e7c6b7a03bfe6540314a7f20313df4b33a74328e`

The Whir target-frontier approximation was rejected.  Exact Whir target identities
remain available to Q.  Search shuffles now use a shared pre-target random ranking:
each legal target branch removes only its exact chosen card from the same shuffled
ordering, preserving exact true-state library identity while reducing
counterfactual RNG noise.

Chain of Vapor optional copies now use visible-payoff policy pruning rather than
Cartesian land x target materialization:

- decline is always retained;
- Urza, Construct, and token bounce targets are excluded from the goldfish policy;
- each exact retained bounce target keeps one lowest-opportunity-cost legal land;
- a copy survives only with an explicit visible payoff such as producer mana/untap,
  Uthros draw, Gadgeteer Clue, Spellseeker retutor, Cage unblock, replay ETB value,
  or a concrete mana-positive same-turn unlock;
- exact target and land identities remain in the resulting true transition.

Final Phase-5H promotion gate on the Chain-enabled shared-shuffle player:

- semantic/regression suite: PASS;
- paired hands: 12, 13, 19, 20, 21, 24, 25, 27, 29, 33;
- 40 total paired worlds;
- rollout-v6 wins: 5/40;
- one-step bounded Q wins: 11/40;
- contingent two-step Q wins: 13/40;
- one-step Q worse than v6: 0/40 worlds;
- contingent Q worse than v6: 0/40 worlds.

Phase 5H is frozen at the source commit above.  Phase 5I must be evaluated
homogeneously from this exact production source.  Workflow-only provenance or
batching commits may descend from it, but no production policy/rules code changes
are permitted without reopening the Phase-5H gate.


## Phase 5I final homogeneous launch — August 28, 2026

Phase 5I is launched from the frozen Phase-5H production source
`e7c6b7a03bfe6540314a7f20313df4b33a74328e`.

The launch commit changes only workflow/provenance/logging files.  Production
rules and policy code are unchanged from the frozen source.  Human evaluation is
split into isolated per-hand jobs, with hands 12, 14, 25, and 26 in a dedicated
low-concurrency heavy lane.  The 112 factorized London continuation samples remain
independent jobs and aggregate only after every homogeneous source artifact
completes successfully.


## Phase 5I mulligan runtime v2 — August 28, 2026

Branch: `phase5i-mulligan-runtime-v2`
Validated source parent: `206282ba72413e61f18c6d5119d880126506bd8f`

This optimization changes only the Phase-5I opening-hand evaluator/orchestration.
Frozen Phase-5H gameplay/rules/card action semantics are unchanged.

Implemented runtime changes:

1. **Process-parallel bottom racing.**
   Independent London bottom candidates can run in separate worker processes.
   Each worker owns one bounded Phase-5H Q cache across that bottom's outer
   worlds, preserving within-bottom cache locality while reducing wall time.
   Human and stage-sample entry points currently request four workers.

2. **Adaptive exact-cutoff tie re-screening.**
   The initial screen remains the frozen Phase-5H player.  If an exact
   finite-sample tie straddles the configured shortlist cutoff, only that
   boundary tie group receives additional paired outer worlds (maximum two by
   current configuration).  Candidates already below the original cutoff never
   re-enter.  If the boundary remains tied after the bounded re-screen, all
   remaining exact ties are conservatively retained.

3. **Exact confirmation early elimination.**
   One fully evaluated confirmation candidate establishes an exact incumbent.
   Another candidate may stop only when the most optimistic possible completion
   of all remaining worlds (every unseen world wins on T1) is still
   lexicographically below the incumbent's exact win-distribution objective.
   Equality is never pruned, preserving deterministic tie-breaking.

RNG/correctness details:

- legacy confirmation outer-world IDs are preserved exactly;
- tie-break worlds use later, disjoint sample IDs, so adaptive tie resolution
  does not shift the existing confirmation random tape;
- process-local cache misses recompute deterministic values from the same
  explicit seeds and therefore do not change player choices;
- live Gemstone Caverns hands currently fall back to the legacy aggregate
  evaluator because they can have multiple pregame exile choices per bottom;
  this is a performance fallback, not a policy/card restriction.

Instrumentation added to human/stage artifacts:

- requested shortlist count and fully-confirmed count;
- adaptive tie-break rollout count;
- exact early-eliminated bottoms;
- worker count;
- confirmation sample start;
- aggregate actual Q-cache hit/miss/eviction work.

Commits:

- `bfdf69dcc6fce299d6c532e3ddfff5a745d42027` core parallel/adaptive/exact-safe evaluator;
- `6d5e541c4be9b7dace2c8e976b7660c2aa670ec7` human benchmark wiring;
- `95041b6560d2b1f6e88869a9242e41b8d65bd442` stage-sample wiring;
- `4917bae9b0b6272030baf2756b2e8fee357d75ae` bound/distribution smoke tests;
- `06485c54f81d749c5cc4a385b626f50413c1abe9` preserve legacy confirmation RNG window.

Validation:

- compile: PASS;
- Phase-5I integration smoke including exact optimistic-bound and distribution
  merge tests: PASS;
- optimized Hand-25 A/B run: `33217243724` (in progress at checkpoint);
- legacy-vs-parallel same-world Hand-24 parity run with adaptive ties disabled:
  `33217537433` (in progress at checkpoint);
- current-code 7-bottom x 4-world Hand-25 postmortem:
  `33216668759`.

Current Hand-25 postmortem evidence already confirms deep repeated-search cost
rather than one giant action list.  Example on final frozen gameplay code:
bottom Island / outer world 0 took 741.0 s, generated 253,504 decision requests,
had 671 Q-cache hits / 284 misses, and max instantaneous request size was only 95.
Large late fanout families included Transmute target choice (~36-37), Grinding
Station mill targets (~25-27), and Repurposing Bay activations (~31).  Do not
constrain these card behaviors heuristically before the outer runtime-v2 A/B is
measured and structural/factoring options are audited.


## Rust rebuild clean-base audit — August 28, 2026

Branch: `rust-engine-rebuild`
Audited spec commit: `ec99eecb821e5146160ebdf8042212906d0cec9a`

Before beginning Rust implementation, the rebuild specification received a source-of-truth and rules/architecture audit specifically to avoid treating Python implementation details as normative semantics.

Key corrections/locks:
- current Comprehensive Rules / Oracle text + explicit project abstractions outrank Python parity;
- Python remains a regression witness/fixture generator, not the rules source of truth;
- Tezzeret -3 puts the searched MV<=1 artifact into hand; Tezzeret 0 also adds a +1/+1 counter to an artifact-creature target;
- Artificer's Assistant triggers on historic spells, not artifact spells only;
- Voltaic Key may target itself; Manifold Key requires another target artifact;
- Otawara's channel target types are artifact/creature/enchantment/planeswalker, so land status alone does not invalidate an otherwise matching permanent;
- Urza's Saga III uses printed mana cost exactly {0}/{1}, not generic MV<=1;
- Repurposing Bay is sorcery-speed and exact MV+1;
- own life starts at 40 and belongs in core state;
- per-object counters/attachments and typed delayed events replace Python redundant globals/trace-backed provenance;
- CardDefId is u16 and physical ObjectId is separate;
- strategic ValueKey and exact sampled-world/cycle identity are distinct;
- production RNG must include a deterministic stochastic-event occurrence coordinate so repeated random events can be fresh, while same-logical-event counterfactual branches deliberately share CRN coordinates;
- game / outer-MC / environment / policy RNG domains are independent;
- MC cache namespace includes model/policy/objective/environment/RNG tape/budget identity, not ValueKey alone;
- runtime-v2 mulligan parallel/tie/early-stop work remains an EXPERIMENT and does not define game semantics;
- R0 must generate a machine-readable card coverage registry and fail CI if any active card is missing/duplicate/unclassified.

Deck coverage check at the audit:
- 99 cards excluding commander;
- 95 distinct card names including Urza;
- no silent-card-coverage exception is permitted in Rust.

Performance reference remains Hand 25, especially Hydroelectric-bottom/world-2 (~1667 s, 762,012 decision requests in Python). Rust performance changes should be validated on deterministic fixtures and should prefer representation/caching/factoring/exact bounds before policy restrictions.
