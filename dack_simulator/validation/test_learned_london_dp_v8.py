"""No-beam learned-policy/backward-London-DP tests with constant synthetic model."""
from __future__ import annotations
import json
import unittest
from unittest.mock import patch

import dack_mulligan_learned_features_v8_20261031 as features
import dack_paired_counterfactual_v1_20261030 as ref
import dack_paired_counterfactual_v8_learned_london_20261031 as policy
from dack_simulator.validation import derive_learned_london_dp_v8 as dp

def constant_model():
    return {
        "schema":"dack_london_multiclass_softmax_v8",
        "classes":[0,1,2,3],
        "feature_sha256":features.feature_hash(),
        "coef":[[0.]*len(features.FEATURES) for _ in range(4)],
        "intercept":[0.,0.,0.,0.],
        "temperature":1.
    }

class LearnedPolicyTests(unittest.TestCase):
    def test_backward_thresholds_handle_free_seven(self):
        m=constant_model()
        table=dp.calibrate(m,"one_key_34",samples=2,start=50000)
        self.assertEqual(table["stage_keep_counts"],list(ref.sim.STAGES))
        for seat in range(4):
            s=table["seats"][str(seat)]
            self.assertEqual(len(s["thresholds_by_london_stage"]),len(ref.sim.STAGES))
            self.assertAlmostEqual(s["thresholds_by_london_stage"][0],.625,places=9)
            self.assertAlmostEqual(s["thresholds_by_london_stage"][1],.625,places=9)
            self.assertEqual(s["thresholds_by_london_stage"][-1],0.)
    def test_model_scoring_no_gameplay_beam_or_future_peek(self):
        m=constant_model()
        fake=dp.calibrate(m,"one_key_34",samples=2,start=50000)
        policy.MODEL=m
        policy.CONTINUATIONS={"one_key_34":fake}
        policy.POLICY_HASH="synthetic-only"
        seat,stages=ref.stage_slots(712928881)
        deck=ref.SLOT_VARIANTS["one_key_34"]
        with patch.object(ref.d,"_win_turn_from_unknown_order",
                          side_effect=AssertionError("unexpected beam")):
            state,hist=policy.choose_keep(deck,seat,stages)
        self.assertEqual(len(hist),1)
        self.assertEqual(hist[0]["keep_n"],7)
        self.assertEqual(state.hand,tuple(sorted(state.hand)))
        self.assertAlmostEqual(sum(hist[0][k] for k in (
            "predicted_T1","predicted_T2_exact",
            "predicted_T3_exact","predicted_fail_by_T3")),1.)
        self.assertEqual(len(state.hand)+len(state.library),99)
    def test_training_model_is_required(self):
        policy.MODEL=None
        policy.CONTINUATIONS={}
        policy.POLICY_HASH=None
        seat,stages=ref.stage_slots(712928881)
        with self.assertRaises(RuntimeError):
            policy.choose_keep(ref.SLOT_VARIANTS["one_key_34"],seat,stages)

if __name__=="__main__":
    unittest.main()
