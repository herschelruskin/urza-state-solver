"""Small CLI for the application foundation.

This is deliberately not the final user interface.  It gives us a stable local
entry point for packaging, database initialization, cache inspection, and smoke tests
while the GUI and engine adapter are built.
"""

from __future__ import annotations

import argparse
import json

from .store import DackStore


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dacksim")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init-db", help="initialize a DACK result database")
    p_init.add_argument("path")

    p_stats = sub.add_parser("stats", help="show database object counts")
    p_stats.add_argument("path")

    args = ap.parse_args(argv)

    if args.cmd == "init-db":
        with DackStore(args.path) as store:
            print(json.dumps({"path": str(store.path), "schema": 1, "stats": store.stats()}, indent=2))
        return 0

    if args.cmd == "stats":
        with DackStore(args.path) as store:
            print(json.dumps({"path": str(store.path), "stats": store.stats()}, indent=2))
        return 0

    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
