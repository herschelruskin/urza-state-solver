# R5 start checkpoint

## Scope

R5 starts from the fully accepted R4 closure and begins the deterministic POLICY layer. R4 rules, model, information, value, coverage, and 13-family terminal contracts remain frozen.

This first R5 slice is deliberately narrow: it establishes the deterministic one-step selection kernel before ordinary-action enumeration, multi-step rollout, or Monte Carlo estimation are added.

## Policy boundary

`urza-policy` continues to depend on `urza-info`, not `urza-core` or `urza-rules`.

The policy receives only:

- an `InformationState`;
- a public legal-candidate set supplied by an external execution bridge.

It cannot inspect `TrueState`, unknown library order, physical `ObjectId`s, execution RNG provenance, or rules implementation details.

## Deterministic candidate contract

The R5-start kernel introduces:

- decision-local opaque `ActionToken`s for bridge round-tripping;
- `PolicyActionClass` for public semantic action categories;
- `PolicyPublicKey` using only card identity and canonical observed object references;
- `PolicyCandidate` as the policy-visible legal choice record;
- `DeterministicPolicy` as the initial stable selector.

Pending contingent rules decisions are mandatory: if `InformationState` says a decision is pending, ordinary candidates cannot bypass it. Candidate enumeration order cannot change the selected action. Semantic public keys are compared before opaque action tokens, so execution numbering is not strategy.

The baseline class order is intentionally simple and auditable: contingent decision, land play, mana production, spell cast, other activation, pass priority. It is infrastructure for deterministic rollout work, not a claim of final gameplay strength.

## Frozen inputs

R5 starts with the accepted R4 namespaces unchanged:

- rules: `r4_acceptance_v6`;
- model: `urza_model_r4c_2026_09_04`;
- information: `information_state_v7_r4`;
- ValueKey: `value_key_v7_r4`.

R5 policy namespace:

- policy: `r5_deterministic_start_v1`.

No rules/card coverage was broadened in this slice.

## Acceptance for this checkpoint

The checkpoint requires:

- policy has no direct `urza-core` or `urza-rules` dependency;
- duplicate action tokens are rejected;
- pending decisions cannot be skipped;
- contingent candidates without a pending decision are rejected;
- input candidate ordering cannot affect selection;
- semantic public identity outranks opaque token numbering;
- full locked workspace formatting, Clippy, tests, benchmark compilation, and R0-R5 audits are green.

Validated R5-start implementation commit: `39d06a960ce21a0b58b39835ffce61410895ae88`.
Dedicated acceptance workflow run: `33941762035` (attempt 2): **PASS**.

## Next R5 block

Build the public ordinary-action candidate bridge across the accepted R4 action surface. The bridge must canonicalize execution objects into public candidate identity without reducing legal strategic capability. After that, add deterministic multi-step rollout sequencing and only then connect `urza-mc` to sampled-world evaluation.

Do not port Python gameplay logic or old Python policy structure. Python remains parity/fixture evidence only.
