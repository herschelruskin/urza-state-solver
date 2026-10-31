#!/usr/bin/env python3
"""Experimental zero-beam London policy. Hand score is NOT calibrated probability.

Uses exact hypergeometric land/white draw probabilities from the known
remaining deck multiset, plus cheap transparent mana/tutor/synergy features.
Every London stage and every bottom choice can be evaluated without beam
search. Actual games still use the existing beam-160 action search.

This is a NEW keep policy, not a parity-preserving engine optimization.
The sampled T1/T2/T3 deployment rates remain legitimate Monte Carlo
statistics for this policy, provided the actual game simulation is sound.
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations
import math

import dack_paired_counterfactual_v1_20261030 as ref

d=ref.d
POLICY_VERSION="no_beam_analytic_london_v6_diagnostic_20261031"
MDFC=frozenset(("Emeria's Call","Razorgrass Ambush"))
WHITE_LANDS=frozenset((
    "Plains","Ancient Den","Eiganjo, Seat of the Empire","Emeria's Call",
    "Razorgrass Ambush","Remote Farm","Ruins of Trokair","Shefet Dunes",
    "City of Brass","Mana Confluence","Gemstone Mine","Tarnished Citadel",
    "Starting Town","Spire of Industry","Gemstone Caverns"))
TWO_LANDS=frozenset(("Ancient Tomb","City of Traitors","Crystal Vein"))
REPEAT_WHITE=frozenset(("Arcane Signet","Fellwar Stone","The Mind Stone"))
SMALL_ROCKS=frozenset(("Mind Stone","Liquimetal Torque","Prismatic Lens",
                       "Giant's Boulder","Everflowing Chalice"))
TUTORS=frozenset(("Enlightened Tutor","Loyal Tutor","Moonsilver Key",
                  "Expedition Map","Tezzeret, Cruel Captain"))
# Deliberately separate from frozen beam-continuation values. Uncalibrated.
CUTOFFS={7:.55,6:.49,5:.40,4:.30,3:.19,2:.10,1:0.0}
STATS=Counter()

def is_land(card):
    return card in d.LANDS or card in MDFC

def hypergeom_p_at_least_one(N,K,n):
    """Exact P(X>=1) for n draws from a finite deck without replacement."""
    N=int(N);K=int(K);n=min(N,max(0,int(n)))
    if n<=0 or K<=0:return 0.
    if n>N-K:return 1.
    return 1.-math.comb(N-K,n)/math.comb(N,n)

def sigmoid(x):
    if x>=0:return 1./(1.+math.exp(-min(50.,x)))
    z=math.exp(max(-50.,x))
    return z/(1.+z)

def proxy_features(kept,unknown,seat):
    """Read only cards seen in hand and counts of UNKNOWN remaining cards."""
    hand=tuple(kept); pool=Counter(unknown); N=len(unknown)
    lands=[x for x in hand if is_land(x)]
    nlands=len(lands)
    nw=sum(x in WHITE_LANDS for x in lands)
    remaining_land=sum(v for x,v in pool.items() if is_land(x))
    remaining_white=sum(v for x,v in pool.items() if x in WHITE_LANDS)
    # Starting seat gets no T1 draw; other seats do. All seats draw at T2/T3.
    nd2=1+int(int(seat)!=0)
    nd3=2+int(int(seat)!=0)
    pl2=hypergeom_p_at_least_one(N,remaining_land,nd2)
    pl3=hypergeom_p_at_least_one(N,remaining_land,nd3)
    pw2=hypergeom_p_at_least_one(N,remaining_white,nd2)
    pw3=hypergeom_p_at_least_one(N,remaining_white,nd3)
    # The following are scoring proxies, NOT executable mana lines.
    land2=min(2.,nlands+(.8*pl2 if nlands<2 else 0))
    land3=min(3.,nlands+(1.5*pl3 if nlands<3 else 0))
    doubles=sum(x in TWO_LANDS for x in lands)
    gener2=land2+min(doubles,land2)
    gener3=land3+min(doubles,land3)
    artifacts=sum(bool(d.is_artifact_perm(x)) for x in hand)
    imprint=any(x in d.MOX_SAFE for x in hand)
    zero_white=int("Lotus Petal" in hand)
    zero_white+=int("Mox Diamond" in hand and nlands>=2)
    zero_white+=int("Chrome Mox" in hand and imprint)
    zero_white+=int("Mox Opal" in hand and artifacts>=3)
    led=3. if "Lion's Eye Diamond" in hand else 0.
    fast=0.
    if nlands and "Sol Ring" in hand:fast+=2.
    if nlands and "Mana Vault" in hand:fast+=2.6
    if (nlands>=2 or doubles) and "Grim Monolith" in hand:fast+=1.7
    if (nlands>=2 or doubles) and "Basalt Monolith" in hand:fast+=1.
    if artifacts>=2 and "Krark-Clan Ironworks" in hand:fast+=.9
    if nlands and "Bucknard's Everfull Purse" in hand:fast+=1.1
    if ("Voltaic Key" in hand and
        any(x in hand for x in ("Mana Vault","Grim Monolith","Basalt Monolith"))):
        fast+=1.1
    if doubles and "Candelabra of Tawnos" in hand:fast+=.65
    if "Gemstone Caverns" in hand and seat!=0:fast+=.65
    fast+=.6*sum(x in REPEAT_WHITE for x in hand)
    fast+=.4*sum(x in SMALL_ROCKS for x in hand)
    fast+=.3*sum(x in TUTORS for x in hand)
    fast=min(fast,7.)
    # LED produces one color on activation, not arbitrary W plus generic.
    # Partial LED white-value credit is only a proxy, NOT a legal allocation.
    extra_white=zero_white+.6*sum(x in REPEAT_WHITE for x in hand)
    if led:extra_white+=1.45
    if "Cavern of Souls" in hand:extra_white+=.8
    if "Great Hall of the Citadel" in hand:extra_white+=.65
    white2=nw+(.85*pw2 if nw<2 else 0)+extra_white
    white3=nw+(1.2*pw3 if nw<2 else 0)+extra_white
    mana2=gener2+zero_white+led+fast
    mana3=gener3+zero_white+led+fast+(.75 if nlands>=2 else .25)
    pseudo2=sigmoid((mana2-5.45)*.9)*sigmoid((white2-1.55)*1.9)
    pseudo3=sigmoid((mana3-5.65)*.7)*sigmoid((white3-1.55)*1.55)
    bricked=(any(x in d.COMBO_CREATURES for x in hand)
             and not ("Brainstone" in hand or "Scroll Rack" in hand))
    if bricked:pseudo2=pseudo3=0.
    auras=sum(x in d.AURAS for x in hand)
    if auras:
        pseudo2*=max(.65,1-.13*auras)
        pseudo3*=max(.7,1-.1*auras)
    utility=pseudo2+.5*(1-pseudo2)*pseudo3
    return {"proxy_utility":round(utility,12),
            "proxy_t2_index":round(pseudo2,12),
            "proxy_t3_index":round(pseudo3,12),
            "p_draw_land_by_t2":pl2,"p_draw_white_by_t2":pw2,
            "expected_mana_t2_proxy":mana2,"white_t2_proxy":white2,
            "lands_in_hand":nlands,"bricked":bool(bricked)}

def select_bottom(seven,keep_n,unknown,seat):
    """Exhaustive <=35 index subsets; no action-tree searches or draw-order peek."""
    best=None
    for inds in combinations(range(7),7-int(keep_n)):
        chosen=set(inds)
        bottom=tuple(seven[i] for i in inds)
        hand=d.sort_hand(seven[i] for i in range(7) if i not in chosen)
        info=proxy_features(hand,unknown,seat)
        structural=sum(d.bottom_priority(seven[i],seven) for i in inds)
        rank=(info["proxy_utility"],structural)
        if best is None or rank>best[0]:
            best=(rank,hand,bottom,info)
    return best[1:]

def choose_keep(deck_slots,seat,order_by_stage):
    """Drop-in no-beam London policy; gameplay remains unchanged."""
    history=[]
    for stage,(keep_n,order) in enumerate(zip(ref.sim.STAGES,order_by_stage)):
        seven=tuple(deck_slots[slot] for slot in order[:7])
        unknown=tuple(deck_slots[slot] for slot in order[7:])
        hand,bottom,info=select_bottom(seven,keep_n,unknown,seat)
        utility=info["proxy_utility"]
        threshold=CUTOFFS[int(keep_n)]
        keep=(int(keep_n)==1 or utility>=threshold)
        STATS["london_stages"]+=1
        STATS["keeps" if keep else "mulls"]+=1
        history.append({
            "stage":stage,"keep_n":int(keep_n),"kept":bool(keep),
            "raw":round(utility,7),"sampled_t1":None,
            "threshold":threshold,"refined":False,
            "policy":POLICY_VERSION,"proxy_features":info,
            "seven_slots":list(order[:7]),"seven":list(seven),
            "hand":list(hand),"bottom":list(bottom),
            "hand_slots":ref.selected_slots(order[:7],seven,hand),
            "bottom_slots":ref.selected_slots(order[:7],seven,bottom)})
        if keep:
            return d.State(1,tuple(hand),tuple(unknown)+tuple(bottom)),history
    raise AssertionError("terminal London keep was not reached")

def selftest():
    assert len(CUTOFFS)==7 and CUTOFFS[1]==0.
    assert hypergeom_p_at_least_one(92,0,3)==0.
    assert hypergeom_p_at_least_one(92,92,1)==1.
    assert abs(hypergeom_p_at_least_one(92,1,2)-2/92)<1e-12
    sample=("Plains","Plains","Lion's Eye Diamond","Mana Vault",
            "Boonweaver Giant","Arcane Signet","Grim Monolith")
    unknown=tuple(ref.VARIANTS["one_key_34"][:92])
    hand,bottom,info=select_bottom(sample,6,unknown,seat=3)
    assert len(hand)==6 and len(bottom)==1
    assert bottom==("Boonweaver Giant",),(hand,bottom)
    assert 0<=info["proxy_utility"]<=1.5
    return {"status":"PASS","policy":POLICY_VERSION,
            "mulligan_beam_calls":0,"scores_uncalibrated":True}

if __name__=="__main__":
    import json
    print(json.dumps(selftest(),indent=2))
