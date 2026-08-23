# Phase 2 Stabilization Audit

**Date:** 2026-08-22 (America/Toronto)  
**Branch:** `phase2-non-oracle-runtime`  
**Audited checkpoint:** `34f3602f88c95dd3545f6e598946ec98dd546658`  
**Reference checkpoint:** `68e11ca585bb9389c19e635bf7be7b7bfc32cbe4`  
**PR:** #10 — Phase 2: non-Oracle runtime kernel  
**Production code changed by this audit:** none

---

## 1. Executive decision

**Stop expanding the Phase-2 card/rules surface.**

The current 250-seed representative run reaches the T6 horizon or a legal win in every sample. There are **zero hard runtime blockers**. The remaining low baseline win rate is dominated by the intentionally simple deterministic policy and by the fact that this diagnostic uses a random opening seven/eight with **no mulligan policy**, not by evidence that another large tranche of Magic rules needs to be implemented.

Phase 2 is therefore considered **mechanically sufficient to begin the value / DP / Monte-Carlo layer**, with a small watchlist of deferred partial surfaces below.

This does **not** mean every card interaction is complete. It means the evidence no longer supports continuing card-by-card implementation before building the decision evaluator the project actually needs.

---

## 2. Green-gate evidence

At checkpoint `34f3602`:

- Phase 2 runtime smoke: **PASS**.
- Oracle stack priority smoke: **PASS**.
- Phase 1 decision / observation acceptance: **PASS**.
- Architecture/state/value-key regressions: **PASS**.
- 250-seed blocker sweep with `--fail-on-blocker`: **PASS**.

The immediately preceding code checkpoint `8e262e3` also passed both primary CI suites after restoring the X-artifact stack resolver accidentally removed during the Grafdigger's Cage correction.

---

## 3. 250-seed behavioral snapshot

Command represented by CI:

```text
python phase2_coverage_profile.py --seed 20260821 --count 250 --horizon 6 --fail-on-blocker
```

Observed:

| Metric | Result |
|---|---:|
| Seeds | 250 |
| Hard runtime blockers | **0** |
| Wins by T6 | 15 / 250 = **6.0%** |
| Horizon no-win | 235 / 250 = 94.0% |
| Mean completed steps | 55.59 |
| T3 wins | 1 |
| T4 wins | 1 |
| T5 wins | 3 |
| T6 wins | 10 |

Observed win families:

| Win family | Count |
|---|---:|
| Power Artifact + Grim | 5 |
| Power Artifact + Basalt | 4 |
| Basalt + Gadgeteer | 4 |
| Knack/Helix + Cam | 1 |
| Top + Gadgeteer + producer | 1 |

### Interpretation

The 6% figure is **not a deck-strength estimate** and must not be compared directly with the validated Oracle ceiling or manual goldfish benchmark.

`phase2_coverage_profile.py` explicitly does not mulligan. It deals a fresh random seven plus the modeled multiplayer turn-one draw and then follows the deterministic base policy. Its purpose is runtime coverage and policy diagnosis.

---

## 4. Classification summary

### BLOCKER — must fix before value evaluation

**None observed.**

No trajectory ended because of an unsupported runtime state, pending decision, stack state, upkeep window, Saga window, step limit, or no-legal-action failure.

This is the most important audit result.

---

## 5. POLICY QUALITY — do not respond with more rules code

### 5.1 Urza reachability

Across 250 seeds:

- Urza cast was legally offered in **54** seeds.
- The deterministic policy chose Urza in **all 54** of those seeds.
- Among the 235 T6 no-win trajectories, Urza remained in the command zone in **196**.

Therefore the major issue is **not** that the policy sees a legal Urza cast and refuses it, and it is not evidence that commander casting is unimplemented. The cast surface works when it becomes legal.

The important remaining problem is earlier resource/sequencing quality: many trajectories never reach a state in which the cast is legally offered.

### 5.2 Why the deterministic baseline is structurally weak

This is expected from the current policy design.

The base policy is explicitly documented as a simple legal continuation policy for future DP/Monte-Carlo improvement, not as an optimized player.

Its current main-phase scoring is one-step greedy. Representative scores include:

- cast Urza: `35`;
- Transmute Artifact: `33`;
- X-artifact tutor: roughly high-20s / low-30s;
- simple tutor: roughly high-20s / low-30s;
- ordinary artifact: `20 + visible_card_score`;
- mana action: only `10 + 2 * immediate mana gained`.

Casts/tutors are only offered once they are currently payable. This means the policy can prefer spending currently available mana on a locally attractive cheap action rather than taking another mana action to cross a future threshold for Urza, a tutor, or a larger engine action.

That is a **lookahead/value problem**. Adding more card-specific runtime implementations will not solve it reliably.

### 5.3 Tutor reachability

The tutor audit shows that the runtime can use every tracked tutor family in real seeded trajectories:

| Tutor source | Seeds chosen at least once |
|---|---:|
| Merchant Scroll | 32 |
| Mystical Tutor | 31 |
| Spellseeker | 19 |
| Transmute Artifact | 19 |
| Reshape | 18 |
| Whir of Invention | 15 |
| Muddle the Mixture | 10 |
| Scour for Scrap | 9 |
| Dizzy Spell | 7 |

A hand-tutor action was legally offered in **130/250** seeds. The policy skipped at least one offered hand tutor in only **23/250** seeds.

Many tutors remain in hand at the T6 horizon, but most of those specific stranded copies were **never legally offered in those trajectories**:

| Stranded tutor | Horizon count | Ever offered in same seed | Never offered |
|---|---:|---:|---:|
| Reshape | 36 | 7 | 29 |
| Muddle the Mixture | 36 | 3 | 33 |
| Whir of Invention | 32 | 3 | 29 |
| Scour for Scrap | 31 | 0 | 31 |
| Dizzy Spell | 30 | 0 | 30 |
| Transmute Artifact | 23 | 0 | 23 |
| Merchant Scroll | 22 | 1 | 21 |
| Spellseeker | 19 | 1 | 18 |
| Mystical Tutor | 7 | 0 | 7 |

This is **not** evidence that those tutor implementations are absent. Their successful use in other seeds proves the action surfaces are reachable. The correct next question is why the current policy failed to build the resources/timing to make them legal in the stranded trajectories.

That question belongs in Q/V evaluation and rollout policy improvement.

### 5.4 Uthros

Uthros stationing was offered in 7 seeds and chosen in 5, with 51 skipped decisions across repeated opportunities. The first skipped example nevertheless ended in a win.

Classification: **policy-quality signal**, not a runtime blocker. Do not tune Uthros heuristics before the value layer exists unless a focused regression proves a clear pathological loop or illegal choice.

---

## 6. EXPECTED / NOT A MODEL GAP

### Reactive interaction left in hand

Reactive interaction was present in **191/235 = 81.28%** of no-win horizon states.

This is expected in a goldfish environment. Counterspells and protection remaining unused do not imply an implementation gap. Opponent/environment interaction belongs to the later stochastic interaction model.

### Modeled cards remaining in hand or on battlefield

The following horizon rows are descriptive, not automatic bug reports:

- hand nonartifact engine present: 51.91%;
- hand artifact tutor present: 42.13%;
- hand simple tutor present: 37.02%;
- hand combo nonartifact present: 31.91%;
- modeled Key activation present: 25.11%;
- modeled Urza spin present: 16.60%;
- modeled Cam/Station/Codex/Top/etc. present at smaller rates.

A modeled card can remain unused because it is uncastable, drawn late, strategically deprioritized, or part of a line the greedy policy does not understand. Presence alone must not trigger implementation work.

---

## 7. DEFERRED EDGE CASE / WATCHLIST

These are real partial surfaces reported by the coverage profiler, but current prevalence does not justify another implementation expansion before DP/Monte Carlo.

| Partial surface | No-win horizon prevalence | Current decision |
|---|---:|---|
| Chrome Dome priority activation partial | 17/235 = 7.23% | **Defer / watch** |
| Top-access nonartifact priority partial | 9/235 = 3.83% | **Defer / watch** |
| Cam tutor-sacrifice LTB partial | 5/235 = 2.13% | **Defer / watch** |

Revisit one only if future value/Monte-Carlo trajectories demonstrate that it:

1. blocks a high-value candidate action;
2. changes estimated win-turn distributions materially;
3. causes an illegal state;
4. or appears much more frequently under an improved policy than under the current baseline.

Do not implement them merely to make the coverage table look complete.

---

## 8. Grafdigger's Cage

Retain the Cage corrections.

Focused smoke coverage now confirms the relevant real rules behavior for:

- Reshape / Whir library-to-battlefield creature filtering;
- Urza's Saga III filtering;
- Transmute Artifact equal-MV and paid-difference resolution behavior under Cage.

This was legitimate correctness work because it prevents illegal creature-card library-to-battlefield transitions. It should not be used as precedent for implementing every low-frequency interaction before value evaluation.

---

## 9. ARCHITECTURE DUPLICATION — freeze, do not immediately rewrite

Compared with known-green checkpoint `68e11ca`, the current branch is **31 commits ahead**.

The comparison spans **38 changed files**, approximately:

- `+8,749` lines;
- `-110` lines.

A substantial portion is tests/diagnostics, but the period also added many dedicated `non_oracle_*_runtime.py` modules for individual engines, activations, top access, Urza permissions, draw engines, milling, utility artifacts, and other card surfaces.

Classification: **architecture duplication risk**.

### Decision

- Do **not** roll back automatically to `68e11ca`; useful correct behavior would be lost.
- Do **not** begin a large consolidation refactor now; that would create another destabilization cycle before we have measured which paths matter to the final value engine.
- Treat the current green runtime as frozen infrastructure.
- Stop adding new runtime modules by default.
- Build the value/DP/Monte-Carlo layer against the stable public interfaces.
- Later consolidate duplicated mechanics based on exercised-path evidence and shared-transition opportunities.

The desired long-term architecture remains one mechanical transition authority wherever practical, with Oracle and non-Oracle differing mainly in information access and decision policy.

---

## 10. Phase-2 acceptance decision

The existing roadmap says Phase 2 needs:

- deterministic choice from the same PolicyView/config despite different hidden futures;
- replayable/full episodes;
- no raw hidden state entering policy decisions;
- complete win/no-win plus exact win-turn records.

Current CI covers these properties, and the 250-seed batch now completes without blockers.

**Audit decision: Phase 2 is accepted as sufficient to proceed.**

This acceptance is conditional in the engineering sense: future DP/MC work can expose a genuinely material missing rule. If it does, fix that single evidenced gap and return immediately to the value layer. Phase 2 should not be reopened as an open-ended card-completeness project.

---

## 11. Next checkpoint: Phase 3 value engine

The next production work should contain **no new card rules**.

Bounded target:

1. define a versioned distribution-rich value object for `P(win by T1)` through `P(win by T6)`;
2. define deterministic comparison / tie semantics;
3. wire real `V(state)` / `Q(state, action)` cache usage through the existing `MemoizationStore` and strategic runtime key;
4. prove exact results on small controlled states;
5. instrument cache hits/misses;
6. only after those exact/value semantics are trustworthy, add hidden-world Monte-Carlo rollout evaluation.

The deterministic base policy remains a rollout continuation baseline. It should **not** be hand-tuned into a pseudo-Oracle before rollout/value improvement is available.

---

## 12. Development rule after this audit

> **No new rules surface without a reproduced blocker or measured material bias.**

For policy weakness:

> **Prefer value/lookahead evidence over another heuristic patch.**

For every next checkpoint:

> **bounded change -> focused tests -> full green gate -> measured result -> document -> continue.**
