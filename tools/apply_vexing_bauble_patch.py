#!/usr/bin/env python3
"""Guarded one-time applicator for Vexing Bauble rules correctness.

Run from the repository root on branch ``vexing-bauble-correctness``:

    py -3 tools/apply_vexing_bauble_patch.py

This patch intentionally fails if audited source anchors no longer match.  It
modifies only ``urza_solver.py``.  The dedicated ``bauble_smoke.py`` file is
already committed on the branch and should be run immediately afterward.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    path = ROOT / "urza_solver.py"
    text = path.read_text(encoding="utf-8")

    # 1. Centralize the actual Bauble condition: mana *spent*, not printed cost
    # or mana value.  The helper is called only after relevant cast triggers.
    anchor = '''def remove_one(tup:Tuple[str,...], card:str)->Tuple[str,...]:\n    x=list(tup); x.remove(card); return tuple(x)\n\n\n'''
    helper = '''def remove_one(tup:Tuple[str,...], card:str)->Tuple[str,...]:\n    x=list(tup); x.remove(card); return tuple(x)\n\n\ndef vexing_bauble_counters_spell(s:State,mana_spent:int)->bool:\n    \"\"\"True iff our in-play Bauble counters this cast for spending no mana.\n\n    Vexing Bauble cares about mana actually spent to cast the spell, not printed\n    mana value. Additional costs such as multikicker count when mana is actually\n    paid; nonmana alternate/additional costs do not.\n    \"\"\"\n    return has(s,\"Vexing Bauble\") and mana_spent==0\n\n\ndef vexing_bauble_countered_cast(s:State,card:str,mana_spent:int,\n                                  message:str=\"\")->Optional[State]:\n    \"\"\"Return the post-counter state, or None when Bauble does not counter.\n\n    Callers must run all modeled cast triggers before this helper because\n    Bauble's ability itself triggers on cast and can be ordered below our other\n    cast triggers. Resolution/ETB/spell effects must happen only if this returns\n    None.\n    \"\"\"\n    if not vexing_bauble_counters_spell(s,mana_spent):\n        return None\n    ns=replace(s,graveyard=s.graveyard+(card,))\n    return add_trace(ns,message or f\"Vexing Bauble counters {card}; no mana spent to cast it\")\n\n\n'''
    text = replace_once(text, anchor, helper, "insert Bauble helpers")

    # 2. Chalice: multikicker/reductions matter only through mana actually paid.
    old = '''        ns=artifact_cast_triggers(ns,"Everflowing Chalice")\n        if has(ns,"Vexing Bauble") and generic==0:\n            ns=replace(ns,graveyard=ns.graveyard+("Everflowing Chalice",))\n            out.append(add_trace(ns,f"cast Everflowing Chalice kicked {k}x; no mana spent -> Vexing Bauble counters"))\n            continue\n'''
    new = '''        ns=artifact_cast_triggers(ns,"Everflowing Chalice")\n        countered=vexing_bauble_countered_cast(\n            ns,"Everflowing Chalice",generic,\n            f"cast Everflowing Chalice kicked {k}x; no mana spent -> Vexing Bauble counters"\n        )\n        if countered is not None:\n            out.append(countered)\n            continue\n'''
    text = replace_once(text, old, new, "Chalice Bauble rule")

    # 3. General casting: track actual mana spent. Probe/Misstep may choose U
    # instead of the Phyrexian/no-mana route when Bauble is already in play.
    old = '''    g,b=spell_cost(s,card,outside=outside)\n    ps=s if free else pay(s,g,b)\n    if ps is None: return None\n    s=replace(ps,hand=remove_one(ps.hand,card),spell_cast_this_turn=True)\n'''
    new = '''    g,b=spell_cost(s,card,outside=outside)\n    mana_spent=0\n    if free:\n        ps=s\n    elif card in {"Gitaxian Probe","Mental Misstep"} and has(s,"Vexing Bauble") and s.blue>=1:\n        # Choose the normal {U} payment instead of a no-mana Phyrexian payment\n        # when that is what allows the spell to survive our own Bauble.\n        ps=pay(s,0,1); mana_spent=1\n    else:\n        ps=pay(s,g,b); mana_spent=g+b\n    if ps is None: return None\n    s=replace(ps,hand=remove_one(ps.hand,card),spell_cast_this_turn=True)\n'''
    text = replace_once(text, old, new, "general cast mana-spent accounting")

    # Artifact branch already has the correct trigger ordering; make the test
    # generic and mana-spent based.
    old = '''    if card in ARTIFACTS:\n        s=artifact_cast_triggers(s,card)\n        if has(s,"Vexing Bauble") and (0 if free else g+b)==0:\n            s=replace(s,graveyard=s.graveyard+(card,))\n            return add_trace(s,f"Vexing Bauble counters zero-mana cast {card}")\n        s=add_perm(s,card,sick=card in CREATURES)\n'''
    new = '''    if card in ARTIFACTS:\n        s=artifact_cast_triggers(s,card)\n        countered=vexing_bauble_countered_cast(s,card,mana_spent)\n        if countered is not None:\n            return countered\n        s=add_perm(s,card,sick=card in CREATURES)\n'''
    text = replace_once(text, old, new, "artifact Bauble rule")

    # Commander / creature / enchantment / planeswalker / supported spells all
    # need the same post-cast-trigger, pre-resolution Bauble gate.
    old = '''    if card==COMMANDER:\n        if has(s,"Artificer's Assistant"): s=apply_scry(s,1,"Artificer's Assistant (legendary cast)")\n        s=vfc_noncreature_cast_trigger(s,card) if False else s\n        s=add_perm(s,COMMANDER,sick=True); s=replace(\n'''
    new = '''    if card==COMMANDER:\n        if has(s,"Artificer's Assistant"): s=apply_scry(s,1,"Artificer's Assistant (legendary cast)")\n        s=vfc_noncreature_cast_trigger(s,card) if False else s\n        countered=vexing_bauble_countered_cast(s,card,mana_spent)\n        if countered is not None: return countered\n        s=add_perm(s,COMMANDER,sick=True); s=replace(\n'''
    text = replace_once(text, old, new, "commander Bauble gate")

    old = '''    if card in CREATURES or card=="Hydroelectric Specimen":\n        s=add_perm(s,card,sick=True); return check_win(add_trace(s,f"cast {card}"))\n    if card in {"Mystic Remora","Rhystic Study","Fortune Teller's Talent"}:\n        s=add_perm(s,card)\n'''
    new = '''    if card in CREATURES or card=="Hydroelectric Specimen":\n        countered=vexing_bauble_countered_cast(s,card,mana_spent)\n        if countered is not None: return countered\n        s=add_perm(s,card,sick=True); return check_win(add_trace(s,f"cast {card}"))\n    if card in {"Mystic Remora","Rhystic Study","Fortune Teller's Talent"}:\n        countered=vexing_bauble_countered_cast(s,card,mana_spent)\n        if countered is not None: return countered\n        s=add_perm(s,card)\n'''
    text = replace_once(text, old, new, "creature/enchantment Bauble gates")

    old = '''    if card=="Tezzeret, Cruel Captain":\n        if has(s,"Artificer's Assistant"): s=apply_scry(s,1,"Artificer's Assistant (legendary cast)")\n        s=vfc_noncreature_cast_trigger(s,card)\n        s=add_perm(s,card,counters=4,mode="tez_ready"); return add_trace(s,"cast Tezzeret (4 loyalty)")\n    if card=="Gitaxian Probe":\n        s=vfc_noncreature_cast_trigger(s,card)\n        if has(s,"Vexing Bauble"):\n            if s.blue>=1:\n                s=replace(s,blue=s.blue-1)\n            else:\n                return add_trace(replace(s,graveyard=s.graveyard+(card,)),"Probe cast for life; Vexing Bauble counters it")\n        s,drawn=draw_from_library(s,1)\n'''
    new = '''    if card=="Tezzeret, Cruel Captain":\n        if has(s,"Artificer's Assistant"): s=apply_scry(s,1,"Artificer's Assistant (legendary cast)")\n        s=vfc_noncreature_cast_trigger(s,card)\n        countered=vexing_bauble_countered_cast(s,card,mana_spent)\n        if countered is not None: return countered\n        s=add_perm(s,card,counters=4,mode="tez_ready"); return add_trace(s,"cast Tezzeret (4 loyalty)")\n    if card=="Gitaxian Probe":\n        s=vfc_noncreature_cast_trigger(s,card)\n        countered=vexing_bauble_countered_cast(\n            s,card,mana_spent,"Probe cast with no mana spent; Vexing Bauble counters it"\n        )\n        if countered is not None: return countered\n        s,drawn=draw_from_library(s,1)\n'''
    text = replace_once(text, old, new, "Tezzeret/Probe Bauble gates")

    for card, anchor_text in [
        ("Dramatic Reversal", '''    if card=="Dramatic Reversal":\n        s=vfc_noncreature_cast_trigger(s,card)\n        b=[]\n'''),
        ("Mana Drain", '''    if card=="Mana Drain":\n        s=vfc_noncreature_cast_trigger(s,card)\n        return add_trace(replace(s,drain_bank=s.drain_bank+2),"Mana Drain assumption: bank +2 next turn")\n'''),
        ("Sea Gate Restoration", '''    if card=="Sea Gate Restoration":\n        s=vfc_noncreature_cast_trigger(s,card)\n        s,drawn=draw_from_library(s,len(s.hand)+1)\n'''),
        ("Sink into Stupor", '''    if card=="Sink into Stupor":\n        s=vfc_noncreature_cast_trigger(s,card)\n        s=replace(s,graveyard=s.graveyard+(card,))\n'''),
    ]:
        if card == "Dramatic Reversal":
            replacement = '''    if card=="Dramatic Reversal":\n        s=vfc_noncreature_cast_trigger(s,card)\n        countered=vexing_bauble_countered_cast(s,card,mana_spent)\n        if countered is not None: return countered\n        b=[]\n'''
        elif card == "Mana Drain":
            replacement = '''    if card=="Mana Drain":\n        s=vfc_noncreature_cast_trigger(s,card)\n        countered=vexing_bauble_countered_cast(s,card,mana_spent)\n        if countered is not None: return countered\n        return add_trace(replace(s,drain_bank=s.drain_bank+2),"Mana Drain assumption: bank +2 next turn")\n'''
        elif card == "Sea Gate Restoration":
            replacement = '''    if card=="Sea Gate Restoration":\n        s=vfc_noncreature_cast_trigger(s,card)\n        countered=vexing_bauble_countered_cast(s,card,mana_spent)\n        if countered is not None: return countered\n        s,drawn=draw_from_library(s,len(s.hand)+1)\n'''
        else:
            replacement = '''    if card=="Sink into Stupor":\n        s=vfc_noncreature_cast_trigger(s,card)\n        countered=vexing_bauble_countered_cast(s,card,mana_spent)\n        if countered is not None: return countered\n        s=replace(s,graveyard=s.graveyard+(card,))\n'''
        text = replace_once(text, anchor_text, replacement, f"{card} Bauble gate")

    # 4. Urza spin should use the same cast path for artifacts and nonartifacts.
    # Free=True means zero mana was spent on the Urza-provided alternate cost.
    old = '''        elif card not in ALL_LANDS or card in MDFC_BLUE_LANDS:\n            ns=replace(ns,hand=ns.hand+(card,),exile=ns.exile[:-1])\n            if has(ns,"Vexing Bauble"):\n                # Cast still happens (and cast triggers happen) but is countered for no mana spent.\n                if card in ARTIFACTS:\n                    tr=artifact_cast_triggers(ns,card); tr=replace(tr,hand=remove_one(tr.hand,card),graveyard=tr.graveyard+(card,),spell_cast_this_turn=True)\n                    out.append(add_trace(tr,f"Urza spin casts {card}; Vexing Bauble counters it"))\n            else:\n                if card=="Everflowing Chalice":\n                    for cs in chalice_cast_variants(ns,outside=True,free=True):\n                        out.append(add_trace(cs,"Urza spin -> free Chalice base cost; optional multikicker paid"))\n                else:\n                    cs=cast_from_hand(ns,card,outside=True,free=True)\n                    if cs: out.append(add_trace(cs,f"Urza spin -> free {card}"))\n'''
    new = '''        elif card not in ALL_LANDS or card in MDFC_BLUE_LANDS:\n            ns=replace(ns,hand=ns.hand+(card,),exile=ns.exile[:-1])\n            if card=="Everflowing Chalice":\n                for cs in chalice_cast_variants(ns,outside=True,free=True):\n                    out.append(add_trace(cs,"Urza spin -> free Chalice base cost; optional multikicker paid"))\n            else:\n                cs=cast_from_hand(ns,card,outside=True,free=True)\n                if cs: out.append(add_trace(cs,f"Urza spin -> free {card}"))\n'''
    text = replace_once(text, old, new, "Urza spin Bauble unification")

    # 5. Chrome Mox remains a special branch but use the central predicate and
    # keep its already-correct trigger-before-counter order.
    old = '''        base=artifact_cast_triggers(base,"Chrome Mox")\n        if has(base,"Vexing Bauble"):\n            base=replace(base,graveyard=base.graveyard+("Chrome Mox",)); out.append(add_trace(base,"Vexing Bauble counters Chrome Mox after cast triggers")); base=None\n'''
    new = '''        base=artifact_cast_triggers(base,"Chrome Mox")\n        countered=vexing_bauble_countered_cast(\n            base,"Chrome Mox",0,"Vexing Bauble counters Chrome Mox after cast triggers"\n        )\n        if countered is not None:\n            out.append(countered); base=None\n'''
    text = replace_once(text, old, new, "Chrome Mox Bauble helper")

    path.write_text(text, encoding="utf-8")
    print("VEXING BAUBLE PATCH APPLIED")
    print("Modified: urza_solver.py")
    print("Next: py -3 bauble_smoke.py")


if __name__ == "__main__":
    main()
