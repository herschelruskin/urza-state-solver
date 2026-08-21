# AGENTS.md

## Project purpose

This repository contains a deterministic state-space / beam-search
simulator for the Urza, Lord High Artificer deck. The primary validated
implementation is **Oracle Mode**: the search engine may use full
deck-order knowledge to identify the strongest reachable line. A later
fork will implement a knowledge-constrained / human-plausible policy
mode.

## Non-negotiable development rules

1.  **Do not silently change Magic rules, card metadata, combo
    definitions, mulligan semantics, or win conditions.**
2.  Treat the current validated Oracle behavior as a regression target.
    Diagnostics may be added without changing search semantics.
3.  Before changing a card rule, identify the exact existing
    implementation and add or update a focused smoke test.
4.  After any rules-engine or search-action change, run the mandatory
    smoke suites in `TEST_PLAN.md`.
5.  A change is not complete merely because the file imports or the
    target smoke passes. Check the other regression suites too.
6.  Prefer instrumenting a suspected search problem before changing
    heuristics or caps.
7.  Never replace a legal multi-step line with an unjustified terminal
    shortcut. Complete wins must be represented as complete wins, not
    partial engines.
8.  Preserve state distinctions that affect future legality:
    tapped/untapped, summoning sickness, commander zone/tax,
    current-turn spell casting, current-turn Knack/Helix effects,
    library/top information, mana/color, sacrifice requirements, and
    relevant temporary effects.
9.  When pruning, distinguish exact-state merging, cycle prevention,
    dominance pruning, beam pruning, and action-cap truncation. Do not
    conflate them.
10. Keep reproducible deterministic seeds for performance/regression
    work.
11. Do not optimize away strategically distinct tutor targets merely
    because multiple tutor-payment/sacrifice routes reach
    similar-looking states.
12. Keep Oracle and future policy-mode logic separable. Do not make
    Oracle less omniscient merely to approximate human play.

## Implementation workflow

-   Work on `development` for active changes.
-   Keep `oracle-stable` as the validated checkpoint.
-   Use a separate `policy` branch when the knowledge-constrained solver
    is started.
-   Commit small, descriptive changes.
-   For performance changes, report both runtime and search-size
    effects.
-   For heuristic changes, compare deterministic seeds before and after.
-   Keep generated reports out of source control unless deliberately
    preserving a benchmark fixture.

## Search priorities

The search should prefer, in broad strategic order:

1.  immediate wins;
2.  guaranteed/strong next-turn wins;
3.  progress toward complete combo engines;
4.  useful card advantage / setup;
5.  lower-value development.

This ordering is a heuristic, not permission to violate card rules or
discard strategically distinct legal branches without auditing them.

## Current search architecture

-   Beam / best-first state search.
-   Search games through the configured turn horizon, commonly T7.
-   Track the exact win family.
-   Track Urza cast turn.
-   Track mulligan/kept-hand information.
-   Track interaction seen before the win state where implemented.
-   Oracle mulligan mode and sequential London mulligan mode must remain
    conceptually distinct.
-   Current diagnostics include graph accounting and cap audits.

## Performance discipline

Known broad states can create very large tutor branch counts. Do not
respond by simply increasing caps without measuring the cause.

Useful graph metrics include:

-   nodes expanded;
-   edges generated;
-   exact-key merges;
-   cycle skips;
-   dominance prunes;
-   beam prunes;
-   search layers;
-   maximum frontier;
-   maximum raw successors;
-   average branching factor.

The current action cap has been observed to truncate only a minority of
states, but tutor-heavy states can have hundreds of pre-cap legal
actions. Tutor-target diversity must therefore be audited before
changing the cap policy.

## Coding-agent behavior

When asked to implement a change:

1.  inspect the relevant functions first;
2.  state which semantics are being changed;
3.  make the smallest coherent patch;
4.  add/update smoke coverage;
5.  run relevant focused smoke tests;
6.  run the mandatory regression suite;
7.  summarize changed files, tests, and any unresolved uncertainty.

Do not claim a rule is implemented merely because a win detector
recognizes a finished board. Integration tests should reach important
combos through normal legal actions.
