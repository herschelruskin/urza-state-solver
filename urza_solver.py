
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
from solver_architecture import RandomStreams, canonical_markov_state_key, stable_digest

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

import argparse, csv, hashlib, heapq, json, math, multiprocessing as mp, os, random, statistics, subprocess, sys, time, traceback, threading, signal, itertools

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
LEGENDARY_CREATURES = {COMMANDER,"Hope of Ghirapur","The Reality Chip"}
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

@dataclass(frozen=True)
class OracleSearchConfig:
    max_turn: int
    beam: int
    depth: int
    action_cap: int
    bottom_cap: int
    min_keep: int

@dataclass(frozen=True)
class OracleWorkerJob:
    seed: int
    deck: List[str]
    config: OracleSearchConfig
    verbose_worker: bool = False

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
    # Current-turn Knack/Helix grants belong to the exact creature object.
    # ``knack_source`` is trace/pruning provenance only; the two spells grant
    # the same ability, so canonical state identity uses only knack_granted.
    knack_granted: bool = False
    knack_source: str = field(default="",compare=False,hash=False)
    # Search compression: old Oracle behavior immediately takes the optional
    # post-trigger Urza tap for +U and leaves Station/Golem tapped. When True,
    # that final +U is still present in the floating blue pool and may be
    # refunded to preserve the producer for a strategically distinct native or
    # Knack/Helix tap. pay() clears credits once that mana is actually spent.
    producer_urza_ready: bool = False
    # Ephemeral object identity for multi-step action macros. Excluded from
    # equality/hash so canonical state merging is not fragmented by runtime IDs.
    instance_tag: int = field(default=0,compare=False,hash=False)

@dataclass(frozen=True)
class State:
    turn: int
    library: Tuple[str,...]
    hand: Tuple[str,...]
    battlefield: Tuple[Perm,...]
    graveyard: Tuple[str,...] = ()
    exile: Tuple[str,...] = ()
    # Cards exiled by Urza's {5} ability that remain legally playable until
    # end of the current turn.  Card-name multiplicity is sufficient because
    # same-name physical copies are strategically interchangeable here.
    urza_exile_permissions: Tuple[str,...] = ()
    # Oracle-only compact top-first stack.  Each entry is a tuple of strings:
    #   ("trigger", spell_id, kind, card, aux)
    #   ("spell",   spell_id, card, mode, aux)
    # Non-Oracle policy mode keeps its richer typed stack in the Phase-1 runtime
    # sidecar; this field exists so the clairvoyant Oracle can search legal
    # priority windows without consuming hidden mechanical depth.
    oracle_stack: Tuple[Tuple[str,...], ...] = ()
    blue: int = 0
    colorless: int = 0
    land_played: bool = False
    drain_bank: int = 0
    bauble_draws: int = 0
    remora_age: int = 0
    remora_upkeep_pending: bool = False
    saga3_pending: bool = False
    ring_counters: int = 0
    ftt_level: int = 1
    uthros_counters: int = 0
    urza: bool = False
    construct: bool = False
    top_access: bool = False
    chip_attached: bool = False
    chip_target: str = ""
    spell_cast_this_turn: bool = False
    pa_target: str = ""
    vfc_pumps: int = 0
    urza_cast_turn: int = 0
    commander_in_command_zone: bool = True
    commander_casts_from_zone: int = 0
    interaction_seen: Tuple[str,...] = ()
    won: bool = False
    win_family: str = ""
    # Root seed selecting the deterministic game-randomness tape.  This is true
    # simulator state, never policy-visible information.
    rng_root_seed: int = 0
    trace: Tuple[str,...] = ()

    @property
    def knack_target(self):
        p=next((p for p in self.battlefield if p.knack_granted),None)
        return p.name if p else ""

    @property
    def knack_target_mode(self):
        p=next((p for p in self.battlefield if p.knack_granted),None)
        return p.mode if p else ""

    def key(self):
        # Preserve exact shuffled/top-access states without storing the full tuple twice in the key.
        libp = (self.library[:10], hash(self.library))
        # producer_urza_ready is a monotone optional-resource annotation: for
        # otherwise identical physical states, having the refund credit strictly
        # dominates not having it. Exclude it from the exact key and let score()
        # retain the credit-bearing representative.
        bf = tuple(sorted((p.name,p.tapped,p.sick,p.counters,p.mode,
                           p.knack_granted) for p in self.battlefield))
        return (self.turn, tuple(sorted(self.hand)), bf, self.blue, self.colorless,
                self.land_played,self.drain_bank,self.bauble_draws,
                self.remora_age,self.remora_upkeep_pending,self.saga3_pending,
                tuple(sorted(self.graveyard)),tuple(sorted(self.exile)),
                tuple(sorted(self.urza_exile_permissions)),tuple(self.oracle_stack),
                self.ring_counters,self.ftt_level,self.uthros_counters,
                self.urza,self.construct,self.top_access,self.chip_attached,self.chip_target,
                self.spell_cast_this_turn,self.pa_target,self.vfc_pumps,
                self.commander_in_command_zone,self.commander_casts_from_zone,
                libp,self.won,self.win_family)

def add_trace(s:State, msg:str)->State:
    return replace(s, trace=s.trace+(msg,))

def append_trace_detail(s:State,msg:str)->State:
    """Add a visible sub-line without changing the semantic action count.

    Deterministic shuffles and Oracle's established same-stage tie-break use
    ``len(trace)``. Automatic draws were historically silent, so representing
    them as new tuple entries would change search results. Appending the text to
    the current trace entry makes the draw visible while preserving that count.
    """
    if not s.trace:
        return add_trace(s,msg)
    trace=list(s.trace)
    trace[-1]=trace[-1]+"\n"+msg
    return replace(s,trace=tuple(trace))

def draw_from_library(s:State,n:int)->Tuple[State,Tuple[str,...]]:
    """Draw up to ``n`` top cards, returning the state and exact card names."""
    count=min(max(0,n),len(s.library))
    drawn=tuple(s.library[:count])
    if not drawn:
        return s,drawn
    return replace(
        s,hand=s.hand+drawn,library=s.library[count:]
    ),drawn

def drawn_cards_text(drawn:Tuple[str,...])->str:
    return ", ".join(drawn) if drawn else "no cards (empty library)"

_DELAYED_BAUBLE_TRACE_SUFFIX=": tap+sacrifice -> delayed next-upkeep draw"

def pending_bauble_draw_sources(s:State)->Tuple[str,...]:
    """Recover unresolved Bauble source names without adding search state.

    ``bauble_draws`` remains the sole gameplay field. Source provenance already
    exists in the activation trace, so keeping it there avoids changing exact
    keys, dominance groups, caches, or graph size for an observability patch.
    """
    if s.bauble_draws<=0:
        return ()
    latest_turn=0
    for i,msg in enumerate(s.trace):
        if msg.startswith("--- Turn "):
            latest_turn=i+1
    sources=[]
    for msg in s.trace[latest_turn:]:
        for line in msg.splitlines():
            if line.endswith(_DELAYED_BAUBLE_TRACE_SUFFIX):
                sources.append(line[:-len(_DELAYED_BAUBLE_TRACE_SUFFIX)])
    sources=sources[-s.bauble_draws:]
    if len(sources)<s.bauble_draws:
        # A partially preserved legacy trace contains the newest recoverable
        # activations; any unknown pending activations happened earlier.
        sources=(
            ["Mishra's/Urza's Bauble"]*(s.bauble_draws-len(sources))
            +sources
        )
    return tuple(sources)

def bf_names(s): return [p.name for p in s.battlefield]
def bf_name_set(s): return frozenset(p.name for p in s.battlefield)
def has(s,name): return any(p.name==name for p in s.battlefield)
def count_bf(s,name): return sum(p.name==name for p in s.battlefield)

def update_perm(s:State, idx:int, **kwargs)->State:
    # Any later tap/untap transition consumes the special ETB refund credit
    # unless the caller explicitly establishes a fresh one.
    if "tapped" in kwargs and "producer_urza_ready" not in kwargs:
        kwargs["producer_urza_ready"]=False
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
    if p.name=="Mystic Remora":
        s=replace(s,remora_age=0,remora_upkeep_pending=False)
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
    if name=="Mystic Remora":
        # Age counters belong to this battlefield object and reset on every
        # zone change/re-entry. The deck contains only one Mystic Remora.
        s=replace(s,remora_age=0,remora_upkeep_pending=False)
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

def oracle_scry_variants(s:State,n:int,label:str)->List[State]:
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

def shuffled_library(s:State,salt:str)->Tuple[str,...]:
    """Return a reproducible shuffle without consulting trajectory history.

    The root seed selects an immutable game-randomness tape.  The event coordinate
    is derived from the action salt plus the canonical Markov state, which excludes
    trace/provenance fields but retains every future-legality distinction.

    Consequences:
    - identical Markov state + action + root seed -> identical shuffle;
    - different root seeds sample different deterministic worlds;
    - adding/removing trace text cannot change a game outcome;
    - policy/Monte-Carlo RNG usage cannot perturb the actual game stream.
    """
    lib=list(s.library)
    state_fingerprint=stable_digest(canonical_markov_state_key(s))
    event_id=("shuffle",salt,state_fingerprint)
    rng=RandomStreams(s.rng_root_seed).game_rng(event_id)
    rng.shuffle(lib)
    return tuple(lib)

def is_artifact_perm(p:Perm)->bool:
    return p.name in F_ARTIFACTS or p.mode in {"clue","construct","treasure","chrome_copy","chrome_copy_preturn"}

def is_creature_perm(p:Perm)->bool:
    if p.mode=="landface": return False
    if p.name=="The Reality Chip" and p.mode=="chip_attached":
        return False
    return p.name in F_CREATURES or p.name==COMMANDER or p.mode=="construct"

def is_land_perm(p:Perm)->bool:
    """Use the permanent's battlefield face, especially for MDFCs."""
    if p.name in MDFC_BLUE_LANDS:
        return p.mode=="landface"
    return p.name in F_ALL_LANDS

def is_token_perm(p:Perm)->bool:
    return p.mode in {
        "clue","construct","treasure","chrome_copy","chrome_copy_preturn",
    }

def is_pruned_own_bounce_target(p:Perm)->bool:
    """Goldfish search pruning: never bounce our Urza or Construct token.

    This is intentionally stricter than Magic target legality. In the current
    singleton goldfish model, returning Urza is a high-cost reset that does not
    improve any retained winning line, while returning a Construct token simply
    makes it cease to exist. Excluding both from own-bounce action generation
    removes strategically dead branches from Chain/Otawara/Spellbomb/Knack.
    """
    return p.name==COMMANDER or p.name=="Construct" or p.mode=="construct"

def is_knack_target_perm(s:State,p:Perm)->bool:
    return bool(p.knack_granted and is_creature_perm(p))

def has_knack_grant(s:State)->bool:
    return any(is_knack_target_perm(s,p) for p in s.battlefield)

def deferred_producer_blue(s:State)->int:
    """Count unspent refundable post-trigger Urza taps in the blue pool."""
    return sum(
        1 for p in s.battlefield
        if p.producer_urza_ready and p.tapped
        and p.name in {"Grinding Station","Battered Golem"}
    )

def _clear_spent_producer_credits(s:State,n:int)->State:
    if n<=0:
        return s
    b=list(s.battlefield)
    candidates=[
        i for i,p in enumerate(b)
        if p.producer_urza_ready and p.tapped
        and p.name in {"Grinding Station","Battered Golem"}
    ]
    # Preserve an already-Knack-granted producer first; among ordinary sources,
    # Battered Golem has no native strategic tap while Station does.
    candidates.sort(key=lambda i:(b[i].knack_granted,b[i].name=="Grinding Station"))
    for i in candidates[:n]:
        b[i]=replace(b[i],producer_urza_ready=False)
    return replace(s,battlefield=tuple(b))

def _refund_producer_urza_tap(s:State,idx:int)->Optional[State]:
    """Undo one still-unspent final Urza tap and restore that producer."""
    p=s.battlefield[idx]
    if (p.name not in {"Grinding Station","Battered Golem"}
            or not p.tapped or not p.producer_urza_ready or s.blue<1):
        return None
    ns=replace(s,blue=s.blue-1)
    return update_perm(ns,idx,tapped=False,producer_urza_ready=False)


def is_otawara_target_perm(p:Perm)->bool:
    return bool(
        is_artifact_perm(p)
        or is_creature_perm(p)
        or p.name in ENCHANTMENT_CARDS
        or p.name=="Tezzeret, Cruel Captain"
    )

def otawara_channel_cost(s:State)->Tuple[int,int]:
    legends=sum(
        1 for p in s.battlefield
        if p.name in LEGENDARY_CREATURES and is_creature_perm(p)
    )
    return max(0,3-legends),1

def bounce_own_perm(s:State,idx:int)->State:
    """Return one modeled permanent; bounced tokens cease to exist."""
    p=s.battlefield[idx]
    ns=remove_perm(s,idx,to_grave=False)
    if not is_token_perm(p):
        ns=replace(ns,hand=ns.hand+(p.name,))
    return ns

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
    # Prefer restoring a creature carrying Knack/Helix; otherwise turn a tapped
    # artifact creature directly into +U through Urza, per the user's speed model.
    if has_knack_grant(s):
        for i,p in enumerate(s.battlefield):
            if is_knack_target_perm(s,p) and p.tapped:
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
    start_blue=s.blue
    b=s.blue-blue_req; c=s.colorless
    use_c=min(c,generic); c-=use_c; generic-=use_c
    b-=generic
    ns=replace(s,blue=b,colorless=c)

    # producer_urza_ready is valid only while its specific +U remains unspent.
    # Spend ordinary floating blue first; only the unavoidable excess consumes
    # refundable producer credits. Later mana production cannot resurrect them.
    spent_blue=start_blue-b
    credits=deferred_producer_blue(s)
    ordinary_blue=max(0,start_blue-credits)
    consumed=max(0,spent_blue-ordinary_blue)
    if consumed:
        ns=_clear_spent_producer_credits(ns,consumed)
    return ns

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
        elif n in MDFC_BLUE_LANDS and p.mode=="landface":
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
    # Every Station/Golem sees the artifact ETB, including its own. Preserve
    # the established fast Oracle compression: if it was untapped, tap before
    # the trigger and again afterward for +UU; if already tapped, untap then
    # take the final Urza tap for +U. The final +U is marked refundable so a
    # later strategically relevant Station/Knack action can instead choose to
    # leave that producer untapped without branching every ETB state.
    if s.urza:
        b=list(s.battlefield); gain=0
        for i,p in enumerate(b):
            if p.name in {"Grinding Station","Battered Golem"}:
                gain += 1 if p.tapped else 2
                b[i]=replace(p,tapped=True,producer_urza_ready=True)
        if gain:
            s=replace(s,battlefield=tuple(b),blue=s.blue+gain)
            s=add_trace(s,f"producer ETB mana from {entered}: +{gain}U")
    else:
        b=list(s.battlefield)
        changed=False
        for i,p in enumerate(b):
            if p.name in {"Grinding Station","Battered Golem"} and p.tapped:
                b[i]=replace(p,tapped=False,producer_urza_ready=False)
                changed=True
        if changed:
            s=replace(s,battlefield=tuple(b))
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
        s,drawn=draw_from_library(s,1)
        s=replace(s,uthros_counters=s.uthros_counters+1)
        s=add_trace(
            s,
            f"Uthros trigger draws: {drawn[0]}; "
            "+1 station counter before artifact resolves"
        )

    gadgets=count_bf(s,"Forensic Gadgeteer")
    for k in range(gadgets):
        s=add_perm(s,"Clue",mode="clue")
        s=artifact_etb_triggers(s,"Clue")
        s=add_trace(s,f"Gadgeteer trigger {k+1}/{gadgets} -> Clue")
    return s

def _artifact_cast_trigger_tokens(s:State,card:str)->Tuple[str,...]:
    """Strategic simultaneous triggers fired by one artifact cast.

    Vexing Bauble is intentionally not included in the permutation. Its counter
    trigger does not erase already-triggered abilities; all of those abilities
    still resolve whether Bauble is above or below them. The existing caller-side
    Bauble resolution is therefore the same final modeled state without a fake
    factorial multiplier.
    """
    tokens=[]
    if card not in CREATURES and has(s,"Valley Floodcaller"):
        tokens.append("vfc")
    tokens.extend(["assistant"]*count_bf(s,"Artificer's Assistant"))
    if has(s,"Uthros Research Craft") and s.uthros_counters>=3 and s.library:
        tokens.append("uthros")
    tokens.extend(["gadgeteer"]*count_bf(s,"Forensic Gadgeteer"))
    return tuple(tokens)

def _unique_multiset_orders(tokens:Tuple[str,...])->Tuple[Tuple[str,...],...]:
    """Unique permutations without factorial duplicate copies."""
    counts=Counter(tokens)
    kinds=tuple(sorted(counts))
    n=len(tokens)
    rows=[]

    def visit(prefix):
        if len(prefix)==n:
            rows.append(tuple(prefix)); return
        for kind in kinds:
            if counts[kind]<=0:
                continue
            counts[kind]-=1; prefix.append(kind)
            visit(prefix)
            prefix.pop(); counts[kind]+=1

    visit([])
    return tuple(rows)

def _resolve_artifact_cast_trigger_order(s:State,card:str,order:Tuple[str,...])->State:
    totals=Counter(order); resolved=Counter()
    for kind in order:
        resolved[kind]+=1
        if kind=="vfc":
            s=vfc_noncreature_cast_trigger(s,card)
        elif kind=="assistant":
            s=apply_scry(
                s,1,
                f"Artificer's Assistant trigger {resolved[kind]}/{totals[kind]}"
            )
        elif kind=="uthros":
            if s.library:
                s,drawn=draw_from_library(s,1)
                s=replace(s,uthros_counters=s.uthros_counters+1)
                s=add_trace(
                    s,
                    f"Uthros trigger draws: {drawn[0]}; "
                    "+1 station counter before artifact resolves"
                )
        elif kind=="gadgeteer":
            s=add_perm(s,"Clue",mode="clue")
            # Any ETB triggers created by this resolving investigate trigger are
            # stacked above the older unresolved cast triggers, so resolving the
            # ETB bundle here before continuing the order is the correct nesting.
            s=artifact_etb_triggers(s,"Clue")
            s=add_trace(
                s,
                f"Gadgeteer trigger {resolved[kind]}/{totals[kind]} -> Clue"
            )
        else:
            raise AssertionError(f"unknown artifact cast trigger kind {kind!r}")
    return s

def artifact_cast_trigger_variants(s:State,card:str)->List[State]:
    """Return every distinct modeled legal resolution order for our cast triggers."""
    tokens=_artifact_cast_trigger_tokens(s,card)
    if not tokens:
        return [s]
    unique={}
    for order in _unique_multiset_orders(tokens):
        ns=_resolve_artifact_cast_trigger_order(s,card,order)
        # Different orders can be strategically identical (for example VFC and
        # Gadgeteer when neither changes library decisions). Collapse only after
        # the complete order has resolved, using trace-free Markov identity.
        key=canonical_markov_state_key(ns)
        if key not in unique:
            unique[key]=ns
    return list(unique.values())

FLASH_CREATURES=frozenset({
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


def _resolve_chrome_imprint_trigger(s:State,source_tag:str="")->List[State]:
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


def _artifact_entry_state_variants(
    s:State,entered_cards:Tuple[str,...]
)->List[State]:
    rows=[]
    for pushed in _push_artifact_etb_stack_variants(s,entered_cards):
        rows.extend(_oracle_stack_pause_frontier(pushed))
    return _dedup_states(rows)


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
        ns=add_perm(ns,"Treasure",mode="treasure")
        for row in _push_artifact_etb_stack_variants(ns,("Treasure","Treasure")):
            out.append(add_trace(row,f"Offer counters pending {card} -> two Treasures"))
    return _dedup_states(out)



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
    x=list(tup); x.remove(card); return tuple(x)


def vexing_bauble_counters_spell(s:State,mana_spent:int)->bool:
    """True iff our in-play Bauble counters this cast for spending no mana.

    Vexing Bauble cares about mana actually spent to cast the spell, not printed
    mana value. Additional costs such as multikicker count when mana is actually
    paid; nonmana alternate/additional costs do not.
    """
    return has(s,"Vexing Bauble") and mana_spent==0


def vexing_bauble_countered_cast(s:State,card:str,mana_spent:int,
                                  message:str="")->Optional[State]:
    """Return the post-counter state, or None when Bauble does not counter.

    Callers must run all modeled cast triggers before this helper because
    Bauble's ability itself triggers on cast and can be ordered below our other
    cast triggers. Resolution/ETB/spell effects must happen only if this returns
    None.
    """
    if not vexing_bauble_counters_spell(s,mana_spent):
        return None
    ns=replace(s,graveyard=s.graveyard+(card,))
    return add_trace(ns,message or f"Vexing Bauble counters {card}; no mana spent to cast it")


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
        cast_state=replace(
            ps,hand=remove_one(ps.hand,"Everflowing Chalice"),
            spell_cast_this_turn=True
        )
        out.extend(_stack_artifact_cast_state_variants(
            cast_state,"Everflowing Chalice",generic,mode="chalice",aux=str(k)
        ))
    return _dedup_states(out)


def cast_from_hand(s:State,card:str,outside:bool=False,free:bool=False)->Optional[State]:
    if card not in s.hand: return None
    if card in ALL_LANDS and card not in MDFC_BLUE_LANDS: return None
    if card in {"Chrome Mox","Mox Diamond","Everflowing Chalice"}: return None  # special branching actions
    g,b=spell_cost(s,card,outside=outside)
    mana_spent=0
    if free:
        ps=s
    elif card in {"Gitaxian Probe","Mental Misstep"} and has(s,"Vexing Bauble") and s.blue>=1:
        # Choose the normal {U} payment instead of a no-mana Phyrexian payment
        # when that is what allows the spell to survive our own Bauble.
        ps=pay(s,0,1); mana_spent=1
    else:
        ps=pay(s,g,b); mana_spent=g+b
    if ps is None: return None
    s=replace(ps,hand=remove_one(ps.hand,card),spell_cast_this_turn=True)
    if card in ARTIFACTS:
        s=artifact_cast_triggers(s,card)
        countered=vexing_bauble_countered_cast(s,card,mana_spent)
        if countered is not None:
            return countered
        s=add_perm(s,card,sick=card in CREATURES)
        if card=="Uthros Research Craft": s=replace(s,uthros_counters=0)
        if card=="The One Ring": s=replace(s,ring_counters=0)
        s=artifact_etb_triggers(s,card)
        s=add_trace(s,f"cast {card}")
        return check_win(s)
    if card==COMMANDER:
        if has(s,"Artificer's Assistant"): s=apply_scry(s,1,"Artificer's Assistant (legendary cast)")
        s=vfc_noncreature_cast_trigger(s,card) if False else s
        countered=vexing_bauble_countered_cast(s,card,mana_spent)
        if countered is not None: return countered
        s=add_perm(s,COMMANDER,sick=True); s=replace(
            s,urza=True,construct=True,commander_in_command_zone=False,
            urza_cast_turn=(s.urza_cast_turn or s.turn)
        )
        s=add_perm(s,"Construct",sick=True,mode="construct"); s=artifact_etb_triggers(s,"Construct")
        return check_win(add_trace(s,"cast Urza -> Construct"))
    if card in CREATURES or card=="Hydroelectric Specimen":
        countered=vexing_bauble_countered_cast(s,card,mana_spent)
        if countered is not None: return countered
        s=add_perm(s,card,sick=True); return check_win(add_trace(s,f"cast {card}"))
    if card in {"Mystic Remora","Rhystic Study","Fortune Teller's Talent"}:
        countered=vexing_bauble_countered_cast(s,card,mana_spent)
        if countered is not None: return countered
        s=add_perm(s,card)
        if card=="Fortune Teller's Talent": s=replace(s,ftt_level=1)
        return check_win(add_trace(s,f"cast {card}"))
    if card=="Tezzeret, Cruel Captain":
        if has(s,"Artificer's Assistant"): s=apply_scry(s,1,"Artificer's Assistant (legendary cast)")
        s=vfc_noncreature_cast_trigger(s,card)
        countered=vexing_bauble_countered_cast(s,card,mana_spent)
        if countered is not None: return countered
        s=add_perm(s,card,counters=4,mode="tez_ready"); return add_trace(s,"cast Tezzeret (4 loyalty)")
    if card=="Gitaxian Probe":
        s=vfc_noncreature_cast_trigger(s,card)
        countered=vexing_bauble_countered_cast(
            s,card,mana_spent,"Probe cast with no mana spent; Vexing Bauble counters it"
        )
        if countered is not None: return countered
        s,drawn=draw_from_library(s,1)
        return add_trace(
            s,
            f"Gitaxian Probe targets an opponent -> draw: "
            f"{drawn_cards_text(drawn)}"
        )
    if card=="Dramatic Reversal":
        s=vfc_noncreature_cast_trigger(s,card)
        countered=vexing_bauble_countered_cast(s,card,mana_spent)
        if countered is not None: return countered
        b=[]
        for p in s.battlefield:
            b.append(p if is_land_perm(p) else replace(p,tapped=False,producer_urza_ready=False))
        return add_trace(
            replace(s,battlefield=tuple(b),graveyard=s.graveyard+(card,)),
            "Dramatic Reversal untaps all nonlands"
        )
    if card=="Mana Drain":
        s=vfc_noncreature_cast_trigger(s,card)
        countered=vexing_bauble_countered_cast(s,card,mana_spent)
        if countered is not None: return countered
        return add_trace(replace(s,drain_bank=s.drain_bank+2),"Mana Drain assumption: bank +2 next turn")
    if card=="Sea Gate Restoration":
        s=vfc_noncreature_cast_trigger(s,card)
        countered=vexing_bauble_countered_cast(s,card,mana_spent)
        if countered is not None: return countered
        s,drawn=draw_from_library(s,len(s.hand)+1)
        return add_trace(
            s,
            f"Sea Gate Restoration draws {len(drawn)}: "
            f"{drawn_cards_text(drawn)}"
        )
    if card=="Sink into Stupor":
        s=vfc_noncreature_cast_trigger(s,card)
        countered=vexing_bauble_countered_cast(s,card,mana_spent)
        if countered is not None: return countered
        s=replace(s,graveyard=s.graveyard+(card,))
        return add_trace(s,"cast Sink into Stupor (opponent target assumed)")
    return None

def cast_from_hand_variants(s:State,card:str,outside:bool=False,free:bool=False)->List[State]:
    """Oracle cast branches; artifact spells expose their real priority stack."""
    if card not in ARTIFACTS:
        one=cast_from_hand(s,card,outside=outside,free=free)
        return [one] if one is not None else []
    if card not in s.hand or card in ALL_LANDS:
        return []
    if card in {"Chrome Mox","Mox Diamond","Everflowing Chalice"}:
        return []
    g,b=spell_cost(s,card,outside=outside)
    mana_spent=0
    if free:
        ps=s
    else:
        ps=pay(s,g,b); mana_spent=g+b
    if ps is None:
        return []
    cast_state=replace(ps,hand=remove_one(ps.hand,card),spell_cast_this_turn=True)
    return _stack_artifact_cast_state_variants(
        cast_state,card,mana_spent,mode="ordinary"
    )

def _play_land_physical(s:State,card:str)->Optional[Tuple[State,str]]:
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

# --------------------------- Draw/card engines ------------------------------

def clue_draw_actions(s:State)->List[State]:
    out=[]
    reduction=1 if has(s,"Forensic Gadgeteer") else 0
    cost=max(1,2-reduction)
    for i,p in enumerate(s.battlefield):
        if p.mode=="clue" and can_pay(s,cost,0):
            ns=pay(s,cost,0); ns=remove_perm(ns,i)
            ns,drawn=draw_from_library(ns,1)
            out.append(add_trace(
                ns,f"sac Clue -> draw: {drawn_cards_text(drawn)}"
            ))
    return out

def ring_actions(s:State)->List[State]:
    out=[]
    for i,p in enumerate(s.battlefield):
        if p.name=="The One Ring" and not p.tapped:
            ns=update_perm(s,i,tapped=True)
            k=ns.ring_counters+1
            ns,drawn=draw_from_library(ns,k)
            ns=replace(ns,ring_counters=k)
            out.append(add_trace(
                ns,
                f"The One Ring draws {len(drawn)}: {drawn_cards_text(drawn)}"
            ))
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
                ns=remove_perm(s,i,to_grave=False)
                ns,drawn=draw_from_library(ns,1)
                # Correct Oracle sequencing: draw, then put Top itself on TOP.
                ns=replace(ns,library=("Sensei's Divining Top",)+ns.library)
                out.append(add_trace(
                    ns,
                    f"Sensei's Divining Top -> draw: {drawn[0]}; "
                    "Top goes on top"
                ))
    return out

def assistant_scry_actions(s:State)->List[State]:
    # v0.2 incorrectly allowed free repeated scries. Assistant is now handled only
    # as a cast trigger in artifact_cast_triggers / historic spell handling.
    return []


def cage_in_play(s:State)->bool:
    return has(s,"Grafdigger's Cage")

def cage_blocks_library_cast(s:State, card:str)->bool:
    # MDFCs are land cards in the library but are still *spells* when their front
    # face is cast from the library, so Cage blocks those spell-face casts too.
    return cage_in_play(s) and card not in TRUE_LAND_CARDS

def cage_blocks_library_battlefield_entry(s:State, card:str)->bool:
    return cage_in_play(s) and card in CREATURES

def chip_ftt_top_casts(s:State,priority:bool=False)->List[State]:
    chip_active = s.chip_attached
    ftt_active = (s.ftt_level>=2 and s.spell_cast_this_turn)
    if not (chip_active or ftt_active) or not s.library:
        return []

    card=s.library[0]
    out=[]

    if card in ALL_LANDS and not priority and not s.land_played:
        ns=replace(s,library=s.library[1:],hand=s.hand+(card,))
        for pl in play_land_variants(ns,card):
            out.append(add_trace(pl,"top access: play land from library"))
        if card not in MDFC_BLUE_LANDS:
            return out

    # MDFCs may still use their spell face.  At a priority window, enforce
    # instant/native-flash/Floodcaller timing before moving the card off top.
    if card not in ALL_LANDS or card in MDFC_BLUE_LANDS:
        if priority and not _can_cast_card_at_priority(s,card):
            return out
        if cage_blocks_library_cast(s,card):
            return out
        ns=replace(s,library=s.library[1:],hand=s.hand+(card,))
        src="Chip" if chip_active else "FTT"
        if card=="Everflowing Chalice":
            for cs in chalice_cast_variants(ns,outside=True,free=False):
                out.append(add_trace(cs,f"{src}: cast Chalice from top"))
        else:
            for cs in cast_from_hand_variants(ns,card,outside=True):
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
                        for row in _artifact_entry_state_variants(ns,(t,)):
                            out.append(add_trace(check_win(row),f"Transmute {p.name}->{t}; pay difference {diff}"))

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
                        for row in _artifact_entry_state_variants(ns,(t,)):
                            out.append(add_trace(check_win(row),f"Reshape X={x}->{t}; generic paid {generic}"))

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
                            b[j]=replace(p,tapped=True,producer_urza_ready=False); need-=1
                    ns=replace(ns,battlefield=tuple(b))

                if need==0:
                    lib=list(ns.library); lib.remove(t)
                    ns=replace(ns,library=tuple(lib))
                    ns=replace(ns,library=shuffled_library(ns,"whir:"+t))
                    ns=add_perm(ns,t,sick=t in CREATURES)
                    for row in _artifact_entry_state_variants(ns,(t,)):
                        out.append(add_trace(check_win(row),f"Whir X={x}->{t}"))
    return out


def power_artifact_actions(s:State)->List[State]:
    out=[]
    if "Power Artifact" not in s.hand: return out
    g,b=spell_cost(s,"Power Artifact")
    if not can_pay(s,g,b): return out
    for p in s.battlefield:
        # Deliberate Oracle state-space prune: PA attachment to a temporary
        # Chrome Dome copy is not a modeled strategic line. All singleton
        # non-copy artifact targets remain available, which also keeps the
        # name-based pa_target representation unambiguous.
        if is_artifact_perm(p) and p.mode not in {"chrome_copy","chrome_copy_preturn"}:
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
        ns=pay(s,g,0); ns=add_perm(ns,p.name,sick=False,mode="chrome_copy")
        for row in _artifact_entry_state_variants(ns,(p.name,)):
            out.append(add_trace(check_win(row),f"Chrome Dome copies {p.name} (haste)"))
    return out

def aether_spellbomb_actions(s:State)->List[State]:
    """Both printed Aether Spellbomb activations; neither has a tap cost."""
    out=[]
    for i,p in enumerate(s.battlefield):
        if p.name!="Aether Spellbomb":
            continue
        if can_pay(s,1,0):
            ns=pay(s,1,0); ns=remove_perm(ns,i)
            ns,drawn=draw_from_library(ns,1)
            out.append(add_trace(
                ns,
                "Aether Spellbomb: pay 1, sacrifice -> draw: "
                f"{drawn_cards_text(drawn)}"
            ))
        if can_pay(s,0,1):
            for j,target in enumerate(s.battlefield):
                if (j==i or not is_creature_perm(target)
                        or is_pruned_own_bounce_target(target)):
                    continue
                ns=pay(s,0,1); ns=remove_perm(ns,i)
                target_i=j-1 if j>i else j
                ns=bounce_own_perm(ns,target_i)
                out.append(add_trace(
                    ns,
                    "Aether Spellbomb: pay U, sacrifice -> bounce "
                    f"{target.name or target.mode}"
                ))
    return out

def draw_sac_actions(s:State)->List[State]:
    out=aether_spellbomb_actions(s)
    for i,p in enumerate(s.battlefield):
        n=p.name

        if n=="Aether Spellbomb":
            continue

        # Witching Well: 3U, sacrifice -> draw 2. No tap symbol.
        if n=="Witching Well" and can_pay(s,3,1):
            ns=pay(s,3,1); ns=remove_perm(ns,i)
            ns,drawn=draw_from_library(ns,2)
            out.append(add_trace(
                ns,
                f"Witching Well: pay 3U, sacrifice -> draw {len(drawn)}: "
                f"{drawn_cards_text(drawn)}"
            ))

        # Sewer-veillance Cam: 3U, sacrifice -> draw 2. No tap symbol.
        # Leaving the battlefield also untaps a target creature.
        elif n=="Sewer-veillance Cam" and can_pay(s,3,1):
            # remove_perm() resolves Cam's LTB untap exactly once via cam_untap_best().
            base=pay(s,3,1); base=remove_perm(base,i)
            base,drawn=draw_from_library(base,2)
            out.append(add_trace(
                base,
                f"Cam: pay 3U, sacrifice -> draw {len(drawn)}: "
                f"{drawn_cards_text(drawn)}"
            ))

        # Vexing Bauble: 1, T, sacrifice -> draw 1.
        elif n=="Vexing Bauble" and not p.tapped and can_pay(s,1,0):
            ns=pay(s,1,0); ns=remove_perm(ns,i)
            ns,drawn=draw_from_library(ns,1)
            out.append(add_trace(
                ns,
                "Vexing Bauble: pay 1, tap+sacrifice -> draw: "
                f"{drawn_cards_text(drawn)}"
            ))

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
        cast_base=replace(
            s,hand=remove_one(s.hand,"Chrome Mox"),spell_cast_this_turn=True
        )
        out.extend(_stack_artifact_cast_state_variants(
            cast_base,"Chrome Mox",0,mode="chrome_mox"
        ))
    if "Mox Diamond" in s.hand:
        cast_base=replace(
            s,hand=remove_one(s.hand,"Mox Diamond"),spell_cast_this_turn=True
        )
        out.extend(_stack_artifact_cast_state_variants(
            cast_base,"Mox Diamond",0,mode="mox_diamond"
        ))
    return _dedup_states(out)

def fetch_actions(s:State)->List[State]:
    out=[]
    for i,p in enumerate(s.battlefield):
        if p.name in FETCHES and "Island" in s.library:
            ns=remove_perm(s,i); lib=list(ns.library); lib.remove("Island"); ns=replace(ns,library=tuple(lib)); ns=add_perm(ns,"Island")
            ns=replace(ns,library=shuffled_library(ns,"fetch:"+p.name))
            out.append(add_trace(ns,f"{p.name} fetches Island and shuffles"))
    return out

def otawara_channel_actions(s:State,only_target:str="")->List[State]:
    """Channel Otawara from hand; this is an ability, not a spell cast."""
    card="Otawara, Soaring City"
    if card not in s.hand:
        return []
    generic,blue_req=otawara_channel_cost(s)
    if not can_pay(s,generic,blue_req):
        return []
    out=[]
    for i,p in enumerate(s.battlefield):
        if not is_otawara_target_perm(p) or is_pruned_own_bounce_target(p):
            continue
        if only_target and p.name!=only_target:
            continue
        ns=pay(s,generic,blue_req)
        ns=replace(
            ns,hand=remove_one(ns.hand,card),
            graveyard=ns.graveyard+(card,),
        )
        ns=bounce_own_perm(ns,i)
        mana=(f"{{{generic}}}{{U}}" if generic else "{U}")
        out.append(add_trace(
            ns,
            f"Otawara channel: pay {mana}, discard -> bounce {p.name or p.mode}"
        ))
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
    # Codex/Station self-mill matters when current top access can be unbricked,
    # Cage must be removed, or the graveyard is an active resource. Grinding
    # Station's cost is T, sacrifice AN artifact: it may sacrifice itself and
    # the sacrificed artifact need not be untapped. Enumerate every distinct
    # legal artifact choice only in these strategically live states to avoid
    # flooding ordinary development nodes with irrelevant mill branches.
    graveyard_live=(
        "Scour for Scrap" in s.hand
        or has(s,"Codex Shredder")
    )
    mill_live=(s.chip_attached or s.ftt_level>=2 or has(s,"Grafdigger's Cage")
               or graveyard_live)
    if s.chip_attached or s.ftt_level>=2:
        for i,p in enumerate(s.battlefield):
            if p.name=="Codex Shredder" and not p.tapped and s.library:
                ns=update_perm(s,i,tapped=True)
                ns=replace(ns,graveyard=ns.graveyard+(ns.library[0],),library=ns.library[1:])
                out.append(add_trace(ns,"Codex mills our top card"))

    if mill_live:
        for i,p in enumerate(s.battlefield):
            if p.name!="Grinding Station" or not s.library:
                continue
            base=s
            if p.tapped:
                base=_refund_producer_urza_tap(s,i)
                if base is None:
                    continue
            for j,a in enumerate(base.battlefield):
                if not is_artifact_perm(a):
                    continue
                # Pay the tap cost first, then sacrifice the chosen artifact.
                ns=update_perm(base,i,tapped=True)
                sac_name=a.name or a.mode
                ns=remove_perm(ns,j,to_grave=True)
                n=min(3,len(ns.library))
                milled=ns.library[:n]
                ns=replace(ns,graveyard=ns.graveyard+milled,library=ns.library[n:])
                out.append(add_trace(
                    ns,
                    f"Grinding Station sacs {sac_name}, self-mill {n}: "
                    f"{', '.join(milled)}"
                ))
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
            out.append(add_trace(
                ns,
                f"Top + {k.name}: double activation draws: {drawn}, "
                "Sensei's Divining Top"
            ))
    return out

def uthros_station_actions(s:State)->List[State]:
    out=[]
    if not has(s,"Uthros Research Craft"): return out
    for i,p in enumerate(s.battlefield):
        if not is_creature_perm(p) or p.name=="Uthros Research Craft":
            continue
        base=s
        if p.tapped:
            base=_refund_producer_urza_tap(s,i)
            if base is None:
                continue
        power=creature_power(base,base.battlefield[i])
        if power>0:
            ns=update_perm(base,i,tapped=True)
            ns=replace(ns,uthros_counters=ns.uthros_counters+power)
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

def _sacrifice_final_saga_if_present(s:State)->State:
    """Apply the Saga final-chapter state-based sacrifice after III resolves."""
    for i,p in enumerate(s.battlefield):
        if p.name=="Urza's Saga" and p.counters>=3:
            return remove_perm(s,i,to_grave=True)
    return s

def saga_actions(s:State)->List[State]:
    out=[]
    # Chapter-II activated ability remains an ordinary sorcery-speed action.
    for i,p in enumerate(s.battlefield):
        if p.name=="Urza's Saga" and p.counters>=2 and not p.tapped and can_pay(s,2,0):
            ns=pay(s,2,0); ns=update_perm(ns,i,tapped=True)
            ns=add_perm(ns,"Construct",sick=True,mode="construct")
            for row in _artifact_entry_state_variants(ns,("Construct",)):
                out.append(add_trace(row,"Saga II ability -> Construct"))

    # Once III triggers it exists independently of the Saga permanent. A legal
    # response (notably Otawara) may remove Saga, but the pending search still
    # resolves. If Saga remains after III resolves, the final-chapter SBA then
    # sacrifices it. ETB triggers from the found artifact resolve only after the
    # search has finished and shuffled.
    if not s.saga3_pending:
        return out

    base=replace(s,saga3_pending=False)

    no_find=replace(base,library=shuffled_library(base,"saga:no-target"))
    no_find=_sacrifice_final_saga_if_present(no_find)
    out.append(add_trace(
        no_find,
        "Saga III search finds no card; shuffle; final chapter resolves"
    ))

    for target in sorted(set(s.library)&SAGA_TARGETS):
        ns=base
        lib=list(ns.library); lib.remove(target)
        ns=replace(ns,library=tuple(lib))
        ns=add_perm(ns,target,sick=target in CREATURES)
        ns=replace(ns,library=shuffled_library(ns,"saga:"+target))
        ns=_sacrifice_final_saga_if_present(ns)
        for row in _artifact_entry_state_variants(ns,(target,)):
            out.append(add_trace(
                check_win(row),
                f"Saga III puts {target} onto battlefield\nSaga III search resolves; shuffle"
            ))
    return out


def repurposing_bay_actions(s:State)->List[State]:
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



_CHAIN_RESULT_CACHE = {}

def _with_runtime_instance_tags(s:State)->State:
    b=tuple(replace(p,instance_tag=i+1) for i,p in enumerate(s.battlefield))
    return replace(s,battlefield=b)

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

def _chain_apply_plan(base:State, bounce_perms:Tuple[Perm,...], land_names:Tuple[str,...],
                      order_mode:str="canonical")->Optional[State]:
    ns=base
    order=list(bounce_perms)

    def move_named(name,where):
        matches=[i for i,p in enumerate(order) if p.name==name]
        if not matches:
            return
        i=matches[0]
        item=order.pop(i)
        if where=="first": order.insert(0,item)
        else: order.append(item)

    if order_mode=="cam_first":
        move_named("Sewer-veillance Cam","first")
    elif order_mode=="cam_last":
        move_named("Sewer-veillance Cam","last")
    elif order_mode=="pa_first":
        move_named("Power Artifact","first")
    elif order_mode=="pa_target_first" and ns.pa_target:
        move_named(ns.pa_target,"first")
    else:
        order=sorted(order,key=lambda p:(p.name,p.mode,p.instance_tag))

    lands_order=sorted(land_names)

    for copy_no,selected in enumerate(order,1):
        idx=next((
            i for i,p in enumerate(ns.battlefield)
            if p.instance_tag==selected.instance_tag
        ),None)
        if idx is None:
            continue
        name=ns.battlefield[idx].name or ns.battlefield[idx].mode
        ns=bounce_own_perm(ns,idx)
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
    # Cached values contain complete successor States. Keying by the complete
    # trace-free source state prevents an omitted legality field (notably a
    # Remora age/upkeep decision or graveyard contents) from being transplanted
    # from a superficially similar cached state. ACTION_CAP also changes Chain's
    # internal shortlist widths and therefore belongs in the cache identity.
    return (ACTION_CAP,replace(s,trace=()))

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
    base=_with_runtime_instance_tags(base)
    base_trace_len=len(base.trace)

    nonlands=tuple(
        p for p in base.battlefield
        if not is_land_perm(p) and not is_pruned_own_bounce_target(p)
    )
    lands=tuple(p.name for p in base.battlefield if is_land_perm(p))
    max_k=min(len(nonlands),1+len(lands))
    if max_k<=0:
        return []

    # Much smaller than the previous full subset Cartesian product.
    bounce_cap=max(18,ACTION_CAP//3)
    land_cap=max(8,ACTION_CAP//8)

    special_bounce_names={
        "Sewer-veillance Cam","Grafdigger's Cage","Power Artifact",
        "Spellseeker","Prized Statue","The One Ring","Witching Well",
        "Mystic Remora",
    }
    if base.pa_target:
        special_bounce_names.add(base.pa_target)
    special_bounce=tuple(p for p in nonlands if p.name in special_bounce_names)
    special_land=("Crystal Vein","City of Traitors","Saprazzan Skerry","Urza's Saga")

    plan_heap=[]
    serial=0

    for k in range(1,max_k+1):
        bsets=_top_scored_subsets(
            nonlands,k,
            lambda p:_chain_card_plan_value(base,p.name),
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
            bvalue=sum(_chain_card_plan_value(base,p.name) for p in bset)
            artifact_bounces=sum(1 for p in bset if is_artifact_perm(p))
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
        if any(p.name=="Sewer-veillance Cam" for p in bset):
            modes.update({"cam_first","cam_last"})
        if (any(p.name=="Power Artifact" for p in bset) and base.pa_target
                and any(p.name==base.pa_target for p in bset)):
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
    # Cast Knack/Helix targeting an exact creature object. Multiple grants in
    # one turn are legal, so the temporary ability lives on Perm rather than a
    # singleton State name/mode field. Canonical state identity includes the
    # grant flag but not the spell-source provenance.
    for k in KNUCKS:
        if k not in s.hand or not can_pay(s,*spell_cost(s,k)):
            continue
        for ti,p in enumerate(s.battlefield):
            if not is_creature_perm(p):
                continue
            ns=pay(s,*spell_cost(s,k))
            ns=replace(
                ns,hand=remove_one(ns.hand,k),
                graveyard=ns.graveyard+(k,),spell_cast_this_turn=True,
            )
            ns=update_perm(ns,ti,knack_granted=True,knack_source=k)
            ns=vfc_noncreature_cast_trigger(ns,k)
            out.append(add_trace(
                check_win(ns),f"cast {k} targeting {p.name or p.mode}"
            ))

    # Each ready granted creature may activate independently and return any
    # nonland permanent, including itself. The tap-symbol cost clears any
    # deferred Urza-mana shortcut on that exact producer.
    for ti,tapper in enumerate(s.battlefield):
        if not is_knack_target_perm(s,tapper) or tapper.sick:
            continue
        base=s
        if tapper.tapped:
            base=_refund_producer_urza_tap(s,ti)
            if base is None:
                continue
        for j,p in enumerate(base.battlefield):
            if is_land_perm(p) or is_pruned_own_bounce_target(p):
                continue
            ns=update_perm(base,ti,tapped=True)
            target_name=p.name or p.mode
            ns=bounce_own_perm(ns,j)
            out.append(add_trace(
                ns,
                f"Knack/Helix target {tapper.name or tapper.mode} "
                f"bounces our {target_name}"
            ))
    return out


def graveyard_land_actions(s:State)->List[State]:
    out=[]

    # Cephalid Coliseum threshold — U, T, sacrifice: draw 3, then discard 3.
    if len(s.graveyard) >= 7:
        for i,p in enumerate(s.battlefield):
            if p.name=="Cephalid Coliseum" and not p.tapped and can_pay(s,0,1):
                ns=pay(s,0,1)
                ns=remove_perm(ns,i,to_grave=True)
                ns,drawn=draw_from_library(ns,3)
                d=len(drawn)
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
                        out.append(add_trace(
                            st,
                            f"Cephalid Coliseum threshold: draw {d}: "
                            f"{drawn_cards_text(drawn)}; discard {', '.join(disc)}"
                        ))

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
    ns,drawn=draw_from_library(ns,1)
    return [add_trace(
        ns,
        f"Faerie Mastermind: pay 3U -> each player draws; we draw: "
        f"{drawn[0]}"
    )]


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
    rows=[]
    for row in _artifact_entry_state_variants(ns,("Construct",)):
        row=add_trace(
            row,
            f"cast Urza from command zone -> Construct"
            + (" (infinite colorless paid generic)" if infinite_colorless_online(s) else "")
        )
        rows.append(check_win(row))
    return _dedup_states(rows)


def urza_exile_permission_actions(s:State,priority:bool=False)->List[State]:
    """Use any still-live card permission created by Urza's {5} ability.

    Not using a permission is represented by choosing another ordinary action.
    The permission therefore survives arbitrary sequencing and additional spins
    until it is consumed or end_turn() expires it.
    """
    out=[]
    for card in sorted(set(s.urza_exile_permissions)):
        if card not in s.exile:
            continue
        base=replace(
            s,
            exile=remove_one(s.exile,card),
            urza_exile_permissions=remove_one(s.urza_exile_permissions,card),
            hand=s.hand+(card,),
        )

        # "Play that card" permits the land face when legal.  MDFCs also retain
        # their independent front-face spell option below.
        if card in ALL_LANDS and not priority and not s.land_played:
            for pl in play_land_variants(base,card):
                out.append(add_trace(pl,f"Urza permission -> play {card}"))

        if card not in ALL_LANDS or card in MDFC_BLUE_LANDS:
            if priority and not _can_cast_card_at_priority(s,card):
                continue
            if card=="Everflowing Chalice":
                # Without paying the mana cost fixes X=0; multikicker remains an
                # optional additional cost and chalice_cast_variants already
                # models the payable {2}-per-kick branches.
                for cs in chalice_cast_variants(base,outside=True,free=True):
                    out.append(add_trace(
                        cs,
                        "Urza permission -> free Chalice base cost; optional multikicker paid"
                    ))
            else:
                for cs in cast_from_hand_variants(base,card,outside=True,free=True):
                    out.append(add_trace(cs,f"Urza permission -> cast {card} free"))
    return out


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
                # Deliberate state-space prune: reconfiguring Reality Chip onto
                # a temporary Chrome Dome copy is not a modeled strategic line.
                # This keeps the singleton name-based chip_target representation
                # exact for all retained attachment choices.
                if (is_creature_perm(p) and p.name!="The Reality Chip"
                        and p.mode not in {"chrome_copy","chrome_copy_preturn"}):
                    ns=replace(pay(s,g,b),chip_attached=True,chip_target=p.name)
                    for ci,cp in enumerate(ns.battlefield):
                        if cp.name=="The Reality Chip":
                            ns=update_perm(ns,ci,mode="chip_attached")
                            break
                    out.append(add_trace(ns,f"reconfigure Reality Chip onto {p.name or p.mode}"))
    if has(s,"Fortune Teller's Talent"):
        if s.ftt_level==1 and can_pay(s,3,1): out.append(add_trace(replace(pay(s,3,1),ftt_level=2),"FTT -> level 2"))
        if s.ftt_level==2 and can_pay(s,2,1): out.append(add_trace(replace(pay(s,2,1),ftt_level=3),"FTT -> level 3"))
    out += urza_spin_actions(s)
    out += urza_exile_permission_actions(s)
    # Key generic untap
    for ki,k in enumerate(s.battlefield):
        if k.name in {"Voltaic Key","Manifold Key"} and not k.tapped and can_pay(s,1,0):
            for ti,t in enumerate(s.battlefield):
                if ti!=ki and t.tapped and is_artifact_perm(t):
                    ns=pay(s,1,0); ns=update_perm(ns,ki,tapped=True); ns=update_perm(ns,ti,tapped=False); out.append(add_trace(ns,f"{k.name} untaps {t.name or t.mode}"))
    out += clue_draw_actions(s)+ring_actions(s)+top_actions(s)+power_artifact_actions(s)+chrome_dome_actions(s)
    out += draw_sac_actions(s)+mox_cast_actions(s)+fetch_actions(s)
    out += otawara_channel_actions(s)+oboro_minamo_actions(s)
    out += producer_native_actions(s)+top_key_combo_actions(s)+uthros_station_actions(s)+tezzeret_actions(s)+saga_actions(s)
    out += repurposing_bay_actions(s)+scour_actions(s)+offer_actions(s)+chain_of_vapor_actions(s)+knack_bounce_actions(s)
    out += simple_tutor_actions(s)+artifact_tutor_actions(s)+chip_ftt_top_casts(s)
    return out

# -------------------------- Combo detection --------------------------------

def active_creatures(s:State)->set:
    return {p.name for p in s.battlefield if p.name in F_CREATURES|{COMMANDER} and not p.sick}


# Repeatable artifact-loop economics.
#
# Important distinction:
# * only a few rocks are intrinsically mana-positive without Urza;
# * with Urza, every repeatable artifact can be tapped for +U, so zero-drops
#   become positive and ordinary one-drops become neutral;
# * visible producers can further improve the steady-state replay margin.
#
# Mox Diamond is never considered repeatable: every recast would require a fresh
# land discard, so its printed mana value of zero is misleading for loop logic.
REPLAY_NEVER_REPEAT=frozenset({"Mox Diamond"})

# Human-audited base classes with Urza in play and no additional producer
# rebates. Sewer-veillance Cam is positive only when its ETB can untap a
# different artifact creature that Urza can convert to another +U.
URZA_REPLAY_POSITIVE_BASE=frozenset({
    "Sol Ring","Mana Vault","Grim Monolith",
    "Welding Jar","Tormod's Crypt","Jeweled Amulet","Mox Opal","Chrome Mox",
    "Mishra's Bauble","Urza's Bauble","Lotus Petal","Everflowing Chalice",
})
URZA_REPLAY_NEUTRAL_BASE=frozenset({
    "Aether Spellbomb","Basalt Monolith","Grafdigger's Cage","Giant's Boulder",
    "Grinding Station","Manifold Key","Moonsnare Prototype","Pithing Needle",
    "Prized Statue","Sensei's Divining Top","Witching Well","Vexing Bauble",
    "Voltaic Key","Hope of Ghirapur","Codex Shredder","Fugitive Droid",
})
NATIVE_REPLAY_POSITIVE_BASE=frozenset({
    "Sol Ring","Mana Vault","Grim Monolith","Mox Opal",
})
NATIVE_REPLAY_NEUTRAL_BASE=frozenset(
    (ZERO_ARTIFACTS-{"Mox Diamond"})|{"Basalt Monolith"}
)


def _replay_card_present(s:State,card:str)->bool:
    return card in s.hand or any(p.name==card for p in s.battlefield)


def _replay_post_entry_artifact_count(s:State,card:str)->int:
    """Artifact count after the candidate has been replayed onto the battlefield."""
    already_present=any(p.name==card for p in s.battlefield)
    return artifact_count(s)+(0 if already_present else 1)


def _native_repeatable_mana_yield(s:State,card:str)->int:
    """Mana one replayed artifact can repeatedly make without using Urza."""
    if card=="Sol Ring":
        return 2
    if card in {"Mana Vault","Grim Monolith","Basalt Monolith"}:
        return 3
    if card=="Mox Opal" and _replay_post_entry_artifact_count(s,card)>=3:
        return 1
    # Lotus Petal and other sacrificial/one-shot objects are deliberately zero:
    # sacrificing the object destroys the bounce/replay recurrence.
    return 0


def _cam_extra_urza_untap_available(s:State,source:Perm,card:str)->bool:
    """Cam is +1 above neutral only with a distinct artifact creature to untap."""
    if card!="Sewer-veillance Cam" or not s.urza:
        return False
    for p in s.battlefield:
        if p.instance_tag==source.instance_tag:
            continue
        if p.name==card:
            continue
        if is_artifact_perm(p) and is_creature_perm(p):
            return True
    return False


def _steady_replay_producer_bonus(s:State,source:Perm,card:str)->int:
    """Steady-state +U supplied by additional visible producers.

    Station/Golem each contribute one reusable Urza tap from the replay ETB.
    Gadgeteer contributes one Clue per artifact cast; the Clue is another +U.
    Each Gadgeteer Clue also creates another ETB for each Station/Golem.
    """
    if not s.urza:
        return 0

    station_golem=0
    gadgeteer=0
    for p in s.battlefield:
        if p.instance_tag==source.instance_tag:
            continue
        if p.name==card:
            continue
        if p.name in {"Grinding Station","Battered Golem"}:
            station_golem += 1
        elif p.name=="Forensic Gadgeteer":
            gadgeteer += 1

    return station_golem + gadgeteer + station_golem*gadgeteer


def replay_mana_margin(s:State,source:Perm,card:str)->Optional[int]:
    """Steady-state mana gained per legal Knack/Helix bounce/recast cycle.

    Positive means unbounded mana. Zero is mana-neutral and can be promoted by
    another visible producer. Negative cards require enough producer rebates to
    move classes. This is repeatability logic, not a generic card-value score.
    """
    if card in REPLAY_NEVER_REPEAT or card not in ARTIFACTS:
        return None
    if not _replay_card_present(s,card):
        return None

    generic,blue_req=spell_cost(s,card,outside=False)
    cast_cost=generic+blue_req
    native=_native_repeatable_mana_yield(s,card)
    urza_yield=1 if s.urza else 0
    produced=max(native,urza_yield)

    if s.urza:
        # A replayed Station/Golem can be tapped once before its own untap
        # trigger resolves and once after. The ordinary Urza tap is already the
        # base +1; this is the extra self-entry +1.
        if card in {"Grinding Station","Battered Golem"}:
            produced += 1

        # Prized Statue creates a Treasure on ETB, yielding the second mana that
        # makes the {2} replay neutral under Urza.
        if card=="Prized Statue":
            produced += 1

        # Cam is neutral by itself under Urza. A distinct artifact creature can
        # be tapped, untapped by Cam ETB, and tapped again for one extra +U.
        if _cam_extra_urza_untap_available(s,source,card):
            produced += 1

        produced += _steady_replay_producer_bonus(s,source,card)

    return produced-cast_cost


def _replay_refreshes_knack_source(source:Perm,card:str)->bool:
    if source.name=="Battered Golem":
        return card in ARTIFACTS
    if source.name=="Valley Floodcaller":
        return card in ARTIFACTS and card not in CREATURES
    return False


def _candidate_replay_cards(s:State,source:Perm)->Tuple[str,...]:
    rows=set()
    for card in s.hand:
        if card in ARTIFACTS and card not in REPLAY_NEVER_REPEAT:
            rows.add(card)
    for p in s.battlefield:
        if p.instance_tag==source.instance_tag:
            continue
        if p.name in ARTIFACTS and p.name not in REPLAY_NEVER_REPEAT:
            rows.add(p.name)
    return tuple(sorted(rows))


def _immediate_replay_mana_capacity(
    s:State,source:Perm,card:str,*,on_battlefield:bool
)->Tuple[int,int]:
    """Return (blue-capable mana, total mana) available for the first replay.

    This is a capacity calculation, not a policy action. It counts only currently
    usable public mana sources. If the replay card starts on the battlefield it
    must first be bounced, so both that permanent and the Knack source are
    unavailable to pay for the recast. If the card starts in hand, a Battered
    Golem source may tap through Urza before the cast because that cast untaps it.
    """
    blue_capable=s.blue
    total=s.blue+s.colorless
    metal=artifact_count(s)>=3

    for p in s.battlefield:
        if p.tapped:
            continue
        if on_battlefield and (
            p.instance_tag==source.instance_tag or p.name==card
        ):
            continue

        n=p.name
        native_total=0
        native_blue=0
        if n in {
            "Island","Cephalid Coliseum","Ipnu Rivulet",
            "Minamo, School at Water's Edge","Oboro, Palace in the Clouds",
            "Otawara, Soaring City","Seat of the Synod",
        }:
            native_total=native_blue=1
        elif n in MDFC_BLUE_LANDS and p.mode=="landface":
            native_total=native_blue=1
        elif n=="Urza's Saga" and p.counters>=1:
            native_total=1
        elif n in {"Ancient Tomb","City of Traitors"}:
            native_total=2
        elif n=="Crystal Vein":
            native_total=2
        elif n=="Saprazzan Skerry" and p.counters>0:
            native_total=native_blue=2
        elif n=="Gemstone Caverns":
            native_total=1
            native_blue=1 if p.mode=="luck" else 0
        elif n=="Sol Ring":
            native_total=2
        elif n in {"Mana Vault","Grim Monolith","Basalt Monolith"}:
            native_total=3
        elif n=="Mox Opal" and metal:
            native_total=native_blue=1
        elif n in {"Chrome Mox","Mox Diamond"} and p.mode in {"imprinted","diamond"}:
            native_total=native_blue=1
        elif n=="Everflowing Chalice" and p.counters>0:
            native_total=p.counters
        elif n=="Lotus Petal" or p.mode=="treasure":
            native_total=native_blue=1

        if s.urza and is_artifact_perm(p):
            # Urza can make U from any untapped artifact. Pick the better native
            # total output, but if equal prefer the blue-capable Urza use.
            if native_total<=1:
                total += 1
                blue_capable += 1
            else:
                total += native_total
                blue_capable += native_blue
        else:
            total += native_total
            blue_capable += native_blue

    return blue_capable,total


def can_bootstrap_replay_cast(
    s:State,source:Perm,card:str,*,in_hand:bool,on_battlefield:bool
)->bool:
    generic,blue_req=spell_cost(s,card,outside=False)
    if can_pay(s,generic,blue_req):
        return True
    blue_capable,total=_immediate_replay_mana_capacity(
        s,source,card,on_battlefield=(on_battlefield and not in_hand)
    )
    return blue_capable>=blue_req and total>=generic+blue_req


def zero_or_positive_replay_artifacts(s:State)->set:
    """Compatibility helper for existing diagnostics."""
    dummy=Perm("Valley Floodcaller",instance_tag=-1)
    rows=set()
    for card in set(s.hand)|set(bf_names(s)):
        margin=replay_mana_margin(s,dummy,card)
        if margin is not None and margin>=0:
            rows.add(card)
    return rows


def knack_replay_loop_family(s:State)->str:
    """Recognize deterministic positive Knack/Helix replay loops.

    The source must be a live Battered Golem or Valley Floodcaller carrying the
    grant. The replay artifact must refresh that source every cycle. Base
    positive artifacts win directly; neutral/negative artifacts win only when
    visible Urza/producer economics promote the steady-state margin above zero.
    """
    if not s.urza:
        return ""

    for source in s.battlefield:
        if not is_knack_target_perm(s,source) or source.sick:
            continue
        if source.name not in {"Battered Golem","Valley Floodcaller"}:
            continue

        for card in _candidate_replay_cards(s,source):
            if not _replay_refreshes_knack_source(source,card):
                continue

            in_hand=card in s.hand
            on_battlefield=any(
                p.name==card and p.instance_tag!=source.instance_tag
                for p in s.battlefield
            )
            if source.tapped and not in_hand:
                continue
            if not in_hand and not on_battlefield:
                continue

            # Steady-state positivity is not enough: the first replay
            # must be payable from the current visible resources. Include mana
            # that can be produced immediately before the first cast, but reserve
            # the Knack source when it must tap to bounce an artifact already on
            # the battlefield.
            if not can_bootstrap_replay_cast(
                s,source,card,in_hand=in_hand,on_battlefield=on_battlefield
            ):
                continue

            margin=replay_mana_margin(s,source,card)
            if margin is None or margin<=0:
                continue
            return (
                "Knack/Helix + Battered Golem"
                if source.name=="Battered Golem"
                else "Knack/Helix + Valley Floodcaller"
            )
    return ""


CHROME_DOME_THREE_MANA_COPY_TARGETS=frozenset({
    "Mana Vault","Grim Monolith","Basalt Monolith",
})

def chrome_dome_positive_copy_target(s:State)->str:
    """Return a visible Chrome Dome copy target that yields positive mana.

    Chrome Dome costs {5} to activate. Power Artifact enchanting Chrome Dome
    reduces that by {2}; Forensic Gadgeteer reduces it by another {1}; the
    resulting activation costs {2}. A fresh token copy of Mana Vault, Grim
    Monolith, or Basalt Monolith enters untapped and taps for {3}, so each
    iteration nets +1 mana and can be repeated arbitrarily.

    The first activation must still be bootstrap-payable from the current
    visible state. The original 3-mana rock may itself provide that bootstrap
    when untapped. Power Artifact must actually enchant Chrome Dome; merely
    having the Aura somewhere on the battlefield is not sufficient.
    """
    names=bf_name_set(s)
    if (
        "Chrome Dome" not in names
        or "Forensic Gadgeteer" not in names
        or "Power Artifact" not in names
        or s.pa_target!="Chrome Dome"
    ):
        return ""

    # Both reductions have a floor of one mana, but from {5} they combine
    # cleanly to {2}.
    activation=5
    activation=max(1,activation-1)  # Forensic Gadgeteer
    activation=max(1,activation-2)  # Power Artifact on Chrome Dome
    if activation>=3:
        return ""

    target=next(
        (name for name in ("Mana Vault","Grim Monolith","Basalt Monolith")
         if name in names),
        "",
    )
    if not target:
        return ""

    # A copied target does not copy tapped status and therefore enters untapped.
    # The existing target can bootstrap the first activation if it is untapped;
    # immediately_available_generic_mana() counts that native {3} correctly.
    if immediately_available_generic_mana(s)<activation:
        return ""
    return target


def infinite_colorless_online(s:State)->bool:
    names=bf_name_set(s)
    if chrome_dome_positive_copy_target(s):
        return True
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
        elif n in MDFC_BLUE_LANDS and p.mode=="landface":
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


def immediately_available_generic_mana(s:State)->int:
    """Maximum currently spendable mana without changing zones/searching.

    Used only for deterministic combo bootstrap checks. For an untapped artifact,
    count the better of its native tap ability and Urza's +U conversion, never
    both. This deliberately does not assume a future land drop or tutor.
    """
    total=s.blue+s.colorless
    metal=artifact_count(s)>=3
    for p in s.battlefield:
        if p.tapped:
            continue
        n=p.name
        native=0
        if n in {
            "Island","Cephalid Coliseum","Ipnu Rivulet",
            "Minamo, School at Water's Edge","Oboro, Palace in the Clouds",
            "Otawara, Soaring City","Seat of the Synod",
        }:
            native=1
        elif n in MDFC_BLUE_LANDS and p.mode=="landface":
            native=1
        elif n=="Urza's Saga" and p.counters>=1:
            native=1
        elif n in {"Ancient Tomb","City of Traitors"}:
            native=2
        elif n=="Crystal Vein":
            native=2
        elif n=="Saprazzan Skerry" and p.counters>0:
            native=2
        elif n=="Gemstone Caverns":
            native=1
        elif n=="Sol Ring":
            native=2
        elif n in {"Mana Vault","Grim Monolith","Basalt Monolith"}:
            native=3
        elif n=="Mox Opal" and metal:
            native=1
        elif n in {"Chrome Mox","Mox Diamond"} and p.mode in {"imprinted","diamond"}:
            native=1
        elif n=="Everflowing Chalice" and p.counters>0:
            native=p.counters
        elif n=="Lotus Petal" or p.mode=="treasure":
            native=1

        urza_mana=1 if s.urza and is_artifact_perm(p) else 0
        total += max(native,urza_mana)
    return total


def monolith_untap_cost(s:State,name:str)->int:
    if name=="Grim Monolith":
        cost=4
    elif name=="Basalt Monolith":
        cost=3
    else:
        raise ValueError(f"unsupported monolith {name!r}")
    if has(s,"Forensic Gadgeteer"):
        cost-=1
    if s.pa_target==name:
        cost-=2
    return max(1,cost)


def monolith_positive_loop_online(s:State,name:str)->bool:
    """Whether the currently visible Monolith can bootstrap its positive loop."""
    perm=next((p for p in s.battlefield if p.name==name),None)
    if perm is None:
        return False
    # If it is untapped, its own first mana activation bootstraps the loop.
    if not perm.tapped:
        return True
    # If already tapped, the first reduced untap must be payable from other
    # currently available resources/floating mana.
    return immediately_available_generic_mana(s)>=monolith_untap_cost(s,name)


def check_win(s:State)->State:
    # A pending cumulative-upkeep trigger must be resolved before the solver
    # can use main-phase terminal recognizers. Upkeep-specific instant actions
    # are handled by the restricted transition closure instead.
    if s.remora_upkeep_pending:
        return s
    names=bf_name_set(s)

    if not s.urza:
        return s

    if (
        "Power Artifact" in names
        and "Grim Monolith" in names
        and s.pa_target=="Grim Monolith"
        and monolith_positive_loop_online(s,"Grim Monolith")
    ):
        return replace(s,won=True,win_family="Power Artifact + Grim")
    if (
        "Power Artifact" in names
        and "Basalt Monolith" in names
        and s.pa_target=="Basalt Monolith"
        and monolith_positive_loop_online(s,"Basalt Monolith")
    ):
        return replace(s,won=True,win_family="Power Artifact + Basalt")
    if (
        "Forensic Gadgeteer" in names
        and "Basalt Monolith" in names
        and monolith_positive_loop_online(s,"Basalt Monolith")
    ):
        return replace(s,won=True,win_family="Basalt + Gadgeteer")

    knack_loop=knack_replay_loop_family(s)
    if knack_loop:
        return replace(s,won=True,win_family=knack_loop)

    if "Sensei's Divining Top" in names:
        chip_active=(
            s.chip_attached
            and bool(s.chip_target)
            and any(
                p.name=="The Reality Chip" and p.mode=="chip_attached"
                for p in s.battlefield
            )
        )
        if chip_active and not cage_in_play(s) and names & PRODUCERS:
            return replace(s,won=True,win_family="Top + Reality Chip")
        if s.ftt_level>=3 and s.spell_cast_this_turn and not cage_in_play(s):
            return replace(s,won=True,win_family="Top + FTT L3")
        if s.ftt_level>=2 and s.spell_cast_this_turn and not cage_in_play(s) and names & PRODUCERS:
            return replace(s,won=True,win_family="Top + FTT L2 + producer")
        if "Forensic Gadgeteer" in names and not cage_in_play(s) and names & {"Grinding Station","Battered Golem"}:
            return replace(s,won=True,win_family="Top + Gadgeteer + producer")

    if "Sewer-veillance Cam" in names and has_knack_grant(s):
        target_live=any(
            is_knack_target_perm(s,p)
            and not p.sick and not p.tapped
            for p in s.battlefield
        )
        if target_live:
            return replace(s,won=True,win_family="Knack/Helix + Cam")

    chrome_mana_target=chrome_dome_positive_copy_target(s)
    if chrome_mana_target:
        return replace(
            s,won=True,
            win_family=f"Chrome Dome + PA + Gadgeteer + {chrome_mana_target}",
        )

    if "Chrome Dome" in names and names & {"Grinding Station","Battered Golem"}:
        reduction=(1 if "Forensic Gadgeteer" in names else 0)+(
            2 if ("Power Artifact" in names and s.pa_target=="Chrome Dome") else 0
        )
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
    bf=tuple(sorted((p.name,p.tapped,p.sick,p.counters,p.mode,p.knack_granted)
                    for p in s.battlefield))
    return (
        s.turn,bf,tuple(sorted(s.hand)),s.library[:5],
        tuple(sorted(s.graveyard)),tuple(sorted(s.exile)),
        tuple(sorted(s.urza_exile_permissions)),tuple(s.oracle_stack),
        s.land_played,s.drain_bank,
        s.remora_age,s.remora_upkeep_pending,
        s.urza,s.ftt_level,s.uthros_counters,
        s.chip_attached,s.chip_target,
        s.pa_target,
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
        # spendable resource vector. If resource vectors are exactly tied, use
        # score so monotone optional-resource annotations (for example a
        # refundable producer Urza tap) keep the richer representative.
        s_dom=(s.blue>=old.blue and s.colorless>=old.colorless and len(s.hand)>=len(old.hand))
        old_dom=(old.blue>=s.blue and old.colorless>=s.colorless and len(old.hand)>=len(s.hand))
        if s_dom and not old_dom:
            best[sig]=s
        elif s_dom and old_dom:
            if score(s)>score(old):
                best[sig]=s
        elif not old_dom and score(s)>score(old):
            best[sig]=s
    return list(best.values())



def classify_action(trace_msg:str)->str:
    # Automatic draw details can share an existing semantic trace entry. Keep
    # diagnostics classified by the original action/header line.
    m=trace_msg.splitlines()[0].lower()
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
        "upkeep_nodes_expanded":0,
        "upkeep_edges_generated":0,
        "upkeep_exact_key_merges":0,
        "upkeep_dominance_pruned":0,
        "upkeep_beam_pruned":0,
        "upkeep_layers":0,
        "upkeep_max_frontier":0,
        "upkeep_max_raw_successors":0,
        "remora_pay_results_generated":0,
        "remora_decline_results_generated":0,
        "remora_bounce_results_generated":0,
    }

def merge_graph_stats(dst,src):
    for k in dst:
        if k in {
            "max_frontier","max_raw_successors",
            "upkeep_max_frontier","upkeep_max_raw_successors",
        }:
            dst[k]=max(dst[k],src.get(k,0))
        else:
            dst[k]+=src.get(k,0)
    return dst

def finalize_graph_stats(g):
    nodes=max(1,g.get("nodes_expanded",0))
    upkeep_nodes=max(1,g.get("upkeep_nodes_expanded",0))
    return dict(
        g,
        average_branching_factor=g.get("edges_generated",0)/nodes,
        upkeep_average_branching_factor=(
            g.get("upkeep_edges_generated",0)/upkeep_nodes
        ),
    )


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
    sc += deferred_producer_blue(s)*0.25  # tie-break toward strictly richer equivalent state
    sc += len(s.hand)*5
    sc += len(s.urza_exile_permissions)*7
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
    x=ns.trace[-1].splitlines()[0]
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

DIRECT_COMBO_TARGETS=frozenset({
    "Sensei's Divining Top","The Reality Chip","Fortune Teller's Talent",
    "Forensic Gadgeteer","Grinding Station","Battered Golem",
    "Power Artifact","Grim Monolith","Basalt Monolith","Chrome Dome",
    "Sewer-veillance Cam","Banishing Knack","Retraction Helix",
})
VALIDATED_ENGINE_ACCESS_TARGETS=frozenset({
    "Spellseeker","Transmute Artifact","Reshape","Whir of Invention",
    "Uthros Research Craft","Valley Floodcaller",
})
KNOWN_ENGINE_TARGETS=DIRECT_COMBO_TARGETS|VALIDATED_ENGINE_ACCESS_TARGETS
# Useful setup/card-advantage engines are reported separately from the
# high-confidence combo/validated-access set above.
KNOWN_SETUP_ENGINE_TARGETS=frozenset(CA_ENGINES-KNOWN_ENGINE_TARGETS)
KNOWN_ENGINE_COMBO_TARGETS=KNOWN_ENGINE_TARGETS|KNOWN_SETUP_ENGINE_TARGETS

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
        "lost_known_engine_combo_target_events":0,
        "lost_direct_combo_target_events":0,
        "lost_engine_access_target_events":0,
        "lost_target_destination_route_events":0,
        "lost_engine_target_destination_route_events":0,
        "route_representative_overflow_states":0,
        "route_representative_overflow_excess_total":0,
        "target_reserve_overflow_states":0,
        "max_unique_tutor_routes_before_cap":0,
        "max_target_aware_reserve_size":0,
        "source_counts_raw":collections.Counter(),
        "source_counts_kept":collections.Counter(),
        "source_unique_targets_raw_total":collections.Counter(),
        "source_unique_targets_kept_total":collections.Counter(),
        "source_lost_target_events":collections.Counter(),
        "source_lost_engine_target_events":collections.Counter(),
        "source_lost_target_destination_route_events":collections.Counter(),
        "source_lost_engine_target_destination_route_events":collections.Counter(),
        "target_counts_raw":collections.Counter(),
        "target_counts_kept":collections.Counter(),
        "lost_targets":collections.Counter(),
        "lost_engine_targets":collections.Counter(),
        "lost_known_engine_combo_targets":collections.Counter(),
        "lost_direct_combo_targets":collections.Counter(),
        "lost_engine_access_targets":collections.Counter(),
        "lost_engine_target_destination_routes":collections.Counter(),
        "lost_setup_engine_targets":collections.Counter(),
        "cap_hit_states":[],
        "worst_states":[],
        "_current_seed":None,
    }

def _tutor_action_from_trace(st):
    """Return (source, target, destination) for a target-selecting search action."""
    if not st.trace:
        return None,None,None
    t=st.trace[-1].splitlines()[0]
    if t.startswith("Transmute ") and "->" in t:
        target=t.split("->",1)[1].split(";",1)[0].strip()
        destination="graveyard" if "; decline " in t else "battlefield"
        return "Transmute Artifact",target,destination
    if t.startswith("Reshape X=") and "->" in t:
        return "Reshape",t.split("->",1)[1].split(";",1)[0].strip(),"battlefield"
    if t.startswith("Whir X=") and "->" in t:
        return "Whir of Invention",t.split("->",1)[1].strip(),"battlefield"
    if t.startswith("Spellseeker ETB -> "):
        return "Spellseeker",t.split("->",1)[1].strip(),"hand"
    mystical_prefix="Mystical -> shuffle, then top "
    if t.startswith(mystical_prefix):
        return "Mystical Tutor",t[len(mystical_prefix):].strip(),"library top"
    for src in ("Dizzy Spell","Muddle the Mixture","Merchant Scroll"):
        if t.startswith(src+" -> "):
            return src,t.split("->",1)[1].strip(),"hand"
    if t.startswith("Tezzeret -3 -> "):
        return "Tezzeret, Cruel Captain",t.split("->",1)[1].strip(),"hand"
    saga_prefix="Saga III puts "
    saga_suffix=" onto battlefield"
    if t.startswith(saga_prefix) and t.endswith(saga_suffix):
        return "Urza's Saga",t[len(saga_prefix):-len(saga_suffix)].strip(),"battlefield"
    if t.startswith("Repurposing Bay sacs ") and " -> " in t:
        return "Repurposing Bay",t.split(" -> ",1)[1].strip(),"battlefield"
    scour_prefix="Scour tutors "
    if t.startswith(scour_prefix):
        target=t[len(scour_prefix):].split(" + returns ",1)[0].strip()
        return "Scour for Scrap",target,"hand"
    # Fetchlands have one fixed modeled target (Island), so they cannot lose
    # target diversity and are intentionally outside this tutor-choice audit.
    return None,None,None

def _tutor_source_target_from_trace(st):
    """Backward-compatible source/target view used by focused diagnostics."""
    source,target,_destination=_tutor_action_from_trace(st)
    return source,target

def _select_actions_with_tutor_diversity(actions):
    """Apply ACTION_CAP while retaining strategically distinct tutor routes.

    A route is (source, target, destination). When all route representatives
    fit, retain the best-scoring action for every route, then fill unused slots
    by the existing global score order (including non-tutor actions).

    More than ACTION_CAP routes cannot all be retained under the strict cap.
    In that overflow case, retain every known engine/combo route first, then
    one best representative for each still-uncovered target, then the
    best-scoring remaining route representatives. This makes the unavoidable
    loss deterministic and prevents redundant payment/sacrifice branches from
    erasing a whole strategic target.
    """
    keep_n=min(ACTION_CAP,len(actions))
    if keep_n<=0:
        return []
    if len(actions)<=ACTION_CAP:
        return heapq.nlargest(keep_n,actions,key=score)

    scores=[score(action) for action in actions]
    ranked_indices=sorted(range(len(actions)),key=lambda i:scores[i],reverse=True)

    # Iterating in global rank order makes the first action seen for a route
    # its best-scoring representative; stable sorting preserves generation
    # order for exact score ties.
    route_for_index={}
    representative_indices=[]
    seen_routes=set()
    for i in ranked_indices:
        route=_tutor_action_from_trace(actions[i])
        if not route[0] or not route[1]:
            continue
        route_for_index[i]=route
        if route not in seen_routes:
            seen_routes.add(route)
            representative_indices.append(i)

    if not representative_indices:
        return [actions[i] for i in ranked_indices[:keep_n]]

    selected=set()

    def retain(i):
        if len(selected)<keep_n:
            selected.add(i)

    if len(representative_indices)<=keep_n:
        for i in representative_indices:
            retain(i)
    else:
        # All known strategic routes fit in the deterministic audit corpus.
        # The target-first sub-fallback keeps this safe if that changes later.
        known_representatives=[
            i for i in representative_indices
            if route_for_index[i][1] in KNOWN_ENGINE_COMBO_TARGETS
        ]
        if len(known_representatives)>keep_n:
            covered_targets=set()
            for i in known_representatives:
                target=route_for_index[i][1]
                if target not in covered_targets:
                    retain(i)
                    covered_targets.add(target)
            for i in known_representatives:
                retain(i)
        else:
            for i in known_representatives:
                retain(i)

        # Preserve whole target identities before choosing between additional
        # source/destination routes for the same target.
        covered_targets={route_for_index[i][1] for i in selected}
        for i in representative_indices:
            target=route_for_index[i][1]
            if target not in covered_targets:
                retain(i)
                covered_targets.add(target)

        # The route guarantee is mathematically impossible in overflow, so use
        # remaining capacity for the best-scoring unrepresented routes.
        for i in representative_indices:
            retain(i)

    # Ordinary cap hits can have spare capacity after route protection. Keep
    # the old global competition among non-tutors and duplicate tutor routes.
    for i in ranked_indices:
        retain(i)

    return [actions[i] for i in ranked_indices if i in selected]

def _tutor_source_retention(raw_actions,kept_actions):
    """Build per-source action, target, and destination-route retention."""
    sources=sorted({src for src,_,_ in raw_actions}|{src for src,_,_ in kept_actions})
    out={}
    for src in sources:
        raw=[x for x in raw_actions if x[0]==src]
        kept=[x for x in kept_actions if x[0]==src]
        raw_targets={target for _,target,_ in raw}
        kept_targets={target for _,target,_ in kept}
        raw_routes={(target,destination) for _,target,destination in raw}
        kept_routes={(target,destination) for _,target,destination in kept}
        lost_targets=raw_targets-kept_targets
        lost_routes=raw_routes-kept_routes
        lost_engine_routes={(target,destination) for target,destination in lost_routes
                            if target in KNOWN_ENGINE_COMBO_TARGETS}
        out[src]={
            "raw_action_count":len(raw),
            "kept_action_count":len(kept),
            "action_retention_rate":len(kept)/len(raw) if raw else 1.0,
            "unique_target_count_before_cap":len(raw_targets),
            "unique_target_count_after_cap":len(kept_targets),
            "target_retention_rate":len(kept_targets)/len(raw_targets) if raw_targets else 1.0,
            "unique_targets_before_cap":sorted(raw_targets),
            "unique_targets_after_cap":sorted(kept_targets),
            "targets_completely_lost":sorted(lost_targets),
            "known_engine_combo_targets_completely_lost":sorted(lost_targets&KNOWN_ENGINE_COMBO_TARGETS),
            "direct_combo_targets_completely_lost":sorted(lost_targets&DIRECT_COMBO_TARGETS),
            "validated_engine_access_targets_completely_lost":sorted(lost_targets&VALIDATED_ENGINE_ACCESS_TARGETS),
            "target_destination_routes_before_cap":[
                {"target":target,"destination":destination}
                for target,destination in sorted(raw_routes)
            ],
            "target_destination_routes_after_cap":[
                {"target":target,"destination":destination}
                for target,destination in sorted(kept_routes)
            ],
            "target_destination_routes_completely_lost":[
                {"target":target,"destination":destination}
                for target,destination in sorted(lost_routes)
            ],
            "known_engine_combo_target_destination_routes_completely_lost":[
                {"target":target,"destination":destination}
                for target,destination in sorted(lost_engine_routes)
            ],
        }
    return out

def _tutor_cap_state_fingerprint(state):
    # Full state except trace, so duplicate-looking rows can be distinguished
    # without embedding every library card in the report.
    payload=repr(replace(state,trace=())).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]

def tutor_source_retention_summary(a):
    sources=sorted(set(a["source_counts_raw"])|set(a["source_counts_kept"]))
    out={}
    for src in sources:
        raw=a["source_counts_raw"][src]
        kept=a["source_counts_kept"][src]
        raw_targets=a["source_unique_targets_raw_total"][src]
        kept_targets=a["source_unique_targets_kept_total"][src]
        out[src]={
            "raw_action_count":raw,
            "kept_action_count":kept,
            "action_retention_rate":kept/raw if raw else 1.0,
            "state_summed_unique_target_count_before_cap":raw_targets,
            "state_summed_unique_target_count_after_cap":kept_targets,
            "target_retention_rate":kept_targets/raw_targets if raw_targets else 1.0,
            "targets_completely_lost_events":a["source_lost_target_events"][src],
            "known_engine_combo_targets_completely_lost_events":a["source_lost_engine_target_events"][src],
            "target_destination_routes_completely_lost_events":a["source_lost_target_destination_route_events"][src],
            "known_engine_combo_target_destination_routes_completely_lost_events":a["source_lost_engine_target_destination_route_events"][src],
        }
    return out

def _record_tutor_cap_state(raw_actions,kept_actions,state,context="normal"):
    global _TUTOR_CAP_AUDIT
    if not _TUTOR_CAP_AUDIT_ENABLED or _TUTOR_CAP_AUDIT is None or len(raw_actions)<=ACTION_CAP:
        return
    aud=_TUTOR_CAP_AUDIT
    aud["truncated_states"]+=1
    raw_tutors=[p for p in (_tutor_action_from_trace(a) for a in raw_actions) if p[0] and p[1]]
    kept_tutors=[p for p in (_tutor_action_from_trace(a) for a in kept_actions) if p[0] and p[1]]
    if not raw_tutors:
        return
    aud["tutor_truncated_states"]+=1
    aud["raw_tutor_actions"]+=len(raw_tutors)
    aud["kept_tutor_actions"]+=len(kept_tutors)
    for src,tgt,_ in raw_tutors:
        aud["source_counts_raw"][src]+=1; aud["target_counts_raw"][tgt]+=1
    for src,tgt,_ in kept_tutors:
        aud["source_counts_kept"][src]+=1; aud["target_counts_kept"][tgt]+=1

    raw_targets=set(t for _,t,_ in raw_tutors)
    kept_targets=set(t for _,t,_ in kept_tutors)
    lost=raw_targets-kept_targets
    lost_engine=lost & KNOWN_ENGINE_TARGETS
    lost_known_engine_combo=lost & KNOWN_ENGINE_COMBO_TARGETS
    lost_direct=lost & DIRECT_COMBO_TARGETS
    lost_access=lost & VALIDATED_ENGINE_ACCESS_TARGETS
    lost_setup=lost & KNOWN_SETUP_ENGINE_TARGETS
    raw_routes=set(raw_tutors)
    kept_routes=set(kept_tutors)
    lost_routes=raw_routes-kept_routes
    lost_engine_routes={(src,target,destination) for src,target,destination in lost_routes
                        if target in KNOWN_ENGINE_COMBO_TARGETS}
    known_routes={route for route in raw_routes if route[1] in KNOWN_ENGINE_COMBO_TARGETS}
    nonknown_targets={target for _source,target,_destination in raw_routes
                      if target not in KNOWN_ENGINE_COMBO_TARGETS}
    target_aware_reserve_size=len(known_routes)+len(nonknown_targets)
    route_overflow=max(0,len(raw_routes)-ACTION_CAP)
    source_retention=_tutor_source_retention(raw_tutors,kept_tutors)

    aud["unique_targets_raw_total"]+=len(raw_targets)
    aud["unique_targets_kept_total"]+=len(kept_targets)
    aud["lost_target_events"]+=len(lost)
    aud["lost_engine_target_events"]+=len(lost_engine)
    aud["lost_known_engine_combo_target_events"]+=len(lost_known_engine_combo)
    aud["lost_direct_combo_target_events"]+=len(lost_direct)
    aud["lost_engine_access_target_events"]+=len(lost_access)
    aud["lost_target_destination_route_events"]+=len(lost_routes)
    aud["lost_engine_target_destination_route_events"]+=len(lost_engine_routes)
    aud["max_unique_tutor_routes_before_cap"]=max(
        aud["max_unique_tutor_routes_before_cap"],len(raw_routes)
    )
    aud["max_target_aware_reserve_size"]=max(
        aud["max_target_aware_reserve_size"],target_aware_reserve_size
    )
    if route_overflow:
        aud["route_representative_overflow_states"]+=1
        aud["route_representative_overflow_excess_total"]+=route_overflow
    if target_aware_reserve_size>ACTION_CAP:
        aud["target_reserve_overflow_states"]+=1
    for t in lost: aud["lost_targets"][t]+=1
    for t in lost_engine: aud["lost_engine_targets"][t]+=1
    for t in lost_known_engine_combo: aud["lost_known_engine_combo_targets"][t]+=1
    for t in lost_direct: aud["lost_direct_combo_targets"][t]+=1
    for t in lost_access: aud["lost_engine_access_targets"][t]+=1
    for t in lost_setup: aud["lost_setup_engine_targets"][t]+=1
    for src,target,destination in lost_engine_routes:
        aud["lost_engine_target_destination_routes"][f"{src} -> {target} [{destination}]"]+=1
    for src,retention in source_retention.items():
        aud["source_unique_targets_raw_total"][src]+=retention["unique_target_count_before_cap"]
        aud["source_unique_targets_kept_total"][src]+=retention["unique_target_count_after_cap"]
        aud["source_lost_target_events"][src]+=len(retention["targets_completely_lost"])
        aud["source_lost_engine_target_events"][src]+=len(retention["known_engine_combo_targets_completely_lost"])
        aud["source_lost_target_destination_route_events"][src]+=len(retention["target_destination_routes_completely_lost"])
        aud["source_lost_engine_target_destination_route_events"][src]+=len(retention["known_engine_combo_target_destination_routes_completely_lost"])

    row={
        "seed":aud.get("_current_seed"),
        "state_fingerprint":_tutor_cap_state_fingerprint(state),
        "turn":state.turn,
        "raw_actions":len(raw_actions),
        "kept_actions":len(kept_actions),
        "raw_tutor_actions":len(raw_tutors),
        "kept_tutor_actions":len(kept_tutors),
        "raw_tutor_action_count":len(raw_tutors),
        "kept_tutor_action_count":len(kept_tutors),
        "raw_unique_targets":len(raw_targets),
        "kept_unique_targets":len(kept_targets),
        "raw_unique_tutor_routes":len(raw_routes),
        "kept_unique_tutor_routes":len(kept_routes),
        "route_representative_overflow":route_overflow,
        "target_aware_reserve_size":target_aware_reserve_size,
        "unique_target_count_before_cap":len(raw_targets),
        "unique_target_count_after_cap":len(kept_targets),
        "unique_targets_before_cap":sorted(raw_targets),
        "unique_targets_after_cap":sorted(kept_targets),
        "lost_targets":sorted(lost),
        "lost_engine_targets":sorted(lost_engine),
        "lost_known_engine_combo_targets":sorted(lost_known_engine_combo),
        "lost_direct_combo_targets":sorted(lost_direct),
        "lost_validated_engine_access_targets":sorted(lost_access),
        "lost_setup_engine_targets":sorted(lost_setup),
        "tutor_sources":sorted(source_retention),
        "targets_completely_lost":sorted(lost),
        "known_engine_combo_targets_completely_lost":sorted(lost_known_engine_combo),
        "target_destination_routes_completely_lost":[
            {"source":src,"target":target,"destination":destination}
            for src,target,destination in sorted(lost_routes)
        ],
        "known_engine_combo_target_destination_routes_completely_lost":[
            {"source":src,"target":target,"destination":destination}
            for src,target,destination in sorted(lost_engine_routes)
        ],
        "raw_sources":dict(collections.Counter(src for src,_,_ in raw_tutors)),
        "kept_sources":dict(collections.Counter(src for src,_,_ in kept_tutors)),
        "source_retention":source_retention,
        "context":context,
        "state":{
            "hand":list(state.hand),
            "battlefield":[{
                "name":p.name,"tapped":p.tapped,"sick":p.sick,
                "counters":p.counters,"mode":p.mode,
                "knack_granted":p.knack_granted,
                "producer_urza_ready":p.producer_urza_ready,
            } for p in state.battlefield],
            "graveyard":list(state.graveyard),
            "exile":list(state.exile),
            "blue":state.blue,"colorless":state.colorless,
            "land_played":state.land_played,
            "urza":state.urza,
            "commander_in_command_zone":state.commander_in_command_zone,
            "commander_casts_from_zone":state.commander_casts_from_zone,
            "ftt_level":state.ftt_level,
            "chip_attached":state.chip_attached,
            "chip_target":state.chip_target,
            "spell_cast_this_turn":state.spell_cast_this_turn,
            "knack_grants":[
                {"name":p.name,"mode":p.mode,"source":p.knack_source}
                for p in state.battlefield if p.knack_granted
            ],
            "pa_target":state.pa_target,
            "library_size":len(state.library),
            "library_top":list(state.library[:10]),
            "trace_tail":list(state.trace[-8:]),
        },
    }
    aud["cap_hit_states"].append(row)
    aud["worst_states"].append(row)
    aud["worst_states"]=sorted(
        aud["worst_states"],
        key=lambda r:(len(r["known_engine_combo_target_destination_routes_completely_lost"]),
                      len(r["lost_known_engine_combo_targets"]),len(r["lost_engine_targets"]),
                      len(r["lost_targets"]),
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


def _enter_precombat_main(s:State)->State:
    """Take the natural draw, then finish setup for the first main phase."""
    if s.remora_upkeep_pending:
        raise ValueError("cannot enter the precombat main phase with Remora upkeep pending")

    s,drawn=draw_from_library(s,1)
    if drawn:
        s=append_trace_detail(
            s,f"normal draw for turn {s.turn}: {drawn[0]}"
        )

    # Sagas receive their turn-based lore counter in the first precombat main
    # phase, after cumulative upkeep. In particular, a Saga that did not
    # already have a lore counter cannot be used to pay Remora first.
    b=[]
    saga3_pending=s.saga3_pending
    for p in s.battlefield:
        q=p
        if q.name=="Urza's Saga":
            nc=q.counters+1
            q=replace(q,counters=nc,mode="saga3" if nc>=3 else q.mode)
            if nc>=3:
                saga3_pending=True
        b.append(q)

    # Mana Drain's modeled mana is added in our precombat main phase. Any mana
    # floated while resolving cumulative upkeep has emptied before this point.
    return replace(
        s,battlefield=tuple(b),saga3_pending=saga3_pending,
        blue=0,colorless=s.drain_bank,drain_bank=0
    )


def _remora_upkeep_mana_actions(s:State,payment_already_available:bool=False)->List[State]:
    """Mana-producing actions allowed while Remora's upkeep trigger is pending."""
    # Fetching can be strategically relevant even after enough mana is pooled,
    # because it shuffles before the normal draw. The actual mana sources are
    # suppressed once payment is available unless a modeled instant response
    # still needs additional/colored mana, avoiding strictly wasted extra taps.
    out=fetch_actions(s)
    response_needs_mana=bool(
        ({"Dramatic Reversal","Chain of Vapor","Otawara, Soaring City"}
         |KNUCKS)&set(s.hand)
    ) or has(s,"Aether Spellbomb")
    allow_source_actions=(not payment_already_available or response_needs_mana)
    if allow_source_actions:
        out+=intrinsic_mana_actions(s)+tap_artifact_for_urza_actions(s)

    # This modeled instant can untap nonland mana sources while the cumulative
    # upkeep trigger is on the stack. Sorcery-speed production remains gated.
    if "Dramatic Reversal" in s.hand:
        reversal=cast_from_hand(s,"Dramatic Reversal")
        if reversal is not None:
            out.append(add_trace(reversal,"Dramatic Reversal during Remora upkeep"))

    # Stored Jeweled Amulet mana can be released after it untaps.
    for i,p in enumerate(s.battlefield):
        if (allow_source_actions and p.name=="Jeweled Amulet"
                and not p.tapped and p.counters>0):
            ns=update_perm(s,i,tapped=True,counters=0)
            if p.mode=="amulet_blue":
                ns=replace(ns,blue=ns.blue+1)
            else:
                ns=replace(ns,colorless=ns.colorless+1)
            out.append(add_trace(ns,"Jeweled Amulet releases stored mana during upkeep"))

    # Prototype's ability and Urza's ability are legal despite summoning
    # sickness because the creature/artifact being tapped is paying another
    # permanent's ability, not activating its own tap-symbol ability.
    for i,p in enumerate(s.battlefield):
        if (allow_source_actions and p.name=="Moonsnare Prototype"
                and not p.tapped):
            for j,q in enumerate(s.battlefield):
                if j!=i and not q.tapped and (is_artifact_perm(q) or is_creature_perm(q)):
                    ns=update_perm(s,i,tapped=True)
                    ns=update_perm(ns,j,tapped=True)
                    ns=replace(ns,colorless=ns.colorless+1)
                    out.append(add_trace(ns,f"Moonsnare taps {q.name or q.mode} during upkeep: +C"))

    # A Key can turn already available mana into an untap of a Monolith or
    # another artifact mana source while the cumulative-upkeep trigger is on
    # the stack. Ordinary main-phase-only actions remain gated off.
    for ki,k in enumerate(s.battlefield):
        if k.name in {"Voltaic Key","Manifold Key"} and not k.tapped and can_pay(s,1,0):
            for ti,t in enumerate(s.battlefield):
                if ti!=ki and t.tapped and is_artifact_perm(t):
                    ns=pay(s,1,0)
                    ns=update_perm(ns,ki,tapped=True)
                    ns=update_perm(ns,ti,tapped=False)
                    out.append(add_trace(ns,f"{k.name} during upkeep untaps {t.name or t.mode}"))
    return out


def _finish_absent_remora_upkeep(ns:State)->State:
    """Let the old cumulative-upkeep trigger resolve after its source left."""
    if has(ns,"Mystic Remora"):
        raise ValueError("cannot finish absent-Remora upkeep while Remora remains")
    ns=replace(ns,remora_age=0,remora_upkeep_pending=False)
    ns=add_trace(
        ns,"Mystic Remora cumulative upkeep resolves with Remora absent"
    )
    return _enter_precombat_main(ns)

def _remora_upkeep_bounce_actions(s:State)->List[State]:
    """Instant-speed ways to act on or bounce Remora before upkeep resolves."""
    out=[]

    # Preserve the simple one-target line directly. Chain's broader canonical
    # macro intentionally caps hundreds of copy-chain plans and can otherwise
    # score away this low-board-value, high-upkeep-value bounce.
    if "Chain of Vapor" in s.hand and can_pay(s,*spell_cost(s,"Chain of Vapor")):
        ns=pay(s,*spell_cost(s,"Chain of Vapor"))
        ns=replace(
            ns,hand=remove_one(ns.hand,"Chain of Vapor"),
            graveyard=ns.graveyard+("Chain of Vapor",),
            spell_cast_this_turn=True,
        )
        ns=vfc_noncreature_cast_trigger(ns,"Chain of Vapor")
        ri=next(i for i,p in enumerate(ns.battlefield) if p.name=="Mystic Remora")
        ns=bounce_own_perm(ns,ri)
        ns=add_trace(ns,"Chain of Vapor during upkeep: bounce Mystic Remora")
        out.append(_finish_absent_remora_upkeep(ns))

    for ns in chain_of_vapor_actions(s):
        if not has(ns,"Mystic Remora"):
            ns=_finish_absent_remora_upkeep(ns)
        out.append(ns)

    # Otawara is a channel ability, so it is legal in this response window and
    # neither counts as casting a spell nor triggers spell-cast effects.
    for ns in otawara_channel_actions(s,only_target="Mystic Remora"):
        out.append(_finish_absent_remora_upkeep(ns))

    # Knack/Helix may be cast now targeting a creature. The pending state is
    # revisited by upkeep closure; a ready granted creature may then tap to
    # return Remora. Other ordinary nonland bounces are not expanded here.
    for ns in knack_bounce_actions(s):
        action=ns.trace[-1].splitlines()[0] if ns.trace else ""
        if action.startswith("cast Banishing Knack targeting ") or action.startswith(
            "cast Retraction Helix targeting "
        ):
            out.append(ns)
        elif action.startswith("Knack/Helix target ") and action.endswith(
            "bounces our Mystic Remora"
        ):
            out.append(_finish_absent_remora_upkeep(ns))

    # Both Spellbomb modes are instant-speed activated abilities. Its creature
    # bounce cannot target Remora, but its draw may reveal a payment/bounce
    # enabler before the cumulative-upkeep trigger resolves.
    out.extend(aether_spellbomb_actions(s))
    return out



def _remora_response_source(s:State)->str:
    """Identify the strategically distinct bounce route since upkeep began."""
    for entry in reversed(s.trace):
        lines=entry.splitlines()
        for line in reversed(lines):
            if line.startswith("Mystic Remora cumulative-upkeep trigger pending:"):
                return ""
            if line.startswith("--- Turn "):
                return ""
            if "Chain of Vapor during upkeep:" in line or line.startswith("Chain resolution "):
                return "Chain of Vapor"
            if line.startswith("Otawara channel:"):
                return "Otawara, Soaring City"
            if line.startswith("cast Banishing Knack targeting "):
                return "Banishing Knack"
            if line.startswith("cast Retraction Helix targeting "):
                return "Retraction Helix"
    return ""

def remora_upkeep_actions(s:State)->List[State]:
    """Resolve one pending Mystic Remora cumulative-upkeep decision."""
    if not s.remora_upkeep_pending:
        return []
    if not has(s,"Mystic Remora"):
        # Defensive recovery for a state constructed outside normal zone-change
        # helpers. Normal removal clears both the age and pending flag.
        ns=replace(s,remora_age=0,remora_upkeep_pending=False)
        return [refresh_observability(_enter_precombat_main(ns))]

    remora_idx=next(i for i,p in enumerate(s.battlefield) if p.name=="Mystic Remora")
    # Cumulative upkeep is one triggered ability. Players respond before it
    # resolves; only on resolution does it add the next age counter and ask for
    # payment. Keep remora_age as the actual counters currently on the object
    # throughout that response window.
    cost=s.remora_age+1

    declined=remove_perm(s,remora_idx,to_grave=True)
    declined=add_trace(
        declined,
        f"Mystic Remora cumulative upkeep {{{cost}}}: decline; sacrifice Mystic Remora"
    )
    declined=refresh_observability(_enter_precombat_main(declined))
    out=[declined]

    # Chain is a legal alternative while the upkeep trigger is on the stack,
    # including after enough mana has already been floated to pay.
    out.extend(_remora_upkeep_bounce_actions(s))

    payment_available=can_pay(s,cost,0)
    if payment_available:
        paid=pay(s,cost,0)
        paid=replace(
            paid,remora_age=cost,remora_upkeep_pending=False
        )
        paid=add_trace(paid,f"Mystic Remora cumulative upkeep {{{cost}}}: pay")
        out.append(refresh_observability(_enter_precombat_main(paid)))
    out.extend(
        _remora_upkeep_mana_actions(
            s,payment_already_available=payment_available
        )
    )

    out=[refresh_observability(x) for x in out]
    kept=_select_actions_with_tutor_diversity(out)
    # Preserve terminal pay/decline plus at least one terminal representative
    # for each materially different bounce source. Knack/Helix casts remain
    # pending for one closure step, so protect one pending continuation per
    # spell source too. This prevents ACTION_CAP from turning four legal reset
    # routes into one generic "bounce" result.
    required=[]
    for family in ("pay","decline"):
        family_actions=[
            x for x in out
            if not x.remora_upkeep_pending
            and _remora_resolution_family(x)==family
        ]
        if family_actions:
            required.append(max(family_actions,key=score))

    terminal_bounces=[
        x for x in out
        if not x.remora_upkeep_pending and _remora_resolution_family(x)=="bounce"
    ]
    by_source={}
    for x in terminal_bounces:
        src=_remora_response_source(x) or "generic bounce"
        if src not in by_source or score(x)>score(by_source[src]):
            by_source[src]=x
    required.extend(by_source[src] for src in sorted(by_source))

    pending_continuations=[x for x in out if x.remora_upkeep_pending]
    pending_by_source={}
    generic_pending=[]
    for x in pending_continuations:
        src=_remora_response_source(x)
        if src in KNUCKS:
            if src not in pending_by_source or score(x)>score(pending_by_source[src]):
                pending_by_source[src]=x
        else:
            generic_pending.append(x)
    required.extend(pending_by_source[src] for src in sorted(pending_by_source))
    if generic_pending:
        required.append(max(generic_pending,key=score))
    for required_action in required:
        if required_action in kept:
            continue
        if not kept:
            kept.append(required_action)
            continue
        protected={x for x in required if x in kept}
        replaceable=[i for i,x in enumerate(kept) if x not in protected]
        if replaceable:
            worst=min(replaceable,key=lambda i:score(kept[i]))
            kept[worst]=required_action
    _record_cap_audit(out,kept,context="remora_upkeep")
    return kept

def legal_actions(s:State)->List[State]:
    if s.won:
        return []

    # A paused Oracle stack is a real priority window.  Do not expose lands,
    # planeswalker loyalty, Station, class-leveling, Reconfigure, Repurposing
    # Bay, or other sorcery-only actions here.
    if s.oracle_stack:
        out=oracle_stack_priority_actions(s)
        if not out:
            # Defensive fallback for a hand-built pending-stack state: permit
            # pure passing even though normal cast/priority predecessors already
            # materialize all pass-only frontiers for free.
            out=[x for x in _oracle_stack_pause_frontier(s)
                 if canonical_markov_state_key(x)!=canonical_markov_state_key(s)]
        out=[refresh_observability(x) for x in out]
        kept=_select_actions_with_tutor_diversity(out)
        _record_cap_audit(out,kept,context="oracle_stack_priority")
        return kept

    # Cumulative upkeep resolves after untap and before all ordinary actions.
    # Only its pay/sacrifice choice and relevant mana abilities are exposed.
    if s.remora_upkeep_pending:
        return remora_upkeep_actions(s)

    # Saga III response/tutor window. The trigger remains pending even if a
    # response removes Saga. Keep the window narrow: mana, fetches, Otawara,
    # and resolving III. Chain/Knack cannot target Saga because it is a land.
    if s.saga3_pending:
        out=(intrinsic_mana_actions(s)+tap_artifact_for_urza_actions(s)
             +fetch_actions(s)+saga_actions(s)+oboro_minamo_actions(s)
             +otawara_channel_actions(s,only_target="Urza's Saga"))
        for ki,k in enumerate(s.battlefield):
            if k.name in {"Voltaic Key","Manifold Key"} and not k.tapped and can_pay(s,1,0):
                for ti,x in enumerate(s.battlefield):
                    if ti!=ki and x.tapped and is_artifact_perm(x):
                        ns=pay(s,1,0)
                        ns=update_perm(ns,ki,tapped=True)
                        ns=update_perm(ns,ti,tapped=False)
                        out.append(add_trace(ns,f"{k.name} during Saga III untaps {x.name}"))
        out=[refresh_observability(x) for x in out]
        kept=_select_actions_with_tutor_diversity(out)
        _record_cap_audit(out,kept,context="saga3")
        _record_tutor_cap_state(out,kept,s,context="saga3")
        return kept

    out=[]
    for c in set(s.hand):
        if c in ALL_LANDS:
            out.extend(play_land_variants(s,c))

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
            out.extend(cast_from_hand_variants(s,c))

    out += special_actions(s)
    out=[refresh_observability(x) for x in out]
    kept=_select_actions_with_tutor_diversity(out)
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
        elif n in MDFC_BLUE_LANDS and p.mode=="landface":
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


def end_turn(s:State,schedule_remora_upkeep:bool=True)->State:
    if not can_end_turn_state(s):
        raise ValueError("cannot end a turn with a mandatory phase action unresolved")
    names=bf_name_set(s)
    # Environmental opponent-cycle draw assumptions are intentionally separate
    # from whether Remora is paid for at our following upkeep. A Remora that is
    # sacrificed then has already generated these modeled intervening draws.
    # The former implementation consumed one aggregate top slice in this
    # effective order: delayed Bauble card(s), Remora, Rhystic, Mastermind.
    # Keeping that order makes the previously tested B/R1/R2 assignment
    # explicit without changing the total cards or zones. All happen before a
    # pending Remora decision; the normal draw remains in the library until
    # _enter_precombat_main() after upkeep.
    draw_state=s
    draw_events=[]
    for source in pending_bauble_draw_sources(s):
        draw_state,drawn=draw_from_library(draw_state,1)
        if drawn:
            draw_events.append(f"{source} delayed draw: {drawn[0]}")
    for source,count in (
        ("Mystic Remora",2 if "Mystic Remora" in names else 0),
        ("Rhystic Study",2 if "Rhystic Study" in names else 0),
        ("Faerie Mastermind",1 if "Faerie Mastermind" in names else 0),
    ):
        if count<=0:
            continue
        draw_state,drawn=draw_from_library(draw_state,count)
        if not drawn:
            continue
        if source=="Faerie Mastermind":
            draw_events.append(
                f"Faerie Mastermind environmental draw: {drawn[0]}"
            )
        else:
            draw_events.append(
                f"{source} draws {len(drawn)}: {drawn_cards_text(drawn)}"
            )
    hand=draw_state.hand
    lib=draw_state.library
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
        if p.name in {"Mana Vault","Grim Monolith","Basalt Monolith"}:
            q=replace(p,sick=False,knack_granted=False,knack_source="",producer_urza_ready=False)
        else:
            q=replace(p,tapped=False,sick=False,knack_granted=False,knack_source="",producer_urza_ready=False)
        if q.name=="Battered Golem": q=replace(q,tapped=False)  # multiplayer assumption
        if q.name=="Tezzeret, Cruel Captain": q=replace(q,mode="tez_ready")
        b.append(q)
    remora_pending=schedule_remora_upkeep and has(s,"Mystic Remora")
    ns=replace(s,turn=s.turn+1,library=lib,hand=hand,battlefield=tuple(b),
               blue=0,colorless=0,bauble_draws=0,land_played=False,
               remora_age=(s.remora_age if has(s,"Mystic Remora") else 0),
               remora_upkeep_pending=remora_pending,
               urza_exile_permissions=(),
               spell_cast_this_turn=False,vfc_pumps=0)
    ns=add_trace(ns,f"--- Turn {ns.turn} ---")
    for event in draw_events:
        ns=append_trace_detail(ns,event)
    if remora_pending:
        ns=add_trace(
            ns,
            "Mystic Remora cumulative-upkeep trigger pending: on resolution "
            f"add age counter {ns.remora_age+1}; then pay "
            f"{{{ns.remora_age+1}}} or sacrifice"
        )
    else:
        ns=_enter_precombat_main(ns)
    ns=refresh_observability(ns)
    return ns


def can_end_turn_state(s:State)->bool:
    """Mandatory upkeep and Saga-III windows cannot be skipped at a depth cap."""
    return (
        not s.remora_upkeep_pending
        and not s.saga3_pending
        and not s.oracle_stack
    )


def _remora_resolution_family(s:State)->str:
    for msg in reversed(s.trace):
        action_line=msg.splitlines()[0]
        if action_line.startswith(
            "Mystic Remora cumulative-upkeep trigger pending:"
        ):
            # No resolution marker occurred after the current upkeep boundary.
            return "none"
        if action_line.startswith("--- Turn "):
            return "none"
        if "Mystic Remora cumulative upkeep" not in action_line:
            continue
        if "decline; sacrifice" in action_line:
            return "decline"
        if "resolves with Remora absent" in action_line:
            return "bounce"
        if action_line.endswith(": pay"):
            return "pay"
    return "none"


def _resolve_remora_upkeep_frontier(states,beam:int,graph_stats=None)->List[State]:
    """Close every next-turn upkeep before exposing states to main search."""
    complete={}
    pending=list(states)
    expanded=set()

    while pending:
        next_pending={}
        for s in pending:
            if not s.remora_upkeep_pending:
                s=check_win(s)
                k=s.key()
                old=complete.get(k)
                if old is not None and graph_stats is not None:
                    graph_stats["upkeep_exact_key_merges"]+=1
                if old is None or score(s)>score(old):
                    complete[k]=s
                continue

            k=s.key()
            if k in expanded:
                continue
            expanded.add(k)
            actions=remora_upkeep_actions(s)
            if graph_stats is not None:
                graph_stats["upkeep_nodes_expanded"]+=1
                graph_stats["upkeep_edges_generated"]+=len(actions)
                graph_stats["upkeep_max_raw_successors"]=max(
                    graph_stats["upkeep_max_raw_successors"],len(actions)
                )
            for ns in actions:
                if not ns.remora_upkeep_pending:
                    ns=check_win(ns)
                    family=_remora_resolution_family(ns)
                    if graph_stats is not None and family in {"pay","decline","bounce"}:
                        graph_stats[f"remora_{family}_results_generated"]+=1
                nk=ns.key()
                target=next_pending if ns.remora_upkeep_pending else complete
                old=target.get(nk)
                if old is not None and graph_stats is not None:
                    graph_stats["upkeep_exact_key_merges"]+=1
                if old is None or score(ns)>score(old):
                    target[nk]=ns

        if graph_stats is not None:
            graph_stats["upkeep_layers"]+=1
        if not next_pending:
            break
        raw_candidates=list(next_pending.values())
        candidates=dominance_prune(raw_candidates)
        if graph_stats is not None:
            graph_stats["upkeep_dominance_pruned"]+=max(
                0,len(raw_candidates)-len(candidates)
            )
            graph_stats["upkeep_beam_pruned"]+=max(0,len(candidates)-beam)
        pending=heapq.nlargest(min(beam,len(candidates)),candidates,key=score)
        if graph_stats is not None:
            graph_stats["upkeep_max_frontier"]=max(
                graph_stats["upkeep_max_frontier"],len(pending)
            )

    raw_complete=list(complete.values())
    candidates=dominance_prune(raw_complete)
    if graph_stats is not None:
        graph_stats["upkeep_dominance_pruned"]+=max(
            0,len(raw_complete)-len(candidates)
        )
    keep_n=min(beam,len(candidates))
    if keep_n<=0:
        return []

    ranked=heapq.nlargest(len(candidates),candidates,key=score)
    best_family={}
    for s in ranked:
        family=_remora_resolution_family(s)
        if family in {"pay","decline","bounce"} and family not in best_family:
            best_family[family]=s

    # When capacity permits, retain at least one result for each genuinely
    # different upkeep resolution before filling by the normal global score.
    required=list(best_family.values())
    if len(required)>keep_n:
        required=heapq.nlargest(keep_n,required,key=score)
    if graph_stats is not None:
        graph_stats["upkeep_beam_pruned"]+=max(0,len(candidates)-keep_n)
    selected=[]
    selected_keys=set()
    for s in required+ranked:
        k=s.key()
        if k in selected_keys:
            continue
        selected.append(s)
        selected_keys.add(k)
        if len(selected)>=keep_n:
            break
    return selected


def end_turn_frontier(frontier,beam:int,resolve_remora_upkeep:bool=True,
                      graph_stats=None)->List[State]:
    """Advance a beam and, for searched turns, close Remora upkeep first."""
    resolved=[s for s in frontier if can_end_turn_state(s)]
    transitioned=[
        end_turn(s,schedule_remora_upkeep=resolve_remora_upkeep)
        for s in heapq.nlargest(min(beam,len(resolved)),resolved,key=score)
    ]
    if not resolve_remora_upkeep:
        # The post-horizon state remains a single diagnostic snapshot; do not
        # branch a turn that the configured search will never explore.
        return transitioned
    return _resolve_remora_upkeep_frontier(
        transitioned,beam,graph_stats=graph_stats
    )

def london_opening_zones(deck_order:List[str],keep_n:int,bottom:List[str]):
    """Return the legal London kept hand and library for one fresh seven."""
    if len(deck_order)<7:
        raise ValueError("London mulligan construction requires a seven-card opening hand")
    if keep_n!=7-len(bottom):
        raise ValueError(
            f"keep_n={keep_n} requires {7-keep_n} bottom card(s), got {len(bottom)}"
        )
    hand=list(deck_order[:7])
    for card in bottom:
        try:
            hand.remove(card)
        except ValueError as exc:
            raise ValueError(f"bottom card is not present in opening seven: {card}") from exc
    return hand,tuple(list(deck_order[7:])+list(bottom))

def search_hand(deck_order:List[str], keep_n:int, bottom:List[str], max_turn=7,
                beam=2500, max_actions_per_turn=60, caverns_live=True,
                progress_tag:str="", progress_seconds:float=0.0, graph_stats=None,
                rng_root_seed:int=0)->Tuple[Optional[int],str,Tuple[str,...],int]:
    hand,lib=london_opening_zones(deck_order,keep_n,bottom)
    s=State(turn=1,library=lib,hand=tuple(hand),battlefield=(),rng_root_seed=rng_root_seed,trace=("--- Turn 1 ---",))
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
    s,drawn=draw_from_library(s,1)
    if drawn:
        s=append_trace_detail(s,f"normal draw for turn 1: {drawn[0]}")
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
        states=end_turn_frontier(
            frontier,beam,resolve_remora_upkeep=(turn<max_turn),
            graph_stats=graph_stats,
        )
    last=states[0] if states else s
    return None,"",last.trace if states else (),searched,last.urza_cast_turn,last.interaction_seen,tuple(sorted(last.hand)),max_depth_reached


def profile_single_hand(deck_order:List[str], max_turn:int=3, beam:int=300,
                        max_actions_per_turn:int=60, caverns_live:bool=True,
                        print_every_depth:int=1, rng_root_seed:int=0):
    """
    Run ONE deterministic opening-7 candidate with no oracle mulligan branching.
    This is diagnostic only. It prints per-depth search statistics so we can
    identify where combinatorial explosion originates.
    """
    hand=deck_order[:7]
    lib=tuple(deck_order[7:])
    s=State(turn=1,library=lib,hand=tuple(hand),battlefield=(),rng_root_seed=rng_root_seed,trace=("--- Turn 1 ---",))
    if caverns_live and "Gemstone Caverns" in s.hand:
        # Keep same pregame handling philosophy as normal search by letting the
        # regular search/actions decide actual use; this profiler is about branching.
        pass
    s,drawn=draw_from_library(s,1)
    if drawn:
        s=append_trace_detail(s,f"normal draw for turn 1: {drawn[0]}")
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
        states=end_turn_frontier(
            frontier,beam,resolve_remora_upkeep=(turn<max_turn)
        )

    print(f"\nPROFILE END: no win through T{max_turn}; searched={searched:,}",flush=True)
    return states[0] if states else None


def profile_seed(seed:int, deck:List[str], max_turn:int, beam:int, depth:int):
    rng=random.Random(seed)
    d=deck[:]
    rng.shuffle(d)
    return profile_single_hand(
        d,max_turn=max_turn,beam=beam,
        max_actions_per_turn=depth,caverns_live=True,rng_root_seed=seed
    )

def oracle_mulligan_stages(min_keep:int=4):
    """Return the shared Commander Oracle mulligan stages in RNG order."""
    if min_keep not in {3,4}:
        raise ValueError(f"min_keep must be 3 or 4, got {min_keep}")
    stages=[("7A",0),("7B",0),("6",1),("5",2),("4",3)]
    if min_keep==3:
        stages.append(("3",4))
    return tuple(stages)

def oracle_mulligan_deals(seed:int,deck:List[str],min_keep:int=4):
    """Generate the fixed Caverns result and each fresh-seven stage deal."""
    rng=random.Random(seed)
    caverns_live=(rng.random()<0.75)
    deals=[]
    for label,bottom_n in oracle_mulligan_stages(min_keep):
        shuffled=deck[:]
        rng.shuffle(shuffled)
        deals.append((label,bottom_n,shuffled))
    return caverns_live,tuple(deals)

def oracle_stage_selection_key(stage_index:int,win_turn):
    """Earlier win first; equal-turn results prefer the earlier mulligan stage."""
    return (win_turn if win_turn is not None else 99,stage_index)

def search_config_payload(config:OracleSearchConfig):
    return {
        "turn_horizon":config.max_turn,
        "action_cap":config.action_cap,
        "bottom_cap":config.bottom_cap,
        "min_keep":config.min_keep,
        "mulligan_stages":[
            {"label":label,"keep_size":7-bottom_n,"bottom_count":bottom_n}
            for label,bottom_n in oracle_mulligan_stages(config.min_keep)
        ],
        "beam":config.beam,
        "depth":config.depth,
    }

@lru_cache(maxsize=1)
def solver_source_provenance():
    solver_path=Path(__file__).resolve()
    out={
        "commit_hash":None,
        "git_dirty":None,
        "solver_sha256":hashlib.sha256(solver_path.read_bytes()).hexdigest(),
        "git_error":None,
    }
    try:
        head=subprocess.run(
            ["git","rev-parse","HEAD"],cwd=solver_path.parent,
            capture_output=True,text=True,timeout=2,check=False
        )
        status=subprocess.run(
            ["git","status","--porcelain","--untracked-files=normal"],cwd=solver_path.parent,
            capture_output=True,text=True,timeout=2,check=False
        )
        if head.returncode!=0:
            raise RuntimeError(head.stderr.strip() or "git rev-parse failed")
        if status.returncode!=0:
            raise RuntimeError(status.stderr.strip() or "git status failed")
        out["commit_hash"]=head.stdout.strip() or None
        out["git_dirty"]=bool(status.stdout.strip())
    except Exception as exc:
        out["git_error"]=str(exc)
    return out

def seed_provenance(base_seed:int,count:int=1,step:int=1):
    last=base_seed+(count-1)*step if count>0 else None
    return {
        "base":base_seed,"count":count,"step":step,
        "first":base_seed if count>0 else None,"last":last,
    }

def report_provenance(mode:str,config:OracleSearchConfig,seeds:dict,deck:List[str],
                      execution:Optional[dict]=None):
    hash_seed=os.environ.get("PYTHONHASHSEED") or None
    source=dict(solver_source_provenance())
    warnings=[]
    if hash_seed is None:
        warnings.append(
            "PYTHONHASHSEED is unset; unordered iteration can prevent exact cross-process reproduction."
        )
    elif hash_seed.lower()=="random":
        warnings.append(
            "PYTHONHASHSEED=random requests a new hash seed per process; exact reproduction is not guaranteed."
        )
    if source.get("git_dirty"):
        warnings.append(
            "Working tree is dirty; commit_hash alone does not identify the executing source."
        )
    if source.get("git_error"):
        warnings.append(f"Git provenance unavailable: {source['git_error']}")
    deck_bytes=json.dumps(list(deck),ensure_ascii=False,separators=(",",":")).encode("utf-8")
    return {
        "mode":mode,
        "source":source,
        "search":search_config_payload(config),
        "seeds":dict(seeds),
        "environment":{
            "python_hash_seed":hash_seed,
            "python_version":sys.version.split()[0],
        },
        "execution":dict(execution or {}),
        "deck":{
            "card_count":len(deck),
            "ordered_cards_sha256":hashlib.sha256(deck_bytes).hexdigest(),
        },
        "argv":list(sys.argv),
        "warnings":warnings,
    }

_HASH_SEED_WARNING_EMITTED=False

def warn_if_unset_python_hash_seed():
    global _HASH_SEED_WARNING_EMITTED
    hash_seed=os.environ.get("PYTHONHASHSEED")
    if not hash_seed and not _HASH_SEED_WARNING_EMITTED:
        print(
            "[REPRODUCIBILITY WARNING] PYTHONHASHSEED is unset; "
            "recorded results may not reproduce exact tie/order behavior.",
            flush=True
        )
        _HASH_SEED_WARNING_EMITTED=True
    elif hash_seed and hash_seed.lower()=="random" and not _HASH_SEED_WARNING_EMITTED:
        print(
            "[REPRODUCIBILITY WARNING] PYTHONHASHSEED=random; "
            "each process may use a different hash seed.",
            flush=True,
        )
        _HASH_SEED_WARNING_EMITTED=True



def profile_oracle_seed(seed:int, deck:List[str], max_turn:int=7, beam:int=300,
                        depth:int=60, bottom_cap:int=4, min_keep:int=4):
    """
    Profile the ACTUAL oracle candidate structure for a single seed.
    Prints before/after every independent hand search so a pathological
    mulligan candidate / London-bottom choice is immediately identifiable.
    """
    config=OracleSearchConfig(max_turn,beam,depth,ACTION_CAP,bottom_cap,min_keep)
    caverns_live,deals=oracle_mulligan_deals(seed,deck,min_keep)
    print("\n=== PROFILE ORACLE SEED ===",flush=True)
    print(
        f"seed={seed} turns={max_turn} beam={beam} depth={depth} "
        f"action_cap={ACTION_CAP} bottom_cap={bottom_cap} min_keep={min_keep} "
        f"PYTHONHASHSEED={os.environ.get('PYTHONHASHSEED','<unset>')}",
        flush=True
    )
    print(
        "provenance="+json.dumps(
            report_provenance(
                "profile-oracle",config,seed_provenance(seed),deck,
                {"worker_count":1,"parallelism":"sequential"},
            ),
            sort_keys=True,
        ),
        flush=True,
    )

    total_searches=0
    total_wall=time.time()
    candidate_results=[]

    for stage_idx,(label,bottom_n,d) in enumerate(deals):
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
                max_actions_per_turn=depth,caverns_live=caverns_live,
                candidate_tag=tag,rng_root_seed=seed
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
                        candidate_tag="candidate", rng_root_seed:int=0):
    """
    Exact search_hand initialization + depth-by-depth diagnostics.
    Used by --profile-oracle so a slow candidate never disappears into a silent call.
    """
    hand,lib=london_opening_zones(deck_order,keep_n,bottom)
    s=State(turn=1,library=lib,hand=tuple(hand),battlefield=(),rng_root_seed=rng_root_seed,trace=("--- Turn 1 ---",))

    if "Gemstone Caverns" in s.hand and caverns_live and len(s.hand)>1:
        choices=[c for c in s.hand if c!="Gemstone Caverns"]
        ex=min(choices,key=lambda c:card_priority(s,c))
        s=replace(s,hand=remove_one(remove_one(s.hand,"Gemstone Caverns"),ex),exile=s.exile+(ex,))
        s=add_perm(s,"Gemstone Caverns",mode="luck")
        s=add_trace(s,f"pregame Caverns exiles {ex}")

    s,drawn=draw_from_library(s,1)
    if drawn:
        s=append_trace_detail(s,f"normal draw for turn 1: {drawn[0]}")
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
                    nlands=sum(1 for p in st.battlefield if is_land_perm(p))
                    nnonlands=sum(1 for p in st.battlefield if not is_land_perm(p))
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
        states=end_turn_frontier(
            frontier,beam,resolve_remora_upkeep=(turn<max_turn)
        )
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
                live_progress:bool=False, progress_seconds:float=10.0,
                min_keep:int=4,bottom_cap=None):
    """
    Oracle mulligan search with exact earliest-win branch-and-bound.

    Once an EARLIER mulligan stage has established a win on turn B, any later
    stage only needs to be searched through B-1: a tie on turn B would lose the
    oracle tie-break to the earlier stage anyway.

    Within the SAME stage, if one bottom choice finds turn B, later bottom
    choices are still searched through B (not B-1) so the existing same-stage
    trace tie-break remains reproducible.
    """
    if bottom_cap is None:
        bottom_cap=BOTTOM_CAP

    # Chain macro results are useful within one concrete Oracle game, but the
    # hidden library is different for every root seed. Carrying thousands of
    # cached result states across games provides little reuse and can create
    # severe batch-memory/tail-latency growth. Keep the cache game-local.
    _CHAIN_RESULT_CACHE.clear()

    caverns_live,deals=oracle_mulligan_deals(seed,deck,min_keep)
    effective_config=OracleSearchConfig(
        max_turn,beam,depth,ACTION_CAP,bottom_cap,min_keep
    )
    candidates=[]
    global_best_turn=None
    total_oracle_states=0
    oracle_graph=new_graph_stats()
    oracle_t0=time.time()

    for stage,(stage_label,bottom_n,d) in enumerate(deals):
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

        bottoms=bottom_candidates(seven,bottom_n,cap=bottom_cap)
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
                graph_stats=hand_graph,
                rng_root_seed=seed
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
            "graph":finalize_graph_stats(oracle_graph),"trace":(),
            "_oracle_search_config":search_config_payload(effective_config),
            "_oracle_mulligan_stage_count":len(deals),
        }

    candidates.sort(key=lambda x:oracle_stage_selection_key(x[0],x[1][1][0]))
    stage,best,seven=candidates[0]
    turn,fam,trace,states,urza_turn,interaction_seen,final_hand,max_depth=best[1]
    kept=list(seven)
    for c in best[2]:
        kept.remove(c)

    return {
        "seed":seed,"win_turn":turn,"family":fam,"mulligan_stage":stage,
        "keep_size":7-len(best[2]),"bottom":best[2],"opening7":seven,
        "kept_hand":kept,"urza_cast_turn":urza_turn,
        "interaction_count":len(interaction_seen),"interaction_seen":list(interaction_seen),
        "final_hand":list(final_hand),"max_depth_reached":max_depth,
        "states":states,"oracle_states_total":total_oracle_states,
        "graph":finalize_graph_stats(oracle_graph),"trace":trace,
        "_oracle_search_config":search_config_payload(effective_config),
        "_oracle_mulligan_stage_count":len(deals),
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


def apply_worker_search_config(config:OracleSearchConfig):
    """Install explicitly transported cap values in a spawned interpreter."""
    global ACTION_CAP,BOTTOM_CAP
    ACTION_CAP=config.action_cap
    BOTTOM_CAP=config.bottom_cap


def worker(job:OracleWorkerJob):
    """Run one Oracle game from a complete, spawn-safe search definition."""
    seed=job.seed
    verbose_worker=job.verbose_worker
    apply_worker_search_config(job.config)

    pid=os.getpid()
    t0=time.time()
    if verbose_worker:
        print(f"[worker {pid}] START seed={seed}", flush=True)
    try:
        result=oracle_game(
            seed,job.deck,
            max_turn=job.config.max_turn,
            beam=job.config.beam,
            depth=job.config.depth,
            min_keep=job.config.min_keep,
            bottom_cap=job.config.bottom_cap,
        )
        result["_elapsed_worker_s"]=time.time()-t0
        result["_error"]=""
        result["_worker_pid"]=pid
        result["_worker_search_config"]=search_config_payload(job.config)
        result["_worker_effective_caps"]={
            "action_cap":ACTION_CAP,"bottom_cap":BOTTOM_CAP,
        }
        result["_worker_python_hash_seed"]=os.environ.get("PYTHONHASHSEED")
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
            "_worker_pid":pid,
            "_worker_search_config":search_config_payload(job.config),
            "_worker_effective_caps":{
                "action_cap":ACTION_CAP,"bottom_cap":BOTTOM_CAP,
            },
            "_worker_python_hash_seed":os.environ.get("PYTHONHASHSEED"),
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


def write_partial_checkpoint(out:Path, results, args, deck:List[str], reason:str):
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
            "provenance":report_provenance(
                "partial-normal-run",
                OracleSearchConfig(
                    args.turns,args.beam,args.depth,args.action_cap,
                    args.bottom_cap,args.min_keep,
                ),
                seed_provenance(args.seed,args.runs),
                deck,
                {
                    "worker_count":args.workers,
                    "parallelism":"sequential" if args.workers==1 else "multiprocessing",
                },
            ),
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

    # Chrome Dome + PA-on-Dome + Gadgeteer makes the Dome ability cost {2}.
    # Copying an untapped Mana Vault pays the first activation and every fresh
    # copy taps for {3}, yielding +1 per iteration. This is genuine infinite
    # colorless before Urza, and a terminal family once Urza is online.
    chrome_pre=State(
        turn=3,library=(),hand=(),
        battlefield=(
            Perm("Chrome Dome",sick=False),
            Perm("Forensic Gadgeteer",sick=False),
            Perm("Power Artifact"),
            Perm("Mana Vault"),
        ),
        pa_target="Chrome Dome",
        blue=2,
        commander_in_command_zone=True,
    )
    assert chrome_dome_positive_copy_target(chrome_pre)=="Mana Vault"
    assert infinite_colorless_online(chrome_pre)
    cast=cast_urza_from_command_zone_actions(chrome_pre)
    assert cast and cast[0].urza
    chrome_live=replace(
        chrome_pre,
        urza=True,commander_in_command_zone=False,blue=0,
        battlefield=chrome_pre.battlefield+(Perm(COMMANDER,sick=False),),
    )
    won=check_win(chrome_live)
    assert won.won
    assert won.win_family=="Chrome Dome + PA + Gadgeteer + Mana Vault"

    wrong_pa=replace(chrome_pre,pa_target="Mana Vault")
    assert not chrome_dome_positive_copy_target(wrong_pa)
    no_gadget=replace(
        chrome_pre,
        battlefield=tuple(
            p for p in chrome_pre.battlefield if p.name!="Forensic Gadgeteer"
        ),
    )
    assert not chrome_dome_positive_copy_target(no_gadget)
    tapped_vault=replace(
        chrome_pre,blue=0,
        battlefield=tuple(
            replace(p,tapped=True) if p.name=="Mana Vault" else p
            for p in chrome_pre.battlefield
        ),
    )
    assert not chrome_dome_positive_copy_target(tapped_vault)
    print("Chrome Dome + PA + Gadgeteer + Vault    PASS | +1 mana per copy",flush=True)

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
                         depth:int,slow_seconds:float,progress_seconds:float=10.0,
                         min_keep:int=4,bottom_cap=None):
    """
    Sequential deterministic Oracle-Mode rules-engine audit.

    This intentionally uses ONE process so runtime differences are attributable
    to game-tree behavior rather than multiprocessing/RAM contention.
    """
    if bottom_cap is None:
        bottom_cap=BOTTOM_CAP
    config=OracleSearchConfig(max_turn,beam,depth,ACTION_CAP,bottom_cap,min_keep)
    print("\n=== ORACLE SMOKE-SEED BATCH ===",flush=True)
    print(
        f"count={count} base_seed={base_seed} step={step} turns={max_turn} "
        f"beam={beam} action_cap={ACTION_CAP} bottom_cap={bottom_cap} "
        f"min_keep={min_keep} depth={depth}",
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
            live_progress=True,progress_seconds=progress_seconds,
            min_keep=min_keep,bottom_cap=bottom_cap,
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
        "provenance":report_provenance(
            "smoke-seeds",config,seed_provenance(base_seed,count,step),deck,
            {"worker_count":1,"parallelism":"sequential"},
        ),
        "config":{
            "base_seed":base_seed,"count":count,"step":step,"turns":max_turn,
            "beam":beam,"action_cap":ACTION_CAP,"bottom_cap":bottom_cap,
            "min_keep":min_keep,"depth":depth,
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
            Perm("Battered Golem",sick=False,tapped=False,knack_granted=True,knack_source="Banishing Knack"),
        ),
        urza=True,commander_in_command_zone=False,
        graveyard=("Banishing Knack",)
    )
    w=check_win(s)
    assert w.won and w.win_family=="Knack/Helix + Cam"
    print("Cam + active current-turn Knack target wins: PASS",flush=True)

    # Old Knack in graveyard from a previous turn is NOT enough.
    stale=replace(s,battlefield=tuple(
        replace(p,knack_granted=False,knack_source="") for p in s.battlefield
    ))
    assert not check_win(stale).won
    print("stale graveyard Knack does not false-positive: PASS",flush=True)

    # Sick/tapped target is not terminal until it can actually activate.
    sick=replace(s,battlefield=(
        Perm(COMMANDER,sick=False),
        Perm("Sewer-veillance Cam"),
        Perm("Battered Golem",sick=True,tapped=False,knack_granted=True),
    ))
    assert not check_win(sick).won
    tapped=replace(s,battlefield=(
        Perm(COMMANDER,sick=False),
        Perm("Sewer-veillance Cam"),
        Perm("Battered Golem",sick=False,tapped=True,knack_granted=True),
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
            Perm("Battered Golem",sick=False,tapped=True,knack_granted=True),
        ),
        blue=4,urza=True,commander_in_command_zone=False
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

    # Accepted state-space prune: temporary Chrome Dome copies are not retained
    # as PA enchantment or Reality Chip reconfigure targets. In this singleton
    # deck those attachment lines have no modeled strategic role, and pruning
    # them keeps the name-based attachment fields unambiguous.
    chip_copy=State(
        turn=3,library=(),hand=(),blue=3,
        battlefield=(
            Perm("The Reality Chip"),
            Perm("Battered Golem",mode="chrome_copy",sick=False),
        ),
    )
    assert not any(
        x.trace and x.trace[-1].startswith("reconfigure Reality Chip")
        for x in special_actions(chip_copy)
    )
    pa_copy=State(
        turn=3,library=(),hand=("Power Artifact",),blue=2,
        battlefield=(Perm("Basalt Monolith",mode="chrome_copy"),),
    )
    assert not power_artifact_actions(pa_copy)
    print("PA/Chip temporary-copy attachment prune: PASS",flush=True)

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
    global ACTION_CAP,_TUTOR_CAP_AUDIT_ENABLED,_TUTOR_CAP_AUDIT
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
    transmute_actions=acts
    print("artifact tutor execution: PASS",flush=True)

    # Every target-selecting production search generator must have an auditable
    # source, target, and destination. These are generated actions, not
    # hand-written trace fixtures, so label drift cannot silently break parsing.
    generated_search_actions=[]
    generated_search_actions += simple_tutor_actions(State(
        turn=4,
        library=(
            "Sewer-veillance Cam","Power Artifact","Whir of Invention",
            "Banishing Knack","Transmute Artifact","Island"
        ),
        hand=("Dizzy Spell","Muddle the Mixture","Merchant Scroll","Mystical Tutor"),
        battlefield=(Perm("Spellseeker",mode="fresh"),),blue=10
    ))
    generated_search_actions += artifact_tutor_actions(State(
        turn=4,library=("Sol Ring","Island"),
        hand=("Reshape","Whir of Invention"),
        battlefield=(Perm("Tormod's Crypt"),),blue=5,colorless=1
    ))
    generated_search_actions += tezzeret_actions(State(
        turn=4,library=("Sensei's Divining Top","Island"),hand=(),
        battlefield=(Perm("Tezzeret, Cruel Captain",counters=3),)
    ))
    generated_search_actions += saga_actions(State(
        turn=4,library=("Sol Ring","Island"),hand=(),
        battlefield=(Perm("Urza's Saga",counters=3,mode="saga3"),),
        saga3_pending=True,
    ))
    generated_search_actions += repurposing_bay_actions(State(
        turn=4,library=("Battered Golem","Island"),hand=(),
        battlefield=(Perm("Repurposing Bay"),Perm("Chrome Dome")),colorless=2
    ))
    generated_search_actions += scour_actions(State(
        turn=4,library=("Sol Ring","Island"),hand=("Scour for Scrap",),
        battlefield=(),graveyard=("Welding Jar",),blue=1,colorless=3
    ))
    fixed_fetch_actions=fetch_actions(State(
        turn=4,library=("Island","Sol Ring"),hand=(),
        battlefield=(Perm("Flooded Strand"),)
    ))
    parsed_searches={_tutor_action_from_trace(a) for a in generated_search_actions}
    parsed_sources={source for source,_target,_destination in parsed_searches if source}
    assert {
        "Dizzy Spell","Muddle the Mixture","Merchant Scroll","Mystical Tutor",
        "Spellseeker","Reshape","Whir of Invention","Tezzeret, Cruel Captain",
        "Urza's Saga","Repurposing Bay","Scour for Scrap",
    } <= parsed_sources
    assert ("Mystical Tutor","Whir of Invention","library top") in parsed_searches
    assert ("Tezzeret, Cruel Captain","Sensei's Divining Top","hand") in parsed_searches
    assert ("Urza's Saga","Sol Ring","battlefield") in parsed_searches
    assert ("Repurposing Bay","Battered Golem","battlefield") in parsed_searches
    assert ("Scour for Scrap","Sol Ring","hand") in parsed_searches
    assert any("Scour tutors Sol Ring + returns Welding Jar"==a.trace[-1]
               and _tutor_action_from_trace(a)==("Scour for Scrap","Sol Ring","hand")
               for a in generated_search_actions)
    assert fixed_fetch_actions
    assert all(_tutor_action_from_trace(a)==(None,None,None) for a in fixed_fetch_actions)
    parsed_transmute={_tutor_action_from_trace(a) for a in transmute_actions}
    assert any(src=="Transmute Artifact" and destination=="battlefield"
               for src,_target,destination in parsed_transmute)
    assert any(src=="Transmute Artifact" and destination=="graveyard"
               for src,_target,destination in parsed_transmute)
    print("tutor-cap parser covers every target-selecting search source/destination: PASS",flush=True)

    # A real tutor-heavy legal-actions state used to spend the cap on redundant
    # Transmute payment/sacrifice branches and completely lose Top, Cam, and
    # Basalt. Every distinct route fits under 60 here, so each must retain its
    # best-scoring representative while global score fills the other slots.
    strategic_targets=(
        "Sensei's Divining Top","Sewer-veillance Cam","The Reality Chip",
        "Uthros Research Craft","Basalt Monolith","The One Ring",
    )
    excluded_artifacts=set(strategic_targets)|{
        "Seat of the Synod","Repurposing Bay","Grinding Station","Grafdigger's Cage",
    }
    diversity_state=State(
        turn=7,
        library=strategic_targets+("Island",),
        hand=("Transmute Artifact",),
        battlefield=tuple(Perm(name) for name in sorted(ARTIFACTS-excluded_artifacts)[:18]),
        blue=2,colorless=4,
    )
    old_cap=ACTION_CAP
    try:
        ACTION_CAP=1000
        raw_diversity_actions=legal_actions(diversity_state)
        legacy_kept=heapq.nlargest(60,raw_diversity_actions,key=score)
        ACTION_CAP=60
        diverse_kept=legal_actions(diversity_state)
    finally:
        ACTION_CAP=old_cap

    raw_by_route=collections.defaultdict(list)
    kept_by_route=collections.defaultdict(list)
    for action in raw_diversity_actions:
        route=_tutor_action_from_trace(action)
        if route[0]:
            raw_by_route[route].append(action)
    for action in diverse_kept:
        route=_tutor_action_from_trace(action)
        if route[0]:
            kept_by_route[route].append(action)
    legacy_targets={
        target for source,target,_destination in
        (_tutor_action_from_trace(action) for action in legacy_kept) if source
    }
    kept_targets={target for _source,target,_destination in kept_by_route}
    assert len(raw_diversity_actions)>60
    assert len(diverse_kept)==60
    assert {
        "Sensei's Divining Top","Sewer-veillance Cam","Basalt Monolith"
    } <= set(strategic_targets)-legacy_targets
    assert set(strategic_targets)<=kept_targets
    assert set(raw_by_route)<=set(kept_by_route)
    for route,candidates in raw_by_route.items():
        assert max(map(score,kept_by_route[route]))==max(map(score,candidates))

    # A strict cap cannot retain 61 distinct routes. Verify the deterministic
    # fallback remains strict and protects known strategic targets even when
    # higher-scoring synthetic routes compete for every slot.
    overflow_actions=[]
    for target in strategic_targets:
        overflow_actions.append(State(
            turn=7,library=(),hand=(),battlefield=(),
            trace=(f"Scour tutors {target}",)
        ))
    for n in range(64):
        overflow_actions.append(State(
            turn=7,library=(),hand=(),battlefield=(),colorless=100+n,
            trace=(f"Scour tutors synthetic-{n:02d}",)
        ))
    old_cap=ACTION_CAP
    try:
        ACTION_CAP=60
        overflow_kept=_select_actions_with_tutor_diversity(overflow_actions)
    finally:
        ACTION_CAP=old_cap
    overflow_routes={_tutor_action_from_trace(action) for action in overflow_kept}
    assert len(overflow_kept)==60
    assert len(overflow_routes)==60
    assert set(strategic_targets)<={target for _source,target,_destination in overflow_routes}
    print("target-aware ACTION_CAP route/strategic-target retention: PASS",flush=True)

    # Enabling the audit must leave production ACTION_CAP selection byte-for-byte
    # equivalent while recording route and target diversity for the cap-hit state.
    audit_state=State(
        turn=4,
        library=("Sewer-veillance Cam","Sol Ring","Basalt Monolith","Grinding Station"),
        hand=("Transmute Artifact",),
        battlefield=(Perm("Mox Opal"),Perm("Welding Jar")),
        blue=2
    )
    old_cap=ACTION_CAP
    old_enabled=_TUTOR_CAP_AUDIT_ENABLED
    old_audit=_TUTOR_CAP_AUDIT
    try:
        _TUTOR_CAP_AUDIT_ENABLED=False
        _TUTOR_CAP_AUDIT=None
        ACTION_CAP=1000
        raw_actions=legal_actions(audit_state)
        ACTION_CAP=3
        baseline_kept=legal_actions(audit_state)

        _TUTOR_CAP_AUDIT=new_tutor_cap_audit_stats()
        _TUTOR_CAP_AUDIT["_current_seed"]=20260826
        _TUTOR_CAP_AUDIT_ENABLED=True
        audited_kept=legal_actions(audit_state)

        assert audited_kept==baseline_kept
        raw_tutors=[p for p in (_tutor_action_from_trace(a) for a in raw_actions) if p[0]]
        kept_tutors=[p for p in (_tutor_action_from_trace(a) for a in audited_kept) if p[0]]
        raw_targets={target for _,target,_ in raw_tutors}
        kept_targets={target for _,target,_ in kept_tutors}
        lost_targets=raw_targets-kept_targets
        assert _TUTOR_CAP_AUDIT["tutor_truncated_states"]==1
        assert _TUTOR_CAP_AUDIT["raw_tutor_actions"]==len(raw_tutors)
        assert _TUTOR_CAP_AUDIT["kept_tutor_actions"]==len(kept_tutors)
        assert len(_TUTOR_CAP_AUDIT["cap_hit_states"])==1
        row=_TUTOR_CAP_AUDIT["cap_hit_states"][0]
        assert set(row["unique_targets_before_cap"])==raw_targets
        assert set(row["unique_targets_after_cap"])==kept_targets
        assert set(row["lost_targets"])==lost_targets
        assert set(row["lost_engine_targets"])==lost_targets&KNOWN_ENGINE_TARGETS
        retention=row["source_retention"]["Transmute Artifact"]
        assert retention["raw_action_count"]==len(raw_tutors)
        assert retention["kept_action_count"]==len(kept_tutors)
        assert retention["unique_target_count_before_cap"]==len(raw_targets)
        assert retention["unique_target_count_after_cap"]==len(kept_targets)
        assert set(retention["targets_completely_lost"])==lost_targets
        aggregate_retention=tutor_source_retention_summary(_TUTOR_CAP_AUDIT)["Transmute Artifact"]
        assert aggregate_retention["raw_action_count"]==len(raw_tutors)
        assert aggregate_retention["kept_action_count"]==len(kept_tutors)

        # Target identity can survive while its useful destination route does
        # not (notably Transmute paid-to-battlefield vs decline-to-graveyard).
        route_retention=_tutor_source_retention(
            [
                ("Transmute Artifact","Sewer-veillance Cam","battlefield"),
                ("Transmute Artifact","Sewer-veillance Cam","graveyard"),
            ],
            [("Transmute Artifact","Sewer-veillance Cam","graveyard")]
        )["Transmute Artifact"]
        assert route_retention["targets_completely_lost"]==[]
        assert route_retention["known_engine_combo_target_destination_routes_completely_lost"]==[
            {"target":"Sewer-veillance Cam","destination":"battlefield"}
        ]

        # Detailed state rows are not truncated with the display shortlist.
        all_rows_audit=new_tutor_cap_audit_stats()
        _TUTOR_CAP_AUDIT=all_rows_audit
        for occurrence in range(51):
            all_rows_audit["_current_seed"]=20260826+occurrence
            _record_tutor_cap_state(raw_actions,baseline_kept,audit_state)
        assert len(all_rows_audit["cap_hit_states"])==51
        assert len(all_rows_audit["worst_states"])==50
    finally:
        ACTION_CAP=old_cap
        _TUTOR_CAP_AUDIT_ENABLED=old_enabled
        _TUTOR_CAP_AUDIT=old_audit
    assert KNOWN_SETUP_ENGINE_TARGETS==frozenset({
        "The One Ring","Mystic Remora","Rhystic Study","Faerie Mastermind"
    })
    assert KNOWN_ENGINE_COMBO_TARGETS==KNOWN_ENGINE_TARGETS|KNOWN_SETUP_ENGINE_TARGETS
    print("tutor-cap audit records every hit and preserves retained actions: PASS",flush=True)

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

    # Attachment metadata must agree with the actual reconfigured Chip object.
    # A stale boolean flag is not sufficient to claim top-cast access.
    stale_chip=State(
        turn=4,library=("Island",),hand=(),
        battlefield=(
            Perm(COMMANDER,sick=False),
            Perm("The Reality Chip"),
            Perm("Grinding Station"),
            Perm("Sensei's Divining Top"),
        ),
        urza=True,commander_in_command_zone=False,
        chip_attached=True,chip_target=COMMANDER
    )
    assert not check_win(stale_chip).won
    print("Top + Chip requires active reconfigure     PASS | stale flag rejected",flush=True)

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

    # 13a. Once Knack/Helix is live on Golem, a zero-mana replay artifact is
    # terminal: bounce/recast untaps Golem and Urza converts each cycle to +U.
    s=State(
        turn=5,library=("Island",),hand=(),
        battlefield=(
            Perm(COMMANDER,sick=False),
            Perm("Battered Golem",sick=False,knack_granted=True),
            Perm("Lotus Petal"),
        ),
        urza=True,commander_in_command_zone=False
    )
    w=check_win(s)
    assert w.won and w.win_family=="Knack/Helix + Battered Golem"
    print("Knack + Golem replay loop              PASS | terminal win recognized",flush=True)

    # 13b. Valley Floodcaller supplies the same recurrence from the cast trigger.
    s=State(
        turn=5,library=("Island",),hand=(),
        battlefield=(
            Perm(COMMANDER,sick=False),
            Perm("Valley Floodcaller",sick=False,knack_granted=True),
            Perm("Everflowing Chalice"),
        ),
        urza=True,commander_in_command_zone=False
    )
    w=check_win(s)
    assert w.won and w.win_family=="Knack/Helix + Valley Floodcaller"
    print("Knack + Floodcaller replay loop         PASS | terminal win recognized",flush=True)

    # Mox Diamond alone must not create a false infinite replay claim.
    s=State(
        turn=5,library=("Island",),hand=(),
        battlefield=(
            Perm(COMMANDER,sick=False),
            Perm("Battered Golem",sick=False,knack_granted=True),
            Perm("Mox Diamond"),
        ),
        urza=True,commander_in_command_zone=False
    )
    assert not check_win(s).won
    print("Knack replay excludes Mox Diamond       PASS | no false infinite",flush=True)

    # Replay mana classes are state-dependent. Without Urza, only native mana
    # counts: Sol/Vault/Grim are positive; zero-drops and Basalt are neutral;
    # Mox Opal is positive only with metalcraft. The three "producers" create
    # no mana rebate at all until Urza is actually on the battlefield.
    dummy=Perm("Valley Floodcaller",sick=False,knack_granted=True,instance_tag=99)
    native=State(
        turn=4,library=(),
        hand=("Sol Ring","Mana Vault","Grim Monolith","Welding Jar","Basalt Monolith"),
        battlefield=(),
        urza=False,
    )
    assert replay_mana_margin(native,dummy,"Sol Ring")>0
    assert replay_mana_margin(native,dummy,"Mana Vault")>0
    assert replay_mana_margin(native,dummy,"Grim Monolith")>0
    assert replay_mana_margin(native,dummy,"Welding Jar")==0
    assert replay_mana_margin(native,dummy,"Basalt Monolith")==0

    opal_no_metal=State(
        turn=4,library=(),hand=("Mox Opal",),battlefield=(),urza=False,
    )
    assert replay_mana_margin(opal_no_metal,dummy,"Mox Opal")==0
    opal_metal=replace(
        opal_no_metal,
        battlefield=(Perm("Welding Jar"),Perm("Tormod's Crypt")),
    )
    assert replay_mana_margin(opal_metal,dummy,"Mox Opal")>0

    producer_no_urza=State(
        turn=4,library=(),hand=("Aether Spellbomb",),
        battlefield=(
            Perm("Grinding Station"),
            Perm("Battered Golem",sick=False),
            Perm("Forensic Gadgeteer",sick=False),
        ),
        urza=False,
    )
    assert _steady_replay_producer_bonus(
        producer_no_urza,dummy,"Aether Spellbomb"
    )==0
    print("Replay native/Urza producer boundary    PASS | producers require Urza",flush=True)

    # A positive steady-state artifact in hand still needs bootstrap mana for
    # the first cast. Once the mana is floated, the same visible state becomes
    # a deterministic loop.
    bootstrap=State(
        turn=5,library=(),hand=("Grim Monolith",),
        battlefield=(
            Perm(COMMANDER,sick=False),
            Perm("Battered Golem",sick=False,knack_granted=True),
        ),
        urza=True,commander_in_command_zone=False,
        blue=0,colorless=0,
    )
    assert not check_win(bootstrap).won
    bootstrap=replace(bootstrap,colorless=2)
    w=check_win(bootstrap)
    assert w.won and w.win_family=="Knack/Helix + Battered Golem"
    print("Knack replay bootstrap affordability    PASS | first cast must be payable",flush=True)

    # A neutral artifact becomes positive only with a separate Urza producer.
    neutral=State(
        turn=5,library=(),hand=("Aether Spellbomb",),
        battlefield=(
            Perm(COMMANDER,sick=False),
            Perm("Battered Golem",sick=False,knack_granted=True),
        ),
        urza=True,commander_in_command_zone=False,
        blue=1,
    )
    assert replay_mana_margin(
        neutral,neutral.battlefield[1],"Aether Spellbomb"
    )==0
    assert not check_win(neutral).won
    promoted=replace(
        neutral,
        battlefield=neutral.battlefield+(Perm("Grinding Station"),),
    )
    assert replay_mana_margin(
        promoted,promoted.battlefield[1],"Aether Spellbomb"
    )>0
    w=check_win(promoted)
    assert w.won and w.win_family=="Knack/Helix + Battered Golem"
    print("Neutral replay + Urza producer          PASS | dynamic class promotion",flush=True)

    # 14. Station ETB conversion. The fast Oracle state takes the post-trigger
    # Urza tap immediately and records it as refundable for native-use branches.
    s=State(
        turn=4,library=(),hand=("Tormod's Crypt",),
        battlefield=(Perm(COMMANDER,sick=False),Perm("Grinding Station",tapped=True)),
        blue=0,colorless=0,urza=True,commander_in_command_zone=False
    )
    acts=legal_actions(s)
    casts=[x for x in acts if has(x,"Tormod's Crypt")]
    assert casts
    assert any(x.blue>s.blue and deferred_producer_blue(x)>0 for x in casts), "Station ETB mana/refund credit missing"
    print("Grinding Station artifact-ETB mana     PASS | fast mana + native refund reachable",flush=True)

    # 15. Golem ETB conversion.
    s=State(
        turn=4,library=(),hand=("Tormod's Crypt",),
        battlefield=(Perm(COMMANDER,sick=False),Perm("Battered Golem",tapped=True,sick=False)),
        blue=0,colorless=0,urza=True,commander_in_command_zone=False
    )
    acts=legal_actions(s)
    casts=[x for x in acts if has(x,"Tormod's Crypt")]
    assert casts
    assert any(x.blue>s.blue and deferred_producer_blue(x)>0 for x in casts), "Golem ETB mana/refund credit missing"
    print("Battered Golem artifact-ETB mana       PASS | fast mana + native refund reachable",flush=True)

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
                     progress_seconds:float=10.0,min_keep:int=4,bottom_cap=None):
    if bottom_cap is None:
        bottom_cap=BOTTOM_CAP
    config=OracleSearchConfig(max_turn,beam,depth,ACTION_CAP,bottom_cap,min_keep)
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
            live_progress=True,progress_seconds=progress_seconds,
            min_keep=min_keep,bottom_cap=bottom_cap,
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
        "provenance":report_provenance(
            "family-smoke",config,seed_provenance(base_seed,count),deck,
            {"worker_count":1,"parallelism":"sequential"},
        ),
        "base_seed":base_seed,
        "count":count,
        "families":dict(fam),
        "cam_hits":cam_hits,
        "rows":rows,
    }
    Path("family_smoke_report.json").write_text(json.dumps(payload,indent=2),encoding="utf-8")
    print("Wrote family_smoke_report.json",flush=True)



def run_cap_audit(deck,base_seed:int,count:int,max_turn:int,beam:int,depth:int,
                  progress_seconds:float=10.0,min_keep:int=4,bottom_cap=None):
    global _CAP_AUDIT
    if bottom_cap is None:
        bottom_cap=BOTTOM_CAP
    config=OracleSearchConfig(max_turn,beam,depth,ACTION_CAP,bottom_cap,min_keep)
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
            r=oracle_game(
                seed,deck,max_turn,beam,depth,
                live_progress=True,progress_seconds=progress_seconds,
                min_keep=min_keep,bottom_cap=bottom_cap,
            )
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
        summary["provenance"]=report_provenance(
            "cap-audit",config,seed_provenance(base_seed,count),deck,
            {"worker_count":1,"parallelism":"sequential"},
        )
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
                        progress_seconds:float=10.0,min_keep:int=4,bottom_cap=None):
    global _TUTOR_CAP_AUDIT_ENABLED,_TUTOR_CAP_AUDIT
    if bottom_cap is None:
        bottom_cap=BOTTOM_CAP
    config=OracleSearchConfig(max_turn,beam,depth,ACTION_CAP,bottom_cap,min_keep)
    previous_enabled=_TUTOR_CAP_AUDIT_ENABLED
    previous_audit=_TUTOR_CAP_AUDIT
    a=new_tutor_cap_audit_stats()
    _TUTOR_CAP_AUDIT_ENABLED=True
    _TUTOR_CAP_AUDIT=a
    rows=[]
    t0=time.time()
    print("\n=== TUTOR CAP DIVERSITY AUDIT ===",flush=True)
    print(
        f"ACTION_CAP={ACTION_CAP} seeds={count} base={base_seed} "
        f"PYTHONHASHSEED={os.environ.get('PYTHONHASHSEED','<unset>')}",
        flush=True
    )
    try:
        for i in range(count):
            seed=base_seed+i
            _TUTOR_CAP_AUDIT["_current_seed"]=seed
            b_states=_TUTOR_CAP_AUDIT["tutor_truncated_states"]
            b_raw=_TUTOR_CAP_AUDIT["raw_tutor_actions"]
            b_kept=_TUTOR_CAP_AUDIT["kept_tutor_actions"]
            b_targets_raw=_TUTOR_CAP_AUDIT["unique_targets_raw_total"]
            b_targets_kept=_TUTOR_CAP_AUDIT["unique_targets_kept_total"]
            b_lost=_TUTOR_CAP_AUDIT["lost_target_events"]
            b_eng=_TUTOR_CAP_AUDIT["lost_engine_target_events"]
            b_known=_TUTOR_CAP_AUDIT["lost_known_engine_combo_target_events"]
            b_engine_routes=_TUTOR_CAP_AUDIT["lost_engine_target_destination_route_events"]
            b_route_overflow=_TUTOR_CAP_AUDIT["route_representative_overflow_states"]
            print(f"\n[TUTOR CAP {i+1}/{count}] seed={seed}",flush=True)
            r=oracle_game(
                seed,deck,max_turn,beam,depth,
                live_progress=True,progress_seconds=progress_seconds,
                min_keep=min_keep,bottom_cap=bottom_cap,
            )
            graph=r.get("graph",{})
            row={
                "seed":seed,
                "win_turn":r.get("win_turn"),
                "family":r.get("family",""),
                "oracle_nodes":graph.get("nodes_expanded",0),
                "oracle_edges_post_cap":graph.get("edges_generated",0),
                "tutor_truncated_states_delta":_TUTOR_CAP_AUDIT["tutor_truncated_states"]-b_states,
                "raw_tutor_actions_delta":_TUTOR_CAP_AUDIT["raw_tutor_actions"]-b_raw,
                "kept_tutor_actions_delta":_TUTOR_CAP_AUDIT["kept_tutor_actions"]-b_kept,
                "unique_targets_before_cap_delta":_TUTOR_CAP_AUDIT["unique_targets_raw_total"]-b_targets_raw,
                "unique_targets_after_cap_delta":_TUTOR_CAP_AUDIT["unique_targets_kept_total"]-b_targets_kept,
                "lost_target_events_delta":_TUTOR_CAP_AUDIT["lost_target_events"]-b_lost,
                "lost_engine_target_events_delta":_TUTOR_CAP_AUDIT["lost_engine_target_events"]-b_eng,
                "lost_known_engine_combo_target_events_delta":_TUTOR_CAP_AUDIT["lost_known_engine_combo_target_events"]-b_known,
                "lost_engine_target_destination_route_events_delta":_TUTOR_CAP_AUDIT["lost_engine_target_destination_route_events"]-b_engine_routes,
                "route_representative_overflow_states_delta":_TUTOR_CAP_AUDIT["route_representative_overflow_states"]-b_route_overflow,
            }
            rows.append(row)
            print(
                f"[TUTOR CAP] seed={seed} win={row['win_turn'] or '-'} family={row['family'] or '-'} "
                f"tutor_cap_states={row['tutor_truncated_states_delta']} "
                f"lost_targets={row['lost_target_events_delta']} "
                f"lost_engine_targets={row['lost_known_engine_combo_target_events_delta']} "
                f"lost_engine_routes={row['lost_engine_target_destination_route_events_delta']}",
                flush=True
            )
    finally:
        _TUTOR_CAP_AUDIT_ENABLED=previous_enabled
        _TUTOR_CAP_AUDIT=previous_audit

    print("\n=== TUTOR CAP AUDIT SUMMARY ===",flush=True)
    print(f"truncated states with tutor branches: {a['tutor_truncated_states']:,}",flush=True)
    print(f"raw tutor actions in those states: {a['raw_tutor_actions']:,}",flush=True)
    print(f"kept tutor actions in those states: {a['kept_tutor_actions']:,}",flush=True)
    print(f"unique tutor targets before cap (state-summed): {a['unique_targets_raw_total']:,}",flush=True)
    print(f"unique tutor targets after cap (state-summed): {a['unique_targets_kept_total']:,}",flush=True)
    print(f"lost target events: {a['lost_target_events']:,}",flush=True)
    print(f"lost known engine/combo target events: {a['lost_known_engine_combo_target_events']:,}",flush=True)
    print(f"lost critical combo/access target events: {a['lost_engine_target_events']:,}",flush=True)
    print(f"lost known engine/combo target-destination routes: {a['lost_engine_target_destination_route_events']:,}",flush=True)
    print(
        f"strict-cap tutor-route overflow states: {a['route_representative_overflow_states']:,} "
        f"(max routes={a['max_unique_tutor_routes_before_cap']:,}, "
        f"excess reps={a['route_representative_overflow_excess_total']:,})",
        flush=True
    )
    print(
        f"target-aware reserve overflow states: {a['target_reserve_overflow_states']:,} "
        f"(max reserve={a['max_target_aware_reserve_size']:,})",
        flush=True
    )
    print(f"lost targets by frequency: {dict(a['lost_targets'].most_common())}",flush=True)
    print(f"lost known engine/combo targets by frequency: {dict(a['lost_known_engine_combo_targets'].most_common())}",flush=True)
    print(f"lost direct combo targets by frequency: {dict(a['lost_direct_combo_targets'].most_common())}",flush=True)
    print(f"lost validated access targets by frequency: {dict(a['lost_engine_access_targets'].most_common())}",flush=True)
    print(f"lost setup/CA engines by frequency: {dict(a['lost_setup_engine_targets'].most_common())}",flush=True)
    print("\nTutor source retention:",flush=True)
    source_retention=tutor_source_retention_summary(a)
    action_retention=(a["kept_tutor_actions"]/a["raw_tutor_actions"] if a["raw_tutor_actions"] else 1.0)
    target_retention=(a["unique_targets_kept_total"]/a["unique_targets_raw_total"] if a["unique_targets_raw_total"] else 1.0)
    for src,retention in source_retention.items():
        print(
            f"  {src:26s} actions={retention['kept_action_count']:7,d}/"
            f"{retention['raw_action_count']:7,d} ({100*retention['action_retention_rate']:6.2f}%) "
            f"targets={retention['state_summed_unique_target_count_after_cap']:6,d}/"
            f"{retention['state_summed_unique_target_count_before_cap']:6,d} "
            f"({100*retention['target_retention_rate']:6.2f}%) "
            f"lost_target_events={retention['targets_completely_lost_events']:,}",
            flush=True
        )

    print("\nWorst tutor-bearing cap-hit states:",flush=True)
    for state_row in a["worst_states"][:10]:
        print(
            f"  seed={state_row['seed']} id={state_row['state_fingerprint']} "
            f"T{state_row['turn']} raw={state_row['raw_actions']} "
            f"tutors={state_row['kept_tutor_actions']}/{state_row['raw_tutor_actions']} "
            f"targets={state_row['kept_unique_targets']}/{state_row['raw_unique_targets']} "
            f"lost={len(state_row['lost_targets'])} "
            f"lost_engine={len(state_row['lost_known_engine_combo_targets'])} "
            f"lost_engine_routes={len(state_row['known_engine_combo_target_destination_routes_completely_lost'])} "
            f"sources={','.join(state_row['tutor_sources'])}",
            flush=True
        )

    payload={
        "provenance":report_provenance(
            "tutor-cap-audit",config,seed_provenance(base_seed,count),deck,
            {"worker_count":1,"parallelism":"sequential"},
        ),
        "base_seed":base_seed,"count":count,"action_cap":ACTION_CAP,
        "python_hash_seed":os.environ.get("PYTHONHASHSEED"),
        "scope":"Target-selecting tutors/searches; fixed-target fetchland-to-Island searches are excluded.",
        "selection_policy":(
            "Best representative per (source,target,destination); strict-cap overflow "
            "protects known routes, then whole target identities, then remaining routes by score."
        ),
        "known_target_sets":{
            "direct_combo_targets":sorted(DIRECT_COMBO_TARGETS),
            "validated_engine_access_targets":sorted(VALIDATED_ENGINE_ACCESS_TARGETS),
            "critical_combo_access_targets":sorted(KNOWN_ENGINE_TARGETS),
            "setup_card_advantage_engines":sorted(KNOWN_SETUP_ENGINE_TARGETS),
            "known_engine_combo_targets":sorted(KNOWN_ENGINE_COMBO_TARGETS),
        },
        "summary":{
            "truncated_states":a["truncated_states"],
            "tutor_truncated_states":a["tutor_truncated_states"],
            "raw_tutor_actions":a["raw_tutor_actions"],
            "kept_tutor_actions":a["kept_tutor_actions"],
            "tutor_action_retention_rate":action_retention,
            "unique_targets_raw_total":a["unique_targets_raw_total"],
            "unique_targets_kept_total":a["unique_targets_kept_total"],
            "state_summed_unique_target_retention_rate":target_retention,
            "lost_target_events":a["lost_target_events"],
            "lost_engine_target_events":a["lost_engine_target_events"],
            "lost_known_engine_combo_target_events":a["lost_known_engine_combo_target_events"],
            "lost_direct_combo_target_events":a["lost_direct_combo_target_events"],
            "lost_engine_access_target_events":a["lost_engine_access_target_events"],
            "lost_target_destination_route_events":a["lost_target_destination_route_events"],
            "lost_engine_target_destination_route_events":a["lost_engine_target_destination_route_events"],
            "route_representative_overflow_states":a["route_representative_overflow_states"],
            "route_representative_overflow_excess_total":a["route_representative_overflow_excess_total"],
            "target_reserve_overflow_states":a["target_reserve_overflow_states"],
            "max_unique_tutor_routes_before_cap":a["max_unique_tutor_routes_before_cap"],
            "max_target_aware_reserve_size":a["max_target_aware_reserve_size"],
            "lost_targets":dict(a["lost_targets"]),
            "lost_engine_targets":dict(a["lost_engine_targets"]),
            "lost_known_engine_combo_targets":dict(a["lost_known_engine_combo_targets"]),
            "lost_direct_combo_targets":dict(a["lost_direct_combo_targets"]),
            "lost_engine_access_targets":dict(a["lost_engine_access_targets"]),
            "lost_setup_engine_targets":dict(a["lost_setup_engine_targets"]),
            "lost_engine_target_destination_routes":dict(a["lost_engine_target_destination_routes"]),
            "source_counts_raw":dict(a["source_counts_raw"]),
            "source_counts_kept":dict(a["source_counts_kept"]),
            "source_unique_targets_raw_total":dict(a["source_unique_targets_raw_total"]),
            "source_unique_targets_kept_total":dict(a["source_unique_targets_kept_total"]),
            "source_lost_target_events":dict(a["source_lost_target_events"]),
            "source_lost_engine_target_events":dict(a["source_lost_engine_target_events"]),
            "source_lost_target_destination_route_events":dict(a["source_lost_target_destination_route_events"]),
            "source_lost_engine_target_destination_route_events":dict(a["source_lost_engine_target_destination_route_events"]),
            "source_retention":source_retention,
            "target_counts_raw":dict(a["target_counts_raw"]),
            "target_counts_kept":dict(a["target_counts_kept"]),
        },
        "rows":rows,
        "cap_hit_states":a["cap_hit_states"],
        "worst_states":a["worst_states"],
        "wall_seconds":time.time()-t0,
    }
    Path("tutor_cap_audit_report.json").write_text(json.dumps(payload,indent=2),encoding="utf-8")
    print("\nWrote tutor_cap_audit_report.json",flush=True)


def _trace_action(states,term):
    """Return the unique smoke successor whose newest trace contains term."""
    matches=[s for s in states if s.trace and term in s.trace[-1]]
    assert len(matches)==1,(term,[s.trace[-1] for s in states if s.trace])
    return matches[0]


def run_remora_smoke():
    """Focused cumulative-upkeep, reset, and state-identity regressions."""
    print("\n=== MYSTIC REMORA CUMULATIVE-UPKEEP SMOKE ===",flush=True)

    # First upkeep: the Island was tapped during our prior turn, untaps first,
    # and can then pay {1}. Opponent-cycle Remora draws remain independent of
    # the later choice to pay or sacrifice. Mana Drain mana is not yet usable.
    first=State(
        turn=1,library=("D1","D2","D3","D4"),hand=(),
        battlefield=(Perm("Mystic Remora"),Perm("Island",tapped=True)),
        drain_bank=2,remora_age=0,trace=("--- Turn 1 ---",),
    )
    first_due=end_turn(first)
    assert first_due.turn==2
    assert first_due.remora_age==0 and first_due.remora_upkeep_pending
    assert first_due.trace[-1].startswith(
        "Mystic Remora cumulative-upkeep trigger pending: on resolution "
        "add age counter 1"
    )
    assert first_due.blue==0 and first_due.colorless==0 and first_due.drain_bank==2
    # Only the two modeled opponent-fed cards exist before upkeep. The normal
    # draw D3 remains on top until the decision has resolved.
    assert first_due.hand==("D1","D2") and first_due.library[0]=="D3"
    assert not next(p for p in first_due.battlefield if p.name=="Island").tapped
    assert not any("cumulative upkeep {1}: pay" in s.trace[-1]
                   for s in legal_actions(first_due))

    first_actions=legal_actions(first_due)
    first_decline=_trace_action(first_actions,"decline; sacrifice Mystic Remora")
    first_tap=_trace_action(first_actions,"tap Island: +U")
    assert not has(first_decline,"Mystic Remora")
    assert first_decline.remora_age==0 and not first_decline.remora_upkeep_pending
    assert "Mystic Remora" in first_decline.graveyard
    assert first_decline.hand==("D1","D2","D3")
    assert first_decline.colorless==2 and first_decline.drain_bank==0

    payable_actions=legal_actions(first_tap)
    first_paid=_trace_action(payable_actions,"cumulative upkeep {1}: pay")
    paid_decline=_trace_action(payable_actions,"decline; sacrifice Mystic Remora")
    assert has(first_paid,"Mystic Remora")
    assert first_paid.remora_age==1 and not first_paid.remora_upkeep_pending
    assert first_paid.hand==("D1","D2","D3")
    assert first_paid.blue==0 and first_paid.colorless==2 and first_paid.drain_bank==0
    assert next(p for p in first_paid.battlefield if p.name=="Island").tapped
    assert not has(paid_decline,"Mystic Remora")
    print("First upkeep {1} + voluntary decline PASS",flush=True)

    upkeep_graph=new_graph_stats()
    closed=end_turn_frontier(
        [first],beam=10,resolve_remora_upkeep=True,
        graph_stats=upkeep_graph,
    )
    assert closed and all(not s.remora_upkeep_pending for s in closed)
    assert {"pay","decline"}<=set(_remora_resolution_family(s) for s in closed)
    assert upkeep_graph["upkeep_nodes_expanded"]>0
    assert upkeep_graph["upkeep_edges_generated"]>0
    assert upkeep_graph["remora_pay_results_generated"]>0
    assert upkeep_graph["remora_decline_results_generated"]>0
    diagnostic=end_turn_frontier(
        [first],beam=10,resolve_remora_upkeep=False
    )
    assert len(diagnostic)==1 and not diagnostic[0].remora_upkeep_pending
    assert diagnostic[0].remora_age==0
    assert diagnostic[0].hand==("D1","D2","D3")
    print("Dedicated closure/final snapshot       PASS",flush=True)

    # On the second upkeep, responses still see one existing age counter. On
    # resolution the second counter is added, so two Islands are required.
    second=State(
        turn=2,library=(),hand=(),
        battlefield=(
            Perm("Mystic Remora"),Perm("Island",tapped=True),
            Perm("Island",tapped=True),
        ),
        remora_age=1,trace=("--- Turn 2 ---",),
    )
    second_due=end_turn(second)
    assert second_due.remora_age==1 and second_due.remora_upkeep_pending
    # The two identical first-tap routes exact-compare alike; selecting either
    # is sufficient for the payment-cost integration check.
    first_island_taps=[s for s in legal_actions(second_due)
                       if s.trace and "tap Island: +U" in s.trace[-1]]
    assert first_island_taps
    one_tap=first_island_taps[0]
    second_island_taps=[s for s in legal_actions(one_tap)
                        if s.trace and "tap Island: +U" in s.trace[-1]]
    assert second_island_taps
    two_taps=second_island_taps[0]
    second_paid=_trace_action(
        legal_actions(two_taps),"cumulative upkeep {2}: pay"
    )
    assert second_paid.remora_age==2 and has(second_paid,"Mystic Remora")
    assert not second_paid.remora_upkeep_pending
    assert sum(p.tapped for p in second_paid.battlefield if p.name=="Island")==2
    second_closed=end_turn_frontier(
        [second],beam=50,resolve_remora_upkeep=True
    )
    assert any(
        _remora_resolution_family(s)=="pay"
        and s.remora_age==2
        and sum(p.tapped for p in s.battlefield if p.name=="Island")==2
        for s in second_closed
    )
    print("Second upkeep {2}                     PASS",flush=True)

    # Saga keeps only its already-earned lore counters during upkeep. It may
    # use an existing chapter-I mana ability after untap; the next lore counter
    # is not added until the Remora decision has resolved and main phase begins.
    saga_start=State(
        turn=1,library=(),hand=(),
        battlefield=(
            Perm("Mystic Remora"),
            Perm("Urza's Saga",tapped=True,counters=1),
        ),
        remora_age=0,
    )
    saga_due=end_turn(saga_start)
    saga_perm=next(p for p in saga_due.battlefield if p.name=="Urza's Saga")
    assert saga_perm.counters==1 and not saga_perm.tapped
    saga_mana=_trace_action(legal_actions(saga_due),"tap Saga: +C")
    saga_paid=_trace_action(
        legal_actions(saga_mana),"cumulative upkeep {1}: pay"
    )
    saga_perm=next(p for p in saga_paid.battlefield if p.name=="Urza's Saga")
    assert saga_perm.counters==2 and saga_perm.tapped
    forced_saga3=replace(
        saga_paid,
        battlefield=tuple(
            replace(p,counters=3,mode="saga3") if p.name=="Urza's Saga" else p
            for p in saga_paid.battlefield
        ),
        saga3_pending=True,
    )
    assert not can_end_turn_state(forced_saga3)
    no_find_source=replace(
        forced_saga3,
        library=("Power Artifact","Island","Rhystic Study"),
    )
    no_find=_trace_action(
        saga_actions(no_find_source),
        "Saga III search finds no card; shuffle; final chapter resolves",
    )
    assert not has(no_find,"Urza's Saga") and can_end_turn_state(no_find)
    assert Counter(no_find.library)==Counter(no_find_source.library)
    print("Saga upkeep/main-phase ordering        PASS",flush=True)

    # Fetching occurs in upkeep, before the normal draw, and the fetched Island
    # can then pay. This also protects the meaningful shuffle-before-draw line.
    fetch_start=State(
        turn=1,library=("R1","R2","Natural","Island","Tail"),hand=(),
        battlefield=(Perm("Mystic Remora"),Perm("Polluted Delta",tapped=True)),
        remora_age=0,
    )
    fetch_due=end_turn(fetch_start)
    assert fetch_due.hand==("R1","R2") and fetch_due.library[0]=="Natural"
    fetched=_trace_action(
        legal_actions(fetch_due),"Polluted Delta fetches Island and shuffles"
    )
    assert fetched.hand==("R1","R2")
    fetch_mana=_trace_action(legal_actions(fetched),"tap Island: +U")
    fetch_paid=_trace_action(
        legal_actions(fetch_mana),"cumulative upkeep {1}: pay"
    )
    assert has(fetch_paid,"Mystic Remora") and len(fetch_paid.hand)==3
    print("Fetch -> Island payment before draw    PASS",flush=True)

    dramatic=State(
        turn=3,library=(),hand=("Dramatic Reversal",),
        battlefield=(Perm("Mystic Remora"),Perm("Mana Vault",tapped=True)),
        blue=1,colorless=1,remora_age=2,remora_upkeep_pending=True,
    )
    reversed_state=_trace_action(
        legal_actions(dramatic),"Dramatic Reversal during Remora upkeep"
    )
    assert "Dramatic Reversal" in reversed_state.graveyard
    assert not next(
        p for p in reversed_state.battlefield if p.name=="Mana Vault"
    ).tapped
    vault_mana=_trace_action(
        legal_actions(reversed_state),"tap Mana Vault: +CCC"
    )
    dramatic_paid=_trace_action(
        legal_actions(vault_mana),"cumulative upkeep {3}: pay"
    )
    assert has(dramatic_paid,"Mystic Remora")

    dramatic_sources=State(
        turn=2,library=(),hand=("Dramatic Reversal",),
        battlefield=(
            Perm("Mystic Remora"),Perm("Island"),Perm("Sol Ring"),
            Perm("Mana Vault",tapped=True),
        ),
        remora_age=0,remora_upkeep_pending=True,
    )
    island_mana=_trace_action(
        legal_actions(dramatic_sources),"tap Island: +U"
    )
    sol_mana=_trace_action(legal_actions(island_mana),"tap Sol Ring: +CC")
    reversal_from_sources=_trace_action(
        legal_actions(sol_mana),"Dramatic Reversal during Remora upkeep"
    )
    source_paid=_trace_action(
        legal_actions(reversal_from_sources),"cumulative upkeep {1}: pay"
    )
    assert has(source_paid,"Mystic Remora")
    print("Dramatic Reversal payment enabler      PASS",flush=True)

    # Chain of Vapor is an implemented instant-speed alternative to paying or
    # sacrificing. Bouncing Remora makes the pending trigger harmless and the
    # next natural draw then occurs normally.
    chain_start=State(
        turn=1,library=("C1","C2","Natural"),hand=("Chain of Vapor",),
        battlefield=(Perm("Mystic Remora"),Perm("Island",tapped=True)),
        remora_age=2,
    )
    chain_due=end_turn(chain_start)
    chain_mana=_trace_action(legal_actions(chain_due),"tap Island: +U")
    chain_bounces=[
        s for s in legal_actions(chain_mana)
        if not has(s,"Mystic Remora")
        and "Mystic Remora" in s.hand
        and any("Chain resolution" in msg for msg in s.trace)
    ]
    assert chain_bounces
    chain_bounce=chain_bounces[0]
    assert chain_bounce.remora_age==0 and not chain_bounce.remora_upkeep_pending
    assert chain_bounce.hand[-1]=="Natural"
    print("Chain response bounces/resets Remora   PASS",flush=True)

    # Even when Chain's macro and mana routes hit a deliberately tiny cap, the
    # direct Remora-bounce resolution remains represented.
    global ACTION_CAP
    old_action_cap=ACTION_CAP
    try:
        ACTION_CAP=3
        broad=State(
            turn=3,library=(),hand=("Chain of Vapor",),
            battlefield=(Perm("Mystic Remora"),)+tuple(
                Perm(name) for name in sorted(F_ARTIFACTS)[:8]
            )+(Perm("Island"),Perm("Ancient Tomb")),
            blue=1,remora_age=1,remora_upkeep_pending=True,
        )
        broad_actions=remora_upkeep_actions(broad)
        assert len(broad_actions)<=3
        assert any(_remora_resolution_family(s)=="bounce" for s in broad_actions)
        assert any(_remora_resolution_family(s)=="decline" for s in broad_actions)
        assert any(s.remora_upkeep_pending for s in broad_actions)
        broad_closed=_resolve_remora_upkeep_frontier([broad],beam=3)
        assert any(_remora_resolution_family(s)=="pay" for s in broad_closed)
    finally:
        ACTION_CAP=old_action_cap
    print("Cap-hit Chain bounce retention         PASS",flush=True)

    # Bauble's delayed upkeep trigger can be ordered before cumulative upkeep,
    # while the fourth card remains the later normal draw.
    bauble=State(
        turn=1,library=("B","R1","R2","N"),hand=(),
        battlefield=(Perm("Mystic Remora"),),bauble_draws=1,
    )
    bauble_due=end_turn(bauble)
    assert bauble_due.hand==("B","R1","R2") and bauble_due.library==("N",)
    bauble_decline=_trace_action(
        legal_actions(bauble_due),"decline; sacrifice Mystic Remora"
    )
    assert bauble_decline.hand==("B","R1","R2","N")
    print("Bauble-before-upkeep / natural-after    PASS",flush=True)

    # No upkeep source means sacrifice is the only legal resolution. Prior
    # floating mana is cleared, and banked Drain mana waits until main phase.
    unable=State(
        turn=2,library=(),hand=(),battlefield=(Perm("Mystic Remora"),),
        blue=7,colorless=7,drain_bank=3,remora_age=1,
    )
    unable_due=end_turn(unable)
    assert unable_due.blue==0 and unable_due.colorless==0
    unable_actions=legal_actions(unable_due)
    assert len(unable_actions)==1
    forced=unable_actions[0]
    assert "decline; sacrifice Mystic Remora" in forced.trace[-1]
    assert not has(forced,"Mystic Remora") and forced.remora_age==0
    assert forced.colorless==3 and forced.drain_bank==0
    print("Unable to pay -> sacrifice            PASS",flush=True)

    pending_combo=State(
        turn=3,library=(),hand=(),
        battlefield=(
            Perm("Mystic Remora"),Perm(COMMANDER),
            Perm("Forensic Gadgeteer"),Perm("Basalt Monolith"),
        ),
        urza=True,remora_age=1,remora_upkeep_pending=True,
    )
    assert not check_win(pending_combo).won
    assert check_win(replace(pending_combo,remora_upkeep_pending=False)).won
    print("Pending upkeep blocks main win check   PASS",flush=True)

    closure_win=State(
        turn=2,library=(),hand=(),
        battlefield=(
            Perm("Mystic Remora"),Perm(COMMANDER),Perm("Chrome Dome"),
            Perm("Grinding Station"),Perm("Island",tapped=True),
        ),
        drain_bank=5,remora_age=0,urza=True,
    )
    closure_results=end_turn_frontier(
        [closure_win],beam=50,resolve_remora_upkeep=True
    )
    assert closure_results and any(
        s.won and s.win_family=="Chrome Dome" for s in closure_results
    )
    print("Closure marks completed main wins      PASS",flush=True)

    # A zone change removes the old age counters. Recasting the bounced card
    # creates a new age-zero Remora whose next upkeep is {1}, not {3}.
    aged=State(
        turn=2,library=(),hand=(),
        battlefield=(Perm("Mystic Remora"),Perm("Island")),
        remora_age=2,remora_upkeep_pending=True,
    )
    bounced=remove_perm(aged,0,to_grave=False)
    assert bounced.remora_age==0 and not bounced.remora_upkeep_pending
    bounced=replace(bounced,hand=("Mystic Remora",),blue=1)
    recast=cast_from_hand(bounced,"Mystic Remora")
    assert recast is not None and recast.remora_age==0
    assert not recast.remora_upkeep_pending and has(recast,"Mystic Remora")
    recast_due=end_turn(recast)
    assert recast_due.remora_age==0 and recast_due.remora_upkeep_pending
    assert "then pay {1} or sacrifice" in recast_due.trace[-1]
    print("Leave/recast age reset                 PASS",flush=True)

    # Age, pending phase, and recoverable graveyard contents all affect future
    # legality and therefore must not merge in exact, dominance, or Chain keys.
    identity=State(
        turn=3,library=("Chain of Vapor",),hand=(),
        battlefield=(Perm("Mystic Remora"),),remora_age=1,
    )
    older=replace(identity,remora_age=2)
    pending=replace(identity,remora_upkeep_pending=True)
    grave=replace(identity,graveyard=("Mystic Remora",))
    for other in (older,pending,grave):
        assert identity.key()!=other.key()
        assert dominance_signature(identity)!=dominance_signature(other)
        assert _chain_cache_key(identity)!=_chain_cache_key(other)
    assert end_turn_frontier([pending],beam=1)==[]
    assert all(
        "end_turn_frontier" in fn.__code__.co_names
        for fn in (search_hand,profile_single_hand,profile_search_hand)
    )
    print("Exact/dominance/cache distinctions     PASS",flush=True)
    print("\nREMORA SMOKE: ALL PASS",flush=True)


def run_draw_trace_smoke():
    """Focused named-draw and trace-neutrality regressions."""
    print("\n=== NAMED DRAW TRACE SMOKE ===",flush=True)

    def lines(s):
        return tuple(line for msg in s.trace for line in msg.splitlines())

    def assert_unchanged_except(before,after,*allowed):
        """Protect every State field outside an action's documented effects."""
        allowed=set(allowed)
        for name in State.__dataclass_fields__:
            if name not in allowed:
                assert getattr(after,name)==getattr(before,name),name

    # The movement helper preserves order and touches only hand/library. A
    # natural draw is folded into the existing turn/action trace entry so the
    # historical trace count—and therefore deterministic shuffle seed—stays
    # unchanged.
    normal=State(
        turn=2,library=("Normal","Tail"),hand=("Held",),battlefield=(),
        trace=("--- Turn 2 ---",),blue=3,colorless=4,drain_bank=2,
    )
    drawn_state,drawn=draw_from_library(normal,3)
    assert drawn==("Normal","Tail")
    assert drawn_state.hand==("Held","Normal","Tail")
    assert drawn_state.library==() and normal.library==("Normal","Tail")
    assert_unchanged_except(normal,drawn_state,"hand","library")
    main=_enter_precombat_main(normal)
    assert main.hand==("Held","Normal") and main.library==("Tail",)
    assert "normal draw for turn 2: Normal" in lines(main)
    assert len(main.trace)==len(normal.trace)
    detailed=append_trace_detail(normal,"normal draw for turn 2: Normal")
    assert len(detailed.trace)==len(normal.trace)
    assert shuffled_library(normal,"named-draw-canary")==shuffled_library(
        detailed,"named-draw-canary"
    )
    tutor_trace=State(
        turn=2,library=(),hand=(),battlefield=(),
        trace=("Muddle the Mixture -> Grinding Station",),
    )
    tutor_detail=append_trace_detail(
        tutor_trace,"normal draw for turn 2: Audit Card"
    )
    assert _tutor_action_from_trace(tutor_detail)==_tutor_action_from_trace(
        tutor_trace
    )
    assert _action_family_from_state(tutor_detail)==_action_family_from_state(
        tutor_trace
    )
    assert classify_action(tutor_detail.trace[-1])==classify_action(
        tutor_trace.trace[-1]
    )

    opening=[f"Opening {i}" for i in range(7)]+["Turn One Draw","Tail"]
    opening_result=search_hand(
        opening,7,[],max_turn=0,beam=1,max_actions_per_turn=1,
        caverns_live=False,
    )
    assert "normal draw for turn 1: Turn One Draw" in tuple(
        line for msg in opening_result[2] for line in msg.splitlines()
    )
    assert len(opening_result[2])==1
    assert all(
        {"draw_from_library","append_trace_detail"}<=set(fn.__code__.co_names)
        for fn in (search_hand,profile_single_hand,profile_search_hand)
    )
    print("Normal T1/later draws + trace neutrality PASS",flush=True)

    # Preserve the current aggregate assignment exactly: delayed Baubles first,
    # then Remora, Rhystic, environmental Mastermind, and finally the normal
    # draw after the pending Remora decision.
    environment=State(
        turn=1,
        library=("B1","B2","R1","R2","H1","H2","F1","N","Tail"),
        hand=(),
        battlefield=(
            Perm("Mystic Remora"),Perm("Rhystic Study"),
            Perm("Faerie Mastermind"),Perm("Mishra's Bauble"),
            Perm("Urza's Bauble"),
        ),
        trace=("--- Turn 1 ---",),
    )
    mishra=_trace_action(
        draw_sac_actions(environment),
        "Mishra's Bauble: tap+sacrifice -> delayed next-upkeep draw",
    )
    both=_trace_action(
        draw_sac_actions(mishra),
        "Urza's Bauble: tap+sacrifice -> delayed next-upkeep draw",
    )
    assert pending_bauble_draw_sources(both)==(
        "Mishra's Bauble","Urza's Bauble"
    )
    due=end_turn(both)
    assert due.hand==("B1","B2","R1","R2","H1","H2","F1")
    assert due.library==("N","Tail") and due.remora_upkeep_pending
    due_lines=lines(due)
    expected_events=(
        "Mishra's Bauble delayed draw: B1",
        "Urza's Bauble delayed draw: B2",
        "Mystic Remora draws 2: R1, R2",
        "Rhystic Study draws 2: H1, H2",
        "Faerie Mastermind environmental draw: F1",
    )
    positions=[due_lines.index(event) for event in expected_events]
    assert positions==sorted(positions)
    assert not any("normal draw" in line for line in due_lines)
    assert len(due.trace)==len(both.trace)+2
    declined=_trace_action(
        legal_actions(due),"decline; sacrifice Mystic Remora"
    )
    assert declined.hand==due.hand+("N",) and declined.library==("Tail",)
    assert "normal draw for turn 2: N" in lines(declined)
    assert len(declined.trace)==len(due.trace)+1

    reverse=State(
        turn=1,library=("X","Y"),hand=(),
        battlefield=(Perm("Urza's Bauble"),Perm("Mishra's Bauble")),
        trace=("--- Turn 1 ---",),
    )
    reverse=_trace_action(draw_sac_actions(reverse),"Urza's Bauble:")
    reverse=_trace_action(draw_sac_actions(reverse),"Mishra's Bauble:")
    assert pending_bauble_draw_sources(reverse)==(
        "Urza's Bauble","Mishra's Bauble"
    )
    fallback=State(
        turn=1,library=("Only",),hand=(),battlefield=(),bauble_draws=1,
        trace=("--- Turn 1 ---",),
    )
    assert pending_bauble_draw_sources(fallback)==(
        "Mishra's/Urza's Bauble",
    )
    partial=State(
        turn=1,library=("Older","Newer"),hand=(),battlefield=(),
        bauble_draws=2,
        trace=(
            "--- Turn 1 ---",
            "Urza's Bauble: tap+sacrifice -> delayed next-upkeep draw",
        ),
    )
    assert pending_bauble_draw_sources(partial)==(
        "Mishra's/Urza's Bauble","Urza's Bauble",
    )
    print("Environmental + delayed draw attribution PASS",flush=True)

    uthros=State(
        turn=3,library=("Grinding Station","Tail"),hand=(),
        battlefield=(Perm("Uthros Research Craft"),),uthros_counters=3,
        trace=("cast setup",),
    )
    uthros_draw=artifact_cast_triggers(uthros,"Welding Jar")
    assert uthros_draw.hand==("Grinding Station",)
    assert uthros_draw.library==("Tail",) and uthros_draw.uthros_counters==4
    assert_unchanged_except(
        uthros,uthros_draw,"hand","library","uthros_counters","trace"
    )
    assert uthros_draw.trace[-1]==(
        "Uthros trigger draws: Grinding Station; "
        "+1 station counter before artifact resolves"
    )

    ring=State(
        turn=3,library=("A","B","C","D"),hand=(),
        battlefield=(Perm("The One Ring"),),ring_counters=2,
    )
    ring_draw=ring_actions(ring)[0]
    assert ring_draw.hand==("A","B","C") and ring_draw.library==("D",)
    assert ring_draw.battlefield==(Perm("The One Ring",tapped=True),)
    assert ring_draw.ring_counters==3
    assert_unchanged_except(
        ring,ring_draw,"hand","library","battlefield","ring_counters","trace"
    )
    assert ring_draw.trace[-1]=="The One Ring draws 3: A, B, C"

    top=State(
        turn=2,library=("Chrome Dome","Tail"),hand=(),
        battlefield=(Perm("Sensei's Divining Top"),),
    )
    top_draw=_trace_action(top_actions(top),"Sensei's Divining Top -> draw")
    assert top_draw.hand==("Chrome Dome",)
    assert top_draw.library==("Sensei's Divining Top","Tail")
    assert top_draw.battlefield==() and top_draw.graveyard==()
    assert_unchanged_except(
        top,top_draw,"hand","library","battlefield","trace"
    )
    assert "draw: Chrome Dome; Top goes on top" in top_draw.trace[-1]
    print("Uthros / Ring / Top named draws         PASS",flush=True)

    clue=State(
        turn=2,library=("Chrome Dome","Tail"),hand=(),
        battlefield=(Perm("Clue",mode="clue"),),colorless=2,
    )
    clue_draw=clue_draw_actions(clue)[0]
    assert clue_draw.hand==("Chrome Dome",) and clue_draw.library==("Tail",)
    assert clue_draw.battlefield==() and clue_draw.graveyard==()
    assert clue_draw.blue==0 and clue_draw.colorless==0
    assert_unchanged_except(
        clue,clue_draw,"hand","library","battlefield","graveyard",
        "blue","colorless","trace"
    )
    assert clue_draw.trace[-1]=="sac Clue -> draw: Chrome Dome"

    probe=State(
        turn=2,library=("Island","Tail"),hand=("Gitaxian Probe",),
        battlefield=(),
    )
    probe_draw=cast_from_hand(probe,"Gitaxian Probe")
    assert probe_draw is not None
    assert probe_draw.hand==("Island",) and probe_draw.library==("Tail",)
    assert probe_draw.spell_cast_this_turn
    assert_unchanged_except(
        probe,probe_draw,"hand","library","spell_cast_this_turn","trace"
    )
    assert "Gitaxian Probe targets an opponent -> draw: Island"==probe_draw.trace[-1]

    mastermind=State(
        turn=3,library=("Mox Opal","Tail"),hand=(),
        battlefield=(Perm("Faerie Mastermind"),),blue=1,colorless=3,
    )
    mastermind_draw=faerie_mastermind_actions(mastermind)[0]
    assert mastermind_draw.hand==("Mox Opal",)
    assert mastermind_draw.library==("Tail",)
    assert mastermind_draw.blue==0 and mastermind_draw.colorless==0
    assert_unchanged_except(
        mastermind,mastermind_draw,"hand","library","blue","colorless","trace"
    )
    assert mastermind_draw.trace[-1].endswith("we draw: Mox Opal")
    print("Clue / Probe / Mastermind named draws   PASS",flush=True)

    sea_gate=State(
        turn=5,library=("SG1","SG2","SG3"),
        hand=("Sea Gate Restoration","Held"),battlefield=(),blue=7,
    )
    sea_gate_draw=cast_from_hand(sea_gate,"Sea Gate Restoration")
    assert sea_gate_draw is not None
    assert sea_gate_draw.hand==("Held","SG1","SG2")
    assert sea_gate_draw.library==("SG3",)
    assert sea_gate_draw.blue==0 and sea_gate_draw.colorless==0
    assert sea_gate_draw.spell_cast_this_turn
    assert_unchanged_except(
        sea_gate,sea_gate_draw,"hand","library","blue","colorless",
        "spell_cast_this_turn","trace"
    )
    assert sea_gate_draw.trace[-1]=="Sea Gate Restoration draws 2: SG1, SG2"

    coliseum=State(
        turn=4,library=("C1","C2","C3","Tail"),hand=(),
        battlefield=(Perm("Cephalid Coliseum"),),blue=1,
        graveyard=tuple(f"G{i}" for i in range(7)),
    )
    coliseum_actions=graveyard_land_actions(coliseum)
    assert len(coliseum_actions)==1
    coliseum_draw=coliseum_actions[0]
    assert coliseum_draw.hand==() and coliseum_draw.library==("Tail",)
    assert coliseum_draw.battlefield==() and coliseum_draw.blue==0
    assert coliseum_draw.graveyard==(
        tuple(f"G{i}" for i in range(7))
        +("Cephalid Coliseum","C1","C2","C3")
    )
    assert_unchanged_except(
        coliseum,coliseum_draw,"hand","library","battlefield","graveyard",
        "blue","colorless","trace"
    )
    assert "draw 3: C1, C2, C3; discard C1, C2, C3" in coliseum_draw.trace[-1]
    print("Sea Gate / Coliseum named draws         PASS",flush=True)

    draw_artifacts=(
        (
            State(2,("AetherCard","Tail"),(),(Perm("Aether Spellbomb"),),
                  colorless=1),
            "Aether Spellbomb:",("AetherCard",),"AetherCard",
        ),
        (
            State(2,("Well1","Well2","Tail"),(),(Perm("Witching Well"),),
                  blue=1,colorless=3),
            "Witching Well:",("Well1","Well2"),"Well1, Well2",
        ),
        (
            State(2,("Cam1","Cam2","Tail"),(),
                  (Perm("Sewer-veillance Cam"),),blue=1,colorless=3),
            "Cam:",("Cam1","Cam2"),"Cam1, Cam2",
        ),
        (
            State(2,("VexingCard","Tail"),(),(Perm("Vexing Bauble"),),
                  colorless=1),
            "Vexing Bauble:",("VexingCard",),"VexingCard",
        ),
    )
    for source,prefix,expected,names_text in draw_artifacts:
        result=_trace_action(draw_sac_actions(source),prefix)
        assert result.hand==expected and result.library==("Tail",)
        sacrificed=source.battlefield[0].name
        assert result.battlefield==() and result.graveyard==(sacrificed,)
        assert result.blue==0 and result.colorless==0
        assert_unchanged_except(
            source,result,"hand","library","battlefield","graveyard",
            "blue","colorless","trace"
        )
        assert names_text in result.trace[-1]

    key_state=State(
        turn=3,library=("Underlying","Tail"),hand=(),
        battlefield=(Perm("Sensei's Divining Top"),Perm("Voltaic Key")),
        colorless=1,
    )
    key_draw=top_key_combo_actions(key_state)[0]
    assert key_draw.hand==("Underlying","Sensei's Divining Top")
    assert key_draw.library==("Tail",)
    assert key_draw.battlefield==(Perm("Voltaic Key",tapped=True),)
    assert key_draw.blue==0 and key_draw.colorless==0
    assert_unchanged_except(
        key_state,key_draw,"hand","library","battlefield","blue",
        "colorless","trace"
    )
    assert key_draw.trace[-1].endswith(
        "draws: Underlying, Sensei's Divining Top"
    )
    print("Other artifact draw paths named        PASS",flush=True)

    print("\nDRAW TRACE SMOKE: ALL PASS",flush=True)


def run_bounce_smoke():
    """Focused target, cost, timing, and destination regressions for bounce."""
    print("\n=== BOUNCE / REMORA RESPONSE SMOKE ===",flush=True)

    def trace_lines(s):
        return tuple(line for msg in s.trace for line in msg.splitlines())

    # Chain costs U, is an instant, can return our nonland Remora, and needs
    # one sacrificed land for each additional copied target.
    chain=State(
        turn=2,library=(),hand=("Chain of Vapor",),
        battlefield=(Perm("Mystic Remora"),Perm("Island",mode="landface")),
        blue=1,remora_age=2,
    )
    chain_one=_trace_action(
        chain_of_vapor_actions(chain),"bounce Mystic Remora"
    )
    assert chain_one.blue==0 and chain_one.colorless==0
    assert chain_one.graveyard==("Chain of Vapor",)
    assert chain_one.hand==("Mystic Remora",)
    assert chain_one.battlefield==(Perm("Island",mode="landface"),)
    assert chain_one.remora_age==0 and not chain_one.remora_upkeep_pending
    assert chain_one.spell_cast_this_turn

    copied=replace(
        chain,battlefield=(
            Perm("Mystic Remora"),Perm("Rhystic Study"),
            Perm("Island",mode="landface"),
        ),
    )
    chain_two=next(
        a for a in chain_of_vapor_actions(copied)
        if {"Mystic Remora","Rhystic Study"}<=set(a.hand)
    )
    assert chain_two.graveyard==("Chain of Vapor","Island")
    assert not chain_two.battlefield

    token_chain=State(
        turn=2,library=(),hand=("Chain of Vapor",),
        battlefield=(Perm("Clue",mode="clue"),),blue=1,
    )
    token_result=chain_of_vapor_actions(token_chain)[0]
    assert token_result.hand==() and token_result.battlefield==()
    assert token_result.graveyard==("Chain of Vapor",)

    creature_face=State(
        turn=2,library=(),hand=("Chain of Vapor",),blue=1,
        battlefield=(Perm("Hydroelectric Specimen",sick=False),),
    )
    creature_bounce=chain_of_vapor_actions(creature_face)[0]
    assert creature_bounce.hand==("Hydroelectric Specimen",)
    land_face=replace(
        creature_face,battlefield=(
            Perm("Hydroelectric Specimen",mode="landface"),
        ),
    )
    assert chain_of_vapor_actions(land_face)==[]
    print("Chain cost/copies/faces/token destination PASS",flush=True)

    # Otawara channels for 3U, with one generic reduction per controlled
    # legendary creature. It is not a spell and may target our enchantment.
    otawara=State(
        turn=2,library=(),hand=("Otawara, Soaring City",),
        battlefield=(Perm("Mystic Remora"),),blue=1,colorless=3,
        remora_age=2,
    )
    ota=otawara_channel_actions(otawara)[0]
    assert ota.hand==("Mystic Remora",) and ota.battlefield==()
    assert ota.graveyard==("Otawara, Soaring City",)
    assert ota.blue==0 and ota.colorless==0
    assert not ota.spell_cast_this_turn and ota.remora_age==0
    assert "pay {3}{U}" in ota.trace[-1]

    urza_reduction=replace(
        otawara,battlefield=(
            Perm("Mystic Remora"),Perm(COMMANDER,sick=False),
        ),colorless=2,urza=True,commander_in_command_zone=False,
    )
    assert otawara_channel_cost(urza_reduction)==(2,1)
    assert otawara_channel_actions(urza_reduction)
    assert not otawara_channel_actions(replace(urza_reduction,colorless=1))
    three_legends=replace(
        urza_reduction,battlefield=(
            Perm("Mystic Remora"),Perm(COMMANDER,sick=False),
            Perm("Hope of Ghirapur",sick=False),
            Perm("The Reality Chip",sick=False),
        ),colorless=0,
    )
    assert otawara_channel_cost(three_legends)==(0,1)
    assert otawara_channel_actions(three_legends)

    attached_chip=replace(
        urza_reduction,battlefield=(
            Perm("Mystic Remora"),
            Perm("The Reality Chip",mode="chip_attached"),
        ),urza=False,commander_in_command_zone=True,
    )
    assert otawara_channel_cost(attached_chip)==(3,1)

    medallion=replace(
        otawara,battlefield=(
            Perm("Mystic Remora"),Perm("Sapphire Medallion"),
        ),colorless=2,
    )
    assert not otawara_channel_actions(medallion)
    plain_land=State(
        turn=2,library=(),hand=("Otawara, Soaring City",),
        battlefield=(Perm("Island",mode="landface"),),blue=1,colorless=3,
    )
    assert otawara_channel_actions(plain_land)==[]
    special_lands=replace(
        plain_land,battlefield=(
            Perm("Urza's Saga",mode="landface"),
            Perm("Seat of the Synod"),
        ),
    )
    assert {a.hand[-1] for a in otawara_channel_actions(special_lands)}=={
        "Urza's Saga","Seat of the Synod",
    }
    print("Otawara targets/cost/reduction/channel   PASS",flush=True)

    # Spellbomb's U mode is creature-only; Remora is not a legal target. The
    # Oracle goldfish also intentionally prunes bouncing our Urza/Construct.
    # Its sacrifice is a cost and it has no tap symbol.
    spellbomb=State(
        turn=2,library=("Drawn",),hand=(),blue=1,colorless=1,
        battlefield=(
            Perm("Aether Spellbomb",tapped=True),Perm("Mystic Remora"),
            Perm("Spellseeker",sick=True),Perm("Construct",mode="construct"),
            Perm(COMMANDER,sick=False),
        ),
        urza=True,commander_in_command_zone=False,
    )
    bomb_actions=aether_spellbomb_actions(spellbomb)
    bomb_bounce=_trace_action(bomb_actions,"bounce Spellseeker")
    assert bomb_bounce.hand==("Spellseeker",)
    assert "Aether Spellbomb" in bomb_bounce.graveyard
    assert has(bomb_bounce,"Mystic Remora")
    assert not any("bounce Mystic Remora" in a.trace[-1] for a in bomb_actions)
    assert not any("bounce Construct" in a.trace[-1] for a in bomb_actions)
    assert not any(f"bounce {COMMANDER}" in a.trace[-1] for a in bomb_actions)
    bomb_draw=_trace_action(bomb_actions,"sacrifice -> draw")
    assert bomb_draw.hand==("Drawn",)
    print("Aether creature-only bounce/draw modes    PASS",flush=True)

    # Goldfish-pruned bounce targets: returning Urza or a Construct is legal
    # Magic, but intentionally omitted from every own-bounce generator because
    # it adds no retained goldfish value and materially increases branching.
    prune_board=(
        Perm(COMMANDER,sick=False),Perm("Construct",mode="construct"),
        Perm("Mystic Remora"),
    )
    chain_prune=State(
        turn=2,library=(),hand=("Chain of Vapor",),blue=1,
        battlefield=prune_board,urza=True,commander_in_command_zone=False,
    )
    chain_prune_actions=chain_of_vapor_actions(chain_prune)
    assert chain_prune_actions
    assert all(COMMANDER not in a.hand and "Construct" not in a.hand
               for a in chain_prune_actions)
    assert all("bounce Urza, Lord High Artificer" not in "\n".join(a.trace)
               and "bounce Construct" not in "\n".join(a.trace)
               for a in chain_prune_actions)

    ota_prune=replace(
        chain_prune,hand=("Otawara, Soaring City",),blue=1,colorless=2,
    )
    ota_prune_actions=otawara_channel_actions(ota_prune)
    assert ota_prune_actions
    assert all(COMMANDER not in a.hand and "Construct" not in a.hand
               for a in ota_prune_actions)

    knack_prune=State(
        turn=2,library=(),hand=(),
        battlefield=(
            Perm("Spellseeker",sick=False,knack_granted=True),
            Perm(COMMANDER,sick=False),Perm("Construct",mode="construct"),
            Perm("Mystic Remora"),
        ),
        urza=True,commander_in_command_zone=False,
    )
    knack_prune_actions=knack_bounce_actions(knack_prune)
    assert knack_prune_actions
    assert all(COMMANDER not in a.hand and "Construct" not in a.hand
               for a in knack_prune_actions)
    assert any("bounces our Mystic Remora" in a.trace[-1]
               for a in knack_prune_actions)
    print("Urza/Construct own-bounce pruning          PASS",flush=True)

    # Oboro's printed {1} self-return ability has no tap symbol, so a tapped
    # Oboro may activate it. It targets/returns only that land itself.
    oboro=State(
        turn=2,library=(),hand=(),colorless=1,
        battlefield=(Perm("Oboro, Palace in the Clouds",tapped=True),),
    )
    oboro_return=_trace_action(oboro_minamo_actions(oboro),"Oboro: pay 1")
    assert oboro_return.colorless==0 and oboro_return.blue==0
    assert oboro_return.hand==("Oboro, Palace in the Clouds",)
    assert not oboro_return.battlefield and not oboro_return.graveyard
    print("Oboro {1} tapped self-return             PASS",flush=True)

    # Knack/Helix costs U to cast. The granted creature must itself be ready to
    # pay the tap-symbol cost, may target itself, and may return any nonland.
    knack_base=State(
        turn=2,library=(),hand=("Banishing Knack",),blue=1,
        battlefield=(Perm("Spellseeker",sick=False),Perm("Mystic Remora")),
    )
    cast_knack=_trace_action(
        knack_bounce_actions(knack_base),"cast Banishing Knack targeting Spellseeker"
    )
    assert cast_knack.blue==0 and cast_knack.hand==()
    assert cast_knack.graveyard==("Banishing Knack",)
    remora_knack=_trace_action(
        knack_bounce_actions(cast_knack),"bounces our Mystic Remora"
    )
    assert remora_knack.hand==("Mystic Remora",)
    assert remora_knack.battlefield==(
        Perm("Spellseeker",tapped=True,sick=False,knack_granted=True),
    )

    self_state=State(
        turn=2,library=(),hand=(),
        battlefield=(Perm("Spellseeker",sick=False,knack_granted=True),),
    )
    self_bounce=_trace_action(
        knack_bounce_actions(self_state),"bounces our Spellseeker"
    )
    assert self_bounce.hand==("Spellseeker",) and not self_bounce.battlefield
    assert self_bounce.knack_target=="" and self_bounce.knack_target_mode==""
    assert knack_bounce_actions(replace(
        self_state,battlefield=(Perm("Spellseeker",tapped=True,sick=False),)
    ))==[]
    assert knack_bounce_actions(replace(
        self_state,battlefield=(Perm("Spellseeker",sick=True),)
    ))==[]

    exact_object=State(
        turn=2,library=(),hand=(),
        battlefield=(
            Perm("Spellseeker",sick=True,knack_granted=True),
            Perm("Spellseeker",sick=False,mode="chrome_copy"),
        ),
    )
    assert knack_bounce_actions(exact_object)==[]
    chrome_bound=replace(
        exact_object,
        battlefield=(
            Perm("Spellseeker",sick=True),
            Perm("Spellseeker",sick=False,mode="chrome_copy",knack_granted=True),
        ),
    )
    assert exact_object.key()!=chrome_bound.key()
    assert dominance_signature(exact_object)!=dominance_signature(chrome_bound)
    mdfc_knack=State(
        turn=2,library=(),hand=(),
        battlefield=(Perm("Hydroelectric Specimen",sick=False,knack_granted=True),),
    )
    assert knack_bounce_actions(mdfc_knack)[0].hand==(
        "Hydroelectric Specimen",
    )
    assert knack_bounce_actions(replace(
        mdfc_knack,battlefield=(
            Perm("Hydroelectric Specimen",sick=False,mode="landface",knack_granted=True),
        ),
    ))==[]
    print("Knack/Helix tap/self/object/face legality PASS",flush=True)

    # Chain plans distinguish same-name permanents when their actual object
    # state differs, while canonical result-state merging still removes truly
    # equivalent choices.
    same_name_chain=State(
        turn=2,library=(),hand=("Chain of Vapor",),blue=1,
        battlefield=(Perm("Spellskite"),Perm("Spellskite",tapped=True)),
    )
    same_name_results=chain_of_vapor_actions(same_name_chain)
    remaining_tap_states={
        tuple(p.tapped for p in a.battlefield if p.name=="Spellskite")
        for a in same_name_results
    }
    assert (True,) in remaining_tap_states and (False,) in remaining_tap_states
    print("Chain same-name instance distinction      PASS",flush=True)

    # Saga III is an independent pending trigger. Otawara may return Saga after
    # III triggers; the search still resolves, Saga remains in hand, and the
    # found artifact enters after the shuffle. Chain/Knack cannot target Saga
    # because their return target must be a nonland permanent.
    saga_pending=State(
        turn=4,library=("Sol Ring","Island"),
        hand=("Otawara, Soaring City",),blue=1,colorless=2,
        battlefield=(
            Perm("Urza's Saga",counters=3,mode="saga3"),
            Perm(COMMANDER,sick=False),
        ),
        urza=True,commander_in_command_zone=False,saga3_pending=True,
    )
    saga_bounced=next(
        a for a in legal_actions(saga_pending)
        if a.trace[-1].startswith("Otawara channel:")
    )
    assert saga_bounced.saga3_pending and "Urza's Saga" in saga_bounced.hand
    saga_resolved=next(
        a for a in saga_actions(saga_bounced) if has(a,"Sol Ring")
    )
    assert not saga_resolved.saga3_pending
    assert "Urza's Saga" in saga_resolved.hand and has(saga_resolved,"Sol Ring")
    assert "Island" in saga_resolved.library
    chain_vs_saga=State(
        turn=4,library=(),hand=("Chain of Vapor",),blue=1,
        battlefield=(Perm("Urza's Saga",counters=3,mode="saga3"),),
    )
    assert chain_of_vapor_actions(chain_vs_saga)==[]
    print("Saga III pending-trigger/Otawara response  PASS",flush=True)

    # The cumulative-upkeep stack window admits channel and a two-step
    # Knack/Helix line, clears the old obligation after bounce, and still gates
    # sorcery-speed actions. Recasting creates a fresh age-zero object.
    upkeep_ota=State(
        turn=2,library=("Natural","Tail"),
        hand=("Otawara, Soaring City","Sea Gate Restoration","Island"),
        battlefield=(
            Perm("Mystic Remora"),Perm(COMMANDER,sick=False),
            Perm("Repurposing Bay"),Perm("Sapphire Medallion"),
        ),
        blue=1,colorless=2,remora_age=0,remora_upkeep_pending=True,
        urza=True,commander_in_command_zone=False,
        trace=(
            "Mystic Remora cumulative-upkeep trigger pending: on resolution "
            "add age counter 1; then pay {1} or sacrifice",
        ),
    )
    pending_actions=legal_actions(upkeep_ota)
    assert not any(
        line.startswith(("Repurposing Bay","cast Sea Gate Restoration","play land"))
        for a in pending_actions for line in trace_lines(a)[-2:]
    )
    ota_done=next(
        a for a in pending_actions
        if any(line.startswith("Otawara channel:") for line in trace_lines(a))
    )
    assert not ota_done.remora_upkeep_pending and ota_done.remora_age==0
    assert "Mystic Remora" in ota_done.hand and "Natural" in ota_done.hand
    assert ota_done.library==("Tail",)
    assert remora_upkeep_actions(ota_done)==[]
    recast=cast_from_hand(replace(ota_done,blue=1),"Mystic Remora")
    assert recast is not None and has(recast,"Mystic Remora")
    assert recast.remora_age==0 and not recast.remora_upkeep_pending

    upkeep_knack=State(
        turn=2,library=("Natural",),hand=("Retraction Helix",),blue=1,
        battlefield=(Perm("Mystic Remora"),Perm("Spellseeker",sick=False)),
        remora_age=0,remora_upkeep_pending=True,
        trace=(
            "Mystic Remora cumulative-upkeep trigger pending: on resolution "
            "add age counter 1; then pay {1} or sacrifice",
        ),
    )
    cast_during=next(
        a for a in remora_upkeep_actions(upkeep_knack)
        if a.remora_upkeep_pending
        and a.trace[-1].splitlines()[0].startswith("cast Retraction Helix targeting Spellseeker")
    )
    knack_done=next(
        a for a in remora_upkeep_actions(cast_during)
        if any("bounces our Mystic Remora" in line for line in trace_lines(a))
    )
    assert not knack_done.remora_upkeep_pending and knack_done.remora_age==0
    assert "Mystic Remora" in knack_done.hand

    sink_pending=State(
        turn=2,library=(),hand=("Sink into Stupor",),blue=2,colorless=1,
        battlefield=(Perm("Mystic Remora"),),
        remora_age=0,remora_upkeep_pending=True,
    )
    assert not any(
        "Sink into Stupor" in line
        for a in legal_actions(sink_pending) for line in trace_lines(a)
    )
    sink_main=cast_from_hand(replace(
        sink_pending,remora_upkeep_pending=False,remora_age=0,
    ),"Sink into Stupor")
    assert sink_main is not None and "Sink into Stupor" in sink_main.graveyard
    assert has(sink_main,"Mystic Remora")
    assert sink_main.trace[-1]=="cast Sink into Stupor (opponent target assumed)"
    print("Upkeep responses/gating/reset/Sink scope   PASS",flush=True)

    # Under a real cap hit, preserve materially different Remora reset routes:
    # terminal Chain/Otawara plus pending Knack and Helix continuations.
    global ACTION_CAP
    old_cap=ACTION_CAP
    try:
        ACTION_CAP=8
        broad=State(
            turn=3,library=(),
            hand=(
                "Chain of Vapor","Otawara, Soaring City",
                "Banishing Knack","Retraction Helix",
            ),
            battlefield=(
                Perm("Mystic Remora"),Perm(COMMANDER,sick=False),
                Perm("Spellseeker",sick=False),Perm("Sol Ring"),
                Perm("Mana Vault"),Perm("Island"),Perm("Ancient Tomb"),
            ),
            blue=5,colorless=5,remora_age=1,remora_upkeep_pending=True,
            urza=True,commander_in_command_zone=False,
            trace=(
                "Mystic Remora cumulative-upkeep trigger pending: on resolution "
                "add age counter 2; then pay {2} or sacrifice",
            ),
        )
        kept=remora_upkeep_actions(broad)
        sources={_remora_response_source(a) for a in kept}
        assert {
            "Chain of Vapor","Otawara, Soaring City",
            "Banishing Knack","Retraction Helix",
        } <= sources
        assert any(_remora_resolution_family(a)=="pay" for a in kept)
        assert any(_remora_resolution_family(a)=="decline" for a in kept)
    finally:
        ACTION_CAP=old_cap
    print("Remora cap preserves bounce-source diversity PASS",flush=True)
    print("\nBOUNCE SMOKE: ALL PASS",flush=True)


def run_bay_smoke():
    """Focused Repurposing Bay and producer-ETB accounting regressions."""
    print("\n=== REPURPOSING BAY / PRODUCER ETB SMOKE ===",flush=True)

    def bay_success(actions,target):
        return next(
            a for a in actions
            if a.trace[-1].splitlines()[0].endswith(" -> "+target)
        )

    # Printed baseline: pay {2}, tap Bay, sacrifice another MV2 artifact,
    # put exactly MV3 Battered onto the battlefield, then shuffle.
    base=State(
        turn=3,
        library=("Battered Golem","Island","Force of Will","Misty Rainforest"),
        hand=(),
        battlefield=(Perm("Repurposing Bay"),Perm("Sapphire Medallion")),
        colorless=2,trace=("setup",),
    )
    assert not repurposing_bay_actions(replace(base,colorless=1))
    actions=repurposing_bay_actions(base)
    result=bay_success(actions,"Battered Golem")
    assert result.colorless==0 and result.blue==0
    assert result.battlefield==(
        Perm("Repurposing Bay",tapped=True),
        Perm("Battered Golem",sick=True),
    )
    assert result.graveyard==("Sapphire Medallion",)
    assert "Battered Golem" not in result.library
    assert result.hand==() and not result.spell_cast_this_turn
    assert len(result.trace)>=len(base.trace)+1
    assert result.trace[-1].splitlines()[0].startswith("Repurposing Bay sacs ")
    assert "pay {2}, tap" in result.trace[-1]
    assert _tutor_action_from_trace(result)==(
        "Repurposing Bay","Battered Golem","battlefield",
    )
    assert any("finds no card" in a.trace[-1] for a in actions)
    print("Sapphire MV2 -> Battered MV3 accounting    PASS",flush=True)

    # Ordinary tokens are MV0, while Chrome copy tokens retain copied mana
    # cost/MV. Both exact +1 searches are represented.
    clue=State(
        turn=3,library=("Aether Spellbomb","Chrome Dome","Island"),hand=(),
        battlefield=(Perm("Repurposing Bay"),Perm("Clue",mode="clue")),
        colorless=2,
    )
    clue_targets={
        _tutor_action_from_trace(a)[1]
        for a in repurposing_bay_actions(clue)
        if _tutor_action_from_trace(a)[0]=="Repurposing Bay"
    }
    assert clue_targets=={"Aether Spellbomb"}
    chrome_copy=State(
        turn=3,library=("The One Ring","Battered Golem","Island"),hand=(),
        battlefield=(
            Perm("Repurposing Bay"),
            Perm("Battered Golem",mode="chrome_copy",sick=False),
        ),colorless=2,
    )
    assert bay_success(
        repurposing_bay_actions(chrome_copy),"The One Ring"
    )
    print("Token/copy mana-value accounting          PASS",flush=True)

    # Cage blocks a library creature while it remains, but sacrificing Cage as
    # Bay's cost removes that restriction before the search resolves.
    cage_stays=State(
        turn=3,library=("Battered Golem","Island"),hand=(),
        battlefield=(
            Perm("Repurposing Bay"),Perm("Sapphire Medallion"),
            Perm("Grafdigger's Cage"),
        ),colorless=2,
    )
    cage_stays_actions=repurposing_bay_actions(cage_stays)
    assert not any(
        a.graveyard==("Sapphire Medallion",)
        and _tutor_action_from_trace(a)[1]=="Battered Golem"
        for a in cage_stays_actions
    )
    cage_sac=State(
        turn=3,library=("Chrome Dome","Island"),hand=(),
        battlefield=(Perm("Repurposing Bay"),Perm("Grafdigger's Cage")),
        colorless=2,
    )
    cage_entry=bay_success(repurposing_bay_actions(cage_sac),"Chrome Dome")
    assert cage_entry.graveyard==("Grafdigger's Cage",)
    assert has(cage_entry,"Chrome Dome")
    print("Cage checked after sacrifice cost         PASS",flush=True)

    # Bay must finish its shuffle before the entered Well's scry trigger
    # resolves. Reconstruct that exact ordered transition as a canary.
    well=State(
        turn=3,
        library=(
            "Witching Well","Power Artifact","Sol Ring","Island","Force of Will",
        ),
        hand=(),battlefield=(
            Perm("Repurposing Bay"),Perm("Treasure",mode="treasure"),
        ),colorless=2,trace=("setup",),
    )
    well_result=bay_success(repurposing_bay_actions(well),"Witching Well")
    expected=pay(well,2,0)
    expected=update_perm(expected,0,tapped=True)
    expected=remove_perm(expected,1)
    lib=list(expected.library); lib.remove("Witching Well")
    expected=replace(expected,library=tuple(lib))
    expected=add_perm(expected,"Witching Well")
    expected=replace(
        expected,library=shuffled_library(expected,"bay:Witching Well")
    )
    expected=artifact_etb_triggers(expected,"Witching Well")
    assert well_result.library==expected.library
    assert any(
        line.startswith("Witching Well ETB: scry 2")
        for entry in well_result.trace
        for line in entry.splitlines()
    )
    assert well_result.trace[-1].splitlines()[0]==(
        "Repurposing Bay sacs Treasure -> Witching Well"
    )
    print("Shuffle-before-ETB-trigger ordering       PASS",flush=True)

    # Putting an artifact directly onto the battlefield is not casting it and
    # must not fire Uthros/Assistant/Gadgeteer/VFC cast triggers.
    direct=State(
        turn=3,library=("Battered Golem","Audit Draw","Island"),hand=(),
        battlefield=(
            Perm("Repurposing Bay"),Perm("Sapphire Medallion"),
            Perm("Uthros Research Craft"),Perm("Artificer's Assistant"),
            Perm("Forensic Gadgeteer"),Perm("Valley Floodcaller"),
        ),colorless=1,uthros_counters=3,
    )
    direct_result=bay_success(
        repurposing_bay_actions(direct),"Battered Golem"
    )
    assert direct_result.hand==() and direct_result.uthros_counters==3
    assert direct_result.vfc_pumps==0 and not direct_result.spell_cast_this_turn
    assert count_bf(direct_result,"Clue")==0
    print("Direct-to-battlefield is not a cast       PASS",flush=True)

    # Production timing: Bay is reachable in an ordinary main-phase state but
    # not while Remora upkeep or the Saga-III stack window is pending.
    assert any(
        a.trace[-1].splitlines()[0].startswith("Repurposing Bay")
        for a in legal_actions(base)
    )
    upkeep=replace(
        base,battlefield=(
            Perm("Repurposing Bay"),Perm("Sapphire Medallion"),
            Perm("Mystic Remora"),
        ),remora_age=0,remora_upkeep_pending=True,
    )
    assert not any(
        a.trace[-1].splitlines()[0].startswith("Repurposing Bay")
        for a in legal_actions(upkeep)
    )
    saga=replace(
        base,battlefield=(
            Perm("Repurposing Bay"),Perm("Sapphire Medallion"),
            Perm("Urza's Saga",counters=3,mode="saga3"),
        ),saga3_pending=True,
    )
    assert not any(
        a.trace[-1].splitlines()[0].startswith("Repurposing Bay")
        for a in legal_actions(saga)
    )
    print("Sorcery-speed production gating           PASS",flush=True)

    # Both producers trigger on their own artifact entry (no "another"). With
    # Urza, an untapped producer legally taps before and after its trigger;
    # without Urza every controlled copy receives its own untap trigger.
    station=State(
        turn=3,library=(),hand=(),
        battlefield=(Perm(COMMANDER,sick=False),),
        urza=True,commander_in_command_zone=False,
    )
    station=add_perm(station,"Grinding Station")
    station=artifact_etb_triggers(station,"Grinding Station")
    sp=next(p for p in station.battlefield if p.name=="Grinding Station")
    assert station.blue==2 and sp.tapped and sp.producer_urza_ready
    golem=State(
        turn=3,library=(),hand=(),
        battlefield=(Perm(COMMANDER,sick=False),),
        urza=True,commander_in_command_zone=False,
    )
    golem=add_perm(golem,"Battered Golem",sick=True)
    golem=artifact_etb_triggers(golem,"Battered Golem")
    gp=next(p for p in golem.battlefield if p.name=="Battered Golem")
    assert golem.blue==2 and gp.tapped and gp.sick and gp.producer_urza_ready

    copies=State(
        turn=3,library=(),hand=(),battlefield=(
            Perm("Grinding Station",tapped=True),
            Perm("Grinding Station",tapped=True,mode="chrome_copy"),
            Perm("Battered Golem",tapped=True,sick=False),
            Perm("Battered Golem",tapped=True,sick=False,mode="chrome_copy"),
        ),
    )
    untapped=artifact_etb_triggers(copies,"Clue")
    assert all(not p.tapped for p in untapped.battlefield)
    multi_urza=replace(copies,urza=True)
    converted=artifact_etb_triggers(multi_urza,"Clue")
    assert converted.blue==4 and deferred_producer_blue(converted)==4
    assert all(p.tapped for p in converted.battlefield)

    # Native Station mill enumerates every legal artifact sacrifice in a live
    # state, including Station itself and an already-tapped artifact. Tokens
    # cease to exist rather than being placed in the graveyard.
    mill_state=State(
        turn=4,library=("Island","Sol Ring","Mana Vault","Tail"),hand=(),
        battlefield=(
            Perm("Grinding Station"),
            Perm("Welding Jar",tapped=True),
            Perm("Clue",mode="clue"),
        ),
        chip_attached=True,
    )
    mills=producer_native_actions(mill_state)
    self_mill=next(a for a in mills if a.trace[-1].startswith("Grinding Station sacs Grinding Station"))
    jar_mill=next(a for a in mills if a.trace[-1].startswith("Grinding Station sacs Welding Jar"))
    clue_mill=next(a for a in mills if a.trace[-1].startswith("Grinding Station sacs Clue"))
    assert not has(self_mill,"Grinding Station") and "Grinding Station" in self_mill.graveyard
    assert has(jar_mill,"Grinding Station") and "Welding Jar" in jar_mill.graveyard
    assert "Clue" not in clue_mill.graveyard

    # The deferred post-trigger Urza tap remains optional: the free pre-trigger
    # U can cast Knack while Golem stays untapped to use the granted ability.
    knack_ready=State(
        turn=4,library=(),hand=("Banishing Knack",),
        battlefield=(Perm(COMMANDER,sick=False),Perm("Battered Golem",sick=False)),
        urza=True,commander_in_command_zone=False,
    )
    knack_ready=artifact_etb_triggers(knack_ready,"Clue")
    assert knack_ready.blue==2 and deferred_producer_blue(knack_ready)==1
    granted=next(
        a for a in knack_bounce_actions(knack_ready)
        if a.trace[-1].startswith("cast Banishing Knack targeting Battered Golem")
    )
    granted_golem=next(p for p in granted.battlefield if p.name=="Battered Golem")
    assert granted_golem.tapped and granted_golem.knack_granted and granted_golem.producer_urza_ready
    assert granted.blue==1
    assert any(
        a.trace[-1].startswith("Knack/Helix target Battered Golem bounces our ")
        for a in knack_bounce_actions(granted)
    )
    print("Producer self-entry/native-choice sanity PASS",flush=True)
    print("\nBAY / PRODUCER SMOKE: ALL PASS",flush=True)


def run_mulligan_smoke():
    """Fast orchestration regressions for Commander London Oracle stages."""
    global search_hand
    print("\n=== ORACLE MULLIGAN CORRECTNESS SMOKE ===",flush=True)

    legacy=(("7A",0),("7B",0),("6",1),("5",2),("4",3))
    assert oracle_mulligan_stages()==legacy
    assert oracle_mulligan_stages(4)==legacy
    assert oracle_mulligan_stages(3)==legacy+(("3",4),)
    print("Shared stage specification             PASS",flush=True)

    synthetic=[f"C{i:02d}" for i in range(99)]
    _,deals4=oracle_mulligan_deals(20260821,synthetic,4)
    _,deals3=oracle_mulligan_deals(20260821,synthetic,3)
    expected_legacy=(
        ("C63","C70","C30","C50","C64","C15","C12"),
        ("C43","C06","C63","C26","C72","C29","C30"),
        ("C37","C93","C54","C86","C69","C14","C45"),
        ("C38","C83","C93","C95","C42","C50","C63"),
        ("C59","C36","C35","C74","C46","C39","C27"),
    )
    assert tuple(tuple(d[:7]) for _,_,d in deals4)==expected_legacy
    assert tuple(tuple(d[:7]) for _,_,d in deals3[:5])==expected_legacy
    assert tuple(deals3[5][2][:7])==(
        "C43","C93","C17","C63","C21","C57","C70"
    )
    print("Legacy stage shuffle sequence          PASS",flush=True)

    seven=list(deals3[-1][2][:7])
    raw=bottom_candidates(seven,4,cap=math.comb(7,4))
    admitted=bottom_candidates(seven,4,cap=4)
    assert math.comb(7,4)==35 and len(raw)==35
    assert len(admitted)==4 and len({tuple(x) for x in admitted})==4
    assert all(len(x)==4 for x in admitted)
    print("Keep-3 bottom combinations             PASS | raw=35 admitted=4",flush=True)

    bottom=admitted[0]
    hand,library=london_opening_zones(deals3[-1][2],3,bottom)
    assert len(hand)==3 and len(bottom)==4
    assert list(library[-4:])==bottom
    assert Counter(hand)+Counter(bottom)==Counter(seven)
    assert Counter(hand)+Counter(library)==Counter(deals3[-1][2])
    print("Fresh seven + bottom four              PASS | legal keep=3",flush=True)

    # Both production paths must depend on the same deal/stage generator.
    assert "oracle_mulligan_deals" in oracle_game.__code__.co_names
    assert "oracle_mulligan_deals" in profile_oracle_seed.__code__.co_names
    assert "london_opening_zones" in search_hand.__code__.co_names
    assert "london_opening_zones" in profile_search_hand.__code__.co_names
    print("Production/profiler stage source       PASS | shared",flush=True)

    provenance=report_provenance(
        "mulligan-smoke",
        OracleSearchConfig(6,300,100,60,4,3),
        seed_provenance(20260821,5),
        synthetic,
        {"worker_count":1,"parallelism":"sequential"},
    )
    assert provenance["source"]["solver_sha256"]
    assert provenance["source"]["commit_hash"] or provenance["source"]["git_error"]
    assert provenance["search"]["mulligan_stages"][-1]["keep_size"]==3
    assert provenance["seeds"]["last"]==20260825
    assert provenance["environment"]["python_hash_seed"]==(
        os.environ.get("PYTHONHASHSEED") or None
    )
    if not os.environ.get("PYTHONHASHSEED"):
        assert provenance["warnings"]
    print("Reproducibility provenance schema      PASS",flush=True)

    real_search_hand=search_hand

    def exercise_stage_tie(wanted_turns):
        global search_hand
        calls=[]

        def stub_search_hand(deck_order,keep_n,bottom,max_turn=7,**kwargs):
            calls.append((keep_n,max_turn,tuple(bottom)))
            wanted=wanted_turns.get(keep_n)
            turn=wanted if wanted is not None and wanted<=max_turn else None
            family=f"keep-{keep_n}" if turn is not None else ""
            trace=("cast Urza",family) if turn is not None else ()
            final_hand=tuple(deck_order[:keep_n])
            return turn,family,trace,1,(1 if turn is not None else 0),(),final_hand,1

        search_hand=stub_search_hand
        try:
            return oracle_game(
                20260821,synthetic,max_turn=4,beam=1,depth=1,
                min_keep=3,bottom_cap=4,
            ),calls
        finally:
            search_hand=real_search_hand

    strict,calls=exercise_stage_tie({4:4,3:3})
    assert strict["win_turn"]==3 and strict["family"]=="keep-3"
    assert strict["mulligan_stage"]==5 and strict["keep_size"]==3
    assert len(strict["bottom"])==4 and len(strict["kept_hand"])==3
    assert Counter(strict["opening7"])==Counter(strict["bottom"])+Counter(strict["kept_hand"])
    assert any(keep_n==3 and horizon==3 for keep_n,horizon,_ in calls)
    print("Strictly earlier keep-3 selection      PASS",flush=True)

    tied,calls=exercise_stage_tie({4:3,3:3})
    assert tied["win_turn"]==3 and tied["family"]=="keep-4"
    assert tied["mulligan_stage"]==4 and tied["keep_size"]==4
    assert any(keep_n==3 and horizon==2 for keep_n,horizon,_ in calls)
    assert oracle_stage_selection_key(4,3)<oracle_stage_selection_key(5,3)
    print("Equal-turn earlier-stage tie-break     PASS",flush=True)
    print("\nMULLIGAN SMOKE: ALL PASS",flush=True)


def run_worker_config_smoke():
    """Exercise the real production worker across an explicit spawn boundary."""
    print("\n=== SPAWNED WORKER CONFIGURATION SMOKE ===",flush=True)
    config=OracleSearchConfig(
        max_turn=0,beam=17,depth=19,action_cap=23,bottom_cap=2,min_keep=3
    )
    job=OracleWorkerJob(seed=12345,deck=[],config=config)
    ctx=mp.get_context("spawn")
    pool=ctx.Pool(1,initializer=worker_process_initializer)
    try:
        result=pool.apply_async(worker,(job,)).get(timeout=20)
        pool.close()
        pool.join()
    except BaseException:
        pool.terminate()
        pool.join()
        raise

    assert not result.get("_error"),result.get("_error")
    assert result["_worker_pid"]!=os.getpid()
    assert result["_worker_search_config"]==search_config_payload(config)
    assert result["_oracle_search_config"]==search_config_payload(config)
    assert result["_oracle_mulligan_stage_count"]==6
    assert result["_worker_effective_caps"]=={
        "action_cap":23,"bottom_cap":2,
    }
    assert result["_worker_python_hash_seed"]==os.environ.get("PYTHONHASHSEED")
    assert result["_worker_search_config"]["mulligan_stages"][-1]=={
        "label":"3","keep_size":3,"bottom_count":4,
    }
    print(
        "Spawned worker received turns=0 beam=17 depth=19 "
        "action_cap=23 bottom_cap=2 min_keep=3",
        flush=True,
    )
    print("WORKER CONFIG SMOKE: ALL PASS",flush=True)


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
    ap.add_argument("--remora-smoke",action="store_true",help="Run Mystic Remora cumulative-upkeep regressions")
    ap.add_argument("--draw-trace-smoke",action="store_true",help="Run named library-draw trace regressions")
    ap.add_argument("--bounce-smoke",action="store_true",help="Run bounce legality and Remora-response regressions")
    ap.add_argument("--bay-smoke",action="store_true",help="Run Repurposing Bay and producer-ETB regressions")
    ap.add_argument("--mulligan-smoke",action="store_true",help="Run Oracle London mulligan-stage and keep-3 regressions")
    ap.add_argument("--worker-config-smoke",action="store_true",help="Verify search parameters cross a spawned-worker boundary")
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
    ap.add_argument("--min-keep",type=int,choices=(3,4),default=4,help="lowest Oracle London keep size (default: 4)")
    args=ap.parse_args()
    # Cache the exact on-disk source/repository identity before any search begins.
    solver_source_provenance()
    signal.signal(signal.SIGINT,parent_interrupt_handler)
    if hasattr(signal,'SIGBREAK'):
        try:
            signal.signal(signal.SIGBREAK,parent_interrupt_handler)
        except Exception:
            pass
    global ACTION_CAP, BOTTOM_CAP
    ACTION_CAP=args.action_cap; BOTTOM_CAP=args.bottom_cap
    warn_if_unset_python_hash_seed()
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
    if args.remora_smoke:
        run_remora_smoke()
        return
    if args.draw_trace_smoke:
        run_draw_trace_smoke()
        return
    if args.bounce_smoke:
        run_bounce_smoke()
        return
    if args.bay_smoke:
        run_bay_smoke()
        return
    if args.mulligan_smoke:
        run_mulligan_smoke()
        return
    if args.worker_config_smoke:
        run_worker_config_smoke()
        return
    deck=load_deck(Path(args.deck))
    if args.cap_audit>0:
        run_cap_audit(
            deck,args.seed,args.cap_audit,args.turns,args.beam,args.depth,
            args.search_progress_seconds,args.min_keep,args.bottom_cap,
        )
        return
    if args.tutor_cap_audit>0:
        run_tutor_cap_audit(
            deck,args.seed,args.tutor_cap_audit,args.turns,args.beam,args.depth,
            args.search_progress_seconds,args.min_keep,args.bottom_cap,
        )
        return
    if args.family_smoke>0:
        run_family_smoke(
            deck,args.seed,args.family_smoke,args.turns,args.beam,args.depth,
            args.search_progress_seconds,args.min_keep,args.bottom_cap,
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
            min_keep=args.min_keep,
            bottom_cap=args.bottom_cap,
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
            beam=args.beam,depth=args.depth,bottom_cap=args.bottom_cap,
            min_keep=args.min_keep,
        )
        return
    if args.profile_one:
        print(f"Profiling one opening candidate for seed={args.seed}",flush=True)
        profile_config=OracleSearchConfig(
            args.profile_turns,args.beam,args.depth,args.action_cap,
            args.bottom_cap,args.min_keep,
        )
        print(
            "provenance="+json.dumps(
                report_provenance(
                    "profile-one",profile_config,seed_provenance(args.seed),deck,
                    {"worker_count":1,"parallelism":"sequential"},
                ),
                sort_keys=True,
            ),
            flush=True,
        )
        profile_seed(args.seed,deck,args.profile_turns,args.beam,args.depth)
        return
    seeds=[args.seed+i for i in range(args.runs)]
    normal_config=OracleSearchConfig(
        args.turns,args.beam,args.depth,args.action_cap,args.bottom_cap,args.min_keep
    )
    jobs=[
        OracleWorkerJob(sd,deck,normal_config,args.verbose_workers)
        for sd in seeds
    ]
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
        f"turns={args.turns}, beam={args.beam}, action_cap={ACTION_CAP}, "
        f"bottom_cap={BOTTOM_CAP}, min_keep={args.min_keep}, "
        f"depth={args.depth}, seed={args.seed}",
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
                    pending[ar]=job.seed

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
        write_partial_checkpoint(out,results,args,deck,"KeyboardInterrupt / Ctrl+C")
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
    expected_worker_config=search_config_payload(normal_config)
    worker_config_mismatch_seeds=[
        r["seed"] for r in results
        if not r.get("_error") and r.get("_oracle_search_config")!=expected_worker_config
    ]
    worker_hash_seeds=sorted({
        r.get("_worker_python_hash_seed") for r in results
        if "_worker_python_hash_seed" in r
    },key=lambda value:"" if value is None else str(value))
    summary={"runs":args.runs,"completed":len(results),"errors":error_count,
             "beam":args.beam,"depth":args.depth,"action_cap":ACTION_CAP,
             "bottom_cap":BOTTOM_CAP,"min_keep":args.min_keep,"seed":args.seed,
             "provenance":report_provenance(
                 "normal-run",normal_config,seed_provenance(args.seed,args.runs),deck,
                 {
                     "worker_count":args.workers,
                     "parallelism":"sequential" if args.workers==1 else "multiprocessing",
                 },
             ),
             "turns":[{"turn":t,"exact":e,"cumulative":c,"cumulative_pct":p,"ci95_halfwidth_pct":ci}
                      for t,e,c,p,ci in rows],
             "families":dict(fam),"keep_sizes":dict(mull),
             "urza_cast_turns":dict(urza_turns),
             "interaction_seen_mean":sum(interaction_counts)/len(interaction_counts) if interaction_counts else 0,
             "interaction_seen_distribution":dict(Counter(interaction_counts)),
             "interaction_card_frequency":dict(interaction_cards),
             "worker_config_mismatch_seeds":worker_config_mismatch_seeds,
             "worker_python_hash_seeds":worker_hash_seeds,
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
