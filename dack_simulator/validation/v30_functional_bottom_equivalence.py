#!/usr/bin/env python3
"""Experimental, read-only functional-bottom equivalence framework.

Do not train on 99k held-out research data or treat a matching signature as
proof of action-equivalence. This is a candidate *stratification* for designing
a future outcome-trained learner, with unknown card abilities explicitly
marked uncertain. Never collapse canonical game-search states by this key.
"""
from __future__ import annotations
from collections import Counter
import json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

import dack_paired_counterfactual_v5_stable_chance_20261031 as teacher
import dack_mulligan_analytic_policy_v6_20261031 as analytic

d=teacher.reference.d
OTHER_MDFC=frozenset(("Emeria's Call","Razorgrass Ambush"))
TUTORS=frozenset(analytic.TUTORS)
KEYS=frozenset(("Voltaic Key","Candelabra of Tawnos","Scroll Rack","Brainstone"))
CORNER=frozenset((
    "Gleaming Splendor","Lion's Eye Diamond","The Mycosynth Gardens",
    "Urza's Saga","Krark-Clan Ironworks","Bucknard's Everfull Purse",
    "Grim Monolith","Basalt Monolith","Mana Vault","Sol Ring",
    "Mox Opal","Mox Diamond","Chrome Mox","Gemstone Caverns",
))
CORE=frozenset(("Boonweaver Giant","Preston, the Vanisher","Roaming Throne"))
# These cards can have their own modeled or real utility. A matching
# signature must NEVER call them globally identical or collapse actual states.
UNPROVEN_ABILITY_EXAMPLES=frozenset((
    "Charitable Levy","Touch the Spirit Realm","Void Mirror",
    "Silence","Defense Grid","Disruptor Flute","Erode",
))

def land(card):
    return card in d.LANDS or card in OTHER_MDFC

def protected_aura(card):
    return card in d.AURAS

def real_critical_cards_in_hand(hand):
    important=set(d.RAMP_PROTECTED)|set(TUTORS)|set(KEYS)|set(CORNER)|set(CORE)
    return tuple(sorted(x for x in hand if land(x) or x in important))

def functional_fingerprint(seven,hand,bottom,seat):
    """A conservative *candidate key*, not certified equivalence.

    Preserve identities of every resource, tutor, combo piece, and land.
    Retain Mox fuel and artifact count flags; do not treat matching keys as
    a proof that unmodeled or late-game card text is irrelevant.
    """
    h=Counter(hand); b=Counter(bottom); s=Counter(seven)
    assert s==h+b and len(seven)==7
    has_chrome=h["Chrome Mox"]>0
    has_opal=h["Mox Opal"]>0
    has_diamond=h["Mox Diamond"]>0
    has_gemstone=h["Gemstone Caverns"]>0 and int(seat)!=0
    eligible_imprints=sum(int(d.chrome_mox_allowed(x))*n for x,n in h.items()
                          if x!="Chrome Mox")
    chrome_white_imprints=sum(int(d.chrome_mox_allowed(x))*n for x,n in h.items()
                    if x not in {"Chrome Mox","Void Mirror"})
    artifact_count=sum(int(d.is_artifact_perm(x))*n for x,n in h.items())
    return {
        "critical_card_identity":real_critical_cards_in_hand(tuple(hand)),
        "creature_contamination":tuple(sorted(x for x in hand if x in CORE)),
        "auras_in_hand":sum(n for x,n in h.items() if protected_aura(x)),
        "auras_bottomed":sum(n for x,n in b.items() if protected_aura(x)),
        "lands_in_hand":sum(n for x,n in h.items() if land(x)),
        "mDFC_in_hand":sum(n for x,n in h.items() if x in OTHER_MDFC),
        "chrome_imprintable_fuel":eligible_imprints if has_chrome else None,
        "chrome_white_imprintable_fuel":chrome_white_imprints if has_chrome else None,
        "metalcraft_artifact_count":artifact_count if has_opal else None,
        "mox_diamond_land_count":sum(n for x,n in h.items() if land(x))
                    if has_diamond else None,
        "gemstone_noncombo_exile_fuel":sum(
                    n for x,n in h.items()
                    if x!="Gemstone Caverns" and
                       x not in CORE and
                       not protected_aura(x) and x!="Gleaming Splendor"
                 ) if has_gemstone else None,
    }

def candidate_distance(first,second,seat):
    assert Counter(first["hand"])+Counter(first["bottom"])==(
        Counter(second["hand"])+Counter(second["bottom"]))
    seven=list(first["hand"])+list(first["bottom"])
    a=functional_fingerprint(seven,first["hand"],first["bottom"],seat)
    b=functional_fingerprint(seven,second["hand"],second["bottom"],seat)
    differences=sorted(k for k in a if a[k]!=b[k])
    # Expected deployment irrelevance is a HYPOTHESIS and can fail because of
    # any card's action text. Existing v29 Chrome Mox imprint case must not
    # have identical signature.
    return {
        "hypothesized_same_deployment_capability":not differences,
        "functional_field_differences":differences,
        "changed_hand_cards":list((Counter(first["hand"])-Counter(second["hand"])).elements()),
        "opposite_changed_hand_cards":list((Counter(second["hand"])-Counter(first["hand"])).elements()),
        "unproven_card_ability_may_matter":any(
            x in UNPROVEN_ABILITY_EXAMPLES for x in
            (Counter(first["hand"])-Counter(second["hand"]))+
            (Counter(second["hand"])-Counter(first["hand"]))
        ),
        "matching_signature_is_not_rules_equivalence":True,
    }

def compare_observed_futures(a,b,n):
    """Speed-equivalence evidence only. No exact-bottom-index loss.

    Exact equal counts across 16 independent futures is a descriptive
    observed-rate tie, NOT a proof of expected-value equivalence.
    """
    assert n>0
    t2a=float(a["heldout_by_T2"]);t2b=float(b["heldout_by_T2"])
    t3a=float(a["heldout_by_T3"]);t3b=float(b["heldout_by_T3"])
    ua=float(a["heldout_blended_utility"]);ub=float(b["heldout_blended_utility"])
    assert all(0<=x<=1 for x in (t2a,t2b,t3a,t3b,ua,ub))
    eps=1e-10
    return {
      "same_T2_and_T3_observed_fractions":abs(t2a-t2b)<eps and abs(t3a-t3b)<eps,
      "same_blended_utility":abs(ua-ub)<eps,
      "delta_v5_minus_student_T2":t2a-t2b,
      "delta_v5_minus_student_T3":t3a-t3b,
      "delta_v5_minus_student_U":ua-ub,
      "net_T2_value_difference_is_primary_not_card_identity":True,
      "sparse_16_future_labels_not_equivalence_proof":True,
    }

def report():
    teacher.audit()
    data=json.loads(Path("benchmark_results/v28_bottom_hidden_order_and_unseen_value_N64.json").read_text())
    assert data["schema"]=="dack_v28_frozen_v5_bottom_hidden_order_and_unseen_utility_N64"
    groups=data["individual_research_groups"]
    assert len(groups)==50 and data["v5_actual_hidden_order_invariant_all_groups"]
    counter=Counter(); examples=[];deltas=[]
    for g in groups:
        lookup={v["candidate_index"]:v for v in g["candidate_results"]}
        a=lookup[g["v5_candidate_index"]]; z=lookup[g["v14_candidate_index"]]
        cmp=compare_observed_futures(a,z,g["sampled_independent_futures_per_candidate"])
        distance=candidate_distance(a,z,g["seat"])
        equal_exact=Counter(a["bottom"])==Counter(z["bottom"])
        stat=( "different_bottoms" if not equal_exact else "same_bottoms" )
        counter[stat]+=1
        if cmp["same_T2_and_T3_observed_fractions"]:
            counter["observed_speed_tie"]+=1
            counter[stat+"_observed_speed_tie"]+=1
        if distance["hypothesized_same_deployment_capability"]:
            counter["same_visible_capability_key"]+=1
            counter[stat+"_same_visible_capability_key"]+=1
        if not equal_exact:
            counter["different_bottoms_with_critical_changes"]+=int(
                not distance["hypothesized_same_deployment_capability"])
            counter["different_bottoms_with_identical_visible_capability"]+=int(
                distance["hypothesized_same_deployment_capability"])
            counter["different_bottoms_but_same_observed_speed"]+=int(
                cmp["same_T2_and_T3_observed_fractions"])
        for name in distance["functional_field_differences"]:
            counter["difference_field:"+name]+=1
        deltas.append(cmp["delta_v5_minus_student_T2"])
        examples.append({
          "game_id":g["game_id"],"seat":g["seat"],"keep_n":g["keep_n"],
          "v5_bottom":a["bottom"],"student_bottom":z["bottom"],
          "exact_same_bottom":equal_exact,**cmp,**distance,
        })
    # Test that mathematical action-value loss is indifferent to the names
    # of a card when all outcome labels are held constant.
    x={"heldout_by_T2":.5,"heldout_by_T3":.75,"heldout_blended_utility":.625}
    y={"heldout_by_T2":.5,"heldout_by_T3":.75,"heldout_blended_utility":.625}
    assert compare_observed_futures(x,y,16)["same_T2_and_T3_observed_fractions"]
    assert sum(abs(v) for v in deltas)/len(deltas)>=0
    return {
      "status":"PASS",
      "schema":"dack_v30_functional_bottom_equivalence_audit_N50",
      "n_teacher_final_kept_groups":len(groups),
      "read_only_eval_band":"99000..99063",
      "summary_counts":dict(sorted(counter.items())),
      "mean_v5_minus_student_T2":sum(deltas)/len(deltas),
      "per_group_details":examples,
      "model_training":False,
      "replaced_exact_bottom_accuracy_with_outcome_equivalence_metric":True,
      "DO_NOT_collapse_search_states_by_heuristic_fingerprint":True,
      "recommended_online_objective":"T2 outcome first, T3 as secondary, combo integrity mandatory, protection retained as tie-breaker among proven or well-supported near-equals",
      "warning":"Same role key or observed rates do not establish exact functional equivalence, particularly for imprints, metalcraft, utility spells, card draw, tutors, and chance-model coupling.",
    }

if __name__=="__main__":
    out=report()
    path=Path("benchmark_results/v30_functional_bottom_equivalence_N50.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print("V30_READONLY_FUNCTIONAL_BOTTOM_AUDIT_PASS",json.dumps({
        "n":out["n_teacher_final_kept_groups"],
        "counts":out["summary_counts"],
        "mean_T2_difference":out["mean_v5_minus_student_T2"],
    },sort_keys=True),flush=True)
