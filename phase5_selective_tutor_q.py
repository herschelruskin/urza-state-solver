#!/usr/bin/env python3
"""Selective information-safe Q policy improvement for tutor/search decisions.

This is intentionally *not* a new heuristic tutor table.  The frozen rollout-v6
policy remains the cheap continuation policy.  A rules-side controller invokes
belief-safe Monte Carlo only when v6 is about to commit to a tutor/search action or
when a tutor/search commitment is already asking for its target/sacrifice/X choice,
or when v6 would end the turn despite a currently castable tutor.

The controller:
1. screens all strategically distinct legal candidates with common hidden worlds;
2. confirms only the best few candidates plus v6's choice with a larger CRN budget;
3. overrides v6 only when the confirmed T1..T6 value is strictly better;
4. keeps v6 on exact value ties, avoiding arbitrary MC/tie-break policy drift.

Transmute's "pay the difference" decision is deliberately excluded.  The rules
retain the legal decline branch, while the rollout policy has a regression-enforced
strategic invariant to pay whenever the selected target is legally payable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from decision_observation import ActionIntent
from non_oracle_episode import (
    EpisodeStep,
    NonOracleEpisodeResult,
    _blocked_reason,
    _checked_runtime,
    episode_cycle_key,
)
from non_oracle_rules_adapter_v2 import apply_main_action, rules_decision_request
from non_oracle_runtime import NonOracleRuntimeState
from phase5_monte_carlo import (
    Phase5ActionEstimate,
    Phase5DecisionEvaluation,
    Phase5MonteCarloDecisionEvaluator,
    Phase5DecisionCache,
)
from phase5_rollout_policy_v6 import (
    DeterministicRolloutPolicyV6,
    PHASE5_ROLLOUT_POLICY_V6,
)

PHASE5_SELECTIVE_TUTOR_Q_VERSION="urza-phase5-selective-tutor-q-v1"

MAIN_TUTOR_KINDS=frozenset({
    "main_use_simple_tutor",
    "main_use_transmute_artifact",
    "main_use_x_artifact_tutor",
    "main_activate_repurposing_bay",
    "main_cast_scour_for_scrap",
    "main_activate_tezzeret_minus3",
})

PENDING_TUTOR_Q_KINDS=frozenset({
    "choose_tutor_target",
    "transmute_choose_sacrifice",
    "transmute_choose_target",
    "x_artifact_search_target",
    "remaining_search_target",
})

# Payment is a legal mechanical branch but not currently a learned strategic
# question: if the committed Transmute target is payable, v5/v6 must pay it.
TRANSMMUTE_PAYMENT_KIND="transmute_pay_difference"


@dataclass(frozen=True)
class TutorQDecision:
    sequence: int
    turn: int
    decision_id: str
    v6_action: str
    chosen_action: str
    overridden: bool
    screen_candidate_count: int
    confirm_candidate_count: int
    v6_value_key: Tuple[float, ...]
    chosen_value_key: Tuple[float, ...]


@dataclass(frozen=True)
class SelectiveTutorQEpisodeResult:
    episode: NonOracleEpisodeResult
    q_decisions: Tuple[TutorQDecision, ...]

    @property
    def win_turn(self):
        return self.episode.win_turn

    @property
    def win_family(self):
        return self.episode.win_family

    @property
    def won_by_horizon(self):
        return self.episode.won_by_horizon


def _representatives(actions):
    rows={}
    for action in sorted(actions,key=lambda a:a.action_id):
        rows.setdefault(action.strategic_key(),action)
    return tuple(rows[key] for key in sorted(rows,key=repr))


def _estimate_for(evaluation:Phase5DecisionEvaluation,action:ActionIntent):
    key=action.strategic_key()
    return next(
        estimate for estimate in evaluation.estimates
        if estimate.action.strategic_key()==key
    )


def _value_rank(estimate:Phase5ActionEstimate):
    return (
        estimate.value.comparison_key(),
        repr(estimate.action.strategic_key()),
    )


class SelectiveTutorQController:
    def __init__(
        self,
        *,
        continuation_policy=None,
        horizon:int=6,
        mc_root_seed:int=20260826,
        screen_rollouts:int=1,
        confirm_rollouts:int=4,
        shortlist_size:int=4,
        max_episode_steps:int=512,
        decision_cache:Phase5DecisionCache|None=None,
    ):
        self.policy=continuation_policy or DeterministicRolloutPolicyV6(
            policy_id=PHASE5_ROLLOUT_POLICY_V6
        )
        self.horizon=int(horizon)
        self.shortlist_size=max(1,int(shortlist_size))
        self.screen=Phase5MonteCarloDecisionEvaluator(
            rollout_count=int(screen_rollouts),
            mc_root_seed=int(mc_root_seed),
            horizon=self.horizon,
            continuation_policy=self.policy,
            max_episode_steps=int(max_episode_steps),
            strict_terminal_reasons=True,
            cache=decision_cache,
        )
        self.confirm=Phase5MonteCarloDecisionEvaluator(
            rollout_count=int(confirm_rollouts),
            mc_root_seed=int(mc_root_seed),
            horizon=self.horizon,
            continuation_policy=self.policy,
            max_episode_steps=int(max_episode_steps),
            strict_terminal_reasons=True,
            cache=decision_cache,
        )

    def _candidate_actions(self,request,fresh_actions,base):
        kinds={action.kind for action in fresh_actions}

        if base.kind==TRANSMMUTE_PAYMENT_KIND:
            return ()

        if kinds & PENDING_TUTOR_Q_KINDS:
            return _representatives(fresh_actions)

        tutor_actions=tuple(
            action for action in fresh_actions if action.kind in MAIN_TUTOR_KINDS
        )
        if not tutor_actions:
            return ()

        # Tutor-opportunity slice:
        # whenever a tutor is legally castable, compare all tutor commitments
        # against v6's preferred action and holding/end-turn. This lets Q rescue
        # tutors that v6 would otherwise strand behind mana/development actions,
        # while still avoiding global Q control over states with no tutor option.

        rows={
            action.strategic_key():action for action in tutor_actions
        }
        rows.setdefault(base.strategic_key(),base)

        for action in fresh_actions:
            if action.kind=="main_end_turn":
                rows.setdefault(action.strategic_key(),action)

        # The actual v6 choice is already in rows as the principal non-tutor
        # comparator whenever v6 did not choose a tutor. If v6 *did* choose a
        # tutor, also add its best ordinary alternative so Q can decide to
        # continue development rather than force a tutor merely because v6 did.
        if base.kind in MAIN_TUTOR_KINDS:
            ordinary=[
                action for action in fresh_actions
                if action.kind not in MAIN_TUTOR_KINDS
                and action.kind!="main_end_turn"
            ]
            if ordinary:
                score_fn=getattr(self.policy,"action_score",None)
                if callable(score_fn):
                    best_other=max(
                        ordinary,
                        key=lambda action:(
                            score_fn(
                                request.observation,action,request.context
                            ),
                            repr(action.strategic_key()),
                        ),
                    )
                else:
                    best_other=max(
                        ordinary,key=lambda action:repr(action.strategic_key())
                    )
                rows.setdefault(best_other.strategic_key(),best_other)

        return tuple(rows[key] for key in sorted(rows,key=repr))

    def choose(self,runtime,request,fresh_actions):
        base=self.policy.choose(
            request.observation,fresh_actions,request.context
        )
        candidates=self._candidate_actions(request,fresh_actions,base)
        if len(candidates)<2:
            return base,None

        screen=self.screen.evaluate(runtime,candidate_actions=candidates)
        screen_by_key={
            est.action.strategic_key():est for est in screen.estimates
        }

        ordered=sorted(screen.estimates,key=_value_rank,reverse=True)
        shortlist=list(ordered[:self.shortlist_size])
        base_est=screen_by_key[base.strategic_key()]
        if all(
            row.action.strategic_key()!=base.strategic_key()
            for row in shortlist
        ):
            shortlist.append(base_est)

        confirm=self.confirm.evaluate(
            runtime,
            candidate_actions=tuple(row.action for row in shortlist),
        )
        confirmed_base=_estimate_for(confirm,base)
        confirmed_best=confirm.estimates[0]

        # Q is an improver, not a replacement tie-break. Preserve the stable
        # deterministic leaf policy whenever downstream value is exactly tied.
        if (
            confirmed_best.value.comparison_key()
            > confirmed_base.value.comparison_key()
        ):
            chosen=confirmed_best.action
        else:
            chosen=base

        chosen_est=_estimate_for(confirm,chosen)
        return chosen,(
            base,
            chosen,
            len(screen.estimates),
            len(confirm.estimates),
            confirmed_base.value.comparison_key(),
            chosen_est.value.comparison_key(),
        )


def make_selective_tutor_q_episode_runner(
    *,
    mc_root_seed:int=20260826,
    screen_rollouts:int=1,
    confirm_rollouts:int=2,
    shortlist_size:int=3,
    decision_cache:Phase5DecisionCache|None=None,
):
    """Return an OpeningKeepEvaluator-compatible episode runner.

    A fresh controller is created for every outer rollout trajectory so controller
    diagnostics/cycle bookkeeping never leak between sampled games. The supplied
    leaf policy is still the continuation policy passed by the mulligan evaluator.
    """
    shared_cache=decision_cache or Phase5DecisionCache()

    def runner(runtime,*,horizon,policy,max_steps):
        controller=SelectiveTutorQController(
            continuation_policy=policy,
            horizon=horizon,
            mc_root_seed=mc_root_seed,
            screen_rollouts=screen_rollouts,
            confirm_rollouts=confirm_rollouts,
            shortlist_size=shortlist_size,
            max_episode_steps=max_steps,
            decision_cache=shared_cache,
        )
        return run_selective_tutor_q_episode(
            runtime,
            controller=controller,
            horizon=horizon,
            max_steps=max_steps,
        ).episode
    runner.decision_cache=shared_cache
    return runner


def run_selective_tutor_q_episode(
    runtime:NonOracleRuntimeState,
    *,
    controller:SelectiveTutorQController|None=None,
    horizon:int=6,
    max_steps:int=512,
)->SelectiveTutorQEpisodeResult:
    controller=controller or SelectiveTutorQController(horizon=horizon)
    policy=controller.policy
    runtime=_checked_runtime(runtime)
    steps=[]
    q_rows=[]
    attempted_by_cycle_state={}

    for sequence in range(max_steps):
        state=runtime.true_state
        if state.won:
            episode=NonOracleEpisodeResult(
                runtime,tuple(steps),horizon,int(state.turn),state.win_family,"win"
            )
            return SelectiveTutorQEpisodeResult(episode,tuple(q_rows))
        if state.turn>horizon:
            episode=NonOracleEpisodeResult(
                runtime,tuple(steps),horizon,None,"","horizon"
            )
            return SelectiveTutorQEpisodeResult(episode,tuple(q_rows))

        request=rules_decision_request(
            runtime,horizon=horizon,policy_id=policy.policy_id
        )
        if not request.actions:
            episode=NonOracleEpisodeResult(
                runtime,tuple(steps),horizon,None,"",
                _blocked_reason(runtime,horizon),
            )
            return SelectiveTutorQEpisodeResult(episode,tuple(q_rows))

        cycle_key=episode_cycle_key(runtime)
        attempted=attempted_by_cycle_state.setdefault(cycle_key,set())
        fresh=tuple(
            action for action in request.actions
            if action.strategic_key() not in attempted
        )
        if not fresh:
            episode=NonOracleEpisodeResult(
                runtime,tuple(steps),horizon,None,"","strategic_cycle_exhausted"
            )
            return SelectiveTutorQEpisodeResult(episode,tuple(q_rows))

        action,q_meta=controller.choose(runtime,request,fresh)
        if q_meta is not None:
            base,chosen,screen_n,confirm_n,base_key,chosen_key=q_meta
            q_rows.append(TutorQDecision(
                sequence=sequence,
                turn=int(state.turn),
                decision_id=str(request.context.decision_id),
                v6_action=base.label,
                chosen_action=chosen.label,
                overridden=chosen.strategic_key()!=base.strategic_key(),
                screen_candidate_count=int(screen_n),
                confirm_candidate_count=int(confirm_n),
                v6_value_key=tuple(base_key),
                chosen_value_key=tuple(chosen_key),
            ))

        attempted.add(action.strategic_key())
        before_turn=int(state.turn)
        before_window=runtime.window.kind
        observation_key=request.observation.key()
        runtime=_checked_runtime(apply_main_action(runtime,action))
        after=runtime.true_state
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

    episode=NonOracleEpisodeResult(
        runtime,
        tuple(steps),
        horizon,
        int(runtime.true_state.turn) if runtime.true_state.won else None,
        runtime.true_state.win_family if runtime.true_state.won else "",
        "step_limit",
    )
    return SelectiveTutorQEpisodeResult(episode,tuple(q_rows))
