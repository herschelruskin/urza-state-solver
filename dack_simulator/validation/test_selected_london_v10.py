"""Correctness contracts for natural physical v7-selected offline labels."""
from __future__ import annotations
from collections import Counter
from unittest.mock import patch
import unittest

from dack_simulator.validation import generate_selected_london_labels_v10 as collector

class SelectedLondonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        collector.v7.audit()

    def test_deterministic_policy_selection(self):
        for gid in [21000,21001,21002,21003,31000]:
            a=collector.sample_selected(gid,"one_key_34")
            b=collector.sample_selected(gid,"one_key_34")
            self.assertEqual(a,b)
            self.assertEqual(len(a["hand"])+len(a["bottom"]),7)
            self.assertEqual(len(a["unknown"]),92)
            self.assertEqual(Counter(a["seven"])+Counter(a["unknown"]),
                             Counter(collector.ref.VARIANTS["one_key_34"]))
            self.assertEqual(a["keep_n"],len(a["hand"]))
            self.assertIn(a["keep_n"],collector.ref.sim.STAGES)
            self.assertEqual(a["policy"],collector.v7.POLICY)

    def test_no_search_invocations_during_keep_selection(self):
        with patch.object(collector.d,"_win_turn_from_unknown_order",
                          side_effect=AssertionError("beam used during selection")):
            c=collector.sample_selected(21007,"one_key_34")
        self.assertIn(c["stage"],range(len(collector.ref.sim.STAGES)))

    def test_future_order_is_not_policy_input(self):
        case=collector.sample_selected(21013,"one_key_34")
        import dack_mulligan_learned_features_v8_20261031 as features
        a=features.extract(case["hand"],case["bottom"],Counter(case["unknown"]),
                           case["seat"],case["keep_n"])
        b=features.extract(case["hand"],case["bottom"],
                           Counter(reversed(case["unknown"])),
                           case["seat"],case["keep_n"])
        self.assertEqual(a,b)

    def test_train_and_calibration_id_bands_never_overlap(self):
        self.assertLess(collector.TRAIN_LIMIT,collector.CAL_START)
        self.assertLess(collector.CAL_LIMIT,40000)

if __name__=="__main__":
    unittest.main()
