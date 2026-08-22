#!/usr/bin/env python3
"""Apply the Oracle artifact-ETB stack patch with the Bay edit made robust.

The first ETB patcher proved its preceding anchors in CI but used a fragile two-step
indentation edit for ``repurposing_bay_actions``. This wrapper replaces only that
patch-program section with a whole-function region replacement, then executes the
rest of the original assertion-heavy patcher unchanged. It also updates legacy Bay
smoke assertions whose trace shape intentionally changes when ETBs become explicit.
"""

from pathlib import Path

SOURCE = Path("apply_oracle_etb_stack_fix.py").read_text(encoding="utf-8")
START_MARKER = "# Repurposing Bay target entry.\n"
END_MARKER = "# Main-phase Offer macro: two Treasure tokens enter simultaneously.\n"

start = SOURCE.find(START_MARKER)
end = SOURCE.find(END_MARKER, start + 1)
if start < 0 or end < 0:
    raise RuntimeError("could not locate the Bay patch-program section")
if SOURCE.find(START_MARKER, start + 1) >= 0:
    raise RuntimeError("Bay patch-program start marker is not unique")

ROBUST_BAY_PATCH = r"""# Repurposing Bay target entry: replace the complete function so indentation is
# not coupled to a second formatting-sensitive patch step.
replace_region(
    "urza_solver.py",
    "def repurposing_bay_actions(s:State)->List[State]:\n",
    "\ndef scour_actions(s:State)->List[State]:\n",
    r'''def repurposing_bay_actions(s:State)->List[State]:
    out=[]
    for bi,bay in enumerate(s.battlefield):
        if bay.name!="Repurposing Bay" or bay.tapped:
            continue
        g=2
        if has(s,"Forensic Gadgeteer"):
            g=max(1,g-1)
        if s.pa_target=="Repurposing Bay":
            g=max(1,g-2)
        if not can_pay(s,g,0):
            continue
        for ai,a in enumerate(s.battlefield):
            if ai==bi or not is_artifact_perm(a):
                continue
            sacmv=(
                0 if a.mode in {"clue","construct","treasure"}
                else mana_value(a.name)
            )
            targetmv=sacmv+1
            ns0=pay(s,g,0)
            ns0=update_perm(ns0,bi,tapped=True)
            ns0=remove_perm(ns0,ai)
            sac_name=a.name or a.mode

            no_find=replace(
                ns0,
                library=shuffled_library(ns0,"bay:no-target:"+sac_name),
            )
            out.append(add_trace(
                check_win(no_find),
                f"Repurposing Bay sacs {sac_name}; finds no card\n"
                f"Repurposing Bay activation: pay {{{g}}}, tap; shuffle"
            ))

            targets=sorted(
                x for x in set(ns0.library)
                if x in ARTIFACTS
                and mana_value(x)==targetmv
                and not cage_blocks_library_battlefield_entry(ns0,x)
            )
            for target in targets:
                ns=ns0
                lib=list(ns.library); lib.remove(target)
                ns=replace(ns,library=tuple(lib))
                ns=add_perm(ns,target,sick=target in CREATURES)
                # Search/shuffle completes before the entered artifact's ETB
                # triggers are put on the Oracle stack.
                ns=replace(ns,library=shuffled_library(ns,"bay:"+target))
                for row in _artifact_entry_state_variants(ns,(target,)):
                    out.append(add_trace(
                        check_win(row),
                        f"Repurposing Bay sacs {sac_name} -> {target}\n"
                        f"Repurposing Bay activation: pay {{{g}}}, tap; put "
                        f"{target} (MV {targetmv}) onto battlefield; shuffle"
                    ))
    return _dedup_states(out)

''',
)

"""

POST_PATCH = r"""
# Explicit ETB resolution now contributes trace entries before the Bay summary.
# Preserve all physical/accounting assertions while relaxing the obsolete
# one-action == one-trace-entry assumption.
replace_once(
    "urza_solver.py",
    '''    assert len(result.trace)==len(base.trace)+1\n    assert "pay {2}, tap" in result.trace[-1]\n''',
    '''    assert len(result.trace)>=len(base.trace)+1\n    assert result.trace[-1].splitlines()[0].startswith("Repurposing Bay sacs ")\n    assert "pay {2}, tap" in result.trace[-1]\n''',
)
replace_once(
    "urza_solver.py",
    '''    assert well_result.trace[-2].startswith("Witching Well: scry 2")\n''',
    '''    assert any(\n        line.startswith("Witching Well ETB: scry 2")\n        for entry in well_result.trace\n        for line in entry.splitlines()\n    )\n''',
)
"""

patched_program = SOURCE[:start] + ROBUST_BAY_PATCH + SOURCE[end:] + POST_PATCH
compiled = compile(patched_program, "apply_oracle_etb_stack_fix.py[v2]", "exec")
exec(compiled, {"__name__": "__main__"})
