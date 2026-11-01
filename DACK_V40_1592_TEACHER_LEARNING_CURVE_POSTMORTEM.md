# v40 actual-v5 archived behavior-cloning learning curve — completed diagnostic

**Status:** both predeclared 128/384/768/1288 group-learning curves completed successfully in GitHub Actions [run 41343592444](https://github.com/herschelruskin/urza-state-solver/actions/runs/41343592444), after a NumPy integer-only model-export fix. No new v5 gameplay or true action-regret trials; both model JSON artifacts are experimental/unapproved.

## Fixed group partition
- Original v5 trace recovery: 1592 independent physical deals, 6101 stage decisions.
- Nested group training: 128, 384, 768, 1288 from 1288 available source deals, mixing old teacher natural traces and historical full-game source records; physical `game_id` is the unit.
- Historical replay diagnostic: all 256 original 115k deals and their 964 naturally reached v5 stage decisions excluded from fitting. **Not** a new untouched prospective test: 115k has been examined earlier in this project.
- Separate DAgger student-visited stress cohort: 48 deals, 231 genuine-v5 annotated stage decisions excluded from fitting.
- Models: unmodified fixed two-head random forests, 48 trees/head depth 10, per-group stage/candidate weighting. Full observable 347 features vs 167-feature portable ablation without individual `seven:<card>` and `bottom:<card>` membership flags. Identical 0.5 keep threshold. The portable variant still retains key card line-specific interactions: its generalization to actual replaced cards is NOT validated.

## Archived historical 115k T2-era teacher-agreement test results

| Independent training groups | Full KEEP/MULL accuracy | Portable KEEP/MULL accuracy | Full choice accuracy | Portable choice accuracy |
|---:|---:|---:|---:|---:|
| 128 | 83.40% | 84.34% | 65.15% | 65.15% |
| 384 | 85.27% | 85.06% | 65.66% | 65.98% |
| 768 | 86.83% | 85.89% | 66.39% | 66.49% |
| 1288 | 86.41% | 86.93% | 66.70% | 65.77% |

Baseline 'always MULL' accuracy on these naturally reached 964 stages is 73.44%, NOT an actionable London policy (stage 7 must keep). Full-1288 balanced keep/mull accuracy 86.26%, portable-1288 balanced 86.49%. Joint exact bottom+keep agreement: 58.40% for each. Student-visited stress v5 KEEP agreement: 86.58% full / 87.88% portable, but bottom choice 57.58% each.

**Crucial bottom-selection denominator pitfall.** At stages 0 and 1, `keep_n=7`: there is only ONE legal candidate, so all bottom models receive 100% free accuracy. Recomputing across stages **2–7 only** (496 115k naturally reached stage records with actual choice), full-1288 bottom top1 accuracy was **35.28%**, portable-1288 **33.47%**, versus original structural-first **30.44%**. This is only +4.84pp and +3.02pp over a weak structural baseline. Stage2 alone: both 47.12%, precisely identical to structural first. Stage3 full 26.75% versus structural 25.48%. Claims of 66% overall bottom accuracy obscure limited nontrivial choice quality.

**Persistent keep-rate calibration mismatch.** On all historical 964 stage rows, v5 KEEP prevalence is **26.56%**. Full predicts keep on 33.30%, portable predicts keep on roughly 33% (from the archived report). On the 212 stage-1 v5-reached sevens, v5 keeps only **9.91%**, while full predicts 20.75%, portable 19.34%. On stage0 256 sevens, v5 keeps 17.19% vs full 23.05% / portable 22.66%. Although overall action accuracy is above the trivial majority baseline, false KEEP decisions still occur at exactly the high-leverage early stages. This is a key hypothesis for the missing v5 T2 goldfish gap, NOT proven physical regret.

**Model family ceiling warning.** A ~13-fold rise in independent training groups from 128 to 1288 added only ~2–3 percentage points of overall keep agreement and ~1–2 percentage points of bottom agreement. Bottom selection has barely improved; collecting 4096 independent additional v5 teacher-only deals may be low value unless features, candidate ranking objective, and/or sampling distribution change. Before that expensive step, consider a paired teacher disagreement / direct physical advantage approach on difficult early KEEP states. A predeclared new prospective *full-game* comparison is still required to establish whether any speed improvement occurred.

## Artifacts
- Raw evaluated report: `benchmark_results/v40_true_v5_teacher_learning_curve.json`
- Frozen unapproved full: `models/v40_true_v5_archived/v40_archived_actual_v5_full_1288_RESEARCH.json`
- Frozen unapproved portable: `models/v40_true_v5_archived/v40_archived_actual_v5_portable_1288_RESEARCH.json`
- Serialized source training script: `dack_simulator/validation/v40_train_recovered_true_v5_curve.py`
- Follow-on: treat model as behavior-clone **candidate**, not verified v5-equivalent mulligan or win-rate model.
