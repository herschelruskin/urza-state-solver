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
| Urza {5} spin | activate/pay 5 → shuffle → exile/observe top card → choose play/cast/decline | `random_observation_adapters.py` |
| Cephalid Coliseum threshold | activate/pay/tap/sacrifice → draw 3 observations → choose discard 3 | `random_observation_adapters.py` |

### B. Hidden result becomes known, but no contingent choice occurs inside the same effect

These do **not** need a second Phase-1 policy decision stage. Phase 2 must still emit typed observations and update `InformationState` before the next ordinary policy decision.

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
- Uthros Research Craft draw trigger;
- modeled Mystic Remora / Rhystic Study / opponent-fed draws;
- Sensei's Divining Top draw ability;
- Top + Key double-draw macro;
- Ipnu Rivulet self-mill;
- Codex Shredder self-mill;
- Grinding Station self-mill.

Required Phase-2 rule: the policy must commit to the action before the actual unknown draw/mill result is resolved. The next policy decision may use the resulting public/known cards.

### C. Shuffle/search effects with no meaningful hidden target choice in the current deck abstraction

- fetchland → Island search/shuffle.

The current model has a deterministic basic-Island destination. The policy must choose to crack the fetch without seeing the resulting shuffled future. A `ShuffleObservation` must clear stale top/bottom knowledge.

### D. Actions whose library card is already legally visible before the decision

- Reality Chip top play/cast;
- active Fortune Teller's Talent top play/cast.

These are information-faithful only if Phase 2 generates the action from `InformationState.known_top` / the derived `PolicyView`, never by reading raw `true_state.library[0]` inside policy code. Continuous top visibility must refresh after draws, mills, shuffles and other top changes.

### E. Public-only choices; no hidden-zone split required

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
- Repurposing/recursion choices entirely within public hand/graveyard/battlefield zones.

They still require normal policy isolation: Oracle search successors may not be used to select among them in policy mode.

## Phase-2 integration obligations exposed by this audit

The Phase-1 adapters deliberately do not duplicate the full validated rules engine. Phase 2 must connect them through one non-Oracle rules adapter.

1. **Shared cast continuation.** `cast_known_card_free` from an Urza spin must route through a shared cast resolver. Do not call the old bundled Oracle macro if it would immediately make Assistant/scry decisions.
2. **Scry trigger integration.** Artifact/legendary casts that trigger Artificer's Assistant, Witching Well or Giant's Boulder must invoke the staged scry effect at the correct trigger point.
3. **ETB continuation.** Search adapters that put an artifact onto the battlefield intentionally defer the artifact ETB trigger bundle so a Well/Boulder scry cannot bypass the observation boundary.
4. **Draw/mill observations.** Every current `draw_from_library` / mill macro used by policy mode must emit typed draw/public-zone events before returning to policy.
5. **Continuous top visibility.** Chip/FTT must refresh only the legally visible current top after a hidden-zone transition.
6. **Fetch shuffle.** Fetch resolution must emit shuffle invalidation even though the current target is deterministic Island.
7. **Urza exile permission lifetime.** The Phase-1 adapter models the immediate post-spin play/cast decision and can leave the card exiled. Phase 2 should decide whether persistent until-end-of-turn permission needs explicit state if delayed play becomes strategically relevant.
8. **Mana/payment plans.** Whir improvise and Transmute during-resolution mana-payment choices are public strategic decisions and must remain outside hidden-target inference.

## Known Oracle-vs-policy implementation distinctions

These are intentional and must not be confused with Oracle regressions:

- Oracle can choose X for Reshape/Whir from the exact hidden target; policy mode must choose X first.
- Oracle bundles Top/scry/tutor outcomes into successor states; policy mode splits them into information sets.
- Oracle Urza spin immediately inspects and plays the randomized card; policy mode observes it only after committing to the spin.
- Oracle Coliseum generates discard branches after seeing actual draws; policy mode makes that same discard choice only after typed draw observations.

## Phase 1 completion gate

Do not merge this branch merely because the audit exists. Phase 1 is complete only when:

- `phase1_acceptance_smoke.py` passes;
- all focused adapter smokes pass;
- architecture/information/strategic-value smokes pass;
- the repository's existing Oracle regression suite remains green;
- branch diff confirms no unintended Oracle/rules/search behavior edits.

Once those conditions are green, Phase 2 begins with the non-Oracle rules adapter and deterministic base policy described in `NON_ORACLE_IMPLEMENTATION_ROADMAP.md`.
