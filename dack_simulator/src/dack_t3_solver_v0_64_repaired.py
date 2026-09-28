
"""
Dack Fayden, Helping Hand T1-T3 solver — v0.11.0

Purpose: auditable, bounded goldfish engine for the current 99.
This version implements the ten requested engine layers as explicit modules.
It is conservative: unsupported/ambiguous actions are not silently granted.

Terminal success:
  Cast Dack Fayden, Helping Hand ({4}{W}{W}) while Boonweaver Giant,
  Preston, the Vanisher, and Roaming Throne are all in the library.

NOTE: this is a focused Dack-deployment engine, not a general MTG engine.
"""
from __future__ import annotations
from dataclasses import dataclass, field, replace
from collections import Counter
from typing import Tuple, FrozenSet
import argparse, random, json, math

COMMANDER="Dack Fayden, Helping Hand"
COMBO_CREATURES=frozenset({"Boonweaver Giant","Preston, the Vanisher","Roaming Throne"})
AURAS=frozenset({
"Bound by Moonsilver","Captured by the Consulate","Coalition Flag","Darksteel Mutation",
"Floating Shield","Gift of Immortality","Idolized",
"Mantle of the Ancients","Sheltered by Ghosts","Shardmage\'s Rescue","Super State","Twinblade Blessing"
})
SPECIAL_MOX=frozenset({"Enlightened Tutor","Loyal Tutor"})
GENERIC_WHITE=frozenset({
"Bilbo's Gambit","Calamity's Wake","Flicker of Fate","March of Otherworldly Light",
"Orim's Chant","Paladin Class","Path to Exile","Portable Hole","Silence",
"Static Prison","Swords to Plowshares","Touch the Spirit Realm","Deafening Silence",
"Rule of Law","Gleaming Splendor"
})
MOX_SAFE=GENERIC_WHITE|SPECIAL_MOX

RAW = """Ancient Den
Ancient Tomb
Arcane Signet
Basalt Monolith
Bilbo's Gambit
Boonweaver Giant
Bound by Moonsilver
Brainstone
Calamity's Wake
Campfire
Candelabra of Tawnos
Captured by the Consulate
Cavern of Souls
Chrome Mox
City of Brass
City of Traitors
Coalition Flag
Coalition Relic
Command Beacon
Crystal Vein
Cursed Totem
Darksteel Mutation
Deafening Silence
Defense Grid
Eiganjo, Seat of the Empire
Eldrazi Confluence
Emeria's Call
Enlightened Tutor
Everflowing Chalice
Expedition Map
Fellwar Stone
Floating Shield
Gemstone Caverns
Gemstone Mine
Giant's Boulder
Gift of Immortality
Gleaming Splendor
Great Hall of the Citadel
Grim Monolith
Idolized
Jeweled Amulet
Kozilek's Command
Lion's Eye Diamond
Liquimetal Torque
Lotus Petal
Loyal Tutor
Mana Confluence
Mana Vault
Manifold Key
Mantle of the Ancients
March of Otherworldly Light
Mishra's Workshop
Moonsilver Key
Mox Diamond
Mox Opal
Orim's Chant
Paladin Class
Path to Exile
Pearl Medallion
Pentad Prism
Plains
Plains
Plains
Plains
Portable Hole
Preston, the Vanisher
Prismatic Lens
Razorgrass Ambush
Remote Farm
Roaming Throne
Ruins of Trokair
Rule of Law
Scroll Rack
Shardmage's Rescue
Shefet Dunes
Sheltered by Ghosts
Silence
Sol Ring
Spire of Industry
Starting Town
Static Prison
Super State
Swords to Plowshares
Talon Gates of Madara
Tarnished Citadel
Tezzeret, Cruel Captain
The Mind Stone
The Mycosynth Gardens
Thorn of Amethyst
Tooth of Ramos
Touch the Spirit Realm
Trinisphere
Twinblade Blessing
Untaidake, the Cloud Keeper
Urza's Cave
Urza's Saga
Vexing Bauble
Void Mirror
Voltaic Key""".splitlines()
DECK=RAW
assert len(DECK)==99

# ---------- 1. core state / turn engine ----------
@dataclass(frozen=True)
class Perm:
    name:str
    tapped:bool=False
    counters:int=0
    entered_turn:int=0
    aux:str=""
    loyalty:int=0
    activated_turn:int=0

@dataclass(frozen=True)
class State:
    turn:int
    hand:Tuple[str,...]
    library:Tuple[str,...]
    battlefield:Tuple[Perm,...]=()
    grave:Tuple[str,...]=()
    exile:Tuple[str,...]=()
    land_played:bool=False
    w:int=0
    c:int=0
    any:int=0
    restricted_legend:int=0
    restricted_artifact:int=0
    restricted_dack_white:int=0
    treasures:int=0
    spawn:int=0
    spells:int=0
    nonartifact_spells:int=0
    noncreature_spells:int=0
    saga_age:Tuple[Tuple[str,int],...]=()
    success:bool=False
    repaired:int=0
    map_bonus_used:int=0

def sort_hand(xs): return tuple(sorted(xs))
def draw(s,n=1):
    n=min(n,len(s.library))
    return replace(s,hand=sort_hand(s.hand+s.library[:n]),library=s.library[n:])

def untap_and_begin(s):
    bf=tuple(replace(x,tapped=(x.tapped if effective_name(x) in {"Mana Vault","Grim Monolith","Basalt Monolith"} else False)) for x in s.battlefield)
    # Coalition Relic charge counters remain through upkeep/draw; they release at the beginning
    # of the first main phase, not during upkeep.
    return replace(s,battlefield=bf,w=0,c=0,any=0,restricted_legend=0,
                   restricted_artifact=0,restricted_dack_white=0,land_played=False,spells=0,nonartifact_spells=0,noncreature_spells=0,map_bonus_used=0)

def add_opponent_cycle_resources(s):
    # Locked goldfish abstraction: a Gleaming Splendor that survived the previous turn cycle
    # has produced exactly one Treasure before our next upkeep.
    if any(x.name=="Gleaming Splendor" for x in s.battlefield):
        return replace(s,treasures=s.treasures+1)
    return s

def begin_first_main(s):
    # Coalition Relic trigger resolves at the beginning of the first main phase.
    charge=sum(x.counters for x in s.battlefield if x.name=="Coalition Relic")
    if not charge:return s
    bf=tuple(replace(x,counters=0) if x.name=="Coalition Relic" else x for x in s.battlefield)
    return replace(s,battlefield=bf,any=s.any+charge)

# ---------- 2. mana / land layer ----------
LANDS=frozenset({
"Ancient Den","Ancient Tomb","Cavern of Souls","City of Traitors","Command Beacon",
"Crystal Vein","Eiganjo, Seat of the Empire","Gemstone Caverns","Gemstone Mine","City of Brass","Mana Confluence",
"Great Hall of the Citadel","Mishra's Workshop","Planar Nexus",
"Remote Farm","Ruins of Trokair","Talon Gates of Madara","The Mycosynth Gardens",
"Untaidake, the Cloud Keeper","Urza's Cave","Urza's Mine","Urza's Power Plant",
"Urza's Saga","Urza's Tower","Urza's Workshop","Plains"
})
ETB_TAPPED=frozenset({"Remote Farm","Ruins of Trokair","Untaidake, the Cloud Keeper"})
WHITE_LANDS=frozenset({"Plains","Ancient Den","Eiganjo, Seat of the Empire","Shefet Dunes"})

def effective_name(p):
    return p.aux[5:] if p.aux.startswith("COPY:") else p.name

def is_artifact_perm(name):
    return name in {
"Ancient Den","Arcane Signet","Basalt Monolith","Brainstone","Campfire","Candelabra of Tawnos",
"Chrome Mox","Coalition Relic","Defense Grid","Everflowing Chalice","Expedition Map",
"Fellwar Stone","Giant's Boulder","Grim Monolith","Jeweled Amulet","Lion's Eye Diamond",
"Liquimetal Torque","Lotus Petal","Mana Vault","Manifold Key","Mox Diamond","Mox Opal",
"Portable Hole","Prismatic Lens","Pentad Prism","Moonsilver Key","Sol Ring","The Mind Stone","Tooth of Ramos","Vexing Bauble",
"Void Mirror","Voltaic Key","Cursed Totem","Trinisphere","Thorn of Amethyst"}

def urza_count(s):
    return sum(x.name in {"Urza's Mine","Urza's Power Plant","Urza's Tower","Urza's Workshop","Planar Nexus"} for x in s.battlefield)

def tron_present(s):
    names={x.name for x in s.battlefield}
    return "Planar Nexus" in names or {"Urza's Mine","Urza's Power Plant","Urza's Tower"}<=names

def metalcraft(s):
    return sum(is_artifact_perm(effective_name(x)) for x in s.battlefield)+s.treasures>=3

def play_land_actions(s):
    if s.land_played:return []
    out=[]
    # Modal DFC land faces. They are not land cards in hand for Mox Diamond.
    for i,n in enumerate(s.hand):
        if n in {"Emeria's Call","Razorgrass Ambush"}:
            h=list(s.hand);h.pop(i)
            landname="Emeria, Shattered Skyclave" if n=="Emeria's Call" else "Razorgrass Field"
            tapped=(n=="Razorgrass Ambush")  # Emeria may pay 3 life; life is outside this goldfish objective.
            # Playing an MDFC land face is still playing a land, so it triggers City of Traitors.
            bf=tuple(replace(x,aux="CITY_PENDING") if x.name=="City of Traitors" else x for x in s.battlefield)
            out.append(replace(s,hand=sort_hand(h),battlefield=bf+(Perm(landname,tapped,0,s.turn),),land_played=True))

    for i,n in enumerate(s.hand):
        if n not in LANDS: continue
        h=list(s.hand);h.pop(i)
        tapped=n in ETB_TAPPED
        counters=2 if n=="Remote Farm" else 0
        # City of Traitors triggers when another land is played. Keep it temporarily with a
        # pending marker so mana/untap abilities may be activated in response before sacrifice.
        bf=list(s.battlefield)
        if n!="City of Traitors":
            bf=[replace(x,aux="CITY_PENDING") if x.name=="City of Traitors" else x for x in bf]
        if n=="Gemstone Mine": counters=3
        bf.append(Perm(n,tapped,(1 if n=="Urza's Saga" else counters),s.turn))
        out.append(replace(s,hand=sort_hand(h),battlefield=tuple(bf),land_played=True))
    return out


def city_trigger_pending(s):
    return any(x.name=="City of Traitors" and x.aux=="CITY_PENDING" for x in s.battlefield)

def resolve_city_trigger_actions(s):
    if not city_trigger_pending(s):return []
    bf=tuple(x for x in s.battlefield if not (x.name=="City of Traitors" and x.aux=="CITY_PENDING"))
    return [replace(s,battlefield=bf)]

def tap_mana_actions(s):
    out=[]
    for i,p in enumerate(s.battlefield):
        if p.tapped: continue
        n=effective_name(p)
        dw=dc=da=rl=ra=rdw=0; remove=False; newc=p.counters
        if n in WHITE_LANDS or n in {"Emeria, Shattered Skyclave","Razorgrass Field"}: dw=1
        elif n in {"City of Brass","Mana Confluence","Starting Town"}: da=1
        elif n=="Gemstone Mine":
            da=1; newc=p.counters-1
            if newc<=0: remove=True
        elif n=="Tarnished Citadel":
            # colored mode (3 damage ignored); colorless mode emitted below as an alternative.
            da=1
        elif n=="Spire of Industry":
            # Colored mode requires controlling an artifact (not Metalcraft).
            if any(is_artifact_perm(effective_name(x)) for x in s.battlefield) or s.treasures>0: da=1
            else: dc=1
        elif n=="Ancient Tomb": dc=2
        elif n=="City of Traitors": dc=2
        elif n=="Crystal Vein": dc=1 # sacrifice mode separately
        elif n=="Great Hall of the Citadel": dc=1
        elif n=="Mishra's Workshop": ra=3
        elif n=="Untaidake, the Cloud Keeper": rl=2
        elif n=="Planar Nexus": dc=1
        elif n=="Urza's Workshop":
            dc=urza_count(s) if metalcraft(s) else 1
        elif n=="Urza's Mine": dc=2 if tron_present(s) else 1
        elif n=="Urza's Power Plant": dc=2 if tron_present(s) else 1
        elif n=="Urza's Tower": dc=3 if tron_present(s) else 1
        elif n=="Gemstone Caverns":
            if p.counters: da=1
            else: dc=1
        elif n=="Cavern of Souls": dc=1
        elif n in {"Command Beacon","The Mycosynth Gardens","Urza's Cave","Urza's Saga"}: dc=1
        elif n=="Eiganjo, Seat of the Empire": dw=1
        elif n=="Talon Gates of Madara": dc=1
        elif n=="Remote Farm" and p.counters>0:
            dw=2;newc-=1
            if newc<=0: remove=True
        elif n=="Ruins of Trokair": dw=1
        elif n in {"Sol Ring"}: dc=2
        elif n in {"Mana Vault"}: dc=3
        elif n in {"Grim Monolith"}: dc=3
        elif n in {"Basalt Monolith"}: dc=3
        elif n=="Everflowing Chalice" and p.counters>0: dc=p.counters
        elif n in {"Arcane Signet","Fellwar Stone"}: dw=1
        elif n=="Mox Diamond": dw=1
        elif n=="Chrome Mox": dw=1
        elif n=="The Mind Stone": dw=1
        elif n in {"Liquimetal Torque","Prismatic Lens"}: dc=1
        elif n=="Mox Opal" and metalcraft(s): da=1
        elif n=="Coalition Relic": da=1
        elif n=="Pentad Prism" and p.counters>0:
            da=1; newc-=1
        elif n=="Everflowing Chalice": dc=p.counters
        elif n=="Jeweled Amulet" and p.counters>0:
            if p.aux=="W": dw=1
            else: dc=1
            newc=0
        elif n=="Tooth of Ramos": dc=1
        else: continue
        bf=list(s.battlefield)
        if remove:
            bf.pop(i)
        else:
            bf[i]=replace(p,tapped=True,counters=newc)
        out.append(replace(s,battlefield=tuple(bf),w=s.w+dw,c=s.c+dc,any=s.any+da,
                           restricted_legend=s.restricted_legend+rl,
                           restricted_artifact=s.restricted_artifact+ra,
                           restricted_dack_white=s.restricted_dack_white+rdw))
    # Lands with a meaningful colorless alternative.
    for i,p in enumerate(s.battlefield):
        if p.name in {"Shefet Dunes","Tarnished Citadel","Starting Town"} and not p.tapped:
            bf=list(s.battlefield); bf[i]=replace(p,tapped=True)
            out.append(replace(s,battlefield=tuple(bf),c=s.c+1))
        elif p.name=="Spire of Industry" and not p.tapped and (any(is_artifact_perm(effective_name(x)) for x in s.battlefield) or s.treasures>0):
            # Spire always has T:C in addition to its conditional any-color mode.
            bf=list(s.battlefield); bf[i]=replace(p,tapped=True)
            out.append(replace(s,battlefield=tuple(bf),c=s.c+1))
    # Cavern of Souls naming Human: colored mana is restricted to Human creature spells; Dack is Human.
    for i,p in enumerate(s.battlefield):
        if p.name=="Cavern of Souls" and not p.tapped:
            bf=list(s.battlefield);bf[i]=replace(p,tapped=True)
            out.append(replace(s,battlefield=tuple(bf),restricted_dack_white=s.restricted_dack_white+1))
    # Planar Nexus / Talon Gates: 1,T -> one mana of any color.
    for i,p in enumerate(s.battlefield):
        if p.name in {"Planar Nexus","Talon Gates of Madara"} and not p.tapped:
            q=pay_simple(s,1)
            if q:
                bf=list(q.battlefield);bf[i]=replace(bf[i],tapped=True)
                out.append(replace(q,battlefield=tuple(bf),any=q.any+1))
    # Prismatic Lens: 1,T -> one mana of any color.
    for i,p in enumerate(s.battlefield):
        if effective_name(p)=="Prismatic Lens" and not p.tapped:
            q=pay_simple(s,1)
            if q:
                bf=list(q.battlefield);bf[i]=replace(bf[i],tapped=True)
                out.append(replace(q,battlefield=tuple(bf),any=q.any+1))
    # Crystal Vein sacrifice for CC.
    for i,p in enumerate(s.battlefield):
        if p.name=="Crystal Vein" and not p.tapped:
            bf=list(s.battlefield);bf.pop(i)
            out.append(replace(s,battlefield=tuple(bf),c=s.c+2,grave=s.grave+("Crystal Vein",)))
    # Ruins sacrifice WW.
    for i,p in enumerate(s.battlefield):
        if p.name=="Ruins of Trokair" and not p.tapped:
            bf=list(s.battlefield);bf.pop(i)
            out.append(replace(s,battlefield=tuple(bf),w=s.w+2,grave=s.grave+("Ruins of Trokair",)))
    # treasures/spawn
    if s.treasures: out.append(replace(s,treasures=s.treasures-1,any=s.any+1))
    if s.spawn: out.append(replace(s,spawn=s.spawn-1,c=s.c+1))
    for i,p in enumerate(s.battlefield):
        if (p.aux[5:] if p.aux.startswith("COPY:") else p.name)=="Lotus Petal":
            bf=list(s.battlefield); bf.pop(i)
            out.append(replace(s,battlefield=tuple(bf),w=s.w+1,grave=s.grave+("Lotus Petal",)))
        elif (p.aux[5:] if p.aux.startswith("COPY:") else p.name)=="Lion's Eye Diamond":
            contaminated=any(x in COMBO_CREATURES for x in s.hand)
            future_draws=max(0,3-s.turn)
            campfire_reachable=(
                any(effective_name(x)=="Campfire" for x in s.battlefield)
                or ("Campfire" in s.library and (
                    "Campfire" in s.library[:future_draws]
                    or any(x.name=="Urza's Saga" and x.counters>=2 for x in s.battlefield)
                    or any(x.name=="Tezzeret, Cruel Captain" and x.loyalty>=3 for x in s.battlefield)
                ))
            )
            if contaminated and not campfire_reachable:
                continue
            bf=list(s.battlefield); bf.pop(i)
            out.append(replace(s,battlefield=tuple(bf),w=s.w+3,
                               grave=s.grave+tuple(s.hand)+("Lion's Eye Diamond",),hand=()))
        elif (p.aux[5:] if p.aux.startswith("COPY:") else p.name)=="Tooth of Ramos":
            bf=list(s.battlefield); bf.pop(i)
            out.append(replace(s,battlefield=tuple(bf),w=s.w+1,grave=s.grave+("Tooth of Ramos",)))
    return out

def total_general(s): return s.w+s.c+s.any

def can_pay(s,generic,white=0,colorless=0,legend=False,artifact=False):
    # restricted pools are only usable for matching spell classes
    W=s.w+s.any
    if W<white:return False
    if s.c<colorless:return False
    base=s.w+s.c+s.any
    restricted=(s.restricted_legend if legend else 0)+(s.restricted_artifact if artifact else 0)
    return base+restricted>=generic+white+colorless

_PAY_CACHE={}
def _pay_pool_options(w,c,a,rl,ra,generic,white,colorless,legend,artifact):
    ck=(w,c,a,rl,ra,generic,white,colorless,bool(legend),bool(artifact))
    got=_PAY_CACHE.get(ck)
    if got is not None:return got
    outs=set();maxrl=rl if legend else 0;maxra=ra if artifact else 0
    if c<colorless:
        _PAY_CACHE[ck]=();return ()
    c0=c-colorless
    for ww in range(min(w,white)+1):
      aa=white-ww
      if aa>a:continue
      w0=w-ww;a0=a-aa
      for gw in range(min(w0,generic)+1):
       for gc in range(min(c0,generic-gw)+1):
        for ga in range(min(a0,generic-gw-gc)+1):
         rem=generic-gw-gc-ga
         for grl in range(min(maxrl,rem)+1):
          gra=rem-grl
          if gra<=maxra:
           outs.add((w0-gw,c0-gc,a0-ga,rl-grl,ra-gra))
    got=tuple(outs);_PAY_CACHE[ck]=got;return got

def pay_options(s,generic,white=0,colorless=0,legend=False,artifact=False):
    return [replace(s,w=w,c=c,any=a,restricted_legend=rl,restricted_artifact=ra)
            for w,c,a,rl,ra in _pay_pool_options(s.w,s.c,s.any,s.restricted_legend,s.restricted_artifact,
                                                 generic,white,colorless,legend,artifact)]

def pay_simple(s,generic,white=0,colorless=0,legend=False,artifact=False,payment_rank=0):
    opts=pay_options(s,generic,white,colorless,legend,artifact)
    if not opts:return None
    opts=sorted(opts,key=lambda q:(min(q.w+q.any,2),q.w+q.c+q.any+q.restricted_legend,q.c,q.w),reverse=True)
    # Do not repeat the last legal payment for all higher global payment ranks.
    # cast_actions already deduplicates outcomes; returning None here avoids generating
    # the same branch up to seven extra times before that deduplication step.
    if payment_rank>=len(opts):return None
    return opts[payment_rank]

def utility_actions(s):
    out=[]
    # Explicit self-untaps. These are activated abilities, not turn untaps.
    for i,p in enumerate(s.battlefield):
        if effective_name(p)=="Grim Monolith" and p.tapped:
            for paid in pay_options(s,4):
                bf=list(paid.battlefield);bf[i]=replace(bf[i],tapped=False)
                out.append(replace(paid,battlefield=tuple(bf)))
        if effective_name(p)=="Basalt Monolith" and p.tapped:
            for paid in pay_options(s,3):
                bf=list(paid.battlefield);bf[i]=replace(bf[i],tapped=False)
                out.append(replace(paid,battlefield=tuple(bf)))
    for ki,k in enumerate(s.battlefield):
        if k.name not in {"Voltaic Key","Manifold Key"} or k.tapped:continue
        for paid in pay_options(s,1):
            for ti,target in enumerate(paid.battlefield):
                if ti!=ki and target.tapped and is_artifact_perm(effective_name(target)):
                    bf=list(paid.battlefield);bf[ki]=replace(bf[ki],tapped=True);bf[ti]=replace(bf[ti],tapped=False)
                    out.append(replace(paid,battlefield=tuple(bf)))
    from itertools import combinations
    for ci,ca in enumerate(s.battlefield):
        if ca.name!="Candelabra of Tawnos" or ca.tapped:continue
        inds=[i for i,x in enumerate(s.battlefield) if x.name in LANDS and x.tapped and not (x.name=="The Mycosynth Gardens" and x.aux.startswith("COPY:"))]
        for X in range(1,len(inds)+1):
            for paid in pay_options(s,X):
                for sub in combinations(inds,X):
                    bf=list(paid.battlefield);bf[ci]=replace(bf[ci],tapped=True)
                    for i in sub:bf[i]=replace(bf[i],tapped=False)
                    out.append(replace(paid,battlefield=tuple(bf)))
    return out

# ---------- 4. tutors ----------
ARTIFACT_TUTOR_TARGETS=("Lion's Eye Diamond","Mana Vault","Sol Ring","Candelabra of Tawnos",
"Voltaic Key","Manifold Key","Expedition Map","Jeweled Amulet","Brainstone","Campfire","Giant's Boulder",
"Chrome Mox","Mox Diamond","Mox Opal","Lotus Petal","Portable Hole","Vexing Bauble")
LAND_TUTOR_TARGETS=("Planar Nexus","Ancient Tomb","Urza's Tower","Urza's Workshop","Great Hall of the Citadel",
"Remote Farm","Ruins of Trokair","Plains","City of Traitors","Crystal Vein","The Mycosynth Gardens",
"Ancient Den","Cavern of Souls","Command Beacon","Eiganjo, Seat of the Empire","Gemstone Caverns","Gemstone Mine","City of Brass","Mana Confluence",
"Mishra's Workshop","Talon Gates of Madara","Untaidake, the Cloud Keeper","Urza's Cave",
"Urza's Mine","Urza's Power Plant","Urza's Saga")

_SHUFFLE_CACHE={}
def shuffled_unknown(lib):
    """Deterministic hidden pseudo-shuffle, cached by exact card multiset.
    Repeated tutor branches overwhelmingly shuffle the same remainder; compute that permutation once.
    """
    import random
    sig=tuple(sorted(lib))
    got=_SHUFFLE_CACHE.get(sig)
    if got is not None:return got
    items=sorted(lib)
    seed=_stable_seed(items,salt=0xDACC50)
    random.Random(seed).shuffle(items)
    out=tuple(items);_SHUFFLE_CACHE[sig]=out
    return out

def tutor_from_library(s,source,targets,to_battlefield=False,tapped=False):
    out=[]
    for target in targets:
        if target not in s.library:continue
        lib=list(s.library);lib.remove(target)
        # Search instruction shuffles. Canonicalize unknown remainder so the solver cannot
        # exploit the pre-shuffle top card as if it survived the shuffle.
        # preserve randomized relative order of unknown remainder
        if to_battlefield:
            bf=s.battlefield+(Perm(target,tapped,0,s.turn),)
            out.append(replace(s,library=shuffled_unknown(lib),battlefield=bf))
        else:
            out.append(replace(s,library=shuffled_unknown(lib),hand=sort_hand(s.hand+(target,))))
    return out

# ---------- 5. top/library manipulation ----------
def repair_actions(s):
    out=[]
    from itertools import combinations
    for i,p in enumerate(s.battlefield):
        if effective_name(p)=="Brainstone" and not p.tapped and len(s.library)>=3:
            for paid in pay_options(s,2):
                bf=list(paid.battlefield);bf.pop(i)
                pool=list(paid.hand)+list(paid.library[:3]);seen=set()
                for inds in combinations(range(len(pool)),2):
                    backs=[pool[j] for j in inds];hand2=[x for j,x in enumerate(pool) if j not in inds]
                    orders=[tuple(backs)]
                    if backs[0]!=backs[1]:orders.append(tuple(reversed(backs)))
                    for order in orders:
                        q=replace(paid,hand=sort_hand(hand2),library=order+paid.library[3:],
                            battlefield=tuple(bf),grave=paid.grave+("Brainstone",),
                            repaired=paid.repaired+sum(x in COMBO_CREATURES for x in order))
                        kk=key(q)
                        if kk not in seen:seen.add(kk);out.append(q)
    # Campfire graveyard repair: {2}, {T}, exile Campfire; shuffle the entire graveyard into library.
    # Expose this branch when at least one required combo creature is in the graveyard.
    for i,p in enumerate(s.battlefield):
        if effective_name(p)=="Campfire" and not p.tapped and any(x in COMBO_CREATURES for x in s.grave):
            for paid in pay_options(s,2):
                bf=list(paid.battlefield); removed=bf.pop(i)
                repaired_n=sum(x in COMBO_CREATURES for x in paid.grave)
                merged=list(paid.library)+list(paid.grave)
                q=replace(paid,battlefield=tuple(bf),library=shuffled_unknown(merged),grave=(),
                          exile=paid.exile+(removed.name,),repaired=paid.repaired+repaired_n)
                out.append(q)
    for i,p in enumerate(s.battlefield):
        if effective_name(p)=="Scroll Rack" and not p.tapped and s.library and s.hand:
            for paid in pay_options(s,1):
                H=list(paid.hand);seen=set()
                for kx in range(1,min(len(H),len(paid.library))+1):
                    for inds in combinations(range(len(H)),kx):
                        moved=[H[j] for j in inds]
                        h2=[x for j,x in enumerate(H) if j not in inds]+list(paid.library[:kx])
                        orders=[tuple(moved)]
                        if len(moved)>1:orders.append(tuple(reversed(moved)))
                        for order in orders:
                            bf=list(paid.battlefield);bf[i]=replace(bf[i],tapped=True)
                            q=replace(paid,hand=sort_hand(h2),library=order+paid.library[kx:],
                                battlefield=tuple(bf),repaired=paid.repaired+sum(x in COMBO_CREATURES for x in moved))
                            kk=key(q)
                            if kk not in seen:seen.add(kk);out.append(q)
    return out

def saga_advance(s):
    bf=list(s.battlefield)
    for i,p in enumerate(bf):
        if p.name=="Urza's Saga":
            lore=p.counters+1
            bf[i]=replace(p,counters=lore,aux=("SAGA3" if lore>=3 else p.aux))
    return replace(s,battlefield=tuple(bf))

def artifact_tutor_choice(s):
    """Visible-state deterministic tutor policy; avoids hidden-future target branching."""
    contaminated=any(x in COMBO_CREATURES for x in s.hand)
    grave_contaminated=any(x in COMBO_CREATURES for x in s.grave)
    present=set(s.hand)|{effective_name(x) for x in s.battlefield}
    if grave_contaminated and "Campfire" in s.library and "Campfire" not in present:
        return "Campfire"
    if contaminated and "Brainstone" in s.library:
        return "Brainstone"
    if contaminated and "Lion's Eye Diamond" in present and "Campfire" in s.library and "Campfire" not in present:
        return "Campfire"
    for target in ("Lion's Eye Diamond","Mana Vault","Sol Ring"):
        if target in s.library and target not in present:
            return target
    return None

def saga_tutor_actions(s):
    out=[]
    for i,p in enumerate(s.battlefield):
        if p.name=="Urza's Saga" and p.aux=="SAGA3":
            target=artifact_tutor_choice(s)
            if target:
                lib=list(s.library);lib.remove(target)
                bf=list(s.battlefield);bf.pop(i)
                bf=list(artifact_enters_bf(tuple(bf),Perm(target,False,0,s.turn)))
                out.append(replace(s,battlefield=tuple(bf),library=shuffled_unknown(lib)))
            # chapter resolves even if no target
            bf=list(s.battlefield);bf.pop(i);out.append(replace(s,battlefield=tuple(bf)))
    return out

# ---------- 6. London mulligan ----------
def bottom_policy(seven,keep_n):
    # combo creatures bottom first; then expensive/nondeployment cards.
    badrank=lambda x:(0 if x in COMBO_CREATURES else
                      1 if x in AURAS else
                      2 if x in {"Cursed Totem","Defense Grid","Rule of Law","Thorn of Amethyst",
                                 "Trinisphere","Vexing Bauble","Void Mirror","Deafening Silence"} else 3)
    ordered=sorted(seven,key=badrank)
    bottom=ordered[:7-keep_n]
    hand=list(seven)
    for x in bottom:hand.remove(x)
    return sort_hand(hand),tuple(bottom)



_KEEP_CACHE={}
# ---------- 6. conditional-draw London EV ----------
_KEEP_CACHE={}
_BOTTOM_CACHE={}

def _stable_seed(items, salt=0):
    h=(2166136261 ^ salt)&0xffffffff
    for x in items:
        for ch in x:
            h=((h^ord(ch))*16777619)&0xffffffff
    return h

def gemstone_exile_choice(hand):
    """Visible-state deterministic exile choice; never inspect library/future draws."""
    candidates=[x for x in hand if x!="Gemstone Caverns" and x not in COMBO_CREATURES]
    if not candidates:return None
    # Same structural philosophy as London bottoms: dead/non-ramp first, mana engines last.
    return max(candidates,key=lambda x:(bottom_priority(x,hand),x))

def _pregame_states(s,seat):
    if seat==0 or "Gemstone Caverns" not in s.hand:return [s]
    out=[s]
    card=gemstone_exile_choice(s.hand)
    if card is not None:
        hh=list(s.hand);hh.remove(card);hh.remove("Gemstone Caverns")
        out.append(replace(s,hand=sort_hand(hh),
            battlefield=s.battlefield+(Perm("Gemstone Caverns",False,1,0),),
            exile=s.exile+(card,)))
    return out

def _t2_from_unknown_order(hand, ordered_lib, seat, beam=500):
    """Conditional T2 success for one sampled unknown-library ordering.
    Crucially, the solver does not see T2's card until T2 actually draws it."""
    pre=_pregame_states(State(1,hand,tuple(ordered_lib)),seat)
    # T1 draw is part of the conditional future, not a requirement of visible keep.
    states=[]
    for s in pre:
        s=draw(s,1)
        wins,fr=search_turn_frontier_many([s],beam=beam,depth=22)
        if wins:return 1
        states.extend(fr)
    states.sort(key=score,reverse=True);states=states[:beam]
    t2=[]
    for s in states:
        q=replace(s,turn=2);q=untap_and_begin(q);q=add_opponent_cycle_resources(q)
        for uq in mana_vault_upkeep_options(q):
            uq=draw(uq,1);uq=saga_advance(uq);uq=begin_first_main(uq)
            t2.append(uq)
    wins,_=search_turn_frontier_many(t2,beam=beam,depth=24)
    return int(bool(wins))

def _win_turn_from_unknown_order_uncached(hand, ordered_lib, seat, beam=500, max_turn=3):
    """Return earliest valid Dack turn (1/2/3), or 0 if no win by max_turn."""
    states=_pregame_states(State(1,hand,tuple(ordered_lib)),seat)
    for turn in range(1,max_turn+1):
        turn_states=[]
        if turn==1:
            for s in states: turn_states.append(draw(s,1))
        else:
            for s in states:
                q=untap_and_begin(replace(s,turn=turn));q=add_opponent_cycle_resources(q)
                for uq in mana_vault_upkeep_options(q):
                    uq=draw(uq,1);uq=saga_advance(uq);uq=begin_first_main(uq)
                    turn_states.append(uq)
        wins,fr=search_turn_frontier_many(turn_states,beam=beam,depth=24 if turn>1 else 22)
        if wins:return turn
        fr.sort(key=score,reverse=True);states=fr[:beam]
    return 0

_WIN_CACHE={}
_WIN_CACHE_HITS=0
_WIN_CACHE_MISSES=0

def _win_turn_from_unknown_order(hand, ordered_lib, seat, beam=500, max_turn=3):
    """Memoize exact conditional game trees as a single byte-like integer outcome 0/1/2/3."""
    global _WIN_CACHE_HITS,_WIN_CACHE_MISSES
    # CARD_ID is defined later at module load, but exists by call time.
    ck=(tuple(sorted(CARD_ID[x] for x in hand)),
        library_token(ordered_lib),int(seat),int(beam),int(max_turn))
    got=_WIN_CACHE.get(ck)
    if got is not None:
        _WIN_CACHE_HITS+=1; return got
    _WIN_CACHE_MISSES+=1
    got=_win_turn_from_unknown_order_uncached(hand,ordered_lib,seat,beam,max_turn)
    _WIN_CACHE[ck]=got
    return got


_FUTURE_SAMPLE_CACHE={}
def _keep_turn_distribution_uncached(hand,unknown_lib,beam=300,samples=8,bottom=()):
    """Nested sampled futures: refining N->M computes only newly requested future samples."""
    hand=sort_hand(hand);unknown_lib=tuple(unknown_lib);bottom=tuple(bottom)
    if any(x in COMBO_CREATURES for x in hand) and not ("Brainstone" in hand or "Scroll Rack" in hand):
        return {"t1":0.0,"t2":0.0,"t3":0.0,"le2":0.0,"le3":0.0}
    import random
    # Common random numbers across London bottom candidates. Candidate hands from the same
    # seven are compared on the same unknown future order instead of independent draw noise.
    base=sorted(unknown_lib)
    rng=random.Random(_stable_seed(tuple(base),0xD3AC))
    n=len(base)
    if n<3:return {"t1":0.0,"t2":0.0,"t3":0.0,"le2":0.0,"le3":0.0}
    counts={1:0,2:0,3:0};trials=0
    for j in range(max(1,samples)):
        inds=list(range(n));rng.shuffle(inds);pick=inds[:3];ps=set(pick)
        first3=[base[i] for i in pick]
        rem=[c for i,c in enumerate(base) if i not in ps];rng.shuffle(rem)
        ll=tuple(first3+rem+list(bottom))
        sk=(tuple(CARD_ID[x] for x in hand),library_token(ll),int(beam))
        got=_FUTURE_SAMPLE_CACHE.get(sk)
        if got is None:
            # Seat affects this goldfish only through Gemstone Caverns: seat 0 is starting,
            # seats 1/2/3 are rules-identical. Solve only the distinct states, then weight them.
            if "Gemstone Caverns" in hand:
                wt0=_win_turn_from_unknown_order(hand,ll,0,beam,max_turn=3)
                wt1=_win_turn_from_unknown_order(hand,ll,1,beam,max_turn=3)
                got=(wt0,wt1,wt1,wt1)
            else:
                wt=_win_turn_from_unknown_order(hand,ll,0,beam,max_turn=3)
                got=(wt,wt,wt,wt)
            _FUTURE_SAMPLE_CACHE[sk]=got
        for wt in got:
            if wt:counts[wt]+=1
            trials+=1
    t1=counts[1]/trials;t2=counts[2]/trials;t3=counts[3]/trials
    return {"t1":t1,"t2":t2,"t3":t3,"le2":t1+t2,"le3":t1+t2+t3}

# ---------- v0.39 compact/memoized evaluator ----------
# Card names are converted to small integers at cache boundaries. This avoids storing duplicate
# long strings in millions of policy-evaluation cache keys while leaving rules code readable.
CARD_ID={n:i for i,n in enumerate(sorted(set(DECK+[COMMANDER])))}
ID_CARD={i:n for n,i in CARD_ID.items()}

# Exact compact library interning. Beam states usually share the very same immutable library
# tuple across many branches. Give each distinct ordered library a small integer token once,
# then use that token in state/cache keys rather than hashing ~90 card names every expansion.
_LIB_OBJ_TOKEN={}
_LIB_INTERN={}
_NEXT_LIB_TOKEN=1
def library_token(lib):
    global _NEXT_LIB_TOKEN
    if not isinstance(lib,tuple):lib=tuple(lib)
    oid=id(lib); got=_LIB_OBJ_TOKEN.get(oid)
    if got is not None and got[0] is lib:return got[1]
    ids=tuple(CARD_ID[x] for x in lib)
    tok=_LIB_INTERN.get(ids)
    if tok is None:
        tok=_NEXT_LIB_TOKEN;_NEXT_LIB_TOKEN+=1;_LIB_INTERN[ids]=tok
    # Keep a strong reference so Python cannot recycle this object id while cached.
    _LIB_OBJ_TOKEN[oid]=(lib,tok)
    return tok

_DIST_CACHE={}
_DIST_CACHE_HITS=0
_DIST_CACHE_MISSES=0

def _ids(xs):
    return tuple(CARD_ID[x] for x in xs)

def _names(ids):
    return tuple(ID_CARD[i] for i in ids)

def clear_distribution_cache():
    global _DIST_CACHE_HITS,_DIST_CACHE_MISSES,_NEXT_LIB_TOKEN
    _DIST_CACHE.clear();_DIST_CACHE_HITS=0;_DIST_CACHE_MISSES=0
    global _WIN_CACHE_HITS,_WIN_CACHE_MISSES
    _WIN_CACHE.clear();_WIN_CACHE_HITS=0;_WIN_CACHE_MISSES=0
    _FUTURE_SAMPLE_CACHE.clear();_SHUFFLE_CACHE.clear()
    _LIB_OBJ_TOKEN.clear();_LIB_INTERN.clear();_NEXT_LIB_TOKEN=1

def distribution_cache_stats():
    return {"distribution_entries":len(_DIST_CACHE),"distribution_hits":_DIST_CACHE_HITS,"distribution_misses":_DIST_CACHE_MISSES,
            "win_entries":len(_WIN_CACHE),"win_hits":_WIN_CACHE_HITS,"win_misses":_WIN_CACHE_MISSES}

def keep_turn_distribution(hand,unknown_lib,beam=300,samples=8,bottom=()):
    """Memoized T1/T2/T3 distribution. Cache stores only five small numeric values."""
    global _DIST_CACHE_HITS,_DIST_CACHE_MISSES
    h=tuple(sorted(_ids(hand))); u=tuple(unknown_lib); b=_ids(bottom)
    ck=(h,library_token(u),b,int(beam),int(samples))
    got=_DIST_CACHE.get(ck)
    if got is not None:
        _DIST_CACHE_HITS+=1
        t1,t2,t3,le2,le3=got
        return {"t1":t1,"t2":t2,"t3":t3,"le2":le2,"le3":le3}
    _DIST_CACHE_MISSES+=1
    ev=_keep_turn_distribution_uncached(_names(h),u,beam,samples,_names(b))
    _DIST_CACHE[ck]=(ev["t1"],ev["t2"],ev["t3"],ev["le2"],ev["le3"])
    return ev

def utility_from_distribution(ev,t3_weight=0.5):
    return ev["le2"]+t3_weight*ev["t3"]

def keep_weighted_ev(hand,unknown_lib,beam=300,samples=8,bottom=(),t3_weight=0.5):
    ev=keep_turn_distribution(hand,unknown_lib,beam=beam,samples=samples,bottom=bottom)
    return {"utility":utility_from_distribution(ev,t3_weight),**ev}


def keep_t2_ev(hand,unknown_lib,beam=500,samples=16,bottom=()):
    """Conditional T2 probability. London-bottomed cards are known to be on the bottom
    and are NEVER included in the T1/T2 unknown draw sample."""
    hand=sort_hand(hand);unknown_lib=tuple(unknown_lib);bottom=tuple(bottom)
    cache_key=(hand,tuple(sorted(unknown_lib)),bottom,beam,samples,"stratpair_bottomsafe")
    if cache_key in _KEEP_CACHE:return _KEEP_CACHE[cache_key]
    if any(x in COMBO_CREATURES for x in hand) and not ("Brainstone" in hand or "Scroll Rack" in hand):
        _KEEP_CACHE[cache_key]=0.0;return 0.0
    import random
    rng=random.Random(_stable_seed(hand+bottom,0xDACC))
    base=list(unknown_lib);n=len(base)
    if n<2:return 0.0
    wins=0;trials=0;S=max(1,samples);order=list(range(n));rng.shuffle(order)
    for j in range(S):
        i1=order[j%n];choices=[i for i in range(n) if i!=i1]
        i2=choices[(j*37+(j//max(1,n)))%len(choices)]
        first,second=base[i1],base[i2]
        rem=[c for i,c in enumerate(base) if i not in {i1,i2}];rng.shuffle(rem)
        ll=[first,second]+rem+list(bottom)
        for seat in range(4):
            wins+=_t2_from_unknown_order(hand,ll,seat,beam);trials+=1
    ev=wins/trials;_KEEP_CACHE[cache_key]=ev;return ev

def keep_t2_ev_firstdraw_stratified(hand,unknown_lib,beam=100,second_samples=1,bottom=()):
    """Enumerate every possible T1 draw from the unknown library; bottom stays bottom."""
    hand=sort_hand(hand);unknown_lib=tuple(unknown_lib);bottom=tuple(bottom)
    if any(x in COMBO_CREATURES for x in hand) and not ("Brainstone" in hand or "Scroll Rack" in hand):return 0.0
    import random
    wins=trials=0
    for i1,first in enumerate(unknown_lib):
        rem1=list(unknown_lib[:i1]+unknown_lib[i1+1:])
        for j in range(max(1,second_samples)):
            i2=(i1*37+j*43)%len(rem1);second=rem1[i2];rem2=rem1[:i2]+rem1[i2+1:]
            rr=random.Random(_stable_seed(hand+bottom,i1*131+j));rr.shuffle(rem2)
            ll=[first,second]+rem2+list(bottom)
            for seat in range(4):
                wins+=_t2_from_unknown_order(hand,ll,seat,beam);trials+=1
    return wins/trials if trials else 0.0


# v0.45 canonical-land audit: these four v0.32 additions were omitted from LANDS.
LANDS = LANDS | frozenset({"Shefet Dunes","Spire of Industry","Starting Town","Tarnished Citadel"})
RAMP_PROTECTED=frozenset({
"Sol Ring","Mana Vault","Grim Monolith","Basalt Monolith","Lotus Petal","Lion's Eye Diamond",
"Mox Diamond","Chrome Mox","Mox Opal","The Mind Stone","Arcane Signet","Fellwar Stone",
"Prismatic Lens","Pentad Prism","Moonsilver Key","Liquimetal Torque","Tooth of Ramos","Jeweled Amulet","Everflowing Chalice",
"Coalition Relic","Candelabra of Tawnos","Voltaic Key","Manifold Key",
"Enlightened Tutor","Loyal Tutor","Tezzeret, Cruel Captain","Expedition Map","Brainstone","Scroll Rack",
"Archaeomancer's Map","Giant's Boulder","Kozilek's Command","Eldrazi Confluence"
,"Pearl Medallion","Gleaming Splendor"})
def bottom_priority(card,seven):
    # Larger = more desirable to bottom.
    if card in COMBO_CREATURES:return 100
    if card in AURAS:return 80
    # Non-ramp spells/permanents before mana development.
    if card not in RAMP_PROTECTED and card not in LANDS and card not in {"Emeria's Call","Razorgrass Ambush"}:return 60
    landish=sum(x in LANDS or x in {"Emeria's Call","Razorgrass Ambush"} for x in seven)
    if (card in LANDS or card in {"Emeria's Call","Razorgrass Ambush"}) and landish>=5:return 45
    # ordinary lands are kept ahead of dead spells but may be bottomed before actual ramp if necessary
    if card in LANDS or card in {"Emeria's Call","Razorgrass Ambush"}:return 15
    # true ramp/tutors/deployment engines last
    return 0

def dack_bottom_ev(seven,keep_n,rest,beam=500,samples=16,refine=False,finalists_n=12):
    from itertools import combinations
    combos=[()] if keep_n==7 else list(combinations(range(7),7-keep_n))
    candidates=[]
    for inds0 in combos:
        inds=set(inds0);hand=sort_hand([x for i,x in enumerate(seven) if i not in inds])
        bottom=tuple(seven[i] for i in sorted(inds))
        # rest is the genuinely unknown library; London bottoms remain separate.
        structural=sum(bottom_priority(seven[i],seven) for i in inds)
        contam=sum(x in COMBO_CREATURES for x in hand)
        aura_kept=sum(x in AURAS for x in hand)
        candidates.append(((structural,-contam,-aura_kept),hand,bottom,tuple(rest)))
    candidates.sort(key=lambda x:x[0],reverse=True)
    # Keep enough alternatives that the hierarchy guides rather than hard-forces the EV answer.
    finalists=candidates[:min(finalists_n,len(candidates))]
    scored=[]
    for struct,hand,bottom,unknown in finalists:
        ev=keep_t2_ev(hand,unknown,beam=beam,samples=samples,bottom=bottom)
        scored.append((ev,struct,hand,bottom,unknown))
    scored.sort(key=lambda x:(x[0],x[1]),reverse=True)
    # High-confidence refinement of the top few only.
    if refine:
        rescored=[]
        for _,struct,hand,bottom,unknown in scored[:min(3,len(scored))]:
            ev=keep_t2_ev_firstdraw_stratified(hand,unknown,beam=min(120,beam),second_samples=1,bottom=bottom)
            rescored.append((ev,struct,hand,bottom,unknown))
        rescored.sort(key=lambda x:(x[0],x[1]),reverse=True);best=rescored[0]
    else:best=scored[0]
    ev,struct,hand,bottom,unknown=best
    # Preserve legacy return shape: final library has unknown cards followed by known bottom.
    lib=tuple(unknown)+tuple(bottom)
    val=(ev,-sum(x in COMBO_CREATURES for x in hand),-sum(x in AURAS for x in hand),struct)
    return (val,hand,bottom,lib)

def dack_bottom_weighted_ev(seven,keep_n,rest,beam=250,samples=8,t3_weight=0.5,finalists_n=3):
    from itertools import combinations
    nbot=7-keep_n
    candidates=[]
    for inds in combinations(range(7),nbot):
        bottom=tuple(seven[i] for i in inds)
        hand=tuple(seven[i] for i in range(7) if i not in inds)
        # structural hierarchy is the cheap first-stage screen
        struct=sum(bottom_priority(x,seven) for x in bottom)
        candidates.append((struct,sort_hand(hand),bottom))
    candidates.sort(key=lambda x:x[0],reverse=True)
    finalists=candidates[:max(1,finalists_n)]
    scored=[]
    for struct,hand,bottom in finalists:
        # bottomed cards are removed from the unknown draw pool
        unknown=tuple(rest)
        ev=keep_weighted_ev(hand,unknown,beam=beam,samples=samples,bottom=bottom,t3_weight=t3_weight)
        scored.append((ev["utility"],ev,struct,hand,bottom,unknown))
    scored.sort(key=lambda x:(x[0],x[2]),reverse=True)
    return scored[0]

def weighted_calibration_batch(seed,k,continuation,n_hands=8,beam=50,samples=4,t3_weight=0.5):
    import random
    rng=random.Random(seed);vals=[];details=[]
    for _ in range(n_hands):
        deck=DECK[:];rng.shuffle(deck);seven=deck[:7];rest=deck[7:]
        raw,ev,struct,hand,bottom,unknown=dack_bottom_weighted_ev(
            seven,k,rest,beam=beam,samples=samples,t3_weight=t3_weight,finalists_n=3)
        vals.append(raw if k==1 else max(raw,continuation));details.append(ev)
    return vals,details

def calibration_batch(seed,k,continuation,n_hands=10,beam=70,samples=8):
    """Resumable batch for one London keep depth. Returns raw optimal values."""
    import random
    rng=random.Random(seed);vals=[]
    for _ in range(n_hands):
        deck=DECK[:];rng.shuffle(deck)
        ev=dack_bottom_ev(deck[:7],k,deck[7:],beam,samples,finalists_n=3)[0][0]
        vals.append(ev if k==1 else max(ev,continuation))
    return vals

def calibrate_mull_values(rng, hands_per_depth=120, beam=350, samples=8):
    """Backward induction continuation values.
    V[k] = expected optimal T2 probability arriving at a fresh seven while keeping k cards.
    A current hand is kept iff its best conditional keep EV >= V[k-1]."""
    V={0:0.0,1:0.0}
    # k=1 is forced: estimate its average best-bottom keep value.
    vals=[]
    for _ in range(hands_per_depth):
        deck=DECK[:];rng.shuffle(deck)
        vals.append(dack_bottom_ev(deck[:7],1,deck[7:],beam,samples,finalists_n=3)[0][0])
    V[1]=sum(vals)/len(vals)
    for k in range(2,8):
        vals=[]
        continuation=V[k-1]
        for _ in range(hands_per_depth):
            deck=DECK[:];rng.shuffle(deck)
            keep_ev=dack_bottom_ev(deck[:7],k,deck[7:],beam,samples,finalists_n=3)[0][0]
            vals.append(max(keep_ev,continuation))
        V[k]=sum(vals)/len(vals)
    return V

def choose_london_hand(rng,V,beam=500,samples=16,refine_margin=0.08,screen_finalists=3):
    """Sequential London mulligan. Refine borderline keep/mull decisions with all-T1-draw stratification."""
    audit=[]
    for keep_n in range(7,0,-1):
        deck=DECK[:];rng.shuffle(deck);seven=deck[:7];rest=deck[7:]
        val,hand,bottom,lib=dack_bottom_ev(seven,keep_n,rest,beam,samples,finalists_n=screen_finalists)
        keep_ev=val[0];threshold=V.get(keep_n-1,0.0);refined=False
        if keep_n>1 and abs(keep_ev-threshold)<=refine_margin:
            # rerun bottom selection with high-confidence refinement
            val,hand,bottom,lib=dack_bottom_ev(seven,keep_n,rest,beam,samples,refine=True,finalists_n=6)
            keep_ev=val[0];refined=True
        decision=(keep_n==1 or keep_ev>=threshold)
        audit.append((keep_n,keep_ev,threshold,decision,seven,hand,bottom,refined))
        if decision:return State(1,hand,lib),keep_n,audit
    raise RuntimeError("London selection failed")
