#!/usr/bin/env python3
"""Small information-safe heuristic layer for Urza exile permissions.

The typed rules layer is intentionally independent of policy.  Now that Urza can
legally use lands, artifacts, proactive spells, cantrips, tutors/search spells, and
X=0 Reshape/Whir from exile, the original base policy's catch-all -20 score would
silently strand most of those legal lines.  This extension gives those public action
families conservative deterministic scores without consulting true state or hidden
library order.

Two principles keep this a base-policy heuristic rather than a new oracle:
- all inputs come from RuntimePolicyView plus the public ActionIntent parameters;
- priority-time Urza actions are normally deferred until the current stack clears,
  because in the goldfish model the same action remains available in main phase and
  needlessly growing the stack is not itself valuable.
"""

from __future__ import annotations

from non_oracle_base_policy import DeterministicBasePolicy

_INSTALLED = False
_ORIGINAL_URZA_PERMISSION_SCORE = DeterministicBasePolicy._urza_permission_score
_ORIGINAL_MAIN_ACTION_SCORE = DeterministicBasePolicy._main_action_score


def _has_public_bauble(observation) -> bool:
    return any(
        str(getattr(perm, "name", "")) == "Vexing Bauble"
        for perm in observation.base.battlefield
    )


def _free_spell_will_be_countered(observation, action) -> bool:
    params = dict(action.parameters)
    if "will_be_countered_by_own_bauble" in params:
        # Reshape can sacrifice the only Bauble as an additional cost, so an
        # explicit rules-side value must override the pre-cast public battlefield.
        return bool(params["will_be_countered_by_own_bauble"])
    use = str(params.get("use", ""))
    if not use.startswith("cast_"):
        return False
    if int(params.get("mana_spent", 0)) != 0:
        return False
    return _has_public_bauble(observation)


def _sacrifice_adjustment(policy, observation, action) -> float:
    params = dict(action.parameters)
    sacrificed = str(params.get("sacrifice_name", ""))
    if not sacrificed:
        return 0.0
    score = -1.25 * policy.visible_card_score(sacrificed, observation)
    if sacrificed == "Prized Statue":
        score += 4.0
    if sacrificed in {"Clue", "Treasure"}:
        score += 3.0
    if sacrificed == "Vexing Bauble" and not bool(params.get("will_be_countered_by_own_bauble", False)):
        score += 2.0
    return score


def _patched_urza_permission_score(self, observation, action) -> float:
    params = dict(action.parameters)
    use = str(params.get("use", ""))
    card = str(params.get("card", ""))

    if _free_spell_will_be_countered(observation, action):
        # A goldfish policy should prefer ending the turn (-100) to deliberately
        # throwing away a spell into its own Bauble for no modeled benefit.
        return -200.0

    # In this opponent-free rollout, priority-time Urza spells can normally wait
    # for the current object to resolve and then be sequenced in main phase.  Keep
    # them rules-legal but prefer a clean stack unless later policy work identifies
    # a concrete stack-sensitive reason to act now.
    if bool(params.get("priority", False)):
        return -5.0

    if use in {"play_land", "cast_artifact"}:
        return _ORIGINAL_URZA_PERMISSION_SCORE(self, observation, action)

    if use == "cast_gitaxian_probe":
        return 40.0

    if use == "cast_proactive_nonartifact":
        return 30.0 + self.visible_card_score(card, observation)

    if use == "cast_simple_tutor":
        return 35.0 + self.visible_card_score(card, observation)

    if use == "cast_transmute_artifact":
        return 35.0

    if use == "cast_scour_for_scrap":
        mode = str(params.get("mode", ""))
        grave = str(params.get("graveyard_target", ""))
        mode_bonus = {"both": 4.0, "library": 2.5, "graveyard": 0.5}.get(mode, 0.0)
        return 32.0 + mode_bonus + 0.25 * self.visible_card_score(grave, observation)

    if use == "cast_reshape_x0":
        # X=0 is real but deliberately valued far below a normal X=2/3 tutor.
        # The only hidden-zone assumption here is none: the score does not inspect
        # which zero-mana artifact remains in the library.
        return 18.0 + _sacrifice_adjustment(self, observation, action)

    if use == "cast_whir_x0":
        return 22.0

    return _ORIGINAL_URZA_PERMISSION_SCORE(self, observation, action)


def _patched_main_action_score(self, observation, action) -> float:
    params = dict(action.parameters)
    if action.kind == "main_activate_urza_spin" and bool(params.get("priority", False)):
        # Same reasoning as permission casts: in a goldfish, do not spend five mana
        # above our own unresolved spell merely because the rules permit it.
        return -5.0
    return _ORIGINAL_MAIN_ACTION_SCORE(self, observation, action)


def install_urza_policy_extension() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    DeterministicBasePolicy._urza_permission_score = _patched_urza_permission_score
    DeterministicBasePolicy._main_action_score = _patched_main_action_score
    _INSTALLED = True
