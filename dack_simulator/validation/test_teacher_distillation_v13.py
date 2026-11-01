"""Teacher v5 stage imitation data and line-aware student no-peek contracts."""
from __future__ import annotations
from collections import Counter
from unittest.mock import patch
import unittest
import dack_mulligan_teacher_features_v13_20261031 as features
from dack_simulator.validation import collect_teacher_london_v13 as collector

class TeacherImitationContracts(unittest.TestCase):
    def test_all_candidates_match_original_top12_ranking(self):
        deck=collector.ref.SLOT_VARIANTS["one_key_34"]
        seat,orders=collector.ref.stage_slots(1231243)
        for keep_n in (7,6,5,4,3,2,1):
            order=orders[0]
            seven=[deck[x] for x in order[:7]]
            unknown=[deck[x] for x in order[7:]]
            rows=collector.finalists(seven,keep_n,unknown)
            self.assertTrue(1<=len(rows)<=12)
            expected=sorted((tuple(r["struct_rank"]) for r in rows),reverse=True)
            self.assertEqual([tuple(r["struct_rank"]) for r in rows],expected)
            self.assertEqual(len(rows),min(12,__import__("math").comb(7,7-keep_n)))
            for rank,row in enumerate(rows):
                self.assertEqual(Counter(row["hand"])+Counter(row["bottom"]),Counter(seven))
                self.assertEqual(len(row["hand"]),keep_n)
                x=features.extract(seven,row["hand"],row["bottom"],
                    Counter(unknown),seat,keep_n,0,row["struct_rank"],rank)
                self.assertEqual(len(x),len(features.FEATURES))
    def test_hidden_draw_order_never_enters_features(self):
        deck=collector.ref.SLOT_VARIANTS["one_key_34"]
        seat,orders=collector.ref.stage_slots(1231243)
        seven=[deck[x] for x in orders[2][:7]]
        rest=[deck[x] for x in orders[2][7:]]
        row=collector.finalists(seven,5,rest)[0]
        x=features.extract(seven,row["hand"],row["bottom"],
            Counter(rest),seat,5,2,row["struct_rank"],0)
        y=features.extract(seven,row["hand"],row["bottom"],
            Counter(reversed(rest)),seat,5,2,row["struct_rank"],0)
        self.assertEqual(x,y)
    def test_feature_manifest(self):
        self.assertEqual(features.selftest()["status"],"PASS")
    def test_split_no_overlap(self):
        splits=collector.SPLITS
        self.assertLess(splits["train"][1],splits["validation"][0])
        self.assertLess(splits["validation"][1],splits["imitation_test"][0])
if __name__=="__main__":unittest.main()
