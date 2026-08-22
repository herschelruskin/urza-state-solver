#!/usr/bin/env python3
"""Legal hidden-zone knowledge propagation for the non-Oracle value layer.

This module is an adapter around the validated Oracle transition engine.  It does
not change ``urza_solver.State`` or any rules/search behavior.  Instead it carries
``InformationState`` beside a concrete State and updates only knowledge the player
is entitled to retain.

Current modeled knowledge events:
- scry: cards looked at, retained top order, and cards put on bottom;
- Sensei's Divining Top reorder and draw ability;
- Mystical Tutor shuffle-then-known-top placement;
- every current library-search shuffle and Urza spin;
- draws/mills/top casts consuming an already-known prefix;
- continuous top visibility from attached Reality Chip or active FTT top access.

The concrete State is used only to validate/infer the consequences of an event the
player observed.  Exact unknown order is never copied wholesale into InformationState.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from functools import lru_cache
import re
from typing import Iterable, Sequence, Tuple

import urza_solver as solver
from solver_architecture import InformationState


class InformationPropagationError(RuntimeError):
    pass


_SCRY_RE = re.compile(r"\bscry\s+(\d+)\s+\((.*)\)\s*$")
_MYSTICAL_PREFIX = "Mystical -> shuffle, then top "

# Search/action summaries whose implementation calls shuffled_library() even if
# the human-readable trace does not literally contain the word "shuffle".
_SHUFFLE_PREFIXES = (
    "Dizzy Spell -> ",
    "Muddle the Mixture -> ",
    "Merchant Scroll -> ",
    "Spellseeker ETB -> ",
    "Transmute ",
    "Reshape X=",
    "Whir X=",
    "Tezzeret -3 -> ",
    "Saga III ",
    "Repurposing Bay ",
    "Scour tutors ",
    "Urza spin -> ",
)


def trace_lines(state) -> Tuple[str, ...]:
    out = []
    for entry in getattr(state, "trace", ()):
        out.extend(str(entry).splitlines())
    return tuple(out)


def new_trace_lines(before, after) -> Tuple[str, ...]:
    """Return newly appended trace lines, including append_trace_detail edits."""
    old = trace_lines(before)
    new = trace_lines(after)
    common = 0
    limit = min(len(old), len(new))
    while common < limit and old[common] == new[common]:
        common += 1
    return new[common:]


def _top_visible(state) -> bool:
    return bool(
        getattr(state, "chip_attached", False)
        or (
            int(getattr(state, "ftt_level", 1)) >= 2
            and bool(getattr(state, "spell_cast_this_turn", False))
        )
    )


def _card_universe(before, after) -> Tuple[str, ...]:
    cards = set()
    for state in (before, after):
        cards.update(str(c) for c in getattr(state, "library", ()))
        cards.update(str(c) for c in getattr(state, "hand", ()))
        cards.update(str(c) for c in getattr(state, "graveyard", ()))
        cards.update(str(c) for c in getattr(state, "exile", ()))
        cards.update(str(getattr(p, "name", "")) for p in getattr(state, "battlefield", ()))
    cards.discard("")
    return tuple(sorted(cards, key=lambda value: (-len(value), value)))


def _parse_card_sequence(text: str, count: int, candidates: Sequence[str]) -> Tuple[str, ...]:
    """Parse comma-separated card names even when a card name itself has commas."""
    text = text.strip()

    @lru_cache(maxsize=None)
    def solve(pos: int, remaining: int):
        if remaining == 0:
            return () if pos == len(text) else None
        for card in candidates:
            if not text.startswith(card, pos):
                continue
            end = pos + len(card)
            if remaining == 1:
                if end == len(text):
                    return (card,)
                continue
            if not text.startswith(", ", end):
                continue
            tail = solve(end + 2, remaining - 1)
            if tail is not None:
                return (card,) + tail
        return None

    result = solve(0, int(count))
    if result is None:
        raise InformationPropagationError(
            f"could not parse {count} observed card(s) from trace text {text!r}"
        )
    return result


def _action_shuffled(lines: Iterable[str]) -> bool:
    for raw in lines:
        line = raw.strip()
        lower = line.lower()
        if "shuffle" in lower:
            return True
        if line.startswith(_SHUFFLE_PREFIXES):
            return True
    return False


def _trim_known_top(
    known_top: Sequence[str], before_library: Sequence[str], after_library: Sequence[str]
) -> Tuple[str, ...]:
    """Carry forward the largest still-valid suffix after known-prefix consumption."""
    known = tuple(known_top)
    before = tuple(before_library)
    after = tuple(after_library)
    if not known:
        return ()
    if before[: len(known)] != known:
        raise InformationPropagationError(
            f"incoming known_top {known!r} is not a prefix of concrete library"
        )
    for consumed in range(len(known) + 1):
        suffix = known[consumed:]
        if after[: len(suffix)] == suffix:
            return suffix
    return ()


def _trim_known_bottom(known_bottom: Sequence[str], after_library: Sequence[str]) -> Tuple[str, ...]:
    """Retain the longest known-bottom suffix still compatible with the library."""
    known = tuple(known_bottom)
    after = tuple(after_library)
    if not known:
        return ()
    # Prefer the full known suffix; if cards have been removed from the library,
    # progressively drop the oldest/topmost known-bottom facts until compatible.
    for dropped in range(len(known) + 1):
        suffix = known[dropped:]
        if after[len(after) - len(suffix) :] == suffix if suffix else True:
            return suffix
    return ()


def _apply_scry_event(
    info: InformationState,
    seen: Sequence[str],
    state_for_priority,
) -> InformationState:
    # Mirror the validated Oracle's deterministic scry choice exactly.  In the
    # future policy engine this will instead be the policy's explicit scry action.
    seen = tuple(seen)
    kept = tuple(
        sorted(
            [card for card in seen if solver.card_priority(state_for_priority, card) >= 45],
            key=lambda card: -solver.card_priority(state_for_priority, card),
        )
    )
    # Deliberately mirrors current apply_scry semantics, including duplicate-name
    # behavior. Commander is singleton except basic Islands, so this is stable.
    bottom = tuple(card for card in seen if card not in kept)
    old_suffix = info.known_top[len(seen) :] if len(info.known_top) > len(seen) else ()
    return replace(
        info,
        known_top=kept + tuple(old_suffix),
        known_bottom=tuple(info.known_bottom) + bottom,
    )


def _reveal_continuous_top(info: InformationState, state) -> InformationState:
    library = tuple(getattr(state, "library", ()))
    if not library or not _top_visible(state):
        return info
    top = str(library[0])
    if info.known_top and info.known_top[0] == top:
        return info
    return replace(info, known_top=(top,))


def validate_information_against_state(info: InformationState, state) -> None:
    library = tuple(str(c) for c in getattr(state, "library", ()))
    if tuple(info.known_top) != library[: len(info.known_top)]:
        raise InformationPropagationError(
            f"known_top {info.known_top!r} contradicts library prefix {library[:len(info.known_top)]!r}"
        )
    if info.known_bottom:
        suffix = library[len(library) - len(info.known_bottom) :]
        if tuple(info.known_bottom) != suffix:
            raise InformationPropagationError(
                f"known_bottom {info.known_bottom!r} contradicts library suffix {suffix!r}"
            )
    remaining = Counter(library)
    for card, count in info.known_library_counts:
        if count < 0:
            raise InformationPropagationError(f"negative known count for {card!r}")
        if count > remaining.get(card, 0):
            raise InformationPropagationError(
                f"known count {card!r}={count} exceeds concrete remaining count {remaining.get(card, 0)}"
            )


def initial_information(state) -> InformationState:
    info = _reveal_continuous_top(InformationState(), state)
    validate_information_against_state(info, state)
    return info


def propagate_information(before, after, prior: InformationState) -> InformationState:
    """Propagate legal hidden-zone knowledge across one concrete solver action.

    The function is pure and does not mutate either State.  It understands bundled
    Oracle macro transitions (for example Bay shuffle followed by Witching Well
    scry) by applying shuffle invalidation before post-shuffle observation events.
    """
    validate_information_against_state(prior, before)
    lines = new_trace_lines(before, after)
    shuffled = _action_shuffled(lines)
    has_scry = any(_SCRY_RE.search(line.strip()) for line in lines)

    if shuffled:
        info = prior.after_shuffle()
    else:
        # A scry moves newly-bottomed cards *below* an already-known bottom suffix.
        # Therefore the old suffix may no longer be the physical end of the final
        # library during this intermediate step. Preserve it through the generic
        # transition; _apply_scry_event appends each newly bottomed card afterward.
        # Non-scry transitions still use the strict suffix trimmer.
        carried_bottom = (
            tuple(prior.known_bottom)
            if has_scry
            else _trim_known_bottom(
                prior.known_bottom, getattr(after, "library", ())
            )
        )
        info = replace(
            prior,
            known_top=_trim_known_top(
                prior.known_top,
                getattr(before, "library", ()),
                getattr(after, "library", ()),
            ),
            known_bottom=carried_bottom,
        )

    universe = _card_universe(before, after)

    # Mystical Tutor is a shuffle followed by explicit known-top placement.
    mystical = next((line for line in lines if line.startswith(_MYSTICAL_PREFIX)), None)
    if mystical is not None:
        target = mystical[len(_MYSTICAL_PREFIX) :].strip()
        info = replace(info, known_top=(target,), known_bottom=())

    # Sensei's Divining Top reorder reveals/reorders the top up to three cards.
    if any(line.strip() == "Top reorder" for line in lines):
        n = min(3, len(getattr(after, "library", ())))
        old_suffix = prior.known_top[n:] if not shuffled and len(prior.known_top) > n else ()
        info = replace(
            info,
            known_top=tuple(getattr(after, "library", ())[:n]) + tuple(old_suffix),
        )

    # Top's draw ability places the physical Top card on top after the draw.  If
    # we previously knew deeper cards, they remain remembered immediately below.
    if any(line.startswith("Sensei's Divining Top -> draw:") for line in lines):
        remembered = prior.known_top[1:] if prior.known_top else ()
        info = replace(info, known_top=("Sensei's Divining Top",) + tuple(remembered))

    # Scry traces include exactly the cards observed. Multiple Assistant triggers
    # can occur in one macro transition; process them in trace order.
    for line in lines:
        match = _SCRY_RE.search(line.strip())
        if not match:
            continue
        n = int(match.group(1))
        seen = _parse_card_sequence(match.group(2), n, universe)
        info = _apply_scry_event(info, seen, after)

    # Clamp stale explicit count facts after publicly observed cards leave the
    # library. No current Oracle action creates these facts, but this preserves a
    # safe invariant for future count-observation effects.
    remaining = Counter(str(c) for c in getattr(after, "library", ()))
    if info.known_library_counts:
        info = replace(
            info,
            known_library_counts=tuple(
                sorted((card, min(int(count), remaining.get(card, 0))) for card, count in info.known_library_counts)
            ),
        )

    # Chip/FTT reveal the current top continuously after all other action effects.
    info = _reveal_continuous_top(info, after)
    validate_information_against_state(info, after)
    return info
