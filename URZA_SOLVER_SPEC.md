# URZA_SOLVER_SPEC.md

## 1. Scope

This document is the repository-level source of truth for the Urza state
solver behavior accumulated during development. It is intentionally
focused on rules and solver semantics that have already mattered in
implementation. If code and this document disagree, investigate rather
than silently choosing one.

Commander: **Urza, Lord High Artificer**.

The current baseline is an **Oracle solver**: it may exploit known deck
order during search. This is useful as an upper-bound / idealized
sequencing model. A separate future policy fork will constrain
information and behavior to more human-plausible knowledge.

## 2. Core game-state requirements

The state must preserve enough information to determine future legality
and value, including where relevant:

-   turn;
-   hand;
-   battlefield;
-   graveyard;
-   command zone;
-   library order / top-card information;
-   lands played;
-   tapped/untapped permanents;
-   summoning sickness;
-   colored and generic mana;
-   Urza cast state and commander tax;
-   whether a spell has already been cast this turn;
-   active current-turn Banishing Knack / Retraction Helix target;
-   temporary copy/effect duration;
-   relevant sacrifice/tap status;
-   combo/win status and family;
-   action trace.

## 3. Urza

Urza must be cast legally from the command zone for **{2}{U}{U}**.

-   Infinite colorless mana cannot satisfy the two blue symbols.
-   Commander tax applies on repeat command-zone casts.
-   If Urza is bounced to hand, he is no longer on the battlefield and
    his artifact-mana ability is unavailable.
-   If Urza would go to the graveyard and the modeled replacement/choice
    sends him to the command zone, subsequent command-zone casting uses
    the appropriate tax.
-   Track the turn Urza was cast.
-   Urza allows an untapped artifact to tap for **{U}**. This matters
    for ETB/untap sequences: an artifact can sometimes be tapped for U,
    untapped by a trigger, and tapped again.
-   Do not use pre-Urza infinite-mana shortcuts to bypass actually
    casting Urza.

## 4. Top-of-library casting

### The Reality Chip

-   Reconfigure costs **{2}{U}**.
-   When correctly attached/active, it permits playing cards from the
    top as implemented by the card.
-   **Grafdigger's Cage** prevents the relevant creature spell casting
    from the library/top and therefore can lock Chip/FTT lines where
    applicable.
-   The solver may remove Cage through legal bounce/sacrifice/removal
    lines such as available bounce effects or Grinding Station
    interactions; removal is not assumed free.

### Fortune Teller's Talent (FTT)

-   FTT top-casting requires that a spell has already been cast during
    the current turn.
-   Track that condition explicitly.
-   Model the relevant FTT levels separately; existing win families
    include `Top + FTT L2 + producer` and `Top + FTT L3`.
-   Do not use hidden-library terminal shortcuts that bypass the
    required legal sequence.
-   Grafdigger's Cage restrictions must be respected.

### Sensei's Divining Top

Top actions must respect their actual costs/tap requirements. Top is
part of several complete win families, including:

-   Top + Reality Chip;
-   Top + FTT L3;
-   Top + FTT L2 + producer;
-   Top + Gadgeteer + producer.

Oracle Mode may use full library-order knowledge. This is intentionally
stronger than human play and will later be contrasted with a
knowledge-constrained policy fork.

## 5. Knack / Helix / Cam engine

Relevant cards include:

-   Banishing Knack;
-   Retraction Helix;
-   Sewer-veillance Cam;
-   Battered Golem;
-   Valley Floodcaller;
-   Urza and other legal creatures when they can serve as the bounce
    target.

Important rules:

-   Knack/Helix creates a **current-turn** activated bounce ability on
    the chosen creature. The grant belongs to that exact battlefield permanent,
    not merely a `(name, mode)` label, so same-name copies remain distinct when
    their resulting states are strategically different.
-   A stale Knack/Helix card in the graveyard must not create a false
    active effect.
-   The chosen creature must obey tapping/summoning-sickness
    restrictions.
-   Cam is a mana-value-1 artifact.
-   Cam ETB and LTB behavior must be represented through the normal
    artifact/trigger machinery.
-   Cam's activated sacrifice ability costs **{3}{U}**, sacrifices Cam,
    and draws two cards; its LTB can create the relevant untap
    interaction exactly once as appropriate.
-   A Cam loop does not inherently require Golem/VFC specifically if
    another legal creature (including Urza) can carry the Knack/Helix
    ability.
-   Transmute Artifact can find Cam.
-   Artifact tutors must not incorrectly classify creature-only cards
    such as Gadgeteer as artifacts.

Validated complex route:

**Spellseeker -\> Banishing Knack -\> bounce Spellseeker -\> replay
Spellseeker -\> Transmute Artifact -\> Sewer-veillance Cam**

The solver has reached this route through ordinary legal actions rather
than a terminal shortcut.

## 6. Monolith / Power Artifact / Gadgeteer families

Validated complete families include:

-   Power Artifact + Grim Monolith;
-   Power Artifact + Basalt Monolith;
-   Basalt Monolith + Forensic Gadgeteer.

Mana, tap, untap, and colored-mana requirements must remain explicit. A
recognized partial engine is not automatically a win unless the complete
modeled win condition is reachable.

**Accepted Oracle state-space prune:** Power Artifact and Reality Chip do not
attach/reconfigure onto temporary Chrome Dome copy permanents. Those attachment
lines have no modeled strategic role in this singleton deck and would make the
existing name-based attachment fields ambiguous. All retained non-copy targets
remain available.

## 7. Chrome Dome

Chrome Dome is a validated natural win family.

-   Respect the end-step timing required before the player's turn to
    copy the relevant object.
-   Copies disappear at the appropriate end-of-turn duration.
-   Do not let stale copies persist into later turns.
-   Chrome Dome is both an artifact and creature where its actual
    characteristics require that classification.
-   Existing integration tests cover Chrome Dome with Station and
    Golem-style engines.

## 8. Grinding Station / Battered Golem / artifact ETB machinery

Artifact ETBs can create important immediate mana/action sequences.

-   Grinding Station's untap behavior from artifact ETBs must be
    represented.
-   Battered Golem's artifact-ETB untap behavior must be represented.
-   Both abilities say "an artifact," not "another artifact," so each
    permanent sees its own entry and every controlled copy triggers.
-   With Urza present, an artifact can be tapped for U before an untap
    trigger resolves and potentially tapped again afterward. The production
    search keeps this fast maximum-mana representation but records the final
    post-trigger Urza tap as refundable until that specific blue mana is spent.
    This preserves the legal alternative of leaving Station/Golem untapped for
    a native or Knack/Helix tap without multiplying every artifact ETB into all
    optional tap configurations.
-   Grinding Station's native `{T}, sacrifice an artifact` activation may
    sacrifice Station itself, a tapped artifact, or a token. When milling is
    strategically live (top access, Cage removal, or an active graveyard
    resource), every legal artifact sacrifice is enumerated. Purely proactive
    mill branches outside those states are intentionally suppressed as a
    throughput/search-space prune.
-   Uthros/Station has dedicated action handling and must remain covered
    by smoke tests.
-   Positive-artifact replay loops with Knack/Golem must be reachable
    when legal.

## 9. Draw / sacrifice artifacts

Do not model draw artifacts as free draws when they have activation
costs.

Examples explicitly audited during development:

-   Witching Well;
-   CAM / Sewer-veillance Cam;
-   bauble-style artifacts where sacrifice and/or tapping is required.

Respect mana costs, tap costs, sacrifice costs, and timing.

Every true library-to-hand draw is audit-visible by card name. This includes
normal draws; modeled opponent-fed Remora, Rhystic Study, and Faerie
Mastermind draws; delayed Mishra's/Urza's Bauble draws; Uthros, Ring, Top,
Clue, Probe, activated Mastermind, Coliseum, Sea Gate Restoration, and the
other implemented draw/sacrifice artifacts. Searches to hand, casts from the
top, scry, mill, and Urza's exile/cast ability are not draws.

The end-turn transition preserves its established card assignment: pending
Bauble draw(s) consume the next cards first, followed by Remora, Rhystic, and
environmental Mastermind draws. All are available before a pending Remora
upkeep choice; the normal draw occurs only after that choice. Multiple Bauble
triggers retain their individual source names in the audit trace.

Named automatic draws are trace-cardinality neutral. They are rendered as
details of the existing turn/upkeep entry rather than new semantic actions,
because deterministic shuffles and Oracle's same-stage tie-break use the
historical trace length. Draw observability must not change zones, search
scores, pruning, shuffle order, or selected outcomes.

## 10. Mystic Remora

Mystic Remora retains the separate multiplayer environmental assumption of
two opponent-fed cards per cycle. Its cumulative upkeep is nevertheless a
real rules/search decision:

-   a newly entered Remora has zero age counters;
-   after untap at each following upkeep, put its cumulative-upkeep trigger on
    the stack; responses occur while the old age-counter total is still real;
-   when that trigger resolves, add one age counter, then branch between paying
    generic mana equal to its age counters and sacrificing it;
-   newly untapped mana sources may pay, but prior floating mana and Mana
    Drain's precombat-main-phase mana may not;
-   opponent-cycle and ordered Bauble draws may precede the choice, but the
    normal draw step follows it;
-   modeled instant-speed payment enablers and a Chain of Vapor bounce remain
    available while the trigger is pending;
-   ordinary main-phase actions and Saga lore advancement wait until the
    upkeep choice resolves;
-   leaving the battlefield and later re-entering resets its age.
-   before the pending trigger resolves, the restricted response window may
    cast Chain of Vapor or Knack/Helix, channel Otawara, and activate modeled
    mana or Aether Spellbomb abilities; it does not expose sorcery-speed
    actions;
-   if the old Remora leaves during that window, its pending payment/sacrifice
    instruction has no remaining effect on the new object, and a later recast
    starts at age zero.
-   when the upkeep response set hits `ACTION_CAP`, cap protection preserves
    materially distinct reset routes by source (Chain, Otawara, Banishing
    Knack, Retraction Helix) rather than collapsing them into one generic
    bounce result.

Age and pending-upkeep phase are future-legality state and must be represented
in exact, dominance, and action-cache identities. Search closes the upkeep
branch before starting the turn's ordinary action-depth loop.

## 11. Faerie Mastermind

Faerie Mastermind has an activated ability costing **{3}{U} / four mana
total** to cause the relevant draw behavior. Do not treat that draw as
free.

## 12. Everflowing Chalice

Everflowing Chalice must respect multikicker / variable mana paid and
the resulting charge counters/mana production. It should not be treated
as a fixed-cost/fixed-output rock.

## 13. Prized Statue

Prized Statue must correctly model its ETB and LTB Treasure generation.
Ensure each event occurs only when the corresponding event actually
happens.

## 14. Sacrifice lands

Sacrifice-based lands such as:

-   City of Traitors where applicable to its actual trigger/land
    sequencing;
-   Crystal Vein;
-   Saprazzan/Saprazzan-style relevant land in the deck;

must not provide reusable mana after they have been sacrificed or
otherwise lost. Preserve the exact cost/zone transition semantics
implemented for the card.

## 15. Cephalid / Ipnu and specialty lands

Cephalid Coliseum / Ipnu Rivulet-style actions and other niche land
abilities must be modeled as explicit legal actions with their costs and
conditions, rather than generic free effects.

## 16. Chain of Vapor

Chain of Vapor historically caused pathological branching.

It must remain a legal active search action, but branch generation
should avoid useless combinatorial explosion. The heuristic restriction
developed for Chain should focus it on strategically relevant situations
such as:

-   Station;
-   Golem;
-   Gadgeteer;
-   Uthros;
-   a line where bouncing is needed to produce mana or enable another
    play.

Do not let Oracle-only knowledge of a useful future top card become the
sole reason a human-inaccessible Chain line is considered strategically
obvious in the future policy fork.

Implemented own-permanent bounce rules also include:

-   Chain of Vapor can legally target our nonland permanents, including Mystic
    Remora; each modeled copy after the first requires sacrificing a land;
-   Otawara channels for {3}{U}, reduced by {1} per legendary creature we
    control, and can legally target our artifact, creature, enchantment, or
    planeswalker, including Remora;
-   Aether Spellbomb pays {U} and sacrifices itself to target a creature only;
-   Banishing Knack and Retraction Helix cost {U}, select a creature, and grant
    it a tap ability that can legally return a nonland permanent, including
    itself or Remora, provided that creature can pay a tap-symbol cost;
-   **Oracle goldfish prune:** our Urza and Construct tokens are intentionally
    excluded as bounce destinations for Chain/Otawara/Spellbomb/Knack-Helix.
    This is not a Magic legality restriction. It removes a costly Urza reset and
    token-destruction branches with no retained goldfish value. Urza may still
    carry a Knack/Helix grant to bounce another retained target;
-   returned retained cards go to hand and returned tokens cease to exist.

Repurposing Bay is a sorcery-speed artifact activation. It pays {2}, taps Bay,
and sacrifices another artifact, then searches for an artifact card with mana
value exactly one greater, puts it directly onto the battlefield, and shuffles.
The costs are subject to applicable artifact-ability reductions but cannot be
reduced below one mana. Ordinary tokens have mana value zero; Chrome copy
tokens retain the copied artifact's mana value. Grafdigger's Cage is evaluated
after the sacrifice cost, a qualified hidden-zone search may fail to find, and
the shuffle completes before the found permanent's ETB triggers resolve.

Urza's Saga chapter III is represented as an independent pending trigger once
the third lore counter is placed. Legal responses may occur before it resolves.
In particular, Otawara can return Saga to hand; the pending chapter-III search
still resolves, and the final-chapter sacrifice applies only if the Saga remains
on the battlefield after the chapter ability leaves the stack. Chain of Vapor
and Knack/Helix cannot return Saga because they require a nonland permanent.

## 17. Tutors and mana value

All 99 deck cards should have known mana-value semantics.

Important metadata constraints already audited:

-   artifact card designations;
-   creature card designations;
-   lands have MV 0 for relevant checks;
-   X costs use correct printed mana-value semantics outside the stack
    and correct paid-X semantics where relevant;
-   Phyrexian and MDFC mana-value behavior must be explicit;
-   Urza's Saga printed-mana-cost target set must be correct;
-   Dizzy Spell eligibility;
-   Muddle the Mixture eligibility;
-   Spellseeker eligibility;
-   Mystical Tutor eligibility;
-   Merchant Scroll eligibility;
-   artifact tutors can find legal artifacts such as Sol Ring / Mana
    Vault but not Forensic Gadgeteer;
-   Sapphire Medallion applies only where its reduction legally applies,
    including the generic portion of relevant X costs;
-   Transmute Artifact must implement the unpaid-difference graveyard
    branch.

Tutor branching is currently a major performance concern. Do not remove
distinct tutor targets merely because many payment/sacrifice paths
exist.

## 18. Other tracked interaction

The simulation should be able to record interaction encountered in hand
or on the battlefield up to the win state, including categories/cards
such as:

-   bounce effects;
-   counterspells;
-   Pithing Needle;
-   Disruptor Flute;
-   Grafdigger's Cage;
-   Otawara.

Stop the interaction count at the win state.

## 19. Mulligans and kept hands

The solver should preserve the actual kept hand and game-state
plan/trace.

Two modes are conceptually distinct:

1.  **Oracle mulligan evaluation**: by default compares candidate
    7/6/5/4 keeps using full information. With `--min-keep 3`, it appends
    a fresh-seven London keep-three stage that bottoms four cards.
2.  **Sequential London mulligan / policy mode**: evaluates hands in
    realistic sequence and bottoms cards according to the chosen policy.

Do not conflate these modes in reported results.

## 20. Search limits

Typical development settings have included:

-   horizon through T7;
-   beam around 300 for smoke/performance work;
-   action cap 60;
-   search depth up to 100.

These are search parameters, not Magic rules.

A cap audit found that only a minority of evaluated states hit the
60-action cap, but some pre-cap states had hundreds of legal actions and
tutor actions dominated discarded branches. Therefore tutor-target
retention must be measured before finalizing cap behavior.

## 21. Validated natural win-family diversity

A deterministic 10-seed family smoke produced natural wins across:

-   Chrome Dome;
-   Basalt + Gadgeteer;
-   Knack/Helix + Cam;
-   Top + FTT L2 + producer;
-   Top + Gadgeteer + producer;
-   Top + Reality Chip.

In that smoke, Knack/Helix + Cam appeared naturally in 2/10 seeds. This
is a regression/coverage observation, not an estimate of the deck's true
combo-family probability.

## 22. Future policy fork

The future constrained solver should address the fact that Oracle Mode
can make impossible human decisions based on exact future deck order,
especially with:

-   scry/top manipulation;
-   Sensei's Divining Top;
-   tutor sequencing;
-   bounce decisions;
-   whether to pursue a line because of a hidden future draw.

Do not weaken Oracle Mode to solve this. Fork the policy behavior so
Oracle remains an explicit upper-bound comparator.
