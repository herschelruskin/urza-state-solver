# Post-R7 Second-Pass Card-Advantage Surface

Status: **COMPLETE — Ring + Uthros + Gadgeteer/Clue accepted**

First-pass policy behavior is frozen by `POST_R7_FIRST_PASS_ACCEPTANCE.md`. This pass expands missing gameplay mechanics without simultaneously retuning policy.

## Slice order

1. **The One Ring — ACCEPTED**
   - normal artifact cast
   - beginning-of-upkeep burden life-loss trigger
   - `{T}` activated draw ability: add burden, then draw equal to burden
   - production CandidateBridge action and exact rules/bridge regressions
   - protection/indestructible are irrelevant to the current goldfish environment and remain deferred
   - mechanics commit: `9cca746a8e8aab95532c09b896f40a519161f8fd`
   - identical 128-world checkpoint after first-pass + Ring:
     - 6,524 audited decisions
     - 1 natural terminal
     - Ring: 4 cast opportunities / 4 selected; 19 activation opportunities / 11 selected
     - tutors: 83 resolutions, 82 real targets, 1 legal fail-to-find

2. **Uthros Research Craft — ACCEPTED**
   - Station activation on supported creatures at sorcery speed
   - charge counters on the exact Uthros object
   - Station reads current modeled creature power on resolution; an activation-time power snapshot is used only as the leave-before-resolution last-known-information fallback
   - current post-R7 public power surface includes printed/base power for supported deck creatures and dynamic Urza Construct artifact-count power; otherwise-unmodeled temporary/static power modifications are explicitly deferred
   - 3+ artifact-cast trigger: draw one, then add a charge counter, resolving before the triggering artifact spell
   - 12+ creature/flying/power striation remains deferred because it does not affect the current goldfish card-advantage objective
   - mechanics commit: `22685e82f0e28f7003319e905aaf665fcc85fba2`
   - write gate `34166762413`: cards, frozen R4 acceptance, rules, CandidateBridge, diagnostic builds, clippy, and rustfmt all green
   - identical 128-world checkpoint `34166916939`:
     - all 128 rollouts completed successfully
     - 6,670 audited decisions
     - 1 natural terminal
     - Uthros: 17 cast opportunities / 13 selected; 87 Station activation opportunities / 76 selected
     - tutors: 81 resolutions, 81 real targets, 0 fail-to-find
   - interpretation: the new Uthros surface is actively used and liveness-clean, but this slice alone did not increase natural terminal count beyond the post-Ring checkpoint

3. **Clue cash-in / Gadgeteer completion — ACCEPTED**
   - `{2}, Sacrifice this artifact: Draw a card`
   - payment and sacrifice are committed as activation costs; draw occurs only when the activated ability resolves
   - Clue sacrifice uses the common artifact-sacrifice lifecycle, so a token Clue ceases to exist rather than entering the graveyard
   - player-chosen sacrifice of an attached Clue preserves the existing `AttachedSacrificeDeferred` boundary; the activation is rejected before any mana or sacrifice cost is partially committed
   - CandidateBridge exposes the activation only when the public state has a legal generic-two payment and the real rules transition is supported
   - CandidateBridge ordinary action-family count expands from 28 to 29; Clue cash-in has its own public semantic key
   - mechanics commit: `77ace29a23964a1b27f782d6f7a6c90f9c913a40`
   - write gate `34167692955`: card-database regression, rules, CandidateBridge, diagnostic builds, clippy, and rustfmt all green
   - identical 128-world checkpoint `34167841723`:
     - all 128 rollouts completed successfully with no `NoCandidate` or step-limit failure
     - 6,625 audited decisions
     - 2 natural terminals, up from 1 on the post-Uthros matched population
     - Clues were visible at 48 audited decisions
     - Clue cash-in was a legal candidate at 4 decisions and selected at 3
     - Uthros shifted from 189 candidate / 98 selected decisions to 186 / 95, with Station activation opportunities/selections moving from 87 / 76 to 84 / 73 as trajectories changed
     - tutors remained 81 resolutions, 81 real targets, 0 fail-to-find
   - interpretation: Clue cash-in is both reachable and actively selected. On this fixed small population the added card-flow branch coincides with one additional natural terminal; the matched total establishes a real trajectory change, while exact per-world causal attribution is intentionally left to a targeted diagnostic rather than inferred from the aggregate alone.

## Attribution gate

Each accepted slice passed:

- targeted `urza-rules` regressions
- `urza-policy-bridge` tests and action-family audit
- full affected crate tests + clippy/rustfmt
- exact matched-world recheck when relevant
- same 16 openings x 8 hidden worlds (`245632..245639`) engine/tutor diagnostic once stable

No Oracle action is copied into the production policy. Oracle remains diagnostic-only and may use hidden state; Rust action generation and selection remain information-faithful.

## Second-pass conclusion

The three missing card-advantage surfaces targeted by this pass are now executable in production Rust rules and CandidateBridge: The One Ring, Uthros Research Craft, and Gadgeteer-created Clue cash-in. The fixed 128-world population progressed from 1 natural terminal after Ring, stayed at 1 after Uthros while Uthros became heavily used, and reached 2 after Clue cash-in while tutors remained fully live. Remaining scarcity should therefore be treated primarily as a policy/value/search-quality question rather than evidence that these three engines are mechanically absent.
