#!/usr/bin/env python3
"""Exact user-provided October 16 Boonweaver Dack T1-T3 goldfish benchmark.

Inherits the tested v0.77 deployment solver and v0.78 Staff/Tithe/
Battlefront/Fomori extensions, but RESTORES the Boonweaver library-only
combo requirement, aura London preference, and no-creature-imprint policy.

Benchmarks two deck variants using a *matched* free multiplayer London
mulligan, lambda=.5 utility and seeded beam search. This reports legal
Dack deployment conditional on combo creatures remaining in the library,
NOT a verified full ETB-chain win or a multiplayer match win rate.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from dataclasses import replace
import gzip
import hashlib
import json
from pathlib import Path
import random
import time

import dack_flicker_v078 as newer
import dack_full_deck_accel_n512_batch as batch

d = newer.d
m = batch.m
assert d is m.d

DECK_TEXT = """1 Ancient Den
1 Ancient Tomb
1 Arcane Signet
1 Basalt Monolith
1 Blast Zone
1 Boonweaver Giant
1 Bound by Moonsilver
1 Brainstone
1 Cavern of Souls
1 Charitable Levy
1 Chrome Mox
1 City of Traitors
1 Command Beacon
1 Crystal Vein
1 Deafening Silence
1 Defense Grid
1 Disruptor Flute
1 Eiganjo, Seat of the Empire
1 Eldrazi Confluence
1 Emergence Zone
1 Emeria's Call
1 Enlightened Tutor
1 Erode
1 Everflowing Chalice
1 Expedition Map
1 Feather of Flight
1 Fellwar Stone
1 Floating Shield
1 Fomori Vault
1 Gemstone Caverns
1 Gift of Immortality
1 Gleaming Splendor
1 Great Hall of the Citadel
1 Grim Monolith
1 Hardlight Containment
1 Homeward Path
1 Idolized
1 Implements of Sacrifice
1 Jeweled Amulet
1 Krark-Clan Ironworks
1 Lion's Eye Diamond
1 Lotus Petal
1 Lunarch Mantle
1 Mana Tithe
1 Mana Vault
1 Mantle of the Ancients
1 March of Otherworldly Light
1 Mind Stone
1 Minimus Containment
1 Mishra's Workshop
1 Moonsilver Key
1 Mox Diamond
1 Mox Opal
1 Orim's Chant
1 Paladin Class
1 Petrified Hamlet
10 Plains
1 Portable Hole
1 Preston, the Vanisher
1 Prismatic Lens
1 Razorgrass Ambush
1 Remote Farm
1 Roaming Throne
1 Ruins of Trokair
1 Scroll Rack
1 Sheltered by Ghosts
1 Silence
1 Smothering Tithe
1 Sol Ring
1 Soul Partition
1 Staff of Compleation
1 Static Prison
1 Super State
1 Talon Gates of Madara
1 Tezzeret, Cruel Captain
1 The Mind Stone
1 The Mycosynth Gardens
1 Thorn of Amethyst
1 Tooth of Ramos
1 Touch the Spirit Realm
1 Trinisphere
1 Twinblade Blessing
1 United Battlefront
1 Untaidake, the Cloud Keeper
1 Unwanted Remake
1 Urza's Cave
1 Urza's Saga
1 Vexing Bauble
1 Void Mirror
1 World Map"""
COMMANDER = "Dack Fayden, Helping Hand"
COMBO = frozenset(("Boonweaver Giant", "Preston, the Vanisher", "Roaming Throne"))
PROTECTED_AURAS = frozenset((
    "Bound by Moonsilver", "Floating Shield", "Gift of Immortality",
    "Hardlight Containment", "Idolized", "Lunarch Mantle",
    "Mantle of the Ancients", "Minimus Containment", "Sheltered by Ghosts",
    "Super State", "Twinblade Blessing",
))
# Feather of Flight is an Aura cantrip. It requires a creature target.
# No creature can be cast before the commander in this focused goldfish.
NONCOMBO_AURAS = frozenset(("Feather of Flight",))

def parse(text):
    cards=[]
    for line in text.splitlines():
        if not line.strip():continue
        n,name=line.split(" ",1)
        cards.extend([name]*int(n))
    return tuple(cards)

CURRENT=parse(DECK_TEXT)
assert len(CURRENT)==99, len(CURRENT)
assert CURRENT.count("Plains")==10
assert len(set(CURRENT))==90
assert COMBO.issubset(CURRENT)
assert len(COMBO.intersection(CURRENT))==3
assert not {"Mana Crypt","Jeweled Lotus"}.intersection(CURRENT)

def legacy_deck():
    """Read the frozen Oct 10 Boonweaver baseline, not an approximate list."""
    tree=ast.parse(Path("dack_lotus_crypt_n1024.py").read_text())
    raw=next(ast.literal_eval(node.value) for node in tree.body
             if isinstance(node,ast.Assign)
             and any(isinstance(t,ast.Name) and t.id=="BASE_TEXT"
                     for t in node.targets))
    result=parse(raw)
    assert len(result)==99 and result.count("Snow-Covered Plains")==13
    assert COMBO.issubset(result)
    assert not {"Mana Crypt","Jeweled Lotus"}.intersection(result)
    return result

LEGACY=legacy_deck()
VARIANTS={"current":CURRENT,"oct10":LEGACY}
# Keep existing default (original Boonweaver) mulligan lambda and replay seeds.
batch.CONFIG.update({
    "engine":"v0.78-extensions-boonweaver-exact99-oct16",
    "policy":"free_multiplayer_London_v077_lambda_0.5_continuation_provisional",
    "max_turn":3,"gameplay_beam":240,"mulligan_eval_beam":60,
    "screen_samples":8,"refine_samples":16,
})
batch.build_deck=lambda variant:VARIANTS[variant]

# Restore core combo semantics removed by the flicker fork.
d.COMBO_CREATURES = COMBO
d.AURAS = frozenset(set(d.AURAS)|PROTECTED_AURAS|NONCOMBO_AURAS)
# White Chrome Mox imprint policy: preserve combo creatures and Auras, as
# in original Boonweaver runs. Explicitly include newly printed white cards.
WHITE_NONAURAS = frozenset((
    "Charitable Levy","Deafening Silence","Enlightened Tutor","Erode",
    "Gleaming Splendor","Mana Tithe","March of Otherworldly Light",
    "Orim's Chant","Paladin Class","Portable Hole","Silence",
    "Smothering Tithe","Soul Partition","Static Prison",
    "Touch the Spirit Realm","United Battlefront","Unwanted Remake",
    "Emeria's Call","Razorgrass Ambush",
))
WHITE_IMPRINTS=frozenset(set(d.MOX_SAFE)|WHITE_NONAURAS)
WHITE_IMPRINTS=frozenset(x for x in WHITE_IMPRINTS
                         if x not in COMBO and x not in d.AURAS)
newer.WHITE_IMPRINTS=WHITE_IMPRINTS
d.chrome_mox_allowed=lambda card:card in WHITE_IMPRINTS

# Add new exact identities before invoking any state/library hash.
for card in set(CURRENT)|set(LEGACY):
    if card not in d.CARD_ID:
        cid=max(d.CARD_ID.values(),default=-1)+1
        d.CARD_ID[card]=cid
        d.ID_CARD[cid]=card

# The new artifact card is a {1} artifact; all of its land searches are
# activated abilities. A fresh untapped noncreature artifact can activate.
d.COSTS["World Map"]=(1,0,0)
_original_is_artifact=d.is_artifact_perm
def is_artifact_perm(name):
    return name=="World Map" or _original_is_artifact(name)
d.is_artifact_perm=is_artifact_perm
d.RAMP_PROTECTED=frozenset(set(d.RAMP_PROTECTED)|{
    "World Map","Staff of Compleation","Smothering Tithe","United Battlefront"
})
# Battlefront puts nonland/noncreature permanents of MV<=3 into play.
# Existing v0.78 enumeration omitted these legacy Boonweaver artifacts.
newer.ELIGIBLE_BATTLEFRONT.update({
    "World Map","Implements of Sacrifice","Tooth of Ramos",
})
assert all(d.COSTS[x][0]<=3 for x in
           ("World Map","Implements of Sacrifice","Tooth of Ramos"))

# Restore the Boonweaver restriction explicitly at the public win check,
# guarding against future changes to legacy d.can_cast_dack.
_existing_dack_check=d.can_cast_dack
def can_cast_dack(s):
    if not COMBO.issubset(set(s.library)):
        return False
    # A Chapter-III tutor currently pending on the stack must resolve
    # before a sorcery-speed commander cast is possible.
    if any(p.name=="Urza's Saga" and p.aux=="SAGA3" for p in s.battlefield):
        return False
    return _existing_dack_check(s)
d.can_cast_dack=can_cast_dack

# World Map: {1},{T},sac to put a basic in hand, or {3},{T},sac for
# any land card in library. Search excludes exiled/grave cards, shuffles
# remaining library using the exact existing known/unknown-order routine.
_previous_utility=d.utility_actions
def utility_actions(s):
    out=list(_previous_utility(s))
    if not any(d.effective_name(p)=="World Map" and not p.tapped
               for p in s.battlefield):
        return out
    for cost,basic_only in ((1,True),(3,False)):
        for paid in d.pay_options(s,cost):
            i=next((i for i,p in enumerate(paid.battlefield)
                    if d.effective_name(p)=="World Map" and not p.tapped),None)
            if i is None:continue
            targets=sorted(set(c for c in paid.library
                               if c=="Plains" if basic_only)) if basic_only else [
                                   c for c in sorted(set(paid.library)) if c in d.LANDS
                               ]
            for name in targets:
                lib=list(paid.library);lib.remove(name)
                bf=list(paid.battlefield);source=bf.pop(i)
                out.append(replace(
                    paid,battlefield=tuple(bf),
                    hand=d.sort_hand(paid.hand+(name,)),
                    library=d.shuffled_unknown(lib),
                    grave=paid.grave+(source.name,)
                ))
    return m._dedupe(out)
d.utility_actions=utility_actions

# Staff of Compleation: {T}, pay 3 life: proliferate. The inherited v0.78
# layer models Staff's mana/draw/untap but not proliferate. Extend its
# *existing* life ledger; do not bypass the 40-life cap or reset past payments.
STAFF_LIFE3="__STAFF_PAID_LIFE_3__"
_base_staff_life_spent = newer.staff_life_spent
def staff_life_spent(s):
    return _base_staff_life_spent(s)+3*s.exile.count(STAFF_LIFE3)
newer.staff_life_spent=staff_life_spent

# A permanent may have loyalty counters (Tezzeret) or its named counter
# kind stored in .counters (Saga lore, Remote Farm depletion, Chalice charge,
# Jeweled Amulet charge, Coalition Relic charge, etc.). Choosing a permanent
# adds one of *each* kind already present, not a counter where there was none.
def proliferate_options(s):
    eligible=[
        i for i,p in enumerate(s.battlefield)
        if p.counters>0 or (p.name=="Tezzeret, Cruel Captain" and p.loyalty>0)
    ]
    out=[]
    # Early T1-T3 deck states ordinarily have few counters. Avoid an
    # unbounded 2^N action explosion in pathological states: selecting every
    # eligible permanent is legal, as is selecting any one; enumerate all
    # subsets when N<=8. This is a stated beam-search approximation above 8.
    masks=(range(1,1<<len(eligible)) if len(eligible)<=8 else
           [1<<i for i in range(len(eligible))]+[(1<<len(eligible))-1])
    for mask in masks:
        bf=list(s.battlefield)
        for bit,idx in enumerate(eligible):
            if not (mask>>bit)&1:continue
            p=bf[idx]
            newc=p.counters+(1 if p.counters>0 else 0)
            newloyalty=p.loyalty+(1 if p.name=="Tezzeret, Cruel Captain" and p.loyalty>0 else 0)
            aux=p.aux
            # Adding a third lore counter triggers Urza's Saga chapter III
            # immediately. The inherited saga_tutor_actions resolves the
            # search and sacrifices Saga; don't synthesize a free tutor.
            if p.name=="Urza's Saga" and p.counters<3<=newc:
                aux="SAGA3"
            bf[idx]=replace(p,counters=newc,loyalty=newloyalty,aux=aux)
        out.append(replace(s,battlefield=tuple(bf)))
    return out

_prev_special_actions=d.special_actions
def special_actions(s):
    out=list(_prev_special_actions(s))
    if not newer.staff_can_pay(s,3):
        return out
    for i,p in enumerate(s.battlefield):
        if d.effective_name(p)!="Staff of Compleation" or p.tapped:
            continue
        bf=list(s.battlefield)
        bf[i]=replace(p,tapped=True)
        paid=replace(s,battlefield=tuple(bf),
                     exile=s.exile+(STAFF_LIFE3,))
        out.extend(proliferate_options(paid))
    return m._dedupe(out)
d.special_actions=special_actions

# A proliferated Jeweled Amulet with two or more charge counters spends only
# one charge counter when tapped for mana. Legacy code set all charges to zero.
_prev_tap_actions=d.tap_mana_actions
def tap_mana_actions(s):
    raw=_prev_tap_actions(s)
    changed=[]
    for q in raw:
        for i,p in enumerate(s.battlefield):
            if (d.effective_name(p)!="Jeweled Amulet" or
                p.tapped or p.counters<=1 or
                len(q.battlefield)!=len(s.battlefield)):
                continue
            after=q.battlefield[i]
            if (after.name==p.name and after.tapped and after.counters==0):
                bf=list(q.battlefield)
                bf[i]=replace(after,counters=p.counters-1)
                q=replace(q,battlefield=tuple(bf))
        changed.append(q)
    return m._dedupe(changed)
d.tap_mana_actions=tap_mana_actions

def install(variant):
    deck=VARIANTS[variant]
    assert len(deck)==99
    m.set_deck(deck)
    return deck

def choose_hand_with_free(rng,seat):
    """One free mulligan at 7, then 7/6/.../1 London, with full bottoming.

    The continuation thresholds were fitted before the free mulligan,
    so this is an explicit provisional policy, not a recalibrated optimum.
    """
    stages=(7,7,6,5,4,3,2,1)
    audit=[]
    for stage,keep_n in enumerate(stages):
        cards=list(d.DECK)
        rng.shuffle(cards)
        seven,rest=cards[:7],cards[7:]
        raw,ev,struct,hand,bottom,unknown,_,refined = \
            batch.evaluate_keep(seven,keep_n,rest,seat)
        threshold=0.0 if keep_n==1 else batch.FROZEN_CONTINUATION[keep_n-1]
        accept=keep_n==1 or float(raw)>=threshold
        audit.append({"stage":stage,"keep_n":keep_n,
                      "utility":round(float(raw),5),
                      "threshold":float(threshold),
                      "kept":accept,"refined":bool(refined)})
        if accept:
            return d.State(1,tuple(hand),tuple(unknown)+tuple(bottom)),keep_n,audit
    raise RuntimeError("failed to keep terminal one")

def simulate(variant,gid,beam):
    seed=batch.CONFIG["seed_base"]+int(gid)*1000003
    m.set_trial_seed(seed)
    rng=random.Random(seed)
    seat=rng.randrange(4)
    state,keep_n,audit=choose_hand_with_free(rng,seat)
    win=d._win_turn_from_unknown_order(
        state.hand,state.library,seat,beam=beam,max_turn=3)
    return {"game_id":int(gid),"seed":int(seed),"seat":int(seat),
            "keep_n":int(keep_n),"free_mull_used":len(audit)>1,
            "win_turn":int(win or 0),"audit":audit}

def audit():
    assert len(CURRENT)==99 and len(LEGACY)==99
    assert len(set(CURRENT))==90
    assert all(x in d.CARD_ID for x in CURRENT)
    assert COMBO.issubset(d.COMBO_CREATURES)
    assert not any(d.chrome_mox_allowed(c) for c in COMBO|PROTECTED_AURAS)
    assert d.chrome_mox_allowed("United Battlefront")
    assert d.chrome_mox_allowed("Smothering Tithe")
    assert "World Map" in newer.ELIGIBLE_BATTLEFRONT
    assert d.is_artifact_perm("World Map")
    assert d.COSTS["World Map"]==(1,0,0)
    assert not d.is_artifact_perm("Smothering Tithe")
    assert d.COSTS["Smothering Tithe"]==(3,1,0)
    assert newer.BATTLEFRONT_COST==(3,1,0)
    assert d.COSTS["Staff of Compleation"]==(3,0,0)
    # Legal Dack requires all three combo creatures in the library.
    all3=tuple(sorted(COMBO))
    assert d.can_cast_dack(d.State(1,(),all3,w=2,c=4))
    assert not d.can_cast_dack(d.State(1,(),all3[1:],w=2,c=4))
    # Map can be cast normally (artifact with cost 1), and activated
    # using {1} and untapped Map; it cannot finance its own ability.
    s=d.State(1,("World Map",),all3+("Plains","Ancient Tomb"),c=1)
    assert any(any(p.name=="World Map" for p in q.battlefield)
               for q in d.cast_actions(s))
    s=d.State(1,(),all3+("Plains","Ancient Tomb"),
              (d.Perm("World Map"),),c=1)
    x=d.utility_actions(s)
    assert any("Plains" in q.hand and "World Map" in q.grave for q in x)
    assert not any("Ancient Tomb" in q.hand for q in x)
    x=d.utility_actions(replace(s,c=3))
    assert any("Ancient Tomb" in q.hand for q in x)
    # Staff proliferate must tap, pay 3 life, and may selectively place
    # exactly one additional counter on each chosen counter-bearing permanent.
    proof_lib=tuple(sorted(COMBO))+("Lion's Eye Diamond","Sol Ring")
    st=d.State(2,(),proof_lib,battlefield=(
        d.Perm("Staff of Compleation"),
        d.Perm("Urza's Saga",False,2),
        d.Perm("Remote Farm",False,2),
        d.Perm("Everflowing Chalice",False,1),
        d.Perm("Jeweled Amulet",False,1,aux="W"),
        d.Perm("Tezzeret, Cruel Captain",False,0,loyalty=4),
    ))
    pro=[q for q in d.special_actions(st)
         if STAFF_LIFE3 in q.exile]
    assert pro and all(q.battlefield[0].tapped for q in pro)
    assert all(newer.staff_life_spent(q)==3 for q in pro)
    # One target only, without accidentally proliferating other permanents.
    assert any(q.battlefield[1].counters==2 and q.battlefield[2].counters==3
               and q.battlefield[3].counters==1 and q.battlefield[5].loyalty==4
               for q in pro)
    # All targets, including Tezzeret loyalty and Saga Chapter III.
    allhit=[q for q in pro
            if q.battlefield[1].counters==3 and q.battlefield[1].aux=="SAGA3"
            and q.battlefield[2].counters==3
            and q.battlefield[3].counters==2
            and q.battlefield[4].counters==2
            and q.battlefield[5].loyalty==5]
    assert allhit
    assert not d.can_cast_dack(replace(allhit[0],w=2,c=4))
    resolved=[z for q in allhit for z in d.saga_tutor_actions(q)]
    assert any("Urza's Saga" not in [p.name for p in z.battlefield]
               and "Lion's Eye Diamond" in [p.name for p in z.battlefield]
               for z in resolved)
    # Remote Farm gains an extra usable depletion counter.
    rf=next(q for q in pro if q.battlefield[2].counters==3)
    rr=d.tap_mana_actions(rf)
    assert any(q.w==2 and q.battlefield[2].counters==2 for q in rr)
    # Chalice adds C equal to its *post-proliferation* counters.
    ec=next(q for q in pro if q.battlefield[3].counters==2)
    assert any(q.c==2 for q in d.tap_mana_actions(ec))
    # Proliferated Jeweled Amulet keeps its other charge after one tap.
    amulet=next(q for q in pro if q.battlefield[4].counters==2)
    assert any(q.w==1 and q.battlefield[4].counters==1
               for q in d.tap_mana_actions(amulet))
    # Ruins of Trokair has NO depletion counters to proliferate.
    r=d.State(2,(),(),battlefield=(d.Perm("Ruins of Trokair"),))
    assert not proliferate_options(r)
    # Old staff life expenses count toward the common budget.
    almost=d.State(2,(),proof_lib,
                   battlefield=(d.Perm("Staff of Compleation"),),
                   exile=(newer.STAFF_LIFE4,)*9)
    assert newer.staff_life_spent(almost)==36
    assert not newer.staff_can_pay(replace(almost,exile=almost.exile+(STAFF_LIFE3,)),3)
    assert not any(STAFF_LIFE3 in q.exile and q.exile!=almost.exile
                   for q in d.special_actions(replace(almost,exile=almost.exile+(STAFF_LIFE3,))))
    # 4-player Tithe contributes 3 Treasures, Splendor adds a separate 1.
    alone=d.State(2,(),(),battlefield=(d.Perm("Smothering Tithe"),))
    with_splendor=replace(alone,battlefield=alone.battlefield+(d.Perm("Gleaming Splendor"),))
    assert d.add_opponent_cycle_resources(alone).treasures==3
    assert d.add_opponent_cycle_resources(with_splendor).treasures==4
    assert len(VARIANTS)==2
    print("BOONWEAVER_EXACT99_STAFF_PROLIFERATE_AUDIT_PASS",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--variant",choices=tuple(VARIANTS),default="current")
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--games",type=int,default=2)
    p.add_argument("--beam",type=int,default=240)
    p.add_argument("--out",default="boonweaver_exact99.json.gz")
    args=p.parse_args()
    audit()
    if args.audit:return
    assert args.games>=1 and args.shard>=0 and args.beam>=1
    batch.CONFIG["gameplay_beam"]=args.beam
    deck=install(args.variant)
    start=time.time()
    rows=[]
    for i in range(args.games):
        gid=args.shard*args.games+i
        row=simulate(args.variant,gid,args.beam)
        rows.append(row)
        print(json.dumps({"variant":args.variant,"game_id":gid,
                          "win_turn":row["win_turn"],"keep_n":row["keep_n"]}),
              flush=True)
    counts=Counter(x["win_turn"] for x in rows)
    payload={
        "schema":"boonweaver_exact99_t1t3_oct16",
        "variant":args.variant,"deck_sha256":hashlib.sha256(
            "\n".join(deck).encode()).hexdigest(),
        "policy":batch.CONFIG["policy"],"lambda":0.5,
        "seed_base":batch.CONFIG["seed_base"],
        "seed_scheme":"seed_base + game_id * 1000003",
        "games":args.games,"shard":args.shard,"beam":args.beam,
        "counts":{str(k):int(v) for k,v in counts.items()},
        "elapsed_seconds":round(time.time()-start,3),
        "rules_scope":"Assumed Boonweaver win on legal Dack cast with three combo creatures in library; no opponents",
        "assumptions":[
            "one free initial London mulligan; legacy continuation thresholds not recalibrated",
            "Smothering Tithe yields three Treasures per full opponent cycle, unopposed",
            "World Map basic/all-land modes and Battlefront hits available",
            "Feather of Flight requires creature target and does not pre-cast without creatures",
            "full Dack ETB/aura infinite combo sequence not proven in deployment solver",
        ],
        "rows":rows,
    }
    with gzip.open(args.out,"wt",encoding="utf8") as fh:
        json.dump(payload,fh,separators=(",",":"))
    print("BOONWEAVER_EXACT99_SHARD_PASS",args.variant,args.games,
          dict(counts),flush=True)

if __name__=="__main__":
    main()
