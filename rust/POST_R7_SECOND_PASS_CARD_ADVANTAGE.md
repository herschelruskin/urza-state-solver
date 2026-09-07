# Post-R7 Second-Pass Card-Advantage Surface

Status: **IN PROGRESS**

First-pass policy behavior is frozen by `POST_R7_FIRST_PASS_ACCEPTANCE.md`. This pass expands missing gameplay mechanics without simultaneously retuning policy.

## Slice order

1. **The One Ring**
   - normal artifact cast
   - beginning-of-upkeep burden life-loss trigger
   - `{T}` activated draw ability: add burden, then draw equal to burden
   - production CandidateBridge action and exact rules/bridge regressions
   - protection/indestructible are irrelevant to the current goldfish environment and remain deferred

2. **Uthros Research Craft**
   - Station activation on supported creatures at sorcery speed
   - charge counters on the exact Uthros object
   - 3+ artifact-cast trigger: draw one, then add a charge counter, resolving before the triggering artifact spell
   - 12+ combat sizing/flying remain irrelevant to the current goldfish objective unless a later diagnostic proves otherwise

3. **Clue cash-in / Gadgeteer completion**
   - `{2}, Sacrifice this artifact: Draw a card`
   - exact sacrifice lifecycle through the common artifact-removal path
   - CandidateBridge generation using public state only

## Attribution gate

After each slice:

- targeted `urza-rules` regressions
- `urza-policy-bridge` tests and action-family audit
- full affected crate tests + clippy/rustfmt
- exact matched-world recheck when relevant
- same 16 openings x 8 hidden worlds (`245632..245639`) engine/tutor diagnostic when the slice is stable

No Oracle action is copied into the production policy. Oracle remains diagnostic-only and may use hidden state; Rust action generation and selection remain information-faithful.
