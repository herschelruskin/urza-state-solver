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

from collections import Counter
from dataclasses import dataclass
from math import comb
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
    _value,
    _wilson,
)
from phase5_rollout_policy_v6 import (
    DeterministicRolloutPolicyV6,
    PHASE5_ROLLOUT_POLICY_V6,
)

PHASE5_SELECTIVE_TUTOR_Q_VERSION="urza-phase5-selective-tutor-q-v4-confidence-gated"
PHASE5_CONTINGENT_TUTOR_Q_VERSION="urza-phase5-contingent-tutor-q-v2-confidence-gated"


@dataclass(frozen=True)
class TutorQPolicyConfig:
    """Immutable execution budget for one selective tutor-Q policy."""

    mc_root_seed:int=2026082802
    screen_rollouts:int=1
    confirm_rollouts:int=2
    shortlist_size:int=3
    contingent:bool=True
    confidence_gate:bool=True
    validation_rollouts:int=2
    max_validation_rollouts:int=8
    confidence_alpha:float=0.25


PHASE5H_PRODUCTION_TUTOR_Q_CONFIG=TutorQPolicyConfig()

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

# Number of post-commit tutor/search decisions whose *executed policy* must be
# reflected while valuing this root action.  Most tutors expose one target after
# commitment. Transmute exposes sacrifice, then a newly observed target choice.
CONTINGENT_DEPTH_AFTER_ACTION_KIND={
    "main_use_simple_tutor":1,
    "main_use_transmute_artifact":2,
    "main_use_x_artifact_tutor":1,
    "main_activate_repurposing_bay":1,
    "main_cast_scour_for_scrap":1,
    "main_activate_tezzeret_minus3":1,
    "transmute_choose_sacrifice":1,
}


def contingent_depth_after_action(action:ActionIntent)->int:
    return int(CONTINGENT_DEPTH_AFTER_ACTION_KIND.get(str(action.kind),0))


def is_contingent_descendant_decision(
    runtime:NonOracleRuntimeState,
    fresh_actions,
    *,
    lineage_source:str,
    remaining:int,
)->bool:
    """True only for the bounded post-commit decision owned by this tutor line."""

    pending_source=(
        str(runtime.pending.spec.source)
        if runtime.pending is not None else ""
    )
    return bool(
        int(remaining)>0
        and str(lineage_source)
        and pending_source==str(lineage_source)
        and any(
            str(action.kind) in PENDING_TUTOR_Q_KINDS
            for action in fresh_actions
        )
    )


def committed_lineage_on_stack(
    runtime:NonOracleRuntimeState,
    *,
    lineage_source:str,
)->bool:
    """Whether the committed tutor/search object is still unresolved on stack."""
    source=str(lineage_source)
    if not source:
        return False
    return any(
        str(obj.source)==source or str(obj.card)==source
        for obj in runtime.stack.objects
    )


def commitment_corridor_pass_action(
    runtime:NonOracleRuntimeState,
    fresh_actions,
    *,
    lineage_source:str,
    remaining:int,
):
    """Resolve the committed tutor cleanly until its bounded child decision.

    Q(root tutor) is supposed to value the tutor plus its immediate dependent
    choice, not let the cheap rollout policy take unrelated mana/development
    actions while that tutor is waiting on the stack.  Cast-trigger ordering and
    post-observation/mechanical decisions still go through the frozen policy; at
    an ordinary priority window, however, passing priority is the canonical
    commitment-preserving transition.
    """
    if int(remaining)<=0 or runtime.pending is not None:
        return None
    if not committed_lineage_on_stack(runtime,lineage_source=lineage_source):
        return None
    passes=tuple(
        action for action in fresh_actions
        if str(action.kind)=="pass_priority"
    )
    if not passes:
        return None
    return min(passes,key=lambda action:repr(action.strategic_key()))


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
    proposed_action: str = ""
    proposed_value_key: Tuple[float, ...] = ()
    validation_rollouts: int = 0
    paired_better: int = 0
    paired_worse: int = 0
    paired_ties: int = 0
    paired_sign_p: float = 1.0
    gate_reason: str = ""


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


@dataclass(frozen=True)
class PairedQEvidence:
    better: int
    worse: int
    ties: int
    sign_p_one_sided: float

    @property
    def informative(self) -> int:
        return int(self.better + self.worse)


def _outcome_rank(outcome):
    if not outcome.won:
        return (0, 0)
    return (1, -int(outcome.win_turn))


def _one_sided_sign_p(*,better:int,worse:int)->float:
    n=int(better)+int(worse)
    if n<=0:
        return 1.0
    wins=int(better)
    return sum(comb(n,k) for k in range(wins,n+1)) / float(2**n)


def paired_q_evidence(
    candidate:Phase5ActionEstimate,
    base:Phase5ActionEstimate,
)->PairedQEvidence:
    """Paired evidence on identical hidden worlds.

    A candidate is better on a world if it wins where base loses or wins on an
    earlier turn. Same-turn wins and joint losses are ties. Hidden-world order is
    aligned because every Phase5 evaluator uses common random numbers across
    candidate actions.
    """
    if len(candidate.outcomes)!=len(base.outcomes):
        raise ValueError("paired Q estimates must use the same number of worlds")
    if not candidate.outcomes:
        raise ValueError("paired Q evidence requires retained rollout outcomes")
    better=worse=ties=0
    for cand_out,base_out in zip(candidate.outcomes,base.outcomes):
        cand_rank=_outcome_rank(cand_out)
        base_rank=_outcome_rank(base_out)
        if cand_rank>base_rank:
            better+=1
        elif cand_rank<base_rank:
            worse+=1
        else:
            ties+=1
    return PairedQEvidence(
        better=better,
        worse=worse,
        ties=ties,
        sign_p_one_sided=_one_sided_sign_p(better=better,worse=worse),
    )


def _aggregate_action_estimates(
    action:ActionIntent,
    estimates,
    *,
    horizon:int,
)->Phase5ActionEstimate:
    outcomes=tuple(
        outcome
        for estimate in estimates
        for outcome in estimate.outcomes
    )
    if not outcomes:
        raise ValueError("adaptive Q validation requires retained paired outcomes")
    reasons=Counter(outcome.terminal_reason for outcome in outcomes)
    wins=sum(outcome.won for outcome in outcomes)
    return Phase5ActionEstimate(
        action=action,
        value=_value(outcomes,horizon=int(horizon)),
        rollouts=len(outcomes),
        terminal_reason_counts=tuple(sorted(reasons.items())),
        win_probability_wilson95=_wilson(wins,len(outcomes)),
        outcomes=outcomes,
    )


def _continuation_id(
    *,
    screen_rollouts,
    confirm_rollouts,
    shortlist_size,
    confidence_gate,
    validation_rollouts,
    max_validation_rollouts,
    confidence_alpha,
):
    return (
        f"{PHASE5_CONTINGENT_TUTOR_Q_VERSION}:"
        f"screen={int(screen_rollouts)}:"
        f"confirm={int(confirm_rollouts)}:"
        f"shortlist={int(shortlist_size)}:"
        f"gate={int(bool(confidence_gate))}:"
        f"validate={int(validation_rollouts)}:"
        f"validate_max={int(max_validation_rollouts)}:"
        f"alpha={float(confidence_alpha):.6g}"
    )


def make_bounded_contingent_tutor_runner(
    *,
    mc_root_seed:int,
    screen_rollouts:int,
    confirm_rollouts:int,
    shortlist_size:int,
    decision_cache:Phase5DecisionCache|None,
    confidence_gate:bool=True,
    validation_rollouts:int=2,
    max_validation_rollouts:int=8,
    confidence_alpha:float=0.25,
):
    """Return a Phase5MC continuation that Q-controls only this tutor's descendants.

    The root action has already been applied in one sampled hidden world.  We
    advance using the frozen policy through stack/mechanical decisions until a
    post-commit tutor/search decision for the same source appears.  That decision
    is Q-evaluated from its *new* legal observation.  Transmute is allowed two
    descendant decisions (sacrifice then target); other tutor commitments get one.
    After the bounded descendant budget is consumed, continuation is plain v6.

    Nested Q values use the same helper recursively, but the action-kind depth map
    strictly decreases: Transmute sacrifice -> target -> zero.  Payment remains
    outside PENDING_TUTOR_Q_KINDS and is therefore handled by the frozen policy.
    """
    shared_cache=decision_cache if decision_cache is not None else Phase5DecisionCache()
    continuation_id=_continuation_id(
        screen_rollouts=screen_rollouts,
        confirm_rollouts=confirm_rollouts,
        shortlist_size=shortlist_size,
        confidence_gate=confidence_gate,
        validation_rollouts=validation_rollouts,
        max_validation_rollouts=max_validation_rollouts,
        confidence_alpha=confidence_alpha,
    )

    def runner(runtime,*,root_action,horizon,policy,max_steps):
        remaining=contingent_depth_after_action(root_action)
        if remaining<=0:
            from non_oracle_episode import run_deterministic_episode
            return run_deterministic_episode(
                runtime,horizon=horizon,policy=policy,max_steps=max_steps
            )

        lineage_source=str(getattr(root_action,"source",""))
        runtime=_checked_runtime(runtime)
        steps=[]
        attempted_by_cycle_state={}

        for sequence in range(max_steps):
            state=runtime.true_state
            if state.won:
                return NonOracleEpisodeResult(
                    runtime,tuple(steps),horizon,int(state.turn),state.win_family,"win"
                )
            if state.turn>horizon:
                return NonOracleEpisodeResult(
                    runtime,tuple(steps),horizon,None,"","horizon"
                )

            request=rules_decision_request(
                runtime,horizon=horizon,policy_id=policy.policy_id
            )
            if not request.actions:
                return NonOracleEpisodeResult(
                    runtime,tuple(steps),horizon,None,"",
                    _blocked_reason(runtime,horizon),
                )

            cycle_key=episode_cycle_key(runtime)
            attempted=attempted_by_cycle_state.setdefault(cycle_key,set())
            fresh=tuple(
                action for action in request.actions
                if action.strategic_key() not in attempted
            )
            if not fresh:
                return NonOracleEpisodeResult(
                    runtime,tuple(steps),horizon,None,"","strategic_cycle_exhausted"
                )

            has_contingent_choice=is_contingent_descendant_decision(
                runtime,
                fresh,
                lineage_source=lineage_source,
                remaining=remaining,
            )
            if has_contingent_choice:
                nested=SelectiveTutorQController(
                    continuation_policy=policy,
                    horizon=horizon,
                    mc_root_seed=mc_root_seed,
                    screen_rollouts=screen_rollouts,
                    confirm_rollouts=confirm_rollouts,
                    shortlist_size=shortlist_size,
                    max_episode_steps=max_steps,
                    decision_cache=shared_cache,
                    contingent=True,
                    confidence_gate=confidence_gate,
                    validation_rollouts=validation_rollouts,
                    max_validation_rollouts=max_validation_rollouts,
                    confidence_alpha=confidence_alpha,
                )
                action,_=nested.choose(runtime,request,fresh)
                remaining-=1
            else:
                corridor=commitment_corridor_pass_action(
                    runtime,
                    fresh,
                    lineage_source=lineage_source,
                    remaining=remaining,
                )
                action=(
                    corridor
                    if corridor is not None
                    else policy.choose(
                        request.observation,fresh,request.context
                    )
                )

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

        return NonOracleEpisodeResult(
            runtime,
            tuple(steps),
            horizon,
            int(runtime.true_state.turn) if runtime.true_state.won else None,
            runtime.true_state.win_family if runtime.true_state.won else "",
            "step_limit",
        )

    runner.continuation_id=continuation_id
    runner.decision_cache=shared_cache
    return runner


class SelectiveTutorQController:
    def __init__(
        self,
        *,
        continuation_policy=None,
        horizon:int=6,
        mc_root_seed:int=20260826,
        screen_rollouts:int=1,
        confirm_rollouts:int=2,
        shortlist_size:int=3,
        max_episode_steps:int=512,
        decision_cache:Phase5DecisionCache|None=None,
        contingent:bool=True,
        confidence_gate:bool=True,
        validation_rollouts:int=2,
        max_validation_rollouts:int=8,
        confidence_alpha:float=0.25,
    ):
        self.policy=continuation_policy or DeterministicRolloutPolicyV6(
            policy_id=PHASE5_ROLLOUT_POLICY_V6
        )
        self.horizon=int(horizon)
        self.shortlist_size=max(1,int(shortlist_size))
        self.contingent=bool(contingent)
        self.confidence_gate=bool(confidence_gate)
        self.validation_rollouts=max(1,int(validation_rollouts))
        self.max_validation_rollouts=max(
            self.validation_rollouts,int(max_validation_rollouts)
        )
        self.confidence_alpha=float(confidence_alpha)
        if not (0.0 < self.confidence_alpha <= 0.5):
            raise ValueError("confidence_alpha must be in (0, 0.5]")
        self._mc_root_seed=int(mc_root_seed)
        self._max_episode_steps=int(max_episode_steps)
        self._decision_cache=decision_cache
        continuation_runner=(
            make_bounded_contingent_tutor_runner(
                mc_root_seed=self._mc_root_seed,
                screen_rollouts=int(screen_rollouts),
                confirm_rollouts=int(confirm_rollouts),
                shortlist_size=self.shortlist_size,
                decision_cache=decision_cache,
                confidence_gate=self.confidence_gate,
                validation_rollouts=self.validation_rollouts,
                max_validation_rollouts=self.max_validation_rollouts,
                confidence_alpha=self.confidence_alpha,
            )
            if self.contingent else None
        )
        continuation_id=(
            continuation_runner.continuation_id
            if continuation_runner is not None
            else "plain-v6"
        )
        self._continuation_runner=continuation_runner
        self._continuation_id=continuation_id
        self.screen=Phase5MonteCarloDecisionEvaluator(
            rollout_count=int(screen_rollouts),
            mc_root_seed=self._mc_root_seed,
            horizon=self.horizon,
            continuation_policy=self.policy,
            max_episode_steps=self._max_episode_steps,
            strict_terminal_reasons=True,
            cache=decision_cache,
            continuation_runner=continuation_runner,
            continuation_id=continuation_id,
            sample_namespace="screen",
        )
        self.confirm=Phase5MonteCarloDecisionEvaluator(
            rollout_count=int(confirm_rollouts),
            mc_root_seed=self._mc_root_seed,
            horizon=self.horizon,
            continuation_policy=self.policy,
            max_episode_steps=self._max_episode_steps,
            strict_terminal_reasons=True,
            cache=decision_cache,
            continuation_runner=continuation_runner,
            continuation_id=continuation_id,
            sample_namespace="confirm",
        )

    def _validation_batch_sizes(self):
        total=0
        while total<self.max_validation_rollouts:
            target=(
                self.validation_rollouts
                if total==0
                else min(self.max_validation_rollouts,total*2)
            )
            target=min(self.max_validation_rollouts,max(target,total+1))
            yield target-total
            total=target

    def _validation_evaluator(self,*,rollout_count:int,round_index:int):
        return Phase5MonteCarloDecisionEvaluator(
            rollout_count=int(rollout_count),
            mc_root_seed=self._mc_root_seed,
            horizon=self.horizon,
            continuation_policy=self.policy,
            max_episode_steps=self._max_episode_steps,
            strict_terminal_reasons=True,
            cache=self._decision_cache,
            continuation_runner=self._continuation_runner,
            continuation_id=self._continuation_id,
            sample_namespace=f"validate-{int(round_index)}",
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
        cutoff_index=min(self.shortlist_size,len(ordered))-1
        cutoff_value=ordered[cutoff_index].value.comparison_key()
        # A tiny screening budget frequently produces exact value ties. Never
        # let strategic-key ordering decide which tied tutor survives into the
        # confirmation set; preserve every action tied at the cutoff.
        shortlist=[
            row for row in ordered
            if row.value.comparison_key()>=cutoff_value
        ]
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
        proposed=confirmed_best.action
        proposed_est=confirmed_best

        # Exact confirmation ties remain v6 ties.  A candidate must first beat
        # v6 on the independent confirmation set before spending any adaptive
        # validation budget.
        if (
            confirmed_best.value.comparison_key()
            <= confirmed_base.value.comparison_key()
        ):
            chosen=base
            chosen_est=confirmed_base
            evidence=PairedQEvidence(0,0,0,1.0)
            validation_total=0
            gate_reason="confirm_no_strict_improvement"
        elif not self.confidence_gate:
            chosen=proposed
            chosen_est=proposed_est
            evidence=PairedQEvidence(0,0,0,1.0)
            validation_total=0
            gate_reason="confidence_gate_disabled"
        else:
            validation_rows={
                base.strategic_key():[],
                proposed.strategic_key():[],
            }
            chosen=base
            chosen_est=confirmed_base
            evidence=PairedQEvidence(0,0,0,1.0)
            validation_total=0
            gate_reason="paired_confidence_unresolved"

            for round_index,batch_size in enumerate(
                self._validation_batch_sizes()
            ):
                validation=self._validation_evaluator(
                    rollout_count=batch_size,
                    round_index=round_index,
                ).evaluate(
                    runtime,
                    candidate_actions=(base,proposed),
                )
                for estimate in validation.estimates:
                    validation_rows[estimate.action.strategic_key()].append(
                        estimate
                    )
                validation_total+=int(batch_size)

                base_agg=_aggregate_action_estimates(
                    base,
                    validation_rows[base.strategic_key()],
                    horizon=self.horizon,
                )
                proposed_agg=_aggregate_action_estimates(
                    proposed,
                    validation_rows[proposed.strategic_key()],
                    horizon=self.horizon,
                )
                evidence=paired_q_evidence(proposed_agg,base_agg)

                candidate_supported=(
                    proposed_agg.value.comparison_key()
                    > base_agg.value.comparison_key()
                    and evidence.better>evidence.worse
                    and evidence.sign_p_one_sided<=self.confidence_alpha
                )
                if candidate_supported:
                    chosen=proposed
                    chosen_est=proposed_agg
                    proposed_est=proposed_agg
                    confirmed_base=base_agg
                    gate_reason="paired_confidence_override"
                    break

                reverse=paired_q_evidence(base_agg,proposed_agg)
                base_supported=(
                    base_agg.value.comparison_key()
                    > proposed_agg.value.comparison_key()
                    and reverse.better>reverse.worse
                    and reverse.sign_p_one_sided<=self.confidence_alpha
                )
                if base_supported:
                    chosen=base
                    chosen_est=base_agg
                    proposed_est=proposed_agg
                    confirmed_base=base_agg
                    gate_reason="paired_confidence_reject"
                    break

                proposed_est=proposed_agg
                confirmed_base=base_agg
                chosen_est=base_agg

        return chosen,(
            base,
            chosen,
            len(screen.estimates),
            len(confirm.estimates),
            confirmed_base.value.comparison_key(),
            chosen_est.value.comparison_key(),
            proposed,
            proposed_est.value.comparison_key(),
            int(validation_total),
            int(evidence.better),
            int(evidence.worse),
            int(evidence.ties),
            float(evidence.sign_p_one_sided),
            str(gate_reason),
        )


def make_selective_tutor_q_episode_runner(
    *,
    mc_root_seed:int=20260826,
    screen_rollouts:int=1,
    confirm_rollouts:int=2,
    shortlist_size:int=3,
    decision_cache:Phase5DecisionCache|None=None,
    contingent:bool=True,
    confidence_gate:bool=True,
    validation_rollouts:int=2,
    max_validation_rollouts:int=8,
    confidence_alpha:float=0.25,
):
    """Return an OpeningKeepEvaluator-compatible episode runner.

    A fresh controller is created for every outer rollout trajectory so controller
    diagnostics/cycle bookkeeping never leak between sampled games. The supplied
    leaf policy is still the continuation policy passed by the mulligan evaluator.
    """
    shared_cache=decision_cache if decision_cache is not None else Phase5DecisionCache()

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
            contingent=contingent,
            confidence_gate=confidence_gate,
            validation_rollouts=validation_rollouts,
            max_validation_rollouts=max_validation_rollouts,
            confidence_alpha=confidence_alpha,
        )
        return run_selective_tutor_q_episode(
            runtime,
            controller=controller,
            horizon=horizon,
            max_steps=max_steps,
        ).episode
    runner.decision_cache=shared_cache
    return runner


def make_phase5h_production_tutor_q_episode_runner(
    *,
    mc_root_seed:int|None=None,
    decision_cache:Phase5DecisionCache|None=None,
):
    """Return the frozen Phase-5H gameplay policy used by downstream valuation.

    Downstream layers may vary their *outer* Monte Carlo budget, but they should
    not silently change the gameplay policy being valued.  This factory therefore
    centralizes the validated 5H action-policy budget.
    """
    config=PHASE5H_PRODUCTION_TUTOR_Q_CONFIG
    effective_seed=(
        int(config.mc_root_seed)
        if mc_root_seed is None
        else int(mc_root_seed)
    )
    runner=make_selective_tutor_q_episode_runner(
        mc_root_seed=effective_seed,
        screen_rollouts=config.screen_rollouts,
        confirm_rollouts=config.confirm_rollouts,
        shortlist_size=config.shortlist_size,
        decision_cache=decision_cache,
        contingent=config.contingent,
        confidence_gate=config.confidence_gate,
        validation_rollouts=config.validation_rollouts,
        max_validation_rollouts=config.max_validation_rollouts,
        confidence_alpha=config.confidence_alpha,
    )
    runner.q_policy_config=config
    runner.q_policy_version=PHASE5_SELECTIVE_TUTOR_Q_VERSION
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
            (
                base,chosen,screen_n,confirm_n,base_key,chosen_key,
                proposed,proposed_key,validation_n,paired_better,
                paired_worse,paired_ties,paired_p,gate_reason,
            )=q_meta
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
                proposed_action=proposed.label,
                proposed_value_key=tuple(proposed_key),
                validation_rollouts=int(validation_n),
                paired_better=int(paired_better),
                paired_worse=int(paired_worse),
                paired_ties=int(paired_ties),
                paired_sign_p=float(paired_p),
                gate_reason=str(gate_reason),
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
