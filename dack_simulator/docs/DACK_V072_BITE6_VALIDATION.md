# DACK v0.72 Bite 6 — Patch C validation at beam 240

Status: **validation only; no solver changes in Bite 6**.

## Engine under test
- Patch C solver: `src/dack_t3_solver_v0_72_payment_dominance.py`
- SHA-256: `31a7b0672b4415c87af2cde12000a083d58b920c93ce59b34eb0ba944ab3a068`
- beam: 240

## Strict Plains-dominance invariants

Fresh completed contexts:
- City of Brass: 10
- Mana Confluence: 10
- Tarnished Citadel: 10

Total:
- 30 independent opening-hand contexts
- 32 seat-class rows (Gemstone Caverns caused seat splitting in two contexts)
- target-worse-than-Plains rows: **0**

Every completed strict-land comparison was equal to or better than Plains by earliest
win turn through T3.

### Pathological runtime event
One additional Mana Confluence context (`namespace=720602, local=1`) exceeded both a
15-second isolated attempt and a later >40-second attempt. It is recorded separately as
a timeout rather than silently omitted or treated as a result.

This is a performance/pathology flag, not a correctness mismatch.

Raw files:
- `validation/v072_bite6_invariants.csv`
- `validation/v072_bite6_timeouts.csv`

## Patch B vs Patch C matched comparison

12 representative targets, two independent contexts each = **24 matched contexts**:
- Ancient Tomb
- Urza's Saga
- Gemstone Caverns
- Mishra's Workshop
- Urza's Cave
- Lion's Eye Diamond
- Mana Vault
- Sol Ring
- Jeweled Amulet
- Pentad Prism
- Expedition Map
- Enlightened Tutor

Each Patch-B and Patch-C comparison used the same target/control opening context,
unknown-library order, seat treatment, and beam=240.

Results:
- Patch-C target earliest-turn mismatches vs Patch B: **0 / 24**
- Patch-C Plains-control earliest-turn mismatches vs Patch B: **0 / 24**
- target utility mismatches: **0 / 24**
- control utility mismatches: **0 / 24**

Tiny-sample wall time:
- Patch B total: 38.622 s
- Patch C total: 34.802 s
- Patch C / Patch B: 0.901
- Patch B median/context pair: 1.576 s
- Patch C median/context pair: 1.392 s

These timings are diagnostic only and are **not** treated as a production benchmark.

Raw file:
- `validation/v072_bite6_patchB_vs_patchC.csv`

## Runtime raw-file SHA-256
- invariants.csv: `db86cdc1228f1de3a500b249eed71a51582896f9f2131c026ea580150359e3d4`
- patchB_vs_patchC.csv: `b1e062bf628071cd935638c1916273d0664f151a64604c236d364049ade7ff96`
- timeouts.csv: `57b93eede1bade7f7ff3d4ff9a464524aaad51d84f0da4e91788d95588159913`

The two multi-line CSVs are committed with the runtime CRLF line endings so their byte
representation is preserved rather than spreadsheet-rendered.

## Interpretation

Patch C passes this Bite-6 validation checkpoint:
- strict rainbow-land invariants remain clean at beam 240;
- no outcome difference from Patch B was observed in the 24-context representative
  matched sample;
- Pentad Prism was explicitly included in the representative comparison and matched.

Patch C is still **not promoted to production** by this document.
Frontier/state dominance has not been implemented.
