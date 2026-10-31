"""Exact physical and no-oracle contracts for v9 stratified data collection."""
from __future__ import annotations
from collections import Counter
from unittest.mock import patch
import unittest

from dack_simulator.validation import generate_stratified_london_labels_v9 as generator

class StratifiedLondonTests(unittest.TestCase):
    def test_schedule_covers_natural_and_fast(self):
        self.assertEqual(len(generator.SCHEDULE),18)
        self.assertEqual(sum(x=="natural" for x in generator.SCHEDULE),6)
        self.assertGreaterEqual(len(generator.FAST_CORES),10)
        self.assertEqual(generator.stratum_for(20000,"train"),"natural")
        self.assertEqual(generator.stratum_for(30000,"calibration"),"natural")

    def test_all_enriched_openings_are_physical(self):
        for split,base in (("train",20000),("calibration",30000)):
            for k in range(len(generator.SCHEDULE)):
                gid=base+k
                c=generator.conditioned_opening(gid,"one_key_34",split)
                self.assertEqual(c["kind"],generator.SCHEDULE[k])
                self.assertEqual(len(c["seven"]),7)
                self.assertEqual(len(c["unknown"]),92)
                self.assertEqual(len(c["sampled_order"]),99)
                self.assertEqual(len(set(c["sampled_order"])),99)
                self.assertEqual(Counter(c["seven"])+Counter(c["unknown"]),
                                 Counter(generator.ref.VARIANTS["one_key_34"]))
                for name in c["forced_core"]:
                    self.assertIn(name,c["seven"])
                if c["kind"]!="natural":
                    self.assertEqual(c["keep_n"],7)
                if c["kind"].startswith("gemstone"):
                    self.assertNotEqual(c["seat"],0)

    def test_seed_determinism(self):
        for gid in (20001,20002,20006,20013,30001):
            split="train" if gid<30000 else "calibration"
            a=generator.conditioned_opening(gid,"one_key_34",split)
            b=generator.conditioned_opening(gid,"one_key_34",split)
            self.assertEqual(a,b)

    def test_creature_exclusion_from_fast_core_list(self):
        for core in generator.FAST_CORES.values():
            self.assertTrue(set(core).issubset(set(generator.ref.VARIANTS["one_key_34"])))
            self.assertFalse(set(core)&set(generator.d.COMBO_CREATURES))

    def test_features_ignore_sampled_library_order(self):
        import dack_mulligan_learned_features_v8_20261031 as features
        for gid in (20001,20003,20006,20013):
            c=generator.conditioned_opening(gid,"one_key_34","train")
            options=generator.base.candidates(c["seven"],c["keep_n"],
                                               c["unknown"],c["seat"],2)
            self.assertGreaterEqual(len(options),1)
            for hand,bottom,struct in options:
                with patch.object(generator.d,"_win_turn_from_unknown_order",
                                  side_effect=AssertionError("beam during features")):
                    a=features.extract(hand,bottom,Counter(c["unknown"]),
                                       c["seat"],c["keep_n"])
                    b=features.extract(hand,bottom,Counter(reversed(c["unknown"])),
                                       c["seat"],c["keep_n"])
                self.assertEqual(a,b)
if __name__=="__main__":
    unittest.main()
