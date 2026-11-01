# DACK v33b — Prospective full-game protocol (frozen before 115k)

Experimental branch `dack-v33b-capability-regret-20261101`, not production.

The pairwise ridge bottom-only candidate was trained exclusively from 112k
physical counterfactuals, no 113k or 110k training. It was evaluated
without any adjustment on separate fresh 114k physical games:
64 independent groups; 46 bottom eligible, 10 altered bottoms;
paired conditional Turn2 +2.9297pp across all 64 groups (8 rollouts
per intervention per eligible hand; group-bootstrap CI +0.1953..+6.6406pp).
T1 +0.7813pp; T3 +2.9297pp. Small number of decisive groups makes
this promising but NOT proof of prospective full-game benefit.
All models remain unapproved.

## Final frozen prospective test, no tuning permitted

Run complete paired N256 real physical 99-card games
`115000..115255`. For each game ID and identical canonical 99-slot
stage shuffles and seat, compare these THREE policies in isolated
independent interpreters:

1. v5 expensive reference, unmodified.
2. v27 baseline, unmodified.
3. v33b bottom-regret candidate: run the EXACT v27 London keep/mull
   logic first, using v14 bottom for all v27 Qkeep and continuation
   estimates; ONLY after v27 has chosen a final KEEP may the 112k-trained
   bootstrap ridge choose another bottom among existing legal
   v14/v27-value/v18-top3/analytical proposals. Conservatively
   require lower-quartile predicted T2 regret > 0.01 and median T3
   > -0.025. No beam search in mulligan decisions. Keep the actual
   92 unseen physical slot order; append chosen legal bottoms.

Assert v27 and v33b have identical complete London stage histories,
same seen sevens, same keep/reject outcomes, same kept stage and number
of cards. They can differ ONLY in which legal cards were bottomed.
Check that this equality holds for ALL 256 games; fail any shard if not.

Each finished kept hand uses the same strict stable-dice actual
beam160 gameplay engine to deploy Dack through Turn3. Never pass
realized unseen future information to the keep/bottom policies.
No changes to core engine, exact legal effects, card text, chance,
mulligan mechanics or beam frontier.

Primary outcome cumulative by Turn2. Report T1 exact and cumulative
T3 as predeclared safeguards, individual policy counts, paired gains,
losses and physical-game bootstrap confidence intervals, actual
gameplay time and v5/v33b and v5/v27 runtime ratios. Also report
count of altered bottoms. Different policies share initial physical
games but may have different kept hands; this is legitimately different
future action space, not a direct exact hidden-world coupling claim.

Use 64 independent 4-game Actions shards (max 16 workers);
archive all original outcomes and report to v33b research branch.
Do not train/tune on 115k. Do not promote unless direct prospective
evidence is convincing, not merely conditional 114k confirmation.

Goldfish Dack deployment, NOT interactive cEDH win probability.
