#!/usr/bin/env python3
"""Matched rainbow-land + Pentad Prism factorial experiment, exact current 99.

Four arms:
current: original Boonweaver 34-land list (Bucknard and Coalition included)
rainbow: Urza's Cave -> Mana Confluence, Fomori Vault -> City of Brass,
         Emergence Zone -> Gemstone Mine (3 lands, no land-count change)
prism: Implements of Sacrifice -> Pentad Prism
rainbow_prism: all four swaps

Fix an inherited rules bug for EVERY arm: Pentad Prism's activated mana ability
removes a counter but does NOT tap. This correction is validated by exact
two-counters-same-turn tests. Original historical engines remain unchanged.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,math,time
from collections import Counter
from pathlib import Path
from dataclasses import replace
import dack_map_to_plains_paired_20261021 as base

root=base.root
d=root.d
m=root.m
swap=base.prev.swap
CURRENT=base.CURRENT

RAINBOW=CURRENT
SWAPS=(
    ("Urza's Cave","Mana Confluence"),
    ("Fomori Vault","City of Brass"),
    ("Emergence Zone","Gemstone Mine"),
)
for removed,added in SWAPS:
    RAINBOW=swap(RAINBOW,removed,added)
PRISM=swap(CURRENT,"Implements of Sacrifice","Pentad Prism")
RAINBOW_PRISM=swap(RAINBOW,"Implements of Sacrifice","Pentad Prism")
VARIANTS={"current":CURRENT,"rainbow":RAINBOW,
          "prism":PRISM,"rainbow_prism":RAINBOW_PRISM}
root.VARIANTS=VARIANTS
root.batch.build_deck=lambda name:VARIANTS[name]

ORIGINAL_TAP=d.tap_mana_actions
PRISM_REPAIR_WITNESSES=0
def corrected_tap(s):
    global PRISM_REPAIR_WITNESSES
    raw=ORIGINAL_TAP(s)
    out=[]
    for q in raw:
        after=list(q.battlefield)
        modified=False
        if len(s.battlefield)==len(after) and q.any==s.any+1:
            for i,p in enumerate(s.battlefield):
                if (d.effective_name(p)=="Pentad Prism" and
                    not p.tapped and p.counters>0 and
                    after[i].name==p.name and after[i].tapped and
                    after[i].counters==p.counters-1):
                    after[i]=replace(after[i],tapped=False)
                    modified=True
        if modified:
            PRISM_REPAIR_WITNESSES+=1
            q=replace(q,battlefield=tuple(after))
        out.append(q)
    seen=set(); unique=[]
    for state in out:
        key=d.key(state)
        if key not in seen:
            seen.add(key);unique.append(state)
    return unique
d.tap_mana_actions=corrected_tap

def sha(deck):return hashlib.sha256("\n".join(deck).encode()).hexdigest()

def audit():
    assert len(CURRENT)==99
    assert set(VARIANTS)=={"current","rainbow","prism","rainbow_prism"}
    assert CURRENT.count("Plains")==10
    for key,deck in VARIANTS.items():
        assert len(deck)==99
        assert root.COMBO.issubset(deck)
        assert deck.count("Bucknard's Everfull Purse")==1 and deck.count("Coalition Relic")==1
        assert not {"Jeweled Lotus","Mana Crypt"}.intersection(deck)
        root.install(key)
        assert all(x in d.CARD_ID for x in d.DECK)
        assert sum(x in d.LANDS or x in ("Emeria's Call","Razorgrass Ambush") for x in deck)==34,(key,"land_count")
    assert Counter(RAINBOW)-Counter(CURRENT)==Counter(x[1] for x in SWAPS)
    assert Counter(CURRENT)-Counter(RAINBOW)==Counter(x[0] for x in SWAPS)
    assert Counter(PRISM)-Counter(CURRENT)==Counter(["Pentad Prism"])
    assert Counter(CURRENT)-Counter(PRISM)==Counter(["Implements of Sacrifice"])
    assert Counter(RAINBOW_PRISM)-Counter(CURRENT)==Counter([x[1] for x in SWAPS]+["Pentad Prism"])
    # 2 color mana generates 2 sunburst charges: original engine already implements this.
    state=d.State(1,("Pentad Prism",),(),w=1,any=1)
    casts=[q for q in d.cast_actions(state) if any(d.effective_name(p)=="Pentad Prism" and p.counters==2 for p in q.battlefield)]
    assert casts, "two-color sunburst missing"
    prism=d.State(1,(),(),battlefield=(d.Perm("Pentad Prism",False,2),))
    one=[q for q in d.tap_mana_actions(prism) if q.any==1 and q.battlefield[0].counters==1 and not q.battlefield[0].tapped]
    assert one,"Prism counter one must NOT tap permanent"
    two=[q for q in d.tap_mana_actions(one[0]) if q.any==2 and q.battlefield[0].counters==0 and not q.battlefield[0].tapped]
    assert two,"Prism counter two must be spendable in same turn"
    # Legacy function has precisely the bug addressed.
    bad=[q for q in ORIGINAL_TAP(prism) if q.any==1 and q.battlefield[0].counters==1 and q.battlefield[0].tapped]
    assert bad,"regression basis absent"
    assert d.COSTS["Pentad Prism"]==(2,0,0)
    print("DACK_RAINBOW_PRISM_EXACT99_AUDIT_PASS",json.dumps({k:sha(v) for k,v in VARIANTS.items()}),flush=True)

def simulate(variant,gid,beam):
    root.install(variant)
    d._WIN_CACHE.clear()
    return root.simulate(variant,gid,beam)

def run(shard,games,beam,out):
    data=[]
    start=time.time()
    for j in range(games):
        gid=shard*games+j
        rows={}
        for variant in VARIANTS:
            rows[variant]=simulate(variant,gid,beam)
            print("GAME",variant,gid,rows[variant]["win_turn"],rows[variant]["keep_n"],flush=True)
        data.append({"gid":gid,**rows})
    obj={"schema":"dack_rainbow_prism_corrected_v1","shard":shard,"games":games,"beam":beam,
         "source_seed":root.batch.CONFIG["seed_base"],
         "deck_sha":{k:sha(v) for k,v in VARIANTS.items()},
         "results":data,"elapsed_sec":round(time.time()-start,2)}
    with gzip.open(out,"wt",encoding="utf8") as f:json.dump(obj,f,separators=(",",":"))
    print("RAINBOW_PRISM_SHARD_PASS",shard,games,round(time.time()-start,2),flush=True)

def pool(path,out,expected):
    data={}; hashes=None; beams=set()
    files=sorted(Path(path).rglob("*.json.gz"))
    assert files,"missing shards"
    for file in files:
        with gzip.open(file,"rt") as f:q=json.load(f)
        assert q["schema"]=="dack_rainbow_prism_corrected_v1"
        assert len(q["results"])==q["games"]
        if hashes is None:hashes=q["deck_sha"]
        assert hashes==q["deck_sha"]
        beams.add(q["beam"])
        for rec in q["results"]:
            gid=rec["gid"];assert gid not in data
            for v in VARIANTS:
                assert rec[v]["game_id"]==gid
                assert rec[v]["seed"]==q["source_seed"]+gid*1000003
            data[gid]=rec
    assert len(beams)==1
    assert set(data)==set(range(expected)),(len(data),expected)
    report={"status":"PASS","n":len(data),"beam":list(beams)[0],"deck_sha":hashes,
        "scope":"Historical full-beam T1-T3 Dack deployment, with corrected Pentad Prism no-tap ability. Deck selection/mulligans still subject to approximate oracle/threshold bias.",
        "swaps":{"rainbow":SWAPS,"prism":["Implements of Sacrifice","Pentad Prism"]}}
    n=len(data)
    for v in VARIANTS:
        c=Counter(data[i][v]["win_turn"] for i in data)
        report[v]={"counts":{str(t):c[t] for t in range(4)},
             **{f"by_T{t}_pct":round(100*sum(c[k] for k in range(1,t+1))/n,4) for t in (1,2,3)},
             "mean_keep":round(sum(data[i][v]["keep_n"] for i in data)/n,4)}
    def paired(v1,v0):
        dct={}
        for t in (1,2,3):
            changes=[int(0<data[i][v1]["win_turn"]<=t)-int(0<data[i][v0]["win_turn"]<=t) for i in data]
            gain=changes.count(1);loss=changes.count(-1)
            mu=(gain-loss)/n
            se=math.sqrt(sum((x-mu)**2 for x in changes)/(n-1)/n) if n>1 else 0
            dct[f"by_T{t}"]={"delta_pp":round(100*mu,4),
                "paired_95pct_pp":[round(100*(mu-1.96*se),3),round(100*(mu+1.96*se),3)],
                "gains":gain,"losses":loss}
        return dct
    report["paired"]={
        "rainbow_minus_current":paired("rainbow","current"),
        "prism_minus_current":paired("prism","current"),
        "rainbow_prism_minus_current":paired("rainbow_prism","current"),
        "rainbow_prism_minus_rainbow":paired("rainbow_prism","rainbow"),
        "rainbow_prism_minus_prism":paired("rainbow_prism","prism"),
    }
    Path(out).write_text(json.dumps(report,indent=2))
    print("RAINBOW_PRISM_POOLED_PASS",json.dumps(report),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--games",type=int,default=8)
    p.add_argument("--beam",type=int,default=160)
    p.add_argument("--out",default="rainbow_prism.json.gz")
    p.add_argument("--pool",action="store_true")
    p.add_argument("--path",default="shards")
    p.add_argument("--expected",type=int,default=64)
    a=p.parse_args()
    audit()
    if a.audit:pass
    elif a.pool:pool(a.path,a.out,a.expected)
    else:run(a.shard,a.games,a.beam,a.out)
