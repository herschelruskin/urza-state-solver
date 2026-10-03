#!/usr/bin/env python3
"""DACK v0.77 full-deck acceleration calibration layer.

Starts from the frozen v0.76 current-99 engine and adds the acceleration cards that
appeared in the historical N=256 ranking / later-computed table so they can be tested
as natural full-deck substitutions under the exact London mulligan policy.

This is still the focused T1-T3 Dack-deployment goldfish. Opponent-facing text is
ignored unless it changes our own deployment resources. Random die cards use a
deterministic per-game seed supplied by the batch runner.
"""
from dataclasses import replace
import hashlib
import dack_v076_current99_20261002 as v

assert v.selftest()
d=v.d
BASE_CURRENT_DECK=tuple(v.CURRENT_DECK)

GENERIC_A="Generic 2C Rock"
GENERIC_B="Generic 2C Rock B"

PROSPECTS=(
    "Helm of Awakening","Krark-Clan Ironworks","Inspiring Statuary","Marble Diamond",
    "Sonic Screwdriver","Urza's Incubator","Worn Powerstone","Chromatic Lantern",
    "Honor-Worn Shaku","Component Pouch","Oketra's Monument","Cloud Key",
    "Pentad Prism","Thran Dynamo","Extraplanar Lens","Bucknard's Everfull Purse",
    "Kozilek's Command","Manifold Key","Voltaic Key",
)

ALL_EXTRA=(GENERIC_A,GENERIC_B)+PROSPECTS
for card in ALL_EXTRA:
    if card not in d.CARD_ID:
        nid=max(d.CARD_ID.values(),default=-1)+1
        d.CARD_ID[card]=nid
        d.ID_CARD[nid]=card

# Casting costs.
d.COSTS.update({
    GENERIC_A:(2,0,0), GENERIC_B:(2,0,0),
    "Helm of Awakening":(2,0,0),
    "Krark-Clan Ironworks":(4,0,0),
    "Inspiring Statuary":(3,0,0),
    "Marble Diamond":(2,0,0),
    "Sonic Screwdriver":(3,0,0),
    "Urza's Incubator":(3,0,0),
    "Worn Powerstone":(3,0,0),
    "Chromatic Lantern":(3,0,0),
    "Honor-Worn Shaku":(3,0,0),
    "Component Pouch":(3,0,0),
    "Oketra's Monument":(3,0,0),
    "Cloud Key":(3,0,0),
    "Thran Dynamo":(4,0,0),
    "Extraplanar Lens":(3,0,0),
    "Bucknard's Everfull Purse":(2,0,0),
    "Kozilek's Command":(0,0,2),
    "Voltaic Key":(1,0,0),
})

EXTRA_ARTIFACTS=frozenset({
    GENERIC_A,GENERIC_B,"Helm of Awakening","Krark-Clan Ironworks",
    "Inspiring Statuary","Marble Diamond","Sonic Screwdriver","Urza's Incubator",
    "Worn Powerstone","Chromatic Lantern","Honor-Worn Shaku","Component Pouch",
    "Oketra's Monument","Cloud Key","Thran Dynamo","Extraplanar Lens",
    "Bucknard's Everfull Purse","Voltaic Key"
})
_base_is_artifact=d.is_artifact_perm
def is_artifact_perm(name):
    return name in EXTRA_ARTIFACTS or _base_is_artifact(name)
d.is_artifact_perm=is_artifact_perm

# Cards that the London structural heuristic should treat as deployment infrastructure.
d.RAMP_PROTECTED=frozenset(set(getattr(d,"RAMP_PROTECTED",())) | set(EXTRA_ARTIFACTS) | {"Kozilek's Command"})

# Moonsilver Key can find artifacts with mana abilities.
d.MOONSILVER_MANA_ARTIFACTS=frozenset(set(d.MOONSILVER_MANA_ARTIFACTS)|{
    GENERIC_A,GENERIC_B,"Krark-Clan Ironworks","Marble Diamond","Sonic Screwdriver",
    "Worn Powerstone","Chromatic Lantern","Honor-Worn Shaku","Component Pouch",
    "Thran Dynamo","Extraplanar Lens"
})

LEGENDARY_PERMS=frozenset({
    "Eiganjo, Seat of the Empire","Great Hall of the Citadel",
    "Untaidake, the Cloud Keeper","Tezzeret, Cruel Captain","Oketra's Monument"
})

def _dedupe(states):
    seen=set(); out=[]
    for q in states:
        k=d.key(q)
        if k not in seen:
            seen.add(k); out.append(q)
    return out

TRIAL_SEED=0
def set_trial_seed(seed):
    global TRIAL_SEED
    TRIAL_SEED=int(seed)

def _roll(s,card,sides,salt=0):
    payload=(str(TRIAL_SEED)+"|"+card+"|"+str(s.turn)+"|"+repr(d.key(s))+"|"+str(salt)).encode()
    h=hashlib.sha256(payload).digest()
    return 1+(int.from_bytes(h[:8],"big")%int(sides))

def set_deck(deck):
    assert len(deck)==99
    d.DECK=list(deck)
    v.clear_caches()

def clear_caches():
    v.clear_caches()

# ---------------- commander deployment semantics ----------------
_base_can_cast_dack=d.can_cast_dack
def can_cast_dack(s):
    if not d.COMBO_CREATURES.issubset(set(s.library)): return False
    if not d.stax_allows(s,d.COMMANDER,is_creature=True): return False

    generic=4
    names=[d.effective_name(x) for x in s.battlefield]
    # Existing Pearl effect.
    if "Pearl Medallion" in names: generic-=1
    # Additional reducers from the historical table.
    generic-=names.count("Helm of Awakening")
    generic-=names.count("Oketra's Monument")
    # Cloud Key only works when the actual permanent made the creature choice.
    generic-=sum(1 for x in s.battlefield if x.name=="Cloud Key" and x.aux=="CLOUD:creature")
    # Incubator's as-enters Human choice is represented explicitly.
    generic-=2*sum(1 for x in s.battlefield if x.name=="Urza's Incubator" and x.aux=="INCUBATOR:Human")
    generic=max(0,generic)

    # Inspiring Statuary: untapped artifacts (including treasures) may improvise generic.
    improvise=0
    if any(d.effective_name(x)=="Inspiring Statuary" for x in s.battlefield):
        improvise=sum(1 for x in s.battlefield if d.is_artifact_perm(d.effective_name(x)) and not x.tapped)
        improvise+=s.treasures

    for rdw_white in range(min(2,s.restricted_dack_white)+1):
        needw=2-rdw_white
        for ww in range(min(s.w,needw)+1):
            aa=needw-ww
            if aa>s.any: continue
            remw=s.w-ww; rema=s.any-aa; remrdw=s.restricted_dack_white-rdw_white
            if remw+s.c+rema+s.restricted_legend+remrdw+improvise>=generic:
                return True
    return False
d.can_cast_dack=can_cast_dack

# ---------------- cast layer / ETB choices ----------------
_base_cast=d.cast_actions

def _entered_count(state,name):
    return sum(d.effective_name(x)==name for x in state.battlefield)

def _postprocess_new_artifact_entries(s,states):
    out=[]
    for q in states:
        qlist=[q]
        # Tapped mana rocks.
        for nm in ("Marble Diamond","Worn Powerstone"):
            if _entered_count(q,nm)>_entered_count(s,nm):
                fixed=[]
                for z in qlist:
                    bf=list(z.battlefield)
                    # newest matching permanent is sufficient in singleton arms
                    inds=[i for i,p in enumerate(bf) if d.effective_name(p)==nm and not p.tapped]
                    if inds:
                        i=inds[-1]; bf[i]=replace(bf[i],tapped=True); z=replace(z,battlefield=tuple(bf))
                    fixed.append(z)
                qlist=fixed

        # Cloud Key: only artifact and creature choices can improve this focused deployment
        # objective; both are explicitly represented.
        if _entered_count(q,"Cloud Key")>_entered_count(s,"Cloud Key"):
            bran=[]
            for z in qlist:
                idx=next((i for i,p in enumerate(z.battlefield) if p.name=="Cloud Key" and not p.aux),None)
                if idx is None:
                    bran.append(z); continue
                for choice in ("artifact","creature"):
                    bf=list(z.battlefield); bf[idx]=replace(bf[idx],aux="CLOUD:"+choice)
                    bran.append(replace(z,battlefield=tuple(bf)))
            qlist=bran

        if _entered_count(q,"Urza's Incubator")>_entered_count(s,"Urza's Incubator"):
            fixed=[]
            for z in qlist:
                idx=next((i for i,p in enumerate(z.battlefield) if p.name=="Urza's Incubator" and not p.aux),None)
                if idx is not None:
                    bf=list(z.battlefield); bf[idx]=replace(bf[idx],aux="INCUBATOR:Human")
                    z=replace(z,battlefield=tuple(bf))
                fixed.append(z)
            qlist=fixed

        # Extraplanar Lens: in this singleton shell only Snow-Covered Plains has another
        # same-name land available after imprint, so no-imprint and Snow-imprint are the
        # deployment-relevant exact branches.
        if _entered_count(q,"Extraplanar Lens")>_entered_count(s,"Extraplanar Lens"):
            bran=[]
            for z in qlist:
                bran.append(z)
                li=next((i for i,p in enumerate(z.battlefield) if p.name=="Extraplanar Lens" and not p.aux),None)
                si=next((i for i,p in enumerate(z.battlefield) if p.name=="Snow-Covered Plains"),None)
                if li is not None and si is not None:
                    bf=list(z.battlefield)
                    # remove land first and relocate Lens if index shifted
                    snow=bf.pop(si)
                    li2=next(i for i,p in enumerate(bf) if p.name=="Extraplanar Lens" and not p.aux)
                    bf[li2]=replace(bf[li2],aux="IMPRINT:Snow-Covered Plains")
                    bran.append(replace(z,battlefield=tuple(bf),exile=z.exile+(snow.name,)))
            qlist=bran

        out.extend(qlist)
    return _dedupe(out)

def _helm_discount_casts(s):
    # One generic discount is represented by one temporary generic/colorless resource.
    # It is accepted only if the synthetic unit was consumed. With an active Trinisphere
    # we conservatively skip this shortcut rather than underpay the Trinisphere floor.
    if not any(d.effective_name(x)=="Helm of Awakening" for x in s.battlefield):
        return []
    if any(x.name=="Trinisphere" and not x.tapped for x in s.battlefield):
        return []
    boosted=replace(s,c=s.c+1)
    out=[]
    for q in _base_cast(boosted):
        if q.spells<=s.spells or q.c>s.c:
            continue
        # Helm cannot reduce the two true-C pips on these spells; reject transitions where
        # the synthetic C may have paid a true colorless requirement.
        if q.grave.count("Kozilek's Command")>s.grave.count("Kozilek's Command"):
            continue
        if q.grave.count("Eldrazi Confluence")>s.grave.count("Eldrazi Confluence"):
            continue
        out.append(q)
    return out

def _cloud_artifact_discount_casts(s):
    if not any(x.name=="Cloud Key" and x.aux=="CLOUD:artifact" for x in s.battlefield):
        return []
    if any(x.name=="Trinisphere" and not x.tapped for x in s.battlefield):
        return []
    boosted=replace(s,restricted_artifact=s.restricted_artifact+1)
    out=[]
    for q in _base_cast(boosted):
        if q.spells<=s.spells or q.restricted_artifact>s.restricted_artifact:
            continue
        out.append(q)
    return out

def _oketra_legend_casts(s):
    if "Oketra's Monument" not in s.hand:
        return []
    # Base engine does not tag ordinary artifacts as legendary for restricted Great Hall mana.
    g=3
    names={x.name for x in s.battlefield}
    if "Thorn of Amethyst" in names: g+=1
    if "Charitable Levy" in names: g+=1
    if any(x.name=="Trinisphere" and not x.tapped for x in s.battlefield): g=max(g,3)
    out=[]
    for paid in d.pay_options(s,g,legend=True,artifact=True):
        if not d.payment_stax_ok(s,paid): continue
        h=list(paid.hand); h.remove("Oketra's Monument")
        base=replace(paid,hand=d.sort_hand(h),spells=paid.spells+1,noncreature_spells=paid.noncreature_spells+1)
        bf=d.artifact_enters_bf(base.battlefield,d.Perm("Oketra's Monument",False,0,s.turn))
        out.append(replace(base,battlefield=bf))
    return out

def cast_actions(s):
    raw=list(_base_cast(s))
    raw.extend(_helm_discount_casts(s))
    raw.extend(_cloud_artifact_discount_casts(s))
    raw.extend(_oketra_legend_casts(s))
    return _postprocess_new_artifact_entries(s,_dedupe(raw))
d.cast_actions=cast_actions

# ---------------- mana layer ----------------
_base_tap=d.tap_mana_actions
def tap_mana_actions(s):
    base=list(_base_tap(s))
    out=list(base)

    simple={
        GENERIC_A:(0,1,0), GENERIC_B:(0,1,0),
        "Marble Diamond":(1,0,0),
        "Sonic Screwdriver":(0,0,1),
        "Worn Powerstone":(0,2,0),
        "Chromatic Lantern":(0,0,1),
        "Honor-Worn Shaku":(0,1,0),
        "Thran Dynamo":(0,3,0),
    }
    for i,p in enumerate(s.battlefield):
        if p.tapped: continue
        n=d.effective_name(p)
        if n in simple:
            dw,dc,da=simple[n]
            bf=list(s.battlefield); bf[i]=replace(p,tapped=True)
            out.append(replace(s,battlefield=tuple(bf),w=s.w+dw,c=s.c+dc,any=s.any+da))

    # Chromatic Lantern gives every land an additional any-color mana ability.
    if any(d.effective_name(x)=="Chromatic Lantern" for x in s.battlefield):
        for i,p in enumerate(s.battlefield):
            if p.tapped or p.name not in d.LANDS: continue
            amt=2 if (p.name=="Snow-Covered Plains" and any(
                x.name=="Extraplanar Lens" and x.aux=="IMPRINT:Snow-Covered Plains"
                for x in s.battlefield)) else 1
            bf=list(s.battlefield); bf[i]=replace(p,tapped=True)
            out.append(replace(s,battlefield=tuple(bf),w=s.w+amt))

    # Extraplanar Lens doubles the mana made by the current Snow basic.
    if any(x.name=="Extraplanar Lens" and x.aux=="IMPRINT:Snow-Covered Plains" for x in s.battlefield):
        for q in base:
            # Identify a Snow land that changed from untapped to tapped.
            doubled=False
            for i,p in enumerate(s.battlefield):
                if p.name!="Snow-Covered Plains" or p.tapped: continue
                if i < len(q.battlefield) and q.battlefield[i].name=="Snow-Covered Plains" and q.battlefield[i].tapped:
                    doubled=True; break
            if doubled and q.w>s.w:
                out.append(replace(q,w=q.w+1))

    return _dedupe(out)
d.tap_mana_actions=tap_mana_actions

# ---------------- activated utility / randomness ----------------
_base_utility=d.utility_actions
def _scry1_bottom(s,source_index,cost):
    out=[]
    if not s.library: return out
    for paid in d.pay_options(s,cost):
        si=next((j for j,x in enumerate(paid.battlefield)
                 if j==source_index and not x.tapped),None)
        # Index can shift only if payment sacrifices something; ordinary payment does not.
        if si is None or si>=len(paid.battlefield): continue
        bf=list(paid.battlefield); bf[si]=replace(bf[si],tapped=True)
        lib=paid.library[1:]+paid.library[:1]
        out.append(replace(paid,battlefield=tuple(bf),library=lib))
    return out

def utility_actions(s):
    out=list(_base_utility(s))

    # KCI — Sacrifice an artifact: add CC. Treasures are artifacts too.
    if any(d.effective_name(x)=="Krark-Clan Ironworks" for x in s.battlefield):
        for ti,target in enumerate(s.battlefield):
            if not d.is_artifact_perm(d.effective_name(target)): continue
            bf=list(s.battlefield); src=bf.pop(ti)
            out.append(replace(s,battlefield=tuple(bf),c=s.c+2,grave=s.grave+(src.name,)))
        if s.treasures:
            out.append(replace(s,treasures=s.treasures-1,c=s.c+2))

    # Sonic Screwdriver — 1,T untap another artifact; 2,T scry 1.
    for i,p in enumerate(s.battlefield):
        if d.effective_name(p)!="Sonic Screwdriver" or p.tapped: continue
        for paid in d.pay_options(s,1):
            si=next((j for j,x in enumerate(paid.battlefield)
                     if d.effective_name(x)=="Sonic Screwdriver" and not x.tapped),None)
            if si is None: continue
            for ti,tgt in enumerate(paid.battlefield):
                if ti==si or not tgt.tapped or not d.is_artifact_perm(d.effective_name(tgt)): continue
                bf=list(paid.battlefield); bf[si]=replace(bf[si],tapped=True); bf[ti]=replace(bf[ti],tapped=False)
                out.append(replace(paid,battlefield=tuple(bf)))
        if s.library:
            for paid in d.pay_options(s,2):
                si=next((j for j,x in enumerate(paid.battlefield)
                         if d.effective_name(x)=="Sonic Screwdriver" and not x.tapped),None)
                if si is None: continue
                bf=list(paid.battlefield); bf[si]=replace(bf[si],tapped=True)
                out.append(replace(paid,battlefield=tuple(bf),library=paid.library[1:]+paid.library[:1]))

    # Honor-Worn Shaku — tap an untapped legendary permanent to untap Shaku.
    for i,p in enumerate(s.battlefield):
        if d.effective_name(p)!="Honor-Worn Shaku" or not p.tapped: continue
        for li,lp in enumerate(s.battlefield):
            if li==i or lp.tapped or d.effective_name(lp) not in LEGENDARY_PERMS: continue
            bf=list(s.battlefield); bf[i]=replace(p,tapped=False); bf[li]=replace(lp,tapped=True)
            out.append(replace(s,battlefield=tuple(bf)))

    # Component Pouch — deterministic seeded d20 roll or cash a counter for two different colors.
    for i,p in enumerate(s.battlefield):
        if d.effective_name(p)!="Component Pouch" or p.tapped: continue
        if p.counters>0:
            bf=list(s.battlefield); bf[i]=replace(p,tapped=True,counters=p.counters-1)
            # One of the two different colors may be white; the other is generic-only here.
            out.append(replace(s,battlefield=tuple(bf),w=s.w+1,c=s.c+1))
        roll=_roll(s,"Component Pouch",20,p.counters)
        add=1 if roll<=9 else 2
        bf=list(s.battlefield); bf[i]=replace(p,tapped=True,counters=p.counters+add)
        out.append(replace(s,battlefield=tuple(bf)))

    # Bucknard — 1,T, roll d4, create that many Treasures, then it leaves our control.
    for p in s.battlefield:
        if d.effective_name(p)!="Bucknard's Everfull Purse" or p.tapped: continue
        for paid in d.pay_options(s,1):
            bi=next((j for j,x in enumerate(paid.battlefield)
                     if d.effective_name(x)=="Bucknard's Everfull Purse" and not x.tapped),None)
            if bi is None: continue
            roll=_roll(s,"Bucknard's Everfull Purse",4,paid.turn)
            bf=list(paid.battlefield); source=bf.pop(bi)
            # Normal resolution: Purse transfers away after making Treasures.
            out.append(replace(paid,battlefield=tuple(bf),treasures=paid.treasures+roll))
            # If KCI is present, respond to the Purse activation by sacrificing the Purse;
            # its already-stacked ability still resolves and makes the Treasures.
            if any(d.effective_name(x)=="Krark-Clan Ironworks" for x in bf):
                out.append(replace(paid,battlefield=tuple(bf),treasures=paid.treasures+roll,
                                   c=paid.c+2,grave=paid.grave+(source.name,)))

    return _dedupe(out)
d.utility_actions=utility_actions

# ---------------- Gardens copies of added artifacts ----------------
_base_v03=d.v03_actions
_EXTRA_MV={
    GENERIC_A:2, GENERIC_B:2, "Helm of Awakening":2, "Krark-Clan Ironworks":4,
    "Inspiring Statuary":3, "Marble Diamond":2, "Sonic Screwdriver":3,
    "Urza's Incubator":3, "Worn Powerstone":3, "Chromatic Lantern":3,
    "Honor-Worn Shaku":3, "Component Pouch":3, "Oketra's Monument":3,
    "Cloud Key":3, "Thran Dynamo":4, "Extraplanar Lens":3,
    "Bucknard's Everfull Purse":2
}
def v03_actions(s):
    out=list(_base_v03(s))
    if any(x.name=="The Mycosynth Gardens" and not x.tapped and not x.aux for x in s.battlefield):
        for target in s.battlefield:
            tn=d.effective_name(target)
            if tn not in _EXTRA_MV: continue
            for paid in d.pay_options(s,_EXTRA_MV[tn]):
                gi=next((j for j,x in enumerate(paid.battlefield)
                         if x.name=="The Mycosynth Gardens" and not x.tapped and not x.aux),None)
                if gi is None: continue
                if not any(d.effective_name(x)==tn for j,x in enumerate(paid.battlefield) if j!=gi): continue
                bf=list(paid.battlefield); bf[gi]=replace(bf[gi],tapped=True,aux="COPY:"+tn)
                out.append(replace(paid,battlefield=tuple(bf)))
    return _dedupe(out)
d.v03_actions=v03_actions

# ---------------- Kozilek's Command corrected deployment modes ----------------
# The inherited engine has a conservative Spawn-only Command branch. Add the goldfish-dominant
# legal pair: create X Spawn + scry X then draw a card, including X=0.
def _scry_draw_relevant(base,X):
    # Exact for X<=3. For larger X, keep the bounded deployment-relevant branch that bottoms
    # all visible combo creatures and preserves relative order of the rest.
    if X<=0:
        return [d.draw(base,1)]
    top=list(base.library[:X]); tail=tuple(base.library[X:])
    if X<=3:
        from itertools import combinations, permutations
        out=[]; inds=range(len(top)); seen=set()
        for nb in range(len(top)+1):
            for bottom_inds in combinations(inds,nb):
                bset=set(bottom_inds)
                kept=[top[j] for j in inds if j not in bset]
                bot=[top[j] for j in inds if j in bset]
                for kp in (set(permutations(kept)) if kept else {()}):
                    for bp in (set(permutations(bot)) if bot else {()}):
                        libv=tuple(kp)+tail+tuple(bp)
                        if libv in seen: continue
                        seen.add(libv)
                        out.append(d.draw(replace(base,library=libv),1))
        return out
    kept=[x for x in top if x not in d.COMBO_CREATURES]
    bot=[x for x in top if x in d.COMBO_CREATURES]
    return [d.draw(replace(base,library=tuple(kept)+tail+tuple(bot)),1)]

_base_ranked=d._cast_actions_ranked
def _cast_actions_ranked(s,payment_rank=0):
    out=list(_base_ranked(s,payment_rank))
    if "Kozilek's Command" in s.hand:
        # Extra corrected branches; inherited Spawn-only branches remain legal alternatives.
        idx=list(s.hand).index("Kozilek's Command")
        names={x.name for x in s.battlefield}
        for X in range(0,7):
            g=X
            if "Thorn of Amethyst" in names: g+=1
            if "Charitable Levy" in names: g+=1
            if any(x.name=="Trinisphere" and not x.tapped for x in s.battlefield):
                g=max(g,1)  # total with CC is then at least 3
            paid=d.pay_simple(s,g,0,2,payment_rank=payment_rank)
            if not paid or not d.payment_stax_ok(s,paid): continue
            hh=list(paid.hand); hh.pop(idx)
            base=replace(paid,hand=d.sort_hand(hh),spawn=paid.spawn+X,
                         grave=paid.grave+("Kozilek's Command",),
                         spells=paid.spells+1,nonartifact_spells=paid.nonartifact_spells+1,
                         noncreature_spells=paid.noncreature_spells+1)
            out.extend(_scry_draw_relevant(base,X))
    return _dedupe(out)
d._cast_actions_ranked=_cast_actions_ranked

# Rebuild v0.74 cast dispatcher dynamically through the overridden ranked function, then
# preserve the v0.76 Snow/Charitable-Levy postprocessing by leaving d.cast_actions wrapper above.
# Our wrapper already calls the inherited v0.76 cast, whose historical dispatcher resolves
# d._cast_actions_ranked dynamically.

# ---------------- score support for new infrastructure ----------------
_base_score=d.score
def score(s):
    z=_base_score(s)
    names=[d.effective_name(x) for x in s.battlefield]
    for p,n in zip(s.battlefield,names):
        if n in {GENERIC_A,GENERIC_B,"Marble Diamond","Sonic Screwdriver","Chromatic Lantern","Honor-Worn Shaku"} and not p.tapped:
            z+=22
        elif n=="Worn Powerstone" and not p.tapped: z+=36
        elif n=="Thran Dynamo" and not p.tapped: z+=48
        elif n=="Component Pouch": z+=12+8*p.counters+(8 if not p.tapped else 0)
        elif n=="Bucknard's Everfull Purse" and not p.tapped: z+=30
        elif n=="Krark-Clan Ironworks": z+=14
        elif n=="Inspiring Statuary": z+=18
        elif n=="Helm of Awakening": z+=22
        elif n=="Oketra's Monument": z+=18
        elif n=="Urza's Incubator" and p.aux=="INCUBATOR:Human": z+=34
        elif n=="Cloud Key": z+=20
        elif n=="Extraplanar Lens" and p.aux=="IMPRINT:Snow-Covered Plains": z+=40
    return z
d.score=score

def selftest():
    set_deck(BASE_CURRENT_DECK)
    assert v.selftest()
    assert d.is_artifact_perm(GENERIC_A)
    assert d.COSTS["Krark-Clan Ironworks"]==(4,0,0)

    # Generic rock / Marble / Worn / Thran mana.
    for card,field,amt in [
        (GENERIC_A,"c",1),("Marble Diamond","w",1),("Worn Powerstone","c",2),("Thran Dynamo","c",3)
    ]:
        s=d.State(1,(),(),(d.Perm(card),))
        assert any(getattr(q,field)>=amt for q in d.tap_mana_actions(s)), card

    # KCI can sacrifice an artifact for CC.
    s=d.State(1,(),(),(d.Perm("Krark-Clan Ironworks"),d.Perm(GENERIC_A)))
    assert any(q.c>=2 and GENERIC_A in q.grave for q in d.utility_actions(s))

    # Sonic untaps another artifact.
    s=d.State(1,(),(),(d.Perm("Sonic Screwdriver"),d.Perm("Mana Vault",True)),c=1)
    assert any(any(d.effective_name(p)=="Mana Vault" and not p.tapped for p in q.battlefield)
               for q in d.utility_actions(s))

    # Component Pouch produces a legal roll branch.
    s=d.State(1,(),(),(d.Perm("Component Pouch"),))
    set_trial_seed(123)
    assert any(any(d.effective_name(p)=="Component Pouch" and p.tapped and p.counters in (1,2)
                   for p in q.battlefield) for q in d.utility_actions(s))

    # Bucknard roll is 1..4 Treasures and leaves our battlefield.
    s=d.State(1,(),(),(d.Perm("Bucknard's Everfull Purse"),),c=1)
    outs=d.utility_actions(s)
    assert any(1<=q.treasures<=4 and not any(d.effective_name(p)=="Bucknard's Everfull Purse" for p in q.battlefield)
               for q in outs)

    # Cost reducers affect Dack generic requirement.
    lib=tuple(d.COMBO_CREATURES)
    s=d.State(1,(),lib,(d.Perm("Urza's Incubator",aux="INCUBATOR:Human"),),w=2,c=2)
    assert d.can_cast_dack(s), "Incubator Human reduction missing"
    s=d.State(1,(),lib,(d.Perm("Oketra's Monument"),),w=2,c=3)
    assert d.can_cast_dack(s), "Oketra reduction missing"
    s=d.State(1,(),lib,(d.Perm("Inspiring Statuary"),d.Perm(GENERIC_A)),w=2,c=2)
    assert d.can_cast_dack(s), "Statuary improvise missing"

    # Lens doubles Snow.
    s=d.State(1,(),(),(d.Perm("Snow-Covered Plains"),d.Perm("Extraplanar Lens",aux="IMPRINT:Snow-Covered Plains")))
    assert any(q.w>=2 for q in d.tap_mana_actions(s))

    # Kozilek requires two true colorless.
    set_deck(tuple("Kozilek's Command" if x=="Implements of Sacrifice" else x for x in BASE_CURRENT_DECK))
    s=d.State(1,("Kozilek's Command",),("Snow-Covered Plains",),c=1,w=10)
    assert not any(q.grave.count("Kozilek's Command") for q in d.cast_actions(s))
    s=replace(s,c=2)
    assert any(q.grave.count("Kozilek's Command") for q in d.cast_actions(s))
    set_deck(BASE_CURRENT_DECK)
    return True

if __name__=="__main__":
    print("selftest:", "PASS" if selftest() else "FAIL")
