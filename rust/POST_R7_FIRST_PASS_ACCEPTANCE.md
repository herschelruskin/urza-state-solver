# Post-R7 First-Pass Policy Acceptance

Status: **CLOSED / FROZEN**

This checkpoint closes the post-R7 policy-correctness pass before any new card-advantage gameplay surface is added.

## Accepted policy changes

- Reusable mana sources are preserved through upkeep/draw unless a current legal decision needs mana.
- Main-phase action ordering is demand-driven: already-affordable casts and genuine engine activations are not pre-empted by unnecessary mana production.
- Native Monolith untap is classified separately as `ManaSetup`, preventing it from being mistaken for a strategic engine activation.
- Staged tutor decisions prefer a real modeled target over legal fail-to-find when at least one real target exists. Target selection among real cards remains deterministic/public and is not Oracle-driven.

## Acceptance evidence

- write gate for policy / bridge / rollout / clippy: green
- committed policy/bridge implementation: `cfb8b653d00760b38800fe5cc52098ab0cbb96fb`
- independent committed-head read-only gate: run `34163577869`, conclusion `success`
- no Ring, Uthros, or Clue-draw gameplay mechanics were added during first pass
- no hidden-library information was added to policy selection

## Freeze boundary

Second-pass work may expand modeled Magic mechanics, but should not retune first-pass policy ordering at the same time. Any policy change after this checkpoint requires its own diagnostic justification and before/after measurement.

The historical 128-world engine/tutor sample remains the pre-first-pass baseline. Subsequent samples should retain the same opening/hidden worlds where possible so policy-only and mechanics-only deltas remain attributable.
