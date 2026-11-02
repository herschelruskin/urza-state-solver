#!/usr/bin/env python3
"""Exhaustive finite mana-ledger parity against installed exact Dack cast gate.
No hypothetical card lines, no model fitting. Source restrictions preserved.
"""
from __future__ import annotations
import json,sys
from itertools import product
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_turn_aware_legal_mana_features_v48_20261101 as x
d=x.d
def main():
    x.v43.audit()
    library=tuple(sorted(d.COMBO_CREATURES))
    n=0
    for pearl in (False,True):
        for w,c,anycolor,legend,artifact,rdw in product(range(4),range(4),range(4),range(4),range(4),range(4)):
            bfield=(d.Perm("Pearl Medallion"),) if pearl else ()
            s=d.State(1,(),library,battlefield=bfield,w=w,c=c,any=anycolor,
                restricted_legend=legend,restricted_artifact=artifact,
                restricted_dack_white=rdw)
            m=x.mana_budget(s)
            proxy=m["white_pips_possible"]==2 and m["generic_after_WW"]>=m["commander_generic_cost"]
            assert proxy==d.can_cast_dack(s),(pearl,w,c,anycolor,legend,artifact,rdw,m)
            assert proxy==m["can_cast"],(s,m)
            n+=1
    # Negative controls: 8 artifact-only generic is not commander mana;
    # 3 colorless generic cannot cover missing white; Dack-only WW can.
    assert not d.can_cast_dack(d.State(1,(),library,c=3,restricted_artifact=20,w=1))
    assert not d.can_cast_dack(d.State(1,(),library,c=10,restricted_artifact=20))
    assert d.can_cast_dack(d.State(1,(),library,c=4,restricted_dack_white=2))
    print("DACK_V48_RESOURCE_LEDGER_EXHAUSTIVE_PARITY_PASS",
       json.dumps({"cases":n,"white_generic_ledger_matches_engine":True,
          "pearl_medallion_reduction_tested":True,
          "artifact_only_excluded":True,"legendary_and_dack_only_pools_tested":True}),flush=True)
if __name__=="__main__":main()
