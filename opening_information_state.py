#!/usr/bin/env python3
"""Pregame/opening hidden-zone knowledge for London mulligans.

The ordinary in-game propagation layer starts from a concrete State plus an
InformationState.  London mulligans create one important piece of legal hidden-zone
knowledge before turn one: the cards the player chose to put on the bottom of the
library, in the exact order used by the simulator.

This module seeds that knowledge explicitly.  It never infers a bottom suffix from
the concrete hidden library, because doing so would leak Oracle information.  The
caller must provide the cards actually chosen as London bottoms.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Tuple

from information_state_propagation import (
    InformationPropagationError,
    initial_information,
    validate_information_against_state,
)
from solver_architecture import InformationState


def london_bottom_tuple(bottom: Iterable[str]) -> Tuple[str, ...]:
    """Canonical player-known London bottom order, top-to-bottom within suffix."""
    return tuple(str(card) for card in bottom)


def seed_london_bottom_information(
    state,
    bottom: Iterable[str],
    *,
    base_information: InformationState | None = None,
) -> InformationState:
    """Return legal information immediately after London bottoming.

    ``state`` must already contain the post-London library produced by
    ``london_opening_zones``. ``bottom`` is the cards/order the player knowingly
    chose to place there.  An empty bottom is valid for keep-seven stages.

    The function validates that the supplied known bottom is actually the suffix
    of the concrete library, but it does not discover or extend the suffix from
    concrete hidden order.
    """
    known_bottom = london_bottom_tuple(bottom)
    info = initial_information(state) if base_information is None else base_information
    library = tuple(str(card) for card in getattr(state, "library", ()))

    if len(known_bottom) > len(library):
        raise InformationPropagationError(
            f"London bottom has {len(known_bottom)} cards but library has only {len(library)}"
        )
    if known_bottom:
        actual_suffix = library[-len(known_bottom) :]
        if actual_suffix != known_bottom:
            raise InformationPropagationError(
                "supplied London bottom does not match post-mulligan library suffix: "
                f"known={known_bottom!r} actual={actual_suffix!r}"
            )

    info = replace(info, known_bottom=known_bottom)
    validate_information_against_state(info, state)
    return info


def unknown_draw_pool_size(state, information: InformationState) -> int:
    """Number of library cards above the currently known bottom suffix.

    This is a convenience diagnostic, not a probability model.  Until a shuffle,
    cards in ``known_bottom`` are outside the unordered/unknown prefix and therefore
    cannot be drawn before that prefix is exhausted.
    """
    library_size = len(tuple(getattr(state, "library", ())))
    bottom_size = len(tuple(information.known_bottom))
    if bottom_size > library_size:
        raise InformationPropagationError(
            "known bottom is longer than the concrete library"
        )
    return library_size - bottom_size
