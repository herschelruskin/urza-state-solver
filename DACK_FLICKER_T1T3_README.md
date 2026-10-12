# Dack flicker: T1-T3 deployment fork (2026-10-12)

This experiment is isolated on branch `dack-flicker-current100-t1t3-20261012`, forked from
`dack-lotus-crypt-policy-sweep-20261010`. The previous Boonweaver benchmark is unchanged.

## Frozen deck and objective

- `dack_flicker_current100_20261012.txt`: exact Commander deck, 99 library + Dack.
- 35 land-capable cards including Emeria's Call and Razorgrass Ambush.
- Eight alternative flicker creatures: these are deliberately **not** modeled as a deterministic
  automatic combo finish.
- The positive result `win_turn=1/2/3` means **Dack can legally be cast** by that turn in
  the goldfish state. It does *not* mean the game has been won or that the cast was protected.

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
- Smothering Tithe has **zero guaranteed opponent-paid Treasures** in the conservative
  goldfish; multiplayer yield requires a separate scenario model.
- Other cards whose value depends entirely on opponents (e.g., Cursed Totem, Blind
  Obedience, Defense Grid) are retained in the deck but cannot be credited with wins.
- The eight creatures' ETB/combo graph and later turn-four-plus card advantage are
  intentionally not solved here.
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
