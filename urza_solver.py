
#!/usr/bin/env python3
"""
Urza Tempo Storm state-search simulator (prototype v0.3)

Goal:
  Goldfish the supplied Urza, Lord High Artificer deck through turn 7 using
  beam search, London mulligans, deck-specific mana / tutor / combo rules,
  deterministic seeds, and multiprocessing.

This is intentionally a transparent research simulator, not a generic MTG rules
engine.  It records traces so individual results can be audited and corrected.

No third-party packages required.
"""

from __future__ import annotations
import collections
from dataclasses import dataclass, field, replace
from collections import Counter, defaultdict
from pathlib import Path
from typing import Tuple, List, Dict, Optional, Iterable
from functools import lru_cache

try:
    import psutil
except Exception:
    psutil=None

def process_rss_mb():
    if psutil is None:
        return None
    try:
        return psutil.Process(os.getpid()).memory_info().rss/(1024*1024)
    except Exception:
        return None

import argparse, csv, hashlib, heapq, json, math, multiprocessing as mp, os, random, statistics, sys, time, traceback, threading, signal, itertools, itertools

# ----------------------------- Card groups ---------------------------------

COMMANDER = "Urza, Lord High Artificer"

LANDS_BLUE = {
    "Island","Cephalid Coliseum","Ipnu Rivulet","Minamo, School at Water's Edge",
    "Oboro, Palace in the Clouds","Otawara, Soaring City","Seat of the Synod",
    "Flooded Strand","Misty Rainforest","Polluted Delta","Prismatic Vista","Scalding Tarn",
}
MDFC_BLUE_LANDS = {"Hydroelectric Specimen","Sea Gate Restoration","Sink into Stupor"}
SPECIAL_LANDS = {"Ancient Tomb","City of Traitors","Crystal Vein","Saprazzan Skerry",
                 "Gemstone Caverns","Urza's Saga"}
ALL_LANDS = LANDS_BLUE | MDFC_BLUE_LANDS | SPECIAL_LANDS

ZERO_ARTIFACTS = {
    "Everflowing Chalice","Jeweled Amulet","Lotus Petal","Mox Opal","Tormod's Crypt",
    "Urza's Bauble","Mishra's Bauble","Welding Jar","Mox Diamond","Chrome Mox",
}
ONE_ARTIFACTS = {
    "Aether Spellbomb","Codex Shredder","Giant's Boulder","Grafdigger's Cage",
    "Hope of Ghirapur","Mana Vault","Manifold Key","Moonsnare Prototype",
    "Pithing Needle","Sensei's Divining Top","Sewer-veillance Cam","Sol Ring",
    "Vexing Bauble","Voltaic Key","Witching Well",
}
TWO_ARTIFACTS = {
    "Chrome Dome","Defense Grid","Disruptor Flute","Grim Monolith","Grinding Station",
    "Imposter Mech","Prized Statue","Sapphire Medallion","Spellskite","The Reality Chip",
}
THREE_ARTIFACTS = {"Basalt Monolith","Battered Golem","Uthros Research Craft",
                   "Repurposing Bay"}
FOUR_ARTIFACTS = {"The One Ring"}
ARTIFACTS = ZERO_ARTIFACTS | ONE_ARTIFACTS | TWO_ARTIFACTS | THREE_ARTIFACTS | FOUR_ARTIFACTS | {"Seat of the Synod"}

CREATURES = {
    "Artificer's Assistant","Battered Golem","Chrome Dome","Faerie Mastermind",
    "Forensic Gadgeteer","Hope of Ghirapur","Spellseeker","Spellskite",
    "The Reality Chip","Valley Floodcaller","Hydroelectric Specimen",
}
KNUCKS = {"Banishing Knack","Retraction Helix"}
PRODUCERS = {"Grinding Station","Battered Golem","Forensic Gadgeteer"}
CA_ENGINES = {"The Reality Chip","Uthros Research Craft","The One Ring",
              "Fortune Teller's Talent","Mystic Remora","Rhystic Study","Faerie Mastermind"}

# Hot-path immutable membership tables. Frozensets avoid rebuilding temporary
# sets during millions of state evaluations.
F_ARTIFACTS=frozenset(ARTIFACTS)
F_CREATURES=frozenset(CREATURES)
F_ALL_LANDS=frozenset(ALL_LANDS)
F_ZERO_ARTIFACTS=frozenset(ZERO_ARTIFACTS)
F_ONE_ARTIFACTS=frozenset(ONE_ARTIFACTS)
F_PRODUCERS=frozenset(PRODUCERS)
F_CA_ENGINES=frozenset(CA_ENGINES)

# Canonical FRONT-FACE card types relevant to tutors.
INSTANTS = {
    "An Offer You Can't Refuse","Banishing Knack","Chain of Vapor","Dizzy Spell",
    "Dramatic Reversal","Fierce Guardianship","Flusterstorm","Force of Negation",
    "Force of Will","Mana Drain","Mental Misstep","Mindbreak Trap",
    "Muddle the Mixture","Mystical Tutor","Pact of Negation","Retraction Helix",
    "Scour for Scrap","Sink into Stupor","Swan Song","Whir of Invention",
}
SORCERIES = {
    "Gitaxian Probe","Merchant Scroll","Reshape","Sea Gate Restoration",
    "Transmute Artifact",
}
ENCHANTMENT_CARDS = {
    "Fortune Teller's Talent","Mystic Remora","Power Artifact","Rhystic Study",
    "Urza's Saga",
}
PLANESWALKERS = {"Tezzeret, Cruel Captain"}

# Simplified printed costs: (generic, blue)
COST = {
    COMMANDER:(2,2),
    "Aether Spellbomb":(1,0), "Artificer's Assistant":(1,1),
    "Banishing Knack":(0,1), "Basalt Monolith":(3,0), "Battered Golem":(3,0),
    "Chain of Vapor":(0,1), "Chrome Dome":(2,0), "Chrome Mox":(0,0),
    "Codex Shredder":(1,0), "Defense Grid":(2,0), "Disruptor Flute":(2,0),
    "Dizzy Spell":(0,1), "Dramatic Reversal":(1,1), "Everflowing Chalice":(0,0),
    "Faerie Mastermind":(1,1), "Fierce Guardianship":(2,1),
    "Flusterstorm":(0,1), "Force of Negation":(1,2), "Force of Will":(3,2),
    "Forensic Gadgeteer":(2,1),
    "Fortune Teller's Talent":(0,1), "Giant's Boulder":(1,0), "Gitaxian Probe":(0,0),
    "Grafdigger's Cage":(1,0), "Grim Monolith":(2,0), "Grinding Station":(2,0),
    "Hope of Ghirapur":(1,0), "Imposter Mech":(1,1), "Jeweled Amulet":(0,0),
    "Lotus Petal":(0,0), "Mana Drain":(0,2), "Mana Vault":(1,0),
    "Mental Misstep":(0,0), "Mindbreak Trap":(2,2), "Mishra's Bauble":(0,0),
    "Manifold Key":(1,0), "Merchant Scroll":(1,1), "Moonsnare Prototype":(0,1),
    "Mox Diamond":(0,0), "Mox Opal":(0,0), "Muddle the Mixture":(0,2),
    "Mystic Remora":(0,1), "Mystical Tutor":(0,1), "Pact of Negation":(0,0),
    "Pithing Needle":(1,0),
    "Power Artifact":(0,2), "Prized Statue":(2,0), "Repurposing Bay":(2,1),
    "Reshape":(0,2), "Retraction Helix":(0,1), "Rhystic Study":(2,1),
    "Sapphire Medallion":(2,0), "Scour for Scrap":(3,1),
    "Sensei's Divining Top":(1,0), "Sewer-veillance Cam":(0,1), "Sol Ring":(1,0),
    "Spellseeker":(2,1), "Spellskite":(2,0), "Swan Song":(0,1),
    "Tezzeret, Cruel Captain":(3,0),
    "The One Ring":(4,0), "The Reality Chip":(1,1), "Tormod's Crypt":(0,0),
    "Transmute Artifact":(0,2), "Urza's Bauble":(0,0), "Uthros Research Craft":(2,1),
    "Valley Floodcaller":(2,1), "Vexing Bauble":(1,0), "Voltaic Key":(1,0),
    "Welding Jar":(0,0), "Whir of Invention":(0,3), "Witching Well":(0,1),
    "Hydroelectric Specimen":(2,1), "Sink into Stupor":(1,2), "Sea Gate Restoration":(4,3),
    "An Offer You Can\'t Refuse":(0,1),
}

# Cards intentionally treated as "other / not proactive" in the goldfish pilot.
# They still remain cards in hand / library and can be imprinted or bottomed.
OTHER = set()

FETCHES = {"Flooded Strand","Misty Rainforest","Polluted Delta","Prismatic Vista","Scalding Tarn"}
TRUE_LAND_CARDS = (LANDS_BLUE | SPECIAL_LANDS) - MDFC_BLUE_LANDS
# Urza's Saga III requires an artifact CARD with printed mana cost exactly {0} or {1}.
# This is intentionally different from "mana value <= 1": blue {U} artifacts and
# artifact lands with no mana cost do NOT qualify.
SAGA_ZERO_PRINTED = frozenset(ZERO_ARTIFACTS)
SAGA_ONE_PRINTED = frozenset({
    "Aether Spellbomb","Codex Shredder","Giant's Boulder","Grafdigger's Cage",
    "Hope of Ghirapur","Mana Vault","Manifold Key","Pithing Needle",
    "Sensei's Divining Top","Sol Ring","Vexing Bauble","Voltaic Key",
})
SAGA_TARGETS = frozenset(SAGA_ZERO_PRINTED | SAGA_ONE_PRINTED)
ACTION_CAP = 80
BOTTOM_CAP = 8

BLUE_NONARTIFACT_FRONT = {c for c,(g,u) in COST.items() if u>0 and c not in ARTIFACTS and c not in TRUE_LAND_CARDS and c!=COMMANDER}
BLUE_NONARTIFACT_FRONT |= {
    "An Offer You Can't Refuse","Fierce Guardianship","Flusterstorm","Force of Negation","Force of Will",
    "Mana Drain","Mental Misstep","Mindbreak Trap","Pact of Negation","Swan Song",
    "Chain of Vapor","Banishing Knack","Retraction Helix","Dramatic Reversal","Dizzy Spell",
    "Merchant Scroll","Mystical Tutor","Muddle the Mixture","Reshape","Transmute Artifact","Whir of Invention",
    "Scour for Scrap","Gitaxian Probe","Sink into Stupor","Sea Gate Restoration","Hydroelectric Specimen"
}

@lru_cache(maxsize=None)
def mana_value(card:str)->int:
    # True land cards have mana value 0. MDFCs use the front face in zones other
    # than the battlefield/stack, so they are handled by explicit overrides below.
    if card in TRUE_LAND_CARDS:
        return 0
    overrides={
        "Gitaxian Probe":1,
        "Mental Misstep":1,
        "Everflowing Chalice":0,   # X is 0 off the stack; multikicker does not alter MV.
        "Reshape":2,               # X=0 off the stack.
        "Whir of Invention":3,     # X=0 off the stack.
        "Sea Gate Restoration":7,
        "Hydroelectric Specimen":3,
        "Sink into Stupor":3,
    }
    if card in overrides:
        return overrides[card]
    if card in COST:
        return sum(COST[card])
    return 99


INTERACTION_CARDS = {
    "Chain of Vapor","Banishing Knack","Retraction Helix","Otawara, Soaring City",
    "Aether Spellbomb",
    "An Offer You Can't Refuse","Fierce Guardianship","Flusterstorm","Force of Negation",
    "Force of Will","Mana Drain","Mental Misstep","Mindbreak Trap","Pact of Negation",
    "Swan Song",
    "Pithing Needle","Disruptor Flute","Grafdigger's Cage","Vexing Bauble","Defense Grid",
}

def refresh_observability(s):
    seen=set(s.interaction_seen)
    seen.update(c for c in s.hand if c in INTERACTION_CARDS)
    seen.update(p.name for p in s.battlefield if p.name in INTERACTION_CARDS)
    return replace(s,interaction_seen=tuple(sorted(seen))) if tuple(sorted(seen))!=s.interaction_seen else s


# ----------------------------- State ---------------------------------------

@dataclass(frozen=True)
class Perm:
    name: str
    tapped: bool = False
    sick: bool = False
    counters: int = 0
    mode: str = ""     # e.g. chip_attached, skerry, saga etc.

@dataclass(frozen=True)
class State:
    turn: int
    library: Tuple[str,...]
    hand: Tuple[str,...]
    battlefield: Tuple[Perm,...]
    graveyard: Tuple[str,...] = ()
    exile: Tuple[str,...] = ()
    blue: int = 0
    colorless: int = 0
    land_played: bool = False
    drain_bank: int = 0
    bauble_draws: int = 0
    remora_age: int = 0
    ring_counters: int = 0
    ftt_level: int = 1
    uthros_counters: int = 0
    urza: bool = False
    construct: bool = False
    top_access: bool = False
    chip_attached: bool = False
    chip_target: str = ""
    spell_cast_this_turn: bool = False
    knack_target: str = ""
    pa_target: str = ""
    vfc_pumps: int = 0
    urza_cast_turn: int = 0
    commander_in_command_zone: bool = True
    commander_casts_from_zone: int = 0
    interaction_seen: Tuple[str,...] = ()
    won: bool = False
    win_family: str = ""
    trace: Tuple[str,...] = ()

    def key(self):
        # Preserve exact shuffled/top-access states without storing the full tuple twice in the key.
        libp = (self.library[:10], hash(self.library))
        bf = tuple(sorted((p.name,p.tapped,p.sick,p.counters,p.mode) for p in self.battlefield))
        return (self.turn, tuple(sorted(self.hand)), bf, self.blue, self.colorless,
                self.land_played,self.drain_bank,self.bauble_draws,self.ring_counters,self.ftt_level,self.uthros_counters,
                self.urza,self.construct,self.top_access,self.chip_attached,self.chip_target,
                self.spell_cast_this_turn,self.knack_target,self.pa_target,self.vfc_pumps,
                self.commander_in_command_zone,self.commander_casts_from_zone,
                libp,self.won,self.win_family)

def add_trace(s:State, msg:str)->State:
    return replace(s, trace=s.trace+(msg,))

def bf_names(s): return [p.name for p in s.battlefield]
def bf_name_set(s): return frozenset(p.name for p in s.battlefield)
def has(s,name): return any(p.name==name for p in s.battlefield)
def count_bf(s,name): return sum(p.name==name for p in s.battlefield)

def update_perm(s:State, idx:int, **kwargs)->State:
    b=list(s.battlefield); b[idx]=replace(b[idx],**kwargs); return replace(s,battlefield=tuple(b))

def remove_perm(s:State, idx:int, to_grave=True)->State:
    b=list(s.battlefield); p=b.pop(idx)
    # Commander leaves battlefield:
    # - graveyard-bound events choose the command-zone option;
    # - bounce leaves it outside command zone so the caller may put it in hand.
    if p.name==COMMANDER:
        gy=s.graveyard
        s=replace(
            s,battlefield=tuple(b),graveyard=gy,urza=False,
            commander_in_command_zone=(True if to_grave else False)
        )
    else:
        gy=s.graveyard+(p.name,) if to_grave and p.name not in {"Clue","Treasure","Construct"} and p.mode!="chrome_copy" else s.graveyard
        s=replace(s,battlefield=tuple(b),graveyard=gy)
    if p.name=="Power Artifact": s=replace(s,pa_target="")
    if p.name=="Fortune Teller's Talent": s=replace(s,ftt_level=1)
    if p.name=="Uthros Research Craft": s=replace(s,uthros_counters=0)
    if p.name=="The One Ring": s=replace(s,ring_counters=0)
    if p.name=="The Reality Chip": s=replace(s,chip_attached=False,chip_target="")
    if s.chip_attached and s.chip_target and p.name==s.chip_target:
        s=replace(s,chip_attached=False,chip_target="")
        for ci,cp in enumerate(s.battlefield):
            if cp.name=="The Reality Chip":
                s=update_perm(s,ci,mode="")
                break
    if s.pa_target and p.name==s.pa_target:
        # enchanted artifact left; Aura is put into graveyard as a state-based action
        pb=list(s.battlefield)
        for j in range(len(pb)-1,-1,-1):
            if pb[j].name=="Power Artifact":
                pb.pop(j); s=replace(s,battlefield=tuple(pb),graveyard=s.graveyard+("Power Artifact",),pa_target=""); break
    if p.name=="Sewer-veillance Cam":
        s=cam_untap_best(s,"LTB")
    if p.name=="Prized Statue" and to_grave:
        s=add_perm(s,"Treasure",mode="treasure")
        s=artifact_etb_triggers(s,"Treasure")
        s=add_trace(s,"Prized Statue put into graveyard from battlefield -> Treasure")
    return s

def add_perm(s:State,name:str,tapped=False,sick=False,counters=0,mode="")->State:
    return replace(s,battlefield=s.battlefield+(Perm(name,tapped,sick,counters,mode),))


def card_priority(s:State, card:str)->float:
    """Only uses the identities the player is entitled to know from a scry."""
    if card==COMMANDER: return 95
    if card in {"Grinding Station","The Reality Chip","Uthros Research Craft","The One Ring","Chrome Dome","Spellseeker"}: return 85
    if card in {"Forensic Gadgeteer","Battered Golem","Fortune Teller's Talent","Power Artifact","Basalt Monolith","Grim Monolith"}: return 75
    if card in FETCHES: return 70 if (s.chip_attached or s.ftt_level>=2) else 55
    if card in ALL_LANDS: return 60 if not s.land_played else 20
    if card in ZERO_ARTIFACTS: return 67
    if card in ONE_ARTIFACTS: return 58
    if card in ARTIFACTS: return 50
    if card in {"Transmute Artifact","Reshape","Whir of Invention","Dizzy Spell","Muddle the Mixture","Mystical Tutor","Merchant Scroll"}: return 72
    if card in {"Gitaxian Probe","Dramatic Reversal","Scour for Scrap"}: return 55
    return 30

def apply_scry(s:State,n:int,label:str)->State:
    n=min(n,len(s.library))
    if n<=0: return s
    seen=list(s.library[:n]); rest=list(s.library[n:])
    # Keep only reasonably useful seen cards, best first; bottom the others.
    kept=sorted([c for c in seen if card_priority(s,c)>=45], key=lambda c:-card_priority(s,c))
    bottom=[c for c in seen if c not in kept]
    lib=tuple(kept+rest+bottom)
    return add_trace(replace(s,library=lib),f"{label}: scry {n} ({', '.join(seen)})")

def shuffled_library(s:State,salt:str)->Tuple[str,...]:
    lib=list(s.library)
    h=hashlib.sha256((salt+'|'+str(s.turn)+'|'+str(len(s.trace))+'|'+repr(lib)).encode()).digest()
    rng=random.Random(int.from_bytes(h[:8],'big'))
    rng.shuffle(lib)
    return tuple(lib)

def is_artifact_perm(p:Perm)->bool:
    return p.name in F_ARTIFACTS or p.mode in {"clue","construct","treasure","chrome_copy","chrome_copy_preturn"}

def is_creature_perm(p:Perm)->bool:
    if p.mode=="landface": return False
    if p.name=="The Reality Chip" and p.mode=="chip_attached":
        return False
    return p.name in F_CREATURES or p.name==COMMANDER or p.mode=="construct"

def creature_power(s:State,p:Perm)->int:
    if p.mode=="construct": return max(1,artifact_count(s))
    base={COMMANDER:1,"Artificer's Assistant":1,"Battered Golem":3,"Faerie Mastermind":2,
            "Forensic Gadgeteer":2,"Hope of Ghirapur":1,"Spellseeker":1,"Spellskite":0,
            "Valley Floodcaller":2,"Hydroelectric Specimen":1}.get(p.name,1)
    if p.name in {"Valley Floodcaller","Artificer's Assistant"}: base += s.vfc_pumps
    return base

def vfc_noncreature_cast_trigger(s:State, card:str)->State:
    if not has(s,"Valley Floodcaller"): return s
    s=replace(s,vfc_pumps=s.vfc_pumps+1)
    b=list(s.battlefield); changed=[]
    for i,p in enumerate(b):
        if p.name in {"Valley Floodcaller","Artificer's Assistant"} and p.tapped:
            b[i]=replace(p,tapped=False); changed.append(p.name)
    if changed:
        s=replace(s,battlefield=tuple(b)); s=add_trace(s,"VFC noncreature cast untaps "+", ".join(changed))
    return s

def cam_untap_best(s:State,label:str)->State:
    # Prefer restoring the creature carrying Knack/Helix; otherwise turn a tapped
    # artifact creature directly into +U through Urza, per the user's speed model.
    if s.knack_target:
        for i,p in enumerate(s.battlefield):
            if p.name==s.knack_target and p.tapped:
                return add_trace(update_perm(s,i,tapped=False),f"Cam {label} untaps Knack target {p.name}")
    if s.urza:
        for i,p in enumerate(s.battlefield):
            if p.tapped and is_artifact_perm(p) and is_creature_perm(p):
                ns=replace(s,blue=s.blue+1)  # untap then immediately tap through Urza
                return add_trace(ns,f"Cam {label} untaps {p.name}; Urza converts it to +U")
    for i,p in enumerate(s.battlefield):
        if p.tapped and is_creature_perm(p):
            return add_trace(update_perm(s,i,tapped=False),f"Cam {label} untaps {p.name}")
    return s

# ----------------------------- Mana ----------------------------------------

def medallion_reduction(s:State, card:str)->int:
    if has(s,"Sapphire Medallion") and card not in ALL_LANDS:
        # all spells in this deck are blue iff COST blue >0; reduce generic only.
        if COST.get(card,(0,0))[1] > 0:
            return 1
    return 0

def can_pay(s:State, generic:int, blue_req:int)->bool:
    if s.blue < blue_req: return False
    rem_blue=s.blue-blue_req
    return rem_blue+s.colorless >= generic

def pay(s:State,generic:int,blue_req:int)->Optional[State]:
    if not can_pay(s,generic,blue_req): return None
    b=s.blue-blue_req; c=s.colorless
    use_c=min(c,generic); c-=use_c; generic-=use_c
    b-=generic
    return replace(s,blue=b,colorless=c)

@lru_cache(maxsize=None)
def base_spell_cost(card:str):
    return COST.get(card,(99,99))

def spell_cost(s:State,card:str,outside:bool=False):
    g,b=base_spell_cost(card)
    g=max(0,g-medallion_reduction(s,card))
    if outside and s.ftt_level>=3:
        g=max(0,g-2)
    return g,b

def x_generic_cost(s:State,card:str,x:int,outside:bool=False)->int:
    """Generic X portion after legal generic spell-cost reductions."""
    reduction=medallion_reduction(s,card)
    if outside and s.ftt_level>=3:
        reduction += 2
    return max(0,x-reduction)

def artifact_count(s):
    return sum(is_artifact_perm(p) for p in s.battlefield)

def tap_artifact_for_urza_actions(s:State)->List[State]:
    if not s.urza: return []
    out=[]
    for i,p in enumerate(s.battlefield):
        if not p.tapped and is_artifact_perm(p):
            ns=update_perm(s,i,tapped=True)
            ns=replace(ns,blue=ns.blue+1)
            out.append(add_trace(ns,f"Urza taps {p.name or p.mode}: +U"))
    return out

def intrinsic_mana_actions(s:State)->List[State]:
    out=[]; metal=artifact_count(s)>=3
    for i,p in enumerate(s.battlefield):
        if p.tapped: continue
        n=p.name
        if n=="Island" or n in {"Cephalid Coliseum","Ipnu Rivulet","Minamo, School at Water's Edge",
                                "Oboro, Palace in the Clouds","Otawara, Soaring City"}:
            ns=update_perm(s,i,tapped=True); ns=replace(ns,blue=ns.blue+1)
            out.append(add_trace(ns,f"tap {n}: +U"))
        elif n in MDFC_BLUE_LANDS:
            ns=update_perm(s,i,tapped=True); ns=replace(ns,blue=ns.blue+1)
            out.append(add_trace(ns,f"tap {n} land face: +U"))
        elif n=="Seat of the Synod":
            ns=update_perm(s,i,tapped=True); ns=replace(ns,blue=ns.blue+1); out.append(add_trace(ns,"tap Seat: +U"))
        elif n=="Urza's Saga" and p.counters>=1:
            ns=update_perm(s,i,tapped=True); ns=replace(ns,colorless=ns.colorless+1); out.append(add_trace(ns,"tap Saga: +C"))
        elif n=="Ancient Tomb":
            ns=update_perm(s,i,tapped=True); ns=replace(ns,colorless=ns.colorless+2); out.append(add_trace(ns,"tap Ancient Tomb: +CC"))
        elif n=="City of Traitors":
            ns=update_perm(s,i,tapped=True); ns=replace(ns,colorless=ns.colorless+2); out.append(add_trace(ns,"tap City: +CC"))
        elif n=="Crystal Vein":
            ns=update_perm(s,i,tapped=True); ns=replace(ns,colorless=ns.colorless+1); out.append(add_trace(ns,"tap Crystal Vein: +C"))
            ns2=remove_perm(s,i); ns2=replace(ns2,colorless=ns2.colorless+2); out.append(add_trace(ns2,"sac Crystal Vein: +CC"))
        elif n=="Saprazzan Skerry" and p.counters>0:
            ns=update_perm(s,i,tapped=True,counters=p.counters-1); ns=replace(ns,blue=ns.blue+2)
            if p.counters-1==0:
                # same permanent remains at this index
                ns=remove_perm(ns,i)
            out.append(add_trace(ns,"tap Skerry: +UU"))
        elif n=="Gemstone Caverns":
            ns=update_perm(s,i,tapped=True); ns=replace(ns,blue=ns.blue+1) if p.mode=="luck" else replace(ns,colorless=ns.colorless+1); out.append(add_trace(ns,"tap Caverns"))
        elif n=="Sol Ring":
            ns=update_perm(s,i,tapped=True); ns=replace(ns,colorless=ns.colorless+2); out.append(add_trace(ns,"tap Sol Ring: +CC"))
        elif n in {"Mana Vault","Grim Monolith","Basalt Monolith"}:
            ns=update_perm(s,i,tapped=True); ns=replace(ns,colorless=ns.colorless+3); out.append(add_trace(ns,f"tap {n}: +CCC"))
        elif n=="Mox Opal" and metal:
            ns=update_perm(s,i,tapped=True); ns=replace(ns,blue=ns.blue+1); out.append(add_trace(ns,"tap Mox Opal: +U"))
        elif n in {"Chrome Mox","Mox Diamond"} and p.mode in {"imprinted","diamond"}:
            ns=update_perm(s,i,tapped=True); ns=replace(ns,blue=ns.blue+1); out.append(add_trace(ns,f"tap {n}: +U"))
        elif n=="Everflowing Chalice" and p.counters>0:
            ns=update_perm(s,i,tapped=True)
            ns=replace(ns,colorless=ns.colorless+p.counters)
            out.append(add_trace(ns,f"tap Everflowing Chalice ({p.counters} charge) -> +{p.counters}C"))
        elif n=="Lotus Petal":
            ns=remove_perm(s,i); ns=replace(ns,blue=ns.blue+1); out.append(add_trace(ns,"sac Lotus Petal: +U"))
        elif p.mode=="treasure":
            ns=remove_perm(s,i,to_grave=False); ns=replace(ns,blue=ns.blue+1); out.append(add_trace(ns,"tap+sac Treasure: +U"))
    return out

# ------------------------ Artifact entry/cast triggers ----------------------

def untap_named_once(s:State,name:str)->State:
    b=list(s.battlefield)
    for i,p in enumerate(b):
        if p.name==name and p.tapped:
            b[i]=replace(p,tapped=False); break
    return replace(s,battlefield=tuple(b))

def artifact_etb_triggers(s:State, entered:str)->State:
    # Tezzeret gets loyalty for every artifact ETB, including tokens.
    b=list(s.battlefield)
    for i,p in enumerate(b):
        if p.name=="Tezzeret, Cruel Captain": b[i]=replace(p,counters=p.counters+1)
    s=replace(s,battlefield=tuple(b))
    # User-requested producer simplification with exact pre/post-trigger tapping:
    # if untapped, tap before trigger and after it -> +UU; if tapped -> +U.
    if s.urza:
        b=list(s.battlefield); gain=0
        for i,p in enumerate(b):
            if p.name in {"Grinding Station","Battered Golem"}:
                gain += 1 if p.tapped else 2
                b[i]=replace(p,tapped=True)
        if gain:
            s=replace(s,battlefield=tuple(b),blue=s.blue+gain)
            s=add_trace(s,f"producer ETB mana from {entered}: +{gain}U")
    else:
        for n in ("Grinding Station","Battered Golem"):
            if has(s,n): s=untap_named_once(s,n)
    if entered in {"Giant's Boulder","Witching Well"}:
        s=apply_scry(s,2,entered)
    if entered=="Sewer-veillance Cam":
        s=cam_untap_best(s,"ETB")
    if entered=="Prized Statue":
        s=add_perm(s,"Treasure",mode="treasure")
        s=artifact_etb_triggers(s,"Treasure")
        s=add_trace(s,"Prized Statue ETB -> Treasure")
    return s

def artifact_cast_triggers(s:State, card:str)->State:
    """
    Resolve our simultaneous cast triggers in a strategically favorable legal order:
      1) VFC noncreature-cast trigger,
      2) every Artificer's Assistant scry (so they can improve an Uthros draw),
      3) Uthros draw if active,
      4) every Gadgeteer investigate trigger.
    Gadget Clue ETBs and the original artifact ETB then independently trigger every
    Grinding Station / Battered Golem in artifact_etb_triggers.
    """
    if card not in CREATURES:
        s=vfc_noncreature_cast_trigger(s,card)

    assistants=count_bf(s,"Artificer's Assistant")
    for k in range(assistants):
        s=apply_scry(s,1,f"Artificer's Assistant trigger {k+1}/{assistants}")

    if has(s,"Uthros Research Craft") and s.uthros_counters>=3 and s.library:
        s=replace(s,hand=s.hand+(s.library[0],),library=s.library[1:],
                  uthros_counters=s.uthros_counters+1)
        s=add_trace(s,"Uthros trigger: draw 1 before artifact resolves; +1 station counter")

    gadgets=count_bf(s,"Forensic Gadgeteer")
    for k in range(gadgets):
        s=add_perm(s,"Clue",mode="clue")
        s=artifact_etb_triggers(s,"Clue")
        s=add_trace(s,f"Gadgeteer trigger {k+1}/{gadgets} -> Clue")
    return s

def remove_one(tup:Tuple[str,...], card:str)->Tuple[str,...]:
    x=list(tup); x.remove(card); return tuple(x)


def chalice_cast_variants(s:State, outside:bool=False, free:bool=False)->List[State]:
    if "Everflowing Chalice" not in s.hand:
        return []
    pool=s.blue+s.colorless
    reduction=2 if (outside and s.ftt_level>=3) else 0
    max_k=min(8,max(0,(pool+reduction)//2))
    out=[]
    for k in range(max_k+1):
        generic=max(0,2*k-reduction)
        ps=pay(s,generic,0)
        if ps is None:
            continue
        ns=replace(ps,hand=remove_one(ps.hand,"Everflowing Chalice"),
                   spell_cast_this_turn=True)
        ns=artifact_cast_triggers(ns,"Everflowing Chalice")
        if has(ns,"Vexing Bauble") and generic==0:
            ns=replace(ns,graveyard=ns.graveyard+("Everflowing Chalice",))
            out.append(add_trace(ns,f"cast Everflowing Chalice kicked {k}x; no mana spent -> Vexing Bauble counters"))
            continue
        ns=add_perm(ns,"Everflowing Chalice",counters=k)
        ns=artifact_etb_triggers(ns,"Everflowing Chalice")
        out.append(add_trace(check_win(ns),f"cast Everflowing Chalice kicked {k}x -> {k} charge counter(s)"))
    return out


def cast_from_hand(s:State,card:str,outside:bool=False,free:bool=False)->Optional[State]:
    if card not in s.hand: return None
    if card in ALL_LANDS and card not in MDFC_BLUE_LANDS: return None
    if card in {"Chrome Mox","Mox Diamond","Everflowing Chalice"}: return None  # special branching actions
    g,b=spell_cost(s,card,outside=outside)
    ps=s if free else pay(s,g,b)
    if ps is None: return None
    s=replace(ps,hand=remove_one(ps.hand,card),spell_cast_this_turn=True)
    if card in ARTIFACTS:
        s=artifact_cast_triggers(s,card)
        if has(s,"Vexing Bauble") and (0 if free else g+b)==0:
            s=replace(s,graveyard=s.graveyard+(card,))
            return add_trace(s,f"Vexing Bauble counters zero-mana cast {card}")
        s=add_perm(s,card,sick=card in CREATURES)
        if card=="Uthros Research Craft": s=replace(s,uthros_counters=0)
        if card=="The One Ring": s=replace(s,ring_counters=0)
        s=artifact_etb_triggers(s,card)
        s=add_trace(s,f"cast {card}")
        return check_win(s)
    if card==COMMANDER:
        if has(s,"Artificer's Assistant"): s=apply_scry(s,1,"Artificer's Assistant (legendary cast)")
        s=vfc_noncreature_cast_trigger(s,card) if False else s
        s=add_perm(s,COMMANDER,sick=True); s=replace(
            s,urza=True,construct=True,commander_in_command_zone=False,
            urza_cast_turn=(s.urza_cast_turn or s.turn)
        )
        s=add_perm(s,"Construct",sick=True,mode="construct"); s=artifact_etb_triggers(s,"Construct")
        return check_win(add_trace(s,"cast Urza -> Construct"))
    if card in CREATURES or card=="Hydroelectric Specimen":
        s=add_perm(s,card,sick=True); return check_win(add_trace(s,f"cast {card}"))
    if card in {"Mystic Remora","Rhystic Study","Fortune Teller's Talent"}:
        s=add_perm(s,card)
        if card=="Fortune Teller's Talent": s=replace(s,ftt_level=1)
        return check_win(add_trace(s,f"cast {card}"))
    if card=="Tezzeret, Cruel Captain":
        if has(s,"Artificer's Assistant"): s=apply_scry(s,1,"Artificer's Assistant (legendary cast)")
        s=vfc_noncreature_cast_trigger(s,card)
        s=add_perm(s,card,counters=4,mode="tez_ready"); return add_trace(s,"cast Tezzeret (4 loyalty)")
    if card=="Gitaxian Probe":
        s=vfc_noncreature_cast_trigger(s,card)
        if has(s,"Vexing Bauble"):
            if s.blue>=1:
                s=replace(s,blue=s.blue-1)
            else:
                return add_trace(replace(s,graveyard=s.graveyard+(card,)),"Probe cast for life; Vexing Bauble counters it")
        if s.library: s=replace(s,hand=s.hand+(s.library[0],),library=s.library[1:])
        return add_trace(s,"Probe targets an opponent -> draw 1")
    if card=="Dramatic Reversal":
        s=vfc_noncreature_cast_trigger(s,card)
        b=[]
        for p in s.battlefield:
            b.append(p if p.name in F_ALL_LANDS else replace(p,tapped=False))
        return add_trace(replace(s,battlefield=tuple(b)),"Dramatic Reversal untaps all nonlands")
    if card=="Mana Drain":
        s=vfc_noncreature_cast_trigger(s,card)
        return add_trace(replace(s,drain_bank=s.drain_bank+2),"Mana Drain assumption: bank +2 next turn")
    if card=="Sea Gate Restoration":
        s=vfc_noncreature_cast_trigger(s,card)
        n=min(len(s.hand)+1,len(s.library)); return add_trace(replace(s,hand=s.hand+s.library[:n],library=s.library[n:]),f"Sea Gate Restoration draws {n}")
    if card=="Sink into Stupor":
        s=vfc_noncreature_cast_trigger(s,card)
        return add_trace(s,"cast Sink into Stupor (opponent target assumed)")
    return None

def play_land(s:State,card:str)->Optional[State]:
    if s.land_played or card not in s.hand or card not in ALL_LANDS: return None
    b=list(s.battlefield); gy=list(s.graveyard); city_bonus=0
    if card!="City of Traitors":
        for i in reversed(range(len(b))):
            if b[i].name=="City of Traitors":
                # Playing another land triggers City. If it was untapped, tap it for CC in response, then sacrifice.
                if not b[i].tapped: city_bonus += 2
                gy.append("City of Traitors"); b.pop(i)
    s=replace(s,hand=remove_one(s.hand,card),battlefield=tuple(b),graveyard=tuple(gy),land_played=True,colorless=s.colorless+city_bonus)
    tapped=card=="Saprazzan Skerry"; counters=2 if card=="Saprazzan Skerry" else (1 if card=="Urza's Saga" else 0)
    s=add_perm(s,card,tapped=tapped,counters=counters,mode="landface" if card in MDFC_BLUE_LANDS else "")
    if card=="Seat of the Synod": s=artifact_etb_triggers(s,card)
    msg=f"play land {card}" + (" (back face)" if card in MDFC_BLUE_LANDS else "") + ("; City trigger -> +CC then sacrifice" if city_bonus else "")
    return add_trace(s,msg)

# --------------------------- Draw/card engines ------------------------------

def clue_draw_actions(s:State)->List[State]:
    out=[]
    reduction=1 if has(s,"Forensic Gadgeteer") else 0
    cost=max(1,2-reduction)
    for i,p in enumerate(s.battlefield):
        if p.mode=="clue" and can_pay(s,cost,0):
            ns=pay(s,cost,0); ns=remove_perm(ns,i)
            if ns.library: ns=replace(ns,hand=ns.hand+(ns.library[0],),library=ns.library[1:])
            out.append(add_trace(ns,"sac Clue -> draw"))
    return out

def ring_actions(s:State)->List[State]:
    out=[]
    for i,p in enumerate(s.battlefield):
        if p.name=="The One Ring" and not p.tapped:
            ns=update_perm(s,i,tapped=True)
            k=ns.ring_counters+1
            draw=min(k,len(ns.library))
            ns=replace(ns,ring_counters=k,hand=ns.hand+ns.library[:draw],library=ns.library[draw:])
            out.append(add_trace(ns,f"Ring draws {draw}"))
    return out

def top_actions(s:State)->List[State]:
    out=[]
    for i,p in enumerate(s.battlefield):
        if p.name=="Sensei's Divining Top":
            if can_pay(s,1,0) and len(s.library)>=2:
                ps=pay(s,1,0); n=min(3,len(ps.library)); top=ps.library[:n]; rest=ps.library[n:]
                for perm in set(itertools.permutations(top)):
                    out.append(add_trace(replace(ps,library=tuple(perm)+rest),"Top reorder"))
            if not p.tapped and s.library:
                ns=remove_perm(s,i,to_grave=False); drawn=ns.library[0]
                # Correct Oracle sequencing: draw, then put Top itself on TOP.
                lib=("Sensei's Divining Top",)+ns.library[1:]
                ns=replace(ns,hand=ns.hand+(drawn,),library=lib)
                out.append(add_trace(ns,"Top: draw 1, Top goes on top"))
    return out

def assistant_scry_actions(s:State)->List[State]:
    # v0.2 incorrectly allowed free repeated scries. Assistant is now handled only
    # as a cast trigger in artifact_cast_triggers / historic spell handling.
    return []


def cage_in_play(s:State)->bool:
    return has(s,"Grafdigger's Cage")

def cage_blocks_library_cast(s:State, card:str)->bool:
    return cage_in_play(s) and card not in ALL_LANDS

def cage_blocks_library_battlefield_entry(s:State, card:str)->bool:
    return cage_in_play(s) and card in CREATURES

def chip_ftt_top_casts(s:State)->List[State]:
    chip_active = s.chip_attached
    ftt_active = (s.ftt_level>=2 and s.spell_cast_this_turn)
    if not (chip_active or ftt_active) or not s.library:
        return []

    card=s.library[0]
    out=[]

    if card in ALL_LANDS and not s.land_played:
        ns=replace(s,library=s.library[1:],hand=s.hand+(card,))
        pl=play_land(ns,card)
        if pl:
            out.append(add_trace(pl,"top access: play land from library"))
        return out

    if card not in ALL_LANDS:
        if cage_blocks_library_cast(s,card):
            return out
        ns=replace(s,library=s.library[1:],hand=s.hand+(card,))
        src="Chip" if chip_active else "FTT"
        if card=="Everflowing Chalice":
            for cs in chalice_cast_variants(ns,outside=True,free=False):
                out.append(add_trace(cs,f"{src}: cast Chalice from top"))
        else:
            cs=cast_from_hand(ns,card,outside=True)
            if cs:
                out.append(add_trace(cs,f"{src}: cast {card} from top"))
    return out

# ----------------------------- Tutors --------------------------------------


def move_library_to_hand(s:State, card:str)->State:
    """
    Remove exactly one named card from the library and put it into hand.
    Search/tutor callers are responsible for any required shuffle/top placement.
    """
    lib=list(s.library)
    if card not in lib:
        return s
    lib.remove(card)
    return replace(s,library=tuple(lib),hand=s.hand+(card,))

def tutor_targets(s:State, kind:str)->Iterable[str]:
    pool=set(s.library)
    if kind=="dizzy":
        return sorted(x for x in pool if mana_value(x)==1)
    if kind=="muddle":
        return sorted(x for x in pool if mana_value(x)==2)
    if kind=="spellseeker":
        return sorted(x for x in pool if x in (INSTANTS|SORCERIES) and mana_value(x)<=2)
    if kind=="mystical":
        return sorted(x for x in pool if x in (INSTANTS|SORCERIES))
    if kind=="merchant":
        # Every instant in this mono-blue deck is a blue instant card.
        return sorted(x for x in pool if x in INSTANTS)
    return []

def simple_tutor_actions(s:State)->List[State]:
    out=[]
    # transmute Dizzy: 1UU
    for card,kind,cost in [("Dizzy Spell","dizzy",(1,2)),("Muddle the Mixture","muddle",(1,2)),
                           ("Merchant Scroll","merchant",(1,1))]:
        if card in s.hand and can_pay(s,*cost):
            ps=pay(s,*cost); ps=replace(ps,hand=remove_one(ps.hand,card),graveyard=ps.graveyard+(card,))
            if card=="Merchant Scroll": ps=vfc_noncreature_cast_trigger(ps,card)
            for t in tutor_targets(ps,kind):
                ns=move_library_to_hand(ps,t)
                ns=replace(ns,library=shuffled_library(ns,f"{card}:{t}"))
                out.append(add_trace(ns,f"{card} -> {t}"))
    if "Mystical Tutor" in s.hand and can_pay(s,0,1):
        ps=pay(s,0,1); ps=replace(ps,hand=remove_one(ps.hand,"Mystical Tutor"),graveyard=ps.graveyard+("Mystical Tutor",))
        ps=vfc_noncreature_cast_trigger(ps,"Mystical Tutor")
        for t in tutor_targets(ps,"mystical"):
            lib=list(ps.library); lib.remove(t)
            ns=replace(ps,library=tuple(lib))
            shuffled=shuffled_library(ns,"mystical:"+t)
            ns=replace(ns,library=(t,)+tuple(shuffled))
            out.append(add_trace(ns,f"Mystical -> shuffle, then top {t}"))
    # Spellseeker ETB tutor represented whenever Seeker exists and was just cast is hard to track;
    # allow one tutor per Seeker object via mode marker.
    for i,p in enumerate(s.battlefield):
        if p.name=="Spellseeker" and p.mode!="used":
            for t in tutor_targets(s,"spellseeker"):
                ns=move_library_to_hand(s,t); ns=update_perm(ns,i,mode="used")
                ns=replace(ns,library=shuffled_library(ns,"spellseeker:"+t))
                out.append(add_trace(ns,f"Spellseeker ETB -> {t}"))
    return out

def artifact_tutor_actions(s:State)->List[State]:
    out=[]
    artifacts=[x for x in set(s.library) if x in ARTIFACTS]

    # Transmute Artifact: {U}{U}, sacrifice an artifact, search any artifact.
    # If target MV exceeds sacrificed MV, you may pay the difference. If you do
    # not, the searched card goes to the graveyard. The library is shuffled.
    if "Transmute Artifact" in s.hand and can_pay(s,0,2):
        base=pay(s,0,2)
        base=replace(
            base,
            hand=remove_one(base.hand,"Transmute Artifact"),
            graveyard=base.graveyard+("Transmute Artifact",),
            spell_cast_this_turn=True
        )
        base=vfc_noncreature_cast_trigger(base,"Transmute Artifact")

        for i,p in enumerate(base.battlefield):
            if is_artifact_perm(p):
                sac_mv=0 if p.mode in {"clue","construct","treasure","chrome_copy","chrome_copy_preturn"} else mana_value(p.name)
                b2=remove_perm(base,i)

                for t in artifacts:
                    mv=mana_value(t)
                    diff=max(0,mv-sac_mv)

                    # Search removes target, then shuffle regardless of payment choice.
                    lib=list(b2.library); lib.remove(t)
                    searched=replace(b2,library=tuple(lib))
                    shuffled=shuffled_library(searched,f"transmute:{p.name}:{t}")

                    if diff==0 or can_pay(b2,diff,0):
                        ns=b2 if diff==0 else pay(b2,diff,0)
                        lib2=list(ns.library); lib2.remove(t)
                        ns=replace(ns,library=tuple(lib2))
                        ns=replace(ns,library=shuffled_library(ns,f"transmute-paid:{p.name}:{t}"))
                        ns=add_perm(ns,t,sick=t in CREATURES)
                        ns=artifact_etb_triggers(ns,t)
                        out.append(add_trace(check_win(ns),f"Transmute {p.name}->{t}; pay difference {diff}"))

                    if diff>0:
                        # Legal choice to decline the difference even if mana is available.
                        ns=replace(searched,graveyard=searched.graveyard+(t,),library=tuple(shuffled))
                        out.append(add_trace(ns,f"Transmute {p.name}->{t}; decline {diff}, target to graveyard"))

    # Reshape: XUU + sacrifice artifact. Search artifact MV <= X.
    # Sapphire Medallion reduces the generic X portion by 1.
    if "Reshape" in s.hand and can_pay(s,0,2):
        reshape_red=medallion_reduction(s,"Reshape")
        for i,p in enumerate(s.battlefield):
            if is_artifact_perm(p):
                b0=pay(s,0,2)
                b0=replace(
                    b0,hand=remove_one(b0.hand,"Reshape"),
                    graveyard=b0.graveyard+("Reshape",),spell_cast_this_turn=True
                )
                b0=vfc_noncreature_cast_trigger(b0,"Reshape")
                b0=remove_perm(b0,i)

                for t in artifacts:
                    x=mana_value(t)
                    generic=max(0,x-reshape_red)
                    if can_pay(b0,generic,0):
                        ns=pay(b0,generic,0)
                        lib=list(ns.library); lib.remove(t)
                        ns=replace(ns,library=tuple(lib))
                        ns=replace(ns,library=shuffled_library(ns,"reshape:"+t))
                        ns=add_perm(ns,t,sick=t in CREATURES)
                        ns=artifact_etb_triggers(ns,t)
                        out.append(add_trace(check_win(ns),f"Reshape X={x}->{t}; generic paid {generic}"))

    # Whir: XUUU with improvise. Sapphire Medallion reduces generic X by 1.
    if "Whir of Invention" in s.hand and s.blue>=3:
        whir_red=medallion_reduction(s,"Whir of Invention")
        base=replace(
            s,blue=s.blue-3,hand=remove_one(s.hand,"Whir of Invention"),
            graveyard=s.graveyard+("Whir of Invention",),spell_cast_this_turn=True
        )
        base=vfc_noncreature_cast_trigger(base,"Whir of Invention")
        untapped_art=sum(1 for p in base.battlefield if not p.tapped and is_artifact_perm(p))
        generic_pool=base.colorless+base.blue+untapped_art

        for t in artifacts:
            x=mana_value(t)
            need=max(0,x-whir_red)
            if need<=generic_pool:
                ns=base
                use=min(ns.colorless,need); ns=replace(ns,colorless=ns.colorless-use); need-=use
                use=min(ns.blue,need); ns=replace(ns,blue=ns.blue-use); need-=use

                if need:
                    b=list(ns.battlefield)
                    for j,p in enumerate(b):
                        if need and not p.tapped and is_artifact_perm(p):
                            b[j]=replace(p,tapped=True); need-=1
                    ns=replace(ns,battlefield=tuple(b))

                if need==0:
                    lib=list(ns.library); lib.remove(t)
                    ns=replace(ns,library=tuple(lib))
                    ns=replace(ns,library=shuffled_library(ns,"whir:"+t))
                    ns=add_perm(ns,t,sick=t in CREATURES)
                    ns=artifact_etb_triggers(ns,t)
                    out.append(add_trace(check_win(ns),f"Whir X={x}->{t}"))
    return out


def power_artifact_actions(s:State)->List[State]:
    out=[]
    if "Power Artifact" not in s.hand: return out
    g,b=spell_cost(s,"Power Artifact")
    if not can_pay(s,g,b): return out
    for p in s.battlefield:
        if is_artifact_perm(p):
            ns=pay(s,g,b); ns=replace(ns,hand=remove_one(ns.hand,"Power Artifact"),spell_cast_this_turn=True)
            ns=vfc_noncreature_cast_trigger(ns,"Power Artifact")
            if has(ns,"Artificer's Assistant"): ns=apply_scry(ns,1,"Artificer's Assistant (Power Artifact)")
            ns=add_perm(ns,"Power Artifact"); ns=replace(ns,pa_target=p.name)
            out.append(add_trace(check_win(ns),f"Power Artifact enchants {p.name or p.mode}"))
    return out

def chrome_dome_actions(s:State)->List[State]:
    out=[]
    if not has(s,"Chrome Dome"): return out
    g=5
    if has(s,"Forensic Gadgeteer"): g=max(1,g-1)
    if s.pa_target=="Chrome Dome": g=max(1,g-2)
    if not can_pay(s,g,0): return out
    useful={"Grinding Station","Battered Golem","Mana Vault","Grim Monolith","Basalt Monolith","Sol Ring","Voltaic Key","Manifold Key","Forensic Gadgeteer","Prized Statue"}
    for p in s.battlefield:
        if p.name=="Chrome Dome" or p.name not in useful: continue
        ns=pay(s,g,0); ns=add_perm(ns,p.name,sick=False,mode="chrome_copy"); ns=artifact_etb_triggers(ns,p.name)
        out.append(add_trace(check_win(ns),f"Chrome Dome copies {p.name} (haste)"))
    return out

def draw_sac_actions(s:State)->List[State]:
    out=[]
    for i,p in enumerate(s.battlefield):
        n=p.name

        # Aether Spellbomb: {1}, sacrifice -> draw 1. No tap symbol.
        if n=="Aether Spellbomb" and can_pay(s,1,0):
            ns=pay(s,1,0); ns=remove_perm(ns,i)
            if ns.library:
                ns=replace(ns,hand=ns.hand+(ns.library[0],),library=ns.library[1:])
            out.append(add_trace(ns,"Aether Spellbomb: pay 1, sacrifice -> draw 1"))

        # Witching Well: 3U, sacrifice -> draw 2. No tap symbol.
        elif n=="Witching Well" and can_pay(s,3,1):
            ns=pay(s,3,1); ns=remove_perm(ns,i)
            d=min(2,len(ns.library))
            ns=replace(ns,hand=ns.hand+ns.library[:d],library=ns.library[d:])
            out.append(add_trace(ns,f"Witching Well: pay 3U, sacrifice -> draw {d}"))

        # Sewer-veillance Cam: 3U, sacrifice -> draw 2. No tap symbol.
        # Leaving the battlefield also untaps a target creature.
        elif n=="Sewer-veillance Cam" and can_pay(s,3,1):
            # remove_perm() resolves Cam's LTB untap exactly once via cam_untap_best().
            base=pay(s,3,1); base=remove_perm(base,i)
            d=min(2,len(base.library))
            base=replace(base,hand=base.hand+base.library[:d],library=base.library[d:])
            out.append(add_trace(base,f"Cam: pay 3U, sacrifice -> draw {d}"))

        # Vexing Bauble: 1, T, sacrifice -> draw 1.
        elif n=="Vexing Bauble" and not p.tapped and can_pay(s,1,0):
            ns=pay(s,1,0); ns=remove_perm(ns,i)
            if ns.library:
                ns=replace(ns,hand=ns.hand+(ns.library[0],),library=ns.library[1:])
            out.append(add_trace(ns,"Vexing Bauble: pay 1, tap+sacrifice -> draw 1"))

        # Mishra's / Urza's Bauble: T, sacrifice -> delayed next-upkeep draw.
        elif n in {"Mishra's Bauble","Urza's Bauble"} and not p.tapped:
            ns=remove_perm(s,i); ns=replace(ns,bauble_draws=ns.bauble_draws+1)
            out.append(add_trace(ns,f"{n}: tap+sacrifice -> delayed next-upkeep draw"))

        # Welding Jar: sacrifice only. No tap/mana cost.
        elif n=="Welding Jar":
            ns=remove_perm(s,i)
            out.append(add_trace(ns,"Welding Jar: sacrifice for free (recursion/setup)"))
    return out

def mox_cast_actions(s:State)->List[State]:
    out=[]
    if "Chrome Mox" in s.hand:
        # Artifact cast triggers happen even if we choose no imprint.
        base=replace(s,hand=remove_one(s.hand,"Chrome Mox"),spell_cast_this_turn=True)
        base=artifact_cast_triggers(base,"Chrome Mox")
        if has(base,"Vexing Bauble"):
            base=replace(base,graveyard=base.graveyard+("Chrome Mox",)); out.append(add_trace(base,"Vexing Bauble counters Chrome Mox after cast triggers")); base=None
        if base is not None:
            base=add_perm(base,"Chrome Mox"); base=artifact_etb_triggers(base,"Chrome Mox")
            out.append(add_trace(base,"cast Chrome Mox, no imprint"))
        if base is not None:
          for c in sorted(set(s.hand)-{"Chrome Mox"}):
            if c in BLUE_NONARTIFACT_FRONT:
                ns=replace(base,hand=remove_one(base.hand,c),exile=base.exile+(c,))
                # mark the newly entered Chrome Mox as imprinted
                for j in range(len(ns.battlefield)-1,-1,-1):
                    if ns.battlefield[j].name=="Chrome Mox": ns=update_perm(ns,j,mode="imprinted"); break
                out.append(add_trace(ns,f"Chrome Mox imprints {c}"))
    if "Mox Diamond" in s.hand:
        # No land discard: spell was still cast but Diamond never enters.
        no=replace(s,hand=remove_one(s.hand,"Mox Diamond"),graveyard=s.graveyard+("Mox Diamond",),spell_cast_this_turn=True)
        no=artifact_cast_triggers(no,"Mox Diamond"); out.append(add_trace(no,"cast Mox Diamond, decline/cannot discard land -> graveyard"))
        if not has(s,"Vexing Bauble"):
          for c in sorted(set(s.hand)-{"Mox Diamond"}):
            if c in TRUE_LAND_CARDS:
                ns=replace(s,hand=remove_one(remove_one(s.hand,"Mox Diamond"),c),graveyard=s.graveyard+(c,),spell_cast_this_turn=True)
                ns=artifact_cast_triggers(ns,"Mox Diamond")
                if has(ns,"Vexing Bauble"):
                    ns=replace(ns,graveyard=ns.graveyard+("Mox Diamond",)); out.append(add_trace(ns,f"Mox Diamond discards {c}; Vexing Bauble counters spell"))
                else:
                    ns=add_perm(ns,"Mox Diamond",mode="diamond"); ns=artifact_etb_triggers(ns,"Mox Diamond"); out.append(add_trace(ns,f"Mox Diamond discards true land card {c}"))
    return out

def fetch_actions(s:State)->List[State]:
    out=[]
    for i,p in enumerate(s.battlefield):
        if p.name in FETCHES and "Island" in s.library:
            ns=remove_perm(s,i); lib=list(ns.library); lib.remove("Island"); ns=replace(ns,library=tuple(lib)); ns=add_perm(ns,"Island")
            ns=replace(ns,library=shuffled_library(ns,"fetch:"+p.name))
            out.append(add_trace(ns,f"{p.name} fetches Island and shuffles"))
    return out

def oboro_minamo_actions(s:State)->List[State]:
    out=[]
    # Oboro can tap for U separately, then spend generic to bounce, replay as land, tap again.
    for i,p in enumerate(s.battlefield):
        if p.name=="Oboro, Palace in the Clouds" and can_pay(s,1,0):
            ns=pay(s,1,0); ns=remove_perm(ns,i,to_grave=False); ns=replace(ns,hand=ns.hand+("Oboro, Palace in the Clouds",))
            out.append(add_trace(ns,"Oboro: pay 1 -> return to hand"))
    for i,p in enumerate(s.battlefield):
        if p.name=="Minamo, School at Water's Edge" and not p.tapped and can_pay(s,0,1):
            for j,t in enumerate(s.battlefield):
                if j==i or t.tapped is False: continue
                if t.name in {COMMANDER,"The One Ring","The Reality Chip","Tezzeret, Cruel Captain"}:
                    ns=pay(s,0,1); ns=update_perm(ns,i,tapped=True); ns=update_perm(ns,j,tapped=False)
                    out.append(add_trace(ns,f"Minamo untaps {t.name}"))
    return out

def producer_native_actions(s:State)->List[State]:
    out=[]
    # Boulder converts generic -> blue before Urza.
    for i,p in enumerate(s.battlefield):
        if p.name=="Giant's Boulder" and not p.tapped and can_pay(s,1,0):
            ns=pay(s,1,0); ns=update_perm(ns,i,tapped=True); ns=replace(ns,blue=ns.blue+1)
            out.append(add_trace(ns,"Giant's Boulder filters 1 -> U"))
    # Codex self-mill clears a brick from Chip/FTT top.
    if s.chip_attached or s.ftt_level>=2:
        for i,p in enumerate(s.battlefield):
            if p.name=="Codex Shredder" and not p.tapped and s.library:
                ns=update_perm(s,i,tapped=True); ns=replace(ns,graveyard=ns.graveyard+(ns.library[0],),library=ns.library[1:])
                out.append(add_trace(ns,"Codex mills our top card"))
            if p.name=="Grinding Station" and not p.tapped and s.library:
                for j,a in enumerate(s.battlefield):
                    if j!=i and is_artifact_perm(a):
                        ns=update_perm(s,i,tapped=True); ns=remove_perm(ns,j if j<i else j)
                        n=min(3,len(ns.library)); ns=replace(ns,graveyard=ns.graveyard+ns.library[:n],library=ns.library[n:])
                        out.append(add_trace(ns,f"Grinding Station sacs {a.name or a.mode}, self-mill {n}"))
                        break
    # Jeweled Amulet banks either blue or colorless one turn and releases it later.
    for i,p in enumerate(s.battlefield):
        if p.name=="Jeweled Amulet" and not p.tapped:
            if p.counters==0:
                if s.blue>=1:
                    ns=replace(s,blue=s.blue-1); ns=update_perm(ns,i,tapped=True,counters=1,mode="amulet_blue"); out.append(add_trace(ns,"Jeweled Amulet stores U"))
                if s.colorless>=1:
                    ns=replace(s,colorless=s.colorless-1); ns=update_perm(ns,i,tapped=True,counters=1,mode="amulet_c"); out.append(add_trace(ns,"Jeweled Amulet stores C"))
            elif p.counters>0:
                ns=update_perm(s,i,tapped=True,counters=0); ns=replace(ns,blue=ns.blue+1) if p.mode=="amulet_blue" else replace(ns,colorless=ns.colorless+1); out.append(add_trace(ns,"Jeweled Amulet releases stored mana"))
    # Moonsnare taps itself plus another untapped artifact/creature for C; useful pre-Urza filtering/acceleration.
    for i,p in enumerate(s.battlefield):
        if p.name=="Moonsnare Prototype" and not p.tapped:
            for j,q in enumerate(s.battlefield):
                if j!=i and not q.tapped and (is_artifact_perm(q) or is_creature_perm(q)):
                    ns=update_perm(s,i,tapped=True); ns=update_perm(ns,j,tapped=True); ns=replace(ns,colorless=ns.colorless+1); out.append(add_trace(ns,f"Moonsnare taps {q.name or q.mode}: +C"))
    # Native Monolith untaps (Gadget/Power Artifact reductions apply to their actual target).
    for i,p in enumerate(s.battlefield):
        if p.name in {"Grim Monolith","Basalt Monolith"} and p.tapped:
            g=4 if p.name=="Grim Monolith" else 3
            if has(s,"Forensic Gadgeteer"): g=max(1,g-1)
            if s.pa_target==p.name: g=max(1,g-2)
            if can_pay(s,g,0):
                ns=pay(s,g,0); ns=update_perm(ns,i,tapped=False); out.append(add_trace(ns,f"pay {g} to untap {p.name}"))
    # Codex recursion: target must already be in graveyard before Codex is sacrificed.
    for i,p in enumerate(s.battlefield):
        if p.name=="Codex Shredder" and not p.tapped:
            g=5-(1 if has(s,"Forensic Gadgeteer") else 0)-(2 if s.pa_target=="Codex Shredder" else 0); g=max(1,g)
            if can_pay(s,g,0):
                for target in sorted(set(s.graveyard)-{"Codex Shredder"}):
                    ns=pay(s,g,0); ns=remove_perm(ns,i); gy=list(ns.graveyard);
                    if target in gy:
                        gy.remove(target); ns=replace(ns,graveyard=tuple(gy),hand=ns.hand+(target,)); out.append(add_trace(ns,f"Codex returns {target}"))

    if has(s,"Grafdigger's Cage"):
        for i,p in enumerate(s.battlefield):
            if p.name=="Grinding Station" and not p.tapped:
                cage_idx=next((j for j,q in enumerate(s.battlefield) if q.name=="Grafdigger's Cage"),None)
                if cage_idx is not None and cage_idx!=i:
                    ns=update_perm(s,i,tapped=True)
                    ns=remove_perm(ns,cage_idx,to_grave=True)
                    m=min(3,len(ns.library))
                    milled=ns.library[:m]
                    ns=replace(ns,library=ns.library[m:],graveyard=ns.graveyard+milled)
                    out.append(add_trace(ns,f"Grinding Station: sac Grafdigger's Cage to unlock library; self-mill {m}"))

    return out

def top_key_combo_actions(s:State)->List[State]:
    out=[]
    topi=next((i for i,p in enumerate(s.battlefield) if p.name=="Sensei's Divining Top" and not p.tapped),None)
    if topi is None or not s.library: return out
    for ki,k in enumerate(s.battlefield):
        if k.name in {"Voltaic Key","Manifold Key"} and not k.tapped and can_pay(s,1,0):
            # A1 Top draw on stack; Key untaps; A2 Top draw. Resolve A2 then A1:
            # draw underlying card, put Top on top; then draw Top. End with both in hand.
            ns=pay(s,1,0); ns=update_perm(ns,ki,tapped=True)
            drawn=ns.library[0]; ns=remove_perm(ns,topi if topi<ki else topi,to_grave=False)
            ns=replace(ns,hand=ns.hand+(drawn,"Sensei's Divining Top"),library=ns.library[1:])
            out.append(add_trace(ns,f"Top + {k.name}: double activation draws {drawn} and returns Top to hand"))
    return out

def uthros_station_actions(s:State)->List[State]:
    out=[]
    if not has(s,"Uthros Research Craft"): return out
    for i,p in enumerate(s.battlefield):
        if not p.tapped and is_creature_perm(p) and p.name!="Uthros Research Craft":
            power=creature_power(s,p)
            if power>0:
                ns=update_perm(s,i,tapped=True); ns=replace(ns,uthros_counters=ns.uthros_counters+power)
                out.append(add_trace(ns,f"Uthros stations {p.name or p.mode} for {power} counters -> {ns.uthros_counters}"))
    return out

def tezzeret_actions(s:State)->List[State]:
    out=[]
    for i,p in enumerate(s.battlefield):
        if p.name!="Tezzeret, Cruel Captain" or p.mode=="tez_used": continue
        # 0: untap artifact or creature
        for j,t in enumerate(s.battlefield):
            if j!=i and t.tapped and (is_artifact_perm(t) or is_creature_perm(t)):
                ns=update_perm(s,j,tapped=False); ns=update_perm(ns,i,mode="tez_used")
                out.append(add_trace(ns,f"Tezzeret 0 untaps {t.name or t.mode}"))
        # -3: MV <=1 artifact to hand, then shuffle
        if p.counters>=3:
            for target in sorted(set(s.library) & ARTIFACTS):
                if mana_value(target)<=1:
                    ns=move_library_to_hand(s,target); ns=update_perm(ns,i,counters=p.counters-3,mode="tez_used")
                    ns=replace(ns,library=shuffled_library(ns,"tezz:"+target))
                    out.append(add_trace(ns,f"Tezzeret -3 -> {target}"))
    return out

def saga_actions(s:State)->List[State]:
    out=[]
    for i,p in enumerate(s.battlefield):
        if p.name=="Urza's Saga" and p.counters>=2 and not p.tapped and can_pay(s,2,0):
            ns=pay(s,2,0); ns=update_perm(ns,i,tapped=True); ns=add_perm(ns,"Construct",sick=True,mode="construct"); ns=artifact_etb_triggers(ns,"Construct")
            out.append(add_trace(ns,"Saga II ability -> Construct"))
        if p.name=="Urza's Saga" and p.mode=="saga3":
            for target in sorted(set(s.library)&SAGA_TARGETS):
                ns=remove_perm(s,i); lib=list(ns.library); lib.remove(target); ns=replace(ns,library=tuple(lib)); ns=add_perm(ns,target,sick=target in CREATURES); ns=artifact_etb_triggers(ns,target); ns=replace(ns,library=shuffled_library(ns,"saga:"+target))
                out.append(add_trace(check_win(ns),f"Saga III puts {target} onto battlefield"))
    return out

def repurposing_bay_actions(s:State)->List[State]:
    out=[]
    for bi,bay in enumerate(s.battlefield):
        if bay.name!="Repurposing Bay" or bay.tapped: continue
        g=2
        if has(s,"Forensic Gadgeteer"): g=max(1,g-1)
        if s.pa_target=="Repurposing Bay": g=max(1,g-2)
        if not can_pay(s,g,0): continue
        for ai,a in enumerate(s.battlefield):
            if ai==bi or not is_artifact_perm(a): continue
            sacmv=0 if a.mode in {"clue","construct","treasure","chrome_copy","chrome_copy_preturn"} else mana_value(a.name)
            targetmv=sacmv+1
            targets=[x for x in set(s.library) if x in ARTIFACTS and mana_value(x)==targetmv]
            if not targets: continue
            ns0=pay(s,g,0); ns0=update_perm(ns0,bi,tapped=True)
            # index remains valid after Bay tap; sacrifice other artifact
            ns0=remove_perm(ns0,ai)
            for target in targets:
                ns=ns0; lib=list(ns.library); lib.remove(target); ns=replace(ns,library=tuple(lib)); ns=add_perm(ns,target,sick=target in CREATURES); ns=artifact_etb_triggers(ns,target); ns=replace(ns,library=shuffled_library(ns,"bay:"+target))
                out.append(add_trace(check_win(ns),f"Repurposing Bay sacs {a.name or a.mode} -> {target}"))
    return out

def scour_actions(s:State)->List[State]:
    out=[]
    if "Scour for Scrap" not in s.hand: return out
    g,b=spell_cost(s,"Scour for Scrap")
    if not can_pay(s,g,b): return out
    artifacts_lib=sorted(set(s.library)&ARTIFACTS)
    artifacts_gy=sorted(set(s.graveyard)&ARTIFACTS)
    ps=pay(s,g,b); ps=replace(ps,hand=remove_one(ps.hand,"Scour for Scrap"),graveyard=ps.graveyard+("Scour for Scrap",),spell_cast_this_turn=True); ps=vfc_noncreature_cast_trigger(ps,"Scour for Scrap")
    # choose one or both modes; both is normally dominant but retain individual branches.
    for t in artifacts_lib:
        ns=move_library_to_hand(ps,t); ns=replace(ns,library=shuffled_library(ns,"scour:"+t)); out.append(add_trace(ns,f"Scour tutors {t}"))
    for gcard in artifacts_gy:
        gy=list(ps.graveyard); gy.remove(gcard); ns=replace(ps,graveyard=tuple(gy),hand=ps.hand+(gcard,)); out.append(add_trace(ns,f"Scour returns {gcard} from graveyard"))
    for t in artifacts_lib:
        for gcard in artifacts_gy:
            ns=move_library_to_hand(ps,t); gy=list(ns.graveyard); gy.remove(gcard); ns=replace(ns,graveyard=tuple(gy),hand=ns.hand+(gcard,),library=shuffled_library(ns,"scourboth:"+t+gcard)); out.append(add_trace(ns,f"Scour tutors {t} + returns {gcard}"))
    return out

def offer_actions(s:State)->List[State]:
    out=[]; offer="An Offer You Can't Refuse"
    if offer not in s.hand: return out
    # Counter our own castable noncreature spell; its cast triggers still happen.
    for card in sorted(set(s.hand)-{offer}):
        if card in ALL_LANDS or card in CREATURES or card in {COMMANDER,"Hydroelectric Specimen"}: continue
        g,b=spell_cost(s,card)
        if not can_pay(s,g,b): continue
        first=pay(s,g,b)
        if first is None: continue
        first=replace(first,hand=remove_one(first.hand,card),spell_cast_this_turn=True)
        if card in ARTIFACTS: first=artifact_cast_triggers(first,card)
        elif card not in CREATURES: first=vfc_noncreature_cast_trigger(first,card)
        if not can_pay(first,0,1): continue
        ns=pay(first,0,1); ns=replace(ns,hand=remove_one(ns.hand,offer),graveyard=ns.graveyard+(card,offer)); ns=vfc_noncreature_cast_trigger(ns,offer)
        ns=add_perm(ns,"Treasure",mode="treasure"); ns=artifact_etb_triggers(ns,"Treasure")
        ns=add_perm(ns,"Treasure",mode="treasure"); ns=artifact_etb_triggers(ns,"Treasure")
        out.append(add_trace(ns,f"Offer counters our {card} -> two Treasures"))
    return out



_CHAIN_RESULT_CACHE = {}

def _chain_card_plan_value(s:State, name:str)->float:
    v=0.0
    if name=="Sewer-veillance Cam": v+=34
    if name=="Prized Statue": v+=30
    if name=="Spellseeker": v+=28
    if name=="Witching Well": v+=23
    if name=="The One Ring": v+=21
    if name=="Chrome Dome": v+=19
    if name in {"Mana Vault","Grim Monolith"}: v+=19
    if name=="Basalt Monolith": v+=17
    if name=="Sol Ring": v+=15
    if name=="Sensei's Divining Top": v+=15
    if name=="Grafdigger's Cage": v+=(18 if (s.chip_attached or s.ftt_level>=2) else 3)
    if name=="Grinding Station": v+=11
    if name=="Battered Golem": v+=10
    if name in {"Forensic Gadgeteer","Uthros Research Craft"}: v+=10
    if name=="The Reality Chip": v+=8
    if name=="Pithing Needle": v+=2
    if name=="Power Artifact": v-=8
    if name in F_ARTIFACTS: v+=4
    return v

def _chain_land_sac_penalty(name:str)->float:
    if name=="Ancient Tomb": return 14
    if name=="Urza's Saga": return 11
    if name=="Saprazzan Skerry": return 9
    if name=="Minamo, School at Water's Edge": return 9
    if name=="City of Traitors": return 7
    if name=="Oboro, Palace in the Clouds": return 7
    if name=="Seat of the Synod": return 6
    if name=="Crystal Vein": return 4
    if name in FETCHES: return 3
    if name=="Island": return 5
    return 5

def _chain_apply_plan(base:State, bounce_names:Tuple[str,...], land_names:Tuple[str,...],
                      order_mode:str="canonical")->Optional[State]:
    ns=base
    order=list(bounce_names)
    if order_mode=="cam_first" and "Sewer-veillance Cam" in order:
        order.remove("Sewer-veillance Cam"); order.insert(0,"Sewer-veillance Cam")
    elif order_mode=="cam_last" and "Sewer-veillance Cam" in order:
        order.remove("Sewer-veillance Cam"); order.append("Sewer-veillance Cam")
    elif order_mode=="pa_first" and "Power Artifact" in order:
        order.remove("Power Artifact"); order.insert(0,"Power Artifact")
    elif order_mode=="pa_target_first" and ns.pa_target and ns.pa_target in order:
        order.remove(ns.pa_target); order.insert(0,ns.pa_target)
    else:
        order=sorted(order)

    lands_order=sorted(land_names)

    for copy_no,name in enumerate(order,1):
        idx=next((i for i,p in enumerate(ns.battlefield) if p.name==name),None)
        if idx is None:
            continue
        ns=remove_perm(ns,idx,to_grave=False)
        ns=replace(ns,hand=ns.hand+(name,))
        ns=add_trace(ns,f"Chain resolution {copy_no}: bounce {name}")

        if copy_no<=len(lands_order):
            lname=lands_order[copy_no-1]
            li=next((i for i,p in enumerate(ns.battlefield) if p.name==lname),None)
            if li is None:
                return None
            ns=remove_perm(ns,li,to_grave=True)
            ns=add_trace(ns,f"Chain: sacrifice {lname} to create copy {copy_no+1}")
    return ns

def _top_scored_subsets(items, choose_n, value_fn, cap, must_include=()):
    """
    Return a diverse top-N subset list without crossing it with another dimension.
    Always preserve subsets containing strategically special requested elements.
    """
    if choose_n==0:
        return [tuple()]
    if choose_n<0 or choose_n>len(items):
        return []

    heap=[]
    forced={}
    serial=0
    for subset in itertools.combinations(items,choose_n):
        sc=sum(value_fn(x) for x in subset)
        item=(sc,serial,subset); serial+=1

        if len(heap)<cap:
            heapq.heappush(heap,item)
        elif sc>heap[0][0]:
            heapq.heapreplace(heap,item)

        if any(x in subset for x in must_include):
            # Keep a bounded collection of special-containing subsets too.
            old=forced.get(subset)
            if old is None or sc>old:
                forced[subset]=sc

    vals=[x[2] for x in heap]
    # Add best forced special variants, bounded to cap extra.
    if forced:
        extra=sorted(forced.items(),key=lambda kv:kv[1],reverse=True)[:cap]
        vals.extend(sub for sub,_ in extra)

    # stable dedup
    seen=set(); out=[]
    for sub in vals:
        if sub not in seen:
            seen.add(sub); out.append(sub)
    return out

def _chain_cache_key(s:State):
    """
    Strategic cache key for Chain macro generation.
    Trace/history is intentionally excluded.
    """
    bf=tuple(sorted((p.name,p.tapped,p.sick,p.counters,p.mode) for p in s.battlefield))
    return (
        bf,tuple(sorted(s.hand)),s.blue,s.colorless,s.land_played,
        s.ftt_level,s.uthros_counters,s.urza,s.chip_attached,s.chip_target,
        s.knack_target,s.pa_target,s.spell_cast_this_turn,
        s.library[:10],hash(s.library)
    )

def chain_of_vapor_actions(s:State)->List[State]:
    """
    Two-stage canonical Chain macro.

    Instead of evaluating the full Cartesian product:
        all bounce subsets x all land-sacrifice subsets
    we shortlist each dimension independently PER chain length, then cross only
    those diverse shortlists.

    This preserves:
      * all chain lengths;
      * high-value bounce packages;
      * low-opportunity-cost and unusual land-sacrifice packages;
      * Cam / Cage / PA special packages;
      * exact order-sensitive Cam and PA variants.

    It also memoizes results for strategically identical Chain-live states.
    """
    if "Chain of Vapor" not in s.hand or not can_pay(s,0,1):
        return []

    ck=_chain_cache_key(s)
    cached=_CHAIN_RESULT_CACHE.get(ck)
    if cached is not None:
        # Cached states carry old traces. Rebase only the resulting strategic
        # states onto the current trace so reporting remains coherent.
        rebased=[]
        for st,delta_trace in cached:
            rebased.append(replace(st,trace=s.trace+delta_trace))
        return rebased

    base=pay(s,0,1)
    base=replace(base,hand=remove_one(base.hand,"Chain of Vapor"),
                 graveyard=base.graveyard+("Chain of Vapor",),
                 spell_cast_this_turn=True)
    base=vfc_noncreature_cast_trigger(base,"Chain of Vapor")
    base_trace_len=len(base.trace)

    nonlands=tuple(p.name for p in base.battlefield if p.name not in F_ALL_LANDS)
    lands=tuple(p.name for p in base.battlefield if p.name in F_ALL_LANDS)
    max_k=min(len(nonlands),1+len(lands))
    if max_k<=0:
        return []

    # Much smaller than the previous full subset Cartesian product.
    bounce_cap=max(18,ACTION_CAP//3)
    land_cap=max(8,ACTION_CAP//8)

    special_bounce=(
        "Sewer-veillance Cam","Grafdigger's Cage","Power Artifact",
        base.pa_target if base.pa_target else "__none__",
        "Spellseeker","Prized Statue","The One Ring","Witching Well"
    )
    special_land=("Crystal Vein","City of Traitors","Saprazzan Skerry","Urza's Saga")

    plan_heap=[]
    serial=0

    for k in range(1,max_k+1):
        bsets=_top_scored_subsets(
            nonlands,k,
            lambda n:_chain_card_plan_value(base,n),
            bounce_cap,
            must_include=special_bounce
        )

        # For lands we want MINIMUM sacrifice penalty, so negate penalty.
        lsets=_top_scored_subsets(
            lands,k-1,
            lambda n:-_chain_land_sac_penalty(n),
            land_cap,
            must_include=special_land
        )

        for bset in bsets:
            bvalue=sum(_chain_card_plan_value(base,n) for n in bset)
            artifact_bounces=sum(1 for n in bset if n in F_ARTIFACTS)
            if artifact_bounces>=2 and (
                has(base,"Grinding Station") or has(base,"Battered Golem")
                or has(base,"Uthros Research Craft") or has(base,"Artificer's Assistant")
            ):
                bvalue += 4*(artifact_bounces-1)

            for lset in lsets:
                penalty=sum(_chain_land_sac_penalty(n) for n in lset)
                ps=bvalue-penalty-0.35*(k-1)
                plan_heap.append((ps,serial,bset,lset)); serial+=1

    # Keep a materialization pool modest but substantially > ACTION_CAP.
    materialize_cap=max(ACTION_CAP*4,240)
    plans=heapq.nlargest(min(materialize_cap,len(plan_heap)),plan_heap,key=lambda x:x[0])

    # Force best representative at every chain length even if its cheap score
    # falls outside the global pool.
    best_by_len={}
    for item in plan_heap:
        k=len(item[2])
        if k not in best_by_len or item[0]>best_by_len[k][0]:
            best_by_len[k]=item
    plans.extend(best_by_len.values())

    best={}
    for _,_,bset,lset in plans:
        modes={"canonical"}
        if "Sewer-veillance Cam" in bset:
            modes.update({"cam_first","cam_last"})
        if "Power Artifact" in bset and base.pa_target and base.pa_target in bset:
            modes.update({"pa_first","pa_target_first"})

        for mode in modes:
            st=_chain_apply_plan(base,bset,lset,mode)
            if st is None:
                continue
            k=st.key()
            utility=score(st)+8*len(st.hand)
            old=best.get(k)
            if old is None or utility>old[0]:
                best[k]=(utility,st)

    vals=[v[1] for v in best.values()]
    vals=heapq.nlargest(min(ACTION_CAP,len(vals)),vals,key=lambda st:score(st)+8*len(st.hand))

    # Cache strategic result plus trace delta generated by Chain.
    cached_payload=[]
    for st in vals:
        delta=st.trace[len(s.trace):]
        cached_payload.append((replace(st,trace=()),delta))
    # bounded cache; simple clear is enough for a singleton-card solver
    if len(_CHAIN_RESULT_CACHE)>20000:
        _CHAIN_RESULT_CACHE.clear()
    _CHAIN_RESULT_CACHE[ck]=tuple(cached_payload)

    return vals

def knack_bounce_actions(s:State)->List[State]:
    out=[]
    # Cast Knack/Helix targeting a creature; the effect lasts for this turn.
    for k in KNUCKS:
        if k in s.hand and can_pay(s,*spell_cost(s,k)):
            for p in s.battlefield:
                if is_creature_perm(p):
                    ns=pay(s,*spell_cost(s,k)); ns=replace(ns,hand=remove_one(ns.hand,k),graveyard=ns.graveyard+(k,),knack_target=p.name,spell_cast_this_turn=True)
                    ns=vfc_noncreature_cast_trigger(ns,k)
                    out.append(add_trace(check_win(ns),f"cast {k} targeting {p.name or p.mode}"))
    if s.knack_target:
        ti=next((i for i,p in enumerate(s.battlefield) if p.name==s.knack_target and not p.tapped and not p.sick),None)
        if ti is not None:
            for j,p in enumerate(s.battlefield):
                if j==ti or p.name in F_ALL_LANDS: continue
                ns=update_perm(s,ti,tapped=True); name=p.name
                ns=remove_perm(ns,j if j<ti else j,to_grave=False); ns=replace(ns,hand=ns.hand+(name,))
                out.append(add_trace(ns,f"Knack/Helix target bounces our {name}"))
    return out


def graveyard_land_actions(s:State)->List[State]:
    out=[]

    # Cephalid Coliseum threshold — U, T, sacrifice: draw 3, then discard 3.
    if len(s.graveyard) >= 7:
        for i,p in enumerate(s.battlefield):
            if p.name=="Cephalid Coliseum" and not p.tapped and can_pay(s,0,1):
                ns=pay(s,0,1)
                ns=remove_perm(ns,i,to_grave=True)
                d=min(3,len(ns.library))
                ns=replace(ns,hand=ns.hand+ns.library[:d],library=ns.library[d:])
                if len(ns.hand)>=3:
                    import itertools
                    hand=list(ns.hand)
                    combos=list(itertools.combinations(range(len(hand)),3))
                    # Keep multiple discard choices because graveyard artifacts can
                    # be strategically useful for Scour/Codex recursion.
                    combos.sort(key=lambda inds:sum(card_priority(ns,hand[j]) for j in inds))
                    for inds in combos[:min(12,len(combos))]:
                        drop=set(inds)
                        disc=tuple(hand[j] for j in inds)
                        keep=tuple(c for j,c in enumerate(hand) if j not in drop)
                        st=replace(ns,hand=keep,graveyard=ns.graveyard+disc)
                        out.append(add_trace(st,f"Cephalid Coliseum threshold: draw {d}, discard {', '.join(disc)}"))

    # Ipnu Rivulet — 1U, T, sacrifice a Desert: self-mill 4.
    # Ipnu itself is a Desert, so it may be sacrificed to its own ability.
    for i,p in enumerate(s.battlefield):
        if p.name=="Ipnu Rivulet" and not p.tapped and can_pay(s,1,1):
            ns=pay(s,1,1)
            ns=remove_perm(ns,i,to_grave=True)
            m=min(4,len(ns.library))
            milled=ns.library[:m]
            ns=replace(ns,library=ns.library[m:],graveyard=ns.graveyard+milled)
            out.append(add_trace(ns,f"Ipnu Rivulet self-mill {m}: {', '.join(milled)}"))
    return out



def faerie_mastermind_actions(s:State)->List[State]:
    # 3U: Each player draws a card. Our goldfish-relevant result is draw 1.
    # No tap symbol, so repeated activations are legal if mana permits.
    if not has(s,"Faerie Mastermind") or not can_pay(s,3,1) or not s.library:
        return []
    ns=pay(s,3,1)
    ns=replace(ns,hand=ns.hand+(ns.library[0],),library=ns.library[1:])
    return [add_trace(ns,"Faerie Mastermind: pay 3U -> each player draws; we draw 1")]


# --------------------------- Special activations ----------------------------


def cast_urza_from_command_zone_actions(s:State)->List[State]:
    """
    Cast Urza from the command zone.

    First command-zone cast is {2}{U}{U}; each prior command-zone cast adds {2}.
    Sapphire Medallion's generic reduction is honored through spell_cost().
    If a deterministic infinite-colorless engine is already online, generic
    payment is free but the solver must still have TWO ACTUAL BLUE MANA floating.
    Normal intrinsic mana actions are responsible for tapping lands/Mox/Petal
    first, so no hidden future source is counted here.
    """
    if s.urza or not s.commander_in_command_zone:
        return []

    g,b=spell_cost(s,COMMANDER)
    g += 2*s.commander_casts_from_zone

    if infinite_colorless_online(s):
        # Infinite C covers all generic; UU must already be genuinely floating.
        if s.blue < b:
            return []
        ns=replace(s,blue=s.blue-b)
    else:
        ns=pay(s,g,b)
        if ns is None:
            return []

    ns=replace(
        ns,
        spell_cast_this_turn=True,
        urza=True,
        construct=True,
        commander_in_command_zone=False,
        commander_casts_from_zone=ns.commander_casts_from_zone+1,
        urza_cast_turn=(ns.urza_cast_turn or ns.turn),
    )

    if has(ns,"Artificer's Assistant"):
        ns=apply_scry(ns,1,"Artificer's Assistant (Urza legendary cast)")

    ns=add_perm(ns,COMMANDER,sick=True)
    ns=add_perm(ns,"Construct",sick=True,mode="construct")
    ns=artifact_etb_triggers(ns,"Construct")
    ns=add_trace(
        ns,
        f"cast Urza from command zone -> Construct"
        + (" (infinite colorless paid generic)" if infinite_colorless_online(s) else "")
    )
    return [check_win(ns)]


def special_actions(s:State)->List[State]:
    out=[]
    out += cast_urza_from_command_zone_actions(s)
    out += uthros_station_actions(s)
    out += graveyard_land_actions(s)
    out += faerie_mastermind_actions(s)
    if has(s,"The Reality Chip") and not s.chip_attached:
        g,b=2,1
        if has(s,"Forensic Gadgeteer"): g=max(0,g-1)
        if s.pa_target=="The Reality Chip": g=max(0,g-2)
        if can_pay(s,g,b):
            for p in s.battlefield:
                if is_creature_perm(p) and p.name!="The Reality Chip":
                    ns=replace(pay(s,g,b),chip_attached=True,chip_target=p.name)
                    for ci,cp in enumerate(ns.battlefield):
                        if cp.name=="The Reality Chip":
                            ns=update_perm(ns,ci,mode="chip_attached")
                            break
                    out.append(add_trace(ns,f"reconfigure Reality Chip onto {p.name or p.mode}"))
    if has(s,"Fortune Teller's Talent"):
        if s.ftt_level==1 and can_pay(s,3,1): out.append(add_trace(replace(pay(s,3,1),ftt_level=2),"FTT -> level 2"))
        if s.ftt_level==2 and can_pay(s,2,1): out.append(add_trace(replace(pay(s,2,1),ftt_level=3),"FTT -> level 3"))
    # Real Urza shuffle/reset. Free-cast top card if legal; Vexing Bauble can counter free spell.
    if s.urza and can_pay(s,5,0) and s.library:
        ps=pay(s,5,0); ps=replace(ps,library=shuffled_library(ps,"urza-spin")); card=ps.library[0]
        ns=replace(ps,library=ps.library[1:],exile=ps.exile+(card,))
        if card in ALL_LANDS and not ns.land_played:
            ns=replace(ns,hand=ns.hand+(card,),exile=ns.exile[:-1]); pl=play_land(ns,card)
            if pl: out.append(add_trace(pl,f"Urza spin -> play {card}"))
        elif card not in ALL_LANDS or card in MDFC_BLUE_LANDS:
            ns=replace(ns,hand=ns.hand+(card,),exile=ns.exile[:-1])
            if has(ns,"Vexing Bauble"):
                # Cast still happens (and cast triggers happen) but is countered for no mana spent.
                if card in ARTIFACTS:
                    tr=artifact_cast_triggers(ns,card); tr=replace(tr,hand=remove_one(tr.hand,card),graveyard=tr.graveyard+(card,),spell_cast_this_turn=True)
                    out.append(add_trace(tr,f"Urza spin casts {card}; Vexing Bauble counters it"))
            else:
                if card=="Everflowing Chalice":
                    for cs in chalice_cast_variants(ns,outside=True,free=True):
                        out.append(add_trace(cs,"Urza spin -> free Chalice base cost; optional multikicker paid"))
                else:
                    cs=cast_from_hand(ns,card,outside=True,free=True)
                    if cs: out.append(add_trace(cs,f"Urza spin -> free {card}"))
    # Key generic untap
    for ki,k in enumerate(s.battlefield):
        if k.name in {"Voltaic Key","Manifold Key"} and not k.tapped and can_pay(s,1,0):
            for ti,t in enumerate(s.battlefield):
                if ti!=ki and t.tapped and is_artifact_perm(t):
                    ns=pay(s,1,0); ns=update_perm(ns,ki,tapped=True); ns=update_perm(ns,ti,tapped=False); out.append(add_trace(ns,f"{k.name} untaps {t.name or t.mode}"))
    out += clue_draw_actions(s)+ring_actions(s)+top_actions(s)+power_artifact_actions(s)+chrome_dome_actions(s)
    out += draw_sac_actions(s)+mox_cast_actions(s)+fetch_actions(s)+oboro_minamo_actions(s)
    out += producer_native_actions(s)+top_key_combo_actions(s)+uthros_station_actions(s)+tezzeret_actions(s)+saga_actions(s)
    out += repurposing_bay_actions(s)+scour_actions(s)+offer_actions(s)+chain_of_vapor_actions(s)+knack_bounce_actions(s)
    out += simple_tutor_actions(s)+artifact_tutor_actions(s)+chip_ftt_top_casts(s)
    return out

# -------------------------- Combo detection --------------------------------

def active_creatures(s:State)->set:
    return {p.name for p in s.battlefield if p.name in F_CREATURES|{COMMANDER} and not p.sick}

def zero_or_positive_replay_artifacts(s:State)->set:
    # Conservative profitable replay set; exact iterative economics are searched elsewhere.
    return set(bf_names(s)) & (ZERO_ARTIFACTS|{"Sol Ring","Mana Vault"})


def infinite_colorless_online(s:State)->bool:
    names=bf_name_set(s)
    if "Forensic Gadgeteer" in names and "Basalt Monolith" in names:
        return True
    if "Power Artifact" in names and ("Grim Monolith" in names or "Basalt Monolith" in names):
        return True
    return False

def ftt3_top_preurza_engine(s:State)->bool:
    names=bf_name_set(s)
    return (
        "Sensei's Divining Top" in names
        and s.ftt_level>=3
        and s.spell_cast_this_turn
        and not cage_in_play(s)
    )

def immediately_available_blue_sources(s:State)->int:
    """Count distinct currently usable blue sources, not future land drops."""
    total = s.blue
    metal = artifact_count(s)>=3
    for p in s.battlefield:
        if p.tapped:
            continue
        n=p.name
        if n in {"Island","Cephalid Coliseum","Ipnu Rivulet","Minamo, School at Water's Edge",
                 "Oboro, Palace in the Clouds","Otawara, Soaring City","Seat of the Synod"}:
            total += 1
        elif n in MDFC_BLUE_LANDS:
            total += 1
        elif n=="Gemstone Caverns" and p.mode=="luck":
            total += 1
        elif n in {"Chrome Mox","Mox Diamond"}:
            total += 1
        elif n=="Mox Opal" and metal:
            total += 1
        elif n=="Lotus Petal":
            total += 1
    return total

def can_cast_urza_now_with_infinite_colorless(s:State)->bool:
    # Infinite colorless pays the generic 2; we still need two actual blue.
    return immediately_available_blue_sources(s) >= 2

def check_win(s:State)->State:
    names=bf_name_set(s)

    if not s.urza:
        return s

    if "Power Artifact" in names and "Grim Monolith" in names:
        return replace(s,won=True,win_family="Power Artifact + Grim")
    if "Power Artifact" in names and "Basalt Monolith" in names:
        return replace(s,won=True,win_family="Power Artifact + Basalt")
    if "Forensic Gadgeteer" in names and "Basalt Monolith" in names:
        return replace(s,won=True,win_family="Basalt + Gadgeteer")

    if "Sensei's Divining Top" in names:
        if s.chip_attached and not cage_in_play(s) and names & PRODUCERS:
            return replace(s,won=True,win_family="Top + Reality Chip")
        if s.ftt_level>=3 and s.spell_cast_this_turn and not cage_in_play(s):
            return replace(s,won=True,win_family="Top + FTT L3")
        if s.ftt_level>=2 and s.spell_cast_this_turn and not cage_in_play(s) and names & PRODUCERS:
            return replace(s,won=True,win_family="Top + FTT L2 + producer")
        if "Forensic Gadgeteer" in names and not cage_in_play(s) and names & {"Grinding Station","Battered Golem"}:
            return replace(s,won=True,win_family="Top + Gadgeteer + producer")

    if "Sewer-veillance Cam" in names and s.knack_target:
        target_live=any(
            p.name==s.knack_target and is_creature_perm(p) and not p.sick and not p.tapped
            for p in s.battlefield
        )
        if target_live:
            return replace(s,won=True,win_family="Knack/Helix + Cam")

    if "Chrome Dome" in names and names & {"Grinding Station","Battered Golem"}:
        reduction=(1 if "Forensic Gadgeteer" in names else 0)+(2 if "Power Artifact" in names else 0)
        activation=max(1,5-reduction)
        if s.blue+s.colorless >= activation:
            return replace(s,won=True,win_family="Chrome Dome")
    return s


def dominance_signature(s:State):
    """
    A deliberately conservative signature for cheap dominance pruning.
    States are compared only when board/hand/library-prefix/tapped structure and
    critical engine flags are identical. Within that group, a state with >= blue,
    >= colorless, and >= hand size dominates one with fewer resources.
    """
    bf=tuple(sorted((p.name,p.tapped,p.sick,p.counters,p.mode) for p in s.battlefield))
    return (
        s.turn,bf,tuple(sorted(s.hand)),s.library[:5],
        s.land_played,s.urza,s.ftt_level,s.uthros_counters,
        s.chip_attached,s.chip_target,s.knack_target,s.pa_target,
        s.spell_cast_this_turn,s.commander_in_command_zone,s.commander_casts_from_zone,
        s.won,s.win_family
    )

def dominance_prune(states):
    best={}
    for s in states:
        sig=dominance_signature(s)
        old=best.get(sig)
        if old is None:
            best[sig]=s
            continue
        # Same core state: preserve the version with the stronger immediately
        # spendable resource vector. Score breaks incomparable ties.
        if (s.blue>=old.blue and s.colorless>=old.colorless and len(s.hand)>=len(old.hand)):
            best[sig]=s
        elif not (old.blue>=s.blue and old.colorless>=s.colorless and len(old.hand)>=len(s.hand)):
            if score(s)>score(old):
                best[sig]=s
    return list(best.values())



def classify_action(trace_msg:str)->str:
    m=trace_msg.lower()
    if m.startswith("tap ") or "urza taps" in m or "sac crystal vein" in m or "tap+sac treasure" in m:
        return "mana/tap"
    if "untap" in m:
        return "untap"
    if m.startswith("cast ") or "cast from top" in m:
        return "cast"
    if "tutor" in m or "->" in m and any(x in m for x in ["mystical","spellseeker","transmute","reshape","whir"]):
        return "tutor"
    if "draw" in m or "top " in m:
        return "draw/top"
    if "bounce" in m or "chain" in m:
        return "bounce"
    return "other"



def new_graph_stats():
    return {
        "nodes_expanded":0,
        "edges_generated":0,
        "exact_key_merges":0,
        "cycle_skips":0,
        "dominance_pruned":0,
        "beam_pruned":0,
        "layers":0,
        "max_frontier":0,
        "max_raw_successors":0,
    }

def merge_graph_stats(dst,src):
    for k in dst:
        if k in {"max_frontier","max_raw_successors"}:
            dst[k]=max(dst[k],src.get(k,0))
        else:
            dst[k]+=src.get(k,0)
    return dst

def finalize_graph_stats(g):
    nodes=max(1,g.get("nodes_expanded",0))
    return dict(g,average_branching_factor=g.get("edges_generated",0)/nodes)


# ---------------------------- Beam search ----------------------------------

def score(s:State)->float:
    if s.won: return 1e9 - s.turn*1e6
    names=bf_name_set(s)
    sc=0.0
    # First CA engine gets high value, second lower.
    ca=sum(1 for x in CA_ENGINES if x in names)
    sc += 55 if ca else 0
    sc += max(0,ca-1)*10
    if "Grinding Station" in names: sc+=45
    if "Battered Golem" in names: sc+=30
    if s.urza: sc+=90
    sc += artifact_count(s)*6
    sc += (s.blue+s.colorless)*4
    sc += len(s.hand)*5
    # combo proximity
    if "Chrome Dome" in names and names&{"Grinding Station","Battered Golem"}: sc+=80
    if "Power Artifact" in names and names&{"Grim Monolith","Basalt Monolith"}: sc+=100
    if "Basalt Monolith" in names and "Forensic Gadgeteer" in names: sc+=100
    if "Sensei's Divining Top" in names: sc+=10
    if s.chip_attached: sc+=45
    if s.ftt_level>=2: sc+=35
    if s.uthros_counters>=3: sc+=45
    return sc


_CAP_AUDIT = None

def _action_family_from_state(ns:State)->str:
    """Coarse family label from the action trace's latest transition."""
    if not ns.trace:
        return "unknown"
    x=ns.trace[-1]
    if "Chain" in x: return "chain"
    if "Transmute" in x or "Reshape" in x or "Whir" in x or "Spellseeker ETB" in x or "Mystical" in x or "Merchant Scroll" in x or "Dizzy" in x or "Muddle" in x: return "tutor"
    if "Top" in x or "Sensei's Divining Top" in x: return "top"
    if "untap" in x or "untaps" in x: return "untap"
    if "taps" in x or "+U" in x or "mana" in x: return "mana/tap"
    if "bounce" in x: return "bounce"
    if x.startswith("cast ") or " cast " in x: return "cast"
    if "draw" in x: return "draw"
    if "FTT" in x or "reconfigure" in x or "Urza spin" in x or "Saga" in x: return "engine"
    return "other"

def _record_cap_audit(out, kept, context="normal"):
    global _CAP_AUDIT
    if _CAP_AUDIT is None:
        return
    raw=len(out); kept_n=len(kept); dropped=max(0,raw-kept_n)
    a=_CAP_AUDIT
    a["states_seen"] += 1
    a["raw_actions_total"] += raw
    a["kept_actions_total"] += kept_n
    a["discarded_actions_total"] += dropped
    a["max_pre_cap_actions"] = max(a["max_pre_cap_actions"],raw)
    a["max_kept_actions"] = max(a["max_kept_actions"],kept_n)
    if raw>ACTION_CAP:
        a["states_truncated"] += 1
        a["excess_over_cap_total"] += raw-ACTION_CAP
        a["raw_count_histogram"][str(raw)] += 1
        fam_raw=collections.Counter(_action_family_from_state(x) for x in out)
        fam_kept=collections.Counter(_action_family_from_state(x) for x in kept)
        fam_drop=fam_raw-fam_kept
        a["truncated_raw_families"].update(fam_raw)
        a["truncated_kept_families"].update(fam_kept)
        a["truncated_dropped_families"].update(fam_drop)
        # Retain a handful of worst states for human inspection.
        rec={
            "raw":raw,"kept":kept_n,"dropped":dropped,"context":context,
            "turn":getattr(out[0],"turn",None) if out else None,
            "raw_families":dict(fam_raw),"dropped_families":dict(fam_drop),
            "kept_families":dict(fam_kept),
        }
        a["worst_states"].append(rec)
        a["worst_states"].sort(key=lambda r:r["raw"],reverse=True)
        del a["worst_states"][20:]


_TUTOR_CAP_AUDIT_ENABLED=False
_TUTOR_CAP_AUDIT=None

KNOWN_ENGINE_TARGETS=frozenset({
    "Sensei's Divining Top","The Reality Chip","Fortune Teller's Talent",
    "Forensic Gadgeteer","Grinding Station","Battered Golem",
    "Power Artifact","Grim Monolith","Basalt Monolith","Chrome Dome",
    "Sewer-veillance Cam","Banishing Knack","Retraction Helix",
    "Spellseeker","Transmute Artifact","Reshape","Whir of Invention",
    "Uthros Research Craft","Valley Floodcaller",
})

def new_tutor_cap_audit_stats():
    return {
        "truncated_states":0,
        "tutor_truncated_states":0,
        "raw_tutor_actions":0,
        "kept_tutor_actions":0,
        "unique_targets_raw_total":0,
        "unique_targets_kept_total":0,
        "lost_target_events":0,
        "lost_engine_target_events":0,
        "source_counts_raw":collections.Counter(),
        "source_counts_kept":collections.Counter(),
        "target_counts_raw":collections.Counter(),
        "target_counts_kept":collections.Counter(),
        "lost_targets":collections.Counter(),
        "lost_engine_targets":collections.Counter(),
        "worst_states":[],
    }

def _tutor_source_target_from_trace(st):
    if not st.trace:
        return None,None
    t=st.trace[-1]
    if t.startswith("Transmute ") and "->" in t:
        return "Transmute Artifact",t.split("->",1)[1].split(";",1)[0].strip()
    if t.startswith("Reshape X=") and "->" in t:
        return "Reshape",t.split("->",1)[1].split(";",1)[0].strip()
    if t.startswith("Whir X=") and "->" in t:
        return "Whir of Invention",t.split("->",1)[1].strip()
    if t.startswith("Spellseeker ETB -> "):
        return "Spellseeker",t.split("->",1)[1].strip()
    if t.startswith("Mystical ->"):
        target=t.split("top",1)[1].strip() if "top" in t else t.split("->",1)[1].strip()
        return "Mystical Tutor",target
    for src in ("Dizzy Spell","Muddle the Mixture","Merchant Scroll"):
        if t.startswith(src+" -> "):
            return src,t.split("->",1)[1].strip()
    return None,None

def _record_tutor_cap_state(raw_actions,kept_actions,state,context="normal"):
    global _TUTOR_CAP_AUDIT
    if not _TUTOR_CAP_AUDIT_ENABLED or _TUTOR_CAP_AUDIT is None or len(raw_actions)<=ACTION_CAP:
        return
    aud=_TUTOR_CAP_AUDIT
    aud["truncated_states"]+=1
    raw_pairs=[p for p in (_tutor_source_target_from_trace(a) for a in raw_actions) if p[0] and p[1]]
    kept_pairs=[p for p in (_tutor_source_target_from_trace(a) for a in kept_actions) if p[0] and p[1]]
    if not raw_pairs:
        return
    aud["tutor_truncated_states"]+=1
    aud["raw_tutor_actions"]+=len(raw_pairs)
    aud["kept_tutor_actions"]+=len(kept_pairs)
    for src,tgt in raw_pairs:
        aud["source_counts_raw"][src]+=1; aud["target_counts_raw"][tgt]+=1
    for src,tgt in kept_pairs:
        aud["source_counts_kept"][src]+=1; aud["target_counts_kept"][tgt]+=1

    raw_targets=set(t for _,t in raw_pairs)
    kept_targets=set(t for _,t in kept_pairs)
    lost=raw_targets-kept_targets
    lost_engine=lost & KNOWN_ENGINE_TARGETS

    aud["unique_targets_raw_total"]+=len(raw_targets)
    aud["unique_targets_kept_total"]+=len(kept_targets)
    aud["lost_target_events"]+=len(lost)
    aud["lost_engine_target_events"]+=len(lost_engine)
    for t in lost: aud["lost_targets"][t]+=1
    for t in lost_engine: aud["lost_engine_targets"][t]+=1

    row={
        "turn":state.turn,
        "raw_actions":len(raw_actions),
        "kept_actions":len(kept_actions),
        "raw_tutor_actions":len(raw_pairs),
        "kept_tutor_actions":len(kept_pairs),
        "raw_unique_targets":len(raw_targets),
        "kept_unique_targets":len(kept_targets),
        "lost_targets":sorted(lost),
        "lost_engine_targets":sorted(lost_engine),
        "raw_sources":dict(collections.Counter(src for src,_ in raw_pairs)),
        "kept_sources":dict(collections.Counter(src for src,_ in kept_pairs)),
        "context":context,
    }
    aud["worst_states"].append(row)
    aud["worst_states"]=sorted(
        aud["worst_states"],
        key=lambda r:(len(r["lost_engine_targets"]),len(r["lost_targets"]),
                      r["raw_tutor_actions"]-r["kept_tutor_actions"]),
        reverse=True
    )[:50]


def new_cap_audit_stats():
    return {
        "states_seen":0,"states_truncated":0,
        "raw_actions_total":0,"kept_actions_total":0,"discarded_actions_total":0,
        "excess_over_cap_total":0,"max_pre_cap_actions":0,"max_kept_actions":0,
        "raw_count_histogram":collections.Counter(),
        "truncated_raw_families":collections.Counter(),
        "truncated_kept_families":collections.Counter(),
        "truncated_dropped_families":collections.Counter(),
        "worst_states":[],
    }

def serializable_cap_audit(a):
    out=dict(a)
    for k in ["raw_count_histogram","truncated_raw_families","truncated_kept_families","truncated_dropped_families"]:
        out[k]=dict(a[k])
    out["truncation_rate"]=(a["states_truncated"]/a["states_seen"] if a["states_seen"] else 0.0)
    out["mean_raw_actions"]=(a["raw_actions_total"]/a["states_seen"] if a["states_seen"] else 0.0)
    out["mean_discarded_per_state"]=(a["discarded_actions_total"]/a["states_seen"] if a["states_seen"] else 0.0)
    out["mean_discarded_when_truncated"]=(a["discarded_actions_total"]/a["states_truncated"] if a["states_truncated"] else 0.0)
    return out

def legal_actions(s:State)->List[State]:
    if s.won:
        return []

    # Saga III response/tutor window.
    if any(p.name=="Urza's Saga" and p.mode=="saga3" for p in s.battlefield):
        out=intrinsic_mana_actions(s)+tap_artifact_for_urza_actions(s)+saga_actions(s)+oboro_minamo_actions(s)
        for ki,k in enumerate(s.battlefield):
            if k.name in {"Voltaic Key","Manifold Key"} and not k.tapped and can_pay(s,1,0):
                for ti,x in enumerate(s.battlefield):
                    if ti!=ki and x.tapped and is_artifact_perm(x):
                        ns=pay(s,1,0)
                        ns=update_perm(ns,ki,tapped=True)
                        ns=update_perm(ns,ti,tapped=False)
                        out.append(add_trace(ns,f"{k.name} during Saga III untaps {x.name}"))
        out=[refresh_observability(x) for x in out]
        kept=heapq.nlargest(min(ACTION_CAP,len(out)),out,key=score)
        _record_cap_audit(out,kept,context="saga3")
        _record_tutor_cap_state(out,kept,s,context="saga3")
        return kept

    out=[]
    for c in set(s.hand):
        if c in ALL_LANDS:
            x=play_land(s,c)
            if x:
                out.append(x)

    out += intrinsic_mana_actions(s)
    out += tap_artifact_for_urza_actions(s)
    out += chalice_cast_variants(s)

    special_spells={
        "Dizzy Spell","Muddle the Mixture","Mystical Tutor","Merchant Scroll",
        "Reshape","Transmute Artifact","Whir of Invention","Chain of Vapor",
        "Banishing Knack","Retraction Helix","Chrome Mox","Mox Diamond",
        "Scour for Scrap","An Offer You Can't Refuse","Power Artifact","Everflowing Chalice"
    }
    for c in set(s.hand):
        if (c not in ALL_LANDS or c in MDFC_BLUE_LANDS) and c not in special_spells:
            x=cast_from_hand(s,c)
            if x:
                out.append(x)

    out += special_actions(s)
    out=[refresh_observability(x) for x in out]
    kept=heapq.nlargest(min(ACTION_CAP,len(out)),out,key=score)
    _record_cap_audit(out,kept,context="normal")
    _record_tutor_cap_state(out,kept,s,context="normal")
    return kept

def chrome_activation_cost(s:State)->int:
    g=5
    if has(s,"Forensic Gadgeteer"):
        g=max(1,g-1)
    if s.pa_target=="Chrome Dome":
        g=max(1,g-2)
    return g

def opponent_endstep_mana_capacity(s:State)->int:
    """
    Generic-paying mana available in the opponent-before-us end step from
    permanents that remained untapped through our prior turn.

    Prior-turn floating mana is intentionally excluded. For an artifact with an
    intrinsic tap ability and Urza's tap ability, count only the better use.
    """
    total=0
    metal=artifact_count(s)>=3
    for p in s.battlefield:
        if p.tapped:
            continue
        n=p.name
        if n in {"Island","Cephalid Coliseum","Minamo, School at Water's Edge",
                 "Oboro, Palace in the Clouds","Otawara, Soaring City","Seat of the Synod"}:
            total += 1
        elif n=="Ipnu Rivulet":
            total += 1
        elif n in {"Ancient Tomb","City of Traitors"}:
            total += 2
        elif n=="Crystal Vein":
            total += 1  # do not auto-sacrifice it for this heuristic
        elif n=="Saprazzan Skerry" and p.counters>0:
            total += 2
        elif n=="Gemstone Caverns":
            total += 1
        elif n in MDFC_BLUE_LANDS:
            total += 1
        elif n=="Sol Ring":
            total += 2
        elif n in {"Mana Vault","Grim Monolith","Basalt Monolith"}:
            total += 3
        elif n=="Mox Opal" and metal:
            total += 1
        elif n in {"Chrome Mox","Mox Diamond"} and p.mode in {"imprinted","diamond"}:
            total += 1
        elif is_artifact_perm(p) and s.urza:
            total += 1
    return total

def choose_preturn_chrome_target(s:State):
    priority={
        "Grinding Station":100, "Battered Golem":96,
        "Mana Vault":93, "Grim Monolith":91, "Basalt Monolith":89,
        "Forensic Gadgeteer":86, "Sol Ring":82, "Prized Statue":74,
        "Voltaic Key":70, "Manifold Key":69,
    }
    choices=[p for p in s.battlefield
             if p.name!="Chrome Dome" and is_artifact_perm(p) and p.name in priority]
    return max(choices,key=lambda p:priority[p.name],default=None)

def add_preturn_chrome_copy_if_possible(s:State)->State:
    """
    Model the opponent immediately before us reaching their end step.

    We activate Chrome AFTER that end step has begun. Therefore the delayed
    "next end step" sacrifice cannot trigger in that already-begun step; the token
    survives our upcoming turn and is sacrificed at the beginning of OUR end step.
    """
    if not has(s,"Chrome Dome"):
        return s
    target=choose_preturn_chrome_target(s)
    if target is None:
        return s
    if opponent_endstep_mana_capacity(s) < chrome_activation_cost(s):
        return s

    ns=add_perm(s,target.name,sick=False,mode="chrome_copy_preturn")
    ns=artifact_etb_triggers(ns,target.name)
    return add_trace(ns,f"opponent end step Chrome: copy {target.name}; survives through our next turn")


def end_turn(s:State)->State:
    hand=list(s.hand); lib=list(s.library)
    draws=1+s.bauble_draws
    names=bf_name_set(s)
    # Environmental assumptions requested by user. Remora payment remains a search-audit item.
    if "Mystic Remora" in names: draws += 2
    if "Rhystic Study" in names: draws += 2
    if "Faerie Mastermind" in names: draws += 1
    draws=min(draws,len(lib)); hand += lib[:draws]; lib=lib[draws:]
    # At the beginning of our end step, both Chrome tokens made during our turn
    # and Chrome tokens made in the preceding opponent's end step are sacrificed.
    cur=s
    for i in range(len(cur.battlefield)-1,-1,-1):
        if cur.battlefield[i].mode in {"chrome_copy","chrome_copy_preturn"}:
            cur=remove_perm(cur,i,to_grave=True)
    # Floating mana empties before the later opponent-end-step Chrome window.
    s=replace(cur,blue=0,colorless=0)

    # After intervening opponents, use the end step immediately before our turn.
    # The new token is created after that end step has begun and therefore persists.
    s=add_preturn_chrome_copy_if_possible(s)
    b=[]
    for p in s.battlefield:
        if p.name in {"Mana Vault","Grim Monolith","Basalt Monolith"}: q=replace(p,sick=False)
        else: q=replace(p,tapped=False,sick=False)
        if q.name=="Battered Golem": q=replace(q,tapped=False)  # multiplayer assumption
        if q.name=="Tezzeret, Cruel Captain": q=replace(q,mode="tez_ready")
        if q.name=="Urza's Saga":
            nc=q.counters+1; q=replace(q,counters=nc,mode="saga3" if nc>=3 else q.mode)
        b.append(q)
    ns=replace(s,turn=s.turn+1,library=tuple(lib),hand=tuple(hand),battlefield=tuple(b),
               blue=0,colorless=s.drain_bank,drain_bank=0,bauble_draws=0,land_played=False,
               spell_cast_this_turn=False,knack_target="",vfc_pumps=0)
    ns=refresh_observability(ns)
    return add_trace(ns,f"--- Turn {ns.turn} ---")

def search_hand(deck_order:List[str], keep_n:int, bottom:List[str], max_turn=7,
                beam=2500, max_actions_per_turn=60, caverns_live=True,
                progress_tag:str="", progress_seconds:float=0.0, graph_stats=None)->Tuple[Optional[int],str,Tuple[str,...],int]:
    hand=deck_order[:7]
    rest=deck_order[7:]
    # bottom chosen cards go to bottom in specified order
    for c in bottom:
        hand.remove(c)
    lib=tuple(rest+bottom)
    s=State(turn=1,library=lib,hand=tuple(hand),battlefield=(),trace=("--- Turn 1 ---",))
    # Gemstone Caverns seating is fixed for all mulligan candidates in this game.
    if "Gemstone Caverns" in s.hand and caverns_live and len(s.hand)>1:
        # Exile the lowest-priority non-Caverns card after London bottoming.
        choices=[c for c in s.hand if c!="Gemstone Caverns"]
        ex=min(choices,key=lambda c:card_priority(s,c))
        s=replace(s,hand=remove_one(remove_one(s.hand,"Gemstone Caverns"),ex),exile=s.exile+(ex,))
        s=add_perm(s,"Gemstone Caverns",mode="luck")
        s=add_trace(s,f"pregame Caverns exiles {ex}")
    # commander is command zone, not deck
    # natural draw T1
    if s.library:
        s=replace(s,hand=s.hand+(s.library[0],),library=s.library[1:])
    s=refresh_observability(s)
    states=[s]
    searched=0
    max_depth_reached=0
    if graph_stats is None:
        graph_stats=new_graph_stats()
    _progress_last=time.time()
    _progress_start=_progress_last
    for turn in range(1,max_turn+1):
        frontier=states
        # Exact per-turn transposition table. If an identical strategic state has
        # already been EXPANDED earlier this turn, expanding it again cannot reveal
        # any new future; only its trace/path length differs.
        expanded_this_turn=set()
        best_by={}
        for depth in range(max_actions_per_turn):
            max_depth_reached=max(max_depth_reached,depth+1)
            nxt=[]
            for st in frontier:
                sk=st.key()
                if sk in expanded_this_turn:
                    graph_stats["cycle_skips"] += 1
                    continue
                expanded_this_turn.add(sk)
                searched+=1
                graph_stats["nodes_expanded"] += 1
                if st.won:
                    return st.turn,st.win_family,st.trace,searched,st.urza_cast_turn,st.interaction_seen,tuple(sorted(st.hand)),max_depth_reached
                _actions=legal_actions(st)
                graph_stats["edges_generated"] += len(_actions)
                graph_stats["max_raw_successors"] = max(graph_stats["max_raw_successors"],len(_actions))
                for ns in _actions:
                    ns=check_win(ns)
                    if ns.won:
                        return ns.turn,ns.win_family,ns.trace,searched,ns.urza_cast_turn,ns.interaction_seen,tuple(sorted(ns.hand)),max_depth_reached
                    k=ns.key()
                    old=best_by.get(k)
                    if old is not None:
                        graph_stats["exact_key_merges"] += 1
                    if old is None or score(ns)>score(old):
                        best_by[k]=ns
            if not best_by: break
            # Keep best states globally; heuristic orders search but does not hard-code card priorities.
            _pre_dom=list(best_by.values())
            _post_dom=dominance_prune(_pre_dom)
            graph_stats["dominance_pruned"] += max(0,len(_pre_dom)-len(_post_dom))
            graph_stats["beam_pruned"] += max(0,len(_post_dom)-beam)
            frontier=heapq.nlargest(beam,_post_dom,key=score)
            graph_stats["layers"] += 1
            graph_stats["max_frontier"] = max(graph_stats["max_frontier"],len(frontier))
            best_by={}
            if progress_tag and progress_seconds>0:
                _now=time.time()
                if _now-_progress_last >= progress_seconds:
                    print(
                        f"[search {progress_tag}] T{turn} D{depth+1} "
                        f"frontier={len(frontier)} searched={searched:,} "
                        f"elapsed={_now-_progress_start:.0f}s",
                        flush=True
                    )
                    _progress_last=_now
        # include end-turn from best surviving states
        states=[end_turn(x) for x in heapq.nlargest(min(beam,len(frontier)),frontier,key=score)]
    last=states[0] if states else s
    return None,"",last.trace if states else (),searched,last.urza_cast_turn,last.interaction_seen,tuple(sorted(last.hand)),max_depth_reached


def profile_single_hand(deck_order:List[str], max_turn:int=3, beam:int=300,
                        max_actions_per_turn:int=60, caverns_live:bool=True,
                        print_every_depth:int=1):
    """
    Run ONE deterministic opening-7 candidate with no oracle mulligan branching.
    This is diagnostic only. It prints per-depth search statistics so we can
    identify where combinatorial explosion originates.
    """
    hand=deck_order[:7]
    lib=tuple(deck_order[7:])
    s=State(turn=1,library=lib,hand=tuple(hand),battlefield=(),trace=("--- Turn 1 ---",))
    if caverns_live and "Gemstone Caverns" in s.hand:
        # Keep same pregame handling philosophy as normal search by letting the
        # regular search/actions decide actual use; this profiler is about branching.
        pass
    if s.library:
        s=replace(s,hand=s.hand+(s.library[0],),library=s.library[1:])
    s=refresh_observability(s)
    states=[s]
    searched=0
    print("\n=== PROFILE SINGLE HAND ===",flush=True)
    print("Opening 7:",", ".join(hand),flush=True)
    print(f"Config: turns={max_turn} beam={beam} depth={max_actions_per_turn} action_cap={ACTION_CAP}",flush=True)

    for turn in range(1,max_turn+1):
        frontier=states
        expanded_this_turn=set()
        print(f"\n[T{turn}] start frontier={len(frontier)} hand={len(frontier[0].hand) if frontier else 0}",flush=True)
        for depth in range(max_actions_per_turn):
            t0=time.time()
            generated=0
            raw_states=0
            cycle_skips=0
            best_by={}
            action_hist=Counter()
            action_classes=Counter()

            for st in frontier:
                sk=st.key()
                if sk in expanded_this_turn:
                    cycle_skips+=1
                    continue
                expanded_this_turn.add(sk)
                searched+=1
                if st.won:
                    print(f"[T{turn} D{depth:02}] WIN already found: {st.win_family}",flush=True)
                    return st
                actions=legal_actions(st)
                na=len(actions)
                action_hist[na]+=1
                raw_states += 1
                generated += na
                for ns in actions:
                    if ns.trace:
                        action_classes[classify_action(ns.trace[-1])] += 1
                    ns=check_win(ns)
                    if ns.won:
                        print(f"[T{turn} D{depth:02}] WIN generated: {ns.win_family}",flush=True)
                        print(f"searched={searched:,}",flush=True)
                        return ns
                    k=ns.key()
                    old=best_by.get(k)
                    if old is None or score(ns)>score(old):
                        best_by[k]=ns

            unique=len(best_by)
            if not best_by:
                print(f"[T{turn} D{depth:02}] no successors; ending turn",flush=True)
                break

            pre_dom=list(best_by.values())
            dom=dominance_prune(pre_dom)
            dom_n=len(dom)
            frontier=heapq.nlargest(beam,dom,key=score)

            dt=time.time()-t0
            rss=process_rss_mb()
            avg_actions=(generated/raw_states) if raw_states else 0
            max_actions=max(action_hist) if action_hist else 0
            rss_txt=f"{rss:.1f} MB" if rss is not None else "n/a"

            if depth % max(1,print_every_depth)==0:
                print(
                    f"[T{turn} D{depth+1:02}] "
                    f"in={raw_states:4d} gen={generated:7,d} "
                    f"avg_act={avg_actions:6.1f} max_act={max_actions:3d} | "
                    f"unique={unique:7,d} dom={dom_n:7,d} keep={len(frontier):4d} "
                    f"cycle_skip={cycle_skips:4d} | "
                    f"dt={dt:6.2f}s total_states={searched:9,d} rss={rss_txt}",
                    flush=True
                )

            if depth % max(1,print_every_depth)==0 and action_classes:
                cls=" ".join(f"{k}={v}" for k,v in action_classes.most_common())
                print(f"           action_mix: {cls}",flush=True)

            # Also print a warning when one depth becomes obviously pathological.
            if dt >= 15:
                print(
                    f"  [WARN] this single depth took {dt:.1f}s. "
                    f"generated={generated:,}, unique={unique:,}, retained={len(frontier)}",
                    flush=True
                )

        if not frontier:
            break
        states=[end_turn(x) for x in heapq.nlargest(min(beam,len(frontier)),frontier,key=score)]

    print(f"\nPROFILE END: no win through T{max_turn}; searched={searched:,}",flush=True)
    return states[0] if states else None


def profile_seed(seed:int, deck:List[str], max_turn:int, beam:int, depth:int):
    rng=random.Random(seed)
    d=deck[:]
    rng.shuffle(d)
    return profile_single_hand(
        d,max_turn=max_turn,beam=beam,
        max_actions_per_turn=depth,caverns_live=True
    )



def profile_oracle_seed(seed:int, deck:List[str], max_turn:int=7, beam:int=300, depth:int=60, bottom_cap:int=4):
    """
    Profile the ACTUAL oracle candidate structure for a single seed.
    Prints before/after every independent hand search so a pathological
    mulligan candidate / London-bottom choice is immediately identifiable.
    """
    rng=random.Random(seed)
    print("\n=== PROFILE ORACLE SEED ===",flush=True)
    print(f"seed={seed} turns={max_turn} beam={beam} depth={depth} bottom_cap={bottom_cap}",flush=True)

    stages=[("7A",0),("7B",0),("6",1),("5",2),("4",3)]
    total_searches=0
    total_wall=time.time()
    candidate_results=[]

    for stage_idx,(label,bottom_n) in enumerate(stages):
        d=deck[:]
        rng.shuffle(d)
        seven=d[:7]
        bottoms=bottom_candidates(seven,bottom_n,cap=bottom_cap)

        print(f"\n[{label}] opening7: {', '.join(seven)}",flush=True)
        print(f"[{label}] bottom variants to test: {len(bottoms)}",flush=True)

        for bi,bottom in enumerate(bottoms,1):
            kept=list(seven)
            for c in bottom:
                kept.remove(c)

            tag=f"{label}.{bi}/{len(bottoms)}"
            print(
                f"\n>>> START {tag} keep={len(kept)} "
                f"bottom=[{', '.join(bottom) if bottom else '-'}]",
                flush=True
            )
            print(f"    kept=[{', '.join(kept)}]",flush=True)

            t0=time.time()
            # Use the real search_hand, not profile_single_hand, so bottom/library
            # construction exactly matches the simulator.
            result=profile_search_hand(
                d,7-bottom_n,bottom,
                max_turn=max_turn,beam=beam,
                max_actions_per_turn=depth,caverns_live=True,
                candidate_tag=tag
            )
            dt=time.time()-t0
            total_searches += 1

            turn,fam,trace,states,urza_turn,interaction_seen,final_hand,max_depth=result
            candidate_results.append((tag,turn,dt,states,max_depth,fam))

            print(
                f"<<< DONE  {tag} time={dt:.2f}s "
                f"win={turn if turn is not None else '-'} "
                f"family={fam or '-'} states={states:,} max_depth={max_depth}",
                flush=True
            )

            if dt>=30:
                print(f"    [SLOW CANDIDATE] {tag} took {dt:.1f}s",flush=True)

    wall=time.time()-total_wall
    print("\n=== ORACLE PROFILE SUMMARY ===",flush=True)
    for tag,turn,dt,states,max_depth,fam in sorted(candidate_results,key=lambda x:x[2],reverse=True):
        print(
            f"{tag:8s} {dt:8.2f}s | win={str(turn or '-'):>2s} "
            f"| states={states:10,d} | depth={max_depth:3d} | {fam or '-'}",
            flush=True
        )
    print(f"Total independent hand searches: {total_searches}",flush=True)
    print(f"Total wall time: {wall:.2f}s",flush=True)
    return candidate_results



def profile_search_hand(deck_order:List[str], keep_n:int, bottom:List[str], max_turn=7,
                        beam=300, max_actions_per_turn=60, caverns_live=True,
                        candidate_tag="candidate"):
    """
    Exact search_hand initialization + depth-by-depth diagnostics.
    Used by --profile-oracle so a slow candidate never disappears into a silent call.
    """
    hand=deck_order[:7]
    rest=deck_order[7:]
    for c in bottom:
        hand.remove(c)
    lib=tuple(rest+bottom)
    s=State(turn=1,library=lib,hand=tuple(hand),battlefield=(),trace=("--- Turn 1 ---",))

    if "Gemstone Caverns" in s.hand and caverns_live and len(s.hand)>1:
        choices=[c for c in s.hand if c!="Gemstone Caverns"]
        ex=min(choices,key=lambda c:card_priority(s,c))
        s=replace(s,hand=remove_one(remove_one(s.hand,"Gemstone Caverns"),ex),exile=s.exile+(ex,))
        s=add_perm(s,"Gemstone Caverns",mode="luck")
        s=add_trace(s,f"pregame Caverns exiles {ex}")

    if s.library:
        s=replace(s,hand=s.hand+(s.library[0],),library=s.library[1:])
    s=refresh_observability(s)

    states=[s]
    searched=0
    max_depth_reached=0
    search_start=time.time()

    print(f"    [{candidate_tag}] actual T1 hand after draw: {', '.join(s.hand)}",flush=True)

    for turn in range(1,max_turn+1):
        frontier=states
        expanded_this_turn=set()
        print(f"    [{candidate_tag}] T{turn} START frontier={len(frontier)}",flush=True)

        for depth in range(max_actions_per_turn):
            layer_start=time.time()
            max_depth_reached=max(max_depth_reached,depth+1)
            best_by={}
            generated=0
            action_classes=Counter()
            action_counts=[]
            incoming=len(frontier)
            cycle_skips=0

            for state_i,st in enumerate(frontier,1):
                sk=st.key()
                if sk in expanded_this_turn:
                    cycle_skips += 1
                    continue
                expanded_this_turn.add(sk)
                searched += 1

                chain_live=(
                    "Chain of Vapor" in st.hand
                    and can_pay(st,0,1)
                )
                if chain_live or state_i==1 or state_i%25==0:
                    nlands=sum(1 for p in st.battlefield if p.name in F_ALL_LANDS)
                    nnonlands=sum(1 for p in st.battlefield if p.name not in F_ALL_LANDS)
                    print(
                        f"        [{candidate_tag}] entering state {state_i}/{incoming} "
                        f"bf={len(st.battlefield)} lands={nlands} nonlands={nnonlands} "
                        f"hand={len(st.hand)} chain={'LIVE' if chain_live else '-'}",
                        flush=True
                    )

                if st.won:
                    print(f"    [{candidate_tag}] T{turn} D{depth+1:02} WIN {st.win_family}",flush=True)
                    return st.turn,st.win_family,st.trace,searched,st.urza_cast_turn,st.interaction_seen,tuple(sorted(st.hand)),max_depth_reached

                action_t0=time.time()
                actions=legal_actions(st)
                action_dt=time.time()-action_t0
                if action_dt>=1.0:
                    print(
                        f"        [SLOW STATE] {candidate_tag} T{turn} D{depth+1} "
                        f"state={state_i}/{incoming} legal_actions={action_dt:.2f}s "
                        f"actions_returned={len(actions)}",
                        flush=True
                    )
                action_counts.append(len(actions))
                generated += len(actions)
                for ns in actions:
                    if ns.trace:
                        action_classes[classify_action(ns.trace[-1])] += 1
                    ns=check_win(ns)
                    if ns.won:
                        print(
                            f"    [{candidate_tag}] T{turn} D{depth+1:02} WIN {ns.win_family} "
                            f"after {searched:,} searched states",
                            flush=True
                        )
                        return ns.turn,ns.win_family,ns.trace,searched,ns.urza_cast_turn,ns.interaction_seen,tuple(sorted(ns.hand)),max_depth_reached
                    k=ns.key()
                    old=best_by.get(k)
                    if old is None or score(ns)>score(old):
                        best_by[k]=ns

            if not best_by:
                dt=time.time()-layer_start
                print(
                    f"    [{candidate_tag}] T{turn} D{depth+1:02} END no successors | "
                    f"in={incoming} gen={generated:,} dt={dt:.3f}s total={searched:,}",
                    flush=True
                )
                break

            unique=len(best_by)
            dom=dominance_prune(best_by.values())
            dom_n=len(dom)
            frontier=heapq.nlargest(beam,dom,key=score)

            dt=time.time()-layer_start
            rss=process_rss_mb()
            rss_txt=f"{rss:.0f}MB" if rss is not None else "n/a"
            avg=(generated/incoming) if incoming else 0
            mx=max(action_counts) if action_counts else 0
            mix=" ".join(f"{k}={v}" for k,v in action_classes.most_common())

            print(
                f"    [{candidate_tag}] T{turn} D{depth+1:02} "
                f"in={incoming:3d} gen={generated:7,d} avg={avg:5.1f} max={mx:2d} | "
                f"unique={unique:7,d} dom={dom_n:7,d} keep={len(frontier):3d} "
                f"cycle_skip={cycle_skips:3d} | "
                f"dt={dt:6.2f}s total={searched:9,d} rss={rss_txt}",
                flush=True
            )
            if mix:
                print(f"        mix: {mix}",flush=True)

            if dt>=10:
                print(
                    f"        [SLOW LAYER] {candidate_tag} T{turn} D{depth+1}: "
                    f"{dt:.1f}s for {generated:,} generated successors",
                    flush=True
                )

        if not frontier:
            break
        end_start=time.time()
        states=[end_turn(x) for x in heapq.nlargest(min(beam,len(frontier)),frontier,key=score)]
        print(
            f"    [{candidate_tag}] T{turn} -> T{turn+1} end-turn expansion "
            f"{len(states)} states in {time.time()-end_start:.2f}s",
            flush=True
        )

    last=states[0] if states else s
    print(
        f"    [{candidate_tag}] SEARCH END no win | wall={time.time()-search_start:.2f}s "
        f"searched={searched:,} max_depth={max_depth_reached}",
        flush=True
    )
    return None,"",last.trace if states else (),searched,last.urza_cast_turn,last.interaction_seen,tuple(sorted(last.hand)),max_depth_reached


# --------------------------- Mulligans -------------------------------------

def bottom_candidates(seven:List[str], n_bottom:int, cap=None)->List[List[str]]:
    if n_bottom<=0: return [[]]
    if cap is None: cap=BOTTOM_CAP
    # prioritize bottoming interaction / redundant expensive cards, but retain diversity.
    def bottom_score(c):
        if c in ALL_LANDS: return -3
        if c in CA_ENGINES: return -4
        if c in {"Grinding Station","Battered Golem",COMMANDER}: return -5
        if c in ARTIFACTS: return -2
        return 2
    import itertools
    combos=list(itertools.combinations(range(7),n_bottom))
    combos.sort(key=lambda inds:sum(bottom_score(seven[i]) for i in inds),reverse=True)
    return [[seven[i] for i in inds] for inds in combos[:cap]]

def oracle_game(seed:int,deck:List[str],max_turn:int,beam:int,depth:int,
                live_progress:bool=False, progress_seconds:float=10.0):
    """
    Oracle mulligan search with exact earliest-win branch-and-bound.

    Once an EARLIER mulligan stage has established a win on turn B, any later
    stage only needs to be searched through B-1: a tie on turn B would lose the
    oracle tie-break to the earlier stage anyway.

    Within the SAME stage, if one bottom choice finds turn B, later bottom
    choices are still searched through B (not B-1) so the existing same-stage
    trace tie-break remains reproducible.
    """
    rng=random.Random(seed)
    caverns_live=(rng.random()<0.75)
    candidates=[]
    global_best_turn=None
    total_oracle_states=0
    oracle_graph=new_graph_stats()
    oracle_t0=time.time()

    stage_specs=[("7A",0),("7B",0),("6",1),("5",2),("4",3)]

    for stage,(stage_label,bottom_n) in enumerate(stage_specs):
        d=deck[:]
        rng.shuffle(d)
        seven=d[:7]

        # Later mulligan stages cannot beat an earlier-stage tie, so only turns
        # STRICTLY earlier than the current global winner matter.
        stage_horizon=max_turn
        if global_best_turn is not None:
            stage_horizon=min(stage_horizon,global_best_turn-1)

        if stage_horizon<1:
            if live_progress:
                print(
                    f"[oracle seed={seed}] SKIP {stage_label}: "
                    f"earlier stage already wins T{global_best_turn}",
                    flush=True
                )
            continue

        bottoms=bottom_candidates(seven,bottom_n)
        best=None
        stage_best_turn=None

        if live_progress:
            print(
                f"[oracle seed={seed}] START {stage_label} "
                f"keep={7-bottom_n} variants={len(bottoms)} horizon=T{stage_horizon}",
                flush=True
            )

        for bi,bottom in enumerate(bottoms,1):
            # Preserve same-stage equal-turn comparison.
            hand_horizon=stage_horizon
            if stage_best_turn is not None:
                hand_horizon=min(hand_horizon,stage_best_turn)

            tag=f"{stage_label}.{bi}/{len(bottoms)}"
            if live_progress:
                print(
                    f"[oracle seed={seed}] -> {tag} "
                    f"bottom=[{', '.join(bottom) if bottom else '-'}] "
                    f"search<=T{hand_horizon}",
                    flush=True
                )

            ht0=time.time()
            hand_graph=new_graph_stats()
            result=search_hand(
                d,7-bottom_n,bottom,
                max_turn=hand_horizon,
                beam=beam,
                max_actions_per_turn=depth,
                caverns_live=caverns_live,
                progress_tag=(f"seed={seed} {tag}" if live_progress else ""),
                progress_seconds=progress_seconds,
                graph_stats=hand_graph
            )
            merge_graph_stats(oracle_graph,hand_graph)
            turn,fam,trace,states,urza_turn,interaction_seen,final_hand,max_depth=result
            total_oracle_states += states

            if live_progress:
                print(
                    f"[oracle seed={seed}] <- {tag} "
                    f"time={time.time()-ht0:.1f}s win={turn if turn is not None else '-'} "
                    f"urza={urza_turn if urza_turn else '-'} states={states:,} "
                    f"oracle_states={total_oracle_states:,}",
                    flush=True
                )

            metric=(turn if turn is not None else 99, -len(trace))
            if best is None or metric<best[0]:
                best=(metric,result,bottom)

            if turn is not None and (stage_best_turn is None or turn<stage_best_turn):
                stage_best_turn=turn

        if best is None:
            continue

        candidates.append((stage,best,d[:7]))

        stage_turn=best[1][0]
        if stage_turn is not None and (global_best_turn is None or stage_turn<global_best_turn):
            global_best_turn=stage_turn

        if live_progress:
            print(
                f"[oracle seed={seed}] DONE {stage_label}: "
                f"best={stage_turn if stage_turn is not None else '-'} "
                f"global_best={global_best_turn if global_best_turn is not None else '-'} "
                f"elapsed={time.time()-oracle_t0:.1f}s",
                flush=True
            )

    if not candidates:
        # Defensive; normally at least 7A exists.
        return {
            "seed":seed,"win_turn":None,"family":"","mulligan_stage":0,
            "keep_size":7,"bottom":[],"opening7":[],"kept_hand":[],
            "urza_cast_turn":0,"interaction_count":0,"interaction_seen":[],
            "final_hand":[],"max_depth_reached":0,"states":0,
            "oracle_states_total":total_oracle_states,
            "graph":finalize_graph_stats(oracle_graph),"trace":()
        }

    candidates.sort(
        key=lambda x:(
            x[1][1][0] if x[1][1][0] is not None else 99,
            x[0]
        )
    )
    stage,best,seven=candidates[0]
    turn,fam,trace,states,urza_turn,interaction_seen,final_hand,max_depth=best[1]
    kept=list(seven)
    for c in best[2]:
        kept.remove(c)

    return {
        "seed":seed,"win_turn":turn,"family":fam,"mulligan_stage":stage,
        "keep_size":[7,7,6,5,4][stage],"bottom":best[2],"opening7":seven,
        "kept_hand":kept,"urza_cast_turn":urza_turn,
        "interaction_count":len(interaction_seen),"interaction_seen":list(interaction_seen),
        "final_hand":list(final_hand),"max_depth_reached":max_depth,
        "states":states,"oracle_states_total":total_oracle_states,
        "graph":finalize_graph_stats(oracle_graph),"trace":trace
    }


def worker_process_initializer():
    """
    Windows multiprocessing safety:
    Pool workers must NOT handle Ctrl+C themselves.

    If a worker receives KeyboardInterrupt and exits independently,
    multiprocessing.Pool treats that as a crashed worker and may spawn a
    replacement. That produced the apparent "Ctrl+C restarts workers" behavior.

    Only the parent handles Ctrl+C; it then terminates the whole pool.
    """
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except Exception:
        pass

    # Windows Ctrl+Break can be delivered separately.
    if hasattr(signal,"SIGBREAK"):
        try:
            signal.signal(signal.SIGBREAK, signal.SIG_IGN)
        except Exception:
            pass


def worker(args):
    # Last tuple element is a reporting-only verbose flag.
    if len(args)==6:
        seed,deck,max_turn,beam,depth,verbose_worker=args
        oracle_args=(seed,deck,max_turn,beam,depth)
    else:
        seed=args[0]
        verbose_worker=False
        oracle_args=args

    pid=os.getpid()
    t0=time.time()
    if verbose_worker:
        print(f"[worker {pid}] START seed={seed}", flush=True)
    try:
        result=oracle_game(*oracle_args)
        result["_elapsed_worker_s"]=time.time()-t0
        result["_error"]=""
        if verbose_worker:
            wt=result.get("win_turn")
            print(f"[worker {pid}] DONE  seed={seed} win={wt if wt is not None else '-'} "
                  f"time={result['_elapsed_worker_s']:.1f}s states={result.get('states',0):,}", flush=True)
        return result
    except Exception:
        if verbose_worker:
            print(f"[worker {pid}] ERROR seed={seed} after {time.time()-t0:.1f}s", flush=True)
        return {
            "seed":seed,
            "win_turn":None,
            "family":"",
            "mulligan_stage":-1,
            "keep_size":0,
            "bottom":[],
            "opening7":[],
            "kept_hand":[],
            "urza_cast_turn":0,
            "interaction_count":0,
            "interaction_seen":[],
            "final_hand":[],
            "max_depth_reached":0,
            "states":0,
            "trace":(),
            "_elapsed_worker_s":time.time()-t0,
            "_error":traceback.format_exc(),
        }


# --------------------------- Reporting -------------------------------------

def load_deck(path:Path)->List[str]:
    cards=[]
    commander=None
    for line in path.read_text(encoding="utf-8").splitlines():
        line=line.strip()
        if not line: continue
        n,name=line.split(" ",1)
        n=int(n)
        if name==COMMANDER:
            commander=name
        else:
            cards.extend([name]*n)
    if len(cards)!=99:
        raise ValueError(f"Expected 99 cards excluding commander, got {len(cards)}")
    return cards

def summarize(results,max_turn):
    exact=Counter(r["win_turn"] for r in results if r["win_turn"] is not None)
    fam=Counter(r["family"] for r in results if r["family"])
    mull=Counter(r["keep_size"] for r in results)
    n=len(results)
    cum=0
    rows=[]
    for t in range(1,max_turn+1):
        cum+=exact[t]
        p=cum/n
        se=math.sqrt(max(1e-12,p*(1-p)/n))
        rows.append((t,exact[t],cum,100*p,100*1.96*se))
    return rows,fam,mull


def write_partial_checkpoint(out:Path, results, args, reason:str):
    """Best-effort checkpoint used on Ctrl+C or abnormal early termination."""
    try:
        out.mkdir(exist_ok=True)
        ordered=sorted(results,key=lambda r:r.get("seed",0))
        payload={
            "status":"partial",
            "reason":reason,
            "completed":len(ordered),
            "requested_runs":args.runs,
            "seed":args.seed,
            "beam":args.beam,
            "action_cap":ACTION_CAP,
            "depth":args.depth,
            "workers":args.workers,
            "timestamp_unix":time.time(),
            "games":[
                {
                    "seed":r.get("seed"),
                    "win_turn":r.get("win_turn"),
                    "urza_cast_turn":r.get("urza_cast_turn"),
                    "family":r.get("family",""),
                    "keep_size":r.get("keep_size",0),
                    "max_depth_reached":r.get("max_depth_reached",0),
                    "states":r.get("states",0),
                    "error":bool(r.get("_error")),
                }
                for r in ordered
            ]
        }
        (out/"partial_checkpoint.json").write_text(json.dumps(payload,indent=2),encoding="utf-8")
        print(f"[checkpoint] wrote {out/'partial_checkpoint.json'}",flush=True)
    except Exception as exc:
        print(f"[checkpoint] failed to write partial checkpoint: {exc}",flush=True)



def run_chain_stress_test():
    """
    Synthetic board deliberately much larger than normal early-game Chain states.
    Verifies that Chain branching terminates quickly rather than factorially.
    """
    bf=(
        Perm("Island"),Perm("Island"),Perm("Island"),Perm("Minamo, School at Water's Edge"),
        Perm("Sensei's Divining Top"),Perm("Codex Shredder"),Perm("Grinding Station"),
        Perm("Grafdigger's Cage"),Perm("Pithing Needle"),Perm("Witching Well"),
        Perm("Sewer-veillance Cam"),Perm("Sol Ring"),Perm("Mana Vault"),
    )
    st=State(
        turn=7,
        library=("Island","Chrome Dome","Basalt Monolith","The Reality Chip"),
        hand=("Chain of Vapor",),
        battlefield=bf,
        blue=1,
        colorless=0,
        urza=False
    )
    t0=time.time()
    actions=chain_of_vapor_actions(st)
    dt=time.time()-t0
    print(
        f"Chain stress test: bf={len(bf)}, lands=4, nonlands=9 -> "
        f"returned={len(actions)} actions in {dt:.3f}s",
        flush=True
    )
    if dt>10:
        raise RuntimeError(f"Chain stress test too slow: {dt:.2f}s")
    return actions



def run_problem_smoke():
    """
    Time likely pathological action generators on developed synthetic states.
    This is performance smoke/QC, not a game-probability simulation.
    """
    print("\n=== PROBLEM-CARD SMOKE SUITE ===",flush=True)

    # Developed board with enough mana/resources to light up many generators.
    bf=(
        Perm("Island"),Perm("Island"),Perm("Island"),
        Perm("Minamo, School at Water's Edge"),Perm("Oboro, Palace in the Clouds"),
        Perm("Sensei's Divining Top"),Perm("Codex Shredder"),Perm("Grinding Station"),
        Perm("Battered Golem",sick=False),Perm("Grafdigger's Cage"),Perm("Pithing Needle"),
        Perm("Sewer-veillance Cam"),Perm("Sol Ring"),Perm("Mana Vault"),
        Perm("Voltaic Key"),Perm("Forensic Gadgeteer",sick=False),
        Perm("Uthros Research Craft",sick=False),
        Perm(COMMANDER,sick=False),
    )
    hand=(
        "Chain of Vapor","Whir of Invention","Reshape","Transmute Artifact",
        "Mystical Tutor","Muddle the Mixture","Dizzy Spell","Banishing Knack",
        "Retraction Helix","Chrome Dome","Everflowing Chalice","Dramatic Reversal",
        "Scour for Scrap"
    )
    lib=tuple(DECKLIST_FALLBACK if "DECKLIST_FALLBACK" in globals() else [])
    if not lib:
        # deterministic representative library
        lib=(
            "The Reality Chip","Fortune Teller's Talent","Power Artifact","Grim Monolith",
            "Basalt Monolith","The One Ring","Spellseeker","Prized Statue","Mox Opal",
            "Lotus Petal","Welding Jar","Urza's Bauble","Mishra's Bauble","Island"
        )

    s=State(
        turn=6,library=lib,hand=hand,battlefield=bf,
        blue=6,colorless=12,urza=True,construct=True,
        uthros_counters=3,spell_cast_this_turn=True
    )

    tests=[
        ("Chain of Vapor",lambda:chain_of_vapor_actions(s)),
        ("simple tutors",lambda:simple_tutor_actions(s)),
        ("artifact tutors",lambda:artifact_tutor_actions(s)),
        ("Top actions",lambda:top_actions(s)),
        ("Top+Key",lambda:top_key_combo_actions(s)),
        ("Chrome Dome",lambda:chrome_dome_actions(s)),
        ("Uthros Station",lambda:uthros_station_actions(s)),
        ("Knack/Helix bounce",lambda:knack_bounce_actions(s)),
        ("producer native",lambda:producer_native_actions(s)),
        ("Chalice variants",lambda:chalice_cast_variants(s)),
        ("all special_actions",lambda:special_actions(s)),
        ("all legal_actions",lambda:legal_actions(s)),
    ]

    failures=[]
    for name,fn in tests:
        t0=time.time()
        try:
            out=fn()
            dt=time.time()-t0
            n=len(out) if out is not None else 0
            mark="OK"
            if dt>=1.0:
                mark="SLOW"
                failures.append((name,dt,n))
            print(f"{name:22s} {dt:8.3f}s | returned={n:5d} | {mark}",flush=True)
        except Exception as exc:
            dt=time.time()-t0
            failures.append((name,dt,-1))
            print(f"{name:22s} {dt:8.3f}s | ERROR: {exc}",flush=True)

    print("\nSmoke summary:",flush=True)
    if failures:
        for name,dt,n in failures:
            print(f"  investigate: {name} {dt:.3f}s returned={n}",flush=True)
    else:
        print("  no action family exceeded 1.0 s on the developed synthetic state",flush=True)


def run_chain_macro_smoke():
    """Focused developed-board canonical Chain performance test."""
    bf=(
        Perm("Island"),Perm("Island"),Perm("Island"),Perm("Minamo, School at Water's Edge"),
        Perm("Oboro, Palace in the Clouds"),
        Perm("Sensei's Divining Top"),Perm("Codex Shredder"),Perm("Grinding Station"),
        Perm("Grafdigger's Cage"),Perm("Pithing Needle"),Perm("Witching Well"),
        Perm("Sewer-veillance Cam"),Perm("Sol Ring"),Perm("Mana Vault"),Perm("Voltaic Key"),
        Perm("Power Artifact"),
        Perm("Grim Monolith"),
    )
    st=State(turn=7,library=("Island","Chrome Dome","Basalt Monolith"),hand=("Chain of Vapor",),
             battlefield=bf,blue=1,pa_target="Grim Monolith")
    t0=time.time()
    out=chain_of_vapor_actions(st)
    dt=time.time()-t0
    print(f"Canonical Chain smoke: lands=5 nonlands=12 -> returned={len(out)} in {dt:.3f}s",flush=True)
    if dt>1.0:
        raise RuntimeError(f"Canonical Chain still too slow after shortlist optimization: {dt:.2f}s")
    return out



_parent_cancel_count=0

def parent_interrupt_handler(signum, frame):
    global _parent_cancel_count
    _parent_cancel_count += 1
    if _parent_cancel_count == 1:
        # Convert into KeyboardInterrupt for the normal graceful cleanup path.
        print("\n[CANCEL] Ctrl+C received by parent; stopping all workers...",flush=True)
        raise KeyboardInterrupt
    else:
        # Emergency escape if pool/join/IO cleanup itself becomes stuck.
        print("\n[FORCE EXIT] Second interrupt received. Exiting immediately.",flush=True)
        os._exit(130)



def _cancel_test_sleep(seconds):
    time.sleep(seconds)
    return seconds

def run_cancel_test(workers:int):
    """
    Windows-safe cancellation test.

    Do NOT block in pool.map()/imap() waiting for a worker result. On Windows,
    that wait can keep the main interpreter inside a low-level synchronization
    call long enough that Ctrl+C appears ignored.

    Instead submit asynchronously and poll every 0.2 s. Python therefore regains
    control continuously and processes KeyboardInterrupt promptly.
    """
    print(f"Cancellation test: starting {workers} worker(s) for 120 s.",flush=True)
    print("Press Ctrl+C ONCE now. Expected immediate pool termination.",flush=True)

    pool=mp.Pool(workers,initializer=worker_process_initializer)
    async_results=[pool.apply_async(_cancel_test_sleep,(120,)) for _ in range(workers)]

    try:
        while True:
            if all(r.ready() for r in async_results):
                break
            time.sleep(0.2)  # interruptible polling point
        pool.close()
        pool.join()
        print("[CANCEL TEST] workers completed normally (no Ctrl+C was received).",flush=True)

    except KeyboardInterrupt:
        print("[CANCEL TEST] parent caught Ctrl+C -> terminate()",flush=True)
        try:
            pool.terminate()
        finally:
            # join should now be quick; don't allow a second hidden blocking loop.
            try:
                pool.join()
            except Exception:
                pass
        print("[CANCEL TEST] PASS: pool terminated; no worker replacement requested.",flush=True)
        return



def run_commander_smoke():
    print("\n=== COMMANDER CAST CORRECTNESS SMOKE ===",flush=True)

    # 2UU normal cast.
    s=State(turn=3,library=(),hand=(),battlefield=(),blue=2,colorless=2)
    a=cast_urza_from_command_zone_actions(s)
    assert a and a[0].urza and a[0].urza_cast_turn==3
    assert not a[0].commander_in_command_zone
    assert any(p.name==COMMANDER for p in a[0].battlefield)
    print("normal {2}{U}{U} command-zone cast: PASS",flush=True)

    # Cannot cast with 4 colorless / no UU.
    s=State(turn=3,library=(),hand=(),battlefield=(),blue=0,colorless=4)
    assert not cast_urza_from_command_zone_actions(s)
    print("colored requirement UU enforced: PASS",flush=True)

    # Infinite colorless does not waive UU.
    s=State(
        turn=3,library=(),hand=(),
        battlefield=(Perm("Basalt Monolith"),Perm("Forensic Gadgeteer",sick=False)),
        blue=1,colorless=0
    )
    assert infinite_colorless_online(s)
    assert not cast_urza_from_command_zone_actions(s)
    s2=replace(s,blue=2)
    a=cast_urza_from_command_zone_actions(s2)
    assert a and a[0].urza and a[0].blue==0
    print("infinite colorless pays generic but still requires real UU: PASS",flush=True)

    # Merely having pre-Urza combo no longer declares win.
    combo=State(
        turn=3,library=(),hand=(),
        battlefield=(Perm("Basalt Monolith"),Perm("Forensic Gadgeteer",sick=False)),
        blue=1
    )
    assert not check_win(combo).won
    print("pre-Urza infinite shortcut removed: PASS",flush=True)

    # FTT3+Top no longer scans hidden library for imaginary future blue.
    ftt=State(
        turn=3,library=("Island","Island","Lotus Petal"),hand=(),
        battlefield=(Perm("Fortune Teller's Talent"),Perm("Sensei's Divining Top")),
        ftt_level=3,spell_cast_this_turn=True
    )
    assert not check_win(ftt).won
    print("FTT3+Top hidden-library terminal shortcut removed: PASS",flush=True)

    # Bounce Urza clears Urza-active flag and moves commander to hand via Chain-style caller.
    us=State(
        turn=4,library=(),hand=(),
        battlefield=(Perm(COMMANDER,sick=False),Perm("Construct",mode="construct")),
        urza=True,commander_in_command_zone=False
    )
    idx=next(i for i,p in enumerate(us.battlefield) if p.name==COMMANDER)
    bounced=remove_perm(us,idx,to_grave=False)
    bounced=replace(bounced,hand=bounced.hand+(COMMANDER,))
    assert not bounced.urza and not bounced.commander_in_command_zone and COMMANDER in bounced.hand
    print("bounced Urza disables artifact-mana ability and goes to hand: PASS",flush=True)

    # Graveyard-bound Urza chooses command zone.
    us=State(
        turn=4,library=(),hand=(),
        battlefield=(Perm(COMMANDER,sick=False),),
        urza=True,commander_in_command_zone=False
    )
    dead=remove_perm(us,0,to_grave=True)
    assert not dead.urza and dead.commander_in_command_zone and COMMANDER not in dead.graveyard
    print("graveyard-bound Urza returns to command zone: PASS",flush=True)

    # Commander tax second zone cast = +2 generic.
    s=State(
        turn=5,library=(),hand=(),battlefield=(),blue=2,colorless=3,
        commander_in_command_zone=True,commander_casts_from_zone=1
    )
    # Needs 4UU now; 3 generic is insufficient.
    assert not cast_urza_from_command_zone_actions(s)
    s=replace(s,colorless=4)
    assert cast_urza_from_command_zone_actions(s)
    print("commander tax on repeat command-zone cast: PASS",flush=True)

    print("COMMANDER SMOKE: ALL PASS",flush=True)



def audit_oracle_result(r,depth_limit:int):
    """Return a list of correctness/performance warnings for one oracle result."""
    issues=[]
    win_turn=r.get("win_turn")
    urza_turn=r.get("urza_cast_turn") or 0
    family=r.get("family","")
    trace=tuple(r.get("trace",()))

    if win_turn is not None:
        if urza_turn<=0:
            issues.append("WIN_WITHOUT_URZA_CAST_TURN")
        if urza_turn and win_turn < urza_turn:
            issues.append("WIN_BEFORE_URZA_CAST")
        if "Pre-Urza" in family:
            issues.append("LEGACY_PRE_URZA_WIN_LABEL")
        if not any("cast Urza" in x for x in trace):
            issues.append("WIN_TRACE_MISSING_URZA_CAST")

    if r.get("max_depth_reached",0) >= depth_limit:
        issues.append("DEPTH_CEILING_HIT")

    return issues


def run_smoke_seed_batch(deck,base_seed:int,count:int,step:int,max_turn:int,beam:int,
                         depth:int,slow_seconds:float,progress_seconds:float=10.0):
    """
    Sequential deterministic Oracle-Mode rules-engine audit.

    This intentionally uses ONE process so runtime differences are attributable
    to game-tree behavior rather than multiprocessing/RAM contention.
    """
    print("\n=== ORACLE SMOKE-SEED BATCH ===",flush=True)
    print(
        f"count={count} base_seed={base_seed} step={step} turns={max_turn} "
        f"beam={beam} action_cap={ACTION_CAP} depth={depth}",
        flush=True
    )

    rows=[]
    batch_t0=time.time()

    for i in range(count):
        seed=base_seed+i*step
        print(f"\n[SMOKE {i+1}/{count}] START seed={seed}",flush=True)
        t0=time.time()
        r=oracle_game(
            seed,deck,max_turn,beam,depth,
            live_progress=True,progress_seconds=progress_seconds
        )
        dt=time.time()-t0
        issues=audit_oracle_result(r,depth)

        if dt>=slow_seconds:
            issues.append(f"SLOW_SEED>{slow_seconds:g}s")

        row={
            "seed":seed,
            "wall_seconds":dt,
            "win_turn":r.get("win_turn"),
            "urza_cast_turn":r.get("urza_cast_turn"),
            "family":r.get("family",""),
            "keep_size":r.get("keep_size"),
            "mulligan_stage":r.get("mulligan_stage"),
            "max_depth_reached":r.get("max_depth_reached"),
            "states":r.get("states"),
            "oracle_states_total":r.get("oracle_states_total",r.get("states",0)),
            "graph":r.get("graph",{}),
            "issues":issues,
            "opening7":r.get("opening7",[]),
            "bottom":r.get("bottom",[]),
            "kept_hand":r.get("kept_hand",[]),
        }
        rows.append(row)

        status="PASS" if not issues else "FLAG:"+"|".join(issues)
        print(
            f"[SMOKE {i+1}/{count}] DONE seed={seed} "
            f"time={dt:.2f}s win={row['win_turn'] if row['win_turn'] is not None else '-'} "
            f"urza={row['urza_cast_turn'] if row['urza_cast_turn'] else '-'} "
            f"keep={row['keep_size']} depth={row['max_depth_reached']} "
            f"selected_states={row['states']:,} oracle_states={row['oracle_states_total']:,} "
            f"edges={row['graph'].get('edges_generated',0):,} "
            f"bf={row['graph'].get('average_branching_factor',0):.2f} "
            f"family={row['family'] or '-'} | {status}",
            flush=True
        )

    wall=time.time()-batch_t0
    print("\n=== SMOKE-SEED SUMMARY ===",flush=True)

    wins=[x for x in rows if x["win_turn"] is not None]
    flagged=[x for x in rows if x["issues"]]
    fam=Counter(x["family"] for x in wins if x["family"])
    urza_turns=Counter(x["urza_cast_turn"] for x in wins if x["urza_cast_turn"])
    win_turns=Counter(x["win_turn"] for x in wins)

    for x in sorted(rows,key=lambda z:z["wall_seconds"],reverse=True):
        flags=";".join(x["issues"]) if x["issues"] else "-"
        print(
            f"seed={x['seed']} {x['wall_seconds']:7.2f}s "
            f"win={str(x['win_turn'] or '-'):>2} urza={str(x['urza_cast_turn'] or '-'):>2} "
            f"keep={x['keep_size']} depth={x['max_depth_reached']:3d} "
            f"sel={x['states']:8,d} total={x['oracle_states_total']:9,d} "
            f"edges={x['graph'].get('edges_generated',0):10,d} "
            f"bf={x['graph'].get('average_branching_factor',0):5.2f} | "
            f"{x['family'] or '-'} | {flags}",
            flush=True
        )

    print(f"\nBatch wall time: {wall:.2f}s",flush=True)
    print(f"Wins: {len(wins)}/{count}",flush=True)
    print(f"Win turns: {dict(sorted(win_turns.items()))}",flush=True)
    print(f"Urza cast turns among wins: {dict(sorted(urza_turns.items()))}",flush=True)
    print(f"Win families: {dict(fam)}",flush=True)
    print(f"Flagged seeds: {len(flagged)}/{count}",flush=True)

    out={
        "config":{
            "base_seed":base_seed,"count":count,"step":step,"turns":max_turn,
            "beam":beam,"action_cap":ACTION_CAP,"depth":depth,
            "slow_seconds":slow_seconds,
        },
        "batch_wall_seconds":wall,
        "wins":len(wins),
        "flagged":len(flagged),
        "win_turns":dict(win_turns),
        "urza_cast_turns":dict(urza_turns),
        "families":dict(fam),
        "rows":rows,
    }
    Path("smoke_seed_report.json").write_text(json.dumps(out,indent=2),encoding="utf-8")
    print("Wrote smoke_seed_report.json",flush=True)
    return rows



def run_cam_smoke():
    print("\n=== CAM / KNACK / HELIX CORRECTNESS SMOKE ===",flush=True)

    assert "Sewer-veillance Cam" in ARTIFACTS
    assert mana_value("Sewer-veillance Cam")==1
    print("Cam classified as MV1 artifact: PASS",flush=True)

    # Cam can actually be cast and resolves ETB.
    s=State(
        turn=4,library=(),hand=("Sewer-veillance Cam",),
        battlefield=(Perm(COMMANDER,sick=False),Perm("Battered Golem",tapped=True,sick=False)),
        blue=1,urza=True,commander_in_command_zone=False
    )
    cs=cast_from_hand(s,"Sewer-veillance Cam")
    assert cs is not None
    assert has(cs,"Sewer-veillance Cam")
    assert has(cs,"Battered Golem")
    print("Cam cast_from_hand + artifact ETB path: PASS",flush=True)

    # Artifact tutors must see Cam.
    lib=("Sewer-veillance Cam","Sensei's Divining Top","Island")
    s=State(
        turn=4,library=lib,hand=("Transmute Artifact",),
        battlefield=(Perm("Tormod's Crypt"),Perm(COMMANDER,sick=False)),
        blue=2,colorless=1,urza=True,commander_in_command_zone=False
    )
    ats=artifact_tutor_actions(s)
    assert any(has(x,"Sewer-veillance Cam") for x in ats)
    print("Transmute Artifact can find Cam: PASS",flush=True)

    # Current-turn Knack effect + Cam + live creature is terminal.
    s=State(
        turn=4,library=(),hand=(),
        battlefield=(
            Perm(COMMANDER,sick=False),
            Perm("Sewer-veillance Cam"),
            Perm("Battered Golem",sick=False,tapped=False),
        ),
        urza=True,commander_in_command_zone=False,
        knack_target="Battered Golem",
        graveyard=("Banishing Knack",)
    )
    w=check_win(s)
    assert w.won and w.win_family=="Knack/Helix + Cam"
    print("Cam + active current-turn Knack target wins: PASS",flush=True)

    # Old Knack in graveyard from a previous turn is NOT enough.
    stale=replace(s,knack_target="")
    assert not check_win(stale).won
    print("stale graveyard Knack does not false-positive: PASS",flush=True)

    # Sick/tapped target is not terminal until it can actually activate.
    sick=replace(s,battlefield=(
        Perm(COMMANDER,sick=False),
        Perm("Sewer-veillance Cam"),
        Perm("Battered Golem",sick=True,tapped=False),
    ))
    assert not check_win(sick).won
    tapped=replace(s,battlefield=(
        Perm(COMMANDER,sick=False),
        Perm("Sewer-veillance Cam"),
        Perm("Battered Golem",sick=False,tapped=True),
    ))
    assert not check_win(tapped).won
    print("summoning sickness / tapped target enforced: PASS",flush=True)

    # Spellseeker tutor pool includes both Knacks and Transmute.
    s=State(
        turn=4,
        library=("Banishing Knack","Retraction Helix","Transmute Artifact","Island"),
        hand=(),
        battlefield=()
    )
    ts=set(tutor_targets(s,"spellseeker"))
    assert {"Banishing Knack","Retraction Helix","Transmute Artifact"} <= ts
    print("Spellseeker tutor chain pieces present: PASS",flush=True)

    # Cam sacrifice LTB should resolve once and draw two.
    s=State(
        turn=4,library=("Island","Sol Ring","Island"),hand=(),
        battlefield=(
            Perm(COMMANDER,sick=False),
            Perm("Sewer-veillance Cam"),
            Perm("Battered Golem",sick=False,tapped=True),
        ),
        blue=4,urza=True,commander_in_command_zone=False,
        knack_target="Battered Golem"
    )
    acts=draw_sac_actions(s)
    cams=[x for x in acts if not has(x,"Sewer-veillance Cam")]
    assert cams
    c=cams[0]
    assert len(c.hand)>=2
    assert any(p.name=="Battered Golem" and not p.tapped for p in c.battlefield)
    print("Cam 3U sacrifice: one LTB untap + draw 2: PASS",flush=True)

    print("CAM SMOKE: ALL PASS",flush=True)



def run_metadata_smoke(deck_path:Path):
    print("\n=== DECK METADATA / TUTOR / X-COST AUDIT ===",flush=True)

    cards=[]
    for line in deck_path.read_text(encoding="utf-8").splitlines():
        line=line.strip()
        if not line: continue
        n,name=line.split(" ",1)
        if name!=COMMANDER:
            cards.extend([name]*int(n))
    unique=set(cards)

    expected_artifacts={
        "Aether Spellbomb","Basalt Monolith","Battered Golem","Chrome Dome","Chrome Mox",
        "Codex Shredder","Defense Grid","Disruptor Flute","Everflowing Chalice",
        "Giant's Boulder","Grafdigger's Cage","Grim Monolith","Grinding Station",
        "Hope of Ghirapur","Imposter Mech","Jeweled Amulet","Lotus Petal","Mana Vault",
        "Manifold Key","Mishra's Bauble","Moonsnare Prototype","Mox Diamond","Mox Opal",
        "Pithing Needle","Prized Statue","Repurposing Bay","Sapphire Medallion",
        "Seat of the Synod","Sensei's Divining Top","Sewer-veillance Cam","Sol Ring",
        "Spellskite","The One Ring","The Reality Chip","Tormod's Crypt","Urza's Bauble",
        "Uthros Research Craft","Vexing Bauble","Voltaic Key","Welding Jar","Witching Well",
    }
    assert ARTIFACTS==expected_artifacts, (
        "artifact mismatch missing="+str(sorted(expected_artifacts-ARTIFACTS))+
        " extra="+str(sorted(ARTIFACTS-expected_artifacts))
    )
    assert "Forensic Gadgeteer" not in ARTIFACTS
    assert {"Sol Ring","Mana Vault","Sewer-veillance Cam"} <= ARTIFACTS
    print("artifact card designations: PASS",flush=True)

    expected_creatures={
        "Artificer's Assistant","Battered Golem","Chrome Dome","Faerie Mastermind",
        "Forensic Gadgeteer","Hope of Ghirapur","Hydroelectric Specimen","Spellseeker",
        "Spellskite","The Reality Chip","Valley Floodcaller",
    }
    assert CREATURES==expected_creatures
    print("creature card designations: PASS",flush=True)

    # Every nonland deck card should now have a known base cost.
    missing=[c for c in sorted(unique) if c not in TRUE_LAND_CARDS and c not in COST]
    assert not missing, "missing COST entries: "+str(missing)
    assert all(mana_value(c)!=99 for c in unique)
    print("all 99 cards have known mana-value semantics: PASS",flush=True)

    # Critical printed costs / MV.
    assert COST["Aether Spellbomb"]==(1,0) and mana_value("Aether Spellbomb")==1
    assert COST["Witching Well"]==(0,1) and mana_value("Witching Well")==1
    assert COST["Sewer-veillance Cam"]==(0,1) and mana_value("Sewer-veillance Cam")==1
    assert COST["Sol Ring"]==(1,0) and COST["Mana Vault"]==(1,0)
    assert mana_value("Jeweled Amulet")==0 and mana_value("Mishra's Bauble")==0
    assert mana_value("Seat of the Synod")==0
    print("critical artifact costs / land MV0: PASS",flush=True)

    # X / MDFC / Phyrexian mana values off the stack.
    assert mana_value("Everflowing Chalice")==0
    assert mana_value("Reshape")==2
    assert mana_value("Whir of Invention")==3
    assert mana_value("Gitaxian Probe")==1
    assert mana_value("Mental Misstep")==1
    assert mana_value("Hydroelectric Specimen")==3
    assert mana_value("Sink into Stupor")==3
    assert mana_value("Sea Gate Restoration")==7
    print("X / Phyrexian / MDFC mana values: PASS",flush=True)

    # Urza's Saga checks PRINTED {0}/{1}, not merely MV<=1.
    assert {"Aether Spellbomb","Mana Vault","Sol Ring","Jeweled Amulet"} <= SAGA_TARGETS
    assert not ({"Witching Well","Sewer-veillance Cam","Moonsnare Prototype","Seat of the Synod"} & SAGA_TARGETS)
    print("Urza's Saga printed-mana-cost target set: PASS",flush=True)

    # Tutor legality from a library containing the whole deck.
    st=State(turn=1,library=tuple(cards),hand=(),battlefield=())

    dz=set(tutor_targets(st,"dizzy"))
    assert {"Fortune Teller's Talent","Sol Ring","Mana Vault","Aether Spellbomb","Witching Well","Sewer-veillance Cam"} <= dz
    assert "Power Artifact" not in dz

    md=set(tutor_targets(st,"muddle"))
    assert {"Power Artifact","Chrome Dome","Grim Monolith","Grinding Station","The Reality Chip",
            "Reshape","Transmute Artifact","Mana Drain"} <= md
    assert "Forensic Gadgeteer" not in md

    ss=set(tutor_targets(st,"spellseeker"))
    assert {"Reshape","Transmute Artifact","Muddle the Mixture","Dizzy Spell",
            "Merchant Scroll","Pact of Negation"} <= ss
    assert not ({"Whir of Invention","Sink into Stupor","Force of Negation"} & ss)

    mt=set(tutor_targets(st,"mystical"))
    assert (INSTANTS|SORCERIES) <= mt

    ms=set(tutor_targets(st,"merchant"))
    assert INSTANTS <= ms
    assert not ({"Reshape","Transmute Artifact","Merchant Scroll","Sea Gate Restoration"} & ms)
    assert {"Dizzy Spell","Scour for Scrap","Whir of Invention","Sink into Stupor","Force of Will","Pact of Negation"} <= ms
    print("Dizzy / Muddle / Spellseeker / Mystical / Merchant eligibility: PASS",flush=True)

    # Forensic must not be artifact-tutorable, while Sol/Vault must be.
    assert "Forensic Gadgeteer" not in ARTIFACTS
    assert {"Sol Ring","Mana Vault"} <= ARTIFACTS
    print("artifact tutors cannot find Gadgeteer and can find Sol/Vault: PASS",flush=True)

    # Sapphire Medallion reduces generic X portion of blue X spells.
    sm=State(
        turn=3,library=(),hand=(),battlefield=(Perm("Sapphire Medallion"),),
        blue=3,colorless=0
    )
    assert x_generic_cost(sm,"Reshape",1)==0
    assert x_generic_cost(sm,"Whir of Invention",1)==0
    assert x_generic_cost(sm,"Reshape",3)==2
    print("Sapphire Medallion applies to generic X portion: PASS",flush=True)

    # Reality Chip is a creature while unattached, noncreature while reconfigured.
    assert is_creature_perm(Perm("The Reality Chip"))
    assert not is_creature_perm(Perm("The Reality Chip",mode="chip_attached"))
    assert is_creature_perm(Perm("Chrome Dome"))
    print("Reality Chip / Chrome Dome creature status: PASS",flush=True)

    # Transmute Artifact can deliberately decline a positive MV difference.
    st=State(
        turn=3,
        library=("Basalt Monolith","Island"),
        hand=("Transmute Artifact",),
        battlefield=(Perm("Tormod's Crypt"),),
        blue=2,colorless=0
    )
    ta=artifact_tutor_actions(st)
    assert any("decline" in x.trace[-1] and "Basalt Monolith" in x.graveyard for x in ta)
    print("Transmute Artifact unpaid-difference graveyard branch: PASS",flush=True)

    print("METADATA SMOKE: ALL PASS",flush=True)




def spellseeker_etb_actions(s:State)->List[State]:
    """Smoke/helper wrapper: return only Spellseeker ETB tutor branches."""
    out=[]
    for i,p in enumerate(s.battlefield):
        if p.name=="Spellseeker" and p.mode!="used":
            for t in tutor_targets(s,"spellseeker"):
                ns=move_library_to_hand(s,t)
                ns=update_perm(ns,i,mode="used")
                ns=replace(ns,library=shuffled_library(ns,"spellseeker:"+t))
                out.append(add_trace(ns,f"Spellseeker ETB -> {t}"))
    return out


def run_tutor_smoke():
    print("\n=== TUTOR EXECUTION SMOKE ===",flush=True)

    # Dizzy transmute -> MV1 card into hand, library changes.
    s=State(
        turn=3,
        library=("Fortune Teller's Talent","Island","Sol Ring"),
        hand=("Dizzy Spell",),
        battlefield=(),
        blue=3
    )
    acts=simple_tutor_actions(s)
    assert any("Fortune Teller's Talent" in a.hand for a in acts)
    print("Dizzy transmute execution: PASS",flush=True)

    # Muddle transmute -> MV2 card.
    s=State(
        turn=3,
        library=("Power Artifact","Island","Chrome Dome"),
        hand=("Muddle the Mixture",),
        battlefield=(),
        blue=3
    )
    acts=simple_tutor_actions(s)
    assert any("Power Artifact" in a.hand for a in acts)
    print("Muddle transmute execution: PASS",flush=True)

    # Merchant Scroll -> instant only.
    s=State(
        turn=3,
        library=("Whir of Invention","Reshape","Island"),
        hand=("Merchant Scroll",),
        battlefield=(),
        blue=2
    )
    acts=simple_tutor_actions(s)
    assert any("Whir of Invention" in a.hand for a in acts)
    assert not any("Reshape" in a.hand for a in acts)
    print("Merchant Scroll execution/type restriction: PASS",flush=True)

    # Mystical Tutor puts target on top after search/shuffle.
    s=State(
        turn=3,
        library=("Whir of Invention","Island","Power Artifact"),
        hand=("Mystical Tutor",),
        battlefield=(),
        blue=1
    )
    acts=simple_tutor_actions(s)
    assert any(a.library and a.library[0]=="Whir of Invention" for a in acts)
    print("Mystical Tutor top placement: PASS",flush=True)

    # Spellseeker ETB can find Knack.
    s=State(
        turn=3,
        library=("Banishing Knack","Island","Transmute Artifact"),
        hand=(),
        battlefield=(Perm("Spellseeker",mode="fresh"),)
    )
    acts=spellseeker_etb_actions(s)
    assert any("Banishing Knack" in a.hand for a in acts)
    print("Spellseeker ETB tutor execution: PASS",flush=True)

    # Artifact tutor smoke including Cam and Sol Ring.
    s=State(
        turn=3,
        library=("Sewer-veillance Cam","Sol Ring","Island"),
        hand=("Transmute Artifact",),
        battlefield=(Perm("Tormod's Crypt"),),
        blue=2,colorless=1
    )
    acts=artifact_tutor_actions(s)
    assert any(has(a,"Sewer-veillance Cam") or has(a,"Sol Ring") for a in acts)
    print("artifact tutor execution: PASS",flush=True)

    print("TUTOR SMOKE: ALL PASS",flush=True)



def _combo_path_find(start:State, expected_families:set, max_depth:int=8, beam:int=1200,
                     required_trace_terms:Tuple[str,...]=()):
    """Bounded integration search using the real legal_actions/check_win engine."""
    start=check_win(start)
    frontier=[start]
    seen={start.key()}
    searched=0

    for depth in range(0,max_depth+1):
        nxt=[]
        for st in frontier:
            searched+=1
            if st.won and st.win_family in expected_families:
                joined="\n".join(st.trace)
                if all(term in joined for term in required_trace_terms):
                    return st,depth,searched

            if depth==max_depth:
                continue

            for ns in legal_actions(st):
                ns=check_win(ns)
                k=ns.key()
                if k not in seen:
                    seen.add(k)
                    nxt.append(ns)

        if not nxt:
            break
        frontier=heapq.nlargest(min(beam,len(nxt)),nxt,key=score)

    return None,None,searched


def _combo_smoke_case(name:str,start:State,expected:set,max_depth:int=8,
                      required_trace_terms:Tuple[str,...]=()):
    t0=time.time()
    result,depth,searched=_combo_path_find(
        start,expected,max_depth=max_depth,required_trace_terms=required_trace_terms
    )
    dt=time.time()-t0
    if result is None:
        raise AssertionError(
            f"{name}: expected {sorted(expected)} not found by depth {max_depth}; "
            f"required_trace_terms={required_trace_terms}; searched={searched}"
        )

    print(
        f"{name:38s} PASS | depth={depth:2d} searched={searched:5d} "
        f"time={dt:6.3f}s | {result.win_family}",
        flush=True
    )
    for x in result.trace[-min(8,len(result.trace)):]:
        print(f"    {x}",flush=True)
    return result


def run_combo_smoke():
    print("\n=== MAJOR COMBO PATH SMOKE SUITE ===",flush=True)

    # 1. PA + Grim.
    s=State(
        turn=4,library=(),hand=("Power Artifact",),
        battlefield=(Perm(COMMANDER,sick=False),Perm("Grim Monolith")),
        blue=2,colorless=0,urza=True,commander_in_command_zone=False
    )
    _combo_smoke_case("Power Artifact + Grim",s,{"Power Artifact + Grim"},4,
                      ("Power Artifact enchants Grim Monolith",))

    # 2. PA + Basalt.
    s=State(
        turn=4,library=(),hand=("Power Artifact",),
        battlefield=(Perm(COMMANDER,sick=False),Perm("Basalt Monolith")),
        blue=2,colorless=0,urza=True,commander_in_command_zone=False
    )
    _combo_smoke_case("Power Artifact + Basalt",s,{"Power Artifact + Basalt"},4,
                      ("Power Artifact enchants Basalt Monolith",))

    # 3. Basalt + Gadgeteer.
    s=State(
        turn=4,library=(),hand=("Basalt Monolith",),
        battlefield=(Perm(COMMANDER,sick=False),Perm("Forensic Gadgeteer",sick=False)),
        blue=0,colorless=3,urza=True,commander_in_command_zone=False
    )
    _combo_smoke_case("Basalt + Gadgeteer",s,{"Basalt + Gadgeteer"},4,
                      ("cast Basalt Monolith",))

    # 4. Top + attached Chip + producer.
    s=State(
        turn=4,library=("Island","Sol Ring"),hand=("Sensei's Divining Top",),
        battlefield=(
            Perm(COMMANDER,sick=False),
            Perm("The Reality Chip",mode="chip_attached"),
            Perm("Grinding Station"),
        ),
        blue=1,colorless=0,urza=True,commander_in_command_zone=False,
        chip_attached=True,chip_target=COMMANDER
    )
    _combo_smoke_case("Top + Reality Chip + producer",s,{"Top + Reality Chip"},4,
                      ("cast Sensei's Divining Top",))

    # 5. FTT L3: require a spell first, then Top.
    # We start with no Top in play so the terminal cannot already be true.
    s=State(
        turn=4,library=("Island","Sol Ring"),
        hand=("Tormod's Crypt","Sensei's Divining Top"),
        battlefield=(Perm(COMMANDER,sick=False),Perm("Fortune Teller's Talent")),
        blue=1,colorless=0,urza=True,commander_in_command_zone=False,
        ftt_level=3,spell_cast_this_turn=False
    )
    _combo_smoke_case("Top + FTT L3",s,{"Top + FTT L3"},5,
                      ("cast Sensei's Divining Top",))

    # 6. FTT L2 + producer.
    s=State(
        turn=4,library=("Island","Sol Ring"),
        hand=("Tormod's Crypt","Sensei's Divining Top"),
        battlefield=(
            Perm(COMMANDER,sick=False),Perm("Fortune Teller's Talent"),
            Perm("Grinding Station"),
        ),
        blue=1,colorless=0,urza=True,commander_in_command_zone=False,
        ftt_level=2,spell_cast_this_turn=False
    )
    _combo_smoke_case("Top + FTT L2 + producer",s,{"Top + FTT L2 + producer"},5,
                      ("cast Sensei's Divining Top",))

    # 7. Gadgeteer + Top + Station.
    s=State(
        turn=4,library=("Island","Sol Ring"),hand=("Sensei's Divining Top",),
        battlefield=(
            Perm(COMMANDER,sick=False),
            Perm("Forensic Gadgeteer",sick=False),
            Perm("Grinding Station"),
        ),
        blue=1,colorless=0,urza=True,commander_in_command_zone=False
    )
    _combo_smoke_case("Top + Gadgeteer + producer",s,{"Top + Gadgeteer + producer"},4,
                      ("cast Sensei's Divining Top",))

    # 8. Chrome Dome + Station.
    s=State(
        turn=4,library=(),hand=("Chrome Dome",),
        battlefield=(Perm(COMMANDER,sick=False),Perm("Grinding Station")),
        blue=0,colorless=7,urza=True,commander_in_command_zone=False
    )
    _combo_smoke_case("Chrome Dome + Station",s,{"Chrome Dome"},5,("cast Chrome Dome",))

    # 9. Chrome Dome + Golem.
    s=State(
        turn=4,library=(),hand=("Chrome Dome",),
        battlefield=(Perm(COMMANDER,sick=False),Perm("Battered Golem",sick=False)),
        blue=0,colorless=7,urza=True,commander_in_command_zone=False
    )
    _combo_smoke_case("Chrome Dome + Golem",s,{"Chrome Dome"},5,("cast Chrome Dome",))

    # 10. Knack + Cam + Golem.
    s=State(
        turn=4,library=(),hand=("Banishing Knack","Sewer-veillance Cam"),
        battlefield=(Perm(COMMANDER,sick=False),Perm("Battered Golem",sick=False)),
        blue=2,colorless=0,urza=True,commander_in_command_zone=False
    )
    _combo_smoke_case("Knack + Cam + Golem",s,{"Knack/Helix + Cam"},6,
                      ("cast Banishing Knack","cast Sewer-veillance Cam"))

    # 11. Helix + Cam + VFC.
    s=State(
        turn=4,library=(),hand=("Retraction Helix","Sewer-veillance Cam"),
        battlefield=(Perm(COMMANDER,sick=False),Perm("Valley Floodcaller",sick=False)),
        blue=2,colorless=0,urza=True,commander_in_command_zone=False
    )
    _combo_smoke_case("Helix + Cam + VFC",s,{"Knack/Helix + Cam"},6,
                      ("cast Retraction Helix","cast Sewer-veillance Cam"))

    # 12. Spellseeker full chain.
    # Keep total mana BELOW 5 to prohibit Urza spin. Spellseeker must:
    # ETB tutor Knack/Helix -> cast it -> bounce Spellseeker -> replay it ->
    # tutor Transmute -> use Tormod's Crypt to find Cam -> terminal.
    s=State(
        turn=5,
        library=(
            "Banishing Knack","Retraction Helix","Transmute Artifact",
            "Sewer-veillance Cam","Island"
        ),
        hand=(),
        battlefield=(
            Perm(COMMANDER,sick=False),
            Perm("Spellseeker",sick=False,mode="fresh"),
            Perm("Battered Golem",sick=False),
            Perm("Tormod's Crypt"),
        ),
        blue=4,colorless=0,urza=True,commander_in_command_zone=False
    )
    _combo_smoke_case(
        "Spellseeker -> Knack -> Transmute -> Cam",
        s,{"Knack/Helix + Cam"},12,
        ("Spellseeker ETB ->","Transmute","Sewer-veillance Cam")
    )

    # 13. Knack/Golem + mana-positive artifact: assert the engine setup action exists.
    s=State(
        turn=5,library=(),hand=("Banishing Knack","Lotus Petal"),
        battlefield=(Perm(COMMANDER,sick=False),Perm("Battered Golem",sick=False)),
        blue=1,colorless=0,urza=True,commander_in_command_zone=False
    )
    acts=legal_actions(s)
    assert any(x.knack_target for x in acts)
    print("Knack + Golem + positive artifact       PASS | Knack engine setup reachable",flush=True)

    # 14. Station ETB conversion. By solver convention, artifact ETB untap is
    # immediately converted into mana rather than leaving Station untapped.
    s=State(
        turn=4,library=(),hand=("Tormod's Crypt",),
        battlefield=(Perm(COMMANDER,sick=False),Perm("Grinding Station",tapped=True)),
        blue=0,colorless=0,urza=True,commander_in_command_zone=False
    )
    acts=legal_actions(s)
    casts=[x for x in acts if has(x,"Tormod's Crypt")]
    assert casts
    assert any(x.blue>s.blue for x in casts), "Station ETB was not converted into mana"
    print("Grinding Station artifact-ETB mana     PASS | immediate mana conversion reachable",flush=True)

    # 15. Golem ETB conversion.
    s=State(
        turn=4,library=(),hand=("Tormod's Crypt",),
        battlefield=(Perm(COMMANDER,sick=False),Perm("Battered Golem",tapped=True,sick=False)),
        blue=0,colorless=0,urza=True,commander_in_command_zone=False
    )
    acts=legal_actions(s)
    casts=[x for x in acts if has(x,"Tormod's Crypt")]
    assert casts
    assert any(x.blue>s.blue for x in casts), "Golem ETB was not converted into mana"
    print("Battered Golem artifact-ETB mana       PASS | immediate mana conversion reachable",flush=True)

    # 16. Uthros + Station dedicated branch generation.
    s=State(
        turn=5,library=("Sol Ring","Island","Mishra's Bauble"),hand=(),
        battlefield=(
            Perm(COMMANDER,sick=False),
            Perm("Grinding Station"),
            Perm("Uthros Research Craft",sick=False),
            Perm("Construct",sick=False,mode="construct"),
        ),
        blue=2,colorless=2,urza=True,construct=True,
        commander_in_command_zone=False,uthros_counters=3
    )
    ua=uthros_station_actions(s)
    assert ua
    print("Uthros + Station dedicated actions     PASS | branches generated",flush=True)

    print("\nCOMBO SMOKE: ALL PASS",flush=True)



def run_family_smoke(deck,base_seed:int,count:int,max_turn:int,beam:int,depth:int,
                     progress_seconds:float=10.0):
    print("\n=== NATURAL WIN-FAMILY SMOKE ===",flush=True)
    fam=Counter()
    rows=[]
    cam_hits=0
    t0=time.time()

    for i in range(count):
        seed=base_seed+i
        print(f"\n[FAMILY {i+1}/{count}] seed={seed}",flush=True)
        r=oracle_game(
            seed,deck,max_turn,beam,depth,
            live_progress=True,progress_seconds=progress_seconds
        )
        family=r.get("family","")
        fam[family or "NO WIN"] += 1
        if "Knack/Helix + Cam" in family:
            cam_hits += 1

        g=r.get("graph",{})
        row={
            "seed":seed,
            "win_turn":r.get("win_turn"),
            "urza_cast_turn":r.get("urza_cast_turn"),
            "keep_size":r.get("keep_size"),
            "family":family,
            "oracle_states_total":r.get("oracle_states_total",0),
            "graph":g,
        }
        rows.append(row)

        print(
            f"[FAMILY] seed={seed} win={r.get('win_turn') or '-'} "
            f"urza={r.get('urza_cast_turn') or '-'} keep={r.get('keep_size')} "
            f"family={family or '-'} nodes={g.get('nodes_expanded',0):,} "
            f"edges={g.get('edges_generated',0):,} "
            f"bf={g.get('average_branching_factor',0):.2f}",
            flush=True
        )

    print("\n=== FAMILY SUMMARY ===",flush=True)
    for k,v in fam.most_common():
        print(f"{k or 'NO WIN'}: {v}",flush=True)
    print(f"Natural Cam/Knack wins: {cam_hits}/{count}",flush=True)
    print(f"Wall time: {time.time()-t0:.2f}s",flush=True)

    payload={
        "base_seed":base_seed,
        "count":count,
        "families":dict(fam),
        "cam_hits":cam_hits,
        "rows":rows,
    }
    Path("family_smoke_report.json").write_text(json.dumps(payload,indent=2),encoding="utf-8")
    print("Wrote family_smoke_report.json",flush=True)



def run_cap_audit(deck,base_seed:int,count:int,max_turn:int,beam:int,depth:int,progress_seconds:float=10.0):
    global _CAP_AUDIT
    _CAP_AUDIT=new_cap_audit_stats()
    rows=[]
    t0=time.time()
    print("\n=== PRE-CAP LEGAL-ACTION AUDIT ===",flush=True)
    print(f"ACTION_CAP={ACTION_CAP} seeds={count} base={base_seed}",flush=True)
    try:
        for i in range(count):
            seed=base_seed+i
            before=dict(serializable_cap_audit(_CAP_AUDIT))
            print(f"\n[CAP {i+1}/{count}] seed={seed}",flush=True)
            st0=_CAP_AUDIT["states_truncated"]
            raw0=_CAP_AUDIT["raw_actions_total"]
            r=oracle_game(seed,deck,max_turn,beam,depth,live_progress=True,progress_seconds=progress_seconds)
            st1=_CAP_AUDIT["states_truncated"]
            raw1=_CAP_AUDIT["raw_actions_total"]
            row={
                "seed":seed,"win_turn":r.get("win_turn"),"family":r.get("family",""),
                "oracle_nodes":r.get("graph",{}).get("nodes_expanded",0),
                "oracle_edges_post_cap":r.get("graph",{}).get("edges_generated",0),
                "cap_states_truncated_delta":st1-st0,
                "raw_actions_delta":raw1-raw0,
            }
            rows.append(row)
            print(
                f"[CAP] seed={seed} win={r.get('win_turn') or '-'} family={r.get('family') or '-'} "
                f"truncated_states+={st1-st0:,} raw_actions+={raw1-raw0:,}",flush=True
            )
    finally:
        summary=serializable_cap_audit(_CAP_AUDIT)
        summary["action_cap"]=ACTION_CAP
        summary["base_seed"]=base_seed
        summary["count"]=count
        summary["rows"]=rows
        summary["wall_seconds"]=time.time()-t0
        Path("cap_audit_report.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
        print("\n=== CAP AUDIT SUMMARY ===",flush=True)
        print(f"states evaluated: {summary['states_seen']:,}",flush=True)
        print(f"states actually truncated: {summary['states_truncated']:,} ({100*summary['truncation_rate']:.3f}%)",flush=True)
        print(f"max pre-cap legal actions: {summary['max_pre_cap_actions']:,}",flush=True)
        print(f"raw actions total: {summary['raw_actions_total']:,}",flush=True)
        print(f"discarded by ACTION_CAP: {summary['discarded_actions_total']:,}",flush=True)
        print(f"mean raw actions/state: {summary['mean_raw_actions']:.3f}",flush=True)
        print(f"mean discarded / truncated state: {summary['mean_discarded_when_truncated']:.2f}",flush=True)
        print("dropped action families:",dict(sorted(summary['truncated_dropped_families'].items(),key=lambda kv:kv[1],reverse=True)),flush=True)
        print("Wrote cap_audit_report.json",flush=True)
        _CAP_AUDIT=None



def run_tutor_cap_audit(deck,base_seed:int,count:int,max_turn:int,beam:int,depth:int,
                        progress_seconds:float=10.0):
    global _TUTOR_CAP_AUDIT_ENABLED,_TUTOR_CAP_AUDIT
    _TUTOR_CAP_AUDIT_ENABLED=True
    _TUTOR_CAP_AUDIT=new_tutor_cap_audit_stats()
    rows=[]
    t0=time.time()
    print("\n=== TUTOR CAP DIVERSITY AUDIT ===",flush=True)
    try:
        for i in range(count):
            seed=base_seed+i
            b_states=_TUTOR_CAP_AUDIT["tutor_truncated_states"]
            b_lost=_TUTOR_CAP_AUDIT["lost_target_events"]
            b_eng=_TUTOR_CAP_AUDIT["lost_engine_target_events"]
            print(f"\n[TUTOR CAP {i+1}/{count}] seed={seed}",flush=True)
            r=oracle_game(seed,deck,max_turn,beam,depth,live_progress=True,progress_seconds=progress_seconds)
            row={
                "seed":seed,
                "win_turn":r.get("win_turn"),
                "family":r.get("family",""),
                "tutor_truncated_states_delta":_TUTOR_CAP_AUDIT["tutor_truncated_states"]-b_states,
                "lost_target_events_delta":_TUTOR_CAP_AUDIT["lost_target_events"]-b_lost,
                "lost_engine_target_events_delta":_TUTOR_CAP_AUDIT["lost_engine_target_events"]-b_eng,
            }
            rows.append(row)
            print(
                f"[TUTOR CAP] seed={seed} win={row['win_turn'] or '-'} family={row['family'] or '-'} "
                f"tutor_cap_states={row['tutor_truncated_states_delta']} "
                f"lost_targets={row['lost_target_events_delta']} "
                f"lost_engine_targets={row['lost_engine_target_events_delta']}",
                flush=True
            )
    finally:
        _TUTOR_CAP_AUDIT_ENABLED=False

    a=_TUTOR_CAP_AUDIT
    print("\n=== TUTOR CAP AUDIT SUMMARY ===",flush=True)
    print(f"truncated states with tutor branches: {a['tutor_truncated_states']:,}",flush=True)
    print(f"raw tutor actions in those states: {a['raw_tutor_actions']:,}",flush=True)
    print(f"kept tutor actions in those states: {a['kept_tutor_actions']:,}",flush=True)
    print(f"unique tutor targets before cap (state-summed): {a['unique_targets_raw_total']:,}",flush=True)
    print(f"unique tutor targets after cap (state-summed): {a['unique_targets_kept_total']:,}",flush=True)
    print(f"lost target events: {a['lost_target_events']:,}",flush=True)
    print(f"lost KNOWN ENGINE target events: {a['lost_engine_target_events']:,}",flush=True)
    print(f"lost targets by frequency: {dict(a['lost_targets'].most_common())}",flush=True)
    print(f"lost engine targets by frequency: {dict(a['lost_engine_targets'].most_common())}",flush=True)
    print("\nTutor source retention:",flush=True)
    for src in sorted(set(a["source_counts_raw"])|set(a["source_counts_kept"])):
        raw=a["source_counts_raw"][src]; kept=a["source_counts_kept"][src]
        pct=(100*kept/raw) if raw else 100.0
        print(f"  {src:20s} raw={raw:7,d} kept={kept:7,d} retention={pct:6.2f}%",flush=True)

    payload={
        "base_seed":base_seed,"count":count,"action_cap":ACTION_CAP,
        "summary":{
            "truncated_states":a["truncated_states"],
            "tutor_truncated_states":a["tutor_truncated_states"],
            "raw_tutor_actions":a["raw_tutor_actions"],
            "kept_tutor_actions":a["kept_tutor_actions"],
            "unique_targets_raw_total":a["unique_targets_raw_total"],
            "unique_targets_kept_total":a["unique_targets_kept_total"],
            "lost_target_events":a["lost_target_events"],
            "lost_engine_target_events":a["lost_engine_target_events"],
            "lost_targets":dict(a["lost_targets"]),
            "lost_engine_targets":dict(a["lost_engine_targets"]),
            "source_counts_raw":dict(a["source_counts_raw"]),
            "source_counts_kept":dict(a["source_counts_kept"]),
            "target_counts_raw":dict(a["target_counts_raw"]),
            "target_counts_kept":dict(a["target_counts_kept"]),
        },
        "rows":rows,"worst_states":a["worst_states"],
        "wall_seconds":time.time()-t0,
    }
    Path("tutor_cap_audit_report.json").write_text(json.dumps(payload,indent=2),encoding="utf-8")
    print("\nWrote tutor_cap_audit_report.json",flush=True)


def main():
    global _parent_cancel_count
    _parent_cancel_count=0
    ap=argparse.ArgumentParser()
    ap.add_argument("--deck",default="decklist.txt")
    ap.add_argument("-n","--runs",type=int,default=100)
    ap.add_argument("--turns",type=int,default=7)
    ap.add_argument("--beam",type=int,default=2500)
    ap.add_argument("--depth",type=int,default=60,help="Maximum sequential state transitions explored per turn")
    ap.add_argument("--seed",type=int,default=20260821)
    ap.add_argument("--workers",type=int,default=max(1,(os.cpu_count() or 2)-1))
    ap.add_argument("--out",default="results")
    ap.add_argument("--trace-count",type=int,default=10)
    ap.add_argument("--progress-every",type=int,default=5,help="Print progress every N completed games")
    ap.add_argument("--heartbeat-seconds",type=int,default=15,help="True wall-clock heartbeat interval in seconds")
    ap.add_argument("--verbose-workers",action="store_true",help="Print START/DONE lines for every seed in worker processes")
    ap.add_argument("--error-log",default="errors.log",help="Error log filename inside output folder")
    ap.add_argument("--profile-one",action="store_true",help="Profile one deterministic opening 7; bypass oracle mulligans")
    ap.add_argument("--profile-oracle",action="store_true",help="Profile every oracle mulligan candidate for one seed")
    ap.add_argument("--chain-stress-test",action="store_true",help="Run synthetic developed-board Chain branching test and exit")
    ap.add_argument("--problem-smoke",action="store_true",help="Time likely branch-heavy action families on developed synthetic states")
    ap.add_argument("--cancel-test",action="store_true",help="Start sleeping worker pool to manually test Ctrl+C cleanup")
    ap.add_argument("--commander-smoke",action="store_true",help="Run command-zone/Urza correctness tests and exit")
    ap.add_argument("--cam-smoke",action="store_true",help="Run Sewer-veillance Cam + Knack/Helix correctness tests and exit")
    ap.add_argument("--metadata-smoke",action="store_true",help="Audit deck card types, mana values, tutor legality, Saga and X costs")
    ap.add_argument("--tutor-smoke",action="store_true",help="Exercise simple, Spellseeker, Mystical and artifact tutor execution paths")
    ap.add_argument("--combo-smoke",action="store_true",help="Exercise near-complete states for every major win family through normal legal actions")
    ap.add_argument("--family-smoke",type=int,default=0,help="Run N deterministic oracle seeds and report naturally occurring win families")
    ap.add_argument("--cap-audit",type=int,default=0,help="Run N deterministic oracle seeds and audit pre-cap legal-action branching")
    ap.add_argument("--tutor-cap-audit",type=int,default=0,help="Run N deterministic oracle seeds and audit tutor-target diversity lost to ACTION_CAP")
    ap.add_argument("--smoke-seeds",type=int,default=0,help="Run N deterministic oracle smoke seeds sequentially and audit invariants")
    ap.add_argument("--smoke-seed-step",type=int,default=1,help="Increment between smoke seeds")
    ap.add_argument("--smoke-slow-seconds",type=float,default=60.0,help="Flag a smoke seed slower than this")
    ap.add_argument("--search-progress-seconds",type=float,default=10.0,help="Live search heartbeat interval for smoke/profile diagnostics")
    ap.add_argument("--profile-turns",type=int,default=7,help="Turns to profile (default 7)")
    ap.add_argument("--action-cap",type=int,default=80,help="max successor actions retained per state")
    ap.add_argument("--bottom-cap",type=int,default=8,help="London bottom combinations tested at each hand size")
    args=ap.parse_args()
    signal.signal(signal.SIGINT,parent_interrupt_handler)
    if hasattr(signal,'SIGBREAK'):
        try:
            signal.signal(signal.SIGBREAK,parent_interrupt_handler)
        except Exception:
            pass
    global ACTION_CAP, BOTTOM_CAP
    ACTION_CAP=args.action_cap; BOTTOM_CAP=args.bottom_cap
    if args.cancel_test:
        run_cancel_test(args.workers)
        return
    if args.commander_smoke:
        run_commander_smoke()
        return
    if args.cam_smoke:
        run_cam_smoke()
        return
    if args.metadata_smoke:
        run_metadata_smoke(Path(args.deck))
        return
    if args.tutor_smoke:
        run_tutor_smoke()
        return
    if args.combo_smoke:
        run_combo_smoke()
        return
    deck=load_deck(Path(args.deck))
    if args.cap_audit>0:
        run_cap_audit(deck,args.seed,args.cap_audit,args.turns,args.beam,args.depth,args.search_progress_seconds)
        return
    if args.tutor_cap_audit>0:
        run_tutor_cap_audit(deck,args.seed,args.tutor_cap_audit,args.turns,args.beam,args.depth,args.search_progress_seconds)
        return
    if args.family_smoke>0:
        run_family_smoke(
            deck,args.seed,args.family_smoke,args.turns,args.beam,args.depth,
            args.search_progress_seconds
        )
        return
    if args.smoke_seeds>0:
        run_smoke_seed_batch(
            deck,
            base_seed=args.seed,
            count=args.smoke_seeds,
            step=args.smoke_seed_step,
            max_turn=args.turns,
            beam=args.beam,
            depth=args.depth,
            slow_seconds=args.smoke_slow_seconds,
            progress_seconds=args.search_progress_seconds,
        )
        return
    if args.chain_stress_test:
        run_chain_macro_smoke()
        return
    if args.problem_smoke:
        run_problem_smoke()
        return
    if args.profile_oracle:
        profile_oracle_seed(
            args.seed,deck,max_turn=args.profile_turns,
            beam=args.beam,depth=args.depth,bottom_cap=args.bottom_cap
        )
        return
    if args.profile_one:
        print(f"Profiling one opening candidate for seed={args.seed}",flush=True)
        profile_seed(args.seed,deck,args.profile_turns,args.beam,args.depth)
        return
    seeds=[args.seed+i for i in range(args.runs)]
    jobs=[(sd,deck,args.turns,args.beam,args.depth,args.verbose_workers) for sd in seeds]
    out=Path(args.out); out.mkdir(exist_ok=True)
    error_log_path=out/args.error_log

    start_wall=time.time()
    last_print=start_wall
    last_completion_wall=start_wall
    results=[]
    error_count=0
    completed=0
    progress_lock=threading.Lock()
    stop_heartbeat=threading.Event()

    def compact_progress_snapshot():
        with progress_lock:
            now=time.time()
            elapsed=max(1e-9,now-start_wall)
            rate=completed/elapsed if completed else 0.0
            since_done=now-last_completion_wall
            exact=Counter(r["win_turn"] for r in results if r.get("win_turn") is not None and not r.get("_error"))
            cum3=sum(v for t,v in exact.items() if t<=3)
            cum4=sum(v for t,v in exact.items() if t<=4)
            depth_hits=sum(1 for r in results if r.get("max_depth_reached",0)>=args.depth)
            return {
                "now":now,"elapsed":elapsed,"rate":rate,"since_done":since_done,
                "completed":completed,"errors":error_count,"cum3":cum3,"cum4":cum4,
                "depth_hits":depth_hits
            }

    def heartbeat_loop():
        # This thread is independent of game completion. It therefore continues
        # printing even while every worker is buried in its first expensive game.
        interval=max(2,args.heartbeat_seconds)
        while not stop_heartbeat.wait(interval):
            q=compact_progress_snapshot()
            remaining=args.runs-q["completed"]
            eta=(remaining/q["rate"]) if q["rate"]>0 else float("inf")
            eta_txt="unknown (no game finished yet)" if not math.isfinite(eta) else f"{eta/60:.1f}m"
            state_txt="SEARCHING" if q["completed"]<args.runs else "FINISHING"
            print(
                f"[heartbeat] {state_txt} | {q['completed']}/{args.runs} complete "
                f"({100*q['completed']/args.runs:5.1f}%) | elapsed {q['elapsed']:.0f}s | "
                f"last completion {q['since_done']:.0f}s ago | "
                f"rate {q['rate']:.3f} games/s | ETA {eta_txt} | "
                f"<=T3 {q['cum3']} <=T4 {q['cum4']} | "
                f"depth hits {q['depth_hits']} | errors {q['errors']} | "
                f"workers requested={args.workers}",
                flush=True
            )

    def progress_line(force=False):
        nonlocal last_print
        q=compact_progress_snapshot()
        if not force and q["completed"]>0 and q["completed"] % max(1,args.progress_every)!=0:
            return
        remaining=args.runs-q["completed"]
        eta=(remaining/q["rate"]) if q["rate"]>0 else float("inf")
        avg_states=(sum(r.get("states",0) for r in results)/len(results)) if results else 0
        avg_worker=(sum(r.get("_elapsed_worker_s",0) for r in results)/len(results)) if results else 0
        exact=Counter(r["win_turn"] for r in results if r.get("win_turn") is not None and not r.get("_error"))
        cum5=sum(v for t,v in exact.items() if t<=5)
        eta_txt="--" if not math.isfinite(eta) else f"{eta/60:.1f}m"
        denom=q["completed"] if q["completed"] else 1
        print(
            f"[progress] {q['completed']}/{args.runs} "
            f"({100*q['completed']/args.runs:5.1f}%) | "
            f"elapsed {q['elapsed']/60:.1f}m | {q['rate']:.3f} games/s | ETA {eta_txt} | "
            f"<=T3 {q['cum3']}/{denom} <=T4 {q['cum4']}/{denom} <=T5 {cum5}/{denom} | "
            f"depth hits {q['depth_hits']} | errors {q['errors']} | "
            f"avg states {avg_states:,.0f} | avg worker {avg_worker:.1f}s",
            flush=True
        )
        last_print=q["now"]

    print(
        f"Starting Urza solver: runs={args.runs}, workers={args.workers}, "
        f"beam={args.beam}, action_cap={ACTION_CAP}, depth={args.depth}, seed={args.seed}",
        flush=True
    )
    print(f"Output folder: {out.resolve()}", flush=True)
    print(f"True heartbeat: every {args.heartbeat_seconds}s even if 0 games have finished; progress every {args.progress_every} completions", flush=True)
    if args.verbose_workers:
        print("Worker seed START/DONE logging: ON", flush=True)
    else:
        print("Tip: add --verbose-workers to see exactly which seeds each process is working on.", flush=True)
    heartbeat_thread=threading.Thread(target=heartbeat_loop,name="solver-heartbeat",daemon=True)
    heartbeat_thread.start()

    cancelled=False
    try:
        if args.workers==1:
            for r in (worker(j) for j in jobs):
                with progress_lock:
                    completed += 1
                    last_completion_wall=time.time()
                if r.get("_error"):
                    with progress_lock:
                        error_count += 1
                    with error_log_path.open("a",encoding="utf-8") as ef:
                        ef.write(f"\n=== seed {r['seed']} ===\n{r['_error']}\n")
                    print(f"[ERROR] seed {r['seed']} failed; traceback written to {error_log_path}",flush=True)
                with progress_lock:
                    results.append(r)
                progress_line()
        else:
            pool=mp.Pool(args.workers, initializer=worker_process_initializer)
            pending={}
            try:
                # Submit independently so the parent never blocks waiting on one
                # long-running result. Each AsyncResult is polled from Python.
                for job in jobs:
                    ar=pool.apply_async(worker,(job,))
                    pending[ar]=job[0]

                while pending:
                    made_progress=False

                    for ar in list(pending.keys()):
                        if not ar.ready():
                            continue

                        seed_for_job=pending.pop(ar)
                        made_progress=True
                        try:
                            r=ar.get(timeout=0)
                        except Exception:
                            # Worker wrapper normally converts exceptions to an
                            # error result; this is a last-resort parent-side guard.
                            r={
                                "seed":seed_for_job,"win_turn":None,"family":"",
                                "mulligan_stage":-1,"keep_size":0,"bottom":[],
                                "opening7":[],"kept_hand":[],"urza_cast_turn":0,
                                "interaction_count":0,"interaction_seen":[],
                                "final_hand":[],"max_depth_reached":0,"states":0,
                                "trace":(),"_elapsed_worker_s":0,
                                "_error":traceback.format_exc(),
                            }

                        with progress_lock:
                            completed += 1
                            last_completion_wall=time.time()

                        if r.get("_error"):
                            with progress_lock:
                                error_count += 1
                            with error_log_path.open("a",encoding="utf-8") as ef:
                                ef.write(f"\n=== seed {r['seed']} ===\n{r['_error']}\n")
                            print(
                                f"[ERROR] seed {r['seed']} failed; traceback written to {error_log_path}",
                                flush=True
                            )

                        with progress_lock:
                            results.append(r)
                        progress_line()

                    # This is the critical Windows behavior change: never sit in
                    # an uninterruptible Pool iterator wait.
                    if pending and not made_progress:
                        time.sleep(0.20)

                pool.close()
                pool.join()

            except KeyboardInterrupt:
                cancelled=True
                print("[CANCEL] Terminating multiprocessing pool...",flush=True)
                try:
                    pool.terminate()
                finally:
                    try:
                        pool.join()
                    except Exception:
                        pass
                raise

            except BaseException:
                try:
                    pool.terminate()
                finally:
                    try:
                        pool.join()
                    except Exception:
                        pass
                raise
    except KeyboardInterrupt:
        cancelled=True
        stop_heartbeat.set()
        try:
            heartbeat_thread.join(timeout=2)
        except Exception:
            pass
        write_partial_checkpoint(out,results,args,"KeyboardInterrupt / Ctrl+C")
        print(f"[CANCEL] Clean exit after {len(results)}/{args.runs} completed game(s). No workers will be respawned.",flush=True)
        return

    stop_heartbeat.set()
    heartbeat_thread.join(timeout=max(1,args.heartbeat_seconds+1))
    progress_line(force=True)
    results.sort(key=lambda r:r["seed"])
    # CSV
    with (out/"games.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow([
            "seed","win_turn","urza_cast_turn","family","mulligan_stage","keep_size",
            "interaction_count","interaction_seen","max_depth_reached","states","opening7","bottom","kept_hand","final_hand"
        ])
        for r in results:
            w.writerow([
                r["seed"],r["win_turn"] or "",r["urza_cast_turn"] or "",r["family"],
                r["mulligan_stage"],r["keep_size"],r["interaction_count"],
                "|".join(r["interaction_seen"]),r["max_depth_reached"],r["states"],"|".join(r["opening7"]),
                "|".join(r["bottom"]),"|".join(r["kept_hand"]),"|".join(r["final_hand"])
            ])
    rows,fam,mull=summarize(results,args.turns)
    urza_turns=Counter(r["urza_cast_turn"] for r in results if r["urza_cast_turn"])
    interaction_counts=[r["interaction_count"] for r in results]
    interaction_cards=Counter(c for r in results for c in r["interaction_seen"])
    depth_counts=[r["max_depth_reached"] for r in results]
    depth_ceiling_hits=sum(1 for d in depth_counts if d>=args.depth)
    summary={"runs":args.runs,"completed":len(results),"errors":error_count,"beam":args.beam,"depth":args.depth,"action_cap":ACTION_CAP,"seed":args.seed,
             "turns":[{"turn":t,"exact":e,"cumulative":c,"cumulative_pct":p,"ci95_halfwidth_pct":ci}
                      for t,e,c,p,ci in rows],
             "families":dict(fam),"keep_sizes":dict(mull),
             "urza_cast_turns":dict(urza_turns),
             "interaction_seen_mean":sum(interaction_counts)/len(interaction_counts) if interaction_counts else 0,
             "interaction_seen_distribution":dict(Counter(interaction_counts)),
             "interaction_card_frequency":dict(interaction_cards),
             "max_depth_reached_distribution":dict(Counter(depth_counts)),
             "depth_ceiling_hits":depth_ceiling_hits,
             "depth_ceiling_hit_pct":(100*depth_ceiling_hits/len(results) if results else 0),"wall_runtime_seconds":time.time()-start_wall}
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    # traces: earliest wins + a few misses
    chosen=sorted(results,key=lambda r:(r["win_turn"] if r["win_turn"] is not None else 99,r["seed"]))[:args.trace_count]
    misses=[r for r in results if r["win_turn"] is None][:args.trace_count]
    with (out/"traces.txt").open("w",encoding="utf-8") as f:
        for r in chosen+misses:
            f.write(f"\n=== seed {r['seed']} win={r['win_turn']} family={r['family']} keep={r['keep_size']} ===\n")
            f.write("Opening7: "+", ".join(r["opening7"])+"\n")
            f.write("Bottom: "+", ".join(r["bottom"])+"\n")
            f.write("Kept hand: "+", ".join(r["kept_hand"])+"\n")
            f.write("Urza cast turn: "+(str(r["urza_cast_turn"]) if r["urza_cast_turn"] else "not cast")+"\n")
            f.write(f"Max action depth reached: {r['max_depth_reached']}\n")
            f.write(f"Interaction seen before terminal state: {r['interaction_count']} — "+", ".join(r["interaction_seen"])+"\n")
            for x in r["trace"]: f.write(x+"\n")
    print(f"\nUrza state-search: {args.runs} games, beam={args.beam}, depth={args.depth}")
    print("Turn  Exact  Cum   Cum%    95% CI half-width")
    for t,e,c,p,ci in rows:
        print(f"T{t:<2}  {e:>5}  {c:>4}  {p:6.2f}%   ±{ci:5.2f} pp")
    print("\nWin families:")
    for k,v in fam.most_common(): print(f"  {k:<34} {v:>6}")
    print("\nSelected keep sizes:")
    for k,v in sorted(mull.items(),reverse=True): print(f"  {k} cards: {v}")
    print(f"\nWrote {out/'games.csv'}, {out/'summary.json'}, {out/'traces.txt'}")
    print(f"Completed with {error_count} error(s). Total wall time: {(time.time()-start_wall)/60:.1f} minutes",flush=True)
    if error_count: print(f"See {error_log_path} for tracebacks.",flush=True)

if __name__=="__main__":
    mp.freeze_support()
    main()
