#!/usr/bin/env python3
"""Smoke tests for bounded Phase-5 decision-cache semantics."""

from phase5_monte_carlo import Phase5DecisionCache
from phase5_production_policy import (
    PHASE5H_PRODUCTION_CACHE_MAX_ENTRIES,
    make_phase5h_production_decision_cache,
)


def test_lru_bound_and_recency():
    cache=Phase5DecisionCache(max_entries=2)
    cache.set(("a",), "A")
    cache.set(("b",), "B")
    assert len(cache)==2
    assert cache.get(("a",))=="A"  # a becomes most recently used
    cache.set(("c",), "C")
    assert len(cache)==2
    assert cache.get(("b",)) is None
    assert cache.get(("a",))=="A"
    assert cache.get(("c",))=="C"
    assert cache.stats.evictions==1


def test_update_does_not_evict():
    cache=Phase5DecisionCache(max_entries=2)
    cache.set(("a",), 1)
    cache.set(("b",), 2)
    cache.set(("a",), 3)
    assert len(cache)==2
    assert cache.stats.evictions==0
    assert cache.get(("a",))==3


def test_unbounded_provenance_mode_remains_available():
    cache=Phase5DecisionCache()
    for i in range(1000):
        cache.set((i,), i)
    assert len(cache)==1000
    assert cache.stats.evictions==0


def test_production_cache_is_bounded():
    cache=make_phase5h_production_decision_cache()
    assert cache.max_entries==PHASE5H_PRODUCTION_CACHE_MAX_ENTRIES==512


def main():
    for test in (
        test_lru_bound_and_recency,
        test_update_does_not_evict,
        test_unbounded_provenance_mode_remains_available,
        test_production_cache_is_bounded,
    ):
        test()
    print("Phase 5 bounded decision cache: PASS")


if __name__=="__main__":
    main()
