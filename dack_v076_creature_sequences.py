"""DACK simulator v0.76: exact combo-creature sequencing.

Changes from v0.75:
- Current deck update: Homeward Path -> Mouth of Ronom; all basic Plains -> Snow-Covered Plains.
- A combo creature in hand is no longer an automatic zero-EV contamination state.
- Exact supported win layouts:
    1) no combo creature in hand -> cast Dack with all three combo creatures in library;
    2) cast Roaming Throne -> cast Dack, with Preston+Boonweaver in library;
    3) cast Preston -> cast Dack, with Throne+Boonweaver in library;
    4) cast Dack -> cast Boonweaver Giant, with Preston+Throne initially in library;
    5) Brainstone / Scroll Rack can repair creature(s) to library first.
- Multiple creature cards in hand are NOT silently treated as a win unless repair or the exact
  supported state transition makes a listed line legal.
"""
from dataclasses import replace
from itertools import combinations
import random
import dack_v075_current99 as v75

d = v75.d

DACK = "Dack Fayden, Helping Hand"
THRONE = "Roaming Throne"
PRESTON = "Preston, the Vanisher"
GIANT = "Boonweaver Giant"
COMBOS = frozenset({THRONE, PRESTON, GIANT})

# ---------------------------------------------------------------------------
# Exact current list: Homeward Path -> Mouth of Ronom; basics become Snow basics.
# ---------------------------------------------------------------------------
CURRENT_DECK = [
    ("Mouth of Ronom" if x == "Homeward Path" else
     "Snow-Covered Plains" if x == "Plains" else x)
    for x in v75.CURRENT_DECK
]
assert len(CURRENT_DECK) == 99
assert "Homeward Path" not in CURRENT_DECK
assert CURRENT_DECK.count("Snow-Covered Plains") == 13
assert CURRENT_DECK.count("Plains") == 0
d.DECK = CURRENT_DECK

for _card in CURRENT_DECK + [DACK]:
    if _card not in d.CARD_ID:
        _nid=max(d.CARD_ID.values(),default=-1)+1
        d.CARD_ID[_card]=_nid
        d.ID_CARD[_nid]=_card

d.LANDS=frozenset(set(d.LANDS)|{"Mouth of Ronom","Snow-Covered Plains"})
d.WHITE_LANDS=frozenset(set(d.WHITE_LANDS)|{"Snow-Covered Plains"})
d.GUARANTEED_WHITE_LANDS=frozenset(set(d.GUARANTEED_WHITE_LANDS)|{"Snow-Covered Plains"})
d.LAND_TUTOR_TARGETS=tuple(dict.fromkeys(tuple(d.LAND_TUTOR_TARGETS)+("Mouth of Ronom","Snow-Covered Plains")))

# Snow Plains and Mouth are ordinary untapped mana lands for the speed objective.
_v076_tap_mana_actions = d.tap_mana_actions
def tap_mana_actions(s):
    out=list(_v076_tap_mana_actions(s))
    for i,p in enumerate(s.battlefield):
        if p.tapped:
            continue
        if p.name=="Snow-Covered Plains":
            bf=list(s.battlefield); bf[i]=replace(p,tapped=True)
            out.append(replace(s,battlefield=tuple(bf),w=s.w+1))
        elif p.name=="Mouth of Ronom":
            bf=list(s.battlefield); bf[i]=replace(p,tapped=True)
            out.append(replace(s,battlefield=tuple(bf),c=s.c+1))
    return _dedupe(out)
d.tap_mana_actions=tap_mana_actions

# Roaming Throne can now be cast by the search and must count for metalcraft.
_v076_is_artifact_perm=d.is_artifact_perm
def is_artifact_perm(name):
    return name==THRONE or _v076_is_artifact_perm(name)
d.is_artifact_perm=is_artifact_perm

def _dedupe(states):
    seen=set(); out=[]
    for q in states:
        k=d.key(q)
        if k not in seen:
            seen.add(k); out.append(q)
    return out

# ---------------------------------------------------------------------------
# Current basic-land / contamination-aware tutor helpers.
# ---------------------------------------------------------------------------
def _hand_contaminated(s):
    return any(x in COMBOS for x in s.hand)

def _repair_artifacts(s, mv1_only=False):
    out=[]
    if not _hand_contaminated(s):
        return out
    if "Brainstone" in s.library:
        out.append("Brainstone")
    if not mv1_only and "Scroll Rack" in s.library:
        out.append("Scroll Rack")
    return out

def land_tutor_choice(s,to_battlefield_tapped=False):
    """v0.76 visible-state land choice with Snow-Covered Plains and repair lines."""
    avail=set(s.library)
    # If a combo creature is stranded, Cave/Map may deliberately begin a repair chain.
    # Saga -> Brainstone is the primary line; Inventors' Fair can find Brainstone/Rack.
    if _hand_contaminated(s):
        if "Urza's Saga" in avail and "Brainstone" in s.library:
            return "Urza's Saga"
        if "Inventors' Fair" in avail and any(x in s.library for x in ("Brainstone","Scroll Rack")):
            return "Inventors' Fair"
    white_now=s.w+s.any+s.restricted_dack_white
    white_sources=sum(x in {"Snow-Covered Plains","Ancient Den","Eiganjo, Seat of the Empire",
                            "City of Brass","Mana Confluence","Gemstone Mine","Starting Town",
                            "Tarnished Citadel"} for x in s.hand)
    if white_now+white_sources<2:
        for x in ("Ancient Den","Snow-Covered Plains","City of Brass","Mana Confluence",
                  "Gemstone Mine","Starting Town"):
            if x in avail:
                return x
    for x in ("Ancient Tomb","City of Traitors","Crystal Vein","Remote Farm","Ruins of Trokair",
              "Urza's Saga","The Mycosynth Gardens","Ancient Den","Snow-Covered Plains"):
        if x in avail:
            return x
    return next((x for x in d.LAND_TUTOR_TARGETS if x in avail),None)
d.land_tutor_choice=land_tutor_choice

# ---------------------------------------------------------------------------
# Exact spell payments for the supported combo creatures / commander.
# ---------------------------------------------------------------------------
def _combo_hand(s):
    return tuple(x for x in s.hand if x in COMBOS)

def _has_marker(s,name,marker):
    return any(p.name==name and p.aux==marker for p in s.battlefield)

def _pearl_reduction(s,g,w):
    if w and any(d.effective_name(x)=="Pearl Medallion" for x in s.battlefield):
        return max(0,g-1)
    return g

def _dack_payment_states(s):
    """Post-payment states for casting first-cast Dack from the command zone."""
    if not d.stax_allows(s,DACK,is_creature=True):
        return []
    g=_pearl_reduction(s,4,2)
    needw=2
    out=[]
    # restricted_dack_white can pay either a Dack white pip or Dack generic.
    max_rdw=min(s.restricted_dack_white,g+needw)
    for rdw_total in range(max_rdw+1):
        for rdw_white in range(min(needw,rdw_total)+1):
            rdw_generic=rdw_total-rdw_white
            if rdw_generic>g:
                continue
            q0=replace(s,restricted_dack_white=s.restricted_dack_white-rdw_total)
            for q in d.pay_options(q0,g-rdw_generic,needw-rdw_white,legend=True):
                if d.payment_stax_ok(s,q):
                    out.append(q)
    return _dedupe(out)

def _cast_combo_creature_states(s,name):
    if name not in s.hand:
        return []
    # Giant is only a supported cast after the Dack->(Preston,Throne) setup.
    if name==GIANT and not _has_marker(s,DACK,"DACK_SETUP_GIANT"):
        return []
    art=(name==THRONE)
    legend=(name==PRESTON)
    if not d.stax_allows(s,name,is_artifact=art,is_creature=True):
        return []
    if name==THRONE:
        g,w=4,0
    elif name==PRESTON:
        g,w=3,1
    else:
        g,w=6,1
    g=_pearl_reduction(s,g,w)
    out=[]
    for paid in d.pay_options(s,g,w,legend=legend,artifact=art):
        if not d.payment_stax_ok(s,paid):
            continue
        h=list(paid.hand); h.remove(name)
        base=replace(
            paid,
            hand=d.sort_hand(h),
            spells=paid.spells+1,
            nonartifact_spells=paid.nonartifact_spells+(0 if art else 1),
            # all three are creatures, so noncreature_spells does not increase
        )
        perm=d.Perm(name,False,0,s.turn,aux="CAST_COMBO")
        bf=d.artifact_enters_bf(base.battlefield,perm) if art else base.battlefield+(perm,)
        won=(name==GIANT and _has_marker(base,DACK,"DACK_SETUP_GIANT"))
        out.append(replace(base,battlefield=bf,success=(base.success or won)))
    return _dedupe(out)

def _precast_tp(s):
    return {p.name for p in s.battlefield
            if p.aux=="CAST_COMBO" and p.name in {THRONE,PRESTON}}

def _dack_giant_setup_actions(s):
    """Cast Dack with Giant still in hand after any needed Throne/Preston pre-casts.
    Dack supplies whichever of Throne/Preston are still in the library; Giant is then
    actually cast from hand. This also supports the very rare multi-creature hands.
    """
    ch=set(_combo_hand(s))
    if GIANT not in ch or THRONE in ch or PRESTON in ch:
        return []
    casted=_precast_tp(s)
    missing={THRONE,PRESTON}-casted
    if not missing.issubset(set(s.library)):
        return []
    out=[]
    for paid in _dack_payment_states(s):
        lib=list(paid.library)
        for x in missing:
            lib.remove(x)
        base=replace(
            paid,
            library=d.shuffled_unknown(lib),
            spells=paid.spells+1,
            nonartifact_spells=paid.nonartifact_spells+1,
            battlefield=paid.battlefield+(d.Perm(DACK,False,0,s.turn,aux="DACK_SETUP_GIANT"),)
        )
        bf=base.battlefield
        if PRESTON in missing:
            bf=bf+(d.Perm(PRESTON,False,0,s.turn,aux="DACK_ETB"),)
        if THRONE in missing:
            bf=d.artifact_enters_bf(bf,d.Perm(THRONE,False,0,s.turn,aux="DACK_ETB"))
        out.append(replace(base,battlefield=bf))
    return _dedupe(out)

def _dack_layout_supported(s):
    """Direct terminal Dack line when Giant is still in library.
    Any subset of Throne/Preston may already have been cast from hand.
    """
    if _combo_hand(s):
        return False
    casted=_precast_tp(s)
    if not casted.issubset({THRONE,PRESTON}):
        return False
    lib=set(s.library)
    missing={THRONE,PRESTON}-casted
    return GIANT in lib and missing.issubset(lib)

def can_cast_dack(s):
    """Terminal success predicate under the explicit user-approved combo sequences."""
    if s.success:
        return True
    if not _dack_layout_supported(s):
        return False
    return bool(_dack_payment_states(s))
d.can_cast_dack=can_cast_dack

# Add legal combo creature casts and the Dack->Giant setup to the normal action graph.
_v076_cast_actions=d.cast_actions
def _enlightened_repair_actions(s):
    if "Enlightened Tutor" not in s.hand or not _hand_contaminated(s):
        return []
    if not d.stax_allows(s,"Enlightened Tutor"):
        return []
    names={x.name for x in s.battlefield}
    g,w=0,1
    if "Thorn of Amethyst" in names: g+=1
    if "Charitable Levy" in names: g+=1
    if any(x.name=="Trinisphere" and not x.tapped for x in s.battlefield):
        g=max(g,3-w)
    out=[]
    for paid in d.pay_options(s,g,w):
        if not d.payment_stax_ok(s,paid):
            continue
        for target in _repair_artifacts(paid,False):
            h=list(paid.hand); h.remove("Enlightened Tutor")
            lib=list(paid.library); lib.remove(target)
            out.append(replace(
                paid, hand=d.sort_hand(h),
                library=(target,)+d.shuffled_unknown(lib),
                grave=paid.grave+("Enlightened Tutor",),
                spells=paid.spells+1,
                nonartifact_spells=paid.nonartifact_spells+1,
                noncreature_spells=paid.noncreature_spells+1
            ))
    return out

def _levy_snow_fetch_branches(s,states):
    """Charitable Levy searches for a Plains card; Snow-Covered Plains qualifies."""
    if not any(x.name=="Charitable Levy" for x in s.battlefield):
        return list(states)
    out=list(states)
    for q in states:
        levy_sacrificed=(q.grave.count("Charitable Levy")>s.grave.count("Charitable Levy")
                         and not any(x.name=="Charitable Levy" for x in q.battlefield))
        if levy_sacrificed and "Snow-Covered Plains" in q.library:
            lib=list(q.library); lib.remove("Snow-Covered Plains")
            bf=q.battlefield+(d.Perm("Snow-Covered Plains",True,0,q.turn),)
            out.append(replace(q,battlefield=bf,library=d.shuffled_unknown(lib)))
    return out

def cast_actions(s):
    inherited=list(_v076_cast_actions(s))
    out=_levy_snow_fetch_branches(s,inherited)
    out.extend(_enlightened_repair_actions(s))
    out.extend(_cast_combo_creature_states(s,THRONE))
    out.extend(_cast_combo_creature_states(s,PRESTON))
    out.extend(_cast_combo_creature_states(s,GIANT))
    out.extend(_dack_giant_setup_actions(s))
    return _dedupe(out)
d.cast_actions=cast_actions

# Tutor repair branches that must coexist with the historical deterministic acceleration target.
_v076_v03_actions=d.v03_actions
def v03_actions(s):
    out=list(_v076_v03_actions(s))

    # Tezzeret -3: MV <= 1, so Brainstone is the only hand-repair target among Rack/Brainstone.
    if _hand_contaminated(s) and "Brainstone" in s.library:
        for i,p in enumerate(s.battlefield):
            if p.name=="Tezzeret, Cruel Captain" and p.activated_turn!=s.turn and p.loyalty>=3:
                lib=list(s.library); lib.remove("Brainstone")
                bf=list(s.battlefield); bf[i]=replace(p,loyalty=p.loyalty-3,activated_turn=s.turn)
                out.append(replace(s,battlefield=tuple(bf),library=d.shuffled_unknown(lib),
                                   hand=d.sort_hand(s.hand+("Brainstone",))))

    # Inventors' Fair: unrestricted artifact tutor, so branch Brainstone and Scroll Rack.
    if _hand_contaminated(s):
        for p in s.battlefield:
            if p.name!="Inventors' Fair" or p.tapped or not d.metalcraft(s):
                continue
            for paid in d.pay_options(s,4):
                fi=next((j for j,x in enumerate(paid.battlefield)
                         if x.name=="Inventors' Fair" and not x.tapped),None)
                if fi is None:
                    continue
                for target in _repair_artifacts(paid,False):
                    lib=list(paid.library); lib.remove(target)
                    bf=list(paid.battlefield); bf.pop(fi)
                    out.append(replace(paid,battlefield=tuple(bf),library=d.shuffled_unknown(lib),
                                       hand=d.sort_hand(paid.hand+(target,)),
                                       grave=paid.grave+("Inventors' Fair",)))

    # Urza's Cave repair chain: allow Saga -> Brainstone or Fair -> Brainstone/Rack,
    # instead of forcing only the normal mana-land heuristic.
    if _hand_contaminated(s) and any(x.name=="Urza's Cave" and not x.tapped for x in s.battlefield):
        for paid in d.pay_options(s,3):
            ci=next((j for j,x in enumerate(paid.battlefield)
                     if x.name=="Urza's Cave" and not x.tapped),None)
            if ci is None:
                continue
            repair_lands=[]
            if "Urza's Saga" in paid.library and "Brainstone" in paid.library:
                repair_lands.append("Urza's Saga")
            if "Inventors' Fair" in paid.library and any(x in paid.library for x in ("Brainstone","Scroll Rack")):
                repair_lands.append("Inventors' Fair")
            for target in repair_lands:
                lib=list(paid.library); lib.remove(target)
                bf=list(paid.battlefield); bf.pop(ci)
                counters=1 if target=="Urza's Saga" else 0
                bf.append(d.Perm(target,True,counters,s.turn))
                out.append(replace(paid,battlefield=tuple(bf),library=d.shuffled_unknown(lib),
                                   grave=paid.grave+("Urza's Cave",)))

    # Moonsilver Key may find a basic land; Snow-Covered Plains is a basic Plains.
    if any(x.name=="Moonsilver Key" and not x.tapped for x in s.battlefield):
        for paid in d.pay_options(s,1):
            ki=next((j for j,x in enumerate(paid.battlefield)
                     if x.name=="Moonsilver Key" and not x.tapped),None)
            if ki is not None and "Snow-Covered Plains" in paid.library:
                lib=list(paid.library); lib.remove("Snow-Covered Plains")
                bf=list(paid.battlefield); bf.pop(ki)
                out.append(replace(paid,battlefield=tuple(bf),library=d.shuffled_unknown(lib),
                                   hand=d.sort_hand(paid.hand+("Snow-Covered Plains",)),
                                   grave=paid.grave+("Moonsilver Key",)))
    return _dedupe(out)
d.v03_actions=v03_actions

# Saga III is a separate action layer; branch Brainstone repair while retaining normal acceleration.
_v076_saga_tutor_actions=d.saga_tutor_actions
def saga_tutor_actions(s):
    out=list(_v076_saga_tutor_actions(s))
    if _hand_contaminated(s) and "Brainstone" in s.library:
        for i,p in enumerate(s.battlefield):
            if p.name=="Urza's Saga" and p.aux=="SAGA3":
                lib=list(s.library); lib.remove("Brainstone")
                bf=list(s.battlefield); bf.pop(i)
                bf=list(d.artifact_enters_bf(tuple(bf),d.Perm("Brainstone",False,0,s.turn)))
                out.append(replace(s,battlefield=tuple(bf),library=d.shuffled_unknown(lib)))
    return _dedupe(out)
d.saga_tutor_actions=saga_tutor_actions

# Keep one-creature legal sequence states alive in the production beam.
_v076_score=d.score
def score(s):
    z=_v076_score(s)
    ncombo=sum(x in COMBOS for x in s.hand)
    if ncombo:
        z+=40*ncombo  # neutralize the legacy automatic-contamination hand penalty
    if _has_marker(s,DACK,"DACK_SETUP_GIANT") and GIANT in s.hand:
        z+=350
    if sum(1 for p in s.battlefield if p.aux=="CAST_COMBO" and p.name in {THRONE,PRESTON})==1:
        z+=100
    return z
d.score=score

# ---------------------------------------------------------------------------
# London: creature in hand is no longer hard-zero EV.
# ---------------------------------------------------------------------------
_WEIGHTED_SEQ_CACHE={}
def keep_weighted_ev_seat(hand,unknown_lib,seat,beam=50,samples=6,bottom=(),t3_weight=0.5):
    hand=d.sort_hand(hand); unknown_lib=tuple(unknown_lib); bottom=tuple(bottom)
    ck=(hand,tuple(sorted(unknown_lib)),bottom,int(seat),int(beam),
        int(samples),float(t3_weight),"v076_combo_sequences")
    got=_WEIGHTED_SEQ_CACHE.get(ck)
    if got is not None:
        return got
    base=list(unknown_lib); n=len(base)
    if n<3:
        out={"utility":0.0,"t1":0.0,"t2":0.0,"t3":0.0,"le2":0.0,"le3":0.0}
        _WEIGHTED_SEQ_CACHE[ck]=out
        return out

    rng=random.Random(d._stable_seed(hand+bottom,0x7600 + int(seat)*997))
    order=list(range(n)); rng.shuffle(order)
    counts={1:0,2:0,3:0}; trials=0
    S=max(1,int(samples))
    for j in range(S):
        inds=[]
        cursor=(j*17) % n
        while len(inds)<3:
            cand=order[(cursor + len(inds)*37 + j*13) % n]
            if cand not in inds:
                inds.append(cand)
            else:
                cursor=(cursor+1)%n
        pick=set(inds)
        first3=[base[i] for i in inds]
        rem=[c for i,c in enumerate(base) if i not in pick]
        rr=random.Random(d._stable_seed(hand+bottom,0x7601 + j*131 + int(seat)*19))
        rr.shuffle(rem)
        ll=tuple(first3+rem+list(bottom))
        wt=d._win_turn_from_unknown_order(hand,ll,int(seat),beam,max_turn=3)
        if wt:
            counts[wt]+=1
        trials+=1
    t1=counts[1]/trials; t2=counts[2]/trials; t3=counts[3]/trials
    out={
        "utility":t1+t2+float(t3_weight)*t3,
        "t1":t1,"t2":t2,"t3":t3,
        "le2":t1+t2,"le3":t1+t2+t3
    }
    _WEIGHTED_SEQ_CACHE[ck]=out
    return out
d.keep_weighted_ev_seat=keep_weighted_ev_seat

def dack_bottom_weighted_ev_seat(seven,keep_n,rest,seat,beam=50,samples=6,t3_weight=0.5,finalists_n=12):
    combos=[()] if keep_n==7 else list(combinations(range(7),7-keep_n))
    candidates=[]
    for inds0 in combos:
        inds=set(inds0)
        hand=d.sort_hand([x for i,x in enumerate(seven) if i not in inds])
        bottom=tuple(seven[i] for i in sorted(inds))
        struct=sum(d.bottom_priority(seven[i],seven) for i in inds)
        contam=sum(x in COMBOS for x in hand)
        aura_kept=sum(x in d.AURAS for x in hand)
        # One combo creature is now a legal sequence, not contamination.
        severe=max(0,contam-1)
        candidates.append(((struct,-severe,-aura_kept),hand,bottom,tuple(rest)))
    candidates.sort(key=lambda x:x[0],reverse=True)
    finalists=candidates[:min(max(1,int(finalists_n)),len(candidates))]
    scored=[]
    for struct,hand,bottom,unknown in finalists:
        ev=keep_weighted_ev_seat(hand,unknown,seat=seat,beam=beam,samples=samples,
                                 bottom=bottom,t3_weight=t3_weight)
        scored.append((ev["utility"],ev,struct,hand,bottom,unknown))
    scored.sort(key=lambda x:(x[0],x[2]),reverse=True)
    return scored[0]
d.dack_bottom_weighted_ev_seat=dack_bottom_weighted_ev_seat

def clear_caches():
    v75.clear_caches()
    _WEIGHTED_SEQ_CACHE.clear()
    for name in ("_WIN_CACHE","_FUTURE_SAMPLE_CACHE","_KEEP_CACHE","_KEEP_SEAT_CACHE","_WEIGHTED_SEAT_CACHE"):
        obj=getattr(d,name,None)
        if hasattr(obj,"clear"):
            obj.clear()

def selftest():
    clear_caches()
    # Validate the inherited v0.75 artifact patch against its own frozen list, then restore v0.76.
    _live=list(d.DECK)
    d.DECK=list(v75.CURRENT_DECK)
    assert v75.selftest()
    d.DECK=_live
    assert len(d.DECK)==99
    assert d.DECK.count("Snow-Covered Plains")==13
    assert "Mouth of Ronom" in d.DECK and "Homeward Path" not in d.DECK

    # New lands are exact speed-equivalent mana sources.
    s=d.State(1,(),(),(d.Perm("Snow-Covered Plains"),))
    assert any(q.w==1 for q in d.tap_mana_actions(s))
    s=d.State(1,(),(),(d.Perm("Mouth of Ronom"),))
    assert any(q.c==1 for q in d.tap_mana_actions(s))

    # Direct clean Dack works.
    s=d.State(1,(),tuple(COMBOS),w=2,c=4)
    assert d.can_cast_dack(s)

    # A creature in hand is NOT an automatic win merely because Dack mana exists.
    for creature in (THRONE,PRESTON,GIANT):
        lib=tuple(x for x in COMBOS if x!=creature)
        s=d.State(1,(creature,),lib,w=8,c=12)
        assert not d.can_cast_dack(s), creature

    # Throne -> Dack.
    s=d.State(1,(THRONE,),(PRESTON,GIANT),c=8,w=2)
    ts=_cast_combo_creature_states(s,THRONE)
    assert ts and any(d.can_cast_dack(q) for q in ts), "Throne -> Dack line missing"

    # Preston -> Dack.
    s=d.State(1,(PRESTON,),(THRONE,GIANT),c=7,w=3)
    ps=_cast_combo_creature_states(s,PRESTON)
    assert ps and any(d.can_cast_dack(q) for q in ps), "Preston -> Dack line missing"

    # Dack -> Giant. 13 total with three white is enough for 4WW then 6W.
    s=d.State(1,(GIANT,),(PRESTON,THRONE),c=10,w=3)
    ds=_dack_giant_setup_actions(s)
    assert ds, "Dack setup for Giant missing"
    gs=[x for q in ds for x in _cast_combo_creature_states(q,GIANT)]
    assert gs and any(d.can_cast_dack(q) for q in gs), "Dack -> Giant line missing"

    # Rule of Law prevents the two-spell same-turn sequence.
    s=d.State(1,(THRONE,),(PRESTON,GIANT),(d.Perm("Rule of Law"),),c=8,w=2)
    ts=_cast_combo_creature_states(s,THRONE)
    assert ts and not any(d.can_cast_dack(q) for q in ts), "Rule of Law failed to stop Throne -> Dack"

    # Two creature cards are not silently declared a win.
    s=d.State(1,(THRONE,PRESTON),(GIANT,),c=20,w=5)
    assert not d.can_cast_dack(s)

    # Multi-creature sequencing: Throne + Preston may both be cast before Dack.
    s=d.State(1,(THRONE,PRESTON),(GIANT,),c=20,w=6)
    t1=_cast_combo_creature_states(s,THRONE)
    t2=[x for q in t1 for x in _cast_combo_creature_states(q,PRESTON)]
    assert t2 and any(d.can_cast_dack(q) for q in t2), "Throne + Preston -> Dack missing"

    # Throne/Preston + Giant: pre-cast the former, Dack supplies the other, then cast Giant.
    s=d.State(1,(THRONE,GIANT),(PRESTON,),c=24,w=6)
    a=_cast_combo_creature_states(s,THRONE)
    b=[x for q in a for x in _dack_giant_setup_actions(q)]
    g=[x for q in b for x in _cast_combo_creature_states(q,GIANT)]
    assert g and any(d.can_cast_dack(q) for q in g), "Throne -> Dack -> Giant missing"

    # Enlightened Tutor can topdeck either repair artifact.
    s=d.State(1,(PRESTON,"Enlightened Tutor"),("Brainstone","Scroll Rack",THRONE,GIANT),w=1)
    er=_enlightened_repair_actions(s)
    assert any(q.library and q.library[0]=="Brainstone" for q in er)
    assert any(q.library and q.library[0]=="Scroll Rack" for q in er)

    # Tezzeret and Saga are correctly limited to the MV1 Brainstone repair.
    s=d.State(1,(PRESTON,),("Brainstone","Scroll Rack",THRONE,GIANT),
              (d.Perm("Tezzeret, Cruel Captain",loyalty=4),))
    assert any("Brainstone" in q.hand for q in d.v03_actions(s))
    s=d.State(3,(PRESTON,),("Brainstone","Scroll Rack",THRONE,GIANT),
              (d.Perm("Urza's Saga",False,3,1,aux="SAGA3"),))
    assert any(any(p.name=="Brainstone" for p in q.battlefield) for q in d.saga_tutor_actions(s))

    # Inventors' Fair can find Rack as well as Brainstone when contaminated.
    s=d.State(2,(PRESTON,),("Brainstone","Scroll Rack",THRONE,GIANT),
              (d.Perm("Inventors' Fair"),d.Perm("Sol Ring"),d.Perm("Mana Vault"),d.Perm("Mox Opal")),c=4)
    fr=d.v03_actions(s)
    assert any("Brainstone" in q.hand for q in fr)
    assert any("Scroll Rack" in q.hand for q in fr)

    # Cave can deliberately start the slow Saga/Fair repair chain.
    s=d.State(2,(PRESTON,),("Urza's Saga","Inventors' Fair","Brainstone","Scroll Rack",THRONE,GIANT),
              (d.Perm("Urza's Cave"),),c=3)
    cr=d.v03_actions(s)
    assert any(any(p.name=="Urza's Saga" for p in q.battlefield) for q in cr)
    assert any(any(p.name=="Inventors' Fair" for p in q.battlefield) for q in cr)

    # Snow-Covered Plains is a legal Moonsilver basic target.
    s=d.State(1,(),("Snow-Covered Plains",),(d.Perm("Moonsilver Key"),),c=1)
    assert any("Snow-Covered Plains" in q.hand for q in d.v03_actions(s))

    # Brainstone can repair the creature to the library, after which clean Dack is legal.
    s=d.State(1,(PRESTON,),("Plains","Sol Ring","Silence",THRONE,GIANT),
              (d.Perm("Brainstone"),),c=6,w=2)
    repaired=d.repair_actions(s)
    assert any(PRESTON in q.library and PRESTON not in q.hand for q in repaired)
    assert any(d.can_cast_dack(q) for q in repaired if PRESTON in q.library and PRESTON not in q.hand)

    clear_caches()
    return True

if __name__=="__main__":
    print("selftest:", "PASS" if selftest() else "FAIL")
