"""DACK simulator v0.76 — exact current 99 frozen for the 2026-10-02 N=4096 baseline.

Starts from the validated v0.75 current-99 engine and changes only the three current-list
differences that were adopted after the N=1024 benchmark:
  Homeward Path -> Mouth of Ronom
  Manifold Key -> Giant's Boulder
  13 Plains -> 13 Snow-Covered Plains

Prospective KCI/Bucknard/Kozilek's Command changes are intentionally NOT included.
"""
from dataclasses import replace
import dack_v075_current99 as v

# Validate the exact inherited v0.75 artifact semantics before mutating its deck globals.
assert v.selftest()
d=v.d

CURRENT_DECK = [
'Ancient Den','Ancient Tomb','Arcane Signet','Basalt Monolith','Blast Zone',
'Boonweaver Giant','Bound by Moonsilver','Brainstone','Campfire','Candelabra of Tawnos',
'Cavern of Souls','Chains of Custody','Charitable Levy','Chrome Mox','City of Traitors',
'Coalition Relic','Command Beacon','Crystal Vein','Deafening Silence','Defense Grid',
'Disruptor Flute','Eiganjo, Seat of the Empire',"Emeria's Call",'Enlightened Tutor',
'Everflowing Chalice','Expedition Map','Fellwar Stone','Floating Shield','Gemstone Caverns',
"Giant's Boulder",'Gift of Immortality','Gleaming Splendor','Great Hall of the Citadel',
'Grim Monolith','Idolized','Implements of Sacrifice',"Inventors' Fair",'Jeweled Amulet',
"Lion's Eye Diamond",'Liquimetal Torque','Lotus Petal','Mana Vault','Mantle of the Ancients',
'March of Otherworldly Light','Mind Stone','Minimus Containment',"Mishra's Workshop",
'Moonsilver Key','Mouth of Ronom','Mox Diamond','Mox Opal',"Orim's Chant",'Paladin Class',
'Path to Exile','Pearl Medallion','Pentarch Ward','Petrified Hamlet',
'Snow-Covered Plains','Snow-Covered Plains','Snow-Covered Plains','Snow-Covered Plains',
'Snow-Covered Plains','Snow-Covered Plains','Snow-Covered Plains','Snow-Covered Plains',
'Snow-Covered Plains','Snow-Covered Plains','Snow-Covered Plains','Snow-Covered Plains',
'Snow-Covered Plains',
'Portable Hole','Preston, the Vanisher','Prismatic Lens','Razorgrass Ambush','Remote Farm',
'Roaming Throne','Ruins of Trokair','Scroll Rack',"Shardmage's Rescue",'Sheltered by Ghosts',
'Silence','Sol Ring','Static Prison','Super State','Swords to Plowshares',
'Talon Gates of Madara','Tezzeret, Cruel Captain','The Mind Stone','The Mycosynth Gardens',
'Thorn of Amethyst','Tooth of Ramos','Touch the Spirit Realm','Trinisphere',
'Twinblade Blessing','Untaidake, the Cloud Keeper',"Urza's Cave","Urza's Saga",
'Vexing Bauble','Void Mirror'
]
assert len(CURRENT_DECK)==99
assert CURRENT_DECK.count("Snow-Covered Plains")==13
d.DECK=CURRENT_DECK

# Register new current-list names in exact cache IDs.
for _card in CURRENT_DECK:
    if _card not in d.CARD_ID:
        _nid=max(d.CARD_ID.values(),default=-1)+1
        d.CARD_ID[_card]=_nid
        d.ID_CARD[_nid]=_card

# Exact current land classification.
d.LANDS=frozenset(set(d.LANDS)|{"Snow-Covered Plains","Mouth of Ronom"})
d.WHITE_LANDS=frozenset(set(d.WHITE_LANDS)|{"Snow-Covered Plains"})
d.GUARANTEED_WHITE_LANDS=frozenset(set(d.GUARANTEED_WHITE_LANDS)|{"Snow-Covered Plains"})
d.LAND_TUTOR_TARGETS=tuple(dict.fromkeys(tuple(d.LAND_TUTOR_TARGETS)+("Snow-Covered Plains","Mouth of Ronom")))

# Keep the historical deterministic land-tutor heuristic exactly equivalent after Plains -> Snow-Covered Plains.
def land_tutor_choice(s,to_battlefield_tapped=False):
    avail=set(s.library)
    white_now=s.w+s.any+s.restricted_dack_white
    white_sources=sum(x in {
        "Snow-Covered Plains","Ancient Den","Eiganjo, Seat of the Empire","Shefet Dunes",
        "City of Brass","Mana Confluence","Gemstone Mine","Starting Town","Tarnished Citadel"
    } for x in s.hand)
    if white_now+white_sources<2:
        for x in ("Ancient Den","Snow-Covered Plains","City of Brass","Mana Confluence",
                  "Gemstone Mine","Starting Town","Shefet Dunes"):
            if x in avail: return x
    for x in ("Ancient Tomb","City of Traitors","Crystal Vein","Remote Farm","Ruins of Trokair",
              "Urza's Saga","The Mycosynth Gardens","Ancient Den","Snow-Covered Plains"):
        if x in avail: return x
    return next((x for x in d.LAND_TUTOR_TARGETS if x in avail),None)
d.land_tutor_choice=land_tutor_choice

def _dedupe(states):
    seen=set(); out=[]
    for q in states:
        k=d.key(q)
        if k not in seen:
            seen.add(k); out.append(q)
    return out

# Mouth of Ronom — T: add C. Its removal ability is irrelevant to this goldfish objective.
_old_tap=d.tap_mana_actions
def tap_mana_actions(s):
    out=list(_old_tap(s))
    for i,p in enumerate(s.battlefield):
        if d.effective_name(p)=="Mouth of Ronom" and not p.tapped:
            bf=list(s.battlefield); bf[i]=replace(p,tapped=True)
            out.append(replace(s,battlefield=tuple(bf),c=s.c+1))
    return _dedupe(out)
d.tap_mana_actions=tap_mana_actions

# Moonsilver Key can search a basic Snow-Covered Plains just as it searched Plains.
_old_v03=d.v03_actions
def v03_actions(s):
    out=list(_old_v03(s))
    if any(x.name=="Moonsilver Key" and not x.tapped for x in s.battlefield):
        for paid in d.pay_options(s,1):
            ki=next((j for j,x in enumerate(paid.battlefield)
                     if x.name=="Moonsilver Key" and not x.tapped),None)
            if ki is None or "Snow-Covered Plains" not in paid.library:
                continue
            lib=list(paid.library); lib.remove("Snow-Covered Plains")
            bf=list(paid.battlefield); bf.pop(ki)
            out.append(replace(
                paid,battlefield=tuple(bf),library=d.shuffled_unknown(lib),
                hand=d.sort_hand(paid.hand+("Snow-Covered Plains",)),
                grave=paid.grave+("Moonsilver Key",)
            ))
    return _dedupe(out)
d.v03_actions=v03_actions

# Charitable Levy's modeled Plains search must find the current basic Snow-Covered Plains.
# The inherited wrapper has already drawn the card when the third counter sacrifices Levy;
# this patch supplies the missing current basic land, tapped, after that draw.
_old_cast=d.cast_actions
def cast_actions(s):
    raw=list(_old_cast(s))
    ready=any(d.effective_name(x)=="Charitable Levy" and x.counters>=2 for x in s.battlefield)
    if not ready:
        return raw
    out=[]
    old_grave_n=s.grave.count("Charitable Levy")
    for q in raw:
        qq=q
        if (q.grave.count("Charitable Levy")>old_grave_n
                and "Snow-Covered Plains" in q.library):
            lib=list(q.library); lib.remove("Snow-Covered Plains")
            qq=replace(
                q,
                battlefield=q.battlefield+(d.Perm("Snow-Covered Plains",True,0,q.turn),),
                library=d.shuffled_unknown(lib)
            )
        out.append(qq)
    return _dedupe(out)
d.cast_actions=cast_actions

def clear_caches():
    v.clear_caches()
    for name in ("_WIN_CACHE","_KEEP_SEAT_CACHE","_WEIGHTED_SEAT_CACHE",
                 "_SHUFFLE_CACHE","_PAY_CACHE","_DIST_CACHE","_FUTURE_SAMPLE_CACHE",
                 "_KEEP_CACHE"):
        obj=getattr(d,name,None)
        if hasattr(obj,"clear"):
            obj.clear()
clear_caches()

def selftest():
    # Inherited v0.75 artifact semantics were validated at module import before deck mutation.
    assert len(d.DECK)==99 and d.DECK.count("Snow-Covered Plains")==13
    assert "Homeward Path" not in d.DECK and "Manifold Key" not in d.DECK
    assert "Giant's Boulder" in d.DECK and "Mouth of Ronom" in d.DECK
    assert "Krark-Clan Ironworks" not in d.DECK and "Bucknard's Everfull Purse" not in d.DECK
    assert "Kozilek's Command" not in d.DECK

    # New current lands are playable and produce the intended mana.
    s=d.State(1,("Snow-Covered Plains",),())
    ps=d.play_land_actions(s)
    assert ps and any(q.battlefield and q.battlefield[-1].name=="Snow-Covered Plains" for q in ps)
    snow=next(q for q in ps if q.battlefield[-1].name=="Snow-Covered Plains")
    assert any(q.w>=1 for q in d.tap_mana_actions(snow))

    s=d.State(1,(),(),(d.Perm("Mouth of Ronom"),))
    assert any(q.c>=1 for q in d.tap_mana_actions(s))

    # Boulder remains the audited one-mana scry/filter engine.
    assert d.COSTS["Giant's Boulder"]==(1,0,0)
    base_lib=("Boonweaver Giant","Mana Vault","Snow-Covered Plains","Sol Ring")
    s=d.State(1,("Giant's Boulder",),base_lib,c=1)
    outs=[q for q in d.cast_actions(s)
          if any(d.effective_name(p)=="Giant's Boulder" for p in q.battlefield)]
    assert outs and len({q.library for q in outs})>=6
    s=d.State(1,(),(),(d.Perm("Giant's Boulder"),),c=1)
    assert any(q.any>=1 for q in d.special_actions(s))

    # Land tutor heuristic and Moonsilver both recognize the current basic.
    s=d.State(1,(),("Snow-Covered Plains","Mouth of Ronom"))
    assert d.land_tutor_choice(s)=="Snow-Covered Plains"
    assert d.score(d.State(1,(),(),(d.Perm("Snow-Covered Plains"),)))==d.score(d.State(1,(),(),(d.Perm("Plains"),)))

    # Moonsilver can fetch the current basic.
    s=d.State(1,(),("Snow-Covered Plains",),(d.Perm("Moonsilver Key"),),c=1)
    assert any("Snow-Covered Plains" in q.hand for q in d.v03_actions(s))

    # Dack exact WW+4 and combo-creature contamination invariants remain intact.
    lib=tuple(d.COMBO_CREATURES)
    assert not d.can_cast_dack(d.State(1,(),lib,w=1,c=5))
    assert d.can_cast_dack(d.State(1,(),lib,w=2,c=4))
    contaminated=d.State(2,("Boonweaver Giant",),
        tuple(x for x in d.COMBO_CREATURES if x!="Boonweaver Giant"),(),w=3,c=3)
    assert not d.can_cast_dack(contaminated)
    return True

if __name__=="__main__":
    print("selftest:", "PASS" if selftest() else "FAIL")
