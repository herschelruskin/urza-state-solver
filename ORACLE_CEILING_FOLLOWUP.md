# Oracle Ceiling Follow-up Status

The Phase-1 information/timing audit found legal strategic choices that the older
validated Oracle did not fully enumerate.  The focused
`oracle-ceiling-permissions-trigger-order` branch now repairs the major known
**play-permission, cast-stack, trigger-order, inter-trigger-priority, and artifact
entry-trigger** gaps while retaining the older Oracle as a regression reference.

The branch has been validated with focused stack/ETB smokes, the complete Phase-1
acceptance suite, and the mandatory Oracle rules suite.  A fresh benchmark is still
required before merge because exact trigger/scry branching materially enlarges some
search frontiers.

## Gap 1 — Urza {5} permission lifetime — FIXED

Old behavior:

`pay 5 -> shuffle -> inspect exiled top -> immediately play/cast if legal`

Corrected behavior:

`pay 5 -> shuffle -> exile top -> permission remains until end of turn`

The Oracle now:

- stores live Urza play permissions in true state;
- permits arbitrary intervening actions and additional spins;
- permits delayed land/spell/MDFC use at its real timing;
- consumes only the permission actually used;
- expires unused permissions at end of turn while leaving the card exiled; and
- includes permission multiplicity in exact/Markov/dominance/value identity.

Focused regression: `oracle_urza_permission_smoke.py`.

## Gap 2 — controlled cast-trigger order and priority — FIXED

The old `artifact_cast_triggers()` macro used one favorable fixed order.  Production
Oracle casting now uses an explicit compact `oracle_stack` while the legacy helper
remains available only as a regression helper.

The corrected Oracle now models:

- every distinct legal ordering of Valley Floodcaller, Artificer's Assistant,
  Uthros Research Craft, Forensic Gadgeteer, and Vexing Bauble cast triggers;
- priority between individual trigger resolutions;
- newly generated triggers above older unresolved stack objects;
- Offer targeting one of our still-pending noncreature spells;
- Mox Diamond's discard choice when it would enter, after earlier triggers may
  have drawn a land;
- Chrome Mox's imprint trigger after entry, including cards drawn before it
  resolves; and
- exact scry choices for stack-resolving Assistant triggers rather than forcing
  the legacy deterministic scry heuristic.

Focused regressions:

- `oracle_trigger_order_smoke.py`
- `oracle_stack_priority_smoke.py`

## Gap 3 — artifact entry-trigger stack and priority — FIXED FOR ENTRY EVENTS

Artifact entry is no longer one atomic `artifact_etb_triggers()` production macro.
The Oracle now collects the actual controlled entry-trigger batch, orders it, and
exposes priority between individual resolutions.

Covered entry triggers include:

- Grinding Station: one optional untap trigger **per artifact that entered**;
- Battered Golem: one optional untap trigger **per artifact that entered**;
- Tezzeret, Cruel Captain: one loyalty trigger **per artifact that entered**;
- Witching Well / Giant's Boulder: exact scry 2;
- Sewer-veillance Cam: target selected when stacked, then real tap/untap/decline
  outcomes on resolution;
- Chrome Mox: imprint in the same entry-trigger batch as the other entry triggers;
- Prized Statue: its Treasure trigger as a real stack object; and
- Gadgeteer Clues, Saga/Bay/Transmute/Reshape/Whir entries, Chrome Dome copies,
  Seat of the Synod, Urza's Construct, and other converted direct-entry paths.

Two Treasure cases are deliberately distinct:

1. **Prized Statue entry** is sequential/nested: Statue enters and creates the first
   Station/Golem trigger wave; later Statue's ETB trigger resolves and creates a
   Treasure; that Treasure enters and creates a second fresh trigger wave above
   older unresolved objects.
2. **An Offer You Can't Refuse** creates its two Treasures simultaneously.  One
   Station and one Golem therefore each trigger twice in the same entry batch;
   Tezzeret likewise triggers twice.

The old maximum-mana Station/Golem + Urza compression is retained only as an
additional legal representative, alongside exact decline/untap/priority branches.

Focused regression: `oracle_etb_stack_smoke.py`.

## Gap 4 — top-card legal-information visibility — FIXED IN PHASE 1

The previous information adapter treated Chip attachment / FTT level-2 play access
as if they were required to *look* at the top.  Phase 1 corrected this:

- Reality Chip allows looking at the top while present, attached or not;
- Fortune Teller's Talent allows looking at the top at level 1;
- scry does not expose the card underneath the actively scried cards; and
- after a scry finishes, continuous look permission immediately reveals the new
  physical top before the next priority/trigger-order decision.

The old five-seed legal-information collapse profile should therefore be rerun; the
previous ~21.1% collapse figure used the narrower visibility model.

## Residual scope — leave-battlefield triggers inside legacy action macros

The artifact **entry** stack is now explicit, but two leave-battlefield triggers are
still compressed inside the legacy `remove_perm()` transition:

- Prized Statue going to the graveyard -> Treasure;
- Sewer-veillance Cam leaving -> tap/untap target creature.

This matters most when the zone change occurs inside another macro action.  Examples
include sacrificing Statue/Cam to Grinding Station, Repurposing Bay, Reshape, or
Transmute Artifact.  Full rules-exact treatment would require representing the
underlying spell/activated ability itself as a pending stack object in those legacy
macros so the leave trigger can be placed above it (or deferred until a currently
resolving spell finishes) with the correct priority windows.

Therefore, even after this branch merges, describe the Oracle as the
**validated clairvoyant regression/ceiling model for its retained semantics**, not as
an absolutely rules-complete mathematical upper bound for every possible Magic
stack line.  Do not interpret a future non-Oracle result marginally exceeding Oracle
as automatically impossible until this residual class is checked.

## Acceptance before merge

Required before merging this branch back to `development`:

- focused Urza permission smoke: green;
- controlled trigger-order smoke: green;
- inter-trigger priority smoke: green;
- artifact ETB stack smoke: green;
- Phase-1 acceptance: green;
- mandatory Oracle rules suite: green;
- `git diff --check`: green; and
- fresh reproducible Oracle benchmark/performance comparison after the larger exact
  branching is quantified.
