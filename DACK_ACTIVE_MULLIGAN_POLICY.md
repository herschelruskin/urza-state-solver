# Dack simulator — promoted active mulligan policy

**Status:** Assertive is the recommended default for **new speed-first deck and card comparisons**, effective October 26, 2026. **Standard remains a supported, explicitly selectable control.** This policy promotion does *not* retroactively rewrite historical experiment scripts or benchmark reports.

## Frozen policy specification

All tests use one free multiplayer London mulligan with stages `(7, 7, 6, 5, 4, 3, 2, 1)`. The identical existing 99-card hand evaluator and bottom selection are retained. Base score is the existing estimated `P(T1)+P(T2 exactly)+0.5*P(T3 exactly)`, with the preexisting continuation thresholds. For **Assertive**, add the following amounts to those thresholds unless the hand already qualifies for a Standard keep *and* its sampled T1 probability is positive:

| Cards kept | Standard threshold | Assertive threshold (unless T1-protected) |
| --- | ---: | ---: |
| 7 | 0.55603 | 0.75603 |
| 6 | 0.51025 | 0.63025 |
| 5 | 0.42268 | 0.47768 |
| 4 | 0.31419 | 0.32919 |
| 3 | 0.19234 | unchanged |
| 2 | 0.06171875 | unchanged |
| 1 | terminal keep | unchanged |

The T1 signal comes from a bounded estimator; a nonzero sampled T1 rate does not guarantee winning, nor does a zero estimate prove impossibility. This is a **policy preference**, not a claim of globally optimal London mulligans.

## Independent held-out evidence

**10,000 matched seeds**, identical frozen 99-card Boonweaver list and beam=160; all 250 shards independently validated.

| Metric | Standard | Assertive | Paired difference (pp) | Paired 95% CI (pp) |
| --- | ---: | ---: | ---: | ---: |
| T1 | 5.26% | 6.00% | +0.74 | +0.54 to +0.94 |
| By T2 | 48.30% | 50.27% | +1.97 | +1.38 to +2.56 |
| By T3 | 86.02% | 83.15% | −2.87 | −3.35 to −2.39 |
| T2 + 0.5 × exact-T3 | 67.16% | 66.71% | −0.45 | descriptive only |

Original 2,048-game discovery showed T2 +3.32 pp, T3 −3.13 pp; fresh replication reduced the T2 gain to +1.97 pp. Thus Assertive is **faster by T2 in the modeled setting**, not universally stronger or more likely to win by T3. Endpoints represent *optimistic goldfish Dack casts conditional on eligible combo library*, **not verified full ETB-combo completions or multiplayer cEDH wins**.

Reference evidence: `benchmark_results/dack_assertive_heldout_n10000_report.json` and `.raw.json.gz` on the source branch `dack-t1-assertive-heldout-n10000-20261026`.

## How to use in new experiments

Run the active default:

```bash
python dack_active_mulligan_policy.py --game-id 8
```

Retain a Standard control explicitly:

```bash
python dack_active_mulligan_policy.py --game-id 8 --policy standard
```

In new card-swap runners:

```python
import dack_active_mulligan_policy as sim

sim.configure_variants({
    "baseline": tuple(baseline_99_cards),
    "candidate": tuple(candidate_99_cards),
})
for gid in range(sample_size):
    for variant in ("baseline", "candidate"):
        sim.reset_caches()
        result = sim.simulate(variant, gid, policy=sim.ACTIVE_POLICY,
                              seed_base=chosen_seed_base, beam=160)
        # persist each result and pool paired game IDs
```

For comparisons, **hold the policy constant across deck variants**, hold sample seeds/seats constant, and do not claim speed improvement without an independent confirmation and paired uncertainty. Do not mix legacy Standard results with new Assertive data as though only cards had changed.

This module is an **opt-in active entry point**. Historical root functions and frozen benchmark files are deliberately unchanged. Future speed runners should import `dack_active_mulligan_policy` rather than implicitly using the legacy root's Standard default.

## Verification

```bash
python dack_active_mulligan_policy.py --audit
python dack_active_mulligan_policy.py --parity
```

The parity check confirms both active policy selectors reproduce the exact previous held-out results (seed, seat, keep size, kept cards, next three cards, and T1/T2/T3) for selected game IDs.
