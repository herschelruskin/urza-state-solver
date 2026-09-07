#!/usr/bin/env python3
from pathlib import Path

path = Path('.github/scripts/patch_post_r7_clue.py')
text = path.read_text()
old = '        Action::ActivateUrzaSpin { source, payment } => source_key('
new = '        Action::PlayLibraryTopLand { card, entry } => PolicyPublicKey {'
count = text.count(old)
if count != 2:
    raise SystemExit(f'expected two stale Clue public-key anchor tails, found {count}')
path.write_text(text.replace(old, new))
print('Clue patcher public-key anchor repaired for runner')
