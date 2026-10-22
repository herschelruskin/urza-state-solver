#!/usr/bin/env python3
"""Independent-seed N256 confirmation: six Dack land/ramp finalists.

This is not a re-use of discovery seeds; seed base is changed before
mulligan screening, shuffling, physical events, and game resolution.
Inherits the fully audited 12-arm correction for Pentad Prism no tap.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import dack_land_ramp_factorial12_20261022 as sweep

FINALISTS=("current","lands_only","ramp_only","rainbow_prism_only",
           "full_basalt_over_boulder","full_voltaic")
VARIANTS={k:sweep.VARIANTS[k] for k in FINALISTS}
sweep.VARIANTS=VARIANTS
sweep.root.VARIANTS=VARIANTS
sweep.root.batch.build_deck=lambda v:VARIANTS[v]
SEED_BASE=82210975119
# Independent of previous 20261022 discovery run's CFG seed base.
sweep.root.batch.CONFIG["seed_base"]=SEED_BASE

def audit():
    assert len(VARIANTS)==6
    assert all(len(deck)==99 and sweep.root.COMBO.issubset(deck) for deck in VARIANTS.values())
    assert all(deck.count("Moonsilver Key")==1 for deck in VARIANTS.values())
    assert all(deck.count("Bucknard's Everfull Purse")==1 for deck in VARIANTS.values())
    assert all(not {"Mana Crypt","Jeweled Lotus"}.intersection(deck) for deck in VARIANTS.values())
    assert sweep.sha(VARIANTS["current"])==sweep.sha(sweep.CURRENT)
    assert sweep.sha(VARIANTS["full_voltaic"])==sweep.sha(sweep.FULL)
    assert SEED_BASE != 0 and SEED_BASE!=7604096001
    assert len({sweep.sha(deck) for deck in VARIANTS.values()})==6
    for v,deck in VARIANTS.items():
        sweep.root.install(v)
        assert len(sweep.d.DECK)==99
        assert len(set(card for card in deck if card!="Plains"))==len([c for c in deck if c!="Plains"])
    p=sweep.d.State(1,(),(),(sweep.d.Perm("Pentad Prism",False,2,1),))
    first=[q for q in sweep.d.tap_mana_actions(p) if q.any==1 and q.battlefield[0].counters==1 and not q.battlefield[0].tapped]
    assert first and any(q.any==2 and q.battlefield[0].counters==0 for q in sweep.d.tap_mana_actions(first[0]))
    print("DACK_SIX_FINALISTS_HOLDOUT_AUDIT_PASS",SEED_BASE,FINALISTS,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--games",type=int,default=8)
    p.add_argument("--beam",type=int,default=160)
    p.add_argument("--out",default="holdout.json.gz")
    p.add_argument("--pool",action="store_true")
    p.add_argument("--path",default="shards")
    p.add_argument("--expected",type=int,default=256)
    a=p.parse_args()
    audit()
    if a.audit:pass
    elif a.pool:
        sweep.pool(a.path,a.out,a.expected)
        q=json.loads(Path(a.out).read_text())
        q["scope"]="Six finalists, independent held-out 256 matched seeds, full-beam Dack deployment; approximate London mulligans and oracle information remain potential biases. Screened twelve variants on disjoint samples."
        q["seed_base"]=SEED_BASE
        q["stage"]="confirmatory_heldout_screen"
        assert q["n_paired"]==a.expected and len(q["variants"])==6
        Path(a.out).write_text(json.dumps(q,indent=2)+"\n")
        print("DACK_HOLDOUT_N256_CONFIRM_PASS",a.expected,flush=True)
    else:sweep.run(a.shard,a.games,a.beam,a.out)
