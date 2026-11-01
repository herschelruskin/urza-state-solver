#!/usr/bin/env python3
"""v26 larger all-stage real-outcome corpus; no 96k evaluation access."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from dack_simulator.validation import label_all_stage_keep_values_v21 as v21

v21.PROTO="DACK_V26_93K_TRAIN_94K_VALID_INDEPENDENT_8_STAGE_FUTURES"
v21.SCHEMA="dack_v26_expanded_all_stage_counterfactual_keep_values"
v21.SPLITS={
    "train":(93000,93255),
    "validation":(94000,94063),
}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--split",choices=tuple(v21.SPLITS),required=True)
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--games",type=int,default=8)
    p.add_argument("--draws",type=int,default=4)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    if a.draws!=4 or a.games!=8:
        raise ValueError("frozen v26 sampling protocol requires 8 groups x 4 future outcomes")
    v21.generate(a.start,a.games,a.out,split=a.split,draws=a.draws)
