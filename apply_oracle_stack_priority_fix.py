#!/usr/bin/env python3
"""Apply the focused Oracle pending-stack / between-trigger priority correction.

This patch upgrades artifact casts from one atomic trigger macro into a compact
Oracle stack representation.  The search still uses the existing State graph,
but a cast action now also exposes pause states before/after individual cast
triggers.  Priority actions taken from those pause states consume ordinary search
depth; pure passes/resolutions are folded into the predecessor/successor frontier
so mechanical stack steps do not consume strategic depth.

The patch is assertion-heavy and must match each source anchor exactly once.
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
# Oracle State: public pending stack as exact transition state.
# ---------------------------------------------------------------------------
replace_once(
    "urza_solver.py",
    '''    urza_exile_permissions: Tuple[str,...] = ()\n    blue: int = 0\n''',
    '''    urza_exile_permissions: Tuple[str,...] = ()\n    # Oracle-only compact top-first stack.  Each entry is a tuple of strings:\n    #   ("trigger", spell_id, kind, card, aux)\n    #   ("spell",   spell_id, card, mode, aux)\n    # Non-Oracle policy mode keeps its richer typed stack in the Phase-1 runtime\n    # sidecar; this field exists so the clairvoyant Oracle can search legal\n    # priority windows without consuming hidden mechanical depth.\n    oracle_stack: Tuple[Tuple[str,...], ...] = ()\n    blue: int = 0\n''',
)

replace_once(
    "urza_solver.py",
    '''                tuple(sorted(self.urza_exile_permissions)),\n                self.ring_counters,self.ftt_level,self.uthros_counters,\n''',
    '''                tuple(sorted(self.urza_exile_permissions)),tuple(self.oracle_stack),\n                self.ring_counters,self.ftt_level,self.uthros_counters,\n''',
)

# ---------------------------------------------------------------------------
# Stack engine inserted beside cast-trigger helpers.
# ---------------------------------------------------------------------------
replace_once(
    "urza_solver.py",
    '''def remove_one(tup:Tuple[str,...], card:str)->Tuple[str,...]:\n''',
    r'''FLASH_CREATURES=frozenset({
    "Faerie Mastermind","Valley Floodcaller","Hydroelectric Specimen",
})


def _can_cast_card_at_priority(s:State,card:str)->bool:
    """Normal instant timing plus native flash and Valley Floodcaller."""
    if card in TRUE_LAND_CARDS:
        return False
    if card in INSTANTS or card in FLASH_CREATURES:
        return True
    if has(s,"Valley Floodcaller") and card not in CREATURES and card!=COMMANDER:
        return True
    return False


def _next_oracle_stack_id(s:State)->str:
    ids=[]
    for entry in s.oracle_stack:
        if len(entry)>=2:
            try:
                ids.append(int(entry[1]))
            except (TypeError,ValueError):
                pass
    return str(max(ids,default=0)+1)


def _stack_trigger_entry(spell_id:str,kind:str,card:str,aux:str="")->Tuple[str,...]:
    return ("trigger",str(spell_id),str(kind),str(card),str(aux))


def _stack_spell_entry(spell_id:str,card:str,mode:str="ordinary",aux:str="")->Tuple[str,...]:
    return ("spell",str(spell_id),str(card),str(mode),str(aux))


def _resolve_vfc_trigger_already_on_stack(s:State)->State:
    """Resolve an existing Floodcaller trigger even if its source left play."""
    s=replace(s,vfc_pumps=s.vfc_pumps+1)
    b=list(s.battlefield); changed=[]
    for i,p in enumerate(b):
        # These are the only modeled Birds/Frogs/Otters/Rats in this deck.
        if p.name in {"Valley Floodcaller","Artificer's Assistant"} and p.tapped:
            b[i]=replace(p,tapped=False,producer_urza_ready=False)
            changed.append(p.name)
    if changed:
        s=replace(s,battlefield=tuple(b))
        s=add_trace(s,"VFC trigger resolves -> untap "+", ".join(changed))
    else:
        s=add_trace(s,"VFC trigger resolves")
    return s


def _remove_pending_spell_entry(s:State,spell_id:str,*,to_grave:bool)->Tuple[State,str]:
    stack=list(s.oracle_stack)
    for i,entry in enumerate(stack):
        if len(entry)>=5 and entry[0]=="spell" and entry[1]==spell_id:
            card=entry[2]
            stack.pop(i)
            ns=replace(s,oracle_stack=tuple(stack))
            if to_grave:
                ns=replace(ns,graveyard=ns.graveyard+(card,))
            return ns,card
    return s,""


def _resolve_chrome_imprint_trigger(s:State)->List[State]:
    out=[add_trace(s,"cast Chrome Mox, no imprint")]
    for card in sorted(set(s.hand)):
        if card not in BLUE_NONARTIFACT_FRONT:
            continue
        ns=replace(s,hand=remove_one(s.hand,card),exile=s.exile+(card,))
        for j in range(len(ns.battlefield)-1,-1,-1):
            if ns.battlefield[j].name=="Chrome Mox" and ns.battlefield[j].mode!="imprinted":
                ns=update_perm(ns,j,mode="imprinted")
                break
        out.append(add_trace(ns,f"Chrome Mox imprints {card}"))
    return out


def _resolve_oracle_stack_top(s:State)->List[State]:
    """Resolve exactly the current top object; callers choose when to pass."""
    if not s.oracle_stack:
        return [s]
    entry=s.oracle_stack[0]
    base=replace(s,oracle_stack=s.oracle_stack[1:])
    if len(entry)<5:
        raise AssertionError(f"malformed Oracle stack entry: {entry!r}")

    etype,spell_id,a,b,aux=entry
    if etype=="trigger":
        kind=a; card=b
        if kind=="vfc":
            return [_resolve_vfc_trigger_already_on_stack(base)]
        if kind=="assistant":
            return [apply_scry(base,1,"Artificer's Assistant stack trigger")]
        if kind=="uthros":
            ns=base
            if ns.library:
                ns,drawn=draw_from_library(ns,1)
                # The trigger exists independently after it triggers.  If Uthros
                # has left, the draw still happens but there is no object to get
                # the charge counter.
                if has(ns,"Uthros Research Craft"):
                    ns=replace(ns,uthros_counters=ns.uthros_counters+1)
                ns=add_trace(ns,f"Uthros stack trigger draws: {drawn[0]}")
            else:
                ns=add_trace(ns,"Uthros stack trigger resolves with empty library")
            return [ns]
        if kind=="gadgeteer":
            ns=add_perm(base,"Clue",mode="clue")
            ns=artifact_etb_triggers(ns,"Clue")
            return [add_trace(ns,"Gadgeteer stack trigger -> Clue")]
        if kind=="bauble":
            ns,removed=_remove_pending_spell_entry(base,spell_id,to_grave=True)
            if removed:
                return [add_trace(ns,f"Vexing Bauble stack trigger counters {removed}")]
            return [add_trace(base,"Vexing Bauble stack trigger resolves; spell already absent")]
        if kind=="chrome_imprint":
            return _resolve_chrome_imprint_trigger(base)
        raise AssertionError(f"unknown Oracle stack trigger kind {kind!r}")

    if etype!="spell":
        raise AssertionError(f"unknown Oracle stack object type {etype!r}")

    card=a; mode=b
    if mode=="ordinary":
        ns=add_perm(base,card,sick=card in CREATURES)
        if card=="Uthros Research Craft":
            ns=replace(ns,uthros_counters=0)
        if card=="The One Ring":
            ns=replace(ns,ring_counters=0)
        ns=artifact_etb_triggers(ns,card)
        return [check_win(add_trace(ns,f"cast {card}"))]

    if mode=="chalice":
        k=int(aux or 0)
        ns=add_perm(base,"Everflowing Chalice",counters=k)
        ns=artifact_etb_triggers(ns,"Everflowing Chalice")
        return [add_trace(
            check_win(ns),
            f"cast Everflowing Chalice kicked {k}x -> {k} charge counter(s)"
        )]

    if mode=="chrome_mox":
        ns=add_perm(base,"Chrome Mox")
        ns=artifact_etb_triggers(ns,"Chrome Mox")
        # Imprint is a triggered ability of the entered Mox, not a casting cost
        # or replacement effect.  Put it above any older outer stack objects.
        imprint=_stack_trigger_entry(spell_id,"chrome_imprint","Chrome Mox")
        ns=replace(ns,oracle_stack=(imprint,)+ns.oracle_stack)
        return [add_trace(ns,"Chrome Mox resolves -> imprint trigger")]

    if mode=="mox_diamond":
        # Mox Diamond's land discard is its would-enter replacement choice.  It
        # is made now, after cast triggers and any intervening priority actions.
        out=[add_trace(
            replace(base,graveyard=base.graveyard+("Mox Diamond",)),
            "cast Mox Diamond, decline/cannot discard land -> graveyard"
        )]
        for land in sorted(set(base.hand)&TRUE_LAND_CARDS):
            ns=replace(
                base,
                hand=remove_one(base.hand,land),
                graveyard=base.graveyard+(land,),
            )
            ns=add_perm(ns,"Mox Diamond",mode="diamond")
            ns=artifact_etb_triggers(ns,"Mox Diamond")
            out.append(add_trace(ns,f"Mox Diamond discards true land card {land}"))
        return out

    raise AssertionError(f"unknown Oracle pending artifact spell mode {mode!r}")


def _dedup_states(states:Iterable[State])->List[State]:
    unique={}
    for st in states:
        key=canonical_markov_state_key(st)
        if key not in unique:
            unique[key]=st
    return list(unique.values())


def _oracle_stack_pause_frontier(s:State)->List[State]:
    """All pass-only pause points from this priority window, finals first.

    The unchanged state is retained as the current priority window.  Every
    prefix obtained by passing through one or more stack objects is also exposed,
    plus every fully resolved final state.  Mechanical pass/resolution therefore
    does not consume the Oracle's strategic action depth.
    """
    rows=[s]
    frontier=[s]
    seen={canonical_markov_state_key(s)}
    guard=0
    while frontier:
        guard+=1
        if guard>64:
            raise AssertionError("Oracle stack pass frontier exceeded 64 layers")
        nxt=[]
        for st in frontier:
            if not st.oracle_stack:
                continue
            for ns in _resolve_oracle_stack_top(st):
                key=canonical_markov_state_key(ns)
                if key in seen:
                    continue
                seen.add(key); rows.append(ns)
                if ns.oracle_stack:
                    nxt.append(ns)
        frontier=nxt
    finals=[x for x in rows if not x.oracle_stack]
    pauses=[x for x in rows if x.oracle_stack]
    return finals+pauses


def _stack_artifact_cast_state_variants(
    cast_state:State,card:str,mana_spent:int,*,mode:str="ordinary",aux:str=""
)->List[State]:
    """Put one artifact spell and its simultaneous cast triggers on the stack."""
    tokens=list(_artifact_cast_trigger_tokens(cast_state,card))
    if vexing_bauble_counters_spell(cast_state,mana_spent):
        tokens.append("bauble")
    orders=_unique_multiset_orders(tuple(tokens)) if tokens else ((),)
    spell_id=_next_oracle_stack_id(cast_state)
    rows=[]
    for order in orders:
        triggers=tuple(
            _stack_trigger_entry(spell_id,kind,card)
            for kind in order
        )
        spell=_stack_spell_entry(spell_id,card,mode,aux)
        ns=replace(cast_state,oracle_stack=triggers+(spell,)+cast_state.oracle_stack)
        ns=add_trace(
            ns,
            f"cast {card} -> pending stack "
            + (" > ".join(order) if order else "spell only")
        )
        rows.extend(_oracle_stack_pause_frontier(ns))
    return _dedup_states(rows)


def _pending_stack_spells(s:State)->List[Tuple[int,Tuple[str,...]]]:
    return [
        (i,e) for i,e in enumerate(s.oracle_stack)
        if len(e)>=5 and e[0]=="spell"
    ]


def offer_pending_stack_actions(s:State)->List[State]:
    """Cast Offer targeting one of our still-pending noncreature spells."""
    offer="An Offer You Can't Refuse"
    if offer not in s.hand or not can_pay(s,0,1):
        return []
    out=[]
    for index,entry in _pending_stack_spells(s):
        _etype,_sid,card,_mode,_aux=entry
        if card in CREATURES or card==COMMANDER:
            continue
        ns=pay(s,0,1)
        stack=list(ns.oracle_stack); stack.pop(index)
        ns=replace(
            ns,
            oracle_stack=tuple(stack),
            hand=remove_one(ns.hand,offer),
            graveyard=ns.graveyard+(card,offer),
            spell_cast_this_turn=True,
        )
        ns=vfc_noncreature_cast_trigger(ns,offer)
        ns=add_perm(ns,"Treasure",mode="treasure")
        ns=artifact_etb_triggers(ns,"Treasure")
        ns=add_perm(ns,"Treasure",mode="treasure")
        ns=artifact_etb_triggers(ns,"Treasure")
        out.append(add_trace(ns,f"Offer counters pending {card} -> two Treasures"))
    return out


def urza_spin_actions(s:State)->List[State]:
    if not (s.urza and can_pay(s,5,0) and s.library):
        return []
    ps=pay(s,5,0)
    ps=replace(ps,library=shuffled_library(ps,"urza-spin"))
    card=ps.library[0]
    ns=replace(
        ps,
        library=ps.library[1:],
        exile=ps.exile+(card,),
        urza_exile_permissions=ps.urza_exile_permissions+(card,),
    )
    return [add_trace(ns,f"Urza spin -> exile {card}; playable until end of turn")]


def _trace_prefix_filter(actions:Iterable[State],prefixes:Tuple[str,...])->List[State]:
    out=[]
    for st in actions:
        action=st.trace[-1].splitlines()[0] if st.trace else ""
        if any(action.startswith(prefix) for prefix in prefixes):
            out.append(st)
    return out


def _oracle_priority_raw_actions(s:State)->List[State]:
    """Modeled legal actions while another Oracle stack object is pending."""
    out=[]

    # Activated abilities with no sorcery-only restriction.
    out += intrinsic_mana_actions(s)
    out += tap_artifact_for_urza_actions(s)
    out += clue_draw_actions(s)+ring_actions(s)+top_actions(s)
    out += draw_sac_actions(s)+fetch_actions(s)
    out += otawara_channel_actions(s)+oboro_minamo_actions(s)
    out += producer_native_actions(s)+top_key_combo_actions(s)
    out += faerie_mastermind_actions(s)+chrome_dome_actions(s)
    out += urza_spin_actions(s)
    out += offer_pending_stack_actions(s)

    # Saga chapter-II's gained activated ability has no sorcery restriction;
    # keep only that branch, not the separate chapter-III resolution macro.
    out += _trace_prefix_filter(saga_actions(s),("Saga II ability",))

    # Current-turn Knack/Helix granted tap abilities and the instant spells that
    # grant them are both legal in a priority window.
    out += knack_bounce_actions(s)
    out += chain_of_vapor_actions(s)
    out += scour_actions(s)

    # Search spells: Mystical and Whir are naturally instant.  Floodcaller also
    # gives flash to Merchant Scroll, Reshape and Transmute Artifact as
    # noncreature spells.  Transmute abilities of Dizzy/Muddle remain sorcery-only
    # activated abilities and are deliberately not enabled by Floodcaller.
    simple=simple_tutor_actions(s)
    prefixes=["Mystical ->"]
    if has(s,"Valley Floodcaller"):
        prefixes.append("Merchant Scroll ->")
    out += _trace_prefix_filter(simple,tuple(prefixes))

    artifact_tutors=artifact_tutor_actions(s)
    prefixes=["Whir X="]
    if has(s,"Valley Floodcaller"):
        prefixes.extend(("Reshape X=","Transmute "))
    out += _trace_prefix_filter(artifact_tutors,tuple(prefixes))

    # Top/exile permissions obey the same timing rules as the card itself.
    out += urza_exile_permission_actions(s,priority=True)
    out += chip_ftt_top_casts(s,priority=True)

    flood=has(s,"Valley Floodcaller")
    if flood:
        out += chalice_cast_variants(s)
        out += mox_cast_actions(s)
        out += power_artifact_actions(s)

    special={
        "Dizzy Spell","Muddle the Mixture","Mystical Tutor","Merchant Scroll",
        "Reshape","Transmute Artifact","Whir of Invention","Chain of Vapor",
        "Banishing Knack","Retraction Helix","Chrome Mox","Mox Diamond",
        "Scour for Scrap","An Offer You Can't Refuse","Power Artifact",
        "Everflowing Chalice",
    }
    for card in sorted(set(s.hand)):
        if card in special or not _can_cast_card_at_priority(s,card):
            continue
        out.extend(cast_from_hand_variants(s,card))

    # Generic Key untap ability (the normal main-phase code keeps this inline).
    for ki,key in enumerate(s.battlefield):
        if key.name not in {"Voltaic Key","Manifold Key"} or key.tapped or not can_pay(s,1,0):
            continue
        for ti,target in enumerate(s.battlefield):
            if ti==ki or not target.tapped or not is_artifact_perm(target):
                continue
            ns=pay(s,1,0)
            ns=update_perm(ns,ki,tapped=True)
            ns=update_perm(ns,ti,tapped=False)
            out.append(add_trace(ns,f"{key.name} untaps {target.name or target.mode}"))
    return out


def oracle_stack_priority_actions(s:State)->List[State]:
    """Take one real priority action, then expose every legal pass/pause point."""
    rows=[]
    for ns in _oracle_priority_raw_actions(s):
        if ns.oracle_stack:
            rows.extend(_oracle_stack_pause_frontier(ns))
        else:
            rows.append(ns)
    return _dedup_states(rows)


def remove_one(tup:Tuple[str,...], card:str)->Tuple[str,...]:
''',
)

# ---------------------------------------------------------------------------
# Artifact casting entry points now create pending stack frames.
# ---------------------------------------------------------------------------
replace_once(
    "urza_solver.py",
    '''def chalice_cast_variants(s:State, outside:bool=False, free:bool=False)->List[State]:\n    if "Everflowing Chalice" not in s.hand:\n        return []\n    pool=s.blue+s.colorless\n    reduction=2 if (outside and s.ftt_level>=3) else 0\n    max_k=min(8,max(0,(pool+reduction)//2))\n    out=[]\n    for k in range(max_k+1):\n        generic=max(0,2*k-reduction)\n        ps=pay(s,generic,0)\n        if ps is None:\n            continue\n        cast_state=replace(ps,hand=remove_one(ps.hand,"Everflowing Chalice"),\n                           spell_cast_this_turn=True)\n        for ns in artifact_cast_trigger_variants(cast_state,"Everflowing Chalice"):\n            countered=vexing_bauble_countered_cast(\n                ns,"Everflowing Chalice",generic,\n                f"cast Everflowing Chalice kicked {k}x; no mana spent -> Vexing Bauble counters"\n            )\n            if countered is not None:\n                out.append(countered)\n                continue\n            ns=add_perm(ns,"Everflowing Chalice",counters=k)\n            ns=artifact_etb_triggers(ns,"Everflowing Chalice")\n            out.append(add_trace(check_win(ns),f"cast Everflowing Chalice kicked {k}x -> {k} charge counter(s)"))\n    return out\n''',
    '''def chalice_cast_variants(s:State, outside:bool=False, free:bool=False)->List[State]:\n    if "Everflowing Chalice" not in s.hand:\n        return []\n    pool=s.blue+s.colorless\n    reduction=2 if (outside and s.ftt_level>=3) else 0\n    max_k=min(8,max(0,(pool+reduction)//2))\n    out=[]\n    for k in range(max_k+1):\n        generic=max(0,2*k-reduction)\n        ps=pay(s,generic,0)\n        if ps is None:\n            continue\n        cast_state=replace(\n            ps,hand=remove_one(ps.hand,"Everflowing Chalice"),\n            spell_cast_this_turn=True\n        )\n        out.extend(_stack_artifact_cast_state_variants(\n            cast_state,"Everflowing Chalice",generic,mode="chalice",aux=str(k)\n        ))\n    return _dedup_states(out)\n''',
)

replace_once(
    "urza_solver.py",
    '''def cast_from_hand_variants(s:State,card:str,outside:bool=False,free:bool=False)->List[State]:\n    """Oracle cast branches, expanding controlled trigger order for artifacts."""\n    if card not in ARTIFACTS:\n        one=cast_from_hand(s,card,outside=outside,free=free)\n        return [one] if one is not None else []\n    if card not in s.hand or card in ALL_LANDS:\n        return []\n    if card in {"Chrome Mox","Mox Diamond","Everflowing Chalice"}:\n        return []\n\n    g,b=spell_cost(s,card,outside=outside)\n    mana_spent=0\n    if free:\n        ps=s\n    else:\n        ps=pay(s,g,b); mana_spent=g+b\n    if ps is None:\n        return []\n    cast_state=replace(ps,hand=remove_one(ps.hand,card),spell_cast_this_turn=True)\n    out=[]\n    for ns in artifact_cast_trigger_variants(cast_state,card):\n        countered=vexing_bauble_countered_cast(ns,card,mana_spent)\n        if countered is not None:\n            out.append(countered); continue\n        ns=add_perm(ns,card,sick=card in CREATURES)\n        if card=="Uthros Research Craft": ns=replace(ns,uthros_counters=0)\n        if card=="The One Ring": ns=replace(ns,ring_counters=0)\n        ns=artifact_etb_triggers(ns,card)\n        out.append(check_win(add_trace(ns,f"cast {card}")))\n    return out\n''',
    '''def cast_from_hand_variants(s:State,card:str,outside:bool=False,free:bool=False)->List[State]:\n    """Oracle cast branches; artifact spells expose their real priority stack."""\n    if card not in ARTIFACTS:\n        one=cast_from_hand(s,card,outside=outside,free=free)\n        return [one] if one is not None else []\n    if card not in s.hand or card in ALL_LANDS:\n        return []\n    if card in {"Chrome Mox","Mox Diamond","Everflowing Chalice"}:\n        return []\n    g,b=spell_cost(s,card,outside=outside)\n    mana_spent=0\n    if free:\n        ps=s\n    else:\n        ps=pay(s,g,b); mana_spent=g+b\n    if ps is None:\n        return []\n    cast_state=replace(ps,hand=remove_one(ps.hand,card),spell_cast_this_turn=True)\n    return _stack_artifact_cast_state_variants(\n        cast_state,card,mana_spent,mode="ordinary"\n    )\n''',
)

# Chrome Mox imprint is an ETB trigger; Mox Diamond discard is a replacement
# choice on resolution.  Neither should be committed before cast-trigger windows.
replace_once(
    "urza_solver.py",
    '''def mox_cast_actions(s:State)->List[State]:\n    out=[]\n    if "Chrome Mox" in s.hand:\n        cast_base=replace(s,hand=remove_one(s.hand,"Chrome Mox"),spell_cast_this_turn=True)\n        for triggered in artifact_cast_trigger_variants(cast_base,"Chrome Mox"):\n            countered=vexing_bauble_countered_cast(\n                triggered,"Chrome Mox",0,\n                "Vexing Bauble counters Chrome Mox after cast triggers"\n            )\n            if countered is not None:\n                out.append(countered); continue\n            entered=add_perm(triggered,"Chrome Mox")\n            entered=artifact_etb_triggers(entered,"Chrome Mox")\n            out.append(add_trace(entered,"cast Chrome Mox, no imprint"))\n            for c in sorted(set(s.hand)-{"Chrome Mox"}):\n                if c not in BLUE_NONARTIFACT_FRONT:\n                    continue\n                ns=replace(entered,hand=remove_one(entered.hand,c),exile=entered.exile+(c,))\n                for j in range(len(ns.battlefield)-1,-1,-1):\n                    if ns.battlefield[j].name=="Chrome Mox":\n                        ns=update_perm(ns,j,mode="imprinted"); break\n                out.append(add_trace(ns,f"Chrome Mox imprints {c}"))\n\n    if "Mox Diamond" in s.hand:\n        no_base=replace(\n            s,hand=remove_one(s.hand,"Mox Diamond"),\n            graveyard=s.graveyard+("Mox Diamond",),spell_cast_this_turn=True\n        )\n        for no in artifact_cast_trigger_variants(no_base,"Mox Diamond"):\n            out.append(add_trace(no,"cast Mox Diamond, decline/cannot discard land -> graveyard"))\n\n        if not has(s,"Vexing Bauble"):\n            for c in sorted(set(s.hand)-{"Mox Diamond"}):\n                if c not in TRUE_LAND_CARDS:\n                    continue\n                cast_base=replace(\n                    s,\n                    hand=remove_one(remove_one(s.hand,"Mox Diamond"),c),\n                    graveyard=s.graveyard+(c,),spell_cast_this_turn=True\n                )\n                for ns in artifact_cast_trigger_variants(cast_base,"Mox Diamond"):\n                    ns=add_perm(ns,"Mox Diamond",mode="diamond")\n                    ns=artifact_etb_triggers(ns,"Mox Diamond")\n                    out.append(add_trace(ns,f"Mox Diamond discards true land card {c}"))\n    return out\n''',
    '''def mox_cast_actions(s:State)->List[State]:\n    out=[]\n    if "Chrome Mox" in s.hand:\n        cast_base=replace(\n            s,hand=remove_one(s.hand,"Chrome Mox"),spell_cast_this_turn=True\n        )\n        out.extend(_stack_artifact_cast_state_variants(\n            cast_base,"Chrome Mox",0,mode="chrome_mox"\n        ))\n    if "Mox Diamond" in s.hand:\n        cast_base=replace(\n            s,hand=remove_one(s.hand,"Mox Diamond"),spell_cast_this_turn=True\n        )\n        out.extend(_stack_artifact_cast_state_variants(\n            cast_base,"Mox Diamond",0,mode="mox_diamond"\n        ))\n    return _dedup_states(out)\n''',
)

# ---------------------------------------------------------------------------
# Timing-aware top/exile permission use during stack priority.
# ---------------------------------------------------------------------------
replace_once(
    "urza_solver.py",
    '''def cage_blocks_library_cast(s:State, card:str)->bool:\n    return cage_in_play(s) and card not in ALL_LANDS\n''',
    '''def cage_blocks_library_cast(s:State, card:str)->bool:\n    # MDFCs are land cards in the library but are still *spells* when their front\n    # face is cast from the library, so Cage blocks those spell-face casts too.\n    return cage_in_play(s) and card not in TRUE_LAND_CARDS\n''',
)

replace_once(
    "urza_solver.py",
    '''def chip_ftt_top_casts(s:State)->List[State]:\n''',
    '''def chip_ftt_top_casts(s:State,priority:bool=False)->List[State]:\n''',
)
replace_once(
    "urza_solver.py",
    '''    if card in ALL_LANDS and not s.land_played:\n        ns=replace(s,library=s.library[1:],hand=s.hand+(card,))\n        pl=play_land(ns,card)\n        if pl:\n            out.append(add_trace(pl,"top access: play land from library"))\n        return out\n\n    if card not in ALL_LANDS:\n        if cage_blocks_library_cast(s,card):\n            return out\n        ns=replace(s,library=s.library[1:],hand=s.hand+(card,))\n        src="Chip" if chip_active else "FTT"\n        if card=="Everflowing Chalice":\n            for cs in chalice_cast_variants(ns,outside=True,free=False):\n                out.append(add_trace(cs,f"{src}: cast Chalice from top"))\n        else:\n            for cs in cast_from_hand_variants(ns,card,outside=True):\n                out.append(add_trace(cs,f"{src}: cast {card} from top"))\n    return out\n''',
    '''    if card in ALL_LANDS and not priority and not s.land_played:\n        ns=replace(s,library=s.library[1:],hand=s.hand+(card,))\n        pl=play_land(ns,card)\n        if pl:\n            out.append(add_trace(pl,"top access: play land from library"))\n        if card not in MDFC_BLUE_LANDS:\n            return out\n\n    # MDFCs may still use their spell face.  At a priority window, enforce\n    # instant/native-flash/Floodcaller timing before moving the card off top.\n    if card not in ALL_LANDS or card in MDFC_BLUE_LANDS:\n        if priority and not _can_cast_card_at_priority(s,card):\n            return out\n        if cage_blocks_library_cast(s,card):\n            return out\n        ns=replace(s,library=s.library[1:],hand=s.hand+(card,))\n        src="Chip" if chip_active else "FTT"\n        if card=="Everflowing Chalice":\n            for cs in chalice_cast_variants(ns,outside=True,free=False):\n                out.append(add_trace(cs,f"{src}: cast Chalice from top"))\n        else:\n            for cs in cast_from_hand_variants(ns,card,outside=True):\n                out.append(add_trace(cs,f"{src}: cast {card} from top"))\n    return out\n''',
)

replace_once(
    "urza_solver.py",
    '''def urza_exile_permission_actions(s:State)->List[State]:\n''',
    '''def urza_exile_permission_actions(s:State,priority:bool=False)->List[State]:\n''',
)
replace_once(
    "urza_solver.py",
    '''        if card in ALL_LANDS and not s.land_played:\n            pl=play_land(base,card)\n            if pl:\n                out.append(add_trace(pl,f"Urza permission -> play {card}"))\n\n        if card not in ALL_LANDS or card in MDFC_BLUE_LANDS:\n            if card=="Everflowing Chalice":\n''',
    '''        if card in ALL_LANDS and not priority and not s.land_played:\n            pl=play_land(base,card)\n            if pl:\n                out.append(add_trace(pl,f"Urza permission -> play {card}"))\n\n        if card not in ALL_LANDS or card in MDFC_BLUE_LANDS:\n            if priority and not _can_cast_card_at_priority(s,card):\n                continue\n            if card=="Everflowing Chalice":\n''',
)

# Factor Urza's instant-speed activated ability so stack priority can use it.
replace_once(
    "urza_solver.py",
    '''    # Urza {5}: shuffle, exile the top card, and grant a play permission\n    # lasting until end of turn.  Do NOT force an immediate play/cast; Oracle\n    # search may sequence other actions or additional spins first.\n    if s.urza and can_pay(s,5,0) and s.library:\n        ps=pay(s,5,0)\n        ps=replace(ps,library=shuffled_library(ps,"urza-spin"))\n        card=ps.library[0]\n        ns=replace(\n            ps,\n            library=ps.library[1:],\n            exile=ps.exile+(card,),\n            urza_exile_permissions=ps.urza_exile_permissions+(card,),\n        )\n        out.append(add_trace(\n            ns,\n            f"Urza spin -> exile {card}; playable until end of turn"\n        ))\n''',
    '''    out += urza_spin_actions(s)\n''',
)

# Old Offer macro no longer synthesizes an artifact cast+counter atomically;
# artifact self-counter lines are now represented by a real pending spell.
replace_once(
    "urza_solver.py",
    '''        if card in ALL_LANDS or card in CREATURES or card in {COMMANDER,"Hydroelectric Specimen"}: continue\n''',
    '''        if card in ALL_LANDS or card in CREATURES or card in ARTIFACTS or card in {COMMANDER,"Hydroelectric Specimen"}: continue\n''',
)

# ---------------------------------------------------------------------------
# Exact/dominance/end-turn identity and stack-specific legal-action window.
# ---------------------------------------------------------------------------
replace_once(
    "urza_solver.py",
    '''        tuple(sorted(s.urza_exile_permissions)),s.land_played,s.drain_bank,\n''',
    '''        tuple(sorted(s.urza_exile_permissions)),tuple(s.oracle_stack),\n        s.land_played,s.drain_bank,\n''',
)

replace_once(
    "urza_solver.py",
    '''    if s.won:\n        return []\n\n    # Cumulative upkeep resolves after untap and before all ordinary actions.\n''',
    '''    if s.won:\n        return []\n\n    # A paused Oracle stack is a real priority window.  Do not expose lands,\n    # planeswalker loyalty, Station, class-leveling, Reconfigure, Repurposing\n    # Bay, or other sorcery-only actions here.\n    if s.oracle_stack:\n        out=oracle_stack_priority_actions(s)\n        if not out:\n            # Defensive fallback for a hand-built pending-stack state: permit\n            # pure passing even though normal cast/priority predecessors already\n            # materialize all pass-only frontiers for free.\n            out=[x for x in _oracle_stack_pause_frontier(s)\n                 if canonical_markov_state_key(x)!=canonical_markov_state_key(s)]\n        out=[refresh_observability(x) for x in out]\n        kept=_select_actions_with_tutor_diversity(out)\n        _record_cap_audit(out,kept,context="oracle_stack_priority")\n        return kept\n\n    # Cumulative upkeep resolves after untap and before all ordinary actions.\n''',
)

replace_once(
    "urza_solver.py",
    '''        not s.remora_upkeep_pending\n        and not s.saga3_pending\n    )\n''',
    '''        not s.remora_upkeep_pending\n        and not s.saga3_pending\n        and not s.oracle_stack\n    )\n''',
)

# ---------------------------------------------------------------------------
# Field audit / strategic value projection.  PolicyView intentionally does not
# expose this Oracle-only compression; Phase-1 runtime view exposes its own typed
# PendingTriggerStack instead.
# ---------------------------------------------------------------------------
replace_once(
    "state_field_audit.py",
    '''    "urza_exile_permissions": FieldAudit("temporary play permission", "state_coordinate", PUBLIC, RETAIN,\n        "Urza's {5} ability grants until-end-of-turn permission to play specific exiled card(s); multiplicity changes future legal actions."),\n    "blue": FieldAudit("mana resource", "state_coordinate", PUBLIC, RETAIN,\n''',
    '''    "urza_exile_permissions": FieldAudit("temporary play permission", "state_coordinate", PUBLIC, RETAIN,\n        "Urza's {5} ability grants until-end-of-turn permission to play specific exiled card(s); multiplicity changes future legal actions."),\n    "oracle_stack": FieldAudit("Oracle pending stack", "state_coordinate", RUNTIME_ONLY, RETAIN,\n        "Clairvoyant Oracle-only compact stack for priority windows. Non-Oracle policy mode uses the typed runtime stack sidecar, so this raw compression is not projected directly to PolicyView."),\n    "blue": FieldAudit("mana resource", "state_coordinate", PUBLIC, RETAIN,\n''',
)

replace_once(
    "strategic_value_state.py",
    '''    urza_exile_permissions: Tuple[str, ...] = ()\n    objective_memory: Tuple[Tuple[str, Any], ...] = ()\n''',
    '''    urza_exile_permissions: Tuple[str, ...] = ()\n    oracle_stack: Tuple[Tuple[str, ...], ...] = ()\n    objective_memory: Tuple[Tuple[str, Any], ...] = ()\n''',
)
replace_once(
    "strategic_value_state.py",
    '''        urza_exile_permissions=_sorted_cards(getattr(state, "urza_exile_permissions", ())),\n        objective_memory=_normalize_objective_memory(objective_memory),\n''',
    '''        urza_exile_permissions=_sorted_cards(getattr(state, "urza_exile_permissions", ())),\n        oracle_stack=tuple(tuple(str(x) for x in entry) for entry in getattr(state, "oracle_stack", ())),\n        objective_memory=_normalize_objective_memory(objective_memory),\n''',
)

print("ORACLE STACK / INTER-TRIGGER PRIORITY SOURCE PATCH: APPLIED")
