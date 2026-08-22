#!/usr/bin/env python3
"""Episode-level interaction/protection analytics for Urza simulations.

This module is intentionally observational: it does not execute Magic rules and
it does not add history fields to the solver's transition state. A rollout or
search can feed states to :class:`InteractionEpisodeTracker` and receive a rich
summary describing interaction seen over the episode and protection actually
available in the terminal/winning position.

The distinction matters for DP/Monte Carlo:
- historical analytics (what was seen, and when) stay outside the Markov key;
- current hand/battlefield/mana remain the source of future legality;
- the same trajectory can later be scored for win speed, interaction exposure,
  protected-win rate, or deck-swap comparisons without rerunning the game.

"Protected line" here is deliberately a *capability* statistic, not a claim that
a real opponent is unable to interact. Opponent holdings/priority/targets are a
separate future model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Tuple

COUNTERSPELL = "counterspell"
BROAD_COUNTER = "broad_counter"
NARROW_COUNTER = "narrow_counter"
FREE_COUNTER_OWN_TURN = "free_counter_own_turn"
CONDITIONAL_FREE_COUNTER = "conditional_free_counter"
BOUNCE = "bounce"
PROACTIVE_PROTECTION = "proactive_protection"
FREE_SPELL_LOCK = "free_spell_lock"
PROACTIVE_DISRUPTION = "proactive_disruption"
STAX_HATE = "stax_hate"

# Analytical taxonomy only; this does not alter solver card types or rules.
INTERACTION_CLASSES: Mapping[str, Tuple[str, ...]] = {
    "An Offer You Can't Refuse": (COUNTERSPELL, NARROW_COUNTER),
    "Fierce Guardianship": (COUNTERSPELL, BROAD_COUNTER, FREE_COUNTER_OWN_TURN),
    "Flusterstorm": (COUNTERSPELL, NARROW_COUNTER),
    "Force of Negation": (COUNTERSPELL, NARROW_COUNTER, CONDITIONAL_FREE_COUNTER),
    "Force of Will": (COUNTERSPELL, BROAD_COUNTER, FREE_COUNTER_OWN_TURN),
    "Mana Drain": (COUNTERSPELL, BROAD_COUNTER),
    "Mental Misstep": (COUNTERSPELL, NARROW_COUNTER),
    "Mindbreak Trap": (COUNTERSPELL, BROAD_COUNTER, CONDITIONAL_FREE_COUNTER),
    "Pact of Negation": (COUNTERSPELL, BROAD_COUNTER, FREE_COUNTER_OWN_TURN),
    "Swan Song": (COUNTERSPELL, NARROW_COUNTER),
    "Chain of Vapor": (BOUNCE,),
    "Otawara, Soaring City": (BOUNCE,),
    "Aether Spellbomb": (BOUNCE,),
    "Banishing Knack": (BOUNCE,),
    "Retraction Helix": (BOUNCE,),
    "Sink into Stupor": (BOUNCE,),
    "Defense Grid": (PROACTIVE_PROTECTION,),
    "Vexing Bauble": (FREE_SPELL_LOCK, PROACTIVE_DISRUPTION),
    "Disruptor Flute": (PROACTIVE_DISRUPTION,),
    "Pithing Needle": (STAX_HATE,),
    "Grafdigger's Cage": (STAX_HATE,),
}

# Own-turn normal mana costs used only for "could this counter be held up now?".
# Mental Misstep may use 2 life when Bauble is absent; with Bauble online it must
# spend U to avoid Bauble's no-mana-spent trigger. Pact has no paid fallback.
COUNTER_MANA_COSTS: Mapping[str, Tuple[int, int]] = {
    "An Offer You Can't Refuse": (0, 1),
    "Fierce Guardianship": (2, 1),
    "Flusterstorm": (0, 1),
    "Force of Negation": (1, 2),
    "Force of Will": (3, 2),
    "Mana Drain": (0, 2),
    "Mental Misstep": (0, 1),
    "Mindbreak Trap": (2, 2),
    "Pact of Negation": (99, 99),
    "Swan Song": (0, 1),
}


def interaction_classes(card: str) -> Tuple[str, ...]:
    return INTERACTION_CLASSES.get(card, ())


def is_interaction_card(card: str) -> bool:
    return card in INTERACTION_CLASSES


def _permanent_names(state: Any) -> Tuple[str, ...]:
    return tuple(str(getattr(p, "name", "")) for p in getattr(state, "battlefield", ()))


def _can_pay_pool(state: Any, generic: int, blue_required: int) -> bool:
    blue = int(getattr(state, "blue", 0))
    colorless = int(getattr(state, "colorless", 0))
    if blue < blue_required:
        return False
    return (blue - blue_required) + colorless >= generic


def _force_pitch_available(
    hand: Tuple[str, ...],
    blue_card_predicate: Optional[Callable[[str], bool]],
) -> bool:
    if blue_card_predicate is None:
        return False
    return any(card != "Force of Will" and blue_card_predicate(card) for card in hand)


def _bauble_online(state: Any) -> bool:
    return "Vexing Bauble" in _permanent_names(state)


def castable_counterspells(
    state: Any,
    *,
    blue_card_predicate: Optional[Callable[[str], bool]] = None,
) -> Tuple[str, ...]:
    """Counterspells representable as live on our own turn.

    Conservative choices:
    - Force of Negation's alternate cost is not live on our own turn.
    - Mindbreak Trap's alternate cost is not assumed without opponent spell-count
      state, so it must be hard-cast here.
    - Force of Will is free only when another blue card is known pitchable.
    - Mental Misstep may use life only while Vexing Bauble is absent.
    - Vexing Bauble prevents us from treating no-mana-spent counters as effective;
      paid normal costs may still qualify. A future action-level evaluator can
      model sacrificing Bauble before deploying free protection.
    """
    hand = tuple(getattr(state, "hand", ()))
    commander_controlled = bool(getattr(state, "urza", False))
    bauble = _bauble_online(state)
    live = []
    for card in sorted(set(hand) & set(COUNTER_MANA_COSTS)):
        if not bauble:
            if card == "Fierce Guardianship" and commander_controlled:
                live.append(card)
                continue
            if card == "Force of Will" and _force_pitch_available(hand, blue_card_predicate):
                live.append(card)
                continue
            if card == "Pact of Negation":
                live.append(card)
                continue
            if card == "Mental Misstep":
                live.append(card)
                continue
        generic, blue_required = COUNTER_MANA_COSTS[card]
        if _can_pay_pool(state, generic, blue_required):
            live.append(card)
    return tuple(live)


def zero_mana_counterspells(
    state: Any,
    *,
    blue_card_predicate: Optional[Callable[[str], bool]] = None,
) -> Tuple[str, ...]:
    """Own-turn counters needing no currently floating mana and not Bauble-blanked."""
    if _bauble_online(state):
        return ()
    hand = tuple(getattr(state, "hand", ()))
    live = set(castable_counterspells(state, blue_card_predicate=blue_card_predicate))
    zero = set()
    if "Pact of Negation" in live:
        zero.add("Pact of Negation")
    if "Mental Misstep" in live:
        zero.add("Mental Misstep")
    if "Fierce Guardianship" in live and bool(getattr(state, "urza", False)):
        zero.add("Fierce Guardianship")
    if "Force of Will" in live and _force_pitch_available(hand, blue_card_predicate):
        zero.add("Force of Will")
    return tuple(sorted(zero))


def _class_counts(cards: Iterable[str]) -> Tuple[Tuple[str, int], ...]:
    counts: Dict[str, int] = {}
    for card in set(cards):
        for cls in interaction_classes(card):
            counts[cls] = counts.get(cls, 0) + 1
    return tuple(sorted(counts.items()))


@dataclass(frozen=True)
class InteractionSnapshot:
    turn: int
    seen_cards: Tuple[str, ...]
    seen_class_counts: Tuple[Tuple[str, int], ...]
    hand_interaction_cards: Tuple[str, ...]
    battlefield_interaction_cards: Tuple[str, ...]
    counterspells_in_hand: Tuple[str, ...]
    castable_counterspells: Tuple[str, ...]
    broad_castable_counterspells: Tuple[str, ...]
    zero_mana_counterspells: Tuple[str, ...]
    proactive_protection_online: Tuple[str, ...]
    free_spell_locks_online: Tuple[str, ...]
    proactive_disruption_online: Tuple[str, ...]
    protection_piece_count_available: int
    protected_line_capable: bool

    @property
    def seen_count(self) -> int:
        return len(self.seen_cards)

    @property
    def counterspell_available(self) -> bool:
        return bool(self.castable_counterspells)

    @property
    def broad_counter_available(self) -> bool:
        return bool(self.broad_castable_counterspells)

    @property
    def zero_mana_counter_available(self) -> bool:
        return bool(self.zero_mana_counterspells)

    @property
    def defense_grid_online(self) -> bool:
        return "Defense Grid" in self.proactive_protection_online

    @property
    def vexing_bauble_online(self) -> bool:
        return "Vexing Bauble" in self.free_spell_locks_online


def interaction_snapshot(
    state: Any,
    *,
    blue_card_predicate: Optional[Callable[[str], bool]] = None,
) -> InteractionSnapshot:
    hand = tuple(getattr(state, "hand", ()))
    battlefield_names = _permanent_names(state)

    # Legacy Oracle interaction_seen remembers earlier exposure. Current hand /
    # battlefield are unioned in as a safety net and for future non-Oracle states.
    seen = set(getattr(state, "interaction_seen", ()))
    seen.update(card for card in hand if is_interaction_card(card))
    seen.update(card for card in battlefield_names if is_interaction_card(card))

    hand_interaction = tuple(sorted(card for card in hand if is_interaction_card(card)))
    battlefield_interaction = tuple(sorted(card for card in battlefield_names if is_interaction_card(card)))
    counters_in_hand = tuple(sorted(card for card in hand if COUNTERSPELL in interaction_classes(card)))
    castable = castable_counterspells(state, blue_card_predicate=blue_card_predicate)
    broad = tuple(sorted(card for card in castable if BROAD_COUNTER in interaction_classes(card)))
    zero = zero_mana_counterspells(state, blue_card_predicate=blue_card_predicate)

    proactive = tuple(sorted(
        card for card in battlefield_names
        if PROACTIVE_PROTECTION in interaction_classes(card)
    ))
    free_locks = tuple(sorted(
        card for card in battlefield_names
        if FREE_SPELL_LOCK in interaction_classes(card)
    ))
    disruption = tuple(sorted(
        card for card in battlefield_names
        if PROACTIVE_DISRUPTION in interaction_classes(card)
    ))

    # Piece count is not an "independent layer" count: two one-mana counters with
    # only U floating are two present options, not necessarily two stack exchanges.
    protection_piece_count = len(castable) + len(proactive) + len(free_locks)

    return InteractionSnapshot(
        turn=int(getattr(state, "turn", 0)),
        seen_cards=tuple(sorted(seen)),
        seen_class_counts=_class_counts(seen),
        hand_interaction_cards=hand_interaction,
        battlefield_interaction_cards=battlefield_interaction,
        counterspells_in_hand=counters_in_hand,
        castable_counterspells=castable,
        broad_castable_counterspells=broad,
        zero_mana_counterspells=zero,
        proactive_protection_online=proactive,
        free_spell_locks_online=free_locks,
        proactive_disruption_online=disruption,
        protection_piece_count_available=protection_piece_count,
        protected_line_capable=bool(castable or proactive or free_locks),
    )


@dataclass(frozen=True)
class InteractionEpisodeSummary:
    seen_cards: Tuple[str, ...]
    seen_class_counts: Tuple[Tuple[str, int], ...]
    first_seen_turn_by_card: Tuple[Tuple[str, int], ...]
    first_seen_turn_by_class: Tuple[Tuple[str, int], ...]
    terminal_snapshot: InteractionSnapshot
    won: bool = False
    win_turn: Optional[int] = None

    @property
    def seen_count(self) -> int:
        return len(self.seen_cards)

    @property
    def protected_at_win(self) -> bool:
        return bool(self.won and self.terminal_snapshot.protected_line_capable)

    @property
    def counterspell_at_win(self) -> bool:
        return bool(self.won and self.terminal_snapshot.counterspell_available)

    @property
    def broad_counter_at_win(self) -> bool:
        return bool(self.won and self.terminal_snapshot.broad_counter_available)

    @property
    def zero_mana_counter_at_win(self) -> bool:
        return bool(self.won and self.terminal_snapshot.zero_mana_counter_available)

    @property
    def defense_grid_at_win(self) -> bool:
        return bool(self.won and self.terminal_snapshot.defense_grid_online)

    @property
    def free_spell_lock_at_win(self) -> bool:
        return bool(self.won and self.terminal_snapshot.free_spell_locks_online)


@dataclass
class InteractionEpisodeTracker:
    """External analytics accumulator; never part of a DP/transposition key.

    For accurate first-seen turns, call ``observe`` as the rollout advances rather
    than constructing the tracker only from a terminal state.
    """

    blue_card_predicate: Optional[Callable[[str], bool]] = None
    _seen_cards: set[str] = field(default_factory=set, init=False, repr=False)
    _first_seen_turn_by_card: Dict[str, int] = field(default_factory=dict, init=False, repr=False)
    _first_seen_turn_by_class: Dict[str, int] = field(default_factory=dict, init=False, repr=False)
    _last_snapshot: Optional[InteractionSnapshot] = field(default=None, init=False, repr=False)

    def observe(self, state: Any) -> InteractionSnapshot:
        snap = interaction_snapshot(state, blue_card_predicate=self.blue_card_predicate)
        self._last_snapshot = snap
        for card in snap.seen_cards:
            self._seen_cards.add(card)
            self._first_seen_turn_by_card.setdefault(card, snap.turn)
            for cls in interaction_classes(card):
                previous = self._first_seen_turn_by_class.get(cls)
                if previous is None or snap.turn < previous:
                    self._first_seen_turn_by_class[cls] = snap.turn
        return snap

    def finalize(
        self,
        state: Any,
        *,
        won: Optional[bool] = None,
        win_turn: Optional[int] = None,
    ) -> InteractionEpisodeSummary:
        terminal = self.observe(state)
        actual_won = bool(getattr(state, "won", False)) if won is None else bool(won)
        actual_win_turn = (
            int(getattr(state, "turn", 0)) if actual_won and win_turn is None else win_turn
        )
        if not actual_won:
            actual_win_turn = None
        return InteractionEpisodeSummary(
            seen_cards=tuple(sorted(self._seen_cards)),
            seen_class_counts=_class_counts(self._seen_cards),
            first_seen_turn_by_card=tuple(sorted(self._first_seen_turn_by_card.items())),
            first_seen_turn_by_class=tuple(sorted(self._first_seen_turn_by_class.items())),
            terminal_snapshot=terminal,
            won=actual_won,
            win_turn=actual_win_turn,
        )
