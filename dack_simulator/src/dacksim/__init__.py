"""DACK application foundation.

The package is intentionally small at first: deterministic canonical identifiers,
compact outcome encoding, and a persistent content-addressed result store.  The
existing validated solver remains separate until it passes the reproducibility gate.
"""

from .codec import Outcome, pack_outcomes, unpack_outcomes
from .canonical import canonical_hash, deck_hash, run_key
from .store import DackStore

__all__ = [
    "Outcome",
    "pack_outcomes",
    "unpack_outcomes",
    "canonical_hash",
    "deck_hash",
    "run_key",
    "DackStore",
]

__version__ = "0.1.0"
