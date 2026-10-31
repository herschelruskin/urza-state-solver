# DACK counterfactual runner v1 (experimental branch)

This branch is a **non-destructive** engineering checkpoint. Do not merge into
`development` or use these outputs to make deck cuts until regression and
gameplay validation are completed.

## Authority and rules

- `dack_simulator/configs/physical99_20261030.json` is the physical 99,
  including **Treasure Vault**, 32 literal land cards, 2 land-capable MDFCs,
  10 Plains, and **Tooth of Ramos**.
- `dack_simulator/validation/audit_physical99_20261030.py` reconstructs
  the physical list independently from the October 16 source and its four
  documented card changes.
- `dack_counterfactual_rules_v1_20261030.py` builds on the Oct 29
  Aura-exile and Bucknard priority fixes. It recognizes Treasure Vault as
  an artifact land, adds the 2X Treasure ability, fixes related tutor/copy
  coverage, and implements Staff of Compleation's missing one-life mode.
  The original patch/solver modules are **not edited**.
- Both `Mind Stone` and `The Mind Stone` are present and distinct.
- No banned Mana Crypt or Jeweled Lotus.

## The paired experiment

`dack_simulator/configs/onekey_artifact_cut_screen_v1.json` specifies an
assertive one-Key 34-land control (Tooth -> Voltaic), plus eight individual
artifact-to-Plains substitutions, all with 35 land-access cards. The spec
is exploratory; it is not an authorization to cut all listed candidates.

`dack_paired_counterfactual_v1_20261030.py` is the **full per-arm replay
reference**. It creates a common seat and eight fresh London-mulligan
permutations over the same 99 persistent physical slot identities. Each arm
independently evaluates its hand, bottoming, future draws, mana and beam
search. It records each London-stage decision, kept hand, first three unknown
library cards, and per-turn beam frontier summaries.

The runner does **not** skip games based on whether a changed card was
played in the baseline winning line. No cross-variant state cache is used.
Within-game inherited memoization is reset between arms, and the actual
kept-hand search clears speculative mulligan-evaluation win cache entries.

Important caveat: inner mulligan-EV sample generation and historical
post-tutor pseudo-shuffling still depend partly on card-name composition
rather than shared slot-ID randomness. This is genuinely paired at the
**outer London scenario** level, but not yet every internal random event.
The legacy search also remains optimistic about future library information
and Bucknard die rolls. The metric is conditional Dack deployment by T1/T2/T3,
not verified combo completion or four-player match wins.

## Commands

From repository root, Python 3.11:

```bash
python dack_simulator/validation/audit_physical99_20261030.py
python dack_counterfactual_rules_v1_20261030.py
python dack_paired_counterfactual_v1_20261030.py --audit
python -m unittest discover -s dack_simulator/validation -p test_paired_v1.py -v
python -m unittest discover -s dack_simulator/validation -p test_pool_v1.py -v
```

One end-to-end reference game, one arm:

```bash
python -u dack_paired_counterfactual_v1_20261030.py --single-variant one_key_34 --start 0
```

One paired test scenario across all nine arms, with resumable JSONL and
an independently inspectable SQLite result block per arm:

```bash
python -u dack_paired_counterfactual_v1_20261030.py \
  --start 0 --games 1 \
  --out shards/paired_0000.json.gz \
  --store shards/paired_0000.sqlite
```

After a complete disjoint set of shard files:

```bash
python pool_dack_paired_counterfactual_v1_20261030.py \
  --folder shards --out benchmark_results/cut_screen_report.json \
  --expected-start 0 --expected-games 256
```

The pooler rejects overlapping or missing game IDs, missing arms, or mixed
experiment/spec/rules versions. It recomputes all paired gains/losses,
confidence intervals and divergence summaries from original game rows.

## Storage and checkpointing

- Within one shard, a `.checkpoint.jsonl` file is fsynced after every
  completed game. Re-running the same shard reuses its completed rows only
  when its spec, manifest, start and count match.
- SQLite is implemented by the existing `dack_simulator/src/dacksim/store.py`
  application foundation, with one-byte outcomes and compressed discordance
  traces. Each independent worker must use **its own** SQLite path.
- A persistent cache should never be assumed valid across rules-version,
  stochastic-policy, search-configuration, deck-hash or seed changes.
- The current implementation does not read historical SQLite outcome blocks
  to shortcut fresh per-variant replays. Doing so safely, including trace
  reconstruction, is a later optimization.

## Validation gates before N256/N1024

1. Run the isolated smoke workflow and a nine-arm one-game E2E.
2. Audit inherited search-state equivalence: its original `key(s)` omits
   graveyard, exile and other fields. This can affect legal future actions,
   especially when protected combo cards are exiled. The new branch must
   establish a safe key or validate a conservative replacement before a
   major screen.
3. Check that a fresh reference run reproduces itself exactly across shards,
   and that the new slot-based outer shuffle retains the expected London
   distribution. It will intentionally not match each historical game ID
   card-for-card because the sampling coupling changed.
4. Measure runtime/memory. Only then allocate balanced N256 exploratory
   shards. Never substitute its small-sample ranking for an independent
   N4096+ confirmation.

All historical results and deck lists remain in the older branches.

## Strict-state-key opt-in

The independent witness in
`dack_simulator/validation/state_key_collision_witness_v1.py` establishes
false equality in the inherited beam key when the only difference is a
protected exile or a combo creature in the graveyard.

`dack_counterfactual_rules_v2_strict_key_20261030.py` composes the
v1 rules with a stricter deduplication key retaining the complete grave
and exile multisets, Saga age, success and repaired status. It is
**not** enabled in the preserved v1 reference entrypoint.

Use `dack_paired_counterfactual_v2_strict_20261030.py --audit` to
validate the opt-in strict implementation; its output has a distinct
rules-version identity and must never be pooled with the v1 replay
results. A small runtime and outcome sensitivity study should establish
whether increased state distinctions materially increase search work.

## 2026-10-31 exact bounded London optimization

Profiling showed ~98.6–99.99% of wall time in mulligan evaluation on
seeds 0 and 1, not in actual Dack gameplay. The inherited
`dack_bottom_weighted_ev_seat` evaluates eight or sixteen sampled
future-games per candidate London bottom choice, even when a completed
candidate has a utility that all remaining futures can never beat.

`dack_mulligan_branchbound_v1_20261031.py` is an **opt-in** exact
branch-and-bound implementation. It changes only the number of
hypothetical futures computed. It retains:
- exactly the same finalist generation and ranking;
- exactly the same sample ordering and card information;
- exactly the same reward weights and structural tie-break;
- the same threshold-triggered 16-sample refinement;
- the same actual kept-hand gameplay search.

If an incumbent has utility U, a challenger with n future samples, k
already completed, and total achieved reward r has the optimistic
upper bound `(r + (n-k) * max(1, t3_weight)) / n`.
The challenger is stopped when the optimistic bound cannot beat U,
including the original structural tie-break. No partial value is
inserted into the complete-evaluation cache.

Use `dack_paired_counterfactual_v3_bounded_20261031.py` for the
combination of conservative strict state keys and exact bounded London
evaluation. The historical v1 and strict-unbounded v2 entrypoints
remain unchanged.

```bash
python dack_mulligan_branchbound_v1_20261031.py
python -m unittest discover -s dack_simulator/validation -p test_bounded_mulligan_v1.py -v
python dack_paired_counterfactual_v3_bounded_20261031.py --audit
python dack_simulator/validation/benchmark_strict_bounded_parity_v3.py --game-id 0
python dack_paired_counterfactual_v3_bounded_20261031.py --start 0 --games 1 \
   --out shards/v3_smoke.json.gz --store shards/v3_smoke.sqlite
```

Exact E2E reference-vs-bounded comparisons, original beam key:
- one_key_34, game 0: 46.4348 s to 39.3378 s, 1.1804×
- one_key_34, game 1: 14.0898 s to 6.3075 s, 2.2338×
- everflow_plains_35, game 0: 70.54 s to 60.8509 s, 1.1592×

All three comparisons passed every game-record and mulligan-history
parity assertion in GitHub Actions 41209135344. Separately,
strict-key-v2 vs strict-key+bounded-v3 E2E parity passed game 0 and
game 1 in GitHub Actions 41209289986 (1.1808× and 2.1918×).

These are observed **few-seed** timings, not an estimated population
average. More performance testing is needed. Cold/warm process order
can affect timings, so use a balanced A/B comparison before estimating
production costs. The one-card counterfactual arms still independently
evaluate all stages: this optimization does not yet implement a
cross-arm semantic-equivalence certificate and does not assume a swap
is irrelevant merely because it was not drawn. The inner sampler still
uses legacy composition-based pseudo-randomness rather than fully
slot-coupled futures.

Pilot workflow: `.github/workflows/dack_bounded_strict_v3_pilot_n4.yml`.
It checks four independent seeds, the full nine-arm counterfactual,
SQLite blocks, checkpoints and strict pooling. This N4 is **diagnostic
only** and must not be used to select deck cuts.
