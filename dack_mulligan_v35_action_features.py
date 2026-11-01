#!/usr/bin/env python3
"""v35 fixed 19-dimensional action regret correction. No exact card-ID memorization.

A decision is observable only from stage, seat, seven, fixed v33b
legal retained hand, known unknown-92 *multiset*, frozen v27 Qkeep and C.
The feature vector is intentionally much smaller than v27's 347
features and never serves as an actual-game state fingerprint.
"""
from __future__ import annotations
import hashlib,json,math
import dack_mulligan_v33b_capability_regret_features as cf

NAMES=(
  "intercept",
  "old_Qkeep_minus_old_C",
  "old_Qkeep",
  "stage_0","stage_1","stage_2",
  "seat_0","seat_1","seat_2",
  "land_count","white_land_count","two_mana_lands",
  "fast_ramp","zero_mana","tutors",
  "chrome_imprint","opal_metalcraft",
  "combo_brick","proxy_T2",
)
N=len(NAMES)
SELECT=(0,1,2,6,7,9,3,4,19,20,22,5)
assert len(NAMES)==19
EARLY=(0,1,2)

def hash_names():
    return hashlib.sha256(json.dumps(NAMES,separators=(",",":")).encode()).hexdigest()

def extract(stage,seat,seven,hand,unknown,old_q,old_c):
    assert stage in range(7) and seat in range(4)
    assert len(seven)==7 and len(unknown)==92
    assert len(hand)==int((7,7,6,5,4,3,2)[stage])
    assert 0<=old_q<=1 and 0<=old_c<=1
    z=cf.extract(tuple(hand),tuple(unknown),seat)
    values=(
       1.,old_q-old_c,old_q,
       float(stage==0),float(stage==1),float(stage==2),
       float(seat==0),float(seat==1),float(seat==2),
       z[0],z[1],z[2],
       z[6],z[7],z[9],
       z[18],z[19],z[22],z[5],
    )
    assert len(values)==N and all(math.isfinite(float(v)) for v in values)
    return tuple(float(v) for v in values)

def selftest():
    assert hash_names() and len(NAMES)==19
    assert NAMES[1]=="old_Qkeep_minus_old_C"
    import dack_paired_counterfactual_v33b_regret_bottom_only_20261101 as d
    assert d.audit()["status"]=="PASS"
    ref=d.ref
    seven=("Plains","Ancient Tomb","Chrome Mox","Void Mirror",
           "Lion's Eye Diamond","Boonweaver Giant","Mox Opal")
    from collections import Counter
    deck=Counter(ref.VARIANTS["one_key_34"])
    for c in seven:
        assert deck[c];deck[c]-=1
    unseen=tuple(c for c,n in deck.items() for _ in range(n))
    assert len(unseen)==92
    for stage in range(7):
        hand=seven[:int(ref.sim.STAGES[stage])]
        x=extract(stage,2,seven,hand,unseen,.4,.3)
        assert len(x)==N
        assert x[1]==.4-.3
    print("DACK_V35_NINETEEN_CAPABILITY_FEATURE_SELFTEST_PASS",flush=True)

if __name__=="__main__":
    selftest()
