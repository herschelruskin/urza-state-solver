#!/usr/bin/env python3
"""Cleanup pass for the X-slot patcher's one ambiguous idempotence anchor."""

from pathlib import Path

p=Path("x_artifact_search_adapter.py")
text=p.read_text(encoding="utf-8")
old='''    index = _slot_index(paid, slot)\n    paid = solver.remove_perm(paid, index)\n'''
new='''    paid = solver.remove_perm(paid, index)\n'''
if old in text:
    text=text.replace(old,new,1)
elif '''    index = _slot_index(state, slot)\n''' in text and new in text:
    print("Phase-1 Reshape stale post-payment lookup already removed")
else:
    raise SystemExit("could not verify Phase-1 Reshape stable-index patch")
p.write_text(text,encoding="utf-8")
print("X-slot cleanup pass complete")
