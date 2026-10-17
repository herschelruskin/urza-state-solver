# Dack Realistic Information Beam — experimental branch (2026-10-17)

## Branch separation

- **Full Beam (historical, unchanged):** \`dack-boonweaver-exact99-20261016\`, plus the independently archived World Map → Bucknard test in \`dack-bucknard-worldmap-confirm-n1024-20261016\`. These benchmarks measure optimistic conditional success and remain frozen.
- **Realistic Beam (this branch):** \`dack_realistic_information_beam_20261017.py\`. It keeps the intra-turn beam but commits decisions before revealing unobserved draws and dice. It must report separately from Full Beam. There is **no conversion** between the two rates.

## Intra-turn search

Same inherited Dack action engine, combo eligibility check, mana-payment options, and multiplayer London mulligan policy. Beam width is configurable. The engine explores mana sequencing and retains a frontier of plausible states.

After a turn's beam ends, it does **not** choose among the frontier based on the true top card of the library. Instead:

1. Deduplicate candidates by a signature that contains the **library multiset, not the hidden library order**.
2. Retain the top \`--pass-cap\` candidate states under the public resource heuristic. This is an explicit bounded approximation, **not** an optimal policy.
3. For each candidate, sample \`--draw-samples\` uniformly selected next cards from the remaining deck multiset, using separately seeded counterfactual futures. These do **not** depend on the real top card.
4. Reveal each counterfactual card, then do a smaller search (\`--rollout-beam\`, \`--rollout-depth\`) for immediate commander deployment and residual resource quality.
5. Select the T1 or T2 line by average prospective value. **Only then** reveal the real T2/T3 card.

The preceding strategy is a *one-step information-aware Monte Carlo rollout*. Realized next draws are not used to choose the pass state. It is still a bounded heuristic with candidate pruning and short rollouts; large samples and more robust information-state handling should be considered before presenting absolute T2 as a realistic win rate.

## Bucknard chance events

The only card replacement in the benchmark is World Map → Bucknard's Everfull Purse.

- Bucknard's casting/activation costs and source movement use inherited validated rules.
- Candidate activation line, mana payment and KCI response are chosen **before** observing the die.
- Each plan is evaluated by averaging all four possible outcomes. The actual d4 is sampled from a separate game-seeded PRNG **after** the choice is committed. The actual roll is not derived from the hashed game state, and it cannot be changed by choosing another precursor state.
- After the die is revealed, ordinary intra-turn beam search resumes.
- Component Pouch is not present in either exact deck and is not supported by this correction.

## What remains imperfect

1. The inherited action generator can still compare lines after unobserved **within-turn draws** / tutor shuffles. Those need explicit chance-node or public/private state separation at every observation boundary. Realistic Beam v1 removes the most blatant *turn-boundary* and Bucknard oracle only.
2. Monte Carlo next-draw modelling assumes **all** cards in library are hidden when choosing a turn-end pass, even if a tutor put a card on top. It therefore fails to exploit **legitimately known top cards**. State must carry known-top-card metadata to fix this.
3. Future Bucknard activations in counterfactual rollouts are suppressed to prevent oracle exploitation. This can undervalue the card; real-game activation is explicitly handled at each realized turn.
4. The current rollout value function uses proven immediate success plus a small resource tie-break and finite depth. It is not necessarily optimal.
5. No opponent responses, donation downside, or full post-Dack Boonweaver line is simulated.
6. Earlier Full Beam results used gameplay beam 240. The initial Realistic Beam pilot uses 120 to manage rollout cost; this is **not** a matched compute-budget comparison.
7. London continuation thresholds were calibrated under historical engine assumptions and remain provisional.

## Test/interpretation contract

- First ensure the hidden-order invariance regression and paired smoke both pass.
- Run current vs Bucknard using identical game IDs, corresponding deck hashes, seat-selection seeds and candidate policy.
- Report T1, T2 and T3 separately, and paired confidence intervals.
- Keep old Full Beam output separately as a useful optimistic ceiling.
- Do **not** treat Realistic Beam's absolute rates as live cEDH game win rates or a proven lower bound on optimal performance.

The workflow lives in \`.github/workflows/dack_realistic_information_beam_20261017.yml\`.
