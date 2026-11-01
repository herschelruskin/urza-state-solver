#!/usr/bin/env python3
"""v30 contract tests: separate concrete exceptions from candidate neutral ties."""
from collections import Counter
import dack_paired_counterfactual_v5_stable_chance_20261031 as t
from dack_simulator.validation.v30_functional_bottom_equivalence import (
    candidate_distance,functional_fingerprint,compare_observed_futures,land
)

def option(core,kept,other):
    return {"hand":list(core)+[kept],"bottom":list(other)}

def main():
    assert t.audit()["status"]=="PASS"
    core=("Chrome Mox","Plains","Sol Ring","Mana Vault")
    white=option(core,"Touch the Spirit Realm",
                 ("Void Mirror","Charitable Levy"))
    white2=option(core,"Charitable Levy",
                 ("Void Mirror","Touch the Spirit Realm"))
    colorless=option(core,"Void Mirror",
                 ("Charitable Levy","Touch the Spirit Realm"))
    assert candidate_distance(white,colorless,seat=2)["functional_field_differences"]
    imprintwhite=candidate_distance(white,white2,seat=2)
    assert imprintwhite["hypothesized_same_deployment_capability"]
    assert imprintwhite["unproven_card_ability_may_matter"]
    core2=("Mox Opal","Plains","Sol Ring","Mana Vault")
    metal=option(core2,"Void Mirror",
                 ("Charitable Levy","Touch the Spirit Realm"))
    no_metal=option(core2,"Charitable Levy",
                 ("Void Mirror","Touch the Spirit Realm"))
    assert "metalcraft_artifact_count" in candidate_distance(
        metal,no_metal,seat=2)["functional_field_differences"]
    core3=("Ancient Tomb","Mana Vault","Plains","Enlightened Tutor")
    assert candidate_distance(
        option(core3,"Touch the Spirit Realm",("Void Mirror","Charitable Levy")),
        option(core3,"Charitable Levy",("Void Mirror","Touch the Spirit Realm")),
        seat=1
    )["hypothesized_same_deployment_capability"]
    # Unlike exact teacher-index imitation, a mathematical regret objective
    # assigns no penalty to different cards with identical observed speed.
    q={"heldout_by_T2":.375,"heldout_by_T3":.875,"heldout_blended_utility":.625}
    assert compare_observed_futures(q,dict(q),16)["same_T2_and_T3_observed_fractions"]
    assert compare_observed_futures(q,dict(q),16)["delta_v5_minus_student_U"]==0.
    assert land("Ancient Tomb") and land("Razorgrass Ambush")
    print("DACK_V30_BOTTOM_FUNCTIONAL_HYPOTHESIS_SELFTEST_PASS",flush=True)

if __name__=="__main__":main()
