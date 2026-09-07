# Post-R7 strategic value policy

## Status

**IMPLEMENTATION CANDIDATE — acceptance requires green policy/rollout gate and 128-world smoke.**

This slice returns from the closed card-text/mechanics validation to the policy/value boundary. It does not change the frozen R5 deterministic selector or its cache/rollout identity. Instead it adds an explicitly versioned `StrategicPolicy` consuming only `InformationState` plus public candidate metadata.

## Value surface

The first strategic layer covers four deliberately narrow concerns:

- **engine value**: public cast/activation candidates can receive explicit values, so intrinsic engines such as Top, Ring, Reality Chip, FTT and Uthros are no longer selected only by structural card/action ordering;
- **tutor value**: legal real targets are ranked by public card value plus progress toward configured terminal recipes; fail-to-find remains below every legal real target;
- **library-selection value**: scry and Top reorder choices score only cards that have actually been observed, while unknown cards receive one anonymous baseline value;
- **terminal-precursor value**: public hand/battlefield progress toward explicit recipes receives a completion/proximity bonus without asserting a terminal win before the rules detector does.

Assistant/Uthros trigger ordering uses the already-public controlled-trigger block. With a known valuable top card the policy prefers Uthros first; with a known poor top card it prefers Assistant first. When the top is unknown, trigger order falls back deterministically and cannot inspect the unknown library multiset. A configured Top-look action may intervene above Assistant/Uthros triggers only while fewer than three top cards are already known; after Top resolves, normal stack draining resumes.

## Boundaries

- No `TrueState` or hidden library order is visible to policy.
- No Python gameplay or policy implementation is ported.
- Rhystic Study, Mystic Remora and Faerie Mastermind receive no fabricated opponent-event draw value; the environment-deferred boundary remains intact.
- Terminal recipes are precursor heuristics only. `detect_terminal_win` remains the sole terminal authority.
- The historical `DeterministicPolicy`, `POLICY_VERSION`, and `rollout` entrypoint are unchanged. The new selector uses `POST_R7_STRATEGIC_POLICY_VERSION` and `POST_R7_STRATEGIC_ROLLOUT_VERSION`.
