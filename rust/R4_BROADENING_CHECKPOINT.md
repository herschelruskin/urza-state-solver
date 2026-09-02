# R4 broadening checkpoint

## Scope

This checkpoint broadens the accepted R4-start foundation through two related engine clusters:

1. exact Power Artifact + Monolith rules and terminal families;
2. Sensei's Divining Top access through Reality Chip / Fortune Teller's Talent, with exact producer identities and Grafdigger's Cage interaction.

It is **not** the R4 acceptance gate. Producer trigger execution, Chrome Dome, Knack/Helix recurrence, and the remaining audited terminal families are still open R4 work.

## Power Artifact and exact targeted stack state

Power Artifact is now a rules-active targeted Aura rather than a battlefield shortcut.

- casting locks an exact artifact target before the spell is put on the stack;
- the stack carries a typed `AuraSpell` with exact execution target identity;
- `InformationState` exposes the target through a canonical object reference;
- strategic ValueKey therefore distinguishes otherwise-similar states whose Power Artifact spells target different objects;
- the Aura resolves attached to the exact live target, or goes to graveyard if the locked target is no longer legal/live;
- Urza free-cast permissions can cast Power Artifact while preserving the same public target boundary;
- the attached Aura reduces only that artifact's activated-ability generic component by `{2}`;
- Power Artifact and Forensic Gadgeteer reductions share the audited one-mana floor;
- Power Artifact + Grim Monolith and Power Artifact + Basalt Monolith are named terminal families, conservatively requiring Urza context and a ready attached Monolith.

This required the first R4 model/information/value schema bump:

- model: `urza_model_r4a_2026_09_01` for the Power Artifact slice;
- information: `information_state_v5_r4`;
- ValueKey: `value_key_v5_r4`.

## Reality Chip / Fortune Teller's Talent top access

The second broadening slice adds executable top-access primitives rather than only terminal labels.

### Reality Chip

- Reality Chip enters in an explicit creature mode;
- continuous top-card visibility is modeled while Chip is on the battlefield;
- reconfigure is a sorcery-speed stack-based `{2}{U}` artifact activated ability;
- reconfigure locks an exact public creature target and uses a typed targeted activated-ability stack object;
- on resolution Chip changes to explicit attached mode and records the exact attachment;
- detach is also stack-based and restores creature mode;
- while attached, Chip grants the modeled library-top play/cast permission.

### Fortune Teller's Talent

- FTT enters at explicit Level 1;
- Level 1 continuously exposes the top card;
- Level 2 and Level 3 advancement use stack-based activated abilities at their modeled printed costs;
- Level 2/3 top-play permission requires `spell_cast_this_turn`;
- Level 3 reduces the generic portion of spells cast from outside the hand by `{2}`;
- the exact FTT level is represented in permanent state and therefore in InformationState/ValueKey.

### Top-changing information

A shared continuous-visibility refresh updates known-top information after top-changing transitions while a Chip/FTT look effect is live. Policy still receives only InformationState; no hidden middle order is exposed.

### Library-top play primitives

- lands can be played from the top through the active Chip/FTT permission, consuming the normal land play;
- ordinary supported spells can be cast from the top through the same permission;
- top-card identity must match the currently known/true top at execution;
- targeted Auras from the library remain explicit deferred scope rather than being silently flattened;
- Grafdigger's Cage blocks the modeled library spell cast path but does not block a land play from the library.

The top-access slice advances the current namespaces to:

- model: `urza_model_r4b_2026_09_01`;
- information: `information_state_v6_r4`;
- ValueKey: `value_key_v6_r4`;
- rules: `r4_top_access_v3`.

The frozen R3 audit remains on the accepted R3 model/rules namespace.

## Producer prerequisites

The accepted Top terminal families use three exact producer identities. They are retained as distinct cards, not merged into a generic strategic identity:

- Grinding Station;
- Battered Golem;
- Forensic Gadgeteer.

Current R4 primitive coverage proves their terminal role while preserving deferred execution work:

- Grinding Station's native mill/sacrifice activation and artifact-ETB untap trigger remain to be implemented;
- Battered Golem's “does not untap normally” behavior is active, while its artifact-ETB untap trigger remains to be implemented;
- Forensic Gadgeteer's static artifact-activation reduction is active; its artifact-cast/investigate trigger remains to be implemented.

Grafdigger's Cage is also active as a top-cast blocker. Its broader library-to-battlefield creature prohibition remains later R4 work.

## Terminal catalog coverage

The public-information terminal detector now covers **7 of the 13 audited named families**:

1. Power Artifact + Grim;
2. Power Artifact + Basalt;
3. Top + Reality Chip;
4. Top + FTT L3;
5. Top + FTT L2 + producer;
6. Basalt + Gadgeteer;
7. Top + Gadgeteer + producer.

All terminal recognition still requires:
- no unresolved stack object;
- no pending contingent decision;
- Urza on the battlefield;
- the exact visible prerequisite state for that family.

Top-access families additionally require a nonempty library, ready Top, and absence of Grafdigger's Cage where the loop requires casting from the library.

## Coverage

Current R4 card database exposes **41 active identities**.

Newly promoted in this broadening:
- Power Artifact — `RULES_ACTIVE`;
- The Reality Chip — `PRIMITIVE_ACTIVE`;
- Fortune Teller's Talent — `PRIMITIVE_ACTIVE`;
- Grafdigger's Cage — `PRIMITIVE_ACTIVE`;
- Grinding Station — `PRIMITIVE_ACTIVE`;
- Battered Golem — `PRIMITIVE_ACTIVE`.

Primitive status is deliberately narrow and each coverage reason records the intrinsic behavior still deferred.

## Validation

Validated implementation head: `6578b369ef7c857ef0574ae6d2552a85f90377a4`.

GitHub Actions run `33588985108`: PASS.

- locked dependency graph: PASS;
- rustfmt: PASS;
- strict Clippy (`-D warnings`): PASS;
- workspace/all-target tests: **90 passed, 0 failed**;
- benchmark compilation: PASS;
- R0 audit: PASS;
- R1 catalog audit: PASS;
- R2 core audit: PASS;
- R3 staged-search audit: PASS;
- R4 engine/win audit: PASS;
- R4 audit reports 41 supported active identities and the seven terminal families listed above.

## Remaining R4 work

R4 acceptance remains open. The major remaining engine/terminal work is:

- Grinding Station sacrifice/mill execution and artifact-ETB untap trigger;
- Battered Golem artifact-ETB untap trigger;
- Forensic Gadgeteer artifact-cast/investigate trigger;
- broader Grafdigger's Cage library-entry prohibition;
- Chrome Dome copy behavior and all three accepted Chrome Dome terminal families;
- Mana Vault details needed by the Chrome Dome + PA + Gadgeteer + Mana Vault family;
- Banishing Knack / Retraction Helix exact-creature temporary grants;
- Valley Floodcaller, Battered Golem, and Sewer-veillance Cam recurrence prerequisites;
- the three Knack/Helix terminal families;
- remaining high-frequency value/mana/trigger engines required before deterministic R5 rollout policy can be meaningfully recreated.

The same rejection rules remain in force: no hidden-order access, no card-role identity merging, no optimistic tutor-presence wins, and no performance shortcuts that reduce legal strategic capability.
