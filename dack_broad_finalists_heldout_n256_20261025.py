#!/usr/bin/env python3
"""Held-out six-finalist broad speed confirmation: N256 fresh paired game seeds.

Uses exactly the card/rules engine from 20261025 16-arm discovery. The six
arm identities are frozen. Do not treat the multi-arm screening winner as
confirmed from discovery games; held-out rerun is independent.

Outcome is T1/T2/T3 Dack deployment on an optimistic full-beam goldfish.
No assumption that Dack wins real cEDH through interaction. Native London
mulligan utility is provisional and may bias apparent small differences.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import dack_broad_speed_levers_16_20261025 as broad

SELECTED=("current","full_basalt_rainbow","double_key",
          "voltaic_candelabra","voltaic_sonic","three_untappers")
DECKS={v:broad.VARIANTS[v] for v in SELECTED}
FRESH_BASE=99144202511255
broad.VARIANTS=DECKS
broad.root.VARIANTS=DECKS
broad.root.batch.build_deck=lambda v:DECKS[v]
broad.SEED_BASE=FRESH_BASE
broad.root.batch.CONFIG["seed_base"]=FRESH_BASE

def audit():
    assert len(DECKS)==6 and len({broad.sha(v) for v in DECKS.values()})==6
    assert broad.sha(DECKS["current"])==broad.sha(broad.CURRENT)
    assert broad.sha(DECKS["full_basalt_rainbow"])==broad.sha(broad.FULL_BASALT)
    assert FRESH_BASE!=202610250122 and FRESH_BASE!=99114422887
    assert all(len(x)==99 and broad.root.COMBO.issubset(x) for x in DECKS.values())
    assert all(not {"Mana Crypt","Jeweled Lotus"}.intersection(x) for x in DECKS.values())
    assert all(x.count("Moonsilver Key")==1 and x.count("Bucknard's Everfull Purse")==1 for x in DECKS.values())
    for label,deck in DECKS.items():
        assert len([c for c in deck if c!="Plains"])==len(set(c for c in deck if c!="Plains")),label
        broad.root.install(label)
        assert len(broad.d.DECK)==99
        assert all(c in broad.d.CARD_ID for c in broad.d.DECK)
    s=broad.d.State(1,(),(),(broad.d.Perm("Pentad Prism",False,2,1),))
    first=[q for q in broad.d.tap_mana_actions(s) if q.any==1 and q.battlefield[0].counters==1 and not q.battlefield[0].tapped]
    assert first and any(q.any==2 and q.battlefield[0].counters==0 for q in broad.d.tap_mana_actions(first[0]))
    print("BROAD_HELDOUT6_AUDIT_PASS",FRESH_BASE,json.dumps({k:broad.sha(v) for k,v in DECKS.items()}),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--games",type=int,default=8)
    p.add_argument("--beam",type=int,default=160)
    p.add_argument("--out",default="broad_heldout6.json.gz")
    p.add_argument("--pool",action="store_true")
    p.add_argument("--path",default="shards")
    p.add_argument("--expected",type=int,default=256)
    args=p.parse_args()
    audit()
    if args.audit:pass
    elif args.pool:
        broad.pool(args.path,args.out,args.expected)
        q=json.loads(Path(args.out).read_text())
        assert q["status"]=="PASS" and q["n_paired"]==256 and len(q["variants"])==6
        q["trial"]="independent held-out 256 seeds; six preselected discovery finalists"
        q["screening_seed_base"]=202610250122
        q["seed_base"]=FRESH_BASE
        Path(args.out).write_text(json.dumps(q,indent=2)+"\n")
        print("BROAD_HELDOUT6_POOL_PASS",json.dumps({"n":q["n_paired"],"ranking_by_T2":q["ranking_by_T2"]}),flush=True)
    else:broad.run(args.shard,args.games,args.beam,args.out)
