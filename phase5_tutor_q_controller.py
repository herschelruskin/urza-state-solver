#!/usr/bin/env python3
"""Selective information-safe Q improvement for tutor/search decisions.

This controller deliberately sits *outside* the policy/rules boundary.  The leaf
policy remains rollout-v6 and sees only RuntimePolicyView + ActionIntent.  The
controller may use the strategic library belief to sample hidden worlds and compare
Q(s,a), then returns one of the already-legal current ActionIntents.

Scope is intentionally narrow:
  * all contingent tutor/search choices are Q-evaluated;
  * main-phase tutor timing is Q-evaluated when v6 wants to tutor, or when v6
    wants to end the turn while a tutor is currently castable;
  * ordinary sequencing remains rollout-v6 for now.

A one-world screen is used only to shortlist large target sets.  Confirmed choices
use a larger common-random-number budget.  Q must be *strictly* better than the v6
choice to override it; ties preserve v6.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

from decision_observation import ActionIntent
from non_oracle_episode import (
    EpisodeStep,
    NonOracleEpisodeResult,
    _blocked_reason,
    _checked_runtime,
    episode_cycle_key,
)
from non_oracle_rules_adapter_v2 import apply_main_action, rules_decision_request
from phase5_monte_carlo import (
    Phase5DecisionEvaluation,
    Phase5MonteCarloDecisionEvaluator,
)
from phase5_rollout_policy_v6 import (
    DeterministicRolloutPolicyV6,
    PHASE5_ROLLOUT_POLICY_V6,
)

PHASE5_TUTOR_Q_CONTROLLER_VERSION = "urza-phase5-tutor-q-controller-v1"

MAIN_TUTOR_KINDS = frozenset({
    "main_use_simple_tutor",
    "main_use_transmute_artifact",
    "main_use_x_artifact_tutor",
    "main_activate_repurposing_bay",
    "main_cast_scour_for_scrap",
    "main_activate_tezzeret_minus3",
})

CONTINGENT_TUTOR_KINDS = frozenset({
    "choose_tutor_target",
    "transmute_choose_sacrifice",
    "transmute_choose_target",
    "transmute_pay_difference",
    "x_artifact_search_target",
    "remaining_search_target",
})

END_TURN_KIND = "main_end_turn"


@dataclass(frozen=True)
class TutorQDecision:
    turn: int
    decision_id: str
    decision_stage: str
    used_q: bool
    reason: str
    v6_action: str
    chosen_action: str
    candidate_count: int
    confirmed_count: int
    screen_best: str = ""
    q_best: str = ""


class Phase5TutorQController:
    """One-step tutor/search policy improvement with rollout-v6 leaves."""

    def __init__(
        self,
        *,
        screen_rollouts: int = 1,
        confirm_rollouts: int = 4,
        shortlist: int = 5,
        mc_root_seed: int = 20260826,
        horizon: int = 6,
        continuation_policy: DeterministicRolloutPolicyV6 | None = None,
        max_episode_steps: int = 512,
    ):
        if shortlist < 2:
            raise ValueError("shortlist must be >= 2")
        self.policy = continuation_policy or DeterministicRolloutPolicyV6(
            policy_id=PHASE5_ROLLOUT_POLICY_V6
        )
        self.horizon = int(horizon)
        self.shortlist = int(shortlist)
        self.screen = Phase5MonteCarloDecisionEvaluator(
            rollout_count=int(screen_rollouts),
            mc_root_seed=int(mc_root_seed),
            horizon=self.horizon,
            continuation_policy=self.policy,
            max_episode_steps=max_episode_steps,
            strict_terminal_reasons=True,
        )
        self.confirm = Phase5MonteCarloDecisionEvaluator(
            rollout_count=int(confirm_rollouts),
            mc_root_seed=int(mc_root_seed),
            horizon=self.horizon,
            continuation_policy=self.policy,
            max_episode_steps=max_episode_steps,
            strict_terminal_reasons=True,
        )
        self.decisions = []

    @staticmethod
    def _unique(actions: Iterable[ActionIntent]) -> Tuple[ActionIntent, ...]:
        rows: Dict[Tuple[object, ...], ActionIntent] = {}
        for action in sorted(actions, key=lambda a: a.action_id):
            rows.setdefault(action.strategic_key(), action)
        return tuple(rows[key] for key in sorted(rows, key=repr))

    def _v6_choice(self, request, fresh_actions):
        return self.policy.choose(
            request.observation,
            fresh_actions,
            request.context,
        )

    def _best_non_tutor_v6(self, request, fresh_actions):
        rows = [
            action for action in fresh_actions
            if action.kind not in MAIN_TUTOR_KINDS
            and action.kind != END_TURN_KIND
        ]
        if not rows:
            return None
        return max(
            rows,
            key=lambda action: (
                self.policy.action_score(
                    request.observation, action, request.context
                ),
                repr(action.strategic_key()),
            ),
        )

    def _candidate_actions(self, request, fresh_actions, v6):
        kinds = {action.kind for action in fresh_actions}

        # Once a tutor/search has committed, this is the actual contingent
        # decision. Compare the complete legal visible choice set.
        if kinds & CONTINGENT_TUTOR_KINDS:
            candidates = list(fresh_actions)

            # Strategic invariant from the human pilot: once Transmute has chosen
            # a target and at least one legal payment plan exists, do not
            # voluntarily put that target into the graveyard. The decline action
            # remains in the rules engine for Magic correctness.
            if kinds == {"transmute_pay_difference"}:
                pay = [
                    action for action in candidates
                    if not action.label.startswith("Decline ")
                ]
                if pay:
                    candidates = pay
            return self._unique(candidates), "contingent_tutor_choice"

        tutors = [
            action for action in fresh_actions
            if action.kind in MAIN_TUTOR_KINDS
        ]
        if not tutors:
            return (), ""

        # Only widen main-phase search where the baseline is itself considering
        # the tutor decision, or where it would otherwise pass the turn with a
        # tutor available. Other sequencing stays with v6 in this first slice.
        if v6.kind not in MAIN_TUTOR_KINDS and v6.kind != END_TURN_KIND:
            return (), ""

        candidates = list(tutors)
        candidates.append(v6)

        for action in fresh_actions:
            if action.kind == END_TURN_KIND:
                candidates.append(action)
                break

        alternate = self._best_non_tutor_v6(request, fresh_actions)
        if alternate is not None:
            candidates.append(alternate)

        return self._unique(candidates), "tutor_timing"

    @staticmethod
    def _estimate_by_key(
        evaluation: Phase5DecisionEvaluation,
    ):
        return {
            estimate.action.strategic_key(): estimate
            for estimate in evaluation.estimates
        }

    def choose(self, runtime, request, fresh_actions) -> ActionIntent:
        v6 = self._v6_choice(request, fresh_actions)
        candidates, reason = self._candidate_actions(
            request, fresh_actions, v6
        )
        if len(candidates) <= 1:
            self.decisions.append(TutorQDecision(
                turn=int(runtime.true_state.turn),
                decision_id=request.context.decision_id,
                decision_stage=request.context.decision_stage,
                used_q=False,
                reason=reason or "outside_tutor_q_scope",
                v6_action=v6.label,
                chosen_action=v6.label,
                candidate_count=len(candidates),
                confirmed_count=0,
            ))
            return v6

        # Small choice sets go straight to confirmation. Large search target sets
        # receive a cheap common-world screen, then confirm a bounded shortlist.
        screen_eval = None
        if len(candidates) <= self.shortlist:
            confirmed = candidates
        else:
            screen_eval = self.screen.evaluate(
                runtime,
                candidate_actions=candidates,
            )
            ranked = list(screen_eval.estimates[: self.shortlist])
            by_key = {
                estimate.action.strategic_key(): estimate.action
                for estimate in ranked
            }
            # Always retain the v6 action as a control when it is among the legal
            # strategic candidates, even if the one-world screen dislikes it.
            candidate_keys = {
                action.strategic_key() for action in candidates
            }
            if v6.strategic_key() in candidate_keys:
                current = next(
                    action for action in candidates
                    if action.strategic_key() == v6.strategic_key()
                )
                by_key.setdefault(current.strategic_key(), current)
            confirmed = tuple(
                by_key[key] for key in sorted(by_key, key=repr)
            )

        confirm_eval = self.confirm.evaluate(
            runtime,
            candidate_actions=confirmed,
        )
        estimates = self._estimate_by_key(confirm_eval)
        q_best = confirm_eval.best_action

        # Preserve v6 on ties. If v6 was intentionally pruned (payable Transmute
        # decline), take the best confirmed legal strategic choice.
        chosen = q_best
        if v6.strategic_key() in estimates:
            base_value = estimates[v6.strategic_key()].value
            best_value = estimates[q_best.strategic_key()].value
            if best_value.comparison_key() <= base_value.comparison_key():
                chosen = next(
                    action for action in confirmed
                    if action.strategic_key() == v6.strategic_key()
                )

        self.decisions.append(TutorQDecision(
            turn=int(runtime.true_state.turn),
            decision_id=request.context.decision_id,
            decision_stage=request.context.decision_stage,
            used_q=True,
            reason=reason,
            v6_action=v6.label,
            chosen_action=chosen.label,
            candidate_count=len(candidates),
            confirmed_count=len(confirmed),
            screen_best=(
                screen_eval.best_action.label
                if screen_eval is not None else ""
            ),
            q_best=q_best.label,
        ))
        return chosen


def run_tutor_q_episode(
    runtime,
    *,
    controller: Phase5TutorQController,
    horizon: int = 6,
    max_steps: int = 512,
) -> NonOracleEpisodeResult:
    """Run one episode with Q improvement only at tutor/search decisions."""
    runtime = _checked_runtime(runtime)
    steps = []
    attempted_by_cycle_state = {}

    for sequence in range(max_steps):
        state = runtime.true_state
        if state.won:
            return NonOracleEpisodeResult(
                runtime, tuple(steps), horizon,
                int(state.turn), state.win_family, "win"
            )
        if state.turn > horizon:
            return NonOracleEpisodeResult(
                runtime, tuple(steps), horizon, None, "", "horizon"
            )

        request = rules_decision_request(
            runtime,
            horizon=horizon,
            policy_id=controller.policy.policy_id,
        )
        if not request.actions:
            return NonOracleEpisodeResult(
                runtime, tuple(steps), horizon, None, "",
                _blocked_reason(runtime, horizon),
            )

        cycle_key = episode_cycle_key(runtime)
        attempted = attempted_by_cycle_state.setdefault(cycle_key, set())
        fresh_actions = tuple(
            action for action in request.actions
            if action.strategic_key() not in attempted
        )
        if not fresh_actions:
            return NonOracleEpisodeResult(
                runtime, tuple(steps), horizon, None, "",
                "strategic_cycle_exhausted",
            )

        action = controller.choose(runtime, request, fresh_actions)
        attempted.add(action.strategic_key())
        before_turn = int(state.turn)
        before_window = runtime.window.kind
        observation_key = request.observation.key()

        runtime = _checked_runtime(apply_main_action(runtime, action))
        after = runtime.true_state
        steps.append(EpisodeStep(
            sequence=sequence,
            turn_before=before_turn,
            window_kind=before_window,
            observation_key=observation_key,
            action_id=action.action_id,
            action_kind=action.kind,
            action_label=action.label,
            action_strategic_key=action.strategic_key(),
            turn_after=int(after.turn),
            won_after=bool(after.won),
            win_family_after=str(after.win_family),
        ))

    return NonOracleEpisodeResult(
        runtime,
        tuple(steps),
        horizon,
        int(runtime.true_state.turn) if runtime.true_state.won else None,
        runtime.true_state.win_family if runtime.true_state.won else "",
        "step_limit",
    )
