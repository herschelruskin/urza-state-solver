# Post-R7 Oracle-Text and Scry/Stack Validation

Status: **MECHANICS VALIDATION SLICE**

This checkpoint is intentionally narrow. It closes the remaining card-text and
scry/stack questions before returning to policy/value work.

## Pinned Oracle text validation

The frozen R1 catalog stores SHA-256 digests of Oracle text rather than copying
raw rules text into every runtime profile. The current regression pins the
following exact text/digest pairs:

- **Faerie Mastermind** — `9057053fb56b1a7734ce8ae12241f7eb15814d48df0cd2dc3b13e4994333a438`
  - `Flash`
  - `Flying`
  - `Whenever an opponent draws their second card each turn, you draw a card.`
  - `{3}{U}: Each player draws a card.`
- **Mystic Remora** — `4c1b24efecbfc96ef5aa572d00c124322ce5f061349ecbec21e3a0676021a00b`
  - `Cumulative upkeep {1} (At the beginning of your upkeep, put an age counter on this permanent, then sacrifice it unless you pay its upkeep cost for each age counter on it.)`
  - `Whenever an opponent casts a noncreature spell, you may draw a card unless that player pays {4}.`
- **Rhystic Study** — `b01edb4edf239cd0b4116ab58ea2fb90152ed9b83b068b6ea34ccbe8d67fd03c`
  - `Whenever an opponent casts a spell, you may draw a card unless that player pays {1}.`
- **Artificer's Assistant** — `4500992939e68bf5d0e9ccaae34745d9b5493891717d983002967d79a4d583f6`
  - `Flying`
  - `Whenever you cast a historic spell, scry 1. (Artifacts, legendaries, and Sagas are historic. To scry 1, look at the top card of your library, then you may put that card on the bottom.)`

These hashes are non-empty and are checked against the pinned R1 metadata.
Rhystic Study, Mystic Remora, and Faerie Mastermind remain **environment
deferred**: their opponent-driven trigger frequencies are not intrinsic rules
facts and must enter through an explicit goldfish environment contract. This
validation does not silently install the old Oracle's 2/2/1 rates.

## Artificer's Assistant / scry / trigger ordering

The existing Rust rules engine already had an exact scry primitive: it observes
the top cards, then exposes every legal top/bottom partition and ordering as a
post-observation contingent decision. It previously had no production card that
used it.

This slice activates Artificer's Assistant and connects its historic-cast
trigger to real `scry 1`.

When one cast creates multiple player-controlled triggers (for example an
artifact cast with Assistant and Uthros at 3+ charge), the triggers are first
placed in a deterministic canonical block and the player receives a real
`TriggerOrder` decision. The selected action names the desired **top-of-stack
first** ordering. This makes the strategically distinct lines explicit:

- Assistant scry resolves first -> the player may bottom the current top card ->
  Uthros draws the next card.
- Uthros resolves first -> it draws the current top card -> Assistant scries the
  following card.

After trigger order is chosen, priority returns normally. Sensei's Divining Top
may therefore be activated above those triggers, and its top-three reorder
resolves before them. The rules/bridge expose that choice; deciding when that
extra Top activation is valuable belongs to the upcoming policy/value pass.

Historic classification for the current database comes from pinned R1 public
type-line metadata: artifacts, legendary spells, and Sagas. Legendary lands do
not create Assistant triggers because lands are played rather than cast.
