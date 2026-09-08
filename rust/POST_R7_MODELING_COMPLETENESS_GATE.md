# Post-R7 modeling completeness gate

## Purpose

This gate exists to prevent catalog presence, primitive support, or milestone labels from being mistaken for complete gameplay modeling.

The active deck has 95 distinct identities including Urza. Every identity must be explicitly classified at the goldfish-model boundary before strategic-policy conclusions are accepted.

## Authority

This is post-R7 validation work under `rust/AGENTS.md`.

- Current Comprehensive Rules + pinned/current Oracle text remain authoritative for card behavior.
- Python gameplay logic is not an implementation source.
- Existing R2/R3/R4/post-R7 primitives are evidence, not automatic completeness.
- A historical `RULES_ACTIVE` label does not grandfather a card through this gate.

## Registry

`rust/data/goldfish_model_gate.v1.tsv` is the gate registry. It must contain exactly one row for every active catalog identity.

Allowed dispositions:

- `COMPLETE`: every Oracle clause relevant to the explicit goldfish model is implemented with executable rules evidence; irrelevant or environment-owned clauses are explicitly accounted for in the rationale/evidence record.
- `GOLDFISH_IRRELEVANT`: no unresolved clause can change legal own-side actions, resources, information, timing, triggers, targets, costs, zones, or terminal reachability in the explicit goldfish model. The exemption must be justified rather than inferred from the card being "interaction".
- `ENVIRONMENT_DEFERRED`: all intrinsic/base behavior needed by the goldfish engine is complete; only opponent-driven behavior owned by the explicit environment model remains deferred.
- `AUDIT_REQUIRED`: the engine exposes some gameplay surface, but clause-level goldfish completeness has not yet been established.
- `IMPLEMENTATION_REQUIRED`: the active identity is not currently exposed as a playable rules role and cannot be accepted without implementation or an explicit audited exemption.
- `ENVIRONMENT_SPLIT_REQUIRED`: an old environment-deferred classification mixes opponent-driven behavior with intrinsic/base behavior that still needs an explicit audit or implementation.

Only `COMPLETE`, `GOLDFISH_IRRELEVANT`, and `ENVIRONMENT_DEFERRED` are resolved dispositions.

## Clause-level rule

The unit of completeness is the Oracle clause, not the card name.

For every card, the audit must account for all clauses that can affect any of the following in a goldfish rollout:

- whether the card can legally be cast, played, activated, triggered, targeted, attached, copied, sacrificed, or otherwise used;
- mana production, costs, cost reductions/increases, alternate/additional costs, resource conversion, or untapping;
- hand/library/graveyard/exile/battlefield movement, tutoring, drawing, scrying, surveilling, milling, recursion, or public information;
- cast/ETB/LTB/sacrifice/untap triggers that can feed another modeled engine card;
- counters, power/toughness changes, copy effects, or object identity when those can affect Station/Uthros/recurrence/terminal logic;
- pregame choices, land-entry conditions, delayed events, upkeep/draw-step costs, or timing permissions;
- any own-spell/self-target line that can be strategically useful even if the card is normally called interaction.

Opponent-only combat/damage/prevention/protection/text may be exempted only when the rationale shows it cannot alter the goldfish state or another relevant trigger.

## Acceptance rule

The modeling completeness gate is GREEN only when all of the following are true:

1. The registry is total over the exact 95-identity active catalog with no duplicates or unknown names.
2. Every `COMPLETE` card is runtime-supported by the current Rust card database.
3. Every entry has a non-empty audited rationale.
4. No entry remains `AUDIT_REQUIRED`, `IMPLEMENTATION_REQUIRED`, or `ENVIRONMENT_SPLIT_REQUIRED`.
5. Dedicated rules fixtures cover each required modeled surface before its disposition is promoted to `COMPLETE`.
6. The three opponent-driven engines are not accepted as pure environment deferrals until their intrinsic/base behavior is separately accounted for.
7. Policy/terminal tuning is not an acceptance substitute for missing card rules.

## Initial state

The v1 registry is deliberately conservative.

- All currently unsupported active identities begin as `IMPLEMENTATION_REQUIRED`.
- Faerie Mastermind, Mystic Remora, and Rhystic Study begin as `ENVIRONMENT_SPLIT_REQUIRED`.
- Every currently supported identity begins as `AUDIT_REQUIRED`, including cards previously labeled `RULES_ACTIVE`.

This means the first gate run is expected to be RED. That failure is the backlog, not a CI defect.

## Work order

Clear the gate by strategic impact rather than by alphabetical order:

1. mana sources, zero/one-mana acceleration, alternate mana costs, untap effects, and sacrifice-for-mana effects;
2. tutors, transmute/search/recursion, draw/filter/scry/surveil/library manipulation;
3. combo/recurrence pieces and power/copy/counter interactions that feed terminal witnesses;
4. modal DFC front faces and utility lands whose non-mana modes can affect assembly;
5. self-targetable/own-spell interaction and cast-trigger enablers;
6. opponent-only/environment-only text and final explicit exemptions.

After the gate becomes GREEN, rerun the frozen strategic populations before diagnosing terminal precursor sequencing or sacrifice/resource policy timing.
