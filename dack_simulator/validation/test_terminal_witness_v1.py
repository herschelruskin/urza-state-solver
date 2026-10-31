"""Equivalence tests for a scoped early-winning-witness search."""
from __future__ import annotations
import unittest
import dack_mulligan_terminal_witness_v1_20261031 as witness

d=witness.d

class TerminalWitnessContracts(unittest.TestCase):
    def test_winning_frontier_equivalence(self):
        trio=tuple(sorted(d.COMBO_CREATURES))
        no=d.State(1,(),trio)
        yes=d.State(1,(),trio,w=2,c=4)
        refwins,_=witness._ORIGINAL_SEARCH([no,yes],beam=60,depth=2)
        wins,_=witness.search_turn_frontier_win_only([no,yes],beam=60,depth=2)
        self.assertEqual(bool(wins),bool(refwins))
        self.assertTrue(wins)
        self.assertEqual(wins[0],yes)
        self.assertGreaterEqual(witness.counters["terminal_witnesses"],1)

    def test_losing_frontier_same_survivors(self):
        trio=tuple(sorted(d.COMBO_CREATURES))
        no=d.State(1,(),trio)
        oldwin,oldstates=witness._ORIGINAL_SEARCH([no],beam=60,depth=2)
        newwin,newstates=witness.search_turn_frontier_win_only([no],beam=60,depth=2)
        self.assertEqual(oldwin,newwin)
        self.assertEqual(oldstates,newstates)

    def test_mulligan_only_scoped_install(self):
        witness.uninstall()
        self.assertIs(d.search_turn_frontier_many,witness._ORIGINAL_SEARCH)
        witness.install()
        self.assertIs(d.keep_weighted_ev_seat,witness.certified_keep_weighted_ev_seat)
        self.assertIs(witness.bounded._rollout_prefix,
                      witness.certified_bounded_rollout_prefix)
        self.assertIs(d.search_turn_frontier_many,witness._ORIGINAL_SEARCH)
        with witness.conditional_win_only():
            self.assertIs(d.search_turn_frontier_many,
                          witness.search_turn_frontier_win_only)
        self.assertIs(d.search_turn_frontier_many,witness._ORIGINAL_SEARCH)
        witness.uninstall()

if __name__=="__main__":
    unittest.main()
