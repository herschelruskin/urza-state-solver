URZA TEMPO STORM STATE-SEARCH SIMULATOR — v0.3
================================================

PURPOSE
-------
Deck-specific Urza, Lord High Artificer goldfish/state-search engine.
This is intentionally NOT a generic Magic rules engine.

v0.3 is a rules-correctness rebuild of v0.2. Use the first local runs to audit
traces before treating large Monte Carlo output as final deck probabilities.

RECOMMENDED FIRST RUN (WINDOWS / POWERSHELL)
--------------------------------------------
Extract this folder, open PowerShell inside it, then:

    py -3 urza_solver.py -n 100 --beam 300 --action-cap 60 --bottom-cap 4 --workers 6 --out audit100

For a beam sensitivity check on identical seeds:

    py -3 urza_solver.py -n 100 --seed 20260821 --beam 150 --action-cap 50 --bottom-cap 4 --workers 6 --out b150
    py -3 urza_solver.py -n 100 --seed 20260821 --beam 300 --action-cap 60 --bottom-cap 4 --workers 6 --out b300
    py -3 urza_solver.py -n 100 --seed 20260821 --beam 600 --action-cap 80 --bottom-cap 6 --workers 6 --out b600

If the win curve still rises materially with beam/action width, the search has
not converged.

OUTPUTS
-------
<out>/games.csv
<out>/summary.json
<out>/traces.txt

The simulator records deterministic seeds so suspicious games can be reproduced.

MULLIGAN MODEL
--------------
Primary output remains the user's requested ORACLE ceiling. By default,
`--min-keep 4` evaluates:
  original 7 -> free second 7 -> 6 -> 5 -> 4
and selects the realized candidate that reaches the earliest win. An equal-turn
result stays with the earlier mulligan stage.

`--min-keep 3` appends a legal Commander London keep-three stage: take a fresh
seven and put four cards on the bottom. `--bottom-cap 4` means that at most four
candidate bottom combinations are searched at each paid-mulligan stage; it does
not reduce the number of cards that must be bottomed.

This is intentionally an upper-bound / perfect-hindsight mulligan statistic.

IMPORTANT v0.3 RULE / STATE FIXES
---------------------------------
* Gitaxian Probe draws against an assumed legal multiplayer target.
* Witching Well ETB scry 2 and sacrifice-to-draw-2.
* Sewer-veillance Cam ETB/LTB creature untap and sacrifice-to-draw-2.
* Giant's Boulder ETB scry 2 and mana filtering.
* Vexing Bauble draw activation and own zero-mana-spell countering.
* Mishra's Bauble / Urza's Bauble delayed next-upkeep draw.
* Sensei's Divining Top now correctly goes on TOP after its draw ability.
* Explicit Top + Voltaic/Manifold Key double-activation line.
* Artificer's Assistant scry occurs only on qualifying historic casts.
* Uthros Station activation from creature power; 3+ artifact casts draw before resolution.
* Valley Floodcaller corrected to 2U; Bird/Otter untaps and temporary pumps tracked.
* Knack/Helix tracks the actual target creature and can proactively bounce our permanents.
* Cam terminal loop requires the actual Knack/Helix target to be usable.
* Golem/VFC replay loops use replay economics rather than only a hard-coded 0-drop list.
* Chain of Vapor can proactively bounce our permanents and sacrifice a land for a copy.
* Reality Chip requires a creature to reconfigure onto; target leaving turns top access off.
* FTT can level for development; L3 generic reduction works on outside-hand casts.
* MDFCs branch between front spell and back land when played from hand/top.
* Chrome Mox may imprint blue spell-front MDFCs; Mox Diamond may not discard them as lands.
* Codex Shredder self-mill top reset and graveyard recursion.
* Grinding Station self-mill top reset.
* Fetchlands fetch an Island and shuffle; they no longer incorrectly tap for U.
* Urza spin actually reshuffles before exiling/casting the hit.
* City of Traitors can tap for CC in response to its own sacrifice trigger after another land is played.
* Crystal Vein and Saprazzan Skerry use one-shot/depletion state.
* Oboro bounce/replay can turn an unused land drop plus generic mana into another blue activation.
* Minamo can untap The One Ring or Urza carrying Knack/Helix.
* Gemstone Caverns seating state is fixed once per simulated game across mulligan candidates.
* Jeweled Amulet stores typed mana and releases it later.
* Moonsnare Prototype can tap itself plus another artifact/creature for C.
* Native Grim/Basalt untaps are available with Gadget/Power Artifact reductions.
* Power Artifact tracks the actual enchanted artifact.
* PA+Monolith and Basalt+Gadget check legal bootstrap mana if the rock is already tapped.
* Chrome Dome creates actual useful artifact copies while building toward a self-sustaining loop.
* An Offer You Can't Refuse can counter our own noncreature spell to make two Treasures.
* Scour for Scrap costs 3U and can use one or both modes.
* Welding Jar can sacrifice itself for free to establish a graveyard target before Scour.
* Repurposing Bay pays {2}, taps, sacrifices another artifact, and uses exact
  sacrificed-MV+1 tutoring directly to the battlefield before shuffling.
* Urza's Saga tracks I / II / III, Construct activation, and exact printed {0}/{1} chapter-III targets.
* Tezzeret, Cruel Captain costs 3 generic, gains loyalty from artifact ETBs, and branches between
  0: untap artifact/creature and -3: MV<=1 artifact tutor, once per turn.
* Spellseeker's tutor tree is much broader than only the combo chain.
* Dizzy/Muddle use true mana value, including Gitaxian Probe being MV1.
* Seat of the Synod is handled as both artifact and land where relevant.

SCOUR FOR SCRAP TARGETING NOTE
------------------------------
The graveyard target must already be legal when Scour is cast.
You cannot cast Scour, then sacrifice Welding Jar in response, and retroactively
choose the Jar as the graveyard target.

You CAN sacrifice Jar before casting Scour, then cast Scour targeting Jar while
also using the library-tutor mode.

MULTIPLAYER ASSUMPTIONS REQUESTED BY USER
-----------------------------------------
* Battered Golem starts each of our turns untapped, representing likely opponent artifact ETBs.
* Mystic Remora: +2 opponent-fed cards per cycle, separately from its real
  cumulative-upkeep pay-or-sacrifice decision.
* Rhystic Study: +2 cards per future cycle.
* Faerie Mastermind: +1 card per future cycle.
* Mana Drain: if UU is available, bank +2 colorless for next turn.
* Opponent interaction otherwise ignored.

SEARCH DESIGN
-------------
Strategic priorities order branches rather than defining combo legality:
  win now
  > deterministic next-turn win
  > first card-advantage engine
  > Grinding Station
  > Battered Golem
  > second card-advantage engine
  > generic development

MYSTIC REMORA CUMULATIVE UPKEEP
-------------------------------
At each upkeep after Remora entered, its cumulative-upkeep trigger is put on the
stack after untap. Responses occur before resolution and therefore see the old
age-counter total. On resolution Remora receives the next counter and branches
between paying that much generic mana or sacrificing it. Saga lore counters and
Mana Drain's modeled mana wait until precombat main.
Leaving and recasting Remora resets its age. The +2 opponent-fed-card assumption
above remains an independent environmental model. Bauble/upkeep draws may occur
before the choice, the normal draw occurs afterward, and modeled fetch, mana,
Dramatic Reversal, Key, Chain of Vapor, Otawara channel, Aether Spellbomb, and
legal Knack/Helix responses remain available while the trigger is pending.
Sorcery-speed actions remain gated. Bouncing the old Remora clears that object's
obligation, and a recast starts at age zero. The upkeep branch closes before
normal per-turn search depth.

Focused regression:
    py -3 urza_solver.py --remora-smoke --action-cap 60 --bottom-cap 4
    py -3 urza_solver.py --bounce-smoke --action-cap 60 --bottom-cap 4

BOUNCE / REPURPOSING BAY FREEZE AUDIT
-------------------------------------
The implemented own-permanent bounce modes are:
* Chain of Vapor: pay U; return a nonland permanent; each modeled copy requires
  sacrificing a land.
* Otawara: channel for 3U, reduced by one generic per legendary creature; return
  an artifact, creature, enchantment, or planeswalker. Channel is not a spell.
* Aether Spellbomb: pay U and sacrifice it to return a creature only; its pay-1
  sacrifice-to-draw mode is separate.
* Banishing Knack / Retraction Helix: pay U to grant a selected creature the
  temporary tap ability; summoning sickness and tapped status are enforced, and
  the ability can return itself or another nonland permanent.

Bounced cards return to hand; bounced tokens cease to exist. The focused suite
also locks MDFC face handling and Remora-upkeep response timing.

Repurposing Bay's focused fixture proves Sapphire Medallion MV2 -> Battered
Golem MV3, including the {2} payment, Bay tap, Sapphire sacrifice, direct
battlefield entry, and shuffle-before-ETB ordering. The same suite confirms
that Grinding Station and Battered Golem see their own artifact entry and that
every controlled copy receives its trigger.

Focused regression:
    py -3 urza_solver.py --bay-smoke --action-cap 60 --bottom-cap 4

NAMED DRAW TRACING
------------------
Every true library-to-hand draw records the actual card names and source in the
winning trace. This covers normal draws; Remora/Rhystic/Mastermind environmental
draws; individual delayed Mishra's/Urza's Bauble draws; Uthros; Ring; Top; Clue;
Probe; activated Mastermind; Coliseum; Sea Gate Restoration; and the other
implemented draw/sacrifice artifacts.

The established end-turn card assignment is explicit: pending Bauble draw(s)
first, then Remora, Rhystic, and environmental Mastermind, with the normal draw
after any Remora cumulative-upkeep decision. Searches, top-casts, scry, mill,
and Urza's exile/cast ability remain separately described because they are not
draws.

Automatic draw names are added within the existing turn/upkeep trace entry, not
as new semantic action entries. This preserves the historical trace length used
by deterministic shuffles and Oracle's same-stage tie-break.

Focused regression:
    py -3 urza_solver.py --draw-trace-smoke

KNOWN REMAINING AUDIT ITEMS
---------------------------
1. Chrome Dome pre-terminal copy targets focus on strategically useful artifacts.
2. Very long multi-land Chain of Vapor copy chains are still underexplored.
3. Simultaneous Gadget/Uthros/Assistant/VFC trigger ordering is strategically approximated.
4. Life totals are ignored.
5. Cephalid Coliseum threshold looting and Ipnu Rivulet Desert mill are not yet proactive actions.
6. Mana Vault upkeep-pay-4 untap is not a separate upkeep-phase decision.
7. Legal-information London mulligans are not yet implemented; oracle remains primary.
8. This is deck-specific, not a complete comprehensive-rules engine.

TRACE AUDIT WORKFLOW
--------------------
Run 100 first, then send ChatGPT:
  summary.json
  traces.txt

Also send several seeds from games.csv for:
  fastest T3 wins
  T4 wins
  apparent T6/T7 misses

v0.3.1 UTHROS PATCH
-------------------
* Uthros Station can be activated repeatedly in the same main phase with each
  different eligible untapped creature.
* Creature power is recalculated for each activation.
* Important baseline: with only Urza + Urza's Construct + Uthros in play,
  Construct is 2/2 (Construct + Uthros are the two artifacts). Station Construct
  for 2, then Station Urza for 1, reaching the 3-counter artifact-draw threshold.


v0.3.2 PRE-URZA ENGINE PATCH
----------------------------
* FTT level 3 + Sensei's Divining Top is recognized as a pre-Urza deterministic
  library-access engine. It can play through the library, deploy mana artifacts,
  and then cast Urza once UU is available.
* Basalt Monolith + Forensic Gadgeteer is recognized as infinite colorless before
  Urza resolves.
* Pre-Urza infinite colorless is NOT itself scored as a win. The state must still
  have two immediately usable blue sources to cast Urza; infinite colorless pays
  the generic portion only.
* The same UU gate applies to pre-Urza Power Artifact + Monolith states.


v0.3.3 CHROME / DESERT / CHAIN / MULTI-TRIGGER PATCH
-----------------------------------------------------
* Chrome Dome has a real opponent-before-us end-step window. A token created
  after that end step begins survives our whole upcoming turn and is sacrificed
  at the beginning of our end step. It cannot spend floating mana from our prior
  turn; the model checks only permanents that remained untapped.
* Cephalid Coliseum threshold is implemented: U,T,sac -> draw 3/discard 3 when
  graveyard >=7, preserving several strategic discard packages.
* Ipnu Rivulet uses its real Desert ability: 1U,T,sac a Desert -> self-mill four;
  it may sacrifice itself.
* Chain of Vapor recursively supports repeated land sacrifices and copies for as
  many lands/nonland targets as remain, with a legal stop after every bounce.
* Multi-trigger audit:
    - every Artificer's Assistant trigger is counted;
    - Assistant scries resolve before the Uthros draw by strategic default;
    - every Gadgeteer creates its own Clue;
    - every Station/Golem copy independently contributes its ETB untap/mana.
  Full arbitrary priority actions between individual triggers remain outside the
  deck-specific abstraction, but the chosen ordering is legal and strategically
  favorable for card access.


v0.3.4 EXPLICIT SACRIFICE / DRAW COST AUDIT
--------------------------------------------
Unit-tested activation semantics:
* Witching Well — 3U, sacrifice: draw 2; does NOT require tapping.
* Sewer-veillance Cam — 3U, sacrifice: draw 2; does NOT require tapping.
  Cam LTB explicitly branches over tapped creature targets to untap.
* Mishra's Bauble — T, sacrifice: delayed draw next upkeep; no mana.
* Urza's Bauble — T, sacrifice: delayed draw next upkeep; no mana.
* Vexing Bauble — 1, T, sacrifice: draw 1.
* Aether Spellbomb — U, sacrifice: draw 1; does NOT require tapping.
* Codex Shredder — T self-mill; 5,T,sac recursion (with Gadget/PA reductions where applicable).
* Welding Jar — sacrifice for free.

Consequences with Urza:
* Well/Cam/Aether Spellbomb/Jar can be tapped through Urza first and still use
  their sacrifice ability later if its mana cost can be paid.
* Mishra's Bauble, Urza's Bauble, Vexing Bauble, and Codex require themselves
  untapped for their native T ability, so tapping them through Urza consumes that
  use unless an untap effect resets them first.


v0.3.5 FTT SPELL-GATE / GRAFDIGGER'S CAGE PATCH
------------------------------------------------
* FTT top play requires a spell to have been cast that turn.
* Grafdigger's Cage blocks spells cast from libraries through FTT/Reality Chip.
* Cage does not stop lands being played from the library.
* Urza spin still works because the card is exiled before being cast.
* Search can remove Cage using bounce/sacrifice lines, including an explicit
  Grinding Station branch that sacrifices Cage and self-mills 3.


v0.3.6 OBSERVABILITY / FAERIE MASTERMIND PATCH
-----------------------------------------------
* Tracks the first turn Urza is actually cast.
* Tracks distinct interaction pieces seen in hand or on our battlefield before
  the terminal win state, including bounce, counterspells, Needle, Flute, Cage,
  Vexing Bauble, Defense Grid, Aether Spellbomb, and Otawara.
* games.csv now records original 7, London bottoms, actual kept hand, final hand,
  Urza-cast turn, interaction count/list, and deterministic seed.
* traces.txt prints the actual kept hand followed by the selected action sequence,
  so kept-hand -> game-plan paths can be audited directly.
* summary.json adds Urza-cast-turn and interaction distributions/frequencies.
* Faerie Mastermind's 3U activated ability is a real repeatable draw-1 action.
  This is separate from the user's environmental +1-card/turn assumption.


v0.3.7 CHALICE / PRIZED STATUE / SAC-LAND AUDIT
------------------------------------------------
* Everflowing Chalice has real multikicker branching, charge counters, and native
  tap-for-C-per-counter mana.
* Zero-counter Chalice remains valid Urza mana.
* Direct-to-battlefield Chalice has zero counters.
* Prized Statue ETB makes Treasure; its second Treasure is only when it goes from
  battlefield to graveyard, not generic LTB.
* Treasure tokens are explicitly recognized as Urza-tappable artifacts and also
  require T+sacrifice for their own mana, preventing illegal double use.
* City of Traitors, Crystal Vein, and Saprazzan Skerry sacrifice/depletion life cycles
  are explicitly unit-tested.


v0.3.8 TURN-DEPTH PATCH
------------------------
The old `max_actions_per_turn=22` default was too shallow for this deck.

* Default per-turn state-transition depth is now 60.
* CLI exposes it as:

      --depth 60

* `--action-cap` and `--depth` are different:
    - action-cap = maximum candidate NEXT actions retained from one state
    - depth = maximum sequential actions explored during one turn
    - beam = maximum global states retained at each depth layer
* Tapping lands/artifacts, untapping things, activating Top/Keys, tutoring,
  casting/replaying artifacts, drawing, bouncing, and other state transitions
  all consume depth.
* games.csv now records `max_depth_reached`.
* summary.json records the depth distribution and how many games actually hit
  the configured ceiling.
* traces.txt prints max action depth for each displayed game.

Recommended depth sensitivity test on identical seeds:

    py -3 urza_solver.py -n 100 --seed 20260821 --beam 300 --action-cap 60 --depth 40 --workers 6 --out d40
    py -3 urza_solver.py -n 100 --seed 20260821 --beam 300 --action-cap 60 --depth 60 --workers 6 --out d60
    py -3 urza_solver.py -n 100 --seed 20260821 --beam 300 --action-cap 60 --depth 100 --workers 6 --out d100

If T3/T4 cumulative win rates or `depth_ceiling_hits` remain materially higher
at 100 than 60, use the deeper setting for the final simulation.


v0.3.9 LIVE PROGRESS / HANG QC / ERROR REPORTING
-------------------------------------------------
Long local runs now print live console diagnostics.

New CLI options:
    --progress-every 5
        Print a full progress line every N completed games.

    --heartbeat-seconds 30
        Ensure a progress/heartbeat line appears at least this often when games
        are completing. Note: if ALL workers are individually stuck inside a
        single extremely expensive game, Python cannot receive a completed result
        to print a new per-game progress line; use Task Manager CPU activity as
        an additional hang check.

    --error-log errors.log
        Worker exceptions are caught, tagged with the deterministic seed, and
        appended to this file inside the output directory instead of silently
        killing the entire batch.

Each progress line reports:
* completed games / requested runs
* percentage complete
* wall-clock elapsed time
* games per second
* estimated time remaining
* cumulative <=T3 / <=T4 / <=T5 wins so far
* number of games hitting the configured turn-depth ceiling
* worker error count
* average states searched
* average per-game worker runtime

Startup prints:
* runs
* worker count
* beam width
* action cap
* turn depth
* base seed
* output directory

summary.json additionally records:
* completed runs
* error count
* action cap
* total wall runtime

Recommended first audit command:

    py -3 urza_solver.py -n 100 --beam 300 --action-cap 60 --depth 60 --workers 6 ^
        --progress-every 5 --heartbeat-seconds 30 --out audit100

If PowerShell is used on one line, omit the ^ line continuation.


v0.3.10 TRUE HEARTBEAT / WORKER VISIBILITY
-------------------------------------------
v0.3.9's "heartbeat" depended on a game finishing first. This was not useful
when all workers were simultaneously searching expensive opening seeds.

v0.3.10 adds a real independent heartbeat thread.

Default:
    --heartbeat-seconds 15

It prints even when ZERO games have completed:

    [heartbeat] SEARCHING | 0/100 complete (0.0%) | elapsed 45s |
    last completion 45s ago | rate 0.000 games/s |
    ETA unknown (no game finished yet) | workers requested=6

Optional:
    --verbose-workers

Each worker then prints:

    [worker 12345] START seed=20260821
    [worker 12346] START seed=20260822
    ...
    [worker 12345] DONE seed=20260821 win=4 time=37.2s states=184,293

This is especially useful for identifying a single pathological seed.

Recommended audit command:

    py -3 urza_solver.py -n 100 --beam 300 --action-cap 60 --bottom-cap 4 ^
      --depth 60 --workers 6 --heartbeat-seconds 15 --verbose-workers --out audit100

PowerShell one-line version:

    py -3 urza_solver.py -n 100 --beam 300 --action-cap 60 --bottom-cap 4 --depth 60 --workers 6 --heartbeat-seconds 15 --verbose-workers --out audit100

What "silent" means now:
* heartbeat continuing + no DONE lines = workers are still inside current games.
* some workers repeatedly DONE while one seed remains START-only = likely a pathological seed.
* no heartbeat at all for >2 heartbeat intervals = parent process itself may be stuck/crashed.


v0.4.0 CLEAN CANCELLATION + LOW-RISK SEARCH OPTIMIZATION
---------------------------------------------------------
Ctrl+C
------
The multiprocessing pool is now explicitly owned by the parent process.

On Ctrl+C:
1. parent catches KeyboardInterrupt;
2. all worker processes are terminated immediately;
3. pool is joined so Windows does not leave orphan Python workers;
4. heartbeat thread stops;
5. completed games are written to partial_checkpoint.json;
6. program exits instead of allowing worker/pool restart behavior.

If Windows still has orphan Python processes from an OLDER build, from
PowerShell you can inspect them with:

    Get-Process python,python3 -ErrorAction SilentlyContinue

and force-stop them with:

    Get-Process python,python3 -ErrorAction SilentlyContinue | Stop-Process -Force

Be careful: this kills every Python process owned by your user session.

Low-risk speed/memory work
--------------------------
This build deliberately avoids changing Magic decisions while beginning the
state-representation optimization:

* immutable hot-path membership tables are precomputed;
* mana-value/base-cost lookup is cached;
* repeated battlefield-name set construction is reduced;
* conservative dominance pruning removes resource-inferior duplicate states
  only when board/hand/library-prefix/engine configuration is otherwise equal;
* worker cancellation no longer leaves expensive orphan searches running.

This is phase 1. The larger possible optimization is replacing Python string /
Perm-heavy states with integer card IDs and packed state arrays. That should be
profiled against v0.4.0 before undertaking the larger rewrite.

Recommended profiling benchmark:

    py -3 urza_solver.py -n 3 --beam 300 --action-cap 60 --bottom-cap 4 --depth 60 --workers 1 --heartbeat-seconds 10 --verbose-workers --out profile3

Using one worker first makes it easier to distinguish per-game search cost from
RAM contention across multiple processes.


v0.4.1 HOTFIX
--------------
Fixed import order for functools.lru_cache. v0.4.0 could fail at startup with:

    NameError: name 'lru_cache' is not defined

v0.4.1 passes:
* Python syntax compilation
* clean module import in a fresh Python process
* CLI --help startup test


v0.4.2 PROFILING BUILD
-----------------------
This build is for diagnosing the 10+ minute per-oracle-game search explosion.

Run exactly ONE deterministic opening 7, bypassing London/oracle branching:

    py -3 urza_solver.py --profile-one --seed 20260821 --beam 300 --action-cap 60 --depth 60 --profile-turns 3

It prints every depth layer:
* states entering layer
* successors generated
* average/max legal actions per state
* unique states after exact-key dedup
* states after conservative dominance pruning
* states retained by beam
* seconds spent in that depth
* cumulative states searched
* process RSS memory if psutil is available
* action mix (mana/tap, untap, cast, tutor, draw/top, bounce, other)

This is intentionally one opening candidate rather than an oracle game. It lets
us see whether the explosion is:
1. repeated equivalent mana/tap permutations,
2. tutor branching,
3. Top/Chip/FTT library manipulation,
4. Chain/bounce branching,
5. or another mechanic.

If `rss=n/a`, optional install for memory reporting only:

    py -3 -m pip install psutil

The profiler works without psutil.

Expected red flag:
    frontier stays at beam=300,
    generated successors remain in the tens of thousands every depth,
    while unique states remain high despite most actions being mana/tap.

That would strongly support replacing individual mana taps with normalized
resource macro-actions rather than merely increasing hardware.


v0.4.3 ORACLE-CANDIDATE PROFILER
---------------------------------
The first single-opening profile for seed 20260821 was tiny (94 searched states
through T3). That proves the original seven was not responsible for the
10+ minute full oracle runtime.

Profile depth now defaults through T7.

Quick one-opening profile through T7:

    py -3 urza_solver.py --profile-one --seed 20260821 --beam 300 --action-cap 60 --depth 60 --profile-turns 7

More important: profile EVERY independent oracle candidate for one seed:

    py -3 urza_solver.py --profile-oracle --seed 20260821 --beam 300 --action-cap 60 --bottom-cap 4 --depth 60 --profile-turns 7

The oracle profiler prints:
* 7A / free 7B / keep-6 / keep-5 / keep-4 opening sevens
* exact London bottom package for every search
* actual kept hand
* START before entering search_hand
* DONE with wall time, win turn/family, states searched and max depth
* a final ranking from slowest candidate to fastest

Therefore if output stops after:

    >>> START 5.3/4 ...

we have identified the exact hand that causes the state explosion.

This profiler is about runtime/search diagnosis. It is not itself a probability
estimate. T3/T4 cumulative win rates still come from the multi-game simulation
once search performance is under control.


v0.4.4 NESTED ORACLE PROFILER
------------------------------
v0.4.3 identified the candidate but still called silent search_hand(), so a slow
7A/7B/6/5/4 candidate could again look frozen.

v0.4.4 profiles INSIDE each oracle candidate. Every T1-T7 depth layer prints:

    [7A.1/1] T4 D17 in=300 gen=14,822 avg=49.4 max=60 |
              unique=9,140 dom=8,902 keep=300 |
              dt=3.42s total=4,381 rss=...

and an action mix below it.

Use:

    py -3 urza_solver.py --profile-oracle --seed 20260821 --beam 300 --action-cap 60 --bottom-cap 4 --depth 60 --profile-turns 7

Now there should never be a long silent period inside a candidate unless one
single legal_actions(state) call itself is pathological. If that happens, the
last printed T/Depth tells us exactly where to instrument next.


v0.4.5 CHAIN EXPLOSION FIX + PER-STATE PROFILING
-------------------------------------------------
The v0.4.4 trace reached T7 D07 in milliseconds, then produced no T7 D08 line.
That means the layer itself had not finished: one legal_actions(state) call was
likely exploding internally.

Code audit identified Chain of Vapor as a structural hazard. The previous
implementation recursively generated every:
    bounce order × sacrificed-land order × next bounce order ...
before performing deduplication or ACTION_CAP truncation.

On a developed board this is factorial even though most permutations produce
the same strategic state.

v0.4.5 changes Chain to:
* expand one Chain-copy depth at a time;
* exact-key deduplicate continuation states after EVERY depth;
* preserve different sacrificed lands / Cam outcomes / attachment outcomes;
* keep all legal stop points;
* retain a generous emergency continuation cap only as a RAM fail-safe.

Profile mode also prints individual frontier-state progress. If another
legal_actions call takes >=1 second it prints [SLOW STATE].

First run the synthetic Chain test:

    py -3 urza_solver.py --chain-stress-test

Then rerun the oracle profile:

    py -3 urza_solver.py --profile-oracle --seed 20260821 --beam 300 --action-cap 60 --bottom-cap 4 --depth 60 --profile-turns 7

If T7 D08 now completes immediately, Chain was the primary pathological pitfall.
If it still stalls, the last "entering state X/Y" line identifies the exact
state where we should time the individual action families next.


v0.4.6 CANONICAL CHAIN + PROBLEM-CARD SMOKE SUITE
--------------------------------------------------
Chain
-----
The T6 profile showed Chain-live states taking ~1.1-1.2 s each even after
levelwise dedup. v0.4.6 eliminates bounce-order permutations entirely.

Chain now chooses:
    bounced permanent SET
    + sacrificed land SET

and constructs the resulting outcome directly.

Only known order-sensitive cases branch:
* Sewer-veillance Cam leaving before vs after other targets;
* Power Artifact vs its enchanted target leaving first.

Focused test:
    py -3 urza_solver.py --chain-stress-test

Broader performance smoke:
    py -3 urza_solver.py --problem-smoke

The smoke suite separately times:
* Chain
* simple tutors
* artifact tutors
* Top
* Top+Key
* Chrome Dome
* Uthros Station
* Knack/Helix bounce
* producer native actions
* Everflowing Chalice
* all special actions
* all legal actions

Any action family taking >=1 second is flagged SLOW.

After smoke passes, rerun:
    py -3 urza_solver.py --profile-oracle --seed 20260821 --beam 300 --action-cap 60 --bottom-cap 4 --depth 60 --profile-turns 7

The key regression target is 4.1/4:
    previously ~29 s
    same expected result: T6 Pre-Urza PA + Grim -> cast Urza


v0.4.7 CHAIN PLAN-SHORTLIST OPTIMIZATION
-----------------------------------------
The v0.4.6 problem smoke conclusively isolated Chain:
    Chain of Vapor      ~4.7 s
    all special_actions ~5.1 s
    all legal_actions   ~6.5 s
while every other individual action family was ~0.00-0.01 s.

Therefore no other card family is currently the performance bottleneck.

v0.4.7 avoids constructing full States for every canonical Chain subset:
1. enumerate bounce/land plans as cheap tuples;
2. cheaply rank them;
3. retain a global shortlist;
4. forcibly retain best plans at every possible chain length;
5. materialize only shortlisted plans;
6. preserve explicit Cam and Power Artifact order-sensitive variants;
7. exact-key dedup and normal ACTION_CAP.

Run:
    py -3 urza_solver.py --chain-stress-test
    py -3 urza_solver.py --problem-smoke

Desired:
    Chain under ~1 second on the oversized synthetic board.
    special_actions/legal_actions should fall with it.

Then rerun the oracle profile and confirm:
    * 4.1/4 still wins T6 through PA + Grim;
    * runtime falls substantially;
    * no new SLOW STATE family appears.


v0.4.8 EXACT PER-TURN CYCLE / TRANSPOSITION PRUNING
----------------------------------------------------
Depth-100 sensitivity found:
* 7A reached a new T7 win at depth 67.
* 5.4 still hit the full depth=100 ceiling despite already finding the same T6
  Basalt + Gadgeteer route.

This indicates repeated action cycles, not a need for arbitrarily deeper search.

The solver previously deduplicated states only among successors in ONE depth
layer. If a sequence such as:
    tap -> untap -> ...
or
    bounce/replay/top manipulation -> ...
returned to an exact state encountered several depths earlier in the SAME turn,
that state could be expanded again.

v0.4.8 keeps an exact `expanded_this_turn` transposition set.

A state is skipped only when its full strategic key has already been expanded
this turn. The key includes the resource/board/library information needed to
determine future legal actions. The trace itself is intentionally irrelevant.

This is exact cycle pruning, not heuristic beam pruning:
* same strategic state -> same possible future;
* therefore re-expansion cannot discover a new line.

The profiler now reports `cycle_skip=N` per depth.

Regression goals:
1. 4.1 remains T6 PA+Grim.
2. 5.4 remains T6 Basalt+Gadget.
3. 5.4 should stop naturally instead of hitting depth 100.
4. 7A may still find T7 if that route genuinely progresses through >60 UNIQUE
   states; if it disappears, inspect whether an omitted state field belongs in key.
5. T3/T4 results must not worsen from exact duplicate-state pruning.


v0.4.9 WINDOWS CTRL+C / WORKER RESPAWN FIX
-------------------------------------------
Root cause of the apparent worker restart:

On Windows, console Ctrl+C can reach Pool child processes. A child receiving
KeyboardInterrupt exits. multiprocessing.Pool interprets that as an unexpectedly
dead worker and may SPAWN A REPLACEMENT before the parent completes cleanup.

v0.4.9:
* Pool workers ignore SIGINT / SIGBREAK.
* Only the parent process receives Ctrl+C.
* Parent immediately terminates + joins the entire Pool.
* Completed results are still checkpointed.
* A second interrupt is an emergency os._exit(130) escape hatch.

Manual cancellation test:

    py -3 urza_solver.py --cancel-test --workers 2

Wait a few seconds, then press Ctrl+C ONCE.

Expected:
    [CANCEL] Ctrl+C received by parent...
    [CANCEL TEST] parent caught interrupt -> terminate()
    [CANCEL TEST] PASS if no Python worker processes respawn.

If OLD orphan workers from prior buggy versions remain:

    Get-Process python,python3 -ErrorAction SilentlyContinue

To force-stop ALL Python processes in the current user session:

    Get-Process python,python3 -ErrorAction SilentlyContinue | Stop-Process -Force

Only use the force-stop command if no other Python job you care about is running.


v0.4.10 WINDOWS INTERRUPTIBLE POOL POLLING
-------------------------------------------
v0.4.9 fixed child worker signal handling, but the parent could still appear to
ignore Ctrl+C while blocked inside multiprocessing.Pool's result iterator wait.

On Windows, low-level process waits are not reliably interruptible at arbitrary
times by Python's KeyboardInterrupt machinery.

v0.4.10 removes blocking imap_unordered() from the parent.

Real solver:
* submit jobs with apply_async();
* poll AsyncResult.ready() from Python every 0.20 seconds;
* consume completed jobs without blocking;
* Ctrl+C is therefore processed at an ordinary Python polling/sleep point;
* parent terminate()+join() shuts down all workers;
* workers still ignore Ctrl+C and are never independently replaced.

Cancellation test uses the same polling architecture.

TEST THIS FIRST:

    py -3 urza_solver.py --cancel-test --workers 2

After it prints:
    Press Ctrl+C ONCE now...

press Ctrl+C once.

Expected within roughly one second:
    [CANCEL] Ctrl+C received by parent...
    [CANCEL TEST] parent caught Ctrl+C -> terminate()
    [CANCEL TEST] PASS...

There should be no replacement workers and PowerShell should return to its
prompt immediately afterward.

Only after this passes should long multi-worker simulations be run.


v0.4.11 CHAIN TWO-DIMENSION SHORTLIST + CACHE
----------------------------------------------
Seed 20260827 exposed a remaining Chain-heavy pathology:
    candidate 5.2/4 ~176.9 s
    ~28k states
    many Chain-live developed states

The problem was no longer permutations. It was repeatedly evaluating the
Cartesian product of:
    bounce subsets x land-sacrifice subsets
for hundreds of Chain-live states.

v0.4.11:
* shortlists bounce subsets independently for every chain length;
* shortlists land-sacrifice subsets independently for every chain length;
* crosses only those diverse shortlists;
* still forces representation of every legal chain length;
* explicitly preserves Cam/Cage/PA/high-value bounce packages;
* preserves unusual land choices such as Crystal Vein/City/Skerry/Saga;
* materializes only a few hundred plans before exact-key dedup;
* memoizes Chain results for strategically identical states, excluding trace.

Regression smoke:
    py -3 urza_solver.py --chain-stress-test
    py -3 urza_solver.py --problem-smoke

Pathological-seed regression:
    py -3 urza_solver.py --profile-oracle --seed 20260827 --beam 300 --action-cap 60 --bottom-cap 4 --depth 100 --profile-turns 7

Primary target:
    5.2/4 should fall dramatically from ~177 s without changing a legitimate
    win/non-win conclusion through T7.


v0.4.12 CRITICAL COMMAND-ZONE / PRE-URZA CORRECTNESS FIX
---------------------------------------------------------
Audit found that prior builds excluded Urza from the 99-card library correctly
but never exposed a normal command-zone cast action. This explains why successful
traces were overwhelmingly "Pre-Urza ... -> cast Urza" terminal shortcuts.

Corrected:
* Urza can now actually be cast from the command zone.
* First cast uses {2}{U}{U}; commander tax adds {2} per prior command-zone cast.
* Sapphire Medallion generic reduction remains available via spell_cost.
* Infinite colorless may pay generic but NEVER waives the required UU.
* `urza_cast_turn` is set only when Urza actually enters via a cast transition.
* Urza creates the Construct and Assistant legendary-cast scry occurs.
* Bouncing/removing Urza clears `s.urza`; the solver can no longer tap artifacts
  for U after Urza has left the battlefield.
* Bounce puts Urza in hand; graveyard-bound Urza chooses command zone.
* Pre-Urza PA/Basalt/Gadget terminal shortcuts were removed.
* Pre-Urza FTT L3+Top "scan the whole library for future blue sources" shortcut
  was removed. The solver must now actually execute the engine and obtain real UU.

TEST:
    py -3 urza_solver.py --commander-smoke

All probability/win-family output from pre-v0.4.12 builds should be considered
invalid for final deck estimates because normal Urza casting was missing.

Chain note:
Do NOT yet restrict Chain in Oracle Mode based on a human tactical policy. The
oracle solver should remain a legal-line upper bound. A tactical Chain gate is
appropriate for the planned knowledge-constrained mode after the rules engine
is stable.


v0.4.13 MULTI-SEED ORACLE RULES-ENGINE SMOKE AUDIT
---------------------------------------------------
Before implementing the knowledge-constrained/policy mulligan mode, freeze and
audit Oracle Mode over multiple deterministic seeds.

New command:

    py -3 urza_solver.py --smoke-seeds 5 --seed 20260821 --beam 300 --action-cap 60 --bottom-cap 4 --depth 100 --turns 7 --smoke-slow-seconds 60

The smoke batch runs SEQUENTIALLY on purpose. This avoids multiprocessing/RAM
contention and makes pathological seed timing easy to interpret.

Each seed reports:
* total oracle runtime;
* chosen win turn;
* actual Urza cast turn;
* mulligan keep size;
* max action depth;
* searched states;
* win family.

Automated flags:
* WIN_WITHOUT_URZA_CAST_TURN
* WIN_BEFORE_URZA_CAST
* LEGACY_PRE_URZA_WIN_LABEL
* WIN_TRACE_MISSING_URZA_CAST
* DEPTH_CEILING_HIT
* SLOW_SEED>N seconds

A batch report is written to:
    smoke_seed_report.json

Recommended cleanup sequence:
1. Run seeds 20260821..20260825.
2. If clean, run 20260826..20260830.
3. Individually profile any seed flagged SLOW or DEPTH_CEILING_HIT.
4. Inspect at least one trace from each distinct win family before treating the
   Oracle engine as frozen.
5. Then fork Oracle Mode into policy/knowledge-constrained mulligan mode.


v0.4.14 LIVE ORACLE PROGRESS + EXACT TURN BOUNDING
---------------------------------------------------
Smoke seeds in v0.4.13 took 45-164 s even when the selected winning hand itself
searched only ~1k-12k states. Audit confirmed why: every discarded mulligan
candidate was still searched all the way through T7.

v0.4.14 exact branch-and-bound:
* If an earlier mulligan stage already wins T5, all LATER stages only search T1-T4.
* A T5 tie from a later mulligan stage cannot beat the earlier stage, so this
  cannot change the oracle result.
* Within the SAME stage, bottom variants still search through the current best
  turn so the existing same-stage tie behavior is preserved.
* `oracle_states_total` now reports ALL searched states, not only the selected
  winning candidate.

Live progress during smoke batches:
    [oracle seed=...] START 6 keep=6 variants=4 horizon=T4
    [oracle seed=...] -> 6.2/4 ... search<=T4
    [search seed=... 6.2/4] T3 D17 frontier=300 searched=...
    [oracle seed=...] <- 6.2/4 time=... win=...
    [oracle seed=...] DONE 6 ...

Default search heartbeat is every 10 seconds. Change with:
    --search-progress-seconds 5

Recommended regression:
    py -3 urza_solver.py --smoke-seeds 5 --seed 20260821 --beam 300 --action-cap 60 --bottom-cap 4 --depth 100 --turns 7 --search-progress-seconds 10

The selected win turns/families should remain compatible with v0.4.13, while
total wall time should fall substantially once an early win is discovered.


v0.4.15 CAM / KNACK / HELIX CORRECTNESS FIX
--------------------------------------------
Audit found a concrete bug: Sewer-veillance Cam had a cost and dedicated
ETB/LTB/draw code, but was missing from ARTIFACTS.

Consequences in older builds:
* Cam could not be cast normally from hand.
* artifact tutors did not recognize Cam.
* Cam did not receive normal artifact cast/ETB triggers.
* Urza did not recognize Cam as an artifact.
* therefore Cam/Knack win families were strongly suppressed.

Also fixed:
* old Knack/Helix merely sitting in the graveyard no longer causes a later
  false-positive Cam win;
* Cam+Knack terminal requires the current turn's `knack_target` to still exist,
  be a creature, be non-sick, and be untapped;
* Cam's 3U sacrifice path no longer resolves its LTB untap twice.

Run:
    py -3 urza_solver.py --cam-smoke

All pre-v0.4.15 Cam-family frequency results should be discarded.


v0.4.16 FULL METADATA / TUTOR / X-COST AUDIT
----------------------------------------------
Critical issues found and fixed:

CARD TYPES
* Forensic Gadgeteer is Creature only, NOT an artifact.
  - artifact tutors can no longer find it;
  - Urza can no longer tap it for U;
  - it no longer counts for metalcraft/artifact count;
  - casting Gadgeteer no longer triggers artifact-cast effects.
* Sol Ring and Mana Vault were missing from ARTIFACTS.
  They now cast/tutor/trigger/tap for Urza correctly.
* Chrome Dome is an artifact creature.
* Reality Chip is an artifact creature while unattached and becomes a
  noncreature while reconfigured.
* Cam remains correctly classified as an artifact.

COSTS / MANA VALUE
* Aether Spellbomb printed cost corrected to {1}.
* Witching Well printed cost corrected to {U}.
* Mishra's Bauble added as {0}.
* Missing interaction spell costs added.
* true lands, including Seat of the Synod, have MV0.
* X cards use X=0 off stack:
  Chalice 0, Reshape 2, Whir 3.
* Gitaxian Probe / Mental Misstep retain MV1 despite Phyrexian/life casting.
* MDFCs use front-face MV: Hydro 3, Sink 3, Sea Gate 7.

TUTORS
* Dizzy Spell transmute = exactly MV1.
* Muddle the Mixture transmute = exactly MV2.
* Spellseeker = instant/sorcery MV<=2.
* Mystical Tutor = any instant/sorcery.
* Merchant Scroll = blue instant; no longer illegally finds Reshape or
  Transmute Artifact, and now correctly sees Dizzy, Scour, Whir, Sink,
  Force/Pact/etc.
* simple search tutors now actually SHUFFLE.
* Mystical shuffles the rest before placing the selected card on top.
* artifact tutors now shuffle after searching.

URZA'S SAGA
Saga III uses PRINTED mana cost {0}/{1}, not generic MV<=1.
Correct examples:
  YES: Aether Spellbomb, Sol Ring, Mana Vault, Jeweled Amulet.
  NO: Witching Well {U}, Cam {U}, Moonsnare {U}, Seat (no mana cost).

X SPELLS
* Sapphire Medallion now reduces the generic X portion of Reshape/Whir.
* Reshape remains XUU, target MV<=X.
* Whir remains XUUU with improvise on the generic X portion.
* Transmute Artifact can legally decline a positive MV difference, putting
  the searched artifact into the graveyard.

AETHER SPELLBOMB
* draw activation corrected from U to {1}.

Run:
    py -3 urza_solver.py --metadata-smoke
    py -3 urza_solver.py --cam-smoke
    py -3 urza_solver.py --commander-smoke

Because Forensic Gadgeteer and Sol Ring/Mana Vault were materially
misclassified, all pre-v0.4.16 probability estimates should be treated as
rules-engine development results, not final deck statistics.


v0.4.17 TUTOR HELPER REGRESSION HOTFIX
--------------------------------------
v0.4.16's tutor metadata rewrite correctly changed tutor eligibility/shuffling,
but `simple_tutor_actions()` referenced `move_library_to_hand()` after that
helper had been lost from the file.

v0.4.17 restores the helper and adds an execution-level tutor smoke that
actually runs:
* Dizzy transmute
* Muddle transmute
* Merchant Scroll
* Mystical Tutor
* Spellseeker ETB
* artifact tutor branches

Run before simulation:
    py -3 urza_solver.py --metadata-smoke
    py -3 urza_solver.py --tutor-smoke
    py -3 urza_solver.py --cam-smoke
    py -3 urza_solver.py --commander-smoke


v0.4.18 MAJOR COMBO-PATH INTEGRATION SMOKE
-------------------------------------------
Run:
    py -3 urza_solver.py --combo-smoke

Unlike the completed-state unit smokes, these cases begin immediately BEFORE
the combo and require the real legal-action graph to navigate to the terminal.

Covered:
* Power Artifact + Grim
* Power Artifact + Basalt
* Basalt + Gadgeteer
* Top + Reality Chip + producer
* Top + FTT L3
* Top + FTT L2 + producer
* Top + Gadgeteer + producer
* Chrome Dome + Station
* Chrome Dome + Golem
* Knack + Cam + Golem
* Helix + Cam + VFC
* Spellseeker -> Knack/Helix -> bounce/reuse Spellseeker ->
  Transmute Artifact -> Cam

Engine integration checks:
* Knack/Golem + positive-artifact setup
* Station artifact-ETB -> immediate mana conversion
* Golem artifact-ETB -> immediate mana conversion
* Uthros + Station branch generation

The Spellseeker fixture keeps total mana below five so Urza spin cannot shortcut
the intended tutor chain.


v0.4.19 GRAPH ACCOUNTING + NATURAL FAMILY SMOKE
------------------------------------------------
Graph metrics are now accumulated across EVERY oracle mulligan candidate:

* nodes_expanded
* edges_generated
* exact_key_merges
* cycle_skips
* dominance_pruned
* beam_pruned
* layers
* max_frontier
* max_raw_successors
* average_branching_factor
* upkeep_nodes_expanded / upkeep_edges_generated
* upkeep_exact_key_merges / upkeep_dominance_pruned / upkeep_beam_pruned
* upkeep_layers / upkeep_max_frontier / upkeep_max_raw_successors
* upkeep_average_branching_factor and generated pay/decline/bounce results

These are included in smoke/family JSON reports and live summaries.

Natural family smoke:
    py -3 urza_solver.py --family-smoke 10 --seed 20260821 --beam 300 --action-cap 60 --bottom-cap 4 --depth 100 --turns 7 --search-progress-seconds 10

This runs deterministic Oracle seeds and records which win families arise
organically. It explicitly reports:
    Natural Cam/Knack wins: X/N

Output:
    family_smoke_report.json

Recommended order:
1. run --combo-smoke once;
2. run --family-smoke 10;
3. if graph metrics show no pathological edge explosion and at least the expected
   family diversity appears, freeze Oracle Mode;
4. then run a larger Oracle sample before creating the knowledge-constrained fork.
\n\nv0.4.20 PRE-CAP ACTION AUDIT\n----------------------------\n`max_raw_successors=60` in v0.4.19 was measured AFTER legal_actions() applied\nACTION_CAP, so it could not reveal whether the solver was hiding a much wider\nuncapped action set.\n\nNew diagnostic mode:\n    py -3 urza_solver.py --cap-audit 3 --seed 20260826 --beam 300 --action-cap 60 --bottom-cap 4 --depth 100 --turns 7 --search-progress-seconds 10\n\nIt leaves production search semantics unchanged, but records BEFORE truncation:\n* states evaluated by legal_actions();\n* states whose legal action set exceeded ACTION_CAP;\n* maximum pre-cap legal action count;\n* total raw actions;\n* total actions discarded by ACTION_CAP;\n* truncation rate;\n* action-family composition of discarded branches;\n* 20 worst high-branching states.\n\nOutput:\n    cap_audit_report.json\n\nRecommended first audit: seeds 20260826-20260828 because v0.4.19 showed the\nlargest graph widths there.\n

v0.4.21 CAP-AUDIT IMPORT HOTFIX
--------------------------------
v0.4.20's cap-audit statistics used collections.Counter() but did not import
the collections module. No rules/search semantics changed.


v0.4.22 TUTOR-TARGET CAP DIVERSITY AUDIT
-----------------------------------------
Diagnostic only; production search semantics are unchanged.

Run:
    py -3 urza_solver.py --tutor-cap-audit 3 --seed 20260826 --beam 300 --action-cap 60 --bottom-cap 4 --depth 100 --turns 7 --search-progress-seconds 10

Reports per cap-hit state:
* tutor source
* unique targets before cap
* unique targets after cap
* targets completely lost
* known engine/combo targets completely lost

Output:
    tutor_cap_audit_report.json


v0.4.23 ORACLE MULLIGAN FLOOR / PROVENANCE / WORKER CONFIG
------------------------------------------------------------
Oracle production runs and the Oracle profiler now use one shared mulligan-stage
definition. The default remains `--min-keep 4`. Use `--min-keep 3` to append a
fresh-seven, bottom-four keep-three stage without changing the RNG/shuffles of
the existing 7A through keep-four stages.

Focused regression commands:
    py -3 urza_solver.py --mulligan-smoke
    py -3 urza_solver.py --worker-config-smoke

The worker smoke uses the real spawned-worker path to confirm that search-
defining settings reach the child process instead of reverting to source
defaults. This includes turn horizon, beam, action cap, bottom cap, turn depth,
and minimum keep.

JSON reports now include provenance for:
* Git commit and dirty-tree state;
* turn horizon, action cap, bottom cap, minimum keep and active stages;
* beam and per-turn search depth;
* base seed, seed count/range, and step;
* worker count / sequential-versus-multiprocessing execution;
* source and ordered-deck hashes;
* the inherited PYTHONHASHSEED value.

PYTHONHASHSEED is fixed when Python starts. The solver reports it but does not
attempt to change it inside the running process. If it is unset, the console and
report contain a reproducibility warning. Set it in PowerShell before every
pinned comparison.

PINNED SEQUENTIAL A/B/C VALIDATION
----------------------------------
Before another 30-seed benchmark, use the same five seeds and search settings to
separate the turn-horizon change from the mulligan-floor change. These smoke
batches run sequentially by design.

A. T7, minimum keep four:
    $env:PYTHONHASHSEED='0'; py -3 urza_solver.py --smoke-seeds 5 --smoke-seed-step 1 --seed 20260821 --turns 7 --min-keep 4 --beam 300 --action-cap 60 --bottom-cap 4 --depth 100 --search-progress-seconds 10

B. T6, minimum keep four:
    $env:PYTHONHASHSEED='0'; py -3 urza_solver.py --smoke-seeds 5 --smoke-seed-step 1 --seed 20260821 --turns 6 --min-keep 4 --beam 300 --action-cap 60 --bottom-cap 4 --depth 100 --search-progress-seconds 10

C. T6, minimum keep three:
    $env:PYTHONHASHSEED='0'; py -3 urza_solver.py --smoke-seeds 5 --smoke-seed-step 1 --seed 20260821 --turns 6 --min-keep 3 --beam 300 --action-cap 60 --bottom-cap 4 --depth 100 --search-progress-seconds 10

Each command evaluates seeds 20260821 through 20260825 with beam 300,
ACTION_CAP 60, BOTTOM_CAP 4, and depth 100. Preserve or rename
smoke_seed_report.json after each case because the next case writes the same
path.
