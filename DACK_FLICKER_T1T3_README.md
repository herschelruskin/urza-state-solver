# Dack flicker: T1-T3 deployment fork (2026-10-12)

This experiment is isolated on branch `dack-flicker-current100-t1t3-20261012`, forked from
`dack-lotus-crypt-policy-sweep-20261010`. The previous Boonweaver benchmark is unchanged.

## Frozen deck and objective

- `dack_flicker_current100_20261012.txt`: exact Commander deck, 99 library + Dack.
- 35 land-capable cards including Emeria's Call and Razorgrass Ambush.
- Eight alternative flicker creatures: creatures are white Chrome Mox imprint cards (except
  strategically reserved Radiant Solar), not modeled as cast spells or resolved combo pieces.
- Provisional combo-hand blocking rule: only **Abdel Adrian, Gorion's Ward AND Radiant Solar
  simultaneously in hand** prevents a counted Dack deployment. A lone combo creature in
  hand does not block it. This is a provisional simplification, not a proof the pile wins.
- A positive `win_turn=1/2/3` means the solver can assemble Dack's {4}{W}{W} payment
  **without the provisional pair-in-hand block**. It is not a full combo win rate, a
  protected-cast rate, or a literal unconditional casting-availability rate.

## New early-deployment mechanics

- Chrome Mox: every white nonartifact nonland card may be imprinted, including seven of
  the eight flicker creatures and the spell faces of both white MDFCs. Radiant Solar is
  excluded by **strategy**, not Magic's imprint legality.
- Old mandatory-in-library Boonweaver/Preston/Roaming Throne condition removed.
- Corrected Thorn of Amethyst: taxes noncreature artifact spells; does not tax creature Dack.
- United Battlefront: `{3}{W}`; picks up to two qualifying noncreature, nonland permanents
  with printed mana value at most 3 in the top seven. The rest go to the bottom in random
  order. Cards enter *without being cast*. It is a controlled alternative, **not** in
  the frozen baseline 100.
- The One Ring: tapping adds a burden counter then draws that many cards; Rings copy
  resolves ahead of the original, drawing 1+2 with zero existing counters.
- Mind Stone ({2}): taps for {C}, or {1}, tap and sacrifice to draw one;
  Rings can copy the draw activation.
- Scout's Warning ({W}) and Abeyance ({1}{W}): cast-and-draw cantrips with normal
  inherited Thorn, Levy, Trinisphere and Deafening Silence restrictions.
- Gleaming Splendor: +1 Treasure per completed opponent cycle under the frozen
  assumption; {2}{W} targeted ability can draw one for us, and Rings may copy it.
- Charitable Levy: its noncreature tax, third spell counter, sacrifice to draw and
  tapped-Plains tutoring are handled by the inherited oracle-audited engine.
- Staff of Compleation can draw by tapping (costs 4 life),
  make colored mana by tapping (costs 2 life), and untap for {5}.
  These Staff-specific life payments are tracked against an initial 40-life
  budget; other life payments/damage remain untracked in this goldfish.
- Throne's draw-two costs {3} **paid entirely in chosen-color white mana**; Rings
  can copy its activated draw ability for {2}.
- Throne of Eldraine: taps for four **restricted** white toward monowhite Dack; its
  activated draw cost must be paid using other white mana.
- Staff of Compleation: taps for white at the cost of 2 life, or draws at the cost
  of 4 life; life does not bind this early deployment-only goldfish.
- Fomori Vault: can add colorless; optional 3-mana top-X selection, discard and random
  bottoming implemented.
- Rings + Basalt: finite 12-colorless proxy only *after* the two external mana required
  to bootstrap the first copy, not an automatic win.
- Rings + Voltaic Key: additional {2} for two untaps including Voltaic Key itself.
- Mirage Mirror: selected nonlegendary mana-source copy lines, reset every new turn.
- Existing KCI artifact sacrifices, Mycosynth Gardens, Keys, and Dack mana payment
  engine reused from v0.77.

## Limitations (must not misrepresent as match win rates)

- Opponents' spells, counters, removal, and interaction are not modeled.
- Smothering Tithe generates **exactly three modeled Treasures per completed opponent turn cycle**
  (one per opponent), per the user's four-player assumption. It produces none on its entry
  turn. This is a scenario assumption, not a guarantee that every real opponent declines
  the tax. Gleaming Splendor's existing independent +1 Treasure/cycle remains active.
- Other cards whose value depends entirely on opponents (e.g., Cursed Totem, Blind
  Obedience, Defense Grid) are retained in the deck but cannot be credited with wins.
- The eight creatures' ETB/combo graph and later turn-four-plus card advantage are
  intentionally not solved here.
- Staff paid life is tracked using a dedicated state ledger to prevent
  infinite draw via repeated untaps. Other life costs/damage remain
  outside this early deployment model, so match win rates are not inferred.
- The Mind Stone's {5}{W} harness and ensuing end-step flicker are deferred to
  turn-four-plus modelling. In T1-T3, its indestructible {W} mana mode is implemented.
- Opponent-cast spells triggering Charitable Levy are not simulated; only our spells
  increment its counters in the early goldfish.
- This fork presently uses a deliberately bounded subset of Mirage Mirror targets.
- The existing lambda=0.5 London mulligan continuation values remain calibrated to
  an older configuration; paired early comparisons may use them, but re-calibration
  is required before treating estimates as final.
- Mirage Mirror has a deliberately limited selection of early-useful copy targets;
  this is not a general oracle-accurate MTG game engine.

## Commands

```bash
python dack_flicker_t1t3_batch.py --audit
python dack_flicker_t1t3_batch.py --variant baseline --shard 0 --games 4 --beam 240 --out baseline_000.json.gz
python dack_flicker_t1t3_batch.py --variant battlefront_over_prismatic --shard 0 --games 4 --beam 240 --out battlefront_000.json.gz
```

For a 1,024-game run, use **16 shards of 64 games** (`--shard 0..15 --games 64`) per variant,
each with the same game-id range. Pool counts from all sixteen shard files after
verifying deck hashes, unique game IDs, and the same seed mapping.

## Verification

`.github/workflows/dack_flicker_v078_smoke.yml` runs code compilation,
unit-style mechanical assertions, and an actual full-deck one-game integration
smoke on each fork update. Old baseline files and branches are not edited.

## Frozen, repeatable benchmark automation

- `.github/workflows/dack_flicker_t1t3_n1024.yml` runs automatically in
  four-game smoke mode when first added, and supports manual `workflow_dispatch`.
- Choose `mode=full`, `variant=baseline` for N=1024 at beam=240; manual full runs
  split into 32 shards of 32 seeded games with max six shards in parallel.
- Supported comparison variants are `battlefront_over_prismatic` and
  `battlefront_over_amulet`. United Battlefront remains {3}{W} = four total.
- Shards are uploaded separately so partial outputs are recoverable. The pool job
  runs only when all shards succeeded; it rejects mixed policies, deck hashes, beams,
  seeds, duplicated game IDs, missing rows, or non-contiguous game IDs.
- `dack_flicker_pool_1024.py` produces exact/cumulative T1-T3 proportions,
  Wilson 95% confidence intervals, seat and mulligan distributions.
- The pooled rates are deployment goldfish frequencies with the provisional
  Abdel+Radiant Solar hand-pair blocker, not four-player win rates.
- Recent audit fixes: prevent Fomori Vault from financing its own {3}, reset
  Mirage Mirror copying a Monolith before the next untap, disallow white from
  un-imprinted Gardens copies of Chrome Mox, track Staff paid life, and include
  incremental Tithe Treasures on opponent draws induced by Gleaming Splendor.
- The old continuation thresholds were originally calibrated on a different
  (Boonweaver) deck. Rerun/optimize mulligan policy after collecting baseline
  data, not by silently changing thresholds inside matched comparisons.
