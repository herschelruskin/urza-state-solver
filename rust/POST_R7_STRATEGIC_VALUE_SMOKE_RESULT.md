# Post-R7 strategic value 128-world smoke result

## Status

**GREEN — all 128 natural worlds completed without `NoCandidate` or `StepLimit`.**

- Source workflow commit: `e4eb5c9603f7d773d2e2dfc5b8436dcbd2d228a8`
- Worlds: **128**
- Frozen deterministic baseline terminals: **0**
- Strategic-policy terminals: **0**
- Strategic decisions: **6882**
- Sensei Top look selections: **0**
- Real staged tutor-target selections: **81**
- Trigger-order decisions: **1**

## Per-opening totals

| Opening | Baseline terminals | Strategic terminals | Decisions | Top looks | Tutor targets | Trigger orders |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | 0 | 345 | 0 | 3 | 0 |
| 1 | 0 | 0 | 625 | 0 | 6 | 0 |
| 2 | 0 | 0 | 380 | 0 | 6 | 0 |
| 3 | 0 | 0 | 595 | 0 | 6 | 1 |
| 4 | 0 | 0 | 386 | 0 | 11 | 0 |
| 5 | 0 | 0 | 414 | 0 | 3 | 0 |
| 6 | 0 | 0 | 476 | 0 | 5 | 0 |
| 7 | 0 | 0 | 367 | 0 | 3 | 0 |
| 8 | 0 | 0 | 542 | 0 | 14 | 0 |
| 9 | 0 | 0 | 415 | 0 | 9 | 0 |
| 10 | 0 | 0 | 335 | 0 | 1 | 0 |
| 11 | 0 | 0 | 272 | 0 | 2 | 0 |
| 12 | 0 | 0 | 371 | 0 | 1 | 0 |
| 13 | 0 | 0 | 784 | 0 | 8 | 0 |
| 14 | 0 | 0 | 247 | 0 | 0 | 0 |
| 15 | 0 | 0 | 328 | 0 | 3 | 0 |

This smoke uses the exact accepted post-R7 opening population and hidden-world range: 16 opening offsets, hidden worlds `245632..245639` for each opening. The smoke binary aborts on `NoCandidate` or `StepLimit`, so successful aggregation means all 128 worlds reached only normal horizon/terminal stops.
