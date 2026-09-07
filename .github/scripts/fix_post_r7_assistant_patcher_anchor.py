#!/usr/bin/env python3
from pathlib import Path

path = Path('.github/scripts/patch_post_r7_assistant_scry.py')
text = path.read_text()
old = 'let mut detail = Vec::with_capacity(2 + top.len() + bottom.len());'
new = 'let mut detail = Vec::with_capacity(top.len() + bottom.len() + 2);'
count = text.count(old)
if count != 1:
    raise SystemExit(f'expected one stale scry public-key capacity anchor, found {count}')
path.write_text(text.replace(old, new, 1))
print('Assistant patcher scry public-key anchor repaired')
