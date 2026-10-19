# Dack realistic beam: reward debugging, October 19, 2026

## Comparisons we will keep

- **Full Beam**: historical omniscient upper-bound goldfish, never overwrite. T2 and T3 rates include conditional multi-frontier foresight.
- **Realistic v2**: future-draw expected-value beam with 3 sampled draws. N32 World Map T2 28.125%, T3 59.375%; Bucknard T2 31.25%, T3 62.5%.
- **v4 known-top**: correctly use Enlightened/Loyal Tutor known top; selected extra candidate slots. N32 World Map T2 31.25%, T3 68.75%; Bucknard T2 34.375%, T3 71.875%.
- **v5 corrected**: same v4 tutor information, but 12 draws and 6 conditional continuation samples. N32 World Map T2 28.125%, T3 68.75%; Bucknard T2 37.5%, T3 75%. This is *not* uniformly superior; 4x planning cost. The corrected N32 report is at \`benchmark_results/dack_v5_population_n32_KNOWNTOP_CORRECTED_20261019.json\`. An **older** report without this suffix was generated with a broken tutor hook and must not be used.
- **v6 (this branch)**: stratified probability-weighted draw futures, still retains all v4 observations and v2 beam. First N32 run: \`.github/workflows/dack_v6_stratified_reward_n32_20261019.yml\`.

## Observed failure mechanism and reward error

- Game IDs 0/1 required known-top tutoring to evaluate actual planned next draw. Treating them as a fresh random next draw loses legitimate information.
- Game ID 31, Bucknard: **tapped Mana Vault + Staff of Compleation + Chrome Mox** was assigned estimated value 0.4293, versus **untapped Mana Vault** 0.1790. Across an independent, frequency-weighted census of *all* next-card identities, they had **1/90 (1.1111%)** and **10/91 (10.9890%)** T2 deployment success respectively. The v2 reward misranked them by a large margin.
- Enlarging pass candidate set from 9 to 24 did NOT recover any of seven selected T2 misses.
- Adding a flat bankable-mana reward also recovered zero, and lost an existing T3 game.
- v4 known-top semantics recovered three additional T3s for each deck on the N32 common seeds.
- Corrected v5 recovered a hand with untapped Mana Vault on T2, but its N32 benefit was mixed and did not justify blanket promotion.

## Why v6 tests stratified sampling

Twelve iid samples *with replacement* from ~90 future cards can fail to test a particular single-card out (~87% chance of not testing it). That makes a candidate's observed P(T2) look nearly zero, even if an alternative has a meaningful ~10% success probability. More samples reduce variance slowly and are expensive.

v6 divides the still-unknown remaining library into broad public card-role strata. It samples every nonempty stratum, then uses normalized inverse sampling weights. This **does not** put a favourable card on top of the real deck. The actual draw remains hidden until after committing the action.

The estimator is consistent for ex ante value, but the engine is still imperfect: nested counterfactual rollouts can inherit within-turn unseen draw advantages, some genuinely known cards from other actions remain untracked, card-role strata use a heuristic taxonomy, and a small pilot cannot distinguish effects on 1-3 percentage-point margins.

## Rules for promotion

- Only compare real T1/T2/T3 deployments using independent matched-seed samples.
- Require no hidden-order sensitivity for the policy decision and valid weights summing to exactly one.
- Audit action replay failures separately; do not reward an oracle-successful path simply because its actual upcoming card worked.
- V4 remains the recommended realistic-branch baseline unless v6 improves an **unselected** sample without major regressions; consider a second independent-seed N256 before promoting.
- Goldfish Dack deployment is not protected cEDH win probability. Neither Bucknard donation downside nor true post-Dack Boonweaver loops is represented.
