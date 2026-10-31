#!/usr/bin/env python3
"""No-beam London v7: v6 feature proxy with independently calibrated keep size.

Exactly the same actual gameplay engine, beam-160, physical 99, outer slots
and seed mapping as v5. Only the MULLIGAN policy changes. Its hand-quality
score is not a calibrated cast probability; exact hypergeometric probabilities
are used only for individual simple draw events.

Cutoffs were selected from game IDs 10000-10511 using ONLY the fixed target
historical mean keep=5.125 (n1024 benchmark), not gameplay outcomes. A distinct
heldout ID range must test actual cast rates. Do not reuse these calibration
seeds for claims.
"""
from __future__ import annotations
import argparse,json

import dack_counterfactual_rules_v2_strict_key_20261030 as strict
import dack_mulligan_stateless_roll_v1_20261031 as dice
import dack_mulligan_analytic_policy_v6_20261031 as analytic
import dack_paired_counterfactual_v1_20261030 as ref

VERSION="dack_stable_dice_strict_nobeam_london_v7_mean5p125_train512"
POLICY="analytic_hypergeometric_keep_v7_trained_only_mean_keep"
TRAIN_SCALE=0.6090461744461209
CALIBRATED_CUTOFFS={7:0.3349754,6:0.29843263,5:0.24361847,
                    4:0.18271385,3:0.11571877,2:0.06090462,1:0.0}
TRAIN_START=10000
TRAIN_COUNT=512
HOLDOUT_START=12000

ref.rules=strict
ref.RULES_VERSION=VERSION

def install():
    dice.install()
    analytic.CUTOFFS.clear()
    analytic.CUTOFFS.update(CALIBRATED_CUTOFFS)
    analytic.POLICY_VERSION=POLICY
    ref.MULLIGAN_POLICY_NAME=POLICY
    ref.MULLIGAN_SAMPLER_NAME="none_exact_hypergeom_features_only"
    ref.choose_keep=analytic.choose_keep

def audit():
    assert strict.rule_smoke()["status"]=="PASS"
    assert dice.selftest()["status"]=="PASS"
    assert analytic.selftest()["status"]=="PASS"
    install()
    result=ref.audit()
    assert result["rules_version"]==VERSION
    return dict(result,
        mulligan_policy=POLICY,
        mulligan_beam_width=0,
        kept_hand_gameplay_beam=160,
        calibrated_cutoffs={str(k):v for k,v in CALIBRATED_CUTOFFS.items()},
        training_seed_ids=[TRAIN_START,TRAIN_START+TRAIN_COUNT-1],
        calibration_target_mean_keep=5.125,
        training_score_only=True,
        cannot_pool_v5_with_v7=True,
        no_lookahead_at_actual_future_draws=True,
        proxy_score_not_cast_probability=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--single-variant",choices=list(ref.VARIANTS))
    p.add_argument("--start",type=int,default=HOLDOUT_START)
    p.add_argument("--games",type=int,default=1)
    p.add_argument("--out",default="shards/dack_no_beam_v7_holdout.json.gz")
    p.add_argument("--store",default=None)
    a=p.parse_args()
    audit()
    if a.audit:
        print(json.dumps(audit(),indent=2),flush=True)
    elif a.single_variant:
        print("CALIBRATED_NO_BEAM_GAME",json.dumps(ref.game(a.single_variant,a.start)),flush=True)
    else:
        ref.run(a.start,a.games,a.out,a.store)
        print("CALIBRATED_NO_BEAM_POLICY_STATS",json.dumps(dict(analytic.STATS)),flush=True)
