"""Fast, deterministic original-vs-bounded bottom-choice parity witnesses."""
from __future__ import annotations

import unittest
from unittest.mock import patch

import dack_mulligan_branchbound_v1_20261031 as fast

d=fast.d

def deterministic_win(hand, library, seat, beam, max_turn=3):
    """A zero-cost controlled rollout to cover early winner and loser cases."""
    if "Lion's Eye Diamond" in hand and "Mana Vault" in hand:
        return 1
    if "Boonweaver Giant" in hand:
        return 0
    if "Plains" in hand and "Mana Vault" in hand:
        return 2
    if "Grim Monolith" in library[:3] and "Plains" in hand:
        return 3
    return 0

class BoundPreservesExactOriginal(unittest.TestCase):
    def test_no_shortcut_can_beat_an_unfinished_upper_bound(self):
        f=fast._proven_uncompetitive
        self.assertFalse(f(0,0,8,.9,(1,0,0),(2,0,0),.5))
        self.assertTrue(f(0,2,8,.9,(1,0,0),(2,0,0),.5))
        self.assertFalse(f(1,2,8,.2,(1,0,0),(2,0,0),.5))
        self.assertTrue(f(4,8,8,.5,(1,0,0),(2,0,0),.5))
        self.assertFalse(f(4,8,8,.5,(3,0,0),(2,0,0),.5))

    def test_original_and_bounded_return_identical_complete_winner(self):
        seven_candidates=[
            ("Lion's Eye Diamond","Mana Vault","Plains","Grim Monolith",
             "Boonweaver Giant","Sol Ring","Arcane Signet"),
            ("Plains","Plains","Lion's Eye Diamond","Boonweaver Giant",
             "Mana Vault","Grim Monolith","Gemstone Caverns"),
            ("Grim Monolith","Plains","Sol Ring","Basalt Monolith",
             "Staff of Compleation","Brainstone","Cavern of Souls"),
        ]
        rest=("Plains",)*90 + ("Grim Monolith","Brainstone")
        calls=0
        with patch.object(d,"_win_turn_from_unknown_order",side_effect=deterministic_win):
            for seven in seven_candidates:
                for keep_n in (7,6,5,4,3):
                    d._WEIGHTED_SEAT_CACHE.clear()
                    expected=fast._ORIGINAL(
                        seven,keep_n,rest,seat=1,
                        beam=60,samples=8,t3_weight=.5,finalists_n=12)
                    d._WEIGHTED_SEAT_CACHE.clear()
                    fast.reset_statistics()
                    actual=fast.bounded_bottom_weighted_ev_seat(
                        seven,keep_n,rest,seat=1,
                        beam=60,samples=8,t3_weight=.5,finalists_n=12)
                    self.assertEqual(actual,expected,(seven,keep_n))
                    calls+=1
        self.assertEqual(calls,15)
        # Under these deterministic witnesses, at least one dominated
        # candidate can be pruned, but all chosen best results are identical.

if __name__=="__main__":
    unittest.main()
