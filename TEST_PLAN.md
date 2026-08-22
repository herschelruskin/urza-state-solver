# TEST_PLAN.md

## Purpose

The solver has enough card-specific logic that every implementation
change should be treated as a regression risk. This document defines the
minimum validation workflow.

## 1. Mandatory correctness suite

Run these after any rules-engine, card-metadata, legal-action,
state-transition, pruning-key, or win-detection change:

``` powershell
py -3 urza_solver.py --metadata-smoke
py -3 urza_solver.py --tutor-smoke
py -3 urza_solver.py --cam-smoke
py -3 urza_solver.py --commander-smoke
py -3 urza_solver.py --combo-smoke
py -3 urza_solver.py --remora-smoke
py -3 urza_solver.py --bounce-smoke --action-cap 60 --bottom-cap 4
py -3 urza_solver.py --bay-smoke --action-cap 60 --bottom-cap 4
py -3 urza_solver.py --draw-trace-smoke
py -3 urza_solver.py --mulligan-smoke
py -3 urza_solver.py --worker-config-smoke
```

Expected terminal markers:

``` text
METADATA SMOKE: ALL PASS
TUTOR SMOKE: ALL PASS
CAM SMOKE: ALL PASS
COMMANDER SMOKE: ALL PASS
COMBO SMOKE: ALL PASS
REMORA SMOKE: ALL PASS
BOUNCE SMOKE: ALL PASS
BAY / PRODUCER SMOKE: ALL PASS
DRAW TRACE SMOKE: ALL PASS
MULLIGAN SMOKE: ALL PASS
WORKER CONFIG SMOKE: ALL PASS
```

A change is not regression-safe if only its new focused test passes.

## 2. Commander correctness coverage

The commander smoke should continue to verify:

-   normal {2}{U}{U} command-zone cast;
-   real UU requirement;
-   infinite colorless cannot pay UU;
-   no pre-Urza infinite shortcut;
-   no FTT3+Top hidden-library terminal shortcut;
-   bounced Urza disables artifact-mana ability and moves appropriately;
-   graveyard-bound Urza can return to command zone as modeled;
-   commander tax applies on repeat command-zone cast.

## 3. Cam / Knack / Helix coverage

The Cam smoke should continue to verify:

-   Cam is classified as MV1 artifact;
-   cast-from-hand + artifact ETB path;
-   Transmute Artifact can find Cam;
-   current-turn Knack target can complete the Cam line;
-   stale graveyard Knack does not count;
-   summoning sickness / tapped target enforced;
-   Spellseeker tutor-chain pieces exist;
-   Cam {3}{U} sacrifice causes one legal LTB untap and draw two.

## 4. Metadata / tutor / X-cost coverage

The metadata smoke should continue to verify:

-   artifact designations;
-   creature designations;
-   known mana-value semantics for all 99;
-   critical artifact costs / land MV0;
-   X / Phyrexian / MDFC mana values;
-   Urza's Saga target set;
-   Dizzy / Muddle / Spellseeker / Mystical / Merchant eligibility;
-   artifact tutors cannot find Gadgeteer and can find legal mana
    artifacts;
-   Sapphire Medallion generic-X reduction behavior;
-   Reality Chip / Chrome Dome creature status;
-   temporary Chrome Dome copy attachment is intentionally pruned for Power
    Artifact and Reality Chip; retained singleton attachment targets remain
    name-unambiguous.
-   Transmute Artifact unpaid-difference graveyard branch.
-   tutor-cap diagnostics recognize every target-selecting tutor/search source,
    distinguish target destinations, record every tutor-bearing cap hit, and
    leave the retained `legal_actions()` list unchanged when enabled; fixed
    fetchland-to-Island searches are outside the target-diversity audit.
-   target-aware action-cap selection keeps the best-scoring representative of
    each tutor `(source, target, destination)` route when the representatives
    fit, retains Top, Cam, Reality Chip, Uthros, Basalt Monolith, and One Ring
    in a focused state with more than 60 raw actions, and applies the documented
    strict-cap strategic-target fallback when more than 60 routes exist.

## 5. Mystic Remora cumulative-upkeep coverage

`--remora-smoke` must verify:

-   the first upkeep adds an age counter and costs {1};
-   the second upkeep adds another age counter and costs {2};
-   sources untap before the payment decision;
-   an existing Saga mana ability is usable during upkeep while its next lore
    counter waits until the precombat main phase;
-   paying and voluntarily declining are distinct legal branches;
-   inability to pay sacrifices Remora;
-   prior floating mana and Mana Drain's main-phase mana cannot pay upkeep;
-   opponent-fed Remora draws remain independent of the later upkeep choice;
-   Bauble's delayed trigger can draw before upkeep, while the normal draw waits
    until after the choice;
-   a fetchland can find an Island and use it to pay before the normal draw;
-   Dramatic Reversal can legally untap an upkeep source and goes to graveyard;
-   Chain of Vapor and Otawara can bounce Remora with the trigger pending and
    reset its age;
-   Banishing Knack / Retraction Helix can be cast during the pending trigger,
    then a ready granted creature can tap to return Remora;
-   response states retain the existing age counters; the next counter and
    corresponding payment are applied together only when the cumulative-upkeep
    trigger resolves;
-   cap-hit upkeep action sets preserve decline, a payment continuation, and
    distinct legal reset routes for Chain, Otawara, Banishing Knack, and
    Retraction Helix when those routes are present;
-   upkeep payment closes before ordinary per-turn depth begins, while the
    post-horizon diagnostic snapshot does not branch an unsearched upkeep;
-   pending upkeep prevents main-phase win recognition;
-   completed upkeep states are win-checked before transition pruning;
-   leaving and recasting resets the age to zero;
-   age, pending-upkeep phase, and recoverable graveyard differences remain
    distinct in exact, dominance, and Chain-cache identities.

### Bounce and Remora-response coverage

`--bounce-smoke` must verify:

-   Chain of Vapor pays {U}, targets our nonland permanents including Mystic
    Remora, and requires one sacrificed land for each modeled copied target;
-   Otawara channels for {3}{U}, reduces that generic cost once per controlled
    legendary creature, targets our artifact/creature/enchantment/planeswalker,
    and is an ability rather than a spell; an attached Reality Chip is not a
    creature and gives no reduction;
-   Aether Spellbomb pays {U} and sacrifices itself to return a creature only,
    so it cannot target Mystic Remora; its {1} draw mode remains available;
-   Knack/Helix pays {U}, grants the selected creature its temporary tap
    ability, enforces summoning sickness and tapped status, and can return that
    creature itself or another retained nonland permanent including Remora;
-   Oracle goldfish pruning excludes our Urza and Construct tokens as bounce
    destinations across Chain, Otawara, Aether Spellbomb, and Knack/Helix, while
    still allowing Urza to carry a Knack/Helix grant used on another target;
-   bounced retained nontoken cards go to hand while bounced tokens cease to exist;
-   MDFC creature and land faces receive the correct target treatment;
-   Oboro pays {1} to return only itself and can activate while tapped because
    its ability has no tap-symbol cost;
-   the Remora response window permits the modeled instant/channel/activated
    responses, clears the old obligation after Remora leaves, resets a recast
    Remora to age zero, and excludes ordinary sorcery-speed actions;
-   Knack/Helix grants live on the exact creature permanent rather than a
    global `(name, mode)` target; two same-name permanents can therefore
    produce materially different legal results and canonical deduplication
    occurs only after the transition;
-   Chain's multi-step macro likewise distinguishes same-name permanent
    instances while applying the action, without putting ephemeral runtime IDs
    into canonical state hashes;
-   once Saga III has triggered, Otawara may bounce Urza's Saga and the
    independent chapter-III search still resolves; Chain/Knack/Helix cannot
    target Saga because it is a land.

### Repurposing Bay and producer-ETB coverage

`--bay-smoke` must verify:

-   Bay pays {2}, taps, and sacrifices another artifact as activation costs;
-   Sapphire Medallion (MV 2) can find Battered Golem (MV 3), put it directly
    onto the battlefield without casting it, and leave the exact post-cost
    mana/tap/graveyard state;
-   ordinary tokens have MV 0 while copy tokens retain the copied mana value;
-   Grafdigger's Cage is checked after activation costs are paid;
-   a qualified hidden-zone search can fail to find and still shuffles;
-   Bay shuffles before the found permanent's ETB triggers resolve;
-   Bay remains sorcery-speed because it is present only in the ordinary
    main-phase action set;
-   Grinding Station and Battered Golem trigger on their own artifact entry and
    every controlled copy receives an artifact-ETB untap trigger; with Urza,
    the fast representation takes the legal maximum-mana line and marks the
    final post-trigger Urza tap as refundable until that blue mana is spent;
-   a refundable Station/Golem can recover the legal leave-untapped alternative
    for Station's native mill or a Knack/Helix tap without branching every ETB
    into all tap configurations; once the represented blue is spent the refund
    option disappears;
-   in strategically live mill states, Grinding Station's native activation
    enumerates every artifact sacrifice, including Station itself, tapped
    artifacts, and tokens, with correct token graveyard handling. Production
    search deliberately suppresses otherwise purposeless proactive-mill
    branches to control state-space growth; this is a documented Oracle search
    pruning rather than a rules claim.

## 6. Named draw-trace coverage

`--draw-trace-smoke` must verify that every true library draw records the
actual card names without changing the resulting hand or library. Coverage
includes:

-   turn-one and later normal draws;
-   Mystic Remora, Rhystic Study, and Faerie Mastermind environmental draws;
-   Mishra's Bauble and Urza's Bauble delayed draws, including distinct source
    attribution when more than one trigger is pending;
-   Uthros Research Craft, The One Ring, Sensei's Divining Top, Clues,
    Gitaxian Probe, and Faerie Mastermind's activated ability;
-   Cephalid Coliseum and Sea Gate Restoration;
-   Aether Spellbomb, Witching Well, Sewer-veillance Cam, Vexing Bauble, and
    the Top-plus-Key double activation.

The current end-turn card assignment remains delayed Bauble draw(s), then
Remora, Rhystic Study, and environmental Mastermind draws; the normal draw
waits until after any pending Remora cumulative-upkeep decision. Each source
must retain its own named trace line/detail.

Automatic draw details must not increase semantic trace cardinality because
deterministic shuffle entropy and the established Oracle same-stage tie-break
depend on trace length. The smoke therefore also checks trace-count and
shuffle-order neutrality. Searches/tutors to hand, casts from the top, scry,
mill, and Urza's exile/cast ability are not draws and remain separately traced.

## 7. Major combo-path integration suite

`--combo-smoke` must reach important wins through normal legal actions,
not merely call `check_win()` on completed boards.

Expected covered families/paths include:

-   Power Artifact + Grim;
-   Power Artifact + Basalt;
-   Basalt + Gadgeteer;
-   Top + Reality Chip + producer;
-   Top + FTT L3;
-   Top + FTT L2 + producer;
-   Top + Gadgeteer + producer;
-   Chrome Dome + Station;
-   Chrome Dome + Golem;
-   Knack + Cam + Golem;
-   Helix + Cam + VFC;
-   Spellseeker -\> Knack -\> bounce Spellseeker -\> replay -\>
    Transmute -\> Cam;
-   Knack + Golem + positive artifact;
-   Grinding Station artifact-ETB mana;
-   Battered Golem artifact-ETB mana;
-   Uthros + Station dedicated actions.

## 8. Problem-card smoke suite

When performance/action-generation logic changes, run the problem-card
smoke suite if present. Historically important cases include:

-   Chain of Vapor;
-   simple tutors;
-   artifact tutors;
-   Top actions;
-   Top + Key;
-   Chrome Dome;
-   Uthros Station;
-   Knack/Helix bounce;
-   producer native;
-   Chalice variants;
-   all `special_actions`;
-   all `legal_actions`.

Chain of Vapor previously dominated runtime and should remain a
dedicated regression target.

## 9. Deterministic natural-family smoke

Before a large Oracle simulation, run a small deterministic family
batch, for example:

``` powershell
py -3 urza_solver.py --family-smoke 10 --seed 20260821 --beam 300 --action-cap 60 --bottom-cap 4 --depth 100 --turns 7 --search-progress-seconds 10
```

Review:

-   win turn;
-   Urza cast turn;
-   keep size;
-   selected states;
-   total Oracle states;
-   win-family diversity;
-   natural Cam/Knack occurrence;
-   runtime outliers.

The historical 10-seed smoke produced six natural families and 2/10
Knack/Helix + Cam wins. Do not require that exact distribution from
unrelated seeds or after legitimate heuristic changes; use it as a
sanity reference.

## 10. Graph accounting

For performance regressions, compare:

-   nodes expanded;
-   edges generated;
-   exact-key merges;
-   cycle skips;
-   dominance prunes;
-   beam prunes;
-   layers;
-   maximum frontier;
-   maximum raw successors;
-   average branching factor.
-   Remora-upkeep nodes, edges, exact merges, dominance/beam prunes, layers,
    maximum frontier/successors, resolution-family results, and upkeep-only
    average branching factor.

A runtime increase with proportional graph growth is different from a
hot action generator that becomes slower per node.

## 11. Action-cap audit

The pre-cap audit command in the diagnostic builds is:

``` powershell
py -3 urza_solver.py --cap-audit 3 --seed 20260826 --beam 300 --action-cap 60 --bottom-cap 4 --depth 100 --turns 7 --search-progress-seconds 10
```

The observed audit that motivated further work evaluated 160,027 states:

-   1,864 states were truncated (1.165%);
-   maximum pre-cap legal actions: 348;
-   raw actions: 1,264,176;
-   discarded by ACTION_CAP: 89,172;
-   mean raw actions/state: 7.900;
-   mean discarded per truncated state: 47.84;
-   dropped branches were dominated by tutor actions.

Do not interpret the low percentage of truncated states as proof that
the cap is harmless. Cap-hit states can be strategically important.

## 12. Tutor-cap diversity audit

On the development build containing the tutor-cap diagnostic, run:

``` powershell
py -3 urza_solver.py --tutor-cap-audit 3 --seed 20260826 --beam 300 --action-cap 60 --bottom-cap 4 --depth 100 --turns 7 --search-progress-seconds 10
```

Review:

-   truncated states containing tutor branches;
-   raw vs kept tutor actions;
-   state-summed unique targets before vs after cap;
-   targets completely lost;
-   known engine targets completely lost;
-   distinct tutor-route overflow under the strict action cap;
-   retention by tutor source;
-   worst cap-hit states.

The important question is not merely how many tutor branches are
dropped. It is whether entire strategically distinct targets disappear.

## 13. Performance acceptance

Do not use a single wall-time threshold as the sole pass/fail criterion.
Seed complexity varies substantially.

Flag:

-   a dramatic runtime increase without corresponding graph growth;
-   unexpected action-family explosion;
-   repeated cap saturation;
-   large increases in branching factor;
-   a deterministic seed changing win family/turn after a supposedly
    diagnostic-only change;
-   loss of previously reachable combo families.

## 14. Before freezing Oracle

Before updating `oracle-stable`:

1.  all mandatory correctness suites pass;
2.  relevant problem-card smokes pass;
3.  deterministic family smoke is sane;
4.  graph metrics show no unexplained pathology;
5.  cap/tutor-cap behavior is understood;
6.  diagnostic-only changes have not changed deterministic outcomes;
7.  commit the exact tested code and record the command/config used.

## 15. Before large simulation

Start with a moderate batch before committing to a very large run.
Preserve:

-   seed range;
-   solver commit hash;
-   mode;
-   turn horizon;
-   beam;
-   action cap;
-   depth;
-   mulligan mode;
-   worker count;
-   machine/runtime information where useful.

Save aggregate results separately from source code.

## 16. Oracle mulligan and worker-configuration coverage

Oracle mulligan stages come from one shared production/profiler stage
definition. The default remains `--min-keep 4`, which evaluates the original
seven, the free multiplayer mulligan, and paid London keeps of six, five, and
four. `--min-keep 3` appends a fresh-seven keep-three stage that bottoms four
cards. `--bottom-cap 4` still admits at most four candidate bottom combinations
per stage; it does not change the number of cards that a London mulligan must
bottom.

`--mulligan-smoke` must verify:

-   fresh seven plus bottom four produces a legal keep-three;
-   keep-three has 35 raw positional bottom sets but admits exactly four when
    the bottom cap is four;
-   keep size and bottom-card reporting are correct;
-   adding keep-three leaves the existing 7A-through-keep-four shuffled hands
    unchanged;
-   a strictly earlier keep-three win may replace an earlier-stage winner, but
    an equal-turn keep-three may not;
-   production Oracle and the profiler use the shared stage definition.

`--worker-config-smoke` must use the real spawned-worker path and verify that
the requested action cap, bottom cap, minimum keep, turn horizon, beam, and
depth reach the child process instead of reverting to source defaults.

## 17. Reproducible sequential A/B/C validation

Reports record source/commit identity, dirty-tree state, turn horizon, action
cap, bottom cap, minimum keep and active stages, beam, depth, seed information,
worker count/execution mode, source/deck hashes, and the inherited
`PYTHONHASHSEED`. The solver must not try to set
`PYTHONHASHSEED` after Python starts. If it is unset, reports and console output
must warn that exact reproduction is not guaranteed.

Before a new 30-seed benchmark, run this pinned five-seed comparison
sequentially in PowerShell. Each command evaluates the identical seeds
20260821--20260825 with beam 300, action cap 60, bottom cap 4, and depth 100:

``` powershell
$env:PYTHONHASHSEED='0'; py -3 urza_solver.py --smoke-seeds 5 --smoke-seed-step 1 --seed 20260821 --turns 7 --min-keep 4 --beam 300 --action-cap 60 --bottom-cap 4 --depth 100 --search-progress-seconds 10
$env:PYTHONHASHSEED='0'; py -3 urza_solver.py --smoke-seeds 5 --smoke-seed-step 1 --seed 20260821 --turns 6 --min-keep 4 --beam 300 --action-cap 60 --bottom-cap 4 --depth 100 --search-progress-seconds 10
$env:PYTHONHASHSEED='0'; py -3 urza_solver.py --smoke-seeds 5 --smoke-seed-step 1 --seed 20260821 --turns 6 --min-keep 3 --beam 300 --action-cap 60 --bottom-cap 4 --depth 100 --search-progress-seconds 10
```

The three cases are respectively A: T7/keep-four floor, B: T6/keep-four
floor, and C: T6/keep-three floor. `--smoke-seeds` is intentionally sequential.
Preserve or rename `smoke_seed_report.json` after each case because the next
case writes the same report path.
