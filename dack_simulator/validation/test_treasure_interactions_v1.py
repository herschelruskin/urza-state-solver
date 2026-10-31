"""Extended Oracle interaction tests for Treasure Vault and Staff v1."""
from __future__ import annotations
from dataclasses import replace
import unittest

import dack_counterfactual_rules_v1_20261030 as rules

d = rules.d


class TreasureInteractions(unittest.TestCase):
    def test_moonsilver_key_retrieves_artifact_land_with_mana_ability(self):
        # Moonsilver Key searches for a basic land or artifact with a mana ability.
        s = d.State(1, (), ("Treasure Vault",),
                    battlefield=(d.Perm("Moonsilver Key"),), c=1)
        choices = d.v03_actions(s)
        self.assertTrue(any(
            "Treasure Vault" in q.hand and "Moonsilver Key" in q.grave
            for q in choices), "Moonsilver should be able to find Treasure Vault")

    def test_treasure_vault_counts_as_artifact_and_uses_exact_2x_cost(self):
        s = d.State(1, (), (), battlefield=(
            d.Perm("Treasure Vault"), d.Perm("Mox Opal"), d.Perm("Sol Ring")))
        self.assertTrue(d.metalcraft(s))
        x1 = d.State(1, (), (), battlefield=(d.Perm("Treasure Vault"),), c=2)
        out = rules.vault_activation_actions(x1)
        self.assertTrue(any(q.treasures == 1 and q.c == 0
                            and "Treasure Vault" in q.grave for q in out))
        self.assertFalse(any(q.treasures >= 2 for q in out))
        x2 = replace(x1, c=4)
        self.assertTrue(any(q.treasures == 2 and q.c == 0
                            for q in rules.vault_activation_actions(x2)))

    def test_vault_cannot_self_fund_sacrifice_ability(self):
        s = d.State(1, (), (), battlefield=(d.Perm("Treasure Vault"),))
        tapped = next(q for q in d.tap_mana_actions(s)
                      if q.c == 1 and q.battlefield[0].tapped)
        self.assertFalse(rules.vault_activation_actions(tapped))
        s = replace(s, c=1)
        self.assertFalse(rules.vault_activation_actions(s))
        s = replace(s, c=2)
        self.assertTrue(rules.vault_activation_actions(s))

    def test_staff_can_pay_life_once_and_destroy_an_owned_permanent(self):
        s = d.State(1, (), (), battlefield=(d.Perm("Staff of Compleation"),
                                            d.Perm("Trinisphere")))
        out = rules.staff_destroy_actions(s)
        self.assertTrue(any(
            "Trinisphere" in q.grave and q.battlefield[0].tapped
            and rules.STAFF_LIFE1 in q.exile for q in out))
        self.assertFalse(any(
            "Trinisphere" in q.grave and q.battlefield[0].tapped is False
            for q in out))

    def test_staff_destroy_cannot_be_used_after_spending_last_life(self):
        spent = d.State(1, (), (), battlefield=(d.Perm("Staff of Compleation"),),
                        exile=(rules.newer.STAFF_LIFE4,)*9
                              + (rules.STAFF_LIFE1,)*3)
        self.assertFalse(rules.staff_destroy_actions(spent))
        self.assertEqual(rules.staff_life_spent(spent),39)


if __name__ == "__main__":
    unittest.main()
