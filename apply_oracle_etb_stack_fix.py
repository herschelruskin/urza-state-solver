#!/usr/bin/env python3
"""Apply the focused Oracle artifact-ETB stack / priority correction.

This patch keeps the legacy ``artifact_etb_triggers`` compression as a regression
helper, but production Oracle paths stop using it.  Real artifact entries now:

* collect every controlled ETB trigger created by the same entry event;
* choose their legal top-first stack order;
* preserve priority between individual trigger resolutions;
* treat Offer's two Treasures as one simultaneous two-artifact entry event;
* treat Prized Statue -> Treasure as two sequential entry events;
* branch Sewer-veillance Cam's real target/tap/untap choices;
* put Chrome Mox imprint on the same ETB batch as other entry triggers; and
* use exact Oracle scry choices for stack-resolving scry triggers.

The patch is assertion-heavy and is intended for the current
``oracle-ceiling-permissions-trigger-order`` branch after the validated pending-
stack patch has already been committed.
"""

from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")
    print(f"PATCHED {path}")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{path}: expected exactly one replacement match, found {count}\nOLD:\n{old}"
        )
    write(path, text.replace(old, new, 1))


def insert_before(path: str, marker: str, block: str) -> None:
    text = read(path)
    count = text.count(marker)
    if count != 1:
        raise RuntimeError(
            f"{path}: expected exactly one insertion marker, found {count}: {marker!r}"
        )
    write(path, text.replace(marker, block + marker, 1))


def replace_region(path: str, start: str, end: str, replacement: str) -> None:
    text = read(path)
    a = text.find(start)
    if a < 0:
        raise RuntimeError(f"{path}: start marker not found: {start!r}")
    if text.find(start, a + 1) >= 0:
        raise RuntimeError(f"{path}: start marker is not unique: {start!r}")
    b = text.find(end, a + len(start))
    if b < 0:
        raise RuntimeError(f"{path}: end marker not found after start: {end!r}")
    write(path, text[:a] + replacement + text[b:])


# ---------------------------------------------------------------------------
# Exact Oracle scry outcomes.  Keep legacy apply_scry() intact for old focused
# smokes and old macro helpers; stack-resolving scry triggers use this expansion.
# ---------------------------------------------------------------------------
insert_before(
    "urza_solver.py",
    "def shuffled_library(s:State,salt:str)->Tuple[str,...]:\n",
    r'''def oracle_scry_variants(s:State,n:int,label:str)->List[State]:
    """Enumerate every distinct legal scry result, legacy-preferred first."""
    n=min(n,len(s.library))
    if n<=0:
        return [s]
    seen=tuple(s.library[:n]); rest=tuple(s.library[n:])
    rows=[apply_scry(s,n,label)]
    known={canonical_markov_state_key(rows[0])}
    for perm in sorted(set(itertools.permutations(seen)),key=repr):
        for top_count in range(n,-1,-1):
            top=tuple(perm[:top_count]); bottom=tuple(perm[top_count:])
            ns=replace(s,library=top+rest+bottom)
            ns=add_trace(
                ns,
                f"{label}: scry {n} ({', '.join(seen)}) -> "
                f"top [{', '.join(top)}]; bottom [{', '.join(bottom)}]"
            )
            key=canonical_markov_state_key(ns)
            if key not in known:
                known.add(key); rows.append(ns)
    return rows

''',
)


# Chrome Mox's imprint trigger now identifies the actual entered Mox when stack
# runtime tags are available, while retaining compatibility with old stack rows.
replace_region(
    "urza_solver.py",
    "def _resolve_chrome_imprint_trigger(s:State)->List[State]:\n",
    "\ndef _resolve_oracle_stack_top(s:State)->List[State]:\n",
    r'''def _resolve_chrome_imprint_trigger(s:State,source_tag:str="")->List[State]:
    out=[add_trace(s,"cast Chrome Mox, no imprint")]
    wanted=int(source_tag) if source_tag else 0
    for card in sorted(set(s.hand)):
        if card not in BLUE_NONARTIFACT_FRONT:
            continue
        ns=replace(s,hand=remove_one(s.hand,card),exile=s.exile+(card,))
        for j in range(len(ns.battlefield)-1,-1,-1):
            p=ns.battlefield[j]
            if p.name!="Chrome Mox" or p.mode=="imprinted":
                continue
            if wanted and p.instance_tag!=wanted:
                continue
            ns=update_perm(ns,j,mode="imprinted"); break
        else:
            continue
        out.append(add_trace(ns,f"Chrome Mox imprints {card}"))
    return out


def _ensure_oracle_instance_tags(s:State)->State:
    """Assign stable runtime-only permanent ids without retagging live objects."""
    used={p.instance_tag for p in s.battlefield if p.instance_tag>0}
    next_tag=max(used,default=0)+1
    b=[]; changed=False
    for p in s.battlefield:
        if p.instance_tag>0:
            b.append(p); continue
        while next_tag in used:
            next_tag+=1
        b.append(replace(p,instance_tag=next_tag))
        used.add(next_tag); next_tag+=1; changed=True
    return replace(s,battlefield=tuple(b)) if changed else s


def _perm_index_for_tag(s:State,tag:str)->Optional[int]:
    try:
        wanted=int(tag)
    except (TypeError,ValueError):
        return None
    return next((i for i,p in enumerate(s.battlefield) if p.instance_tag==wanted),None)


def _artifact_entry_label(entered_cards:Tuple[str,...])->str:
    counts=Counter(entered_cards)
    return ", ".join(
        f"{name} x{counts[name]}" if counts[name]>1 else name
        for name in sorted(counts)
    )


def _artifact_etb_token_sets(s:State,entered_cards:Tuple[str,...])->Tuple[Tuple[str,...],...]:
    """Controlled ETBs generated by one simultaneous artifact-entry event."""
    tokens=[]

    # Tezzeret and every Station/Golem trigger once PER artifact that entered.
    for p in s.battlefield:
        if p.name=="Tezzeret, Cruel Captain":
            tokens.extend([f"tezz|{p.instance_tag}"]*len(entered_cards))
    for p in s.battlefield:
        if p.name in {"Grinding Station","Battered Golem"}:
            tokens.extend([f"producer|{p.instance_tag}"]*len(entered_cards))

    # Entry abilities of the objects that just entered.
    cam_count=0
    chrome_count=0
    for card in entered_cards:
        if card in {"Giant's Boulder","Witching Well"}:
            tokens.append(f"scry2|{card}")
        elif card=="Sewer-veillance Cam":
            cam_count+=1
        elif card=="Prized Statue":
            tokens.append("prized|")
        elif card=="Chrome Mox":
            chrome_count+=1

    if chrome_count:
        tags=sorted(
            (p.instance_tag for p in s.battlefield
             if p.name=="Chrome Mox" and p.mode!="imprinted"),
            reverse=True,
        )[:chrome_count]
        for tag in reversed(tags):
            tokens.append(f"chrome|{tag}")

    token_sets=[tuple(tokens)]
    if cam_count:
        targets=tuple(
            p.instance_tag for p in s.battlefield
            if is_creature_perm(p)
        )
        # A targeted trigger with no legal target is removed rather than stacked.
        if targets:
            for _ in range(cam_count):
                token_sets=[row+(f"cam|{tag}",) for row in token_sets for tag in targets]

    # Stable dedup for pathological same-target/same-card copy cases.
    seen=set(); rows=[]
    for row in token_sets:
        if row not in seen:
            seen.add(row); rows.append(row)
    return tuple(rows)


def _etb_token_to_entry(event_id:str,token:str,label:str)->Tuple[str,...]:
    kind,_,aux=token.partition("|")
    mapped={
        "tezz":"etb_tezz",
        "producer":"etb_producer",
        "scry2":"etb_scry2",
        "cam":"etb_cam",
        "prized":"etb_prized_treasure",
        "chrome":"etb_chrome_imprint",
    }.get(kind)
    if mapped is None:
        raise AssertionError(f"unknown artifact ETB token {token!r}")
    return _stack_trigger_entry(event_id,mapped,label,aux)


def _preferred_multiset_orders(tokens:Tuple[str,...])->Tuple[Tuple[str,...],...]:
    orders=_unique_multiset_orders(tokens) if tokens else ((),)
    preferred=tuple(tokens)
    if preferred in orders:
        return (preferred,)+tuple(order for order in orders if order!=preferred)
    return orders


def _push_artifact_etb_stack_variants(
    s:State,entered_cards:Tuple[str,...]
)->List[State]:
    """Put all ETBs from one entry event above older stack objects."""
    if not entered_cards:
        return [s]
    tagged=_ensure_oracle_instance_tags(s)
    label=_artifact_entry_label(entered_cards)
    event_id=_next_oracle_stack_id(tagged)
    unique={}
    for tokens in _artifact_etb_token_sets(tagged,entered_cards):
        for order in _preferred_multiset_orders(tokens):
            triggers=tuple(_etb_token_to_entry(event_id,t,label) for t in order)
            ns=replace(tagged,oracle_stack=triggers+tagged.oracle_stack)
            key=canonical_markov_state_key(ns)
            if key not in unique:
                unique[key]=ns
    return list(unique.values()) if unique else [tagged]


def _resolve_producer_etb_trigger(s:State,source_tag:str,label:str)->List[State]:
    """Exact may-untap branch plus the established legal fast-Urza compression."""
    idx=_perm_index_for_tag(s,source_tag)
    if idx is None:
        return [add_trace(s,f"producer ETB from {label}: source absent")]
    p=s.battlefield[idx]
    if p.name not in {"Grinding Station","Battered Golem"}:
        return [add_trace(s,f"producer ETB from {label}: source changed/absent")]

    rows=[add_trace(s,f"{p.name} ETB trigger from {label}: decline untap")]
    if p.tapped:
        untapped=update_perm(s,idx,tapped=False)
        rows.append(add_trace(untapped,f"{p.name} ETB trigger from {label}: untap"))
    else:
        untapped=s

    # Preserve the old maximum-mana Oracle compression as an additional LEGAL
    # representative.  If the source was untapped, this represents Urza tap ->
    # resolve untap -> Urza tap (+2U).  If it was tapped, it represents untap ->
    # Urza tap (+1U).  The final tap remains refundable exactly as before.
    if s.urza:
        if p.tapped:
            fast=update_perm(s,idx,tapped=False)
            fast=update_perm(fast,idx,tapped=True,producer_urza_ready=True)
            fast=replace(fast,blue=fast.blue+1)
            gain=1
        else:
            fast=update_perm(s,idx,tapped=True,producer_urza_ready=True)
            fast=replace(fast,blue=fast.blue+2)
            gain=2
        rows.append(add_trace(
            fast,f"{p.name} ETB fast Urza line from {label}: +{gain}U"
        ))

    unique={}
    for row in rows:
        key=canonical_markov_state_key(row)
        if key not in unique:
            unique[key]=row
    return list(unique.values())


def _resolve_cam_etb_trigger(s:State,target_tag:str,label:str)->List[State]:
    idx=_perm_index_for_tag(s,target_tag)
    if idx is None or not is_creature_perm(s.battlefield[idx]):
        return [add_trace(s,f"Cam {label} trigger: target absent")]
    target=s.battlefield[idx]
    rows=[add_trace(s,f"Cam {label} trigger: decline on {target.name or target.mode}")]

    if not target.tapped:
        rows.append(add_trace(
            update_perm(s,idx,tapped=True),
            f"Cam {label} taps {target.name or target.mode}"
        ))
    if target.tapped:
        untapped=update_perm(s,idx,tapped=False)
        rows.append(add_trace(
            untapped,f"Cam {label} untaps {target.name or target.mode}"
        ))
        if s.urza and is_artifact_perm(target):
            fast=update_perm(untapped,idx,tapped=True,
                             producer_urza_ready=(target.name in {"Grinding Station","Battered Golem"}))
            fast=replace(fast,blue=fast.blue+1)
            rows.append(add_trace(
                fast,
                f"Cam {label} untaps {target.name or target.mode}; Urza converts it to +U"
            ))

    unique={}
    for row in rows:
        key=canonical_markov_state_key(row)
        if key not in unique:
            unique[key]=row
    return list(unique.values())


''',
)


# Real stack resolver: add ETB trigger types and ensure artifact creation/entry
# pushes nested ETBs above older unresolved objects.
replace_region(
    "urza_solver.py",
    "def _resolve_oracle_stack_top(s:State)->List[State]:\n",
    "\ndef _dedup_states(states:Iterable[State])->List[State]:\n",
    r'''def _resolve_oracle_stack_top(s:State)->List[State]:
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
            return oracle_scry_variants(base,1,"Artificer's Assistant stack trigger")
        if kind=="uthros":
            ns=base
            if ns.library:
                ns,drawn=draw_from_library(ns,1)
                if has(ns,"Uthros Research Craft"):
                    ns=replace(ns,uthros_counters=ns.uthros_counters+1)
                ns=add_trace(ns,f"Uthros stack trigger draws: {drawn[0]}")
            else:
                ns=add_trace(ns,"Uthros stack trigger resolves with empty library")
            return [ns]
        if kind=="gadgeteer":
            ns=add_perm(base,"Clue",mode="clue")
            rows=_push_artifact_etb_stack_variants(ns,("Clue",))
            return [add_trace(row,"Gadgeteer stack trigger -> Clue") for row in rows]
        if kind=="bauble":
            ns,removed=_remove_pending_spell_entry(base,spell_id,to_grave=True)
            if removed:
                return [add_trace(ns,f"Vexing Bauble stack trigger counters {removed}")]
            return [add_trace(base,"Vexing Bauble stack trigger resolves; spell already absent")]
        if kind=="chrome_imprint":
            return _resolve_chrome_imprint_trigger(base)

        # Artifact-entry triggers.
        if kind=="etb_tezz":
            idx=_perm_index_for_tag(base,aux)
            if idx is None or base.battlefield[idx].name!="Tezzeret, Cruel Captain":
                return [add_trace(base,f"Tezzeret ETB trigger from {card}: source absent")]
            ns=update_perm(base,idx,counters=base.battlefield[idx].counters+1)
            return [add_trace(ns,f"Tezzeret artifact-entry trigger from {card}: +1 loyalty")]
        if kind=="etb_producer":
            return _resolve_producer_etb_trigger(base,aux,card)
        if kind=="etb_scry2":
            return oracle_scry_variants(base,2,f"{aux} ETB")
        if kind=="etb_cam":
            return _resolve_cam_etb_trigger(base,aux,"ETB")
        if kind=="etb_prized_treasure":
            ns=add_perm(base,"Treasure",mode="treasure")
            rows=_push_artifact_etb_stack_variants(ns,("Treasure",))
            return [add_trace(row,"Prized Statue ETB -> Treasure") for row in rows]
        if kind=="etb_chrome_imprint":
            return _resolve_chrome_imprint_trigger(base,aux)
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
        ns=add_trace(ns,f"cast {card}")
        return [check_win(row) for row in _push_artifact_etb_stack_variants(ns,(card,))]

    if mode=="chalice":
        k=int(aux or 0)
        ns=add_perm(base,"Everflowing Chalice",counters=k)
        ns=add_trace(ns,f"cast Everflowing Chalice kicked {k}x -> {k} charge counter(s)")
        return [check_win(row) for row in _push_artifact_etb_stack_variants(
            ns,("Everflowing Chalice",)
        )]

    if mode=="chrome_mox":
        ns=add_perm(base,"Chrome Mox")
        ns=add_trace(ns,"Chrome Mox resolves")
        # Chrome Mox's imprint trigger and producer/Tezzeret triggers are all
        # generated by the same entry event and are ordered together.
        return _push_artifact_etb_stack_variants(ns,("Chrome Mox",))

    if mode=="mox_diamond":
        # The land discard replacement choice is made as Diamond would enter.
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
            ns=add_trace(ns,f"Mox Diamond discards true land card {land}")
            out.extend(_push_artifact_etb_stack_variants(ns,("Mox Diamond",)))
        return out

    raise AssertionError(f"unknown Oracle pending artifact spell mode {mode!r}")


''',
)


# Direct-to-battlefield actions need the same free pass/pause closure that casts
# already receive, without charging strategic depth for merely resolving ETBs.
insert_before(
    "urza_solver.py",
    "def _stack_artifact_cast_state_variants(\n",
    r'''def _artifact_entry_state_variants(
    s:State,entered_cards:Tuple[str,...]
)->List[State]:
    rows=[]
    for pushed in _push_artifact_etb_stack_variants(s,entered_cards):
        rows.extend(_oracle_stack_pause_frontier(pushed))
    return _dedup_states(rows)


''',
)


# Offer creates TWO Treasures simultaneously.  Their ETB triggers are therefore
# collected as one batch: each Station/Golem and each Tezzeret triggers twice.
replace_region(
    "urza_solver.py",
    "def offer_pending_stack_actions(s:State)->List[State]:\n",
    "\ndef urza_spin_actions(s:State)->List[State]:\n",
    r'''def offer_pending_stack_actions(s:State)->List[State]:
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
        ns=add_perm(ns,"Treasure",mode="treasure")
        for row in _push_artifact_etb_stack_variants(ns,("Treasure","Treasure")):
            out.append(add_trace(row,f"Offer counters pending {card} -> two Treasures"))
    return _dedup_states(out)


''',
)


# Keep play_land() legacy-compatible but give production Oracle a variant-returning
# path for Seat of the Synod's artifact entry triggers.
replace_region(
    "urza_solver.py",
    "def play_land(s:State,card:str)->Optional[State]:\n",
    "\n# --------------------------- Draw/card engines ------------------------------\n",
    r'''def _play_land_physical(s:State,card:str)->Optional[Tuple[State,str]]:
    if s.land_played or card not in s.hand or card not in ALL_LANDS:
        return None
    b=list(s.battlefield); gy=list(s.graveyard); city_bonus=0
    if card!="City of Traitors":
        for i in reversed(range(len(b))):
            if b[i].name=="City of Traitors":
                if not b[i].tapped:
                    city_bonus+=2
                gy.append("City of Traitors"); b.pop(i)
    ns=replace(
        s,hand=remove_one(s.hand,card),battlefield=tuple(b),graveyard=tuple(gy),
        land_played=True,colorless=s.colorless+city_bonus
    )
    tapped=card=="Saprazzan Skerry"
    counters=2 if card=="Saprazzan Skerry" else (1 if card=="Urza's Saga" else 0)
    ns=add_perm(ns,card,tapped=tapped,counters=counters,
                mode="landface" if card in MDFC_BLUE_LANDS else "")
    msg=(f"play land {card}"
         + (" (back face)" if card in MDFC_BLUE_LANDS else "")
         + ("; City trigger -> +CC then sacrifice" if city_bonus else ""))
    return ns,msg


def play_land(s:State,card:str)->Optional[State]:
    physical=_play_land_physical(s,card)
    if physical is None:
        return None
    ns,msg=physical
    if card=="Seat of the Synod":
        ns=artifact_etb_triggers(ns,card)
    return add_trace(ns,msg)


def play_land_variants(s:State,card:str)->List[State]:
    physical=_play_land_physical(s,card)
    if physical is None:
        return []
    ns,msg=physical
    if card!="Seat of the Synod":
        return [add_trace(ns,msg)]
    return [add_trace(row,msg) for row in _artifact_entry_state_variants(
        ns,("Seat of the Synod",)
    )]


# --------------------------- Draw/card engines ------------------------------
''',
)

replace_once(
    "urza_solver.py",
    '''        pl=play_land(ns,card)\n        if pl:\n            out.append(add_trace(pl,"top access: play land from library"))\n''',
    '''        for pl in play_land_variants(ns,card):\n            out.append(add_trace(pl,"top access: play land from library"))\n''',
)

replace_once(
    "urza_solver.py",
    '''            pl=play_land(base,card)\n            if pl:\n                out.append(add_trace(pl,f"Urza permission -> play {card}"))\n''',
    '''            for pl in play_land_variants(base,card):\n                out.append(add_trace(pl,f"Urza permission -> play {card}"))\n''',
)

replace_once(
    "urza_solver.py",
    '''    for c in set(s.hand):\n        if c in ALL_LANDS:\n            x=play_land(s,c)\n            if x:\n                out.append(x)\n''',
    '''    for c in set(s.hand):\n        if c in ALL_LANDS:\n            out.extend(play_land_variants(s,c))\n''',
)


# ---------------------------------------------------------------------------
# Direct artifact-entry production paths.
# ---------------------------------------------------------------------------

# Transmute paid target.
replace_once(
    "urza_solver.py",
    '''                        ns=add_perm(ns,t,sick=t in CREATURES)\n                        ns=artifact_etb_triggers(ns,t)\n                        out.append(add_trace(check_win(ns),f"Transmute {p.name}->{t}; pay difference {diff}"))\n''',
    '''                        ns=add_perm(ns,t,sick=t in CREATURES)\n                        for row in _artifact_entry_state_variants(ns,(t,)):\n                            out.append(add_trace(check_win(row),f"Transmute {p.name}->{t}; pay difference {diff}"))\n''',
)

# Reshape target.
replace_once(
    "urza_solver.py",
    '''                        ns=add_perm(ns,t,sick=t in CREATURES)\n                        ns=artifact_etb_triggers(ns,t)\n                        out.append(add_trace(check_win(ns),f"Reshape X={x}->{t}; generic paid {generic}"))\n''',
    '''                        ns=add_perm(ns,t,sick=t in CREATURES)\n                        for row in _artifact_entry_state_variants(ns,(t,)):\n                            out.append(add_trace(check_win(row),f"Reshape X={x}->{t}; generic paid {generic}"))\n''',
)

# Whir target.
replace_once(
    "urza_solver.py",
    '''                    ns=add_perm(ns,t,sick=t in CREATURES)\n                    ns=artifact_etb_triggers(ns,t)\n                    out.append(add_trace(check_win(ns),f"Whir X={x}->{t}"))\n''',
    '''                    ns=add_perm(ns,t,sick=t in CREATURES)\n                    for row in _artifact_entry_state_variants(ns,(t,)):\n                        out.append(add_trace(check_win(row),f"Whir X={x}->{t}"))\n''',
)

# Chrome Dome copy entry.
replace_once(
    "urza_solver.py",
    '''        ns=pay(s,g,0); ns=add_perm(ns,p.name,sick=False,mode="chrome_copy"); ns=artifact_etb_triggers(ns,p.name)\n        out.append(add_trace(check_win(ns),f"Chrome Dome copies {p.name} (haste)"))\n''',
    '''        ns=pay(s,g,0); ns=add_perm(ns,p.name,sick=False,mode="chrome_copy")\n        for row in _artifact_entry_state_variants(ns,(p.name,)):\n            out.append(add_trace(check_win(row),f"Chrome Dome copies {p.name} (haste)"))\n''',
)

# Saga II Construct entry.
replace_once(
    "urza_solver.py",
    '''            ns=add_perm(ns,"Construct",sick=True,mode="construct")\n            ns=artifact_etb_triggers(ns,"Construct")\n            out.append(add_trace(ns,"Saga II ability -> Construct"))\n''',
    '''            ns=add_perm(ns,"Construct",sick=True,mode="construct")\n            for row in _artifact_entry_state_variants(ns,("Construct",)):\n                out.append(add_trace(row,"Saga II ability -> Construct"))\n''',
)

# Saga III found artifact entry, after shuffle/final-chapter sacrifice.
replace_once(
    "urza_solver.py",
    '''        ns=_sacrifice_final_saga_if_present(ns)\n        ns=artifact_etb_triggers(ns,target)\n        out.append(add_trace(\n            check_win(ns),\n            f"Saga III puts {target} onto battlefield\\nSaga III search resolves; shuffle"\n        ))\n''',
    '''        ns=_sacrifice_final_saga_if_present(ns)\n        for row in _artifact_entry_state_variants(ns,(target,)):\n            out.append(add_trace(\n                check_win(row),\n                f"Saga III puts {target} onto battlefield\\nSaga III search resolves; shuffle"\n            ))\n''',
)

# Repurposing Bay target entry.
replace_once(
    "urza_solver.py",
    '''                ns=replace(ns,library=shuffled_library(ns,"bay:"+target))\n                ns=artifact_etb_triggers(ns,target)\n                out.append(add_trace(\n                    check_win(ns),\n''',
    '''                ns=replace(ns,library=shuffled_library(ns,"bay:"+target))\n                for row in _artifact_entry_state_variants(ns,(target,)):\n                    out.append(add_trace(\n                    check_win(row),\n''',
)
# The Bay replacement opens one extra loop indentation level; close it at the
# known end of the appended trace call.
replace_once(
    "urza_solver.py",
    '''                    f"{target} onto battlefield, shuffle"\n                ))\n    return out\n\ndef scour_actions''',
    '''                    f"{target} onto battlefield, shuffle"\n                    ))\n    return out\n\ndef scour_actions''',
)

# Main-phase Offer macro: two Treasure tokens enter simultaneously.
replace_region(
    "urza_solver.py",
    "def offer_actions(s:State)->List[State]:\n",
    "\n\n\n_CHAIN_RESULT_CACHE = {}\n",
    r'''def offer_actions(s:State)->List[State]:
    out=[]; offer="An Offer You Can't Refuse"
    if offer not in s.hand:
        return out
    # Counter our own castable noncreature spell; its cast triggers still happen.
    for card in sorted(set(s.hand)-{offer}):
        if card in ALL_LANDS or card in CREATURES or card in {COMMANDER,"Hydroelectric Specimen"}:
            continue
        g,b=spell_cost(s,card)
        if not can_pay(s,g,b):
            continue
        first=pay(s,g,b)
        if first is None:
            continue
        first=replace(first,hand=remove_one(first.hand,card),spell_cast_this_turn=True)
        first_states=(artifact_cast_trigger_variants(first,card) if card in ARTIFACTS
                      else [vfc_noncreature_cast_trigger(first,card)])
        for first in first_states:
            if not can_pay(first,0,1):
                continue
            ns=pay(first,0,1)
            ns=replace(
                ns,hand=remove_one(ns.hand,offer),
                graveyard=ns.graveyard+(card,offer)
            )
            ns=vfc_noncreature_cast_trigger(ns,offer)
            ns=add_perm(ns,"Treasure",mode="treasure")
            ns=add_perm(ns,"Treasure",mode="treasure")
            for row in _artifact_entry_state_variants(ns,("Treasure","Treasure")):
                out.append(add_trace(row,f"Offer counters our {card} -> two Treasures"))
    return _dedup_states(out)


_CHAIN_RESULT_CACHE = {}
''',
)

# Command-zone Urza Construct artifact entry.
replace_once(
    "urza_solver.py",
    '''    ns=add_perm(ns,COMMANDER,sick=True)\n    ns=add_perm(ns,"Construct",sick=True,mode="construct")\n    ns=artifact_etb_triggers(ns,"Construct")\n    ns=add_trace(\n        ns,\n        f"cast Urza from command zone -> Construct"\n        + (" (infinite colorless paid generic)" if infinite_colorless_online(s) else "")\n    )\n    return [check_win(ns)]\n''',
    '''    ns=add_perm(ns,COMMANDER,sick=True)\n    ns=add_perm(ns,"Construct",sick=True,mode="construct")\n    rows=[]\n    for row in _artifact_entry_state_variants(ns,("Construct",)):\n        row=add_trace(\n            row,\n            f"cast Urza from command zone -> Construct"\n            + (" (infinite colorless paid generic)" if infinite_colorless_online(s) else "")\n        )\n        rows.append(check_win(row))\n    return _dedup_states(rows)\n''',
)


# ---------------------------------------------------------------------------
# Static guard: production Oracle should have no remaining legacy ETB calls in
# the stack/direct-entry paths we just converted.  Legacy helper internals,
# legacy cast_from_hand, Prized Statue LTB compression, and smoke code remain.
# ---------------------------------------------------------------------------
text=read("urza_solver.py")
required_snippets=(
    '_push_artifact_etb_stack_variants(ns,("Clue",))',
    '_push_artifact_etb_stack_variants(ns,("Treasure","Treasure"))',
    '_artifact_entry_state_variants(ns,(target,))',
    'play_land_variants(s,c)',
    'oracle_scry_variants(base,1,"Artificer\'s Assistant stack trigger")',
)
for snippet in required_snippets:
    if snippet not in text:
        raise RuntimeError(f"post-patch structural assertion missing: {snippet}")

print("ORACLE ARTIFACT ETB STACK SOURCE PATCH: APPLIED")
