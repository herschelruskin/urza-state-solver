#!/usr/bin/env python3
"""USER-CONFIRMED live Boonweaver deck state, October 28, 2026.

The physical/current 99 replaced WORLD MAP with GIANT'S BOULDER.
This is distinct from the previously frozen historical "current" control
used by prior published benchmarking scripts. Do not silently overwrite the
archived baseline: import ACTUAL_CURRENT_99 for NEW tests.

Other recent proposals (4 real rainbow land replacements; Voltaic Key,
Pentad Prism, Basalt/Tooth/Implements/Everflowing cuts) are hypotheses,
not user-confirmed live-deck swaps.
"""
from collections import Counter
import dack_active_mulligan_policy as sim

HISTORICAL_CURRENT_99=tuple(sim.FROZEN_DECK)
CONFIRMED_OUT=("World Map",)
CONFIRMED_IN=("Giant's Boulder",)
LOCKED_COMBO_SUPPORT=frozenset(("Hardlight Containment","Lunarch Mantle"))
COMBO_CREATURES=frozenset(("Boonweaver Giant","Preston, the Vanisher","Roaming Throne"))
HYPOTHETICAL_FOUR_REAL_RAINBOW=(
    "City of Brass","Mana Confluence","Tarnished Citadel","Gemstone Mine",
)

def swaps(deck,replacements):
    cards=list(deck)
    for old,new in replacements:
        assert old in cards and (old=="Plains" or cards.count(old)==1)
        assert new=="Plains" or new not in cards
        cards[cards.index(old)]=new
    return tuple(cards)

ACTUAL_CURRENT_99=swaps(
    HISTORICAL_CURRENT_99,(("World Map","Giant's Boulder"),))
EXPLORATORY_RAINBOW_99=swaps(
    ACTUAL_CURRENT_99,tuple(("Plains",land)
                            for land in HYPOTHETICAL_FOUR_REAL_RAINBOW))

def audit():
    assert len(HISTORICAL_CURRENT_99)==len(ACTUAL_CURRENT_99)==99
    assert len(EXPLORATORY_RAINBOW_99)==99
    assert sim.deck_hash(HISTORICAL_CURRENT_99)==sim.FROZEN_DECK_HASH
    assert Counter(ACTUAL_CURRENT_99)-Counter(HISTORICAL_CURRENT_99)==Counter(CONFIRMED_IN)
    assert Counter(HISTORICAL_CURRENT_99)-Counter(ACTUAL_CURRENT_99)==Counter(CONFIRMED_OUT)
    assert "World Map" not in ACTUAL_CURRENT_99
    assert ACTUAL_CURRENT_99.count("Giant's Boulder")==1
    assert ACTUAL_CURRENT_99.count("Staff of Compleation")==1
    assert LOCKED_COMBO_SUPPORT.issubset(ACTUAL_CURRENT_99)
    assert COMBO_CREATURES.issubset(ACTUAL_CURRENT_99)
    for cards in (ACTUAL_CURRENT_99,EXPLORATORY_RAINBOW_99):
        assert len([x for x in cards if x!="Plains"])==len(set(x for x in cards if x!="Plains"))
        assert not {"Mana Crypt","Jeweled Lotus"}.intersection(cards)
        assert all(x in sim.d.CARD_ID for x in cards)
        assert sum(x in sim.d.LANDS or x in ("Emeria's Call","Razorgrass Ambush") for x in cards)==34
    assert ACTUAL_CURRENT_99.count("Plains")==HISTORICAL_CURRENT_99.count("Plains")
    assert EXPLORATORY_RAINBOW_99.count("Plains")==ACTUAL_CURRENT_99.count("Plains")-4
    assert all(x in EXPLORATORY_RAINBOW_99 for x in HYPOTHETICAL_FOUR_REAL_RAINBOW)
    assert "Command Tower" not in HYPOTHETICAL_FOUR_REAL_RAINBOW
    return {"status":"PASS","live_deck_hash":sim.deck_hash(ACTUAL_CURRENT_99),
            "historical_hash":sim.FROZEN_DECK_HASH,
            "rainbow_hypothesis_hash":sim.deck_hash(EXPLORATORY_RAINBOW_99),
            "confirmed_swap":"World Map -> Giant's Boulder",
            "land_count":34,"live_plains":ACTUAL_CURRENT_99.count("Plains"),
            "other_changes":"exploratory only; not user-confirmed"}

if __name__=="__main__":
    import json
    print("DACK_ACTUAL_CURRENT_BOULDER_AUDIT",json.dumps(audit()),flush=True)
