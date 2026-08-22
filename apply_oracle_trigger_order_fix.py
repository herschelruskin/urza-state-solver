#!/usr/bin/env python3
"""Apply the focused Oracle controlled artifact-cast trigger-order correction.

The validated Oracle historically collapsed simultaneous artifact-cast triggers to
one fixed order.  This assertion-heavy patcher adds exact multiset ordering
variants while retaining the old single-state helper for regression compatibility.

Run once from the repository root on branch
`oracle-ceiling-permissions-trigger-order`, then run oracle_trigger_order_smoke.py.
"""

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{path}: expected exactly one replacement match, found {count}\nOLD:\n{old}"
        )
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"PATCHED {path}")


# ---------------------------------------------------------------------------
# Exact distinct trigger-order variants.  The old artifact_cast_triggers()
# remains untouched so older regression tests can continue asserting its legacy
# deterministic sequence.  Oracle action generation uses the new variants.
# ---------------------------------------------------------------------------
replace_once(
    "urza_solver.py",
    '''    return s\n\ndef remove_one(tup:Tuple[str,...], card:str)->Tuple[str,...]:\n''',
    '''    return s\n\ndef _artifact_cast_trigger_tokens(s:State,card:str)->Tuple[str,...]:\n    """Strategic simultaneous triggers fired by one artifact cast.\n\n    Vexing Bauble is intentionally not included in the permutation. Its counter\n    trigger does not erase already-triggered abilities; all of those abilities\n    still resolve whether Bauble is above or below them. The existing caller-side\n    Bauble resolution is therefore the same final modeled state without a fake\n    factorial multiplier.\n    """\n    tokens=[]\n    if card not in CREATURES and has(s,"Valley Floodcaller"):\n        tokens.append("vfc")\n    tokens.extend(["assistant"]*count_bf(s,"Artificer's Assistant"))\n    if has(s,"Uthros Research Craft") and s.uthros_counters>=3 and s.library:\n        tokens.append("uthros")\n    tokens.extend(["gadgeteer"]*count_bf(s,"Forensic Gadgeteer"))\n    return tuple(tokens)\n\ndef _unique_multiset_orders(tokens:Tuple[str,...])->Tuple[Tuple[str,...],...]:\n    """Unique permutations without factorial duplicate copies."""\n    counts=Counter(tokens)\n    kinds=tuple(sorted(counts))\n    n=len(tokens)\n    rows=[]\n\n    def visit(prefix):\n        if len(prefix)==n:\n            rows.append(tuple(prefix)); return\n        for kind in kinds:\n            if counts[kind]<=0:\n                continue\n            counts[kind]-=1; prefix.append(kind)\n            visit(prefix)\n            prefix.pop(); counts[kind]+=1\n\n    visit([])\n    return tuple(rows)\n\ndef _resolve_artifact_cast_trigger_order(s:State,card:str,order:Tuple[str,...])->State:\n    totals=Counter(order); resolved=Counter()\n    for kind in order:\n        resolved[kind]+=1\n        if kind=="vfc":\n            s=vfc_noncreature_cast_trigger(s,card)\n        elif kind=="assistant":\n            s=apply_scry(\n                s,1,\n                f"Artificer's Assistant trigger {resolved[kind]}/{totals[kind]}"\n            )\n        elif kind=="uthros":\n            if s.library:\n                s,drawn=draw_from_library(s,1)\n                s=replace(s,uthros_counters=s.uthros_counters+1)\n                s=add_trace(\n                    s,\n                    f"Uthros trigger draws: {drawn[0]}; "\n                    "+1 station counter before artifact resolves"\n                )\n        elif kind=="gadgeteer":\n            s=add_perm(s,"Clue",mode="clue")\n            # Any ETB triggers created by this resolving investigate trigger are\n            # stacked above the older unresolved cast triggers, so resolving the\n            # ETB bundle here before continuing the order is the correct nesting.\n            s=artifact_etb_triggers(s,"Clue")\n            s=add_trace(\n                s,\n                f"Gadgeteer trigger {resolved[kind]}/{totals[kind]} -> Clue"\n            )\n        else:\n            raise AssertionError(f"unknown artifact cast trigger kind {kind!r}")\n    return s\n\ndef artifact_cast_trigger_variants(s:State,card:str)->List[State]:\n    """Return every distinct modeled legal resolution order for our cast triggers."""\n    tokens=_artifact_cast_trigger_tokens(s,card)\n    if not tokens:\n        return [s]\n    unique={}\n    for order in _unique_multiset_orders(tokens):\n        ns=_resolve_artifact_cast_trigger_order(s,card,order)\n        # Different orders can be strategically identical (for example VFC and\n        # Gadgeteer when neither changes library decisions). Collapse only after\n        # the complete order has resolved, using trace-free Markov identity.\n        key=canonical_markov_state_key(ns)\n        if key not in unique:\n            unique[key]=ns\n    return list(unique.values())\n\ndef remove_one(tup:Tuple[str,...], card:str)->Tuple[str,...]:\n''',
)

# ---------------------------------------------------------------------------
# Chalice is a special branching cast and therefore must explicitly cross its
# kick choice with every trigger-order result before Bauble/spell resolution.
# ---------------------------------------------------------------------------
replace_once(
    "urza_solver.py",
    '''        ns=replace(ps,hand=remove_one(ps.hand,"Everflowing Chalice"),\n                   spell_cast_this_turn=True)\n        ns=artifact_cast_triggers(ns,"Everflowing Chalice")\n        countered=vexing_bauble_countered_cast(\n            ns,"Everflowing Chalice",generic,\n            f"cast Everflowing Chalice kicked {k}x; no mana spent -> Vexing Bauble counters"\n        )\n        if countered is not None:\n            out.append(countered)\n            continue\n        ns=add_perm(ns,"Everflowing Chalice",counters=k)\n        ns=artifact_etb_triggers(ns,"Everflowing Chalice")\n        out.append(add_trace(check_win(ns),f"cast Everflowing Chalice kicked {k}x -> {k} charge counter(s)"))\n''',
    '''        cast_state=replace(ps,hand=remove_one(ps.hand,"Everflowing Chalice"),\n                           spell_cast_this_turn=True)\n        for ns in artifact_cast_trigger_variants(cast_state,"Everflowing Chalice"):\n            countered=vexing_bauble_countered_cast(\n                ns,"Everflowing Chalice",generic,\n                f"cast Everflowing Chalice kicked {k}x; no mana spent -> Vexing Bauble counters"\n            )\n            if countered is not None:\n                out.append(countered)\n                continue\n            ns=add_perm(ns,"Everflowing Chalice",counters=k)\n            ns=artifact_etb_triggers(ns,"Everflowing Chalice")\n            out.append(add_trace(check_win(ns),f"cast Everflowing Chalice kicked {k}x -> {k} charge counter(s)"))\n''',
)

# ---------------------------------------------------------------------------
# Generic artifact spell variants. Nonartifact callers retain cast_from_hand().
# ---------------------------------------------------------------------------
replace_once(
    "urza_solver.py",
    '''    return None\n\ndef play_land(s:State,card:str)->Optional[State]:\n''',
    '''    return None\n\ndef cast_from_hand_variants(s:State,card:str,outside:bool=False,free:bool=False)->List[State]:\n    """Oracle cast branches, expanding controlled trigger order for artifacts."""\n    if card not in ARTIFACTS:\n        one=cast_from_hand(s,card,outside=outside,free=free)\n        return [one] if one is not None else []\n    if card not in s.hand or card in ALL_LANDS:\n        return []\n    if card in {"Chrome Mox","Mox Diamond","Everflowing Chalice"}:\n        return []\n\n    g,b=spell_cost(s,card,outside=outside)\n    mana_spent=0\n    if free:\n        ps=s\n    else:\n        ps=pay(s,g,b); mana_spent=g+b\n    if ps is None:\n        return []\n    cast_state=replace(ps,hand=remove_one(ps.hand,card),spell_cast_this_turn=True)\n    out=[]\n    for ns in artifact_cast_trigger_variants(cast_state,card):\n        countered=vexing_bauble_countered_cast(ns,card,mana_spent)\n        if countered is not None:\n            out.append(countered); continue\n        ns=add_perm(ns,card,sick=card in CREATURES)\n        if card=="Uthros Research Craft": ns=replace(ns,uthros_counters=0)\n        if card=="The One Ring": ns=replace(ns,ring_counters=0)\n        ns=artifact_etb_triggers(ns,card)\n        out.append(check_win(add_trace(ns,f"cast {card}")))\n    return out\n\ndef play_land(s:State,card:str)->Optional[State]:\n''',
)

# Chip/FTT top casts must retain trigger-order diversity after the top card is
# removed from the library and is therefore known to the Oracle.
replace_once(
    "urza_solver.py",
    '''        else:\n            cs=cast_from_hand(ns,card,outside=True)\n            if cs:\n                out.append(add_trace(cs,f"{src}: cast {card} from top"))\n''',
    '''        else:\n            for cs in cast_from_hand_variants(ns,card,outside=True):\n                out.append(add_trace(cs,f"{src}: cast {card} from top"))\n''',
)

# Urza's persistent free-cast permission likewise branches the artifact trigger
# order rather than returning to the legacy fixed helper.
replace_once(
    "urza_solver.py",
    '''            else:\n                cs=cast_from_hand(base,card,outside=True,free=True)\n                if cs:\n                    out.append(add_trace(cs,f"Urza permission -> cast {card} free"))\n''',
    '''            else:\n                for cs in cast_from_hand_variants(base,card,outside=True,free=True):\n                    out.append(add_trace(cs,f"Urza permission -> cast {card} free"))\n''',
)

# Ordinary hand-cast action generation uses variants for artifacts and a singleton
# result for every other spell.
replace_once(
    "urza_solver.py",
    '''    for c in set(s.hand):\n        if (c not in ALL_LANDS or c in MDFC_BLUE_LANDS) and c not in special_spells:\n            x=cast_from_hand(s,c)\n            if x:\n                out.append(x)\n''',
    '''    for c in set(s.hand):\n        if (c not in ALL_LANDS or c in MDFC_BLUE_LANDS) and c not in special_spells:\n            out.extend(cast_from_hand_variants(s,c))\n''',
)

# ---------------------------------------------------------------------------
# Chrome Mox / Mox Diamond special casts.
# ---------------------------------------------------------------------------
replace_once(
    "urza_solver.py",
    '''def mox_cast_actions(s:State)->List[State]:\n    out=[]\n    if "Chrome Mox" in s.hand:\n        # Artifact cast triggers happen even if we choose no imprint.\n        base=replace(s,hand=remove_one(s.hand,"Chrome Mox"),spell_cast_this_turn=True)\n        base=artifact_cast_triggers(base,"Chrome Mox")\n        countered=vexing_bauble_countered_cast(\n            base,"Chrome Mox",0,"Vexing Bauble counters Chrome Mox after cast triggers"\n        )\n        if countered is not None:\n            out.append(countered); base=None\n        if base is not None:\n            base=add_perm(base,"Chrome Mox"); base=artifact_etb_triggers(base,"Chrome Mox")\n            out.append(add_trace(base,"cast Chrome Mox, no imprint"))\n        if base is not None:\n          for c in sorted(set(s.hand)-{"Chrome Mox"}):\n            if c in BLUE_NONARTIFACT_FRONT:\n                ns=replace(base,hand=remove_one(base.hand,c),exile=base.exile+(c,))\n                # mark the newly entered Chrome Mox as imprinted\n                for j in range(len(ns.battlefield)-1,-1,-1):\n                    if ns.battlefield[j].name=="Chrome Mox": ns=update_perm(ns,j,mode="imprinted"); break\n                out.append(add_trace(ns,f"Chrome Mox imprints {c}"))\n    if "Mox Diamond" in s.hand:\n        # No land discard: spell was still cast but Diamond never enters.\n        no=replace(s,hand=remove_one(s.hand,"Mox Diamond"),graveyard=s.graveyard+("Mox Diamond",),spell_cast_this_turn=True)\n        no=artifact_cast_triggers(no,"Mox Diamond"); out.append(add_trace(no,"cast Mox Diamond, decline/cannot discard land -> graveyard"))\n        if not has(s,"Vexing Bauble"):\n          for c in sorted(set(s.hand)-{"Mox Diamond"}):\n            if c in TRUE_LAND_CARDS:\n                ns=replace(s,hand=remove_one(remove_one(s.hand,"Mox Diamond"),c),graveyard=s.graveyard+(c,),spell_cast_this_turn=True)\n                ns=artifact_cast_triggers(ns,"Mox Diamond")\n                if has(ns,"Vexing Bauble"):\n                    ns=replace(ns,graveyard=ns.graveyard+("Mox Diamond",)); out.append(add_trace(ns,f"Mox Diamond discards {c}; Vexing Bauble counters spell"))\n                else:\n                    ns=add_perm(ns,"Mox Diamond",mode="diamond"); ns=artifact_etb_triggers(ns,"Mox Diamond"); out.append(add_trace(ns,f"Mox Diamond discards true land card {c}"))\n    return out\n''',
    '''def mox_cast_actions(s:State)->List[State]:\n    out=[]\n    if "Chrome Mox" in s.hand:\n        cast_base=replace(s,hand=remove_one(s.hand,"Chrome Mox"),spell_cast_this_turn=True)\n        for triggered in artifact_cast_trigger_variants(cast_base,"Chrome Mox"):\n            countered=vexing_bauble_countered_cast(\n                triggered,"Chrome Mox",0,\n                "Vexing Bauble counters Chrome Mox after cast triggers"\n            )\n            if countered is not None:\n                out.append(countered); continue\n            entered=add_perm(triggered,"Chrome Mox")\n            entered=artifact_etb_triggers(entered,"Chrome Mox")\n            out.append(add_trace(entered,"cast Chrome Mox, no imprint"))\n            for c in sorted(set(s.hand)-{"Chrome Mox"}):\n                if c not in BLUE_NONARTIFACT_FRONT:\n                    continue\n                ns=replace(entered,hand=remove_one(entered.hand,c),exile=entered.exile+(c,))\n                for j in range(len(ns.battlefield)-1,-1,-1):\n                    if ns.battlefield[j].name=="Chrome Mox":\n                        ns=update_perm(ns,j,mode="imprinted"); break\n                out.append(add_trace(ns,f"Chrome Mox imprints {c}"))\n\n    if "Mox Diamond" in s.hand:\n        no_base=replace(\n            s,hand=remove_one(s.hand,"Mox Diamond"),\n            graveyard=s.graveyard+("Mox Diamond",),spell_cast_this_turn=True\n        )\n        for no in artifact_cast_trigger_variants(no_base,"Mox Diamond"):\n            out.append(add_trace(no,"cast Mox Diamond, decline/cannot discard land -> graveyard"))\n\n        if not has(s,"Vexing Bauble"):\n            for c in sorted(set(s.hand)-{"Mox Diamond"}):\n                if c not in TRUE_LAND_CARDS:\n                    continue\n                cast_base=replace(\n                    s,\n                    hand=remove_one(remove_one(s.hand,"Mox Diamond"),c),\n                    graveyard=s.graveyard+(c,),spell_cast_this_turn=True\n                )\n                for ns in artifact_cast_trigger_variants(cast_base,"Mox Diamond"):\n                    ns=add_perm(ns,"Mox Diamond",mode="diamond")\n                    ns=artifact_etb_triggers(ns,"Mox Diamond")\n                    out.append(add_trace(ns,f"Mox Diamond discards true land card {c}"))\n    return out\n''',
)

# Offer's first spell has already been cast before Offer is cast. If it is an
# artifact, each simultaneous trigger order is a distinct pre-Offer state.
replace_once(
    "urza_solver.py",
    '''        first=replace(first,hand=remove_one(first.hand,card),spell_cast_this_turn=True)\n        if card in ARTIFACTS: first=artifact_cast_triggers(first,card)\n        elif card not in CREATURES: first=vfc_noncreature_cast_trigger(first,card)\n        if not can_pay(first,0,1): continue\n        ns=pay(first,0,1); ns=replace(ns,hand=remove_one(ns.hand,offer),graveyard=ns.graveyard+(card,offer)); ns=vfc_noncreature_cast_trigger(ns,offer)\n        ns=add_perm(ns,"Treasure",mode="treasure"); ns=artifact_etb_triggers(ns,"Treasure")\n        ns=add_perm(ns,"Treasure",mode="treasure"); ns=artifact_etb_triggers(ns,"Treasure")\n        out.append(add_trace(ns,f"Offer counters our {card} -> two Treasures"))\n''',
    '''        first=replace(first,hand=remove_one(first.hand,card),spell_cast_this_turn=True)\n        first_states=(\n            artifact_cast_trigger_variants(first,card)\n            if card in ARTIFACTS\n            else [vfc_noncreature_cast_trigger(first,card)]\n        )\n        for first_state in first_states:\n            if not can_pay(first_state,0,1):\n                continue\n            ns=pay(first_state,0,1)\n            ns=replace(\n                ns,hand=remove_one(ns.hand,offer),\n                graveyard=ns.graveyard+(card,offer)\n            )\n            ns=vfc_noncreature_cast_trigger(ns,offer)\n            ns=add_perm(ns,"Treasure",mode="treasure"); ns=artifact_etb_triggers(ns,"Treasure")\n            ns=add_perm(ns,"Treasure",mode="treasure"); ns=artifact_etb_triggers(ns,"Treasure")\n            out.append(add_trace(ns,f"Offer counters our {card} -> two Treasures"))\n''',
)

print("ORACLE CONTROLLED TRIGGER ORDER SOURCE PATCH: APPLIED")
