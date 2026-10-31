"""Cheap contract tests for the isolated full-replay paired counterfactual runner."""
from __future__ import annotations
import unittest

import dack_paired_counterfactual_v1_20261030 as run


class CounterfactualContracts(unittest.TestCase):
    def test_physical_manifest_and_rules(self):
        self.assertEqual(run.audit()["status"], "PASS")
        self.assertEqual(len(run.VARIANTS), 9)

    def test_canonical_slot_permutation_is_repeatable(self):
        for gid in (0, 1, 19):
            seed = int(run.SPEC["seed_base"]) + gid * run.SEED_STRIDE
            a = run.stage_slots(seed)
            self.assertEqual(a, run.stage_slots(seed))
            seat, stages = a
            self.assertIn(seat, range(4))
            self.assertEqual(len(stages), 8)
            for slots in stages:
                self.assertEqual(len(slots), 99)
                self.assertEqual(set(slots), set(run.SLOTS))
        self.assertNotEqual(run.stage_slots(int(run.SPEC["seed_base"])),
                            run.stage_slots(int(run.SPEC["seed_base"]) + run.SEED_STRIDE))

    def test_candidate_maps_are_one_slot_swaps(self):
        physical = run.PHYSICAL
        baseline = run.BASE_SLOTS
        changed = [slot for slot in run.SLOTS if physical[slot] != baseline[slot]]
        self.assertEqual(len(changed), 1)
        self.assertEqual((physical[changed[0]], baseline[changed[0]]),
                         ("Tooth of Ramos", "Voltaic Key"))
        for name, names in run.SLOT_VARIANTS.items():
            diffs = [slot for slot in run.SLOTS if names[slot] != baseline[slot]]
            self.assertEqual(len(diffs), 0 if name == "one_key_34" else 1)
            if diffs:
                self.assertEqual(names[diffs[0]], "Plains")
                self.assertEqual(baseline[diffs[0]],
                                 run.SPEC["variants"][name][0][0])
        self.assertEqual(run.VARIANTS["one_key_34"].count("Plains"), 10)

    def test_slot_assignment_keeps_duplicate_plains_distinct(self):
        seven = list(run.SLOTS[:7])
        cards = ["Plains", "Sol Ring", "Plains", "Staff of Compleation",
                 "Gemstone Caverns", "Plains", "Island"]
        picked = run.selected_slots(seven, cards, ["Plains", "Plains", "Island"])
        self.assertEqual(picked, [seven[0], seven[2], seven[6]])

    def test_zero_is_a_loss_not_success(self):
        self.assertFalse(run.t2_success(0))
        self.assertTrue(run.t2_success(1))
        self.assertTrue(run.t2_success(2))
        self.assertFalse(run.t2_success(3))

    def test_paired_confidence_from_discordant_games(self):
        control = "one_key_34"
        challenger = "staff_plains_35"
        rows = []
        for gid, (a, b) in enumerate(((0, 2), (2, 0), (0, 0), (3, 2))):
            rows.append({"game_id": gid, "seat": 0, "arms": {
                name: {"win_turn": a if name == control else
                       b if name == challenger else a,
                       "keep_n": 7}
                for name in run.VARIANTS}})
        out = run.metrics(rows)
        self.assertEqual(out["n"], 4)
        d = out["paired_vs_control"][challenger]["T2"]
        self.assertEqual((d["gains"], d["losses"], d["ties"]), (2, 1, 1))
        self.assertEqual(d["delta_pp"], 25.0)
        self.assertEqual(out["arms"][control]["T2_pct"], 25.0)
        self.assertEqual(out["arms"][challenger]["T2_pct"], 50.0)

    def test_same_card_slot_is_seen_with_same_outer_london_order(self):
        seat, stages = run.stage_slots(int(run.SPEC["seed_base"]))
        baseline = run.SLOT_VARIANTS["one_key_34"]
        altered = run.SLOT_VARIANTS["staff_plains_35"]
        slot = next(s for s in run.SLOTS if baseline[s] != altered[s])
        for stage in stages:
            seven_a = [baseline[s] for s in stage[:7]]
            seven_b = [altered[s] for s in stage[:7]]
            self.assertEqual([i for i,(a,b) in enumerate(zip(seven_a,seven_b))
                              if a != b], ([stage[:7].index(slot)]
                                          if slot in stage[:7] else []))


if __name__ == "__main__":
    unittest.main()
