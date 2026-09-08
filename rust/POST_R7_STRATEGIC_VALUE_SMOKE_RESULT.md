# Post-R7 strategic value 128-world smoke result

## Status

**GREEN — all 128 natural worlds completed without `NoCandidate` or `StepLimit`.**

- Source workflow commit: `5f20f399c0a04d24c2e1691c0d6d977505559463`
- Worlds: **128**
- Frozen deterministic baseline terminals: **0**
- Strategic-policy terminals: **0**
- Strategic decisions: **6905**
- Sensei Top look selections: **0**
- Real staged tutor-target selections: **77**
- Trigger-order decisions: **2**

## Per-opening totals

| Opening | Baseline terminals | Strategic terminals | Decisions | Top looks | Tutor targets | Trigger orders |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | 0 | 346 | 0 | 3 | 0 |
| 1 | 0 | 0 | 632 | 0 | 5 | 0 |
| 2 | 0 | 0 | 391 | 0 | 6 | 0 |
| 3 | 0 | 0 | 602 | 0 | 7 | 2 |
| 4 | 0 | 0 | 375 | 0 | 8 | 0 |
| 5 | 0 | 0 | 405 | 0 | 3 | 0 |
| 6 | 0 | 0 | 458 | 0 | 5 | 0 |
| 7 | 0 | 0 | 372 | 0 | 4 | 0 |
| 8 | 0 | 0 | 585 | 0 | 15 | 0 |
| 9 | 0 | 0 | 431 | 0 | 9 | 0 |
| 10 | 0 | 0 | 335 | 0 | 1 | 0 |
| 11 | 0 | 0 | 272 | 0 | 2 | 0 |
| 12 | 0 | 0 | 367 | 0 | 1 | 0 |
| 13 | 0 | 0 | 753 | 0 | 6 | 0 |
| 14 | 0 | 0 | 247 | 0 | 0 | 0 |
| 15 | 0 | 0 | 334 | 0 | 2 | 0 |

This smoke uses the exact accepted post-R7 opening population and hidden-world range: 16 opening offsets, hidden worlds `245632..245639` for each opening. The smoke binary aborts on `NoCandidate` or `StepLimit`, so successful aggregation means all 128 worlds reached only normal horizon/terminal stops.
