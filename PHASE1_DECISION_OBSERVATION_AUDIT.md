# Phase 1 Decision / Observation Macro Audit

**Branch:** `phase1-decision-observation-boundary`  
**Purpose:** identify every current Oracle macro that can expose hidden information and classify whether it needs an explicit decision → observation → contingent-decision split before Phase 2.

This document is an implementation audit, not a claim that Oracle mode should change. Oracle remains the clairvoyant regression ceiling. All Phase-1 adapters are sidecar policy-mode code.

## Classification

### A. Contingent choice after newly revealed hidden information — explicit split required

These effects are unsafe if represented as one policy action whose successor is scored through the actual hidden future.

| Effect | Required staging | Phase-1 adapter |
|---|---|---|
| Sensei's Divining Top look/reorder | activate → reveal top 3 → choose order | `top_decision_adapter.py` |
| Scry 1/2 | commit source → reveal N → choose top/bottom order | `scry_decision_adapter.py` |
| Dizzy / Muddle / Merchant / Mystical / Spellseeker | use tutor → search observation → choose target → shuffle/placement | `tutor_decision_adapter.py` |
| Transmute Artifact | cast/pay UU → choose sacrifice on resolution → search → choose target → pay/decline MV difference → shuffle | `transmute_artifact_adapter.py` |
| Reshape | choose X + sacrifice as cast commitment → search MV <= X → choose target → shuffle | `x_artifact_search_adapter.py` |
| Whir of Invention | choose X + improvise/payment plan while casting → search MV <= X → choose target → shuffle | `x_artifact_search_adapter.py` |
| Repurposing Bay | pay/tap/sacrifice as activation cost → exact-MV search → choose target → shuffle | `remaining_search_adapters.py` |
| Tezzeret -3 | pay loyalty / commit activation → search MV <= 1 → choose target → shuffle | `remaining_search_adapters.py` |
| Urza's Saga III | pending trigger → search observation → choose target/fail → shuffle | `remaining_search_adapters.py` |
| Scour for Scrap | choose mode(s) + graveyard target when casting → library search if chosen → choose library artifact → shuffle → resolve public graveyard mode | `remaining_search_adapters.py` |
| Cephalid Coliseum threshold | activate/pay/tap/sacrifice → draw 3 observations → choose discard 3 | `random_observation_adapters.py` |

### B. Random result creates a persistent public permission rather than an immediate choice

**Urza {5} spin** is intentionally *not* modeled as “spin → observe → play/cast/decline now.” Its rules text creates a permission lasting until end of turn.

Correct policy staging:

`activate/pay 5 → shuffle → exile/observe top → grant persistent play permission → return to ordinary sequencing`

The permission:

- remains available through later actions, trigger resolutions and additional spins;
- follows normal timing restrictions;
- can be used in a priority window when normal timing/flash permits (including Valley Floodcaller for noncreature spells);
- allows an MDFC's land face and spell face when each is legal;
- forces X=0 when a spell with X in its mana cost is cast without paying its mana cost;
- expires at end of turn if unused, while the card itself remains exiled;
- is individually tracked so multiple spins can create multiple simultaneous live permissions.

Adapter: `urza_permission_adapter.py`.

### C. Simultaneous controlled triggers — observation may precede ordering choice

A cast may create simultaneous triggers we control. Their stack order is a strategic policy decision when different orders produce different future information/resources.

Current modeled cast-trigger batch can include:

- Valley Floodcaller noncreature-cast trigger;
- Artificer's Assistant scry 1;
- Uthros Research Craft draw + charge-counter trigger;
- Forensic Gadgeteer investigate;
- Vexing Bauble's no-mana-spent counter trigger.

`trigger_order_adapter.py` models:

`cast completes → refresh legally lookable top → collect simultaneous triggers → choose resolution order → persist ordered trigger stack`

Important: Reality Chip and Fortune Teller's Talent are **not** triggers here. Their relevant abilities are continuous look/play permissions. They can make the newly exposed top card legally knowable after casting finishes and before simultaneous triggers are ordered. That information may change whether, for example, Assistant should resolve before Uthros or Uthros before Assistant.

Phase 2 must resolve one trigger at a time. After a trigger resolves, normal priority is returned before the next object resolves. New triggers created during resolution (for example artifact-ETB triggers created by Gadgeteer's Clue) are placed above older unresolved stack objects.

### D. Hidden result becomes known, but no contingent choice occurs inside the same effect

These do **not** need another Phase-1 choice inside the effect itself. Phase 2 must still emit typed observations and update `InformationState` before the next legal policy decision / priority window.

- normal draw step;
- Clue draw;
- The One Ring draw;
- Gitaxian Probe draw;
- Sea Gate Restoration draw;
- Witching Well draw ability;
- Sewer-veillance Cam draw ability;
- Vexing Bauble draw;
- delayed Mishra's/Urza's Bauble draw;
- Faerie Mastermind draw;
- Uthros Research Craft draw **once its trigger is the next object resolving**;
- modeled Mystic Remora / Rhystic Study / opponent-fed draws;
- Sensei's Divining Top draw ability;
- Top + Key double-draw macro;
- Ipnu Rivulet self-mill;
- Codex Shredder self-mill;
- Grinding Station self-mill.

Required Phase-2 rule: the policy must commit to the action before the actual unknown draw/mill result is resolved. The next legal policy decision may use the resulting public/known cards.

### E. Shuffle/search effects with no meaningful hidden target choice in the current deck abstraction

- fetchland → Island search/shuffle.

The current model has a deterministic basic-Island destination. The policy must choose to crack the fetch without seeing the resulting shuffled future. A `ShuffleObservation` must clear stale top/bottom knowledge.

### F. Actions whose library card is already legally visible before the decision

- Reality Chip top play/cast while attached;
- Fortune Teller's Talent level-2 top play/cast after a spell has been cast this turn.

The **look permission is broader than the play permission**:

- The Reality Chip lets its controller look at the top card whenever the Chip is on the battlefield, attached or not.
- Fortune Teller's Talent lets its controller look at the top card at level 1, before level 2 is active and before a spell has been cast that turn.

These actions are information-faithful only if Phase 2 generates them from `InformationState.known_top` / the derived `PolicyView`, never by reading raw `true_state.library[0]` inside policy code. Continuous top visibility must refresh after draws, mills, shuffles, top casts and other top changes.

### G. Public-only choices; no hidden-zone split required

Examples include:

- ordinary mana abilities;
- land play from hand;
- Chrome Mox imprint choice from hand;
- Mox Diamond discard choice from hand;
- Power Artifact attachment target;
- Reality Chip reconfigure target;
- Key/Minamo untap targets;
- Otawara / Aether Spellbomb / Knack / Chain bounce choices;
- Uthros station creature target;
- Tezzeret 0 target;
- Offer self-counter target;
- recursion choices entirely within public hand/graveyard/battlefield zones.

They still require normal policy isolation: Oracle search successors may not be used to select among them in policy mode.

## Runtime value identity exposed by this audit

The non-Oracle Bellman/MC state is not just `StrategicValueState + InformationState`.

The following public sidecars change future legal actions and therefore belong in V/Q identity:

1. live Urza play permissions, including multiplicity and expiry;
2. ordered pending trigger stack;
3. current decision window (`main_empty`, `priority`, or post-observation choice).

`non_oracle_runtime_value_key.py` composes these with the validated strategic state projection. Permission IDs and sequence counters are provenance and are excluded from strategic identity; card/expiry/multiplicity are retained. Trigger order is retained.

## Phase-2 integration obligations exposed by this audit

The Phase-1 adapters deliberately do not duplicate the full validated rules engine. Phase 2 must connect them through one non-Oracle rules adapter.

1. **Shared cast continuation.** Casting a live Urza-permission card must move that card directly from exile to the stack, consume the exact permission, enforce “without paying mana cost” rules, and then generate cast triggers. Do not stage the card through hand.
2. **Persistent Urza permissions.** Add every live permission to ordinary action generation at every legal timing window until end of turn. Additional spins append permissions rather than replacing earlier ones.
3. **Controlled trigger stack.** After casting completes, refresh any legally lookable new top, then order simultaneous controlled triggers. Resolve one at a time with priority between resolutions. New triggers stack above older unresolved objects.
4. **Scry trigger integration.** Artificer's Assistant and Well/Boulder scry events must invoke staged scry at the correct resolution point.
5. **ETB continuation.** Search adapters that put an artifact onto the battlefield intentionally defer the artifact ETB trigger bundle so a Well/Boulder scry cannot bypass the observation boundary.
6. **Draw/mill observations.** Every current `draw_from_library` / mill macro used by policy mode must emit typed draw/public-zone events before returning to policy.
7. **Continuous top visibility.** Chip/FTT look permission must refresh the legally visible current top even when their play-from-top condition is inactive.
8. **Fetch shuffle.** Fetch resolution must emit shuffle invalidation even though the current target is deterministic Island.
9. **Mana/payment plans.** Whir improvise and Transmute during-resolution mana-payment choices are public strategic decisions and must remain outside hidden-target inference.
10. **Timing modifications.** Valley Floodcaller's flash permission must affect legal casts from hand, top and Urza exile permissions during priority windows.

## Known Oracle-vs-policy implementation distinctions

These are intentional and must not be confused with Oracle regressions:

- Oracle can choose X for Reshape/Whir from the exact hidden target; policy mode must choose X first.
- Oracle bundles Top/scry/tutor outcomes into successor states; policy mode splits them into information sets.
- Oracle Urza spin immediately inspects and plays the randomized card; policy mode grants a persistent until-end-of-turn permission and returns to ordinary sequencing.
- Oracle artifact-cast trigger macro uses one favorable fixed trigger order; policy mode must choose order from legal information and persist the unresolved stack.
- Oracle Coliseum generates discard branches after seeing actual draws; policy mode makes that same discard choice only after typed draw observations.

## Phase 1 completion gate

Do not merge this branch merely because the audit exists. Phase 1 is complete only when:

- `phase1_acceptance_smoke.py` passes, including persistent Urza-permission, continuous-top, trigger-order and runtime-key suites;
- all focused adapter smokes pass;
- architecture/information/strategic-value smokes pass;
- the repository's existing Oracle regression suite remains green;
- branch diff confirms no unintended Oracle/rules/search behavior edits.

Once those conditions are green, Phase 2 begins with the non-Oracle rules adapter and deterministic base policy described in `NON_ORACLE_IMPLEMENTATION_ROADMAP.md`.
