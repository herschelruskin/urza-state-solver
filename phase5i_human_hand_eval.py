#!/usr/bin/env python3
"""Score one held-out human mulligan hand under the frozen Phase-5H player.

Human annotations are read only after the solver has completed its own bottom
screen/confirmation.  If an actual recorded human bottom was pruned by the solver
screen, that bottom is then evaluated on the identical confirmation outer-world
window for diagnostic ranking/regret only; it never changes the solver shortlist
or selected bottom.

Commander seat was not recorded in the human sheet.  Hands without Gemstone
Caverns are evaluated once because current opening mechanics are seat-invariant.
Hands containing Gemstone are evaluated in both relevant contexts: seat 1
(Caverns dead, 25% ex ante) and a representative seat 2 (Caverns live, 75% ex
ante).  Optimization occurs inside each known-seat context before any mixture.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from phase3_value_engine import WinDistributionValue
from phase5_mulligan import OpeningEnvironment, keep_size_for_stage
from phase5i_mulligan import Phase5IOpeningKeepEvaluator


OUTER_SCREEN = 1
OUTER_CONFIRM = 3
BOTTOM_SHORTLIST = 4
MC_ROOT_SEED = 2026082901
Q_MC_ROOT_SEED = 2026082902
HORIZON = 6


def load_deck():
    cards=[]
    for raw in Path("decklist.txt").read_text(encoding="utf-8").splitlines():
        line=raw.strip()
        if not line:
            continue
        count,name=line.split(" ",1)
        if name=="Urza, Lord High Artificer":
            continue
        cards.extend([name]*int(count))
    assert len(cards)==99
    return tuple(cards)


def value_json(value):
    return {
        "win_probability":value.win_probability,
        "exact_win":list(value.exact_win),
        "cumulative":[value.win_by(t) for t in range(1,value.horizon+1)],
        "comparison_key":list(value.comparison_key()),
        "no_win":value.no_win,
        "win_families":[list(row) for row in value.win_families],
    }


def estimate_json(estimate):
    return {
        "bottom":list(estimate.bottom),
        "kept_hand":list(estimate.kept_hand),
        "pregame_choice":{
            "use_caverns":bool(estimate.pregame_choice.use_caverns),
            "exile_card":str(estimate.pregame_choice.exile_card),
        },
        "value":value_json(estimate.value),
        "rollouts":estimate.rollouts,
        "terminal_reasons":[list(x) for x in estimate.terminal_reason_counts],
    }


def contexts_for(seven):
    if "Gemstone Caverns" not in seven:
        return (("seat_invariant",OpeningEnvironment(seat=1,player_count=4),1.0),)
    return (
        ("seat1_caverns_dead",OpeningEnvironment(seat=1,player_count=4),0.25),
        ("seats2to4_caverns_live",OpeningEnvironment(seat=2,player_count=4),0.75),
    )


def find_estimate(evaluation,bottom):
    bottom=tuple(sorted(bottom))
    return next((x for x in evaluation.estimates if x.bottom==bottom),None)


def diagnostic_rank(rows,target_bottom):
    target=tuple(sorted(target_bottom))
    ranked=sorted(
        rows,
        key=lambda x:(x.value.comparison_key(),repr(x.bottom)),
        reverse=True,
    )
    for rank,row in enumerate(ranked,1):
        if row.bottom==target:
            return rank
    return None


def objective_gap(best,human):
    a=best.value.comparison_key()
    b=human.value.comparison_key()
    return [float(x-y) for x,y in zip(a,b)]


def evaluate_context(deck,row,label,environment,weight):
    seven=tuple(row["drawn_seven"])
    stage=int(row["mulligan_count"])
    evaluator=Phase5IOpeningKeepEvaluator(
        deck,
        screen_rollouts=OUTER_SCREEN,
        confirm_rollouts=OUTER_CONFIRM,
        shortlist_size=BOTTOM_SHORTLIST,
        mc_root_seed=MC_ROOT_SEED,
        q_mc_root_seed=Q_MC_ROOT_SEED,
        horizon=HORIZON,
        opening_environment=environment,
    )
    solved=evaluator.evaluate(seven,stage=stage)
    best=solved.best

    human_bottom=tuple(sorted(row.get("cards_bottomed") or ()))
    human_estimate=None
    human_screen_rank=None
    human_confirmed_rank=None
    bottom_exact=None
    regret=None

    # Only actual kept hands at stages with a bottom decision carry a meaningful
    # human-bottom label. Stage-0/1 empty bottoms are mechanically identical.
    has_human_bottom=(
        str(row.get("decision"))=="Keep"
        and stage>=2
        and len(human_bottom)>0
    )
    if has_human_bottom:
        if solved.screen is not None:
            for rank,estimate in enumerate(solved.screen.estimates,1):
                if estimate.bottom==human_bottom:
                    human_screen_rank=rank
                    break

        human_estimate=find_estimate(solved.confirmation,human_bottom)
        diagnostic_rows=list(solved.confirmation.estimates)
        if human_estimate is None:
            # External diagnostic only.  Same fresh confirmation outer worlds as
            # the solver shortlist, but this cannot alter solved.best.
            nominated=evaluator.confirm_evaluator.evaluate(
                seven,
                stage=stage,
                candidate_bottoms=(human_bottom,),
                sample_start=OUTER_SCREEN,
            )
            human_estimate=nominated.best
            diagnostic_rows.append(human_estimate)
        human_confirmed_rank=diagnostic_rank(diagnostic_rows,human_bottom)
        bottom_exact=(best.bottom==human_bottom)
        regret={
            "delta_pwin_best_minus_human":float(
                best.value.win_probability-human_estimate.value.win_probability
            ),
            "objective_key_gap_best_minus_human":objective_gap(best,human_estimate),
        }

    return {
        "label":label,
        "weight":weight,
        "seat":environment.seat,
        "caverns_live":environment.caverns_live,
        "stage":stage,
        "keep_size":keep_size_for_stage(stage),
        "solver":{
            "best":estimate_json(best),
            "legal_bottom_count":solved.legal_bottom_count,
            "confirmed_bottom_count":solved.confirmed_bottom_count,
            "shortlisted_bottoms":[list(x) for x in solved.shortlisted_bottoms],
        },
        "human_bottom_diagnostic":{
            "applicable":has_human_bottom,
            "bottom":list(human_bottom),
            "screen_rank":human_screen_rank,
            "confirmed_rank_among_shortlist_plus_human":human_confirmed_rank,
            "exact_match":bottom_exact,
            "estimate":None if human_estimate is None else estimate_json(human_estimate),
            "regret":regret,
        },
        "q_cache":{
            "hits":evaluator.cache.stats.hits,
            "misses":evaluator.cache.stats.misses,
        },
    }


def weighted_value(contexts,key_fn):
    rows=[]
    for context in contexts:
        value=key_fn(context)
        if value is None:
            return None
        rows.append((float(context["weight"]),value))
    total=sum(w for w,_ in rows)
    rows=tuple((w/total,v) for w,v in rows)
    return WinDistributionValue.mixture(rows,horizon=HORIZON)


def value_from_json(payload):
    return WinDistributionValue(
        horizon=HORIZON,
        exact_win=tuple(payload["exact_win"]),
        no_win=float(payload["no_win"]),
        win_families=tuple((str(a),float(b)) for a,b in payload["win_families"]),
    )


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--hand-id",type=int,required=True)
    args=parser.parse_args()

    fixture=json.loads(
        Path("benchmarks/human/human_mulligan_exact_hands.json").read_text(encoding="utf-8")
    )
    row=next(x for x in fixture["hands"] if int(x["hand_id"])==int(args.hand_id))
    if not row.get("primary_benchmark_usable",False):
        raise SystemExit(f"hand {args.hand_id} is not an exact-state benchmark")

    deck=load_deck()
    contexts=[
        evaluate_context(deck,row,label,environment,weight)
        for label,environment,weight in contexts_for(tuple(row["drawn_seven"]))
    ]

    best_mix=weighted_value(
        contexts,
        lambda c:value_from_json(c["solver"]["best"]["value"]),
    )
    human_mix=weighted_value(
        contexts,
        lambda c:(
            None
            if c["human_bottom_diagnostic"]["estimate"] is None
            else value_from_json(c["human_bottom_diagnostic"]["estimate"]["value"])
        ),
    )

    payload={
        "kind":"phase5i-human-hand-evaluation",
        "hand_id":int(row["hand_id"]),
        "human":{
            "decision":row.get("decision"),
            "mulligan_count":int(row["mulligan_count"]),
            "keep_size":int(row["keep_size"]),
            "rating_within_size":row.get("rating_within_size"),
            "drawn_seven":list(row["drawn_seven"]),
            "cards_bottomed":list(row.get("cards_bottomed") or []),
        },
        "budgets":{
            "outer_screen":OUTER_SCREEN,
            "outer_confirm":OUTER_CONFIRM,
            "bottom_shortlist":BOTTOM_SHORTLIST,
            "mc_root_seed":MC_ROOT_SEED,
            "q_mc_root_seed":Q_MC_ROOT_SEED,
        },
        "seat_missing_in_human_source":True,
        "contexts":contexts,
        "ex_ante_after_seat_conditioned_optimization":{
            "solver_best_value":value_json(best_mix),
            "human_bottom_value":None if human_mix is None else value_json(human_mix),
        },
    }
    out=Path(f"phase5i_human_hand_{int(row['hand_id']):02d}.json")
    out.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print("PHASE5I_HAND="+json.dumps({
        "hand_id":payload["hand_id"],
        "human_decision":payload["human"]["decision"],
        "stage":payload["human"]["mulligan_count"],
        "contexts":[{
            "label":c["label"],
            "best_bottom":c["solver"]["best"]["bottom"],
            "pwin":c["solver"]["best"]["value"]["win_probability"],
            "human_bottom_rank":c["human_bottom_diagnostic"]["confirmed_rank_among_shortlist_plus_human"],
            "bottom_exact":c["human_bottom_diagnostic"]["exact_match"],
        } for c in contexts],
        "ex_ante_pwin":best_mix.win_probability,
    },sort_keys=True))


if __name__=="__main__":
    main()
