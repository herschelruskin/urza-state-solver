# Oracle Ceiling Follow-up Required

The Phase-1 information/timing audit found legal strategic choices that the current
validated Oracle does not fully enumerate.  This does **not** invalidate the Oracle
as a regression target for its existing modeled semantics, but it means we should
not currently describe it as a strict mathematical upper bound for every legal
line involving these cards.

Phase 1 remains additive-only.  Do not silently modify `urza_solver.py` on the
information-boundary branch.  Correct the Oracle separately with focused rules and
search regressions.

## Gap 1 — Urza {5} permission lifetime

Current Oracle behavior:

`pay 5 -> shuffle -> inspect exiled top -> immediately play/cast if legal`

Actual modeled requirement:

`pay 5 -> shuffle -> exile top -> permission remains until end of turn`

Consequences the current Oracle can miss:

- spin, take another action, then cast the exiled card later;
- multiple spins accumulating multiple playable exiled cards;
- sequencing a known exiled card around top-card information;
- using a permission during a later priority window when normal timing/Valley
  Floodcaller allows it;
- choosing MDFC land/spell face later in the turn.

Required Oracle follow-up: add explicit temporary play-permission state or an
Oracle-equivalent exact representation, expire permissions at end of turn, and
include them in exact-state/search identity.

## Gap 2 — simultaneous controlled cast-trigger order

Current Oracle `artifact_cast_triggers()` chooses one fixed favorable order:

1. Valley Floodcaller;
2. Artificer's Assistant scry(s);
3. Uthros draw;
4. Gadgeteer investigate;
5. Vexing Bauble handling is compressed separately.

Actual legal choice can depend on currently known information.  Examples:

- if the current top is a desired card, resolve Uthros draw before Assistant scry;
- if the current top is poor, resolve Assistant scry before Uthros draw;
- order Vexing Bauble below value triggers on a no-mana cast;
- Gadgeteer's Clue can create artifact-ETB triggers above older unresolved stack
  objects, with priority windows between resolutions.

Reality Chip and Fortune Teller's Talent are not triggers here, but they can make
the newly exposed top legally knowable after casting completes and before the
controlled triggers are ordered.

Required Oracle follow-up: branch or otherwise exactly optimize legal controlled
trigger order at the relevant cast windows while preserving performance and search
identity.

## Gap 3 — top-card legal-information visibility

The previous information adapter treated Chip attachment / FTT level-2 play access
as if they were also required to *look* at the top.  Card text is broader:

- Reality Chip lets its controller look at the top while present, attached or not;
- Fortune Teller's Talent lets its controller look at the top at level 1.

The Phase-1 non-Oracle information layer is corrected.  The five-seed legal-info
collapse profile should be rerun after Phase 1 because the old 21.1% compression
measurement was produced under the narrower visibility model and may therefore be
slightly optimistic.

## Acceptance policy

Until the Oracle follow-up is complete:

- keep all existing Oracle regression tests as stability checks;
- do not call non-Oracle > Oracle automatically impossible or a policy bug;
- inspect any such case for one of the known timing gaps above;
- do not merge Oracle corrections into the Phase-1 boundary branch;
- make each Oracle correction on a focused branch with explicit smoke/regression
  coverage and fresh benchmark comparison.
