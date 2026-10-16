#!/usr/bin/env python3
"""Paired *single-card* Bucknard return experiment on the corrected Oct 16 list.

Four distinct 1-for-1 replacements vs exactly the Oct 16 corrected current-99:
  1) Tooth of Ramos  2) Implements of Sacrifice
  3) United Battlefront  4) World Map

Uses the SAME original game IDs, 4-player free London policy, 0.5 lambda,
beam 240, Staff proliferate, new-card rules and Boonweaver combo gate.
The original Oct 16 baseline is reused from successful run 38912678782,
not regenerated with a different policy or simulator.
"""
from __future__ import annotations
import argparse
from collections import Counter
import gzip,hashlib,json
from pathlib import Path
import time

import dack_boonweaver_exact99_20261016 as root

CUTS={
    "buck_tooth":"Tooth of Ramos",
    "buck_implements":"Implements of Sacrifice",
    "buck_battlefront":"United Battlefront",
    "buck_worldmap":"World Map",
}
NEW="Bucknard's Everfull Purse"
ORIGINAL=tuple(root.CURRENT)

def replace_one(cut):
    assert ORIGINAL.count(cut)==1,(cut,ORIGINAL.count(cut))
    assert NEW not in ORIGINAL
    d=list(ORIGINAL)
    d[d.index(cut)]=NEW
    assert len(d)==99
    assert len(set(d))==len(set(ORIGINAL))
    assert sum(x in root.COMBO for x in d)==3
    return tuple(d)

VARIANTS={v:replace_one(c) for v,c in CUTS.items()}
VARIANTS["current"]=ORIGINAL
root.VARIANTS=VARIANTS
root.batch.build_deck=lambda variant:VARIANTS[variant]

def audit():
    d=root.d
    assert len(VARIANTS)==5 and len(ORIGINAL)==99
    assert d.COSTS[NEW]==(2,0,0)
    assert NEW in d.CARD_ID and d.is_artifact_perm(NEW)
    assert NEW in d.RAMP_PROTECTED
    assert root.COMBO==d.COMBO_CREATURES
    assert root.STAFF_LIFE3 and callable(d.special_actions)
    assert root.batch.CONFIG["lambda"]==0.5
    assert root.batch.CONFIG["gameplay_beam"]==240
    for variant,deck in VARIANTS.items():
        assert len(deck)==99 and deck.count(NEW)==(0 if variant=="current" else 1)
        assert root.COMBO.issubset(deck)
        assert not {"Mana Crypt","Jeweled Lotus"}.intersection(deck)
        if variant!="current":
            cut=CUTS[variant]
            assert cut not in deck
            assert Counter(deck)-Counter(ORIGINAL)==Counter([NEW])
            assert Counter(ORIGINAL)-Counter(deck)==Counter([cut])
    # Purse requires paying {1} and tapping, rolls an actual d4, and
    # hands away the source after creating 1-4 treasure tokens.
    root.m.set_trial_seed(123)
    st=d.State(1,(),tuple(root.COMBO),
               battlefield=(d.Perm(NEW),),c=1)
    direct=d.utility_actions(st)
    purse=[q for q in direct if q.treasures>=1]
    assert purse and all(1<=q.treasures<=4 and
        not any(d.effective_name(x)==NEW for x in q.battlefield)
        for q in purse)
    st=d.State(1,(),tuple(root.COMBO),
               battlefield=(d.Perm(NEW),d.Perm("Krark-Clan Ironworks")),c=1)
    kci=d.utility_actions(st)
    assert any(q.treasures in (1,2,3,4) and q.c==2 and
               NEW in q.grave for q in kci),"Purse+KCI mana line missing"
    # No source/activation mana => no treasure.
    st=d.State(1,(),tuple(root.COMBO),
               battlefield=(d.Perm(NEW),),c=0)
    assert not any(q.treasures>0 for q in d.utility_actions(st))
    print("BUCKNARD_MINIMAL_SWAP_AUDIT_PASS",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--variant",choices=tuple(VARIANTS),default="buck_tooth")
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--games",type=int,default=2)
    p.add_argument("--beam",type=int,default=240)
    p.add_argument("--out",default="bucknard_shard.json.gz")
    args=p.parse_args()
    audit()
    if args.audit:return
    assert args.games>=1 and args.shard>=0 and args.beam>=1
    root.batch.CONFIG["gameplay_beam"]=args.beam
    deck=root.install(args.variant)
    start=time.time()
    rows=[]
    for i in range(args.games):
        gid=args.shard*args.games+i
        q=root.simulate(args.variant,gid,args.beam)
        rows.append(q)
        print(json.dumps({"variant":args.variant,"game_id":gid,
                          "win_turn":q["win_turn"],"keep_n":q["keep_n"]}),flush=True)
    payload={
        "schema":"bucknard_minimal_swaps_20261016",
        "variant":args.variant,
        "cut":CUTS.get(args.variant,"NONE"),
        "add":NEW if args.variant!="current" else "NONE",
        "deck_sha256":hashlib.sha256("\n".join(deck).encode()).hexdigest(),
        "baseline_run_id":38912678782,
        "policy":root.batch.CONFIG["policy"],
        "seed_base":root.batch.CONFIG["seed_base"],
        "games":args.games,"shard":args.shard,"beam":args.beam,
        "counts":{str(k):int(v) for k,v in Counter(q["win_turn"] for q in rows).items()},
        "elapsed_sec":round(time.time()-start,3),"rows":rows
    }
    with gzip.open(args.out,"wt",encoding="utf8") as f:
        json.dump(payload,f,separators=(",",":"))
    print("BUCKNARD_MINIMAL_SWAP_SHARD_PASS",args.variant,args.games,
          payload["counts"],flush=True)

if __name__=="__main__":main()
