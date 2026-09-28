# DACK v0.72 Patch D / Bite 7 — conservative frontier-state dominance

Status: **implemented and validated; not yet promoted to production**.

## Engine

New source:
- `src/dack_t3_solver_v0_72_frontier_dominance.py`
- SHA-256: `abba6f0baa7bedfb0b248bdd62501dae10157ba90bd5a3952fbeffbdcca48a7a`
- 2,852 source lines

Patch D branches from validated Patch C and leaves Patch-C payment dominance unchanged.

## Scope

Patch D does **not** modify `key()`.

A separate `_state_nonresource_key()` requires exact equality of every modeled strategic
field except the six floating/restricted mana pools:

- turn
- hand
- ordered library
- exact battlefield tuple and permanent state
- graveyard
- exile
- land-play status
- treasures and spawn
- spell counters
- Saga state
- success / repair state
- map-bonus state

Only the following fields may differ:
- W
- C
- unrestricted colored (`any`)
- legend-restricted
- artifact-restricted
- Dack-white-restricted mana

A state is removed only when another otherwise-identical state is a **strict, proven
resource-capability superset** under the same conservative matcher introduced for Patch C.

Capability-equivalent but differently encoded states are retained rather than arbitrarily
choosing one.

No score, beam rank, strategic diversity signature, or card heuristic participates in the
dominance proof.

## Search integration

To keep Patch D narrow, frontier dominance is added only to the production
`search_turn_frontier_many()` path:

1. initial multi-state frontier;
2. newly generated `nxt` states, before heuristic/diversity beam selection;
3. pass-state reservoir before size capping;
4. final/early-return pass-state output.

The legacy `search_turn()` and `search_turn_frontier()` functions are unchanged.

## Validation

### Full inherited self-test
`--selftest`: **PASS**

New regressions additionally verify:
- unrestricted colored residual mana strictly dominates W for the same strategic state;
- W does not dominate unrestricted colored;
- W and C remain incomparable;
- graveyard differences block state comparison;
- treasure-count differences block state comparison;
- battlefield differences block state comparison.

### Patch C vs Patch D matched beam-240 validation

Completed matched contexts: **21**
Distinct representative targets: **15**

Representative cards include:
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
- City of Brass
- Mana Confluence
- Tarnished Citadel

Results:
- target outcome/utility mismatches: **0 / 21**
- Plains-control outcome/utility mismatches: **0 / 21**
- strict-land invariant contexts: **9** (3 each for City of Brass, Mana Confluence,
  Tarnished Citadel)
- strict-land target-worse-than-Plains violations: **0 / 9**

One Gemstone Caverns context exceeded the isolated 20-second validation cap and is recorded
as a timeout. A different independent Gemstone Caverns context completed and matched Patch C
exactly. Gemstone Caverns is not a strict Plains-dominance invariant because its pregame rule
can make it strategically different from Plains.

Small-sample wall time:
- Patch C total: 27.7774 s
- Patch D total: 27.4134 s
- Patch D / Patch C: 0.9869
- medians: 1.0669 s vs 1.0645 s

These timings are diagnostic only; Patch D is not claimed to be materially faster from this
sample.

### Realistic frontier-pruning diagnostics

Patch D was wrapped with counters without changing its decisions:

- Mana Vault context:
  - 48 dominance-filter calls
  - 3,822 input frontier/pass states
  - 3,735 retained
  - **87 removed**
  - maximum 41 removed in one call

- Pentad Prism context:
  - 48 calls
  - 7,229 input states
  - 7,120 retained
  - **109 removed**
  - maximum 40 removed in one call

This confirms Patch D performs real search-state reduction while the matched validation
showed no outcome change in the tested sample.

## Raw validation files

- `validation/v072_bite7_patchC_vs_patchD.csv`
- `validation/v072_bite7_timeouts.csv`
- `validation/v072_bite7_frontier_pruning.csv`

Runtime SHA-256:
- matched CSV: `b4b5552bf17963a37f5466b8b2a851095907e70b4d6956d90c9ea118192f130d`
- timeout CSV: `d06d61119c981b5a57c7bf02571dd527388d13c10b7f8473d502320f88a7a814`
- pruning diagnostic CSV: `0b620ea37fce4274f370c3161e0b89980baa378acd8bb1c699cd2391857389e9`

## Production status

Patch D passes Bite 7 but is **not yet the production engine**.

The next checkpoint should be validation/promotion rather than another search optimization:
run a larger fresh Patch-C/Patch-D equivalence sample plus the strict rainbow-land audit,
then freeze the resulting solver/config SHA before returning to the data-lake production run.
