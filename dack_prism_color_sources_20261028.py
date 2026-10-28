#!/usr/bin/env python3
"""Sunburst-aware correction for currently active Assertive Dack goldfish.

Rules fixes:
 - Mox Diamond produces one mana of ANY color, not obligatorily white, when
   a Pentad Prism is in hand. Otherwise keep the historical single-white
   canonical representative: all non-Prism outcomes are unchanged.
 - Mycosynth Gardens supports its real {1}, {T}: add one mana of any color,
   paying from OTHER mana resources before tapping Gardens itself.
 - Previously correct Mox Opal, Talon Gates, Prismatic Lens, Coalition Relic
   and Giant's Boulder abilities are tested, not replaced.
 - 4 REAL rainbow lands: City of Brass, Mana Confluence, Tarnished Citadel,
   Gemstone Mine. Command Tower is WHITE-ONLY and not used to claim sunburst.

Sunburst abstraction still tracks W vs flexible-offcolor vs colorless, not
five explicit colored resource vectors. This is sufficient for direct
W+offcolor two-counter witnesses but NOT perfect five-color accounting.
"""
from __future__ import annotations
from dataclasses import replace
import json
import dack_active_mulligan_policy as sim

d=sim.d
OLD_TAP=d.tap_mana_actions
OLD_UTILITY=d.utility_actions
FIX_VERSION="mox_diamond_any_and_gardens_filter_20261028_v1"

def colored_mox_diamond_tap(s):
    """Use offcolor-capable any mana for Diamond iff Prism is still in hand.

    Do not change its source-specific tap, keep, imprint, land-discard, or
    casting rules. A flexible pool can still pay W; always-white default
    canonicalization remains identical when Pentad Prism is not in hand.
    """
    out=OLD_TAP(s)
    if "Pentad Prism" not in s.hand:
        return out
    transformed=[]
    for q in out:
        is_diamond_tap=(
            len(s.battlefield)==len(q.battlefield) and
            q.w==s.w+1 and q.any==s.any and
            any(
                d.effective_name(p)=="Mox Diamond" and not p.tapped
                and q.battlefield[i].tapped
                and d.effective_name(q.battlefield[i])=="Mox Diamond"
                for i,p in enumerate(s.battlefield)
            )
        )
        if is_diamond_tap:
            q=replace(q,w=q.w-1,any=q.any+1)
        transformed.append(q)
    return transformed

def gardens_colored_filter(s):
    out=list(OLD_UTILITY(s))
    for i,p in enumerate(s.battlefield):
        # No extra mana ability if Gardens has become a COPY of something else.
        if p.name!="The Mycosynth Gardens" or p.tapped or p.aux:
            continue
        for paid in d.pay_options(s,1):
            # No tapping Gardens itself to pay its own {1} activation.
            matches=[j for j,q in enumerate(paid.battlefield) if
                q.name=="The Mycosynth Gardens" and
                not q.tapped and not q.aux]
            if i>=len(paid.battlefield) or i not in matches:
                continue
            bf=list(paid.battlefield)
            bf[i]=replace(bf[i],tapped=True)
            out.append(replace(paid,battlefield=tuple(bf),any=paid.any+1))
    seen=set()
    unique=[]
    for q in out:
        key=d.key(q)
        if key not in seen:
            unique.append(q);seen.add(key)
    return unique

d.tap_mana_actions=colored_mox_diamond_tap
d.utility_actions=gardens_colored_filter

def exact_source_witnesses():
    # In the full base, Prism sunburst checks the actual W/any spent.
    assert d.COSTS["Pentad Prism"]==(2,0,0)
    assert "Tarnished Citadel" in d.CARD_ID and "Tarnished Citadel" in d.LANDS
    assert "Mox Opal" in d.CARD_ID and "Mox Diamond" in d.CARD_ID

    # Diamond now makes offcolor-capable mana when Prism is available,
    # but still canonical W when Prism is absent.
    md=d.Perm("Mox Diamond")
    prism=d.State(1,("Pentad Prism",),(),(md,))
    with_diamond=[z for z in d.tap_mana_actions(prism) if
        z.battlefield[0].tapped and z.any==1 and z.w==0]
    assert with_diamond,"Diamond cannot finance offcolor sunburst"
    normal=d.State(1,(),(),(md,))
    assert any(z.w==1 and z.any==0 and z.battlefield[0].tapped
               for z in d.tap_mana_actions(normal))

    # Exact cast witness from Diamond + white pool = 2 charge counters.
    diamond_cast=d.State(1,("Pentad Prism",),(),
                         (d.Perm("Mox Diamond"),),w=1)
    dm=[z for z in d.tap_mana_actions(diamond_cast)
        if z.any==1 and z.w==1]
    assert dm and any(any(
        d.effective_name(p)=="Pentad Prism" and p.counters==2
        for p in z.battlefield) for z in d.cast_actions(dm[0]))

    # Opal already produces real flexible mana, only after 3 artifacts.
    opal=d.State(1,("Pentad Prism",),(),(
        d.Perm("Mox Opal"),d.Perm("Sol Ring"),d.Perm("Mox Diamond")))
    assert any(z.any==1 and z.battlefield[0].tapped for z in d.tap_mana_actions(opal))
    no_metal=d.State(1,("Pentad Prism",),(),(d.Perm("Mox Opal"),))
    assert not any(z.any==1 for z in d.tap_mana_actions(no_metal))

    # Four true rainbow lands, including Tarnished's real colored mode.
    for land in ("City of Brass","Mana Confluence","Tarnished Citadel","Gemstone Mine"):
        s=d.State(1,("Pentad Prism",),(),(d.Perm(land),))
        if land=="Gemstone Mine":
            s=d.State(1,("Pentad Prism",),(),(d.Perm(land,False,3,1),))
        assert any(z.any>=1 for z in d.tap_mana_actions(s)),("rainbow",land)

    # Command Tower has no second color in mono-white color identity.
    s=d.State(1,("Pentad Prism",),(),(d.Perm("Command Tower"),))
    assert any(z.w==1 for z in d.tap_mana_actions(s))
    assert not any(z.any>0 for z in d.tap_mana_actions(s))

    # Gardens is DIFFERENT from a free rainbow land. Pay one EXTERNAL mana.
    # Its {T}: {C} remains present; its {1},{T}: colored is now present.
    s=d.State(1,("Pentad Prism",),(),(d.Perm("The Mycosynth Gardens"),),c=1)
    assert any(z.any==1 and z.c==0 and z.battlefield[0].tapped
               for z in d.utility_actions(s))
    s=d.State(1,("Pentad Prism",),(),(d.Perm("The Mycosynth Gardens"),),c=0)
    assert not any(z.any==1 for z in d.utility_actions(s))
    s=d.State(1,("Pentad Prism",),(),(d.Perm("The Mycosynth Gardens",aux="COPY:Sol Ring"),),c=1)
    assert not any(z.any==1 for z in d.utility_actions(s))

    # Talon filter (already correct) requires external {1}.
    s=d.State(1,("Pentad Prism",),(),(d.Perm("Talon Gates of Madara"),),c=1)
    assert any(z.any==1 and z.c==0 for z in d.tap_mana_actions(s))
    # Prismatic Lens filter (already correct) requires external {1}.
    s=d.State(1,("Pentad Prism",),(),(d.Perm("Prismatic Lens"),),c=1)
    assert any(z.any==1 and z.c==0 for z in d.tap_mana_actions(s))
    # Boulder filter (already correct) requires external {1}.
    s=d.State(1,("Pentad Prism",),(),(d.Perm("Giant's Boulder"),),c=1)
    assert any(z.any==1 and z.c==0 for z in d.special_actions(s))
    # Relic produces any color when tapped and can bank a charge counter.
    s=d.State(1,("Pentad Prism",),(),(d.Perm("Coalition Relic"),))
    assert any(z.any==1 and z.battlefield[0].tapped for z in d.tap_mana_actions(s))
    assert any(z.battlefield[0].counters==1 for z in d.special_actions(s))

    # Prism's two counters can be cashed one after another without tapping.
    s=d.State(1,(),(),(d.Perm("Pentad Prism",False,2,1),))
    a=[z for z in d.tap_mana_actions(s) if z.any==1 and
       z.battlefield[0].counters==1 and not z.battlefield[0].tapped]
    assert a and any(z.any==2 and z.battlefield[0].counters==0 and
                     not z.battlefield[0].tapped
                     for z in d.tap_mana_actions(a[0]))

    print("PRISM_20261028_SOURCES_AUDIT_PASS",json.dumps({
        "fix":FIX_VERSION,
        "four_true_rainbow_lands":["City of Brass","Mana Confluence",
                                  "Tarnished Citadel","Gemstone Mine"],
        "mox_diamond":"offcolor-capable when Prism in hand",
        "mox_opal":"already-any with metalcraft",
        "filters":["Talon Gates of Madara","The Mycosynth Gardens",
                   "Prismatic Lens","Giant's Boulder"],
        "relic":"already-any, charge storage supported",
        "command_tower":"W-only",
        "Prism_two_charge_non_tap":"pass",
        "incompleteness":"two-color canonical abstraction; not full 5-color accounting"
    }),flush=True)

if __name__=="__main__":
    exact_source_witnesses()
