#!/usr/bin/env python3
"""Symbolic action-space primitives for Phase-5.

Large action families are represented without materializing every concrete leaf:
integer bitsets, reduced ZDDs, factored DAGs, exact Pareto frontiers, and
caller-bounded exact branch-and-bound traversal.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from heapq import heappop, heappush
from itertools import count
from math import comb
from typing import Callable, Generic, Iterable, Iterator, Sequence, Tuple, TypeVar

SYMBOLIC_ACTION_SPACE_VERSION = "urza-symbolic-action-space-v1"
T = TypeVar("T")
V = TypeVar("V")

def bit(index: int) -> int:
    if int(index) < 0:
        raise ValueError("bit index must be >= 0")
    return 1 << int(index)

def has_bit(mask: int, index: int) -> bool:
    return bool(int(mask) & bit(index))

def add_bit(mask: int, index: int) -> int:
    return int(mask) | bit(index)

def remove_bit(mask: int, index: int) -> int:
    return int(mask) & ~bit(index)

def bit_count(mask: int) -> int:
    return int(mask).bit_count()

def iter_bits(mask: int) -> Iterator[int]:
    value = int(mask)
    while value:
        lsb = value & -value
        yield lsb.bit_length() - 1
        value ^= lsb

def highest_bit(mask: int) -> int:
    value = int(mask)
    return -1 if value == 0 else value.bit_length() - 1

ZDD_FALSE = 0
ZDD_TRUE = 1

@dataclass(frozen=True, slots=True)
class ZDDNode:
    variable: int
    low: int
    high: int

@dataclass(frozen=True, slots=True)
class ZDDStats:
    variable_count: int
    node_count: int
    represented_sets: int
    min_cardinality: int
    max_cardinality: int

class CardinalityZDD:
    """Reduced ZDD for subsets whose size lies in a closed cardinality range."""

    __slots__ = (
        "variable_count", "min_k", "max_k", "nodes", "root", "_count_cache"
    )

    def __init__(self, variable_count: int, min_k: int, max_k: int):
        n = int(variable_count)
        lo = int(min_k)
        hi = int(max_k)
        if n < 0:
            raise ValueError("variable_count must be >= 0")
        if lo < 0 or hi < lo or hi > n:
            raise ValueError("require 0 <= min_k <= max_k <= variable_count")
        self.variable_count = n
        self.min_k = lo
        self.max_k = hi
        nodes = [None, None]
        unique = {}

        @lru_cache(maxsize=None)
        def build(index: int, chosen: int) -> int:
            remaining = n - index
            if chosen > hi or chosen + remaining < lo:
                return ZDD_FALSE
            if index == n:
                return ZDD_TRUE if lo <= chosen <= hi else ZDD_FALSE
            low = build(index + 1, chosen)
            high = build(index + 1, chosen + 1)
            if high == ZDD_FALSE:
                return low
            key = (index, low, high)
            existing = unique.get(key)
            if existing is not None:
                return existing
            node_id = len(nodes)
            unique[key] = node_id
            nodes.append(ZDDNode(index, low, high))
            return node_id

        self.root = build(0, 0)
        self.nodes = tuple(nodes)
        self._count_cache = {}

    def node(self, node_id: int) -> ZDDNode:
        node = self.nodes[int(node_id)]
        if node is None:
            raise ValueError("terminal ZDD id does not have a node")
        return node

    def count_sets(self, node_id: int | None = None) -> int:
        root = self.root if node_id is None else int(node_id)
        cached = self._count_cache.get(root)
        if cached is not None:
            return cached
        if root == ZDD_FALSE:
            return 0
        if root == ZDD_TRUE:
            return 1
        node = self.node(root)
        value = self.count_sets(node.low) + self.count_sets(node.high)
        self._count_cache[root] = value
        return value

    def stats(self) -> ZDDStats:
        represented = sum(
            comb(self.variable_count, k)
            for k in range(self.min_k, self.max_k + 1)
        )
        actual = self.count_sets()
        if actual != represented:
            raise AssertionError((actual, represented))
        return ZDDStats(
            variable_count=self.variable_count,
            node_count=max(0, len(self.nodes) - 2),
            represented_sets=actual,
            min_cardinality=self.min_k,
            max_cardinality=self.max_k,
        )

    def contains_mask(self, mask: int) -> bool:
        return self.min_k <= bit_count(mask) <= self.max_k and not (
            int(mask) >> self.variable_count
        )

    def iter_masks(self) -> Iterator[int]:
        def walk(current: int, mask: int):
            if current == ZDD_FALSE:
                return
            if current == ZDD_TRUE:
                yield mask
                return
            node = self.node(current)
            yield from walk(node.low, mask)
            yield from walk(node.high, add_bit(mask, node.variable))
        yield from walk(self.root, 0)

    def has_completion(self, *, start_index: int, chosen_count: int) -> bool:
        start = int(start_index)
        chosen = int(chosen_count)
        if not 0 <= start <= self.variable_count:
            return False
        remaining = self.variable_count - start
        return not (
            chosen > self.max_k
            or chosen + remaining < self.min_k
        )

    def can_finish(self, mask: int) -> bool:
        return self.min_k <= bit_count(mask) <= self.max_k

    def next_include_indices(self, mask: int) -> Tuple[int, ...]:
        selected = int(mask)
        chosen = bit_count(selected)
        start = highest_bit(selected) + 1
        rows = []
        for index in range(start, self.variable_count):
            if self.has_completion(
                start_index=index + 1,
                chosen_count=chosen + 1,
            ):
                rows.append(index)
        return tuple(rows)

@lru_cache(maxsize=256)
def cached_cardinality_zdd(
    variable_count: int, min_k: int, max_k: int
) -> CardinalityZDD:
    return CardinalityZDD(
        int(variable_count), int(min_k), int(max_k)
    )

@dataclass(frozen=True, slots=True)
class ActionDAGEdge(Generic[T]):
    label: T
    child: int

@dataclass(frozen=True, slots=True)
class ActionDAGNode(Generic[T]):
    node_id: int
    edges: Tuple[ActionDAGEdge[T], ...] = ()
    terminal: bool = False

class FactoredActionDAG(Generic[T]):
    """Immutable node-addressed DAG with lazy concrete path traversal."""

    def __init__(self, nodes: Sequence[ActionDAGNode[T]], root: int):
        rows = tuple(nodes)
        table = {int(node.node_id): node for node in rows}
        if len(table) != len(rows):
            raise ValueError("Action DAG node ids must be unique")
        if int(root) not in table:
            raise ValueError("Action DAG root is absent")
        for node in table.values():
            for edge in node.edges:
                if int(edge.child) not in table:
                    raise ValueError(
                        f"Action DAG child {edge.child} is absent"
                    )
        self._nodes = table
        self.root = int(root)

    def node(self, node_id: int) -> ActionDAGNode[T]:
        return self._nodes[int(node_id)]

    def iter_paths(self) -> Iterator[Tuple[T, ...]]:
        stack = [(self.root, ())]
        while stack:
            node_id, path = stack.pop()
            node = self.node(node_id)
            if node.terminal:
                yield path
            for edge in reversed(node.edges):
                stack.append((edge.child, path + (edge.label,)))

    def node_count(self) -> int:
        return len(self._nodes)

@dataclass(frozen=True, slots=True)
class ParetoPoint(Generic[T]):
    value: T
    maximize: Tuple[float, ...]
    minimize: Tuple[float, ...] = ()

def pareto_dominates(a: ParetoPoint, b: ParetoPoint) -> bool:
    if len(a.maximize) != len(b.maximize) or len(a.minimize) != len(b.minimize):
        raise ValueError("Pareto points have incompatible dimensions")
    no_worse = (
        all(x >= y for x, y in zip(a.maximize, b.maximize))
        and all(x <= y for x, y in zip(a.minimize, b.minimize))
    )
    strictly = (
        any(x > y for x, y in zip(a.maximize, b.maximize))
        or any(x < y for x, y in zip(a.minimize, b.minimize))
    )
    return bool(no_worse and strictly)

class ParetoFrontier(Generic[T]):
    """Exact nondominated set under caller-proven monotone dimensions."""

    def __init__(self):
        self._rows = []

    def add(self, point: ParetoPoint[T]) -> bool:
        if any(pareto_dominates(row, point) for row in self._rows):
            return False
        self._rows = [
            row for row in self._rows
            if not pareto_dominates(point, row)
        ]
        self._rows.append(point)
        return True

    def rows(self) -> Tuple[ParetoPoint[T], ...]:
        return tuple(self._rows)

@dataclass(frozen=True, slots=True)
class BranchBoundResult(Generic[T, V]):
    best_item: T | None
    best_value: V | None
    evaluated_leaves: int
    pruned_nodes: int

def branch_and_bound(
    *,
    root: T,
    is_terminal: Callable[[T], bool],
    children: Callable[[T], Iterable[T]],
    upper_bound: Callable[[T], V],
    evaluate: Callable[[T], V],
    better: Callable[[V, V], bool],
    can_beat: Callable[[V, V], bool],
) -> BranchBoundResult[T, V]:
    """Exact best-first branch-and-bound with caller-supplied admissible bounds."""

    serial = count()
    queue = []
    root_bound = upper_bound(root)
    heappush(queue, (0, next(serial), root, root_bound))
    best_item = None
    best_value = None
    evaluated = 0
    pruned = 0

    while queue:
        _, _, item, bound = heappop(queue)
        if best_value is not None and not can_beat(bound, best_value):
            pruned += 1
            continue
        if is_terminal(item):
            value = evaluate(item)
            evaluated += 1
            if best_value is None or better(value, best_value):
                best_item = item
                best_value = value
            continue
        for child in children(item):
            child_bound = upper_bound(child)
            if best_value is not None and not can_beat(child_bound, best_value):
                pruned += 1
                continue
            heappush(queue, (0, next(serial), child, child_bound))

    return BranchBoundResult(
        best_item=best_item,
        best_value=best_value,
        evaluated_leaves=evaluated,
        pruned_nodes=pruned,
    )
