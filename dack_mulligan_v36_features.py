#!/usr/bin/env python3
"""v36 higher-coverage features for frozen v33b retained KEEP state.

Only observable (seven, proposed bottom, 92-unknown multiset, seat,
London stage, original frozen v27 score/threshold). Exact card features
are SMALL hand-level line indicators, never used as a game state key.
No full hidden deck order or future outcome is passed to inference.
"""
from __future__ import annotations
from collections import Counter
import hashlib,json,math
import dack_mulligan_v33b_capability_regret_features as cap
import dack_mulligan_teacher_features_v13_20261031 as old

KEY_CARDS=(
 "Lion's Eye Diamond","Mana Vault","Sol Ring","Grim Monolith",
 "Basalt Monolith","Ancient Tomb","City of Traitors","Gemstone Caverns",
 "Mox Diamond","Chrome Mox","Mox Opal","Lotus Petal",
 "Enlightened Tutor","Tezzeret, Cruel Captain","Voltaic Key",
 "The Mycosynth Gardens","Bucknard's Everfull Purse",
 "Scroll Rack","Brainstone","Urza's Saga",
)
INTERACTIONS=old.INTERACTIONS
NAMES=(
 ("old_Qkeep","old_C","old_Qkeep_minus_old_C")
 + tuple("stage_"+str(x) for x in range(3))
 + tuple("seat_"+str(x) for x in range(4))
 + tuple("cap_"+name for name in cap.NAMES)
 + tuple("has_"+name for name in KEY_CARDS)
 + tuple("pair_"+a+"_"+b for a,b in INTERACTIONS)
)
SCHEMA="dack_v36_observable_line_capability_features_1"

def feature_hash():
    return hashlib.sha256(json.dumps(NAMES,separators=(",",":")).encode()).hexdigest()

def extract(seven,hand,bottom,unknown,seat,stage,oldq,oldc):
    assert seat in range(4) and stage in range(7)
    assert len(seven)==7 and len(unknown)==92
    assert len(hand)==int((7,7,6,5,4,3,2)[stage])
    assert Counter(seven)==Counter(hand)+Counter(bottom)
    assert 0<=oldq<=1 and 0<=oldc<=1
    h=Counter(hand)
    source=cap.extract(tuple(hand),tuple(unknown),seat)
    values=(
       float(oldq),float(oldc),float(oldq-oldc),
       *(float(stage==k) for k in range(3)),
       *(float(seat==k) for k in range(4)),
       *source,
       *(float(h[x]>0) for x in KEY_CARDS),
       *(float(h[a]>0 and h[b]>0) for a,b in INTERACTIONS)
    )
    assert len(values)==len(NAMES) and all(math.isfinite(float(x)) for x in values)
    return tuple(values)

def selftest():
    assert len(NAMES)==3+3+4+len(cap.NAMES)+len(KEY_CARDS)+len(INTERACTIONS)
    assert len(set(NAMES))==len(NAMES)
    assert feature_hash()
    print("DACK_V36_OBSERVABLE_FEATURE_SCHEMA_PASS",len(NAMES),flush=True)

if __name__=="__main__":selftest()
