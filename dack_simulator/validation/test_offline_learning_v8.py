"""V8 offline-learning contracts. No actual beam needed for unit tests."""
from __future__ import annotations
import unittest
from collections import Counter

import dack_mulligan_learned_features_v8_20261031 as features
import dack_paired_counterfactual_v1_20261030 as ref
import dack_mulligan_analytic_policy_v6_20261031 as proxy
from dack_simulator.validation import generate_offline_london_labels_v8 as data

class TrainingProtocolTests(unittest.TestCase):
    def test_no_peek_and_all_four_outputs(self):
        gid=20001
        s=data.sample_scenario(gid,"one_key_34",stage=3,
                               max_candidates=3,draws=2)
        self.assertEqual(s["keep_n"],int(ref.sim.STAGES[3]))
        self.assertEqual(len(s["unknown"]),92)
        self.assertGreaterEqual(len(s["candidate_options"]),1)
        for hand,bottom,struct in s["candidate_options"]:
            self.assertEqual(len(hand)+len(bottom),7)
            unseen=Counter(s["unknown"])
            x=features.extract(hand,bottom,unseen,s["seat"],s["keep_n"])
            # Permuting the unknown hidden library cannot affect features.
            y=features.extract(hand,bottom,Counter(reversed(s["unknown"])),
                               s["seat"],s["keep_n"])
            self.assertEqual(x,y)
            self.assertEqual(len(x),len(features.FEATURES))
    def test_split_bands_nonoverlap(self):
        ranges=data.ALLOWED_SPLITS
        self.assertTrue(ranges["train"][1]<ranges["calibration"][0])
        self.assertTrue(ranges["calibration"][1]<ranges["policy_evaluation"][0])
        self.assertNotIn(12000,range(*ranges["train"]))
    def test_class_probabilities_are_normalized(self):
        self.assertEqual(features.selftest()["status"],"PASS")
        self.assertEqual(len(features.CARD_NAMES),len(set(features.CARD_NAMES)))
        self.assertIn("hand:Lion's Eye Diamond",features.FEATURES)
        self.assertIn("hand:Mana Vault",features.FEATURES)
        self.assertIn("hand:Plains",features.FEATURES)
    def test_mandatory_combo_piece_preferred_bottom(self):
        s=data.sample_scenario(20003,"one_key_34",stage=4,max_candidates=3)
        for hand,bottom,struct in s["candidate_options"]:
            self.assertEqual(len(hand),s["keep_n"])
            self.assertEqual(len(bottom),7-s["keep_n"])
    def test_predictor_no_search_modules(self):
        # Feature extraction does not call simulation action search.
        seat,orders=ref.stage_slots(9941044)
        seven=[ref.SLOT_VARIANTS["one_key_34"][x] for x in orders[0][:7]]
        unknown=[ref.SLOT_VARIANTS["one_key_34"][x] for x in orders[0][7:]]
        h,b,_=proxy.select_bottom(seven,7,unknown,seat)
        from unittest.mock import patch
        with patch.object(ref.d,"_win_turn_from_unknown_order",
                          side_effect=AssertionError("unexpected gameplay search")):
            v=features.extract(h,b,Counter(unknown),seat,7)
            self.assertEqual(len(v),len(features.FEATURES))

if __name__=="__main__":
    unittest.main()
