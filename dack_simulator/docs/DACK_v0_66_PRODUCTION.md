# DACK v0.66 production checkpoint

## Engine change from v0.64
Search-scoring only; game rules/actions are unchanged. Flexible white-capable lands are now credited in white-potential scoring so bounded frontier search does not systematically undervalue legal white-mana lines.

Affected scoring coverage includes City of Brass, Mana Confluence, Gemstone Mine, Starting Town, Tarnished Citadel, and conditional Spire of Industry white potential. Tarnished Citadel is also included in the white-source diversity signature.

## Production beam
Beam 40 was shown to produce impossible negative paired outcomes for lands that weakly dominate Plains in the life-ignored speed objective. Adversarial convergence testing found some failures persisting through 160/200. Beam 240 is the first candidate that passed the fresh strict dominance audit.

### Fresh beam-240 dominance audit
- City of Brass: 10 contexts, 44 future/seat rows, 0 target-worse-than-Plains rows, all context deltas 0.000.
- Mana Confluence: 10 contexts, 48 future/seat rows, 0 target-worse-than-Plains rows, all context deltas 0.000.
- Tarnished Citadel: 10 contexts, 40 future/seat rows, 0 target-worse-than-Plains rows, all context deltas 0.000.

Gemstone Mine and Starting Town are not used as strict invariants because their special rules can make them strategically non-equivalent to Plains in some sequences.

## Production rule
Use v0.66 with beam=240 for the next full matched mana-source/infrastructure screen. Do not pool the older beam-40 N=10 debug screen into production estimates.