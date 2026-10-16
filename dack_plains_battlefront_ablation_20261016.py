#!/usr/bin/env python3
"""Exactly matched 1-/2-/3-slot ablations for lands and Battlefront.

N512 per arm under frozen corrected 2026-10-16 Dack Boonweaver simulator.
Baseline is preserved unchanged. All edits are explicitly enumerated below.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import argparse,gzip,hashlib,json,time
import dack_boonweaver_exact99_20261016 as root

ORIGINAL=tuple(root.CURRENT)
BUCK="Bucknard's Everfull Purse"
GENERIC="Generic 2C Rock"
SWAPS={
    "map_plains":(("World Map","Plains"),),
    "partition_plains":(("Soul Partition","Plains"),),
    "tithe_plains":(("Mana Tithe","Plains"),),
    "double_plains":(("Soul Partition","Plains"),("Mana Tithe","Plains")),
    "battlefront_generic":(("United Battlefront",GENERIC),),
    "buck_double_plains":(("World Map",BUCK),("Soul Partition","Plains"),("Mana Tithe","Plains")),
    "buck_battlefront_generic":(("World Map",BUCK),("United Battlefront",GENERIC)),
}

def altered(spec):
    d=list(ORIGINAL)
    for cut,add in spec:
        assert d.count(cut)==1,(cut,d.count(cut))
        assert add not in root.COMBO
        d[d.index(cut)]=add
    assert len(d)==99
    assert root.COMBO.issubset(d)
    assert not {"Mana Crypt","Jeweled Lotus"}.intersection(d)
    return tuple(d)

VARIANTS={"current":ORIGINAL}
VARIANTS.update({v:altered(spec) for v,spec in SWAPS.items()})
root.VARIANTS=VARIANTS
root.batch.build_deck=lambda variant:VARIANTS[variant]

def audit():
    d=root.d
    assert len(VARIANTS)==8
    assert root.STAFF_LIFE3 and callable(d.special_actions)
    assert root.batch.CONFIG["lambda"]==0.5
    assert root.batch.CONFIG["gameplay_beam"]==240
    assert len(ORIGINAL)==99 and ORIGINAL.count("Plains")==10
    assert d.COSTS[GENERIC]==(2,0,0),d.COSTS[GENERIC]
    assert d.is_artifact_perm(GENERIC)
    assert BUCK in d.CARD_ID and d.COSTS[BUCK]==(2,0,0)
    assert root.COMBO==d.COMBO_CREATURES
    for v,deck in VARIANTS.items():
        changes=SWAPS.get(v,())
        assert len(deck)==99 and set(root.COMBO).issubset(deck)
        expected=Counter(ORIGINAL)
        for cut,add in changes:
            expected[cut]-=1
            expected[add]+=1
        assert Counter(deck)==+expected,(v,"bad changes")
        assert deck.count("Plains")==10+sum(add=="Plains" for cut,add in changes)
        assert deck.count(BUCK)==sum(add==BUCK for cut,add in changes)
        assert deck.count(GENERIC)==sum(add==GENERIC for cut,add in changes)
    # The generic rock must actually be castable for 2 generic and tap for 1C.
    st=d.State(1,(GENERIC,),tuple(root.COMBO),c=2)
    casts=[q for q in d.cast_actions(st)
           if any(x.name==GENERIC for x in q.battlefield)]
    assert casts, "generic 2C rock wasn't cast"
    taps=[z for q in casts for z in d.tap_mana_actions(q)]
    assert any(q.c==1 for q in taps), "generic 2C rock lacks tap for 1C"
    # Bucknard and Staff remain live in all tests.
    st=d.State(1,(),tuple(root.COMBO),battlefield=(d.Perm(BUCK),),c=1)
    assert any(q.treasures>0 for q in d.utility_actions(st))
    st=d.State(1,(),tuple(root.COMBO),battlefield=(d.Perm("Staff of Compleation"),d.Perm("Urza's Saga",False,2)))
    assert any(any(x.name=="Urza's Saga" and x.aux=="SAGA3" for x in q.battlefield)
               for q in d.special_actions(st))
    print("PLAINS_BATTLEFRONT_EXACT_ABLATION_AUDIT_PASS",flush=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",action="store_true")
    ap.add_argument("--variant",choices=tuple(VARIANTS),default="map_plains")
    ap.add_argument("--shard",type=int,default=0)
    ap.add_argument("--games",type=int,default=32)
    ap.add_argument("--beam",type=int,default=240)
    ap.add_argument("--out",default="ablation_shard.json.gz")
    a=ap.parse_args()
    audit()
    if a.audit:return
    assert a.shard>=0 and a.games>=1 and a.beam>0
    deck=root.install(a.variant)
    root.batch.CONFIG["gameplay_beam"]=a.beam
    start=time.time()
    rows=[]
    for j in range(a.games):
        gid=a.shard*a.games+j
        q=root.simulate(a.variant,gid,a.beam)
        rows.append(q)
        print(json.dumps({"variant":a.variant,"gid":gid,"turn":q["win_turn"],"keep":q["keep_n"]}),flush=True)
    payload={
        "schema":"plains_battlefront_ablation_20261016",
        "variant":a.variant,
        "swaps":SWAPS.get(a.variant,()),
        "deck_sha256":hashlib.sha256("\n".join(deck).encode()).hexdigest(),
        "baseline_run_id":38912678782,
        "seed_base":root.batch.CONFIG["seed_base"],
        "policy":root.batch.CONFIG["policy"],
        "beam":a.beam,"games":a.games,"shard":a.shard,
        "counts":{str(k):int(v) for k,v in Counter(q["win_turn"] for q in rows).items()},
        "elapsed_sec":round(time.time()-start,3),
        "rows":rows}
    with gzip.open(a.out,"wt",encoding="utf8") as f:
        json.dump(payload,f,separators=(",",":"))
    print("PLAINS_BATTLEFRONT_SHARD_PASS",a.variant,a.games,payload["counts"],flush=True)

if __name__=="__main__":main()
