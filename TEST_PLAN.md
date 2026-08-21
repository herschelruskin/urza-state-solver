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
```

Expected terminal markers:

``` text
METADATA SMOKE: ALL PASS
TUTOR SMOKE: ALL PASS
CAM SMOKE: ALL PASS
COMMANDER SMOKE: ALL PASS
COMBO SMOKE: ALL PASS
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

## 5. Major combo-path integration suite

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

## 6. Problem-card smoke suite

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

## 7. Deterministic natural-family smoke

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

## 8. Graph accounting

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

A runtime increase with proportional graph growth is different from a
hot action generator that becomes slower per node.

## 9. Action-cap audit

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

## 10. Tutor-cap diversity audit

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

## 11. Performance acceptance

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

## 12. Before freezing Oracle

Before updating `oracle-stable`:

1.  all mandatory correctness suites pass;
2.  relevant problem-card smokes pass;
3.  deterministic family smoke is sane;
4.  graph metrics show no unexplained pathology;
5.  cap/tutor-cap behavior is understood;
6.  diagnostic-only changes have not changed deterministic outcomes;
7.  commit the exact tested code and record the command/config used.

## 13. Before large simulation

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
