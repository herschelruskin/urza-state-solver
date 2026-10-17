# Dack fair-randomness / hidden-information audit (2026-10-16)

The historical `dack_boonweaver_exact99_20261016.py` and `dack_bucknard_minimal_swaps_20261016.py` **remain frozen**. Their rates are conditional perfect-information beam-search upper-bound *proxies*, not independently realized fair gameplay. Do not overwrite their reported results.

## Implemented in the opt-in fair playthrough

New entry point: `dack_fair_random_deployment_v1_20261016.py`.

| Original behavior / potential exploit | Fair mode treatment | Verification |
|---|---|---|
| Bucknard d4 from SHA256(state key): several action sequences may produce different favourable rolls; hindsight branch choice possible. | A separate per-game physical d4 stream is sampled using an independent RNG **after** activation is committed, never from action-state identity. One call per committed activation. | `--audit` validates 1,2,3,4 and that the event is blocked from the beam search. Per-game log records actual rolls. |
| Paying for Bucknard and choosing whether KCI sacrifices it may be decided after viewing the die in an outcome-tree search. | Payment source and KCI-response state are fixed in a one-Treasure template BEFORE the d4 result is sampled. The only post-sampling modification is addition of `roll-1` Treasures. | `--audit` verifies both KCI and normal handoff. |
| T1 beam keeps many endings, then retrospectively picks whichever works with the exact top card drawn T2; analogously T2/T3. | Commit a SINGLE turn-ending state by visible-state heuristic BEFORE the following draw. The search is rerun only after the revealed draw. | `fair_turn` + `turnstart`. |
| Gemstone Caverns pregame exile could be chosen after looking at T1 draw. | Select the pregame exile from opening-hand/battlefield information only, BEFORE the T1 draw. | `choose_pregame`. |
| Mana Vault upkeep-untap options could be evaluated after drawing and chosen retroactively. | Choose one upkeep option by visible-state score BEFORE revealing draw. | `turnstart`. |
| Mulligan policy might exploit a lucky hash-based Bucknard roll in its conditional success estimates. | Use a neutral, undisclosed two-Treasure roll during approximate EV-based mulligan screening. Never use the actual future die value. | `simulate` sets independent roll only after the keep decision. |
| Kozilek's Command scry X + draw and Giant's Boulder scry 2 might optimize a choice using still-hidden later cards. | Choose a legal ordering using the X visible scry cards ONLY; never choose based on deeper unseen cards. | `visible_scry_order`, `honest_kozilek_scry_draw`, `honest_boulder_casts` and audit assertions. |

## IMPORTANT remaining limitations — not fully fixed

1. **Within-turn hidden shuffle/draw lookahead**. When a tutor shuffles the library and a later action draws in the same turn, the underlying beam may still compare branches using the post-shuffle next card. The legacy `shuffled_unknown` produces a deterministic deck-multiset pseudo-shuffle. Selecting tutors based on the identity of unseen subsequent cards would be invalid. Correct solution: model shuffle/draw as chance nodes with action commitment before realization (or belief-state rollouts). Merely reseeding a hash **does not fix** this.
2. **Other reveal/draw in the same search action**. We hardened Kozilek's Command and Giant's Boulder by fixing their scry choices from revealed cards only, but other draw/search sequences may still expose unobserved future cards in the beam. They need an explicit atomic event/commit mechanism.
3. **Random additional cards**. `Component Pouch` also uses state-key-derived die rolls in the inherited engine; it is **not in the exact99 Boonweaver deck** tested here. If reinstated, it needs a separate real-event resolver. Other random cards require individual audit.
4. **One-activation-per-turn policy**. This v1 experiment blocks additional Bucknard activations after the first to avoid choosing branches through uncommitted random events. This may undervalue very rare copy/repeat lines.
5. **Mulligan calibration and incomplete-information policy**. Existing continuation thresholds and sampled mulligan EV were calibrated with the old search. The fair execution mode reuses them, with neutral-roll assumptions, to enable a controlled comparison; this is not an optimized imperfect-information mulligan policy.
6. **Finite beam/heuristic**. Choosing one end-of-turn state (instead of preserving multiple hypothetical futures) is nonclairvoyant but may be significantly suboptimal versus a strong real player. Compare deck arms **within this mode**, not its absolute rate directly against the previous optimistic T2 baseline.
7. **Opponent actions and card resolution**. The goldfish assumes a specified resource model for Smothering Tithe and related interactions. Actual opponent decisions, responses, Bucknard control donation's downside, and post-Dack win resolution remain outside scope.

## Usage and analysis contract

Run `python dack_fair_random_deployment_v1_20261016.py --audit` to check safety invariants. Test paired `current` and `buck_worldmap` using identical shard/game IDs and `--beam 160 --candidates 8`; pool using `dack_fair_random_deployment_v1_pool.py`. Each result includes the independent actual die outcomes and a record of each turn's chosen action/commitment.

**Interpretation:** The new mode is a transparent, conservative nonclairvoyant approximation for turn-end decisions and Bucknard d4 resolution. It is not a full information-set Monte Carlo tree search and does not yet remove every oracle effect from the inherited action generators. Further development should add atomic event transitions and an information-set action policy for shuffle/draw/scry sequences.
