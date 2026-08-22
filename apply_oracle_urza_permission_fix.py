#!/usr/bin/env python3
"""Apply the focused Oracle Urza-spin permission correction.

This is a temporary, assertion-heavy source patcher because the project keeps the
large validated Oracle solver in one file.  Every replacement must match exactly
once; otherwise the script stops without silently guessing.

Run once from the repository root on branch
`oracle-ceiling-permissions-trigger-order`, then run the focused smoke suite.
"""

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one replacement match, found {count}\nOLD:\n{old}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"PATCHED {path}")


# ---------------------------------------------------------------------------
# urza_solver.State + exact Oracle search identity
# ---------------------------------------------------------------------------
replace_once(
    "urza_solver.py",
    '''    graveyard: Tuple[str,...] = ()\n    exile: Tuple[str,...] = ()\n    blue: int = 0\n''',
    '''    graveyard: Tuple[str,...] = ()\n    exile: Tuple[str,...] = ()\n    # Cards exiled by Urza's {5} ability that remain legally playable until\n    # end of the current turn.  Card-name multiplicity is sufficient because\n    # same-name physical copies are strategically interchangeable here.\n    urza_exile_permissions: Tuple[str,...] = ()\n    blue: int = 0\n''',
)

replace_once(
    "urza_solver.py",
    '''                tuple(sorted(self.graveyard)),self.ring_counters,self.ftt_level,self.uthros_counters,\n''',
    '''                tuple(sorted(self.graveyard)),tuple(sorted(self.exile)),\n                tuple(sorted(self.urza_exile_permissions)),\n                self.ring_counters,self.ftt_level,self.uthros_counters,\n''',
)

# ---------------------------------------------------------------------------
# Persistent permission actions.  These deliberately reuse the existing free
# cast / land-play mechanics so the correction changes timing, not card rules.
# ---------------------------------------------------------------------------
replace_once(
    "urza_solver.py",
    '''def special_actions(s:State)->List[State]:\n''',
    '''def urza_exile_permission_actions(s:State)->List[State]:\n    """Use any still-live card permission created by Urza's {5} ability.\n\n    Not using a permission is represented by choosing another ordinary action.\n    The permission therefore survives arbitrary sequencing and additional spins\n    until it is consumed or end_turn() expires it.\n    """\n    out=[]\n    for card in sorted(set(s.urza_exile_permissions)):\n        if card not in s.exile:\n            continue\n        base=replace(\n            s,\n            exile=remove_one(s.exile,card),\n            urza_exile_permissions=remove_one(s.urza_exile_permissions,card),\n            hand=s.hand+(card,),\n        )\n\n        # "Play that card" permits the land face when legal.  MDFCs also retain\n        # their independent front-face spell option below.\n        if card in ALL_LANDS and not s.land_played:\n            pl=play_land(base,card)\n            if pl:\n                out.append(add_trace(pl,f"Urza permission -> play {card}"))\n\n        if card not in ALL_LANDS or card in MDFC_BLUE_LANDS:\n            if card=="Everflowing Chalice":\n                # Without paying the mana cost fixes X=0; multikicker remains an\n                # optional additional cost and chalice_cast_variants already\n                # models the payable {2}-per-kick branches.\n                for cs in chalice_cast_variants(base,outside=True,free=True):\n                    out.append(add_trace(\n                        cs,\n                        "Urza permission -> free Chalice base cost; optional multikicker paid"\n                    ))\n            else:\n                cs=cast_from_hand(base,card,outside=True,free=True)\n                if cs:\n                    out.append(add_trace(cs,f"Urza permission -> cast {card} free"))\n    return out\n\n\ndef special_actions(s:State)->List[State]:\n''',
)

# Replace the old immediate-use spin macro with a single persistent-permission
# successor.  The Oracle may later choose this permission among ordinary actions.
replace_once(
    "urza_solver.py",
    '''    # Real Urza shuffle/reset. Free-cast top card if legal; Vexing Bauble can counter free spell.\n    if s.urza and can_pay(s,5,0) and s.library:\n        ps=pay(s,5,0); ps=replace(ps,library=shuffled_library(ps,"urza-spin")); card=ps.library[0]\n        ns=replace(ps,library=ps.library[1:],exile=ps.exile+(card,))\n        if card in ALL_LANDS and not ns.land_played:\n            ns=replace(ns,hand=ns.hand+(card,),exile=ns.exile[:-1]); pl=play_land(ns,card)\n            if pl: out.append(add_trace(pl,f"Urza spin -> play {card}"))\n        elif card not in ALL_LANDS or card in MDFC_BLUE_LANDS:\n            ns=replace(ns,hand=ns.hand+(card,),exile=ns.exile[:-1])\n            if card=="Everflowing Chalice":\n                for cs in chalice_cast_variants(ns,outside=True,free=True):\n                    out.append(add_trace(cs,"Urza spin -> free Chalice base cost; optional multikicker paid"))\n            else:\n                cs=cast_from_hand(ns,card,outside=True,free=True)\n                if cs: out.append(add_trace(cs,f"Urza spin -> free {card}"))\n''',
    '''    # Urza {5}: shuffle, exile the top card, and grant a play permission\n    # lasting until end of turn.  Do NOT force an immediate play/cast; Oracle\n    # search may sequence other actions or additional spins first.\n    if s.urza and can_pay(s,5,0) and s.library:\n        ps=pay(s,5,0)\n        ps=replace(ps,library=shuffled_library(ps,"urza-spin"))\n        card=ps.library[0]\n        ns=replace(\n            ps,\n            library=ps.library[1:],\n            exile=ps.exile+(card,),\n            urza_exile_permissions=ps.urza_exile_permissions+(card,),\n        )\n        out.append(add_trace(\n            ns,\n            f"Urza spin -> exile {card}; playable until end of turn"\n        ))\n    out += urza_exile_permission_actions(s)\n''',
)

# Dominance may never merge away a live temporary permission.
replace_once(
    "urza_solver.py",
    '''        s.turn,bf,tuple(sorted(s.hand)),s.library[:5],\n        tuple(sorted(s.graveyard)),s.land_played,s.drain_bank,\n''',
    '''        s.turn,bf,tuple(sorted(s.hand)),s.library[:5],\n        tuple(sorted(s.graveyard)),tuple(sorted(s.exile)),\n        tuple(sorted(s.urza_exile_permissions)),s.land_played,s.drain_bank,\n''',
)

# Beam score: a free playable card is at least a hand-sized live resource.  This
# is only ranking; exact state identity above carries correctness.
replace_once(
    "urza_solver.py",
    '''    sc += len(s.hand)*5\n    # combo proximity\n''',
    '''    sc += len(s.hand)*5\n    sc += len(s.urza_exile_permissions)*7\n    # combo proximity\n''',
)

# Permission expires at end of turn; the actual exiled card remains in exile.
replace_once(
    "urza_solver.py",
    '''               remora_upkeep_pending=remora_pending,\n               spell_cast_this_turn=False,vfc_pumps=0)\n''',
    '''               remora_upkeep_pending=remora_pending,\n               urza_exile_permissions=(),\n               spell_cast_this_turn=False,vfc_pumps=0)\n''',
)

# ---------------------------------------------------------------------------
# Architecture/audit projections: the new field is public and value relevant.
# ---------------------------------------------------------------------------
replace_once(
    "solver_architecture.py",
    '''    commander_in_command_zone: bool\n    commander_casts_from_zone: int\n    known_top: Tuple[str, ...] = ()\n''',
    '''    commander_in_command_zone: bool\n    commander_casts_from_zone: int\n    urza_exile_permissions: Tuple[str, ...] = ()\n    known_top: Tuple[str, ...] = ()\n''',
)
replace_once(
    "solver_architecture.py",
    '''        commander_casts_from_zone=int(getattr(true_state, "commander_casts_from_zone", 0)),\n        known_top=tuple(information.known_top),\n''',
    '''        commander_casts_from_zone=int(getattr(true_state, "commander_casts_from_zone", 0)),\n        urza_exile_permissions=tuple(sorted(getattr(true_state, "urza_exile_permissions", ()))),\n        known_top=tuple(information.known_top),\n''',
)

replace_once(
    "state_field_audit.py",
    '''    "exile": FieldAudit("zone accounting", "state_coordinate", PUBLIC, RETAIN,\n        "Exiled cards remain unavailable; order is not modeled as relevant."),\n    "blue": FieldAudit("mana resource", "state_coordinate", PUBLIC, RETAIN,\n''',
    '''    "exile": FieldAudit("zone accounting", "state_coordinate", PUBLIC, RETAIN,\n        "Exiled cards remain unavailable; order is not modeled as relevant."),\n    "urza_exile_permissions": FieldAudit("temporary play permission", "state_coordinate", PUBLIC, RETAIN,\n        "Urza's {5} ability grants until-end-of-turn permission to play specific exiled card(s); multiplicity changes future legal actions."),\n    "blue": FieldAudit("mana resource", "state_coordinate", PUBLIC, RETAIN,\n''',
)

replace_once(
    "strategic_value_state.py",
    '''    commander_in_command_zone: bool\n    commander_casts_from_zone: int\n    won: bool\n    objective_memory: Tuple[Tuple[str, Any], ...] = ()\n''',
    '''    commander_in_command_zone: bool\n    commander_casts_from_zone: int\n    won: bool\n    urza_exile_permissions: Tuple[str, ...] = ()\n    objective_memory: Tuple[Tuple[str, Any], ...] = ()\n''',
)
replace_once(
    "strategic_value_state.py",
    '''        commander_casts_from_zone=int(getattr(state, "commander_casts_from_zone", 0)),\n        won=bool(getattr(state, "won", False)),\n        objective_memory=_normalize_objective_memory(objective_memory),\n''',
    '''        commander_casts_from_zone=int(getattr(state, "commander_casts_from_zone", 0)),\n        won=bool(getattr(state, "won", False)),\n        urza_exile_permissions=_sorted_cards(getattr(state, "urza_exile_permissions", ())),\n        objective_memory=_normalize_objective_memory(objective_memory),\n''',
)

print("ORACLE URZA PERMISSION SOURCE PATCH: APPLIED")
