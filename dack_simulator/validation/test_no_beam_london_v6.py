"""Fast analytic mulligan policy contract and hidden-order safety tests."""
from __future__ import annotations
import unittest
from unittest.mock import patch

import dack_mulligan_analytic_policy_v6_20261031 as analytic
import dack_paired_counterfactual_v1_20261030 as ref

class NoBeamPolicyTests(unittest.TestCase):
    def test_exact_hypergeometric(self):
        p=analytic.hypergeom_p_at_least_one
        self.assertEqual(p(92,0,3),0.)
        self.assertEqual(p(92,92,3),1.)
        self.assertAlmostEqual(p(92,1,3),3/92)
        self.assertAlmostEqual(p(92,3,1),3/92)
        self.assertEqual(p(92,10,0),0.)

    def test_no_information_leak_from_actual_draw_order(self):
        seat,orders=ref.stage_slots(int(ref.SPEC["seed_base"])+2000006)
        deck=ref.SLOT_VARIANTS["one_key_34"]
        cards=tuple(deck[x] for x in orders[0])
        seven,unknown=cards[:7],cards[7:]
        a=analytic.select_bottom(seven,5,unknown,seat)
        b=analytic.select_bottom(seven,5,tuple(reversed(unknown)),seat)
        self.assertEqual(a,b)

    def test_no_gameplay_beam_during_mulligan(self):
        seat,orders=ref.stage_slots(int(ref.SPEC["seed_base"])+2000006)
        deck=ref.SLOT_VARIANTS["one_key_34"]
        # Any beam evaluation attempted by the policy is a hard regression.
        with patch.object(analytic.d,"_win_turn_from_unknown_order",
                          side_effect=AssertionError("beam invoked in mulligan")):
            state,history=analytic.choose_keep(deck,seat,orders)
        self.assertGreaterEqual(len(history),1)
        self.assertEqual(len(state.library)+len(state.hand),99)
        self.assertEqual(state.hand,tuple(sorted(state.hand)))
        self.assertEqual(history[-1]["kept"],True)
        self.assertTrue(all(x["sampled_t1"] is None for x in history))
        self.assertTrue(all(x["policy"]==analytic.POLICY_VERSION for x in history))

    def test_combo_creature_bottoming_when_allowed(self):
        seven=("Plains","Plains","Lion's Eye Diamond","Mana Vault",
               "Boonweaver Giant","Arcane Signet","Grim Monolith")
        hand,bottom,_=analytic.select_bottom(seven,6,(),seat=3)
        self.assertEqual(bottom,("Boonweaver Giant",))
        self.assertNotIn("Boonweaver Giant",hand)

    def test_bricked_proxy_zero_without_repair(self):
        feature=analytic.proxy_features(("Boonweaver Giant","Plains","Sol Ring"),(),0)
        self.assertEqual(feature["proxy_utility"],0)

if __name__=="__main__":
    unittest.main()
