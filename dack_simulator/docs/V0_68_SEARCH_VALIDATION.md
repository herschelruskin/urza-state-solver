# v0.68 search validation

## Why v0.68 exists

The matched land-vs-Plains screen found negative paired deltas for City of Brass and Mana Confluence even though, with life ignored in this goldfish and no nonwhite cost requirement, those lands cannot be intrinsically worse than Plains. This was therefore a bounded-search correctness signal rather than a card-performance result.

## Findings

1. The v0.64 scorer credited only a narrow white-land set, causing rainbow sources to be undervalued by the beam.
2. Even after that scorer repair, flexible colored mana created additional payment-state shapes. At moderate beam widths the target tree could therefore lose a valid continuation that the simpler Plains control tree retained.
3. Raising the beam alone was not sufficient at 80, 120, 160, or 200 for all adversarial rows.
4. In the current white/colorless deck, unrestricted colored mana is strategically identical to W unless Pentad Prism is currently in hand; Prism can distinguish colors through sunburst.
5. v0.68 canonicalizes that otherwise redundant choice while retaining unrestricted color when Prism can use it.

## Adversarial convergence

Hard City of Brass and Mana Confluence future orders were replayed at beams 80, 120, 160, 200, 240, 320, 480, and selected cases at 640. The hardest known rows become correct by beam 240 and stay correct at larger beams.

A fresh/replayed 10-context set each for City of Brass and Mana Confluence at beam 240 yielded:
- 20 matched contexts total;
- 80 future/seat rows;
- zero cases where the rainbow land won later than its paired Plains control;
- zero context-level utility delta in all 20 replayed contexts.

Previously failing Tarnished Citadel and Starting Town future orders also match their Plains controls at beam 240.

## Production rule

Use v0.68 with:
- beam = 240;
- four sampled future orders per matched context;
- exact target/control pairing;
- process-isolated tiny shards;
- immediate CSV flush after every completed context.

The prior v0.64/v0.65 beam-40 N=10 screen is retained as a debugging artifact only. Never pool it with v0.68 production data.

## Remaining limitation

Beam search is still bounded search, not a proof of exhaustive reachability. Production results should therefore include convergence spot checks at larger beams, especially for decision-critical borderline cards. The dominance regressions are a guardrail, not a guarantee that every non-dominance comparison is exact.

