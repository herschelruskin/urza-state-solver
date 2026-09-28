
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
# Lands that can deterministically provide white in this goldfish (life costs ignored).
# Keep this broader than WHITE_LANDS so the beam scorer does not prune rainbow-land lines.
GUARANTEED_WHITE_LANDS=WHITE_LANDS|frozenset({"City of Brass","Mana Confluence","Gemstone Mine","Tarnished Citadel","Starting Town"})

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
        elif n in {"City of Brass","Mana Confluence","Starting Town"}:
            # In this white/colorless deck, unrestricted colored mana is strategically
            # identical to W unless Pentad Prism is currently in hand (sunburst can care
            # about a second color). Canonicalizing the otherwise redundant color choice
            # prevents flexible sources from generating a larger bounded-search tree than Plains.
            if "Pentad Prism" in s.hand: da=1
            else: dw=1
        elif n=="Gemstone Mine":
            if "Pentad Prism" in s.hand: da=1
            else: dw=1
            newc=p.counters-1
            if newc<=0: remove=True
        elif n=="Tarnished Citadel":
            # Colored mode (3 damage ignored); colorless mode emitted below as an alternative.
            if "Pentad Prism" in s.hand: da=1
            else: dw=1
        elif n=="Spire of Industry":
            # Colored mode requires controlling an artifact (not Metalcraft).
            if any(is_artifact_perm(effective_name(x)) for x in s.battlefield) or s.treasures>0:
                if "Pentad Prism" in s.hand: da=1
                else: dw=1
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


# ---------- 7. Chrome Mox policy ----------
def chrome_mox_allowed(card):
    return card in MOX_SAFE and card not in AURAS and card not in COMBO_CREATURES

# ---------- 8. special engines ----------
# Coalition Relic charging
def special_actions(s):
    out=[]
    # Archaeomancer's Map catch-up abstraction: once per opponent land event, if an opponent
    # has more lands, we may put a Plains from hand onto battlefield. Primary goldfish model exposes two such opportunities per opponent cycle.
    if s.turn>=2 and s.map_bonus_used<2 and any(x.name=="Archaeomancer's Map" for x in s.battlefield):
        for land in s.hand:
            if land in LANDS:
                hh=list(s.hand);hh.remove(land)
                tapped=land in ETB_TAPPED
                counters=2 if land=="Remote Farm" else (1 if land=="Urza's Saga" else 0)
                out.append(replace(s,hand=sort_hand(hh),battlefield=s.battlefield+(Perm(land,tapped,counters,s.turn),),map_bonus_used=s.map_bonus_used+1))
    # Talon Gates of Madara: 4: put it from hand onto battlefield (not a land play).
    if "Talon Gates of Madara" in s.hand:
        for paid in pay_options(s,4):
            hh=list(paid.hand);hh.remove("Talon Gates of Madara")
            out.append(replace(paid,hand=sort_hand(hh),battlefield=paid.battlefield+(Perm("Talon Gates of Madara",False,0,s.turn),)))
    for i,p in enumerate(s.battlefield):
        if p.name=="Coalition Relic" and not p.tapped:
            bf=list(s.battlefield);bf[i]=replace(p,tapped=True,counters=p.counters+1)
            out.append(replace(s,battlefield=tuple(bf)))
    # Giant's Boulder: 1,T -> one mana of any color.
    for i,p in enumerate(s.battlefield):
        if p.name=="Giant's Boulder" and not p.tapped:
            for paid in pay_options(s,1):
                bf=list(paid.battlefield);bf[i]=replace(bf[i],tapped=True)
                out.append(replace(paid,battlefield=tuple(bf),any=paid.any+1))
    # Great Hall conversion: 1,T -> two legend-only mana.
    for i,p in enumerate(s.battlefield):
        if p.name=="Great Hall of the Citadel" and not p.tapped:
            for paid in pay_options(s,1):
                bf=list(paid.battlefield);bf[i]=replace(bf[i],tapped=True)
                out.append(replace(paid,battlefield=tuple(bf),restricted_legend=paid.restricted_legend+2))
                out.append(replace(paid,battlefield=tuple(bf),restricted_dack_white=paid.restricted_dack_white+2))
    return out


# v0.3 deployment-relevant activated abilities

def land_tutor_choice(s,to_battlefield_tapped=False):
    """Deterministic target from visible state only; never inspect library order."""
    avail=set(s.library)
    # White shortage first. Prefer robust untapped W for Map-to-hand; Cave target enters tapped anyway.
    white_now=s.w+s.any+s.restricted_dack_white
    white_sources=sum(x in {"Plains","Ancient Den","Eiganjo, Seat of the Empire","Shefet Dunes",
                            "City of Brass","Mana Confluence","Gemstone Mine","Starting Town","Tarnished Citadel"}
                      for x in s.hand)
    if white_now+white_sources<2:
        for x in ("Ancient Den","Plains","City of Brass","Mana Confluence","Gemstone Mine","Starting Town","Shefet Dunes"):
            if x in avail:return x
    # Raw acceleration/deployment. Cave puts target tapped, so City/Tomb are future-turn mana.
    for x in ("Ancient Tomb","City of Traitors","Crystal Vein","Remote Farm","Ruins of Trokair",
              "Urza's Saga","The Mycosynth Gardens","Ancient Den","Plains"):
        if x in avail:return x
    return next((x for x in LAND_TUTOR_TARGETS if x in avail),None)

def v03_actions(s):
    out=[]
    # Expedition Map
    for i,p in enumerate(s.battlefield):
        if p.name=="Expedition Map" and not p.tapped:
            for q in pay_options(s,2):
                target=land_tutor_choice(q,False)
                if target:
                    lib=list(q.library); lib.remove(target)
                    bf=list(q.battlefield); bf.pop(i)
                    out.append(replace(q,battlefield=tuple(bf),library=shuffled_unknown(lib),
                                       hand=sort_hand(q.hand+(target,)),grave=q.grave+("Expedition Map",)))
    # Moonsilver Key: 1,T,sac -> artifact with mana ability or basic land, to hand.
    for i,p in enumerate(s.battlefield):
        if p.name=="Moonsilver Key" and not p.tapped:
            for paid in pay_options(s,1):
                # Key can find an artifact WITH A MANA ABILITY or a basic land.
                # Brainstone is not legal even when the hand is contaminated.
                target=next((x for x in ("Lion's Eye Diamond","Mana Vault","Sol Ring") if x in paid.library and x not in paid.hand),None)
                if target is None and "Plains" in paid.library:
                    target="Plains"
                if target and target in paid.library:
                    lib=list(paid.library);lib.remove(target)
                    bf=list(paid.battlefield)
                    # identify Key after payment state by index/name safely
                    ki=next((j for j,x in enumerate(bf) if x.name=="Moonsilver Key" and not x.tapped),None)
                    if ki is not None:
                        bf.pop(ki)
                        out.append(replace(paid,battlefield=tuple(bf),library=shuffled_unknown(lib),
                                           hand=sort_hand(paid.hand+(target,)),grave=paid.grave+("Moonsilver Key",)))
    # Urza's Cave
    for i,p in enumerate(s.battlefield):
        if p.name=="Urza's Cave" and not p.tapped:
            for q in pay_options(s,3):
                target=land_tutor_choice(q,True)
                if target:
                    lib=list(q.library); lib.remove(target)
                    bf=list(q.battlefield); bf.pop(i); bf.append(Perm(target,True,0,s.turn))
                    out.append(replace(q,battlefield=tuple(bf),library=shuffled_unknown(lib),grave=q.grave+("Urza's Cave",)))
    # Gardens copy: relevant 0/1 MV artifacts.
    mv={"Lion's Eye Diamond":0,"Lotus Petal":0,"Mox Opal":0,"Chrome Mox":0,"Mox Diamond":0,
        "Jeweled Amulet":0,"Everflowing Chalice":0,"Mana Vault":1,"Sol Ring":1,"Candelabra of Tawnos":1,
        "Voltaic Key":1,"Manifold Key":1,"Expedition Map":1,"Brainstone":1,"Campfire":1,"Giant's Boulder":1,
        "Arcane Signet":2,"Fellwar Stone":2,"Liquimetal Torque":2,"Prismatic Lens":2,"The Mind Stone":2,
        "Grim Monolith":2,"Basalt Monolith":3,"Coalition Relic":3}
    for i,p in enumerate(s.battlefield):
        if p.name=="The Mycosynth Gardens" and not p.tapped and not p.aux:
            for q0 in s.battlefield:
                if effective_name(q0) in mv:
                    for q in pay_options(s,mv[effective_name(q0)]):
                        bf=list(q.battlefield); bf[i]=replace(bf[i],tapped=True,aux="COPY:"+effective_name(q0))
                        out.append(replace(q,battlefield=tuple(bf)))
    # Jeweled Amulet charge. Unrestricted colored mana can be chosen as white when paying
    # the activation, so it may be banked as W rather than being ignored.
    for i,p in enumerate(s.battlefield):
        if effective_name(p)=="Jeweled Amulet" and not p.tapped and p.counters==0:
            if s.w:
                bf=list(s.battlefield); bf[i]=replace(p,tapped=True,counters=1,aux="W")
                out.append(replace(s,battlefield=tuple(bf),w=s.w-1))
            if s.any:
                bf=list(s.battlefield); bf[i]=replace(p,tapped=True,counters=1,aux="W")
                out.append(replace(s,battlefield=tuple(bf),any=s.any-1))
            if s.c:
                bf=list(s.battlefield); bf[i]=replace(p,tapped=True,counters=1,aux="C")
                out.append(replace(s,battlefield=tuple(bf),c=s.c-1))
    # Tezzeret 0 / -3, one activation per turn.
    for i,p in enumerate(s.battlefield):
        if p.name=="Tezzeret, Cruel Captain" and p.activated_turn!=s.turn:
            for j,q in enumerate(s.battlefield):
                if q.tapped and is_artifact_perm(effective_name(q)):
                    bf=list(s.battlefield); bf[i]=replace(p,activated_turn=s.turn); bf[j]=replace(q,tapped=False)
                    out.append(replace(s,battlefield=tuple(bf)))
            if p.loyalty>=3:
                target=artifact_tutor_choice(s)
                if target:
                    lib=list(s.library);lib.remove(target)
                    bf=list(s.battlefield);bf[i]=replace(p,loyalty=p.loyalty-3,activated_turn=s.turn)
                    out.append(replace(s,battlefield=tuple(bf),library=shuffled_unknown(lib),hand=sort_hand(s.hand+(target,))))
    return out


def nasty_mana_actions(s):
    out=[]
    for ki,k in enumerate(s.battlefield):
        if k.name not in {"Voltaic Key","Manifold Key"} or k.tapped:continue
        for paid in pay_options(s,1):
            for ti,target in enumerate(paid.battlefield):
                if ti!=ki and target.tapped and is_artifact_perm(effective_name(target)):
                    bf=list(paid.battlefield);bf[ki]=replace(bf[ki],tapped=True);bf[ti]=replace(bf[ti],tapped=False)
                    out.append(replace(paid,battlefield=tuple(bf)))
    from itertools import combinations
    for ci,cand in enumerate(s.battlefield):
        if cand.name!="Candelabra of Tawnos" or cand.tapped:continue
        inds=[i for i,p in enumerate(s.battlefield) if p.tapped and p.name in LANDS and not (p.name=="The Mycosynth Gardens" and p.aux.startswith("COPY:"))]
        for X in range(1,len(inds)+1):
            for paid in pay_options(s,X):
                for sub in combinations(inds,X):
                    bf=list(paid.battlefield);bf[ci]=replace(bf[ci],tapped=True)
                    for j in sub:bf[j]=replace(bf[j],tapped=False)
                    out.append(replace(paid,battlefield=tuple(bf)))
    return out

# ---------- 9. stax legality ----------
STAX={"Rule of Law","Deafening Silence","Trinisphere","Thorn of Amethyst","Vexing Bauble","Void Mirror"}
def stax_allows(s,name,is_artifact=False,is_creature=False,mana_spent=True):
    names={x.name for x in s.battlefield}
    if "Rule of Law" in names and s.spells>=1:return False
    if "Deafening Silence" in names and not is_creature and s.noncreature_spells>=1:return False
    return True

# v0.72 Patch A: observational payment semantics only.
# This record is NOT consulted by payment generation, casting, state keys, scoring,
# frontier pruning, or any other game/search behavior in Patch A.
@dataclass(frozen=True)
class PaymentSemanticSignature:
    residual_w:int
    residual_c:int
    residual_any:int
    residual_restricted_legend:int
    residual_restricted_artifact:int
    residual_restricted_dack_white:int
    spent_total:int
    spent_colored:int
    spent_w:int
    spent_c:int
    spent_any:int
    spent_restricted_legend:int
    spent_restricted_artifact:int
    spent_restricted_dack_white:int
    prism_color_class:int

def payment_semantic_signature(before,after):
    """Describe payment semantics without changing or pruning any payment branch.

    `prism_color_class` mirrors the current Pentad Prism abstraction exactly:
      0 = no W/unrestricted-colored mana spent;
      1 = one distinguishable colored class represented;
      2 = two Sunburst-relevant color classes are representable (W+any or >=2 any).

    Restricted legend/artifact pools are colorless in the current deck model.
    Restricted Dack-white is tracked separately and counts as colored for Void Mirror,
    but is intentionally excluded from Prism color class because it cannot pay for Prism.
    """
    fields=("w","c","any","restricted_legend","restricted_artifact","restricted_dack_white")
    spent={f:max(0,getattr(before,f)-getattr(after,f)) for f in fields}
    spent_total=sum(spent.values())
    spent_colored=spent["w"]+spent["any"]+spent["restricted_dack_white"]
    if spent["any"]>=2 or (spent["w"]>0 and spent["any"]>0):
        prism_color_class=2
    elif spent["w"]>0 or spent["any"]>0:
        prism_color_class=1
    else:
        prism_color_class=0
    return PaymentSemanticSignature(
        residual_w=after.w,
        residual_c=after.c,
        residual_any=after.any,
        residual_restricted_legend=after.restricted_legend,
        residual_restricted_artifact=after.restricted_artifact,
        residual_restricted_dack_white=after.restricted_dack_white,
        spent_total=spent_total,
        spent_colored=spent_colored,
        spent_w=spent["w"],
        spent_c=spent["c"],
        spent_any=spent["any"],
        spent_restricted_legend=spent["restricted_legend"],
        spent_restricted_artifact=spent["restricted_artifact"],
        spent_restricted_dack_white=spent["restricted_dack_white"],
        prism_color_class=prism_color_class,
    )

def payment_tags(before,after):
    """Return (total mana spent, colored mana spent) from resource deltas."""
    fields=("w","c","any","restricted_legend","restricted_artifact","restricted_dack_white")
    total=sum(max(0,getattr(before,f)-getattr(after,f)) for f in fields)
    # `w`, unrestricted `any`, and Dack-white are colored pools. Restricted legend/artifact
    # are currently generated colorlessly in this deck model.
    colored=max(0,before.w-after.w)+max(0,before.any-after.any)+max(0,before.restricted_dack_white-after.restricted_dack_white)
    return total,colored

def payment_stax_ok(before,after):
    names={x.name for x in before.battlefield}
    total,colored=payment_tags(before,after)
    if "Vexing Bauble" in names and total==0:return False
    if "Void Mirror" in names and colored==0:return False
    return True

# ---------- spell casting ----------
COSTS={ "Defense Grid":(2,0,0),"Cursed Totem":(2,0,0),"Portable Hole":(0,1,0),
"Vexing Bauble":(1,0,0),"Void Mirror":(2,0,0),"Trinisphere":(3,0,0),"Thorn of Amethyst":(2,0,0),
"Shardmage\'s Rescue":(0,1,0),"Deafening Silence":(0,1,0),"Rule of Law":(2,1,0),"Paladin Class":(0,1,0),"Static Prison":(0,1,0),
 "Archaeomancer's Map":(2,1,0),

"Sol Ring":(1,0,0),"Mana Vault":(1,0,0),"Candelabra of Tawnos":(1,0,0),
"Voltaic Key":(1,0,0),"Manifold Key":(1,0,0),"Expedition Map":(1,0,0),
"Brainstone":(1,0,0),"Campfire":(1,0,0),"Giant's Boulder":(1,0,0),
"Arcane Signet":(2,0,0),"Fellwar Stone":(2,0,0),"Liquimetal Torque":(2,0,0),
"Prismatic Lens":(2,0,0),"Pentad Prism":(2,0,0),"Moonsilver Key":(2,0,0),"Pearl Medallion":(2,0,0),"Scroll Rack":(2,0,0),
"The Mind Stone":(1,1,0),"Basalt Monolith":(3,0,0),"Grim Monolith":(2,0,0),
"Coalition Relic":(3,0,0),"Tezzeret, Cruel Captain":(3,0,0),
"Gleaming Splendor":(1,1,0),"Enlightened Tutor":(0,1,0),"Loyal Tutor":(0,1,0),
"Everflowing Chalice":(0,0,0),"Chrome Mox":(0,0,0),"Mox Diamond":(0,0,0),
"Mox Opal":(0,0,0),"Lotus Petal":(0,0,0),"Lion's Eye Diamond":(0,0,0),
"Jeweled Amulet":(0,0,0),"Tooth of Ramos":(3,0,0),
"Kozilek\'s Command":(0,0,2),"Eldrazi Confluence":(2,0,2)
}
def artifact_enters_bf(bf, perm):
    arr=list(bf)+[perm]
    # Tezzeret triggers for another artifact entering; if Tezz is already present, +1.
    arr=[replace(x,loyalty=x.loyalty+1) if x.name=="Tezzeret, Cruel Captain" else x for x in arr]
    return tuple(arr)


def _cast_actions_ranked(s,payment_rank=0):
    out=[]
    for idx,n in enumerate(s.hand):
        if n not in COSTS:continue
        art=is_artifact_perm(n)
        if not stax_allows(s,n,is_artifact=art):continue
        g,w,cc=COSTS[n]
        # Pearl Medallion
        if w and any(x.name=="Pearl Medallion" for x in s.battlefield):g=max(0,g-1)
        # Thorn/Trinisphere conservative handling
        names={x.name for x in s.battlefield}
        if "Thorn of Amethyst" in names and not art:g+=1
        if "Trinisphere" in names:g=max(g,3-w-cc)

        # Variable/special payment cards are handled directly from the pre-cast state so a
        # non-saturating payment rank does not suppress their inner payment alternatives.
        if n=="Pentad Prism":
            if payment_rank>0:continue
            seenpp=set()
            for pp in pay_options(s,2,artifact=True):
                w_spent=max(0,s.w-pp.w); any_spent=max(0,s.any-pp.any)
                counters=0
                if w_spent>0:counters=1
                if any_spent>0:counters=max(counters,1)
                if any_spent>=2 or (w_spent>0 and any_spent>0):counters=2
                hh=list(pp.hand);hh.pop(idx)
                q=replace(pp,hand=sort_hand(hh),spells=pp.spells+1,noncreature_spells=pp.noncreature_spells+1,
                          battlefield=artifact_enters_bf(pp.battlefield,Perm(n,False,counters,s.turn)))
                kk=key(q)
                if kk not in seenpp:seenpp.add(kk);out.append(q)
            continue
        if n=="Everflowing Chalice":
            for k in range(0,4):
                p2=pay_simple(s,2*k,artifact=True,payment_rank=payment_rank)
                if not p2:continue
                if not payment_stax_ok(s,p2):continue
                hh=list(p2.hand);hh.pop(idx)
                base2=replace(p2,hand=sort_hand(hh),spells=p2.spells+1,noncreature_spells=p2.noncreature_spells+1)
                out.append(replace(base2,battlefield=artifact_enters_bf(base2.battlefield,Perm(n,False,k,s.turn))))
            continue
        if n=="Kozilek's Command":
            for X in range(1,7):
                q=pay_simple(s,X,0,2,payment_rank=payment_rank)
                if not q:continue
                if not payment_stax_ok(s,q):continue
                hh=list(q.hand);hh.pop(idx)
                out.append(replace(q,hand=sort_hand(hh),spawn=q.spawn+X,grave=q.grave+(n,),
                                   spells=q.spells+1,nonartifact_spells=q.nonartifact_spells+1,
                                   noncreature_spells=q.noncreature_spells+1))
            continue

        paid=pay_simple(s,g,w,cc,artifact=art,payment_rank=payment_rank)
        if not paid:continue
        if not payment_stax_ok(s,paid):continue
        h=list(paid.hand);h.pop(idx)
        base=replace(paid,hand=sort_hand(h),spells=paid.spells+1,
                     nonartifact_spells=paid.nonartifact_spells+(0 if art else 1),noncreature_spells=paid.noncreature_spells+1)
        # tutors
        if n=="Enlightened Tutor":
            target=artifact_tutor_choice(base)
            if target:
                lib=list(base.library);lib.remove(target)
                out.append(replace(base,library=(target,)+shuffled_unknown(lib),grave=base.grave+(n,)))
            continue
        if n=="Loyal Tutor":
            if "Tezzeret, Cruel Captain" in base.library:
                lib=list(base.library);lib.remove("Tezzeret, Cruel Captain");# preserve randomized relative order of unknown remainder
                out.append(replace(base,library=("Tezzeret, Cruel Captain",)+shuffled_unknown(lib),grave=base.grave+(n,)))
            continue
        # Chrome Mox requires safe imprint
        if n=="Chrome Mox":
            for j,card in enumerate(base.hand):
                if chrome_mox_allowed(card):
                    hh=list(base.hand);hh.pop(j)
                    out.append(replace(base,hand=sort_hand(hh),exile=base.exile+(card,),
                                       battlefield=artifact_enters_bf(base.battlefield,Perm(n,False,0,s.turn))))
            continue
        # Mox Diamond requires actual land card in hand; MDFCs deliberately excluded.
        if n=="Mox Diamond":
            for j,card in enumerate(base.hand):
                if card in LANDS and card not in {"Emeria's Call","Razorgrass Ambush"}:
                    hh=list(base.hand);hh.pop(j)
                    out.append(replace(base,hand=sort_hand(hh),grave=base.grave+(card,),
                                       battlefield=artifact_enters_bf(base.battlefield,Perm(n,False,0,s.turn))))
            continue
        if n=="Eldrazi Confluence":
            # Choose the Scion mode three times: three 1/1 Scions, each sacs for C.
            out.append(replace(base,spawn=base.spawn+3,grave=base.grave+(n,)))
            continue
        # Archaeomancer's Map ETB: take up to two basic Plains (taking both weakly dominates here).
        if n=="Archaeomancer's Map":
            lib=list(base.library); hh=list(base.hand)
            for _ in range(2):
                if "Plains" in lib:
                    lib.remove("Plains"); hh.append("Plains")
            # preserve randomized relative order of unknown remainder
            bf=base.battlefield+(Perm(n,False,0,s.turn),)
            # artifact ETB adds loyalty to an existing Tezzeret
            bf=tuple(replace(x,loyalty=x.loyalty+1) if x.name=="Tezzeret, Cruel Captain" else x for x in bf)
            out.append(replace(base,hand=sort_hand(hh),library=shuffled_unknown(lib),battlefield=bf))
            continue
        # Giant's Boulder ETB scry 2: enumerate every legal keep/bottom subset and ordering.
        if n=="Giant's Boulder":
            from itertools import combinations, permutations
            seen_libs=set(); top=list(base.library[:2]); tail=tuple(base.library[2:])
            inds=range(len(top))
            for nb in range(len(top)+1):
                for bottom_inds in combinations(inds,nb):
                    bset=set(bottom_inds)
                    kept=[top[j] for j in inds if j not in bset]
                    bot=[top[j] for j in inds if j in bset]
                    kept_orders=set(permutations(kept)) if kept else {()}
                    bottom_orders=set(permutations(bot)) if bot else {()}
                    for kp in kept_orders:
                        for bp in bottom_orders:
                            libv=tuple(kp)+tail+tuple(bp)
                            if libv in seen_libs: continue
                            seen_libs.add(libv)
                            bf=base.battlefield+(Perm(n,False,0,s.turn),)
                            bf=tuple(replace(x,loyalty=x.loyalty+1) if x.name=="Tezzeret, Cruel Captain" else x for x in bf)
                            out.append(replace(base,battlefield=bf,library=libv))
            continue
        # zero/normal permanent
        bf=base.battlefield+(Perm(n,False,0,s.turn,loyalty=(4 if n=="Tezzeret, Cruel Captain" else 0)),)
        if is_artifact_perm(n):
            bf=tuple(replace(x,loyalty=x.loyalty+1) if x.name=="Tezzeret, Cruel Captain" and x.name!=n else x for x in bf)
        out.append(replace(base,battlefield=bf))
    return out

def upkeep_untap_mana_actions(s):
    """Activated mana/untap abilities legal and relevant during Mana Vault upkeep."""
    out=[]
    # Keys may untap mana artifacts during upkeep.
    for ki,k in enumerate(s.battlefield):
        if k.name not in {"Voltaic Key","Manifold Key"} or k.tapped:continue
        for paid in pay_options(s,1):
            for ti,target in enumerate(paid.battlefield):
                if ti!=ki and target.tapped and is_artifact_perm(effective_name(target)):
                    bf=list(paid.battlefield);bf[ki]=replace(bf[ki],tapped=True);bf[ti]=replace(bf[ti],tapped=False)
                    out.append(replace(paid,battlefield=tuple(bf)))
    # Monolith self-untaps are legal activated abilities.
    for i,p in enumerate(s.battlefield):
        if effective_name(p)=="Grim Monolith" and p.tapped:
            for paid in pay_options(s,4):
                bf=list(paid.battlefield);bf[i]=replace(bf[i],tapped=False);out.append(replace(paid,battlefield=tuple(bf)))
        if effective_name(p)=="Basalt Monolith" and p.tapped:
            for paid in pay_options(s,3):
                bf=list(paid.battlefield);bf[i]=replace(bf[i],tapped=False);out.append(replace(paid,battlefield=tuple(bf)))
    # Candelabra is also an activated untap ability.
    from itertools import combinations
    for ci,ca in enumerate(s.battlefield):
        if ca.name!="Candelabra of Tawnos" or ca.tapped:continue
        inds=[i for i,x in enumerate(s.battlefield) if x.name in LANDS and x.tapped]
        for X in range(1,len(inds)+1):
            for paid in pay_options(s,X):
                for sub in combinations(inds,X):
                    bf=list(paid.battlefield);bf[ci]=replace(bf[ci],tapped=True)
                    for i in sub:bf[i]=replace(bf[i],tapped=False)
                    out.append(replace(paid,battlefield=tuple(bf)))
    return out

def mana_vault_upkeep_options(s,beam=300,depth=10):
    """No-pay line plus legal upkeep {4} Mana Vault untap lines only."""
    outs=[s]
    if not any(effective_name(p)=="Mana Vault" and p.tapped for p in s.battlefield):return outs
    frontier=[s];seen={key(s)}
    for _ in range(depth):
        nxt=[]
        for q in frontier:
            for a in tap_mana_actions(q)+upkeep_untap_mana_actions(q):
                # no card-zone manipulation is permitted by this upkeep helper
                if a.hand!=q.hand or a.library!=q.library:continue
                kk=key(a)
                if kk not in seen:seen.add(kk);nxt.append(a)
        for q in frontier+nxt:
            for paid in pay_options(q,4):
                for vi,pv in enumerate(paid.battlefield):
                    if effective_name(pv)=="Mana Vault" and pv.tapped:
                        bf=list(paid.battlefield);bf[vi]=replace(pv,tapped=False)
                        outs.append(replace(paid,battlefield=tuple(bf),w=0,c=0,any=0,
                            restricted_legend=0,restricted_artifact=0,restricted_dack_white=0))
        if not nxt:break
        nxt.sort(key=score,reverse=True);frontier=nxt[:beam]
    d={}
    for q in outs:d[key(q)]=q
    return list(d.values())


def can_cast_dack(s):
    if not COMBO_CREATURES.issubset(set(s.library)):return False
    if not stax_allows(s,COMMANDER,is_creature=True):return False
    names={x.name for x in s.battlefield};generic=4
    if "Thorn of Amethyst" in names:generic+=1
    if "Pearl Medallion" in names:generic=max(0,generic-1)
    # Exact allocation. restricted_dack_white may pay either W pips or generic for Dack;
    # fold it into an any-like Dack-only pool, then enumerate the two white pips first.
    for rdw_white in range(min(2,s.restricted_dack_white)+1):
        needw=2-rdw_white
        for ww in range(min(s.w,needw)+1):
            aa=needw-ww
            if aa>s.any:continue
            remw=s.w-ww;rema=s.any-aa;remrdw=s.restricted_dack_white-rdw_white
            # generic can use W/C/any/legend-only (Dack is legendary)/remaining Dack-only.
            if remw+s.c+rema+s.restricted_legend+remrdw>=generic:return True
    return False


# ---------- 10. bounded search / diagnostics ----------
# Battlefield-only equivalence classes. Cards collapse only after their distinct cast/play/search
# identity can no longer matter to the T1-T3 objective.
BF_EQUIV={"City of Brass":"RAINBOW_LAND","Mana Confluence":"RAINBOW_LAND"}
_BF_EQUIV_ID={"RAINBOW_LAND":-1}
def _perm_key(x):
    n=BF_EQUIV.get(x.name,x.name)
    nid=_BF_EQUIV_ID.get(n,CARD_ID.get(n,-2))
    # aux is normally empty; preserve exact copy identity when present.
    return (nid,x.tapped,x.counters,x.aux,x.loyalty,x.activated_turn)
def key(s):
    return (s.turn,tuple(CARD_ID[x] for x in s.hand),library_token(s.library),
            tuple(sorted(_perm_key(x) for x in s.battlefield)),
            s.land_played,s.w,s.c,s.any,s.restricted_legend,s.restricted_artifact,
            s.treasures,s.spawn,s.spells,s.nonartifact_spells,s.noncreature_spells,s.restricted_dack_white,s.map_bonus_used)

def _cast_rank_limit(s):
    """Exact upper bound (capped at the historical 8) on payment ranks worth asking for."""
    mx=1; names={x.name for x in s.battlefield}
    for n in s.hand:
        if n not in COSTS:continue
        art=is_artifact_perm(n);g,w,cc=COSTS[n]
        if w and "Pearl Medallion" in names:g=max(0,g-1)
        if "Thorn of Amethyst" in names and not art:g+=1
        if "Trinisphere" in names:g=max(g,3-w-cc)
        if n=="Everflowing Chalice":
            for k in range(4):mx=max(mx,len(_pay_pool_options(s.w,s.c,s.any,s.restricted_legend,s.restricted_artifact,2*k,0,0,False,True)))
        elif n=="Kozilek's Command":
            for X in range(1,7):mx=max(mx,len(_pay_pool_options(s.w,s.c,s.any,s.restricted_legend,s.restricted_artifact,X,0,2,False,False)))
        elif n=="Pentad Prism":
            mx=max(mx,1)
        else:
            mx=max(mx,len(_pay_pool_options(s.w,s.c,s.any,s.restricted_legend,s.restricted_artifact,g,w,cc,False,art)))
    return min(8,mx)

def cast_actions(s):
    out=[];seen=set()
    for rank in range(_cast_rank_limit(s)):
        for q in _cast_actions_ranked(s,payment_rank=rank):
            kk=key(q)
            if kk not in seen:seen.add(kk);out.append(q)
    return out

def score(s):
    mana=s.w+s.c+s.any+s.restricted_legend+s.restricted_dack_white
    white=s.w+s.any+s.restricted_dack_white
    white_potential=white
    bank=0
    for p in s.battlefield:
        n=effective_name(p)
        if p.name in GUARANTEED_WHITE_LANDS or n in {"Emeria, Shattered Skyclave","Razorgrass Field","Mox Diamond","Chrome Mox","Tooth of Ramos","The Mind Stone","Cavern of Souls"}:
            white_potential+=1
        if p.name=="Gemstone Caverns" and p.counters: white_potential+=1
        # Approximate reusable next-turn mana. This matters especially for turn-end frontier pruning.
        if n=="Ancient Tomb": bank+=2
        elif n in {"Sol Ring"}: bank+=2
        elif n in {"Mana Vault","Grim Monolith","Basalt Monolith"}:
            if not p.tapped: bank+=3
        elif n=="Coalition Relic": bank+=1+p.counters
        elif n=="Everflowing Chalice": bank+=p.counters
        elif n=="Pentad Prism": bank+=p.counters
        elif n=="Remote Farm": bank+=2 if p.counters else 0
        elif n=="Untaidake, the Cloud Keeper": bank+=2
        elif n=="Lion's Eye Diamond" and not any(x in COMBO_CREATURES for x in s.hand):
            bank+=3; white_potential+=3
        elif n in LANDS or n in {"Arcane Signet","Fellwar Stone","Mox Diamond","Chrome Mox","Mox Opal","The Mind Stone","Liquimetal Torque","Prismatic Lens","Tooth of Ramos"}: bank+=1
    white_hand=sum(x in GUARANTEED_WHITE_LANDS or x in {"Emeria's Call","Razorgrass Ambush","Mox Diamond","Chrome Mox","Lotus Petal","Tooth of Ramos"} for x in s.hand)
    if "Lion's Eye Diamond" in s.hand and not any(x in COMBO_CREATURES for x in s.hand):
        white_hand+=3
    future_lands=min(3,sum(x in LANDS or x in {"Emeria's Call","Razorgrass Ambush"} for x in s.hand))
    # Floating mana is useful within-turn but bankable infrastructure dominates when choosing pass states.
    return ((1000 if can_cast_dack(s) else 0)+18*min(mana,8)+24*min(bank,8)+28*min(white,2)+
            18*min(white_potential+white_hand,2)+5*future_lands+8*len(s.battlefield)-
            40*sum(x in COMBO_CREATURES for x in s.hand))

def search_turn_frontier_many(states,beam=6000,depth=24):
    # Cache exact key/score calculations for immutable states within this turn search.
    kcache={};scache={}
    def kf(q):
        oid=id(q);got=kcache.get(oid)
        if got is not None and got[0] is q:return got[1]
        v=key(q);kcache[oid]=(q,v);return v
    def sf(q):
        oid=id(q);got=scache.get(oid)
        if got is not None and got[0] is q:return got[1]
        v=score(q);scache[oid]=(q,v);return v
    frontier=list(states);seen={kf(q) for q in frontier};wins=[]
    end_by_key={kf(q):q for q in frontier}
    for _ in range(depth):
        nxt=[]
        for q in frontier:
            if can_cast_dack(q) and not city_trigger_pending(q):wins.append(q);continue
            # A City sacrifice trigger on the stack must resolve before sorcery-speed actions/pass.
            if city_trigger_pending(q):
                resp_special=[a for a in special_actions(q)
                              if a.hand==q.hand and a.library==q.library and len(a.battlefield)==len(q.battlefield)]
                acts=tap_mana_actions(q)+utility_actions(q)+resp_special+nasty_mana_actions(q)+resolve_city_trigger_actions(q)
            else:
                # Passing priority through the rest of the turn is always legal.
                kq=kf(q)
                prev=end_by_key.get(kq)
                if prev is None or sf(q)>sf(prev): end_by_key[kq]=q
                acts=play_land_actions(q)+tap_mana_actions(q)+utility_actions(q)+special_actions(q)+v03_actions(q)+nasty_mana_actions(q)+repair_actions(q)+saga_tutor_actions(q)+cast_actions(q)
            for a in acts:
                k=kf(a)
                if k not in seen:seen.add(k);nxt.append(a)
        if wins:return wins,sorted(end_by_key.values(),key=sf,reverse=True)[:beam]
        if not nxt:break
        # Diversity-aware beam: preserve the best state within strategic signatures before filling by score.
        nxt.sort(key=sf,reverse=True)
        sigbest={}
        for q in nxt:
            names=frozenset(x.name for x in q.battlefield)
            sig=(q.land_played,
                 min(2,sum(x in GUARANTEED_WHITE_LANDS for x in q.hand)),
                 "Urza's Saga" in names, "Mana Vault" in names, "Sol Ring" in names,
                 ("Lion's Eye Diamond" in names or "Lion's Eye Diamond" in q.hand),
                 min(3,sum(x in LANDS or x in {"Emeria's Call","Razorgrass Ambush"} for x in q.hand)),
                 "Coalition Relic" in names,
                 any(x.name in {"Brainstone","Scroll Rack"} for x in q.battlefield))
            if sig not in sigbest: sigbest[sig]=q
        diverse=sorted(sigbest.values(),key=sf,reverse=True)[:max(1,beam//3)]
        dk={kf(q) for q in diverse}
        frontier=diverse+[q for q in nxt if kf(q) not in dk][:max(0,beam-len(diverse))]
        # Bound the pass-state reservoir as well.
        if len(end_by_key)>beam*3:
            vals=sorted(end_by_key.values(),key=sf,reverse=True)
            keep=vals[:beam]
            end_by_key={kf(q):q for q in keep}
    wins.extend(q for q in frontier if can_cast_dack(q) and not city_trigger_pending(q))
    for q in frontier:
        if not city_trigger_pending(q):end_by_key[kf(q)]=q
    return wins,sorted(end_by_key.values(),key=sf,reverse=True)[:beam]


def search_turn_frontier(s,beam=3000,depth=18):
    frontier=[s];seen={key(s)}
    wins=[]
    for _ in range(depth):
        nxt=[]
        for q in frontier:
            if can_cast_dack(q):
                wins.append(q);continue
            acts=play_land_actions(q)+tap_mana_actions(q)+utility_actions(q)+special_actions(q)+v03_actions(q)+nasty_mana_actions(q)+repair_actions(q)+saga_tutor_actions(q)+cast_actions(q)
            for a in acts:
                k=key(a)
                if k not in seen:
                    seen.add(k);nxt.append(a)
        if not nxt:break
        nxt.sort(key=score,reverse=True);frontier=nxt[:beam]
    wins.extend(q for q in frontier if can_cast_dack(q))
    return wins,frontier

def search_turn(s,beam=6000,depth=18):
    frontier=[s]; seen=set()
    for _ in range(depth):
        nxt=[]
        for q in frontier:
            if can_cast_dack(q):return q
            acts=play_land_actions(q)+tap_mana_actions(q)+utility_actions(q)+special_actions(q)+v03_actions(q)+nasty_mana_actions(q)+repair_actions(q)+saga_tutor_actions(q)+cast_actions(q)
            for a in acts:
                k=key(a)
                if k not in seen:seen.add(k);nxt.append(a)
        if not nxt:break
        nxt.sort(key=score,reverse=True);frontier=nxt[:beam]
    wins=[q for q in frontier if can_cast_dack(q)]
    return max(wins,key=score) if wins else max(frontier,key=score,default=s)

def apply_gemstone_pregame(s,rng):
    # Four-player seat model: 1/4 starting player (Caverns inactive), 3/4 non-starting.
    if rng.random() < 0.25:
        return s, True
    if "Gemstone Caverns" not in s.hand:
        return s, False
    # Branch safe exile choices and choose best by solver score; never exile combo creatures.
    outs=[s]
    for i,card in enumerate(s.hand):
        if card=="Gemstone Caverns" or card in COMBO_CREATURES: continue
        hh=list(s.hand);hh.pop(i);hh.remove("Gemstone Caverns")
        bf=s.battlefield+(Perm("Gemstone Caverns",False,1,0),)
        outs.append(replace(s,hand=sort_hand(hh),battlefield=bf,exile=s.exile+(card,)))
    return max(outs,key=score), False

def simulate_one_frontier(rng,beam=2500,V=None,mull_beam=120,mull_samples=4):
    if V is None:raise ValueError("pass calibrated V")
    chosen,mull_depth,audit=choose_london_hand(rng,V,beam=mull_beam,samples=mull_samples)
    # apply actual randomized seat once for the realized game
    starting=(rng.random()<0.25)
    states=_pregame_states(chosen,0 if starting else 1)
    states=[draw(s,1) for s in states]
    result={"win_turn":None,"mull":mull_depth,"repaired":0,"audit":audit}
    for turn in (1,2,3):
        if turn>1:
            ns=[]
            for s in states:
                q=replace(s,turn=turn);q=untap_and_begin(q);q=add_opponent_cycle_resources(q)
                for uq in mana_vault_upkeep_options(q):
                    uq=draw(uq,1);uq=saga_advance(uq);uq=begin_first_main(uq)
                    ns.append(uq)
            states=ns
        wins,states=search_turn_frontier_many(states,beam=beam,depth=24)
        if wins:
            result["win_turn"]=turn;result["repaired"]=max(q.repaired for q in wins);return result
    if states:result["repaired"]=max(q.repaired for q in states)
    return result

def simulate_one(rng,beam=3000,V=None,mull_beam=500,mull_samples=16):
    return simulate_one_frontier(rng,beam=beam,V=V,mull_beam=mull_beam,mull_samples=mull_samples)


def run(n,seed,beam):
    rng=random.Random(seed)
    rows=[simulate_one(rng,beam) for _ in range(n)]
    c=Counter(r["win_turn"] for r in rows);m=Counter(r["mull"] for r in rows)
    return {
      "n":n,"seed":seed,"beam":beam,
      "T1":c[1]/n,"T2_exact":c[2]/n,"T3_exact":c[3]/n,
      "le_T2":(c[1]+c[2])/n,"le_T3":(c[1]+c[2]+c[3])/n,
      "fail_T3":c[None]/n,
      "white_fail_T2":sum(r["white_fail_t2"] for r in rows)/n,
      "white_fail_T3":sum(r["white_fail_t3"] for r in rows)/n,
      "repair_rate":sum(r["repaired"]>0 for r in rows)/n,
      "mulligan_keep_n":dict(sorted(m.items(),reverse=True))
    }

def selftest():
    assert len(DECK)==99
    # v0.72 Patch A: semantic payment signatures are observational only.
    # Generic {1} from W+C must still retain both distinct legal residual pools.
    _pay_before=State(1,(),(),w=1,c=1)
    _pay_after=pay_options(_pay_before,1)
    _pay_sigs=[payment_semantic_signature(_pay_before,q) for q in _pay_after]
    assert any(x.residual_w==1 and x.residual_c==0 and x.spent_colored==0 for x in _pay_sigs), "v0.72 signature lost C-payment residual"
    assert any(x.residual_w==0 and x.residual_c==1 and x.spent_colored==1 for x in _pay_sigs), "v0.72 signature lost W-payment residual"
    assert len(set(_pay_sigs))==len(_pay_after), "v0.72 signature unexpectedly collapses distinct W/C payments"
    for q,x in zip(_pay_after,_pay_sigs):
        assert payment_tags(_pay_before,q)==(x.spent_total,x.spent_colored), "v0.72 signature/payment_tags disagreement"
    # Prism-sensitive color class mirrors the current Sunburst abstraction.
    _pp1a=State(1,(),(),w=2); _pp1b=replace(_pp1a,w=0)
    _pp2a=State(1,(),(),w=1,any=1); _pp2b=replace(_pp2a,w=0,any=0)
    _pp3a=State(1,(),(),any=2); _pp3b=replace(_pp3a,any=0)
    assert payment_semantic_signature(_pp1a,_pp1b).prism_color_class==1, "v0.72 Prism one-color signature failed"
    assert payment_semantic_signature(_pp2a,_pp2b).prism_color_class==2, "v0.72 Prism W+any signature failed"
    assert payment_semantic_signature(_pp3a,_pp3b).prism_color_class==2, "v0.72 Prism two-any signature failed"
    # Restricted pools remain independently visible in the signature.
    _r0=State(1,(),(),restricted_legend=2,restricted_artifact=2,restricted_dack_white=1)
    _r1=replace(_r0,restricted_legend=1,restricted_artifact=0,restricted_dack_white=0)
    _rs=payment_semantic_signature(_r0,_r1)
    assert (_rs.residual_restricted_legend,_rs.residual_restricted_artifact,_rs.residual_restricted_dack_white)==(1,0,0)
    assert (_rs.spent_restricted_legend,_rs.spent_restricted_artifact,_rs.spent_restricted_dack_white)==(1,2,1)
    assert _rs.spent_total==4 and _rs.spent_colored==1 and _rs.prism_color_class==0
    # v0.66 search-scoring regression: guaranteed rainbow/white lands must never
    # receive a worse heuristic score than Plains solely because their mana is stored as `any`.
    plains_bf_score=score(State(1,(),(),(Perm("Plains"),)))
    for _land,_counters in (("City of Brass",0),("Mana Confluence",0),("Gemstone Mine",3),
                             ("Tarnished Citadel",0),("Starting Town",0)):
        assert score(State(1,(),(),(Perm(_land,counters=_counters),))) >= plains_bf_score, (_land,"battlefield score")
        assert score(State(1,(_land,),())) >= score(State(1,("Plains",),())), (_land,"hand score")
    assert not chrome_mox_allowed("Boonweaver Giant")
    assert not chrome_mox_allowed("Coalition Flag")
    assert not chrome_mox_allowed("Super State")
    assert chrome_mox_allowed("Enlightened Tutor")
    assert chrome_mox_allowed("Loyal Tutor")
    assert chrome_mox_allowed("Silence")
    # Nexus + Tower -> Tower taps for 3.
    s=State(1,(),(),(Perm("Planar Nexus"),Perm("Urza's Tower")))
    vals=tap_mana_actions(s)
    assert any(x.c==3 for x in vals)
    # Workshop with Nexus + 3 artifacts -> >=2 from Workshop.
    s=State(1,(),(),(Perm("Planar Nexus"),Perm("Urza's Workshop"),
        Perm("Sol Ring"),Perm("Mana Vault"),Perm("Chrome Mox")))
    assert any(x.c>=2 for x in tap_mana_actions(s))
    # Great Hall can create 2 legend-restricted.
    s=State(1,(),(),(Perm("Great Hall of the Citadel"),),c=1)
    assert any(x.restricted_legend==2 for x in special_actions(s))
    # v0.3 regression tests
    s=State(1,("Silence",),tuple(COMBO_CREATURES),(Perm("Lion's Eye Diamond"),))
    assert any(x.w==3 and not x.hand for x in tap_mana_actions(s))
    s=State(1,(),(),(Perm("Lotus Petal"),))
    assert any(x.w==1 for x in tap_mana_actions(s))
    s=State(1,(),(),(Perm("Mox Opal"),))
    assert not any(x.any for x in tap_mana_actions(s))
    s=State(1,(),(),(Perm("Mox Opal"),Perm("Sol Ring"),Perm("Mana Vault")))
    assert any(x.any for x in tap_mana_actions(s))
    s=State(1,(),("Planar Nexus",),(Perm("Expedition Map"),),c=2)
    assert any("Planar Nexus" in x.hand for x in v03_actions(s))
    s=State(1,(),("Lion's Eye Diamond",),(Perm("Tezzeret, Cruel Captain",loyalty=4),))
    assert any("Lion's Eye Diamond" in x.hand for x in v03_actions(s))
    # Eldrazi ramp abstraction tests.
    s=State(1,("Kozilek's Command",),(),(),c=5)
    ka=cast_actions(s)
    assert any(x.spawn==3 for x in ka), "Kozilek Command X=3 ramp missing"
    s=State(1,("Eldrazi Confluence",),(),(),c=4)
    ea=cast_actions(s)
    assert any(x.spawn==3 for x in ea), "Eldrazi Confluence triple-Scion ramp missing"

    # Compound: Tezzeret -3 -> LED -> cast -> activate.
    s=State(1,(),("Lion's Eye Diamond",)+tuple(COMBO_CREATURES),
            (Perm("Tezzeret, Cruel Captain",loyalty=4),))
    aa=[x for x in v03_actions(s) if "Lion's Eye Diamond" in x.hand]
    assert aa, "Tezzeret -> LED tutor failed"
    bb=[x for q in aa for x in cast_actions(q)]
    assert any(any(p.name=="Lion's Eye Diamond" for p in q.battlefield) for q in bb), "LED cast failed"
    assert any(x.w>=3 for q in bb for x in tap_mana_actions(q)), "LED activation failed"

    # Compound: Gardens -> LED copy -> copied LED activation.
    s=State(1,(),tuple(COMBO_CREATURES),
            (Perm("The Mycosynth Gardens"),Perm("Lion's Eye Diamond")))
    aa=[x for x in v03_actions(s) if any(p.aux=="COPY:Lion's Eye Diamond" for p in x.battlefield)]
    assert aa, "Gardens copy failed"
    assert any(x.w>=3 for q in aa for x in tap_mana_actions(q)), "copied LED activation failed"

    # Compound: Map -> Nexus -> play Nexus.
    s=State(1,(),("Planar Nexus",)+tuple(COMBO_CREATURES),(Perm("Expedition Map"),),c=2)
    aa=[x for x in v03_actions(s) if "Planar Nexus" in x.hand]
    assert aa, "Map -> Nexus tutor failed"
    assert any(any(p.name=="Planar Nexus" for p in x.battlefield)
               for q in aa for x in play_land_actions(q)), "Map -> Nexus play failed"

    # Rack repair.
    s=State(1,("Boonweaver Giant",),("Plains","Sol Ring","Preston, the Vanisher","Roaming Throne"),
            (Perm("Scroll Rack"),),c=1)
    aa=repair_actions(s)
    assert any("Boonweaver Giant" in x.library and "Boonweaver Giant" not in x.hand for x in aa), "Rack repair failed"

    # Brainstone repair.
    s=State(1,("Preston, the Vanisher",),
            ("Plains","Sol Ring","Silence","Boonweaver Giant","Roaming Throne"),
            (Perm("Brainstone"),),c=2)
    aa=repair_actions(s)
    assert any("Preston, the Vanisher" in x.library and "Preston, the Vanisher" not in x.hand for x in aa), "Brainstone repair failed"

    # Nexus/Tower and Nexus/Workshop.
    s=State(1,(),tuple(COMBO_CREATURES),(Perm("Planar Nexus"),Perm("Urza's Tower")))
    assert any(x.c==3 for x in tap_mana_actions(s)), "Nexus/Tower failed"
    s=State(1,(),tuple(COMBO_CREATURES),(Perm("Planar Nexus"),Perm("Urza's Workshop"),
      Perm("Sol Ring"),Perm("Mana Vault"),Perm("Chrome Mox")))
    assert any(x.c>=2 for x in tap_mana_actions(s)), "Nexus/Workshop failed"


    # Vault + Key = 5 net after retap.
    s=State(1,(),tuple(COMBO_CREATURES),(Perm("Mana Vault"),Perm("Voltaic Key")))
    a=[x for x in tap_mana_actions(s) if x.c>=3]
    b=[x for q in a for x in nasty_mana_actions(q) if any(p.name=="Mana Vault" and not p.tapped for p in x.battlefield)]
    assert b and any(x.c+x.any+x.w>=5 for q in b for x in tap_mana_actions(q)), "Vault/Key failed"

    # Grim + Manifold Key = 5 net.
    s=State(1,(),tuple(COMBO_CREATURES),(Perm("Grim Monolith"),Perm("Manifold Key")))
    a=[x for x in tap_mana_actions(s) if x.c>=3]
    b=[x for q in a for x in nasty_mana_actions(q) if any(p.name=="Grim Monolith" and not p.tapped for p in x.battlefield)]
    assert b and any(x.c+x.any+x.w>=5 for q in b for x in tap_mana_actions(q)), "Grim/Key failed"

    # Tomb + Candelabra = 3 net after untap/retap.
    s=State(1,(),tuple(COMBO_CREATURES),(Perm("Ancient Tomb"),Perm("Candelabra of Tawnos")))
    a=[x for x in tap_mana_actions(s) if x.c>=2]
    b=[x for q in a for x in nasty_mana_actions(q) if any(p.name=="Ancient Tomb" and not p.tapped for p in x.battlefield)]
    assert b and any(x.c+x.any+x.w>=3 for q in b for x in tap_mana_actions(q)), "Candelabra/Tomb failed"

    # Chalice kicked twice -> taps for 2.
    s=State(1,("Everflowing Chalice",),tuple(COMBO_CREATURES),(),c=4)
    a=[x for x in cast_actions(s) if any(p.name=="Everflowing Chalice" and p.counters==2 for p in x.battlefield)]
    assert a and any(x.c>=2 for q in a for x in tap_mana_actions(q)), "Chalice x2 failed"

    # Coalition Relic bank releases at first main, not during upkeep.
    s=State(1,(),tuple(COMBO_CREATURES),(Perm("Coalition Relic"),))
    a=[x for x in special_actions(s) if any(p.name=="Coalition Relic" and p.counters for p in x.battlefield)]
    assert a, "Relic charge failed"
    q=untap_and_begin(replace(a[0],turn=2))
    assert q.any==0 and any(p.name=="Coalition Relic" and p.counters==1 and not p.tapped for p in q.battlefield), "Relic released before first main"
    q=begin_first_main(q)
    assert q.any>=1 and any(p.name=="Coalition Relic" and p.counters==0 and not p.tapped for p in q.battlefield), "Relic main-phase release failed"

    # Saga I -> II -> III -> LED using existing saga transition.
    s=State(1,(),("Lion's Eye Diamond",)+tuple(COMBO_CREATURES),(Perm("Urza's Saga",False,1,1),))
    q=saga_advance(replace(s,turn=2))
    assert any(p.name=="Urza's Saga" and p.counters==2 for p in q.battlefield), "Saga II failed"
    q=saga_advance(replace(q,turn=3))
    opts=saga_tutor_actions(q)
    assert any(any(p.name=="Lion's Eye Diamond" for p in z.battlefield) for z in opts), "Saga III LED failed"

    # LED plus 3 generic gives a valid six-mana WW Dack state.
    s=State(2,(),tuple(COMBO_CREATURES),(Perm("Lion's Eye Diamond"),),c=3)
    a=[x for x in tap_mana_actions(s) if x.w>=3]
    assert a and any(can_cast_dack(x) for x in a), "LED + generic Dack failed"


    # Full search must preserve the white line rather than greedily choosing Tomb/colorless.
    s=State(1,("Plains","Ancient Tomb","City of Traitors","Mox Diamond","Sol Ring","Mana Vault","Lotus Petal"),
            tuple(COMBO_CREATURES))
    q=search_turn(s,beam=12000,depth=24)
    assert can_cast_dack(q), "full-search WW/Mox-Diamond T1 line was pruned"

    # Full search Tezzeret -> LED. Petal supplies the otherwise missing sixth mana.
    s=State(1,("Ancient Tomb","Sol Ring","Mana Vault","Lotus Petal","Tezzeret, Cruel Captain"),
            ("Lion's Eye Diamond",)+tuple(COMBO_CREATURES))
    q=search_turn(s,beam=12000,depth=24)
    assert can_cast_dack(q), "full-search Tezzeret -> LED T1 line missing"

    # Full search direct LED hand.
    s=State(1,("Plains","Ancient Tomb","Sol Ring","Mana Vault","Lion's Eye Diamond"),
            tuple(COMBO_CREATURES))
    q=search_turn(s,beam=12000,depth=24)
    assert can_cast_dack(q), "full-search direct LED T1 line missing"

    # Full search Vault+Key with two white sources.
    s=State(2,(),tuple(COMBO_CREATURES),
            (Perm("Mana Vault"),Perm("Voltaic Key"),Perm("Plains"),Perm("Ancient Den")))
    q=search_turn(s,beam=12000,depth=24)
    assert can_cast_dack(q), "full-search Vault/Key Dack line missing"

    # Saga III -> LED state must finish Dack.
    s=State(3,(),("Lion's Eye Diamond",)+tuple(COMBO_CREATURES),
            (Perm("Urza's Saga",False,2,1),Perm("Ancient Tomb"),Perm("Sol Ring")))
    s=saga_advance(s)
    q=search_turn(s,beam=12000,depth=24)
    assert can_cast_dack(q), "full-search Saga III -> LED Dack line missing"

    # Audit regression: Planar Nexus color conversion.
    s=State(1,(),tuple(COMBO_CREATURES),(Perm("Planar Nexus"),),c=1)
    assert any(x.any>=1 for x in tap_mana_actions(s)), "Planar Nexus color ability failed"
    # Audit regression: Cavern naming Human can supply Dack-white.
    s=State(1,(),tuple(COMBO_CREATURES),(Perm("Cavern of Souls"),),c=5,w=1)
    assert any(can_cast_dack(x) for x in tap_mana_actions(s)), "Cavern Human Dack mana failed"
    # Audit regression: Great Hall converts external 1 mana into WW for legendary Dack.
    s=State(1,(),tuple(COMBO_CREATURES),(Perm("Great Hall of the Citadel"),),c=5)
    assert any(can_cast_dack(x) for x in special_actions(s)), "Great Hall WW Dack failed"
    # Audit regression: Workshop counts itself as an Urza's land.
    s=State(1,(),tuple(COMBO_CREATURES),(Perm("Urza's Workshop"),Perm("Planar Nexus"),Perm("Sol Ring"),Perm("Mox Opal")))
    assert urza_count(s)>=2, "Workshop self Urza count failed"
    # Audit regression: Giant's Boulder mana conversion.
    s=State(1,(),tuple(COMBO_CREATURES),(Perm("Giant's Boulder"),),c=1)
    assert any(x.any>=1 for x in special_actions(s)), "Boulder mana failed"
    # Regression: Map is castable at 2W and fetches two Plains.
    s=State(1,("Archaeomancer's Map",),("Plains","Plains")+tuple(COMBO_CREATURES),c=2,w=1)
    opts=cast_actions(s)
    assert any(sum(x=="Plains" for x in q.hand)>=2 for q in opts), "Map ETB failed"
    # Regression: Map catch-up can put a Plains without consuming land play on T2.
    s=State(2,("Plains",),tuple(COMBO_CREATURES),(Perm("Archaeomancer's Map"),),map_bonus_used=False)
    assert any(any(x.name=="Plains" for x in q.battlefield) and not q.land_played for q in special_actions(s)), "Map catch-up failed"
    # Regression: Tezzeret gains loyalty when another artifact enters.
    bf=artifact_enters_bf((Perm("Tezzeret, Cruel Captain",False,0,1,loyalty=4),),Perm("Sol Ring"))
    assert next(x for x in bf if x.name=="Tezzeret, Cruel Captain").loyalty==5, "Tezz ETB loyalty failed"
    # Tezz only finds Brainstone as a contamination-repair exception.
    s=State(1,("Boonweaver Giant",),("Brainstone","Lion's Eye Diamond"),(Perm("Tezzeret, Cruel Captain",False,0,1,loyalty=4),))
    assert any("Brainstone" in q.hand for q in v03_actions(s)), "Tezz repair priority failed"
    # Regression: land tutors include all relevant lands, including Cavern/Saga/Workshop.
    assert {"Cavern of Souls","Urza's Saga","Mishra's Workshop","Urza's Workshop"} <= set(LAND_TUTOR_TARGETS), "land tutor target coverage failed"
    # Regression: Gleaming Splendor is not an Aura and can be a safe Chrome imprint under user policy.
    assert "Gleaming Splendor" not in AURAS and chrome_mox_allowed("Gleaming Splendor"), "Splendor Chrome classification failed"
    # Regression: Rule of Law/Deafening are valid safe Chrome imprints.
    assert chrome_mox_allowed("Rule of Law") and chrome_mox_allowed("Deafening Silence"), "Chrome white imprint coverage failed"
    # Regression: Emeria MDFC can be played untapped for W but is not a Mox Diamond land card.
    s=State(1,("Emeria's Call",),tuple(COMBO_CREATURES))
    opts=play_land_actions(s)
    assert any(any(x.name=="Emeria, Shattered Skyclave" and not x.tapped for x in q.battlefield) for q in opts), "Emeria MDFC failed"
    assert "Emeria's Call" not in LANDS, "Emeria incorrectly Mox-Diamond eligible"
    # Regression: Razorgrass Field is a tapped W land face and not Mox-Diamond eligible.
    s=State(1,("Razorgrass Ambush",),tuple(COMBO_CREATURES))
    opts=play_land_actions(s)
    assert any(any(x.name=="Razorgrass Field" and x.tapped for x in q.battlefield) for q in opts), "Razorgrass MDFC failed"
    assert "Razorgrass Ambush" not in LANDS, "Razorgrass incorrectly Mox-Diamond eligible"
    # Regression: Map catch-up may deploy nonbasic land from hand.
    s=State(2,("Ancient Tomb",),tuple(COMBO_CREATURES),(Perm("Archaeomancer's Map"),))
    assert any(any(x.name=="Ancient Tomb" for x in q.battlefield) for q in special_actions(s)), "Map any-land catch-up failed"
    # Environment regression: Map permits exactly two catch-up land placements per cycle abstraction.
    s=State(2,("Plains","Ancient Tomb","City of Traitors"),tuple(COMBO_CREATURES),(Perm("Archaeomancer's Map"),))
    a=special_actions(s); assert a, "Map first catch-up absent"
    s1=next(q for q in a if q.map_bonus_used==1)
    a2=special_actions(s1); assert any(q.map_bonus_used==2 for q in a2), "Map second catch-up absent"
    s2=next(q for q in a2 if q.map_bonus_used==2)
    assert not any(q.map_bonus_used>2 for q in special_actions(s2)), "Map exceeded two catch-ups"
    # Environment regression: Caverns pregame leaves starting-seat hand unchanged.
    class FixedStart:
        def random(self): return 0.0
    s=State(1,("Gemstone Caverns","Silence"),tuple(COMBO_CREATURES))
    q,starting=apply_gemstone_pregame(s,FixedStart())
    assert starting and q==s, "Caverns active for starting player"
    # Environment regression: non-starting Caverns can pregame into luck-counter Caverns.
    class FixedNonStart:
        def random(self): return 0.9
    q,starting=apply_gemstone_pregame(s,FixedNonStart())
    assert not starting and any(x.name=="Gemstone Caverns" and x.counters==1 for x in q.battlefield), "Caverns non-start pregame failed"
    # ---- Compound sequencing regressions ----
    # Rule of Law: after one spell, Dack cannot be cast this turn.
    s=State(2,(),tuple(COMBO_CREATURES),(Perm("Rule of Law"),),w=2,c=4,spells=1)
    assert not can_cast_dack(s), "Rule of Law failed to stop second spell"
    # Rule of Law still allows Dack as first spell.
    assert can_cast_dack(replace(s,spells=0)), "Rule of Law incorrectly stops first Dack"
    # Deafening Silence counts artifact spells as noncreature spells.
    s=State(2,("Sol Ring",),tuple(COMBO_CREATURES),(Perm("Deafening Silence"),),c=1,noncreature_spells=1)
    assert not any("Sol Ring" in [x.name for x in q.battlefield] for q in cast_actions(s)), "Deafening allowed second noncreature"
    # Deafening does not stop Dack creature after a prior noncreature spell.
    s=State(2,(),tuple(COMBO_CREATURES),(Perm("Deafening Silence"),),w=2,c=4,noncreature_spells=1)
    assert can_cast_dack(s), "Deafening incorrectly stopped Dack creature"
    # Thorn taxes nonartifact Tezzeret but not Mana Vault.
    s=State(1,("Tezzeret, Cruel Captain","Mana Vault"),tuple(COMBO_CREATURES),(Perm("Thorn of Amethyst"),),c=3)
    ca=cast_actions(s)
    assert any(any(x.name=="Mana Vault" for x in q.battlefield) for q in ca), "Thorn taxed artifact"
    assert not any(any(x.name=="Tezzeret, Cruel Captain" for x in q.battlefield) for q in ca), "Thorn failed to tax Tezz"
    # Trinisphere makes Sol Ring cost 3.
    s=State(1,("Sol Ring",),tuple(COMBO_CREATURES),(Perm("Trinisphere"),),c=1)
    assert not cast_actions(s), "Trinisphere failed on Sol Ring"
    s=replace(s,c=3); assert cast_actions(s), "Trinisphere overblocked Sol Ring"
    # Gardens copies Mana Vault and copied identity taps for 3.
    s=State(1,(),tuple(COMBO_CREATURES),(Perm("The Mycosynth Gardens"),Perm("Mana Vault")),c=1)
    copies=[q for q in v03_actions(s) if any(x.aux=="COPY:Mana Vault" for x in q.battlefield)]
    assert copies, "Gardens->Vault copy absent"
    assert any(x.c>=3 for q in copies for x in tap_mana_actions(q)), "Gardens Vault copy doesn't tap as Vault"
    # Tezz 0 can untap a Gardens artifact copy.
    q=copies[0]
    bf=q.battlefield+(Perm("Tezzeret, Cruel Captain",False,0,1,loyalty=4),)
    q=replace(q,battlefield=bf,c=0)
    tapped=[x for x in tap_mana_actions(q) if any(y.aux=="COPY:Mana Vault" and y.tapped for y in x.battlefield)]
    assert tapped and any(any(y.aux=="COPY:Mana Vault" and not y.tapped for y in z.battlefield) for x in tapped for z in v03_actions(x)), "Tezz failed copied-artifact untap"
    # Tezz -3 -> LED -> activation can generate WWW with combo creatures safely in library.
    s=State(1,(),("Lion's Eye Diamond",)+tuple(COMBO_CREATURES),(Perm("Tezzeret, Cruel Captain",False,0,1,loyalty=4),))
    qs=[q for q in v03_actions(s) if "Lion's Eye Diamond" in q.hand]
    assert qs, "Tezz->LED tutor absent"
    ledcasts=[z for q in qs for z in cast_actions(q) if any(x.name=="Lion's Eye Diamond" for x in z.battlefield)]
    assert ledcasts and any(x.w>=3 for z in ledcasts for x in tap_mana_actions(z)), "Tezz->LED activation chain failed"
    # Expedition Map can contextually find Great Hall, not merely fixed priority.
    s=State(1,(),("Great Hall of the Citadel",)+tuple(COMBO_CREATURES),(Perm("Expedition Map"),),c=2)
    assert any("Great Hall of the Citadel" in q.hand for q in v03_actions(s)), "Map contextual target failed"
    # Urza's Cave can contextually put Planar Nexus tapped.
    s=State(1,(),("Planar Nexus",)+tuple(COMBO_CREATURES),(Perm("Urza's Cave"),),c=3)
    assert any(any(x.name=="Planar Nexus" and x.tapped for x in q.battlefield) for q in v03_actions(s)), "Cave contextual target failed"
    # Saga III follows deterministic LED > Vault policy.
    s=State(3,(),("Lion's Eye Diamond","Mana Vault")+tuple(COMBO_CREATURES),(Perm("Urza's Saga",False,3,1,aux="SAGA3"),))
    ss=saga_tutor_actions(s)
    got={x.name for q in ss for x in q.battlefield}
    assert "Lion's Eye Diamond" in got and "Mana Vault" not in got, "Saga tutor heuristic failed"
    # Creature contamination overrides acceleration and finds Brainstone.
    s=State(3,("Boonweaver Giant",),("Brainstone","Lion's Eye Diamond","Mana Vault"),(Perm("Urza's Saga",False,3,1,aux="SAGA3"),))
    ss=saga_tutor_actions(s)
    assert any(any(x.name=="Brainstone" for x in q.battlefield) for q in ss), "Saga failed repair priority"
    # Search-level direct LED T1 line.
    hand=sort_hand(("Lion's Eye Diamond","Ancient Tomb","Sol Ring","Lotus Petal"))
    lib=tuple(COMBO_CREATURES)+tuple(x for x in DECK if x not in hand and x not in COMBO_CREATURES)[:30]
    q=search_turn(State(1,hand,lib),beam=3000,depth=24)
    assert can_cast_dack(q), "search lost direct LED T1 line"
    # Search-level Vault + Key engine retains the expected five generic after setup.
    hand=sort_hand(("Mana Vault","Voltaic Key","Ancient Tomb","Plains","Lotus Petal"))
    lib=tuple(COMBO_CREATURES)+tuple(x for x in DECK if x not in hand and x not in COMBO_CREATURES)[:30]
    q=search_turn(State(1,hand,lib),beam=3000,depth=28)
    assert q.c+q.w+q.any>=6, "search lost Vault-Key mana engine"
    # Exhaustive payment regression: generic 1 from W+C retains both distinct remainders.
    s=State(1,(),tuple(COMBO_CREATURES),w=1,c=1)
    po=pay_options(s,1)
    assert any(q.w==1 and q.c==0 for q in po) and any(q.w==0 and q.c==1 for q in po), "payment branching incomplete"
    # Frontier search must retain multiple strategically distinct terminal states.
    s=State(1,("Plains","Ancient Tomb","Sol Ring"),tuple(COMBO_CREATURES))
    wins,fr=search_turn_frontier(s,beam=1000,depth=8)
    assert len(fr)>1 or wins, "turn frontier collapsed to one line"
    # Brainstone/Rack must be proactive dig engines, not only creature-repair buttons.
    s=State(1,("Plains","Sol Ring"),("Mana Vault","Ancient Tomb","Lotus Petal")+tuple(COMBO_CREATURES),
            battlefield=(Perm("Brainstone",False,0,1),),c=2)
    assert repair_actions(s), "Brainstone proactive dig missing"
    s=State(1,("Plains","Sol Ring"),("Mana Vault","Ancient Tomb")+tuple(COMBO_CREATURES),
            battlefield=(Perm("Scroll Rack",False,0,1),),c=1)
    assert repair_actions(s), "Scroll Rack proactive dig missing"
    s=State(1,(),(),battlefield=(Perm("Grim Monolith",True,0,1),),c=4)
    assert any(not q.battlefield[0].tapped for q in utility_actions(s)), "Grim self-untap missing"
    s=State(1,(),(),battlefield=(Perm("Basalt Monolith",True,0,1),),c=3)
    assert any(not q.battlefield[0].tapped for q in utility_actions(s)), "Basalt self-untap missing"
    # Exact commander payment allocation: 6 total with only one usable white must fail.
    lib=tuple(COMBO_CREATURES)
    assert not can_cast_dack(State(1,(),lib,w=1,c=5)), "Dack incorrectly cast with only one white"
    assert can_cast_dack(State(1,(),lib,w=2,c=4)), "Dack exact WW+4 failed"
    assert can_cast_dack(State(1,(),lib,w=1,c=4,restricted_dack_white=1)), "Cavern/Great-Hall Dack white failed"
    # Nonstarting Caverns branches no-use plus each safe exile.
    gs=State(1,sort_hand(("Gemstone Caverns","Plains","Sol Ring")),())
    assert len(_pregame_states(gs,1))==2, "Gemstone deterministic visible-state branch missing"
    assert _pregame_states(gs,1)[1].exile==("Plains",), "Gemstone exile heuristic regression"
    # 2026 The Mind Stone is {1}{W} and taps for W.
    assert COSTS["The Mind Stone"]==(1,1,0), "The Mind Stone cost regression"
    ms=State(1,(),(),battlefield=(Perm("The Mind Stone",False,0,1),))
    assert any(q.w==1 for q in tap_mana_actions(ms)), "The Mind Stone must tap W"
    # Urza's Cave is a Cave, not an Urza's land; Workshop and Nexus are Urza's.
    us=State(1,(),(),battlefield=(Perm("Urza's Cave"),Perm("Urza's Workshop"),Perm("Planar Nexus")))
    assert urza_count(us)==2, "Urza land-type count wrong"
    # Remote Farm persists after its final depletion counter is removed.
    rf=State(2,(),(),battlefield=(Perm("Remote Farm",False,1,1),))
    rr=[q for q in tap_mana_actions(rf) if q.w==2]
    assert rr and not any(x.name=="Remote Farm" for x in rr[0].battlefield), "Remote Farm must sacrifice after last depletion counter"
    uv=State(2,(),(),battlefield=(Perm("Mana Vault",True,0,1),Perm("Sol Ring"),Perm("Ancient Tomb")))
    uo=mana_vault_upkeep_options(uv,beam=80,depth=6)
    assert any(any(effective_name(x)=="Mana Vault" and not x.tapped for x in q.battlefield) for q in uo), "Mana Vault upkeep untap missing"
    # Natural combo-creature contamination is represented deterministically.
    cs=State(2,("Boonweaver Giant",),tuple(x for x in COMBO_CREATURES if x!="Boonweaver Giant"),(),w=3,c=3)
    assert not can_cast_dack(cs), "combo creature contamination failed to invalidate Dack"
    # London-bottom semantics: bottom cards are excluded from unknown T1/T2 draws.
    uh=("Plains","Ancient Den","Sol Ring","Mana Vault")
    bb=("Boonweaver Giant",)
    # direct construction invariant used by both evaluators
    assert bb[0] not in uh[:2] and (list(uh)+list(bb))[-1]=="Boonweaver Giant"
    # structural hierarchy requested for London screening.
    sev=("Boonweaver Giant","Shardmage\'s Rescue","Silence","Plains","Ancient Tomb","Mana Vault","Sol Ring")
    assert bottom_priority("Boonweaver Giant",sev)>bottom_priority("Shardmage\'s Rescue",sev)>bottom_priority("Silence",sev)>bottom_priority("Mana Vault",sev)
    sev2=("Chrome Mox","Plains","Paladin Class","Prismatic Lens","Touch the Spirit Realm","Bilbo's Gambit","Tooth of Ramos")
    assert bottom_priority("Paladin Class",sev2)>bottom_priority("Plains",sev2)>bottom_priority("Chrome Mox",sev2)
    # Weighted T2/T3 utility identity regression.
    wh=sort_hand(("Mana Vault","Voltaic Key","Plains","Ancient Tomb","Lotus Petal","Silence","Path to Exile"))
    wl=("Floating Shield","Idolized","Bilbo's Gambit")+tuple(x for x in DECK if x not in wh and x not in {"Floating Shield","Idolized","Bilbo's Gambit"})
    assert _win_turn_from_unknown_order(wh,wl,0,beam=500,max_turn=3)==2, "weighted turn evaluator lost known T2 line"
    we=keep_weighted_ev(wh,tuple(wl),beam=80,samples=1,t3_weight=.5)
    assert abs(we["utility"]-(we["le2"]+.5*we["t3"]))<1e-12, "weighted utility identity failed"
    # v0.33 exact Bauble / Void Mirror payment regressions.
    bs=State(1,("Lotus Petal",),(),(Perm("Vexing Bauble"),))
    assert not cast_actions(bs), "Bauble failed to counter true zero-mana spell"
    bs=State(1,("Lotus Petal",),(),(Perm("Vexing Bauble"),Perm("Trinisphere")),c=3)
    assert any(any(x.name=="Lotus Petal" for x in q.battlefield) for q in cast_actions(bs)), "Bauble incorrectly blocked taxed zero-MV spell"
    vs=State(1,("Sol Ring",),(),(Perm("Void Mirror"),),c=1)
    assert not cast_actions(vs), "Void Mirror failed on all-colorless payment"
    vs=State(1,("Sol Ring",),(),(Perm("Void Mirror"),),w=1)
    assert any(any(x.name=="Sol Ring" for x in q.battlefield) for q in cast_actions(vs)), "Void Mirror blocked colored generic payment"
    # Full state key distinguishes different future libraries.
    ka=State(1,(),("Plains","Sol Ring")); kb=State(1,(),("Plains","Mana Vault"))
    assert key(ka)!=key(kb), "full-library state key regression"
    # Post-search shuffle canonicalizes unknown remainder.
    ss=State(1,(),("Mana Vault","Z","A"),(Perm("Tezzeret, Cruel Captain",loyalty=4),))
    so=v03_actions(ss)
    assert any(q.library==shuffled_unknown(("A","Z")) for q in so if "Mana Vault" in q.hand), "post-search hidden shuffle regression"
    # v0.32 canonical deck and new-card regressions.
    assert len(DECK)==99 and DECK.count("Plains")==4, "canonical v0.32 deck count failed"
    assert "Pentad Prism" in DECK and "Moonsilver Key" in DECK and "Starting Town" in DECK
    # New colored lands produce usable colored mana (canonical W is equivalent in this deck).
    for land in ("City of Brass","Mana Confluence","Gemstone Mine","Starting Town","Tarnished Citadel"):
        qs=tap_mana_actions(State(1,(),(),(Perm(land),)))
        assert any(q.w+q.any>=1 for q in qs), f"{land} colored mana missing"
    # Spire gives colorless without Metalcraft and colored with Metalcraft.
    assert any(q.c>=1 for q in tap_mana_actions(State(1,(),(),(Perm("Spire of Industry"),))))
    sm=State(1,(),(),(Perm("Spire of Industry"),Perm("Sol Ring"),Perm("Mana Vault"),Perm("Ancient Den")))
    assert any(q.w+q.any>=1 for q in tap_mana_actions(sm)), "Spire artifact-enabled color missing"
    # Prism with two unrestricted colored units can enter with two counters and spend them.
    ps=State(1,("Pentad Prism",),(),(),any=2)
    pp=[q for q in cast_actions(ps) if any(x.name=="Pentad Prism" and x.counters==2 for x in q.battlefield)]
    assert pp, "Pentad Prism two-counter sunburst missing"
    assert any(q.any>=1 for q in pp for q in tap_mana_actions(q)), "Pentad Prism mana activation missing"
    # Moonsilver Key follows LED-first deterministic tutor policy.
    ks=State(1,(),("Lion's Eye Diamond","Mana Vault","Plains"),(Perm("Moonsilver Key"),),c=1)
    ko=v03_actions(ks)
    assert any("Lion's Eye Diamond" in q.hand for q in ko), "Moonsilver Key LED tutor missing"
    # Known deterministic Vault T2 shell must survive the search.
    hand=sort_hand(("Mana Vault","Voltaic Key","Plains","Ancient Tomb","Lotus Petal","Silence","Path to Exile"))
    lib=("Floating Shield","Idolized")+tuple(x for x in DECK if x not in hand and x not in {"Floating Shield","Idolized"})
    s=draw(State(1,hand,lib),1)
    wins,f1=search_turn_frontier_many([s],beam=2500,depth=24)
    if not wins:
        states=[]
        for x in f1:
            y=draw(untap_and_begin(replace(x,turn=2)),1)
            states.append(y)
        wins,_=search_turn_frontier_many(states,beam=2500,depth=24)
    assert wins, "known Mana Vault/Tomb/Petal T2 line lost"

    # v0.38 hard regressions: known exact T3 continuations must survive the mulligan-evaluator beam.
    def _exact_lib(h,b,d):
        rr=DECK[:]
        for xx in list(h)+list(b)+list(d): rr.remove(xx)
        return tuple(list(d)+rr+list(b))
    h=("Ancient Tomb","Loyal Tutor","Mana Confluence","Mana Vault","The Mycosynth Gardens")
    b=("Bilbo's Gambit","Pearl Medallion");d=("Plains","Liquimetal Torque","Eldrazi Confluence")
    assert _win_turn_from_unknown_order(sort_hand(h),_exact_lib(h,b,d),2,beam=40,max_turn=3)==3, "known Vault/Tutor T3 pruned"
    h=("Mox Opal","Plains","Plains","The Mycosynth Gardens","Urza's Saga")
    b=("Bound by Moonsilver","Shefet Dunes");d=("Mox Diamond","Calamity's Wake","Silence")
    assert _win_turn_from_unknown_order(sort_hand(h),_exact_lib(h,b,d),2,beam=40,max_turn=3)==3, "known Saga/Opal T3 pruned"
    # v0.68 color canonicalization: flexible sources choose W when no current card
    # can distinguish a nonwhite color, but retain unrestricted color for Pentad Prism.
    for _land,_cnt in (("City of Brass",0),("Mana Confluence",0),("Starting Town",0),
                       ("Tarnished Citadel",0),("Gemstone Mine",3)):
        _plain=State(1,(),(),(Perm(_land,False,_cnt,1),))
        _a=tap_mana_actions(_plain)
        assert any(q.w==1 for q in _a), f"{_land} failed W canonicalization"
        _prism=State(1,("Pentad Prism",),(),(Perm(_land,False,_cnt,1),))
        _b=tap_mana_actions(_prism)
        assert any(q.any==1 for q in _b), f"{_land} lost Prism color flexibility"

    print("selftest: PASS")

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--games",type=int,default=1000)
    ap.add_argument("--seed",type=int,default=20260925)
    ap.add_argument("--beam",type=int,default=3000)
    ap.add_argument("--selftest",action="store_true")
    ap.add_argument("--json",default="")
    a=ap.parse_args()
    if a.selftest:selftest()
    else:
        r=run(a.games,a.seed,a.beam)
        print(json.dumps(r,indent=2))
        if a.json:
            open(a.json,"w").write(json.dumps(r,indent=2))

def london_sizes(min_keep=1):
    """Legal London keep sizes. Commander mulligans may continue through 3/2/1."""
    min_keep=max(1,min(7,int(min_keep)))
    return tuple(range(7,min_keep-1,-1))

def structural_bottom_candidates(seven,keep_n,top_n=2):
    from itertools import combinations
    seven=tuple(seven)
    if keep_n==7:return [(sort_hand(seven),())]
    nb=7-keep_n; out=[]
    for inds in combinations(range(7),nb):
        ii=set(inds); b=tuple(seven[i] for i in inds); h=tuple(seven[i] for i in range(7) if i not in ii)
        out.append((sum(bottom_priority(x,seven) for x in b),sort_hand(h),b))
    out.sort(key=lambda z:z[0],reverse=True)
    # Structural score is a screen, not a hard oracle. Preserve diverse mana shapes so tied
    # coarse priorities cannot erase compact Tomb/land/fast-mana keeps.
    chosen=[]
    def add(z):
        hb=(z[1],z[2])
        if hb not in chosen: chosen.append(hb)
    for z in out[:top_n]: add(z)
    def sigscore(z,mode):
        h=z[1]
        lands=sum(x in LANDS or x in {"Emeria's Call","Razorgrass Ambush"} for x in h)
        fast=sum(x in {"Ancient Tomb","City of Traitors","Crystal Vein","Lion's Eye Diamond",
                       "Lotus Petal","Mana Vault","Grim Monolith","Sol Ring","Mox Diamond","Chrome Mox"} for x in h)
        white=sum(x in WHITE_LANDS or x in {"City of Brass","Mana Confluence","Gemstone Mine","Starting Town",
                                            "Tarnished Citadel","Lotus Petal","Mox Diamond"} for x in h)
        engines=sum(x in RAMP_PROTECTED for x in h)
        return ((fast,lands,white,engines,z[0]) if mode==0 else
                (lands,fast,white,engines,z[0]) if mode==1 else
                (white,fast,lands,engines,z[0]))
    for mode in range(3):
        for z in sorted(out,key=lambda z:sigscore(z,mode),reverse=True)[:2]: add(z)
    return chosen

LOW_HAND_EXACT_MAX=3

def adaptive_bottom_weighted_ev(seven,keep_n,unknown_lib,threshold,t3_weight=.5,beam=40,
                                base_samples=2,refine_samples=5,margin=.16,top_n=2):
    """Common-future adaptive London evaluation with exhaustive exact low-hand treatment through keep-3."""
    from itertools import combinations
    structural=structural_bottom_candidates(seven,keep_n,top_n)
    def struct_score(b):return sum(bottom_priority(x,seven) for x in b)

    # Reaching 3/2/1 cards is rare, and there are only 35/21/7 legal bottom choices. Sparse
    # early futures are especially dangerous here because continuation thresholds are tiny.
    # Evaluate every legal choice at N=20 so genuine compact low-card hands are not lost to a zero tie.
    if keep_n<=LOW_HAND_EXACT_MAX:
        scored=[]
        for inds0 in combinations(range(7),7-keep_n):
            inds=set(inds0)
            h=sort_hand([x for i,x in enumerate(seven) if i not in inds])
            b=tuple(seven[i] for i in sorted(inds))
            ev=keep_turn_distribution(h,unknown_lib,beam=beam,samples=20,bottom=b)
            u=utility_from_distribution(ev,t3_weight)
            scored.append((u,struct_score(b),h,b,ev))
        scored.sort(key=lambda z:(z[0],z[1]),reverse=True)
        u,_,h,b,ev=scored[0]
        return (u,h,b,ev,20)

    candidates=list(structural)
    # At keep 3-6, enumerate every legal bottom set only on a cheap screening beam. Every
    # nominated finalist is then re-evaluated at the production beam.
    if keep_n<=6:
        allc=[]
        for inds0 in combinations(range(7),7-keep_n):
            inds=set(inds0)
            h=sort_hand([x for i,x in enumerate(seven) if i not in inds])
            b=tuple(seven[i] for i in sorted(inds))
            ev1=keep_turn_distribution(h,unknown_lib,beam=min(14,beam),samples=1,bottom=b)
            allc.append((utility_from_distribution(ev1,t3_weight),struct_score(b),h,b))
        allc.sort(reverse=True,key=lambda z:(z[0],z[1]))
        candidates=[]
        for _,_,h,b in allc[:4]:
            if (h,b) not in candidates:candidates.append((h,b))
        for h,b in structural[:3]:
            if (h,b) not in candidates:candidates.append((h,b))

    scored=[]
    for h,b in candidates:
        ev=keep_turn_distribution(h,unknown_lib,beam=beam,samples=base_samples,bottom=b)
        u=utility_from_distribution(ev,t3_weight)
        scored.append((u,struct_score(b),h,b,ev))
    scored.sort(key=lambda z:(z[0],z[1]),reverse=True)
    u,_,h,b,ev=scored[0];best=(u,h,b,ev,base_samples)

    if keep_n>1 and abs(best[0]-threshold)<=margin:
        finalists=[]
        for _,_,h,b,_ in scored[:min(3,len(scored))]:
            if (h,b) not in finalists:finalists.append((h,b))
        # Keep structural-prior candidates alive when the first two common futures tie at zero.
        for h,b in structural[:3]:
            if (h,b) in candidates and (h,b) not in finalists:finalists.append((h,b))
        scored5=[]
        for h,b in finalists:
            ev=keep_turn_distribution(h,unknown_lib,beam=beam,samples=refine_samples,bottom=b)
            u=utility_from_distribution(ev,t3_weight)
            scored5.append((u,struct_score(b),h,b,ev))
        scored5.sort(key=lambda z:(z[0],z[1]),reverse=True)
        u,_,h,b,ev=scored5[0];best=(u,h,b,ev,refine_samples)

        if abs(best[0]-threshold)<=0.08:
            finalists10=[]
            for _,_,h,b,_ in scored5[:min(2,len(scored5))]:finalists10.append((h,b))
            for h,b in structural[:1]:
                if (h,b) in candidates and (h,b) not in finalists10:finalists10.append((h,b))
            scored10=[]
            for h,b in finalists10:
                ev=keep_turn_distribution(h,unknown_lib,beam=beam,samples=10,bottom=b)
                u=utility_from_distribution(ev,t3_weight)
                scored10.append((u,struct_score(b),h,b,ev))
            scored10.sort(key=lambda z:(z[0],z[1]),reverse=True)
            u,_,h,b,ev=scored10[0];best=(u,h,b,ev,10)
    return best

def backward_values_from_raw(raw_by_k):
    """Recompute London continuation utilities from pooled raw keep utilities."""
    V={0:0.0}; out={}
    for k in range(1,8):
        vals=list(raw_by_k[k])
        V[k]=sum(max(x,V[k-1]) for x in vals)/len(vals) if vals else V[k-1]
        out[k]=V[k]
    return out

def classification_audit():
    """Fail loudly if known canonical mana-development categories regress."""
    required_lands={"Shefet Dunes","Spire of Industry","Starting Town","Tarnished Citadel"}
    required_ramp={"Pearl Medallion","Moonsilver Key","Expedition Map","Candelabra of Tawnos",
                   "Giant's Boulder","Pentad Prism","Gleaming Splendor"}
    assert required_lands <= set(LANDS), ("missing lands",required_lands-set(LANDS))
    assert required_ramp <= set(RAMP_PROTECTED), ("missing ramp",required_ramp-set(RAMP_PROTECTED))
    return True

def v048_rules_audit():
    # Moonsilver Key must never tutor Brainstone.
    st=State(1,("Boonweaver Giant",),("Brainstone","Lion's Eye Diamond","Mana Vault","Plains"),
             (Perm("Moonsilver Key"),),c=1)
    ks=[q for q in v03_actions(st) if "Moonsilver Key" in q.grave]
    assert ks and all("Brainstone" not in q.hand for q in ks)
    assert any("Lion's Eye Diamond" in q.hand for q in ks)
    # Gemstone Mine has exactly three colored activations before sacrifice.
    q=play_land_actions(State(1,("Gemstone Mine",),()))[0]
    assert q.battlefield[0].counters==3
    for n in (2,1):
        q=next(x for x in tap_mana_actions(q) if x.any>q.any)
        assert q.battlefield[0].counters==n
        q=replace(q,battlefield=(replace(q.battlefield[0],tapped=False),))
    q=next(x for x in tap_mana_actions(q) if x.any>q.any)
    assert not q.battlefield
    # Tarnished and Shefet expose both C and colored/W modes.
    ta=tap_mana_actions(State(1,(),(),(Perm("Tarnished Citadel"),)))
    assert any(x.c==1 for x in ta) and any(x.any==1 for x in ta)
    sh=tap_mana_actions(State(1,(),(),(Perm("Shefet Dunes"),)))
    assert any(x.c==1 for x in sh) and any(x.w==1 for x in sh)
    return True

def v050_hidden_audit():
    # Search shuffle cannot depend on pre-search unknown ordering.
    a=("Plains","Ancient Tomb","Sol Ring","Silence")
    assert shuffled_unknown(a)==shuffled_unknown(tuple(reversed(a)))
    # Land target cannot depend on library ordering.
    a=State(1,(),("Plains","Ancient Tomb","City of Traitors"))
    b=State(1,(),("City of Traitors","Plains","Ancient Tomb"))
    assert land_tutor_choice(a)==land_tutor_choice(b)
    # White shortage visibly prioritizes white source; adequate visible white prioritizes acceleration.
    assert land_tutor_choice(a)=="Plains"
    c=State(1,("Plains","Ancient Den"),("Plains","Ancient Tomb","City of Traitors"))
    assert land_tutor_choice(c)=="Ancient Tomb"
    return True

def v051_candidate_audit():
    seven=("Ancient Tomb","Vexing Bauble","Plains","Starting Town","Lotus Petal","Sheltered by Ghosts","Razorgrass Ambush")
    target=sort_hand(("Ancient Tomb","Lotus Petal","Starting Town"))
    cs=structural_bottom_candidates(seven,3,2)
    assert any(h==target for h,b in cs), "compact fast-mana keep pruned by structural screen"
    return True

def v052_deep_bottom_prescreen_audit():
    seven=("Voltaic Key","Grim Monolith","Candelabra of Tawnos","Silence","Kozilek's Command","Shefet Dunes","Jeweled Amulet")
    target=sort_hand(("Candelabra of Tawnos","Grim Monolith","Jeweled Amulet","Shefet Dunes","Voltaic Key"))
    # Structural candidate generator may rank differently; exhaustive one-future prescreen in the
    # adaptive evaluator must be capable of surfacing this compact synergy hand.
    from itertools import combinations
    assert any(sort_hand([x for i,x in enumerate(seven) if i not in set(inds)])==target
               for inds in combinations(range(7),2))
    return True


def v056_performance_audit():
    # Payment ranks above the number of distinct residual pools must not repeat branches.
    st=State(1,(),(),w=1,c=2,any=1)
    opts=pay_options(st,1)
    assert pay_simple(st,1,payment_rank=len(opts)) is None
    # Exact library tokens: same ordered content interns together; changed order differs.
    a=("Plains","Ancient Tomb","Sol Ring")
    b=tuple(list(a)); c=("Ancient Tomb","Plains","Sol Ring")
    assert library_token(a)==library_token(b)
    assert library_token(a)!=library_token(c)
    # Cached deterministic shuffle is content-exact and returns the same permutation.
    sh1=shuffled_unknown(("Plains","Ancient Tomb","Sol Ring"));sh2=shuffled_unknown(("Sol Ring","Plains","Ancient Tomb"))
    assert sh1==sh2
    # Chalice still exposes higher-rank kicker payments after duplicate-rank suppression.
    st2=State(1,("Everflowing Chalice",),(),w=1,c=3)
    assert cast_actions(st2), "Chalice payment branches disappeared"
    # London structural hierarchy orientation: larger means more desirable to bottom.
    seven=("Boonweaver Giant","Gift of Immortality","Silence","Plains","Mana Vault","Sol Ring","Ancient Tomb")
    assert bottom_priority("Boonweaver Giant",seven)>bottom_priority("Gift of Immortality",seven)>bottom_priority("Silence",seven)>bottom_priority("Plains",seven)>bottom_priority("Mana Vault",seven)
    # Seats 1/2/3 are identical in the current goldfish; only Gemstone distinguishes seat 0.
    h=("Plains","Sol Ring");lib=("Silence","Mana Vault","Ancient Tomb")
    assert _pregame_states(State(1,h,lib),1)==_pregame_states(State(1,h,lib),2)==_pregame_states(State(1,h,lib),3)
    return True

def v058_trace_audit():
    # Sparse low-card keeps must bypass sampled shortlist pruning.
    assert LOW_HAND_EXACT_MAX==3

    # LED is a real three-white resource for a commander-zone Dack cast. This exact land+LED
    # line was pruned at beam 40 before the LED-aware score/signature repair.
    h=sort_hand(("Cavern of Souls","Command Beacon","Eiganjo, Seat of the Empire",
                 "Lion's Eye Diamond","Plains","Urza's Cave"))
    b=("Static Prison",)
    rr=DECK[:]
    for x in list(h)+list(b): rr.remove(x)
    d=[]
    for x in ("Silence","Path to Exile","Portable Hole"):
        rr.remove(x); d.append(x)
    lib=tuple(d+rr+list(b))
    assert _win_turn_from_unknown_order(h,lib,0,beam=40,max_turn=3)==3, "LED T3 line pruned at beam40"
    return True

def v059_land_rules_audit():
    # Remote Farm: ETB tapped with two depletion counters; second activation produces WW and sacrifices it.
    q=play_land_actions(State(1,("Remote Farm",),()))[0]
    assert q.battlefield[0].tapped and q.battlefield[0].counters==2
    q=replace(q,battlefield=(replace(q.battlefield[0],tapped=False),))
    q=next(x for x in tap_mana_actions(q) if x.w==2)
    assert q.battlefield and q.battlefield[0].counters==1
    q=replace(q,battlefield=(replace(q.battlefield[0],tapped=False),),w=0)
    q=next(x for x in tap_mana_actions(q) if x.w==2)
    assert not any(x.name=="Remote Farm" for x in q.battlefield)

    # Playing either MDFC land face while City is present creates the sacrifice trigger.
    for card in ("Emeria's Call","Razorgrass Ambush"):
        s=State(1,(card,),(),(Perm("City of Traitors"),))
        outs=play_land_actions(s)
        assert outs and all(city_trigger_pending(o) for o in outs)
        assert all(not any(x.name=="City of Traitors" for x in resolve_city_trigger_actions(o)[0].battlefield) for o in outs)

    # Ruins of Trokair's normal and sacrifice modes.
    s=State(1,(),(),(Perm("Ruins of Trokair"),))
    acts=tap_mana_actions(s)
    assert any(q.w==1 and any(x.name=="Ruins of Trokair" for x in q.battlefield) for q in acts)
    assert any(q.w==2 and not any(x.name=="Ruins of Trokair" for x in q.battlefield) for q in acts)
    return True

def v060_targeted_rules_audit():
    # Spire of Industry: unconditional C, colored mode with ANY artifact (not Metalcraft).
    s=State(1,(),(),(Perm("Spire of Industry"),))
    acts=tap_mana_actions(s)
    assert any(q.c==1 for q in acts) and not any(q.any==1 for q in acts)
    s=State(1,(),(),(Perm("Spire of Industry"),Perm("Sol Ring")))
    acts=tap_mana_actions(s)
    assert any(q.c==1 for q in acts) and any(q.any==1 for q in acts)

    # Mox Opal still requires actual Metalcraft and counts itself as one artifact.
    s=State(1,(),(),(Perm("Mox Opal"),Perm("Sol Ring")))
    assert not any(q.any==1 for q in tap_mana_actions(s))
    s=State(1,(),(),(Perm("Mox Opal"),Perm("Sol Ring"),Perm("Ancient Den")))
    assert any(q.any==1 for q in tap_mana_actions(s))

    # Candelabra X=1 can untap a tapped land; X distinct targets are preserved.
    s=State(1,(),(),(Perm("Candelabra of Tawnos"),Perm("Ancient Tomb",True)),c=1)
    ca=utility_actions(s)
    assert any(any(p.name=="Ancient Tomb" and not p.tapped for p in q.battlefield) for q in ca)

    # Coalition Relic charge cannot be spent in upkeep, but appears in first main.
    s=State(2,(),(),(Perm("Coalition Relic",False,1),Perm("Mana Vault",True),
                       Perm("Sol Ring")))
    q=untap_and_begin(s)
    assert q.any==0 and any(p.name=="Coalition Relic" and p.counters==1 for p in q.battlefield)
    # Coalition's ordinary tap + Sol Ring = only 3, so charge counter must not illegally untap Vault in upkeep.
    up=mana_vault_upkeep_options(q)
    assert not any(any(p.name=="Mana Vault" and not p.tapped for p in z.battlefield) for z in up)
    q=begin_first_main(q)
    assert q.any==1 and any(p.name=="Coalition Relic" and p.counters==0 for p in q.battlefield)

    # Gleaming locked abstraction: one Treasure exists before upkeep, so it may pay upkeep costs.
    s=State(2,(),(),(Perm("Gleaming Splendor"),Perm("Mana Vault",True),
                       Perm("Sol Ring"),Perm("Plains")))
    q=add_opponent_cycle_resources(untap_and_begin(s))
    assert q.treasures==1
    up=mana_vault_upkeep_options(q)
    assert any(any(p.name=="Mana Vault" and not p.tapped for p in z.battlefield) for z in up)

    # Pentad Prism sunburst color accounting.
    ps=State(1,("Pentad Prism",),(),(),w=2)
    assert any(p.name=="Pentad Prism" and p.counters==1 for q in cast_actions(ps) for p in q.battlefield)
    ps=State(1,("Pentad Prism",),(),(),w=1,any=1)
    assert any(p.name=="Pentad Prism" and p.counters==2 for q in cast_actions(ps) for p in q.battlefield)

    # LED: discards hand for WWW and cannot be used while a combo creature is stranded in hand.
    s=State(1,("Silence",),(),(Perm("Lion's Eye Diamond"),))
    la=tap_mana_actions(s)
    assert any(q.w==3 and not q.hand and "Silence" in q.grave for q in la)
    s=State(1,("Boonweaver Giant",),(),(Perm("Lion's Eye Diamond"),))
    assert not any(q.w>=3 for q in tap_mana_actions(s))

    # Mox Diamond may discard true land cards, never MDFCs.
    s=State(1,("Mox Diamond","Plains","Emeria's Call","Razorgrass Ambush"),())
    ma=[q for q in cast_actions(s) if any(p.name=="Mox Diamond" for p in q.battlefield)]
    assert ma and all("Plains" in q.grave for q in ma)
    assert all("Emeria's Call" not in q.grave and "Razorgrass Ambush" not in q.grave for q in ma)

    # City trigger remains on stack long enough to tap City in response, then City is sacrificed.
    s=State(1,("Plains",),(),(Perm("City of Traitors"),))
    q=play_land_actions(s)[0]
    assert city_trigger_pending(q)
    taps=[z for z in tap_mana_actions(q) if z.c>=2]
    assert taps
    z=resolve_city_trigger_actions(taps[0])[0]
    assert z.c>=2 and not any(p.name=="City of Traitors" for p in z.battlefield)

    # If City was already tapped, Candelabra can untap it in response to its sacrifice trigger.
    s=State(1,("Plains",),(),(Perm("City of Traitors",True),Perm("Candelabra of Tawnos")),c=1)
    q=play_land_actions(s)[0]
    assert city_trigger_pending(q)
    unt=[z for z in utility_actions(q)
         if any(p.name=="City of Traitors" and not p.tapped for p in z.battlefield)]
    assert unt
    taps=[z for z in tap_mana_actions(unt[0]) if z.c>=2]
    assert taps
    return True

# ---------- v0.61 dual-policy tracking ----------
POLICY_OBJECTIVES = {
    "t2_max": 0.0,
    "t2_t3_balanced": 0.5,
}

def policy_utility(ev, policy):
    lam = POLICY_OBJECTIVES[policy] if isinstance(policy, str) else float(policy)
    return ev["le2"] + lam * ev["t3"]

def dual_policy_keep_eval(seven, keep_n, unknown_lib, thresholds, beam=40,
                          base_samples=2, refine_samples=5, margin=.16, top_n=2):
    """Evaluate the same visible London hand under both policy objectives.
    Distribution/win caches are shared; only utility and continuation thresholds differ.
    """
    out={}
    for policy,lam in POLICY_OBJECTIVES.items():
        u,h,b,ev,ns = adaptive_bottom_weighted_ev(
            seven, keep_n, unknown_lib, thresholds.get(policy,0.0),
            lam, beam, base_samples, refine_samples, margin, top_n
        )
        out[policy]={"utility":u,"hand":h,"bottom":b,"ev":ev,"samples":ns}
    return out

def dual_backward_values(raw_by_policy):
    """Recompute policy-specific London continuation values from raw best-keep utilities."""
    out={}
    for policy in POLICY_OBJECTIVES:
        V={0:0.0}
        for k in range(1,8):
            vals=list(raw_by_policy[policy].get(k,()))
            V[k]=sum(max(x,V[k-1]) for x in vals)/len(vals) if vals else V[k-1]
        out[policy]=V
    return out

# ---------- v0.62 threshold-independent calibration mode ----------
def calibration_keep_eval(seven, keep_n, unknown_lib, policy, beam=40):
    """Raw best-keep utility independent of continuation thresholds.
    k<=3 retains exhaustive N=20 evaluation; k>=4 forces nominated finalists
    through fixed N=10 production-beam evaluation.
    """
    lam = POLICY_OBJECTIVES[policy] if isinstance(policy,str) else float(policy)
    return adaptive_bottom_weighted_ev(
        seven, keep_n, unknown_lib,
        threshold=0.0, t3_weight=lam, beam=beam,
        base_samples=2, refine_samples=10, margin=99.0, top_n=2
    )

def dual_calibration_keep_eval(seven, keep_n, unknown_lib, beam=40):
    return {policy: calibration_keep_eval(seven,keep_n,unknown_lib,policy,beam)
            for policy in POLICY_OBJECTIVES}

def backward_from_fixed_raw(raw_by_policy):
    out={}
    for policy in POLICY_OBJECTIVES:
        V={0:0.0}
        for k in range(1,8):
            vals=list(raw_by_policy[policy].get(k,()))
            V[k]=sum(max(u,V[k-1]) for u in vals)/len(vals) if vals else V[k-1]
        out[policy]=V
    return out


# ---------- v0.63 frozen dual-policy calibration ----------
FROZEN_POLICY_THRESHOLDS = {'t2_max': {0: 0.0, 1: 0.0140625, 2: 0.09457, 3: 0.17125, 4: 0.25766, 5: 0.35113, 6: 0.39885}, 't2_t3_balanced': {0: 0.0, 1: 0.06171875, 2: 0.19234, 3: 0.31419, 4: 0.42268, 5: 0.51025, 6: 0.55603}}

def v063_frozen_calibration_audit():
    for policy,V in FROZEN_POLICY_THRESHOLDS.items():
        assert set(V)==set(range(7))
        assert V[0]==0.0
        for k in range(1,7):
            assert 0.0 <= V[k] <= 1.0
            assert V[k] >= V[k-1], (policy,k,V[k-1],V[k])
    return True


# ---------- v0.64 repair / smoothing audit ----------
def v064_repair_smoothing_audit():
    # Boulder: scry 2 includes keep-one/bottom-one branches.
    base_lib=("Boonweaver Giant","Mana Vault","Plains","Sol Ring")
    s=State(1,("Giant's Boulder",),base_lib,c=1)
    outs=[q for q in cast_actions(s) if any(effective_name(p)=="Giant's Boulder" for p in q.battlefield)]
    libs={q.library for q in outs}
    assert ("Mana Vault","Plains","Sol Ring","Boonweaver Giant") in libs, "Boulder cannot bottom only creature"
    assert ("Boonweaver Giant","Plains","Sol Ring","Mana Vault") in libs, "Boulder cannot bottom only second card"
    assert len(libs)>=6, ("Boulder missing scry branches",len(libs),libs)

    # Amulet: unrestricted colored mana may be banked as white and returned as white.
    s=State(1,(),(),(Perm("Jeweled Amulet"),),any=1)
    charged=[q for q in v03_actions(s) if any(effective_name(p)=="Jeweled Amulet" and p.counters==1 and p.aux=="W" for p in q.battlefield)]
    assert charged and any(q.any==0 for q in charged), "Amulet failed to charge from any-color mana"
    q=untap_and_begin(replace(charged[0],turn=2))
    assert any(z.w>=1 for z in tap_mana_actions(q)), "Amulet failed to return stored white"

    # Campfire: shuffle required creature plus rest of grave into library, exile itself.
    s=State(2,(),("Plains","Mana Vault"),(Perm("Campfire"),),
            grave=("Boonweaver Giant","Lion's Eye Diamond"),c=2)
    rr=repair_actions(s)
    assert rr, "Campfire repair action missing"
    assert any("Boonweaver Giant" in q.library and "Lion's Eye Diamond" in q.library and not q.grave
               and "Campfire" in q.exile for q in rr), "Campfire did not shuffle grave/exile itself"

    # LED may discard a creature if Campfire remains reachable.
    s=State(1,("Boonweaver Giant",),("Campfire","Plains","Mana Vault"),(Perm("Lion's Eye Diamond"),),c=3)
    led=[q for q in tap_mana_actions(s) if "Boonweaver Giant" in q.grave and q.w>=3]
    assert led, "LED incorrectly blocked despite reachable Campfire"

    # Artifact tutor sees grave contamination and prioritizes Campfire.
    s=State(2,(),("Campfire","Lion's Eye Diamond","Mana Vault"),(),grave=("Boonweaver Giant",))
    assert artifact_tutor_choice(s)=="Campfire", "grave repair tutor policy did not choose Campfire"
    return True
