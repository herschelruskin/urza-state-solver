#!/usr/bin/env python3
"""Independent-seed Dack 4-finalist confirmation; standard N512 + fixed-mulligan N256.

The fixed-stage diagnostic removes differential *keep stage* choices:
each seed uses the CURRENT deck's free-London accepted stage for all arms,
while every deck receives its own correct cards and legal London bottoming.
This is NOT an optimized policy for each variant, and may favor reference.
It helps diagnose whether a reported difference is caused by stage selection.

The standard experiment retains each deck's own mulligan decisions.
All cards are singleton-legal, T1–T3 Dack deployment with combo trio in library.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,math,random,time
from pathlib import Path
from collections import Counter
import dack_land_ramp_factorial12_20261022 as study

root=study.root
d=study.d
m=study.m
batch=root.batch
NAMES=("current","ramp_only","full_basalt_over_boulder","full_voltaic")
DECKS={k:study.VARIANTS[k] for k in NAMES}
study.VARIANTS=DECKS
root.VARIANTS=DECKS
batch.build_deck=lambda v:DECKS[v]
SEED_BASE=99114422887
assert batch.CONFIG["seed_base"]!=SEED_BASE
batch.CONFIG["seed_base"]=SEED_BASE
STAGES=(7,7,6,5,4,3,2,1)
def sha(cards):return hashlib.sha256("\n".join(cards).encode()).hexdigest()
def audit():
    assert len(DECKS)==4
    assert sha(DECKS["current"])==sha(study.CURRENT)
    assert sha(DECKS["full_voltaic"])==sha(study.FULL)
    assert len({sha(v) for v in DECKS.values()})==4
    assert all(len(v)==99 and root.COMBO.issubset(v) for v in DECKS.values())
    assert all(v.count("Bucknard's Everfull Purse")==1 and v.count("Moonsilver Key")==1 for v in DECKS.values())
    assert all(not {"Mana Crypt","Jeweled Lotus"}.intersection(v) for v in DECKS.values())
    assert all(len([n for n in v if n!="Plains"])==len(set(n for n in v if n!="Plains")) for v in DECKS.values())
    for k in DECKS:root.install(k);assert len(d.DECK)==99
    assert batch.CONFIG["lambda"]==0.5
    assert SEED_BASE not in (82210975119,)
    s=d.State(1,(),(),(d.Perm("Pentad Prism",False,2,1),))
    p=[q for q in d.tap_mana_actions(s) if q.any==1 and not q.battlefield[0].tapped and q.battlefield[0].counters==1]
    assert p and any(q.any==2 and q.battlefield[0].counters==0 for q in d.tap_mana_actions(p[0]))
    print("DACK_FINALIST4_MULL_CONTROL_AUDIT_PASS",json.dumps({k:sha(v) for k,v in DECKS.items()}),flush=True)

def fixed_stage_game(v,gid,stage,beam):
    root.install(v)
    seed=batch.CONFIG["seed_base"]+int(gid)*1000003
    m.set_trial_seed(seed)
    rng=random.Random(seed)
    seat=rng.randrange(4)
    assert 0<=stage<8
    last=None
    for i,keep_n in enumerate(STAGES):
        cards=list(d.DECK)
        rng.shuffle(cards)
        seven,rest=cards[:7],cards[7:]
        # Evaluate every earlier stage just as standard London does. This
        # preserves deterministic draw/evaluator side effects for replay.
        raw,ev,struct,hand,bottom,unknown,_,refined=batch.evaluate_keep(seven,keep_n,rest,seat)
        if i==stage:
            state=d.State(1,tuple(hand),tuple(unknown)+tuple(bottom))
            last=(keep_n,raw,seat,state)
            break
    assert last is not None
    keep_n,raw,seat,state=last
    d._WIN_CACHE.clear()
    turn=d._win_turn_from_unknown_order(state.hand,state.library,seat,beam=beam,max_turn=3)
    return {"game_id":int(gid),"seed":seed,"seat":seat,
            "keep_n":keep_n,"fixed_stage":stage,
            "win_turn":int(turn or 0),"utility":round(float(raw),5)}
def run(shard,games,beam,out):
    records=[];started=time.time()
    for i in range(games):
        gid=shard*games+i
        native={}
        for v in NAMES:
            root.install(v);d._WIN_CACHE.clear()
            native[v]=root.simulate(v,gid,beam)
            print("NATIVE",v,gid,native[v]["win_turn"],native[v]["keep_n"],flush=True)
        rec={"gid":gid,"native":native}
        if gid<256:
            stage=len(native["current"]["audit"])-1
            fixed={"current":{"game_id":gid,
                               "seed":native["current"]["seed"],
                               "seat":native["current"]["seat"],
                               "keep_n":native["current"]["keep_n"],
                               "fixed_stage":stage,
                               "win_turn":native["current"]["win_turn"]}}
            for v in NAMES[1:]:
                fixed[v]=fixed_stage_game(v,gid,stage,beam)
                print("FIXED_KEEP",v,gid,stage,fixed[v]["win_turn"],fixed[v]["keep_n"],flush=True)
                assert fixed[v]["seat"]==native["current"]["seat"]
                assert fixed[v]["keep_n"]==native["current"]["keep_n"]
            rec["fixed"]=fixed
        records.append(rec)
    doc={"schema":"dack_finalist4_native512_fixed256_v1","shard":shard,
         "games":games,"beam":beam,"seed_base":SEED_BASE,
         "hashes":{k:sha(v) for k,v in DECKS.items()},
         "records":records,"duration_sec":round(time.time()-started,2)}
    with gzip.open(out,"wt",encoding="utf8") as f:json.dump(doc,f,separators=(",",":"))
    print("DACK_FINALIST4_SHARD_PASS",shard,games,round(time.time()-started,2),flush=True)

def describe(data,mode,ids):
    n=len(ids)
    assert n>1
    doc={"n":n,"arms":{},"paired_vs_current":{},"paired_basalt_vs_boulder":{}}
    for v in NAMES:
        counts=Counter(data[i][mode][v]["win_turn"] for i in ids)
        doc["arms"][v]={"counts":{str(x):counts[x] for x in range(4)},
             "by_T1_pct":round(100*counts[1]/n,4),
             "by_T2_pct":round(100*(counts[1]+counts[2])/n,4),
             "by_T3_pct":round(100*(counts[1]+counts[2]+counts[3])/n,4),
             "T2_plus_half_T3_only_pct":round(100*(counts[1]+counts[2]+.5*counts[3])/n,4)}
    def compare(v,base):
        result={}
        for turn in (1,2,3):
            x=[int(0<data[i][mode][v]["win_turn"]<=turn)-int(0<data[i][mode][base]["win_turn"]<=turn) for i in ids]
            gain=x.count(1);loss=x.count(-1);mu=(gain-loss)/n
            se=math.sqrt(sum((z-mu)**2 for z in x)/(n-1)/n)
            result[f"T{turn}"]={"delta_pp":round(mu*100,4),"gains":gain,"losses":loss,
                 "paired_95_ci_pp":[round(100*(mu-1.96*se),3),round(100*(mu+1.96*se),3)],
                 "discordant_keep_n_changed":sum(data[i][mode][v]["keep_n"]!=data[i][mode][base]["keep_n"] for i in ids if x[i])}
        return result
    for v in NAMES[1:]:doc["paired_vs_current"][v]=compare(v,"current")
    doc["paired_basalt_vs_boulder"]=compare("full_basalt_over_boulder","full_voltaic")
    return doc
def pool(path,out,expected):
    files=sorted(Path(path).rglob("*.json.gz"));assert files
    rows={}; hashes=None; beamset=set()
    for file in files:
        with gzip.open(file,"rt") as f:q=json.load(f)
        assert q["schema"]=="dack_finalist4_native512_fixed256_v1"
        assert q["seed_base"]==SEED_BASE
        if hashes is None:hashes=q["hashes"]
        assert q["hashes"]==hashes
        beamset.add(q["beam"])
        assert len(q["records"])==q["games"]
        for rec in q["records"]:
            gid=rec["gid"];assert gid not in rows
            for v in NAMES:
                assert rec["native"][v]["game_id"]==gid
                assert rec["native"][v]["seed"]==SEED_BASE+gid*1000003
            if gid<256:
                assert "fixed" in rec
                for v in NAMES:
                    assert rec["fixed"][v]["game_id"]==gid
                    assert rec["fixed"][v]["keep_n"]==rec["native"]["current"]["keep_n"]
            else:assert "fixed" not in rec
            rows[gid]=rec
    assert len(beamset)==1 and set(rows)==set(range(expected))
    assert expected>=256
    report={"status":"PASS","seed_base":SEED_BASE,"n":expected,
      "beam":next(iter(beamset)),"deck_hashes":hashes,
      "caveats":"Full-beam optimistic goldfish Dack deployment, no multiplayer/validated full combo. Native mulligan optimization is approximate. Fixed-stage diagnostic uses baseline chosen London stage for all arms (favors baseline, not independent optimal policies), but allows each candidate proper bottoming.",
      "normal":{"explanation":"Each deck follows its own free multiplayer London mulligan heuristic on new paired seeds.",**describe(rows,"native",list(range(expected)))},
      "fixed_stage":{"explanation":"For the first 256 independent seeds, all variants are forced to the baseline's accepted London stage, but use their own cards and legal bottoming.",**describe(rows,"fixed",list(range(256)))}}
    Path(out).write_text(json.dumps(report,indent=2)+"\n")
    print("DACK_FINALIST4_POOLED_PASS",json.dumps({"normal":report["normal"],"fixed_stage":report["fixed_stage"]}),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--games",type=int,default=16)
    p.add_argument("--beam",type=int,default=160)
    p.add_argument("--out",default="finalist4.json.gz")
    p.add_argument("--pool",action="store_true")
    p.add_argument("--path",default="shards")
    p.add_argument("--expected",type=int,default=512)
    a=p.parse_args()
    audit()
    if a.audit:pass
    elif a.pool:pool(a.path,a.out,a.expected)
    else:run(a.shard,a.games,a.beam,a.out)
