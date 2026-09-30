"""DACK simulator v0.75 current-99 patch.

Imports the audited v0.74 engine and applies the exact 2026-09-29 current list:
Implements of Sacrifice + Mind Stone replace Coalition Flag + Darksteel Mutation.

The patch keeps the v0.74 search/mulligan machinery and adds exact speed-relevant
Oracle behavior for the two new artifacts, including Moonsilver Key and
Mycosynth Gardens interactions.
"""
from dataclasses import replace
import dack_v0740_oracle_mana_audit as d

CURRENT_DECK = [
'Ancient Den','Ancient Tomb','Arcane Signet','Basalt Monolith','Blast Zone',
'Boonweaver Giant','Bound by Moonsilver','Brainstone','Campfire','Candelabra of Tawnos',
'Cavern of Souls','Chains of Custody','Charitable Levy','Chrome Mox','City of Traitors',
'Coalition Relic','Command Beacon','Crystal Vein','Deafening Silence','Defense Grid',
'Disruptor Flute','Eiganjo, Seat of the Empire',"Emeria's Call",'Enlightened Tutor',
'Everflowing Chalice','Expedition Map','Fellwar Stone','Floating Shield','Gemstone Caverns',
'Gift of Immortality','Gleaming Splendor','Great Hall of the Citadel','Grim Monolith',
'Homeward Path','Idolized','Implements of Sacrifice',"Inventors' Fair",'Jeweled Amulet',
"Lion's Eye Diamond",'Liquimetal Torque','Lotus Petal','Mana Vault','Manifold Key',
'Mantle of the Ancients','March of Otherworldly Light','Mind Stone','Minimus Containment',
"Mishra's Workshop",'Moonsilver Key','Mox Diamond','Mox Opal',"Orim's Chant",'Paladin Class',
'Path to Exile','Pearl Medallion','Pentarch Ward','Petrified Hamlet',
'Plains','Plains','Plains','Plains','Plains','Plains','Plains','Plains','Plains','Plains','Plains','Plains','Plains',
'Portable Hole','Preston, the Vanisher','Prismatic Lens','Razorgrass Ambush','Remote Farm',
'Roaming Throne','Ruins of Trokair','Scroll Rack',"Shardmage's Rescue",'Sheltered by Ghosts',
'Silence','Sol Ring','Static Prison','Super State','Swords to Plowshares',
'Talon Gates of Madara','Tezzeret, Cruel Captain','The Mind Stone','The Mycosynth Gardens',
'Thorn of Amethyst','Tooth of Ramos','Touch the Spirit Realm','Trinisphere','Twinblade Blessing',
'Untaidake, the Cloud Keeper',"Urza's Cave","Urza's Saga",'Vexing Bauble','Void Mirror'
]
assert len(CURRENT_DECK) == 99
assert CURRENT_DECK.count("Plains") == 13
d.DECK = CURRENT_DECK

# Compact IDs are used in exact cache keys.
for _card in CURRENT_DECK:
    if _card not in d.CARD_ID:
        _nid=max(d.CARD_ID.values(),default=-1)+1
        d.CARD_ID[_card]=_nid
        d.ID_CARD[_nid]=_card

# Both new cards are ordinary {2} artifacts.
d.COSTS["Implements of Sacrifice"]=(2,0,0)
d.COSTS["Mind Stone"]=(2,0,0)
d.RAMP_PROTECTED=frozenset(set(d.RAMP_PROTECTED)|{"Implements of Sacrifice","Mind Stone"})
d.MOONSILVER_MANA_ARTIFACTS=frozenset(
    set(d.MOONSILVER_MANA_ARTIFACTS)|{"Implements of Sacrifice","Mind Stone"}
)

_v075_is_artifact_perm=d.is_artifact_perm
def is_artifact_perm(name):
    return name in {"Implements of Sacrifice","Mind Stone"} or _v075_is_artifact_perm(name)
d.is_artifact_perm=is_artifact_perm

_v075_tap_mana_actions=d.tap_mana_actions
def tap_mana_actions(s):
    out=list(_v075_tap_mana_actions(s))
    # Mind Stone — T: add C. Locate the physical/copy source by effective name.
    for i,p in enumerate(s.battlefield):
        if d.effective_name(p)=="Mind Stone" and not p.tapped:
            bf=list(s.battlefield); bf[i]=replace(p,tapped=True)
            out.append(replace(s,battlefield=tuple(bf),c=s.c+1))
    return _dedupe(out)
d.tap_mana_actions=tap_mana_actions

_v075_utility_actions=d.utility_actions
def utility_actions(s):
    out=list(_v075_utility_actions(s))

    # Mind Stone — {1}, T, sacrifice: draw a card.
    # The source must remain untapped after paying {1}; it cannot finance its own activation.
    for p in s.battlefield:
        if d.effective_name(p)!="Mind Stone" or p.tapped:
            continue
        for paid in d.pay_options(s,1):
            si=next((j for j,x in enumerate(paid.battlefield)
                     if d.effective_name(x)=="Mind Stone" and not x.tapped),None)
            if si is None:
                continue
            bf=list(paid.battlefield); source=bf.pop(si)
            q=replace(paid,battlefield=tuple(bf),grave=paid.grave+(source.name,))
            out.append(d.draw(q,1))

    # Implements of Sacrifice — {1}, T, sacrifice: add two mana of any one color.
    # For this mono-white Dack objective, one exact branch chooses white.  A second branch
    # represents a single nonwhite color as one flexible colored unit + one generic-only
    # unit; this preserves "same color" sunburst behavior for Pentad Prism (two nonwhite
    # mana alone count as one color, while W + that color count as two).
    for p in s.battlefield:
        if d.effective_name(p)!="Implements of Sacrifice" or p.tapped:
            continue
        for paid in d.pay_options(s,1):
            si=next((j for j,x in enumerate(paid.battlefield)
                     if d.effective_name(x)=="Implements of Sacrifice" and not x.tapped),None)
            if si is None:
                continue
            bf=list(paid.battlefield); source=bf.pop(si)
            base=replace(paid,battlefield=tuple(bf),grave=paid.grave+(source.name,))
            out.append(replace(base,w=base.w+2))
            out.append(replace(base,any=base.any+1,c=base.c+1))
    return _dedupe(out)
d.utility_actions=utility_actions

_v075_v03_actions=d.v03_actions
def v03_actions(s):
    out=list(_v075_v03_actions(s))
    # v0.74's Gardens copy table predates the two new artifacts. Both have mana value 2.
    if any(x.name=="The Mycosynth Gardens" and not x.tapped and not x.aux for x in s.battlefield):
        for target in s.battlefield:
            tn=d.effective_name(target)
            if tn not in {"Implements of Sacrifice","Mind Stone"}:
                continue
            for paid in d.pay_options(s,2):
                gi=next((j for j,x in enumerate(paid.battlefield)
                         if x.name=="The Mycosynth Gardens" and not x.tapped and not x.aux),None)
                if gi is None:
                    continue
                if not any(d.effective_name(x)==tn for j,x in enumerate(paid.battlefield) if j!=gi):
                    continue
                bf=list(paid.battlefield)
                bf[gi]=replace(bf[gi],tapped=True,aux="COPY:"+tn)
                out.append(replace(paid,battlefield=tuple(bf)))
    return _dedupe(out)
d.v03_actions=v03_actions

_v075_score=d.score
def score(s):
    z=_v075_score(s)
    # Preserve setup states that the older heuristic cannot recognize.
    for p in s.battlefield:
        n=d.effective_name(p)
        if n=="Mind Stone" and not p.tapped:
            z+=24
        elif n=="Implements of Sacrifice" and not p.tapped:
            z+=26
    return z
d.score=score

def _dedupe(states):
    seen=set(); out=[]
    for q in states:
        k=d.key(q)
        if k not in seen:
            seen.add(k); out.append(q)
    return out

def clear_caches():
    d.clear_v074_caches()
    for name in ("_DIST_CACHE","_FUTURE_SAMPLE_CACHE","_KEEP_CACHE"):
        obj=getattr(d,name,None)
        if hasattr(obj,"clear"):
            obj.clear()
clear_caches()

def selftest():
    assert len(d.DECK)==99 and d.DECK.count("Plains")==13
    assert "Implements of Sacrifice" in d.DECK and "Mind Stone" in d.DECK
    assert "Coalition Flag" not in d.DECK and "Darksteel Mutation" not in d.DECK
    assert d.COSTS["Mind Stone"]==(2,0,0)
    assert d.COSTS["Implements of Sacrifice"]==(2,0,0)
    assert d.is_artifact_perm("Mind Stone") and d.is_artifact_perm("Implements of Sacrifice")

    # Mind Stone mana and draw.
    s=d.State(1,(),("Plains",),(d.Perm("Mind Stone"),))
    assert any(q.c==1 and any(x.name=="Mind Stone" and x.tapped for x in q.battlefield)
               for q in d.tap_mana_actions(s))
    s=replace(s,c=1)
    drawouts=d.utility_actions(s)
    assert any("Plains" in q.hand and "Mind Stone" in q.grave for q in drawouts)

    # Implements cannot self-finance, but with {1} available produces two white.
    s=d.State(1,(),(),(d.Perm("Implements of Sacrifice"),))
    assert not any(q.w>=2 for q in d.utility_actions(s))
    s=replace(s,c=1)
    assert any(q.w>=2 and "Implements of Sacrifice" in q.grave for q in d.utility_actions(s))

    # Moonsilver recognizes both mana artifacts.
    assert {"Mind Stone","Implements of Sacrifice"} <= set(d.MOONSILVER_MANA_ARTIFACTS)

    # Gardens can copy either new artifact with two external mana.
    for target in ("Mind Stone","Implements of Sacrifice"):
        s=d.State(1,(),(),(d.Perm("The Mycosynth Gardens"),d.Perm(target)),c=2)
        assert any(any(x.aux=="COPY:"+target for x in q.battlefield) for q in d.v03_actions(s))
    return True

if __name__=="__main__":
    print("selftest:", "PASS" if selftest() else "FAIL")
