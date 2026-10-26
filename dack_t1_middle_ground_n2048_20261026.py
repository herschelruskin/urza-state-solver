#!/usr/bin/env python3
"""Dack middle-ground T1 policy sweep: matched, isolated, resumable N2048.

All four policies use EXACTLY the same evaluated London hand and bottom for
each sequential stage, same shuffled 99, one free mulligan and seat. No
differences in cards, game engine, draw order or beam. Only the keep/mull
threshold changes; T1-positive hands that the native policy would keep are
grandfathered in, so we never reject known prospective T1 keeps in pursuit
of hypothetical better 7s. The 3 candidate policies are exploratory, not
optimally calibrated continuation values.

Outcome = optimistic goldfish Dack CAST with combo-trio library requirement;
not a mechanically certified combo win or actual 4-player win probability.
"""
from __future__ import annotations
import argparse, collections, gc, gzip, hashlib, json, math, os, random, time
from pathlib import Path
import dack_t1_hypergeo_paired_n10000_20261025 as base

root, d, m, batch = base.root, base.d, base.m, base.batch
DECK=base.DECK
HASH=base.HASH
SCHEMA="dack_t1_middle_ground_paired_v1"
SEED_BASE=20261026175233
BEAM=160
N=2048
GAMES_PER_SHARD=32
STAGES=(7,7,6,5,4,3,2,1)
POLICIES={
    "native":{7:0.0,6:0.0,5:0.0,4:0.0},
    "gentle":{7:0.060,6:0.035,5:0.000,4:0.0},
    "balanced":{7:0.120,6:0.070,5:0.025,4:0.0},
    "assertive":{7:0.200,6:0.120,5:0.055,4:0.015},
}
root.VARIANTS={"current":DECK}
batch.build_deck=lambda name:DECK
batch.CONFIG["seed_base"]=SEED_BASE

def audit():
    base.audit()
    assert N==GAMES_PER_SHARD*64
    assert HASH==base.EXPECTED_HASH
    assert set(POLICIES)=={"native","gentle","balanced","assertive"}
    assert SEED_BASE != base.SEED_BASE
    assert all(v>=0 for bump in POLICIES.values() for v in bump.values())
    assert all(POLICIES[k][7]>=POLICIES[k][6]>=POLICIES[k][5]>=POLICIES[k][4]
               for k in POLICIES)
    assert batch.CONFIG["lambda"]==0.5
    print("MIDDLE_AUDIT_PASS",json.dumps({"deck":HASH,"seed":SEED_BASE,"n":N,"beam":BEAM,"policies":POLICIES}),flush=True)

def stage_evals(gid, seed_override=None):
    root.install("current")
    seed=(SEED_BASE if seed_override is None else seed_override)+gid*1000003
    m.set_trial_seed(seed)
    rng=random.Random(seed)
    seat=rng.randrange(4)
    found={}
    history=[]
    for stage,k in enumerate(STAGES):
        deck=list(d.DECK);rng.shuffle(deck)
        seven,rest=deck[:7],deck[7:]
        raw,ev,struct,hand,bottom,unknown,unused,refined=batch.evaluate_keep(seven,k,rest,seat)
        assert len(hand)==k and len(unknown)==92 and len(bottom)==7-k
        standard=0.0 if k==1 else batch.FROZEN_CONTINUATION[k-1]
        # Exactly mimic the previously published native policy.
        native_keep=(k==1 or float(raw)>=standard)
        # Sampling noise around T1=0.125 is accepted as a diagnostic proxy,
        # not a proof of winning on T1.
        sampled_t1=float(ev["t1"])
        row={"stage":stage,"keep_n":k,"raw":round(float(raw),6),
             "sampled_T1":round(sampled_t1,6),
             "threshold":standard,"refined":bool(refined),
             "native_keep":native_keep}
        history.append(row)
        for name,bumps in POLICIES.items():
            if name in found:continue
            bump=bumps.get(k,0.0)
            # A T1-positive native keep cannot be rejected by any candidate.
            actual_threshold=standard+(0 if sampled_t1>0 and native_keep else bump)
            accept=(k==1 or float(raw)>=actual_threshold)
            if accept:
                found[name]={"game_id":gid,"seed":seed,"seat":seat,
                             "keep_n":k,"stage":stage,"hand":list(hand),
                             "library":tuple(unknown)+tuple(bottom),
                             "sampled_t1":sampled_t1,"keep_utility":round(float(raw),6),
                             "threshold":round(actual_threshold,6)}
        if len(found)==len(POLICIES):break
    assert set(found)==set(POLICIES)
    assert found["native"]["stage"]==next(r["stage"] for r in history if r["native_keep"])
    # Monotonic more aggressive caps guarantee deeper or equal keep stages.
    assert (found["gentle"]["stage"]>=found["native"]["stage"] and
            found["balanced"]["stage"]>=found["gentle"]["stage"] and
            found["assertive"]["stage"]>=found["balanced"]["stage"])
    return found,history

def simulate(gid,seed_override=None):
    found,history=stage_evals(gid,seed_override)
    results={}
    solved={}
    for name,rec in found.items():
        # Solve identical kept hands once, not four times. Exact state, same
        # seat and full ordered library; no cross-policy future look-ahead.
        key=(tuple(rec["hand"]),rec["library"],rec["seat"])
        if key not in solved:
            d._WIN_CACHE.clear()
            turn=d._win_turn_from_unknown_order(key[0],key[1],key[2],
                                                  beam=BEAM,max_turn=3)
            solved[key]=int(turn or 0)
        results[name]={k:v for k,v in rec.items() if k!="library"}
        results[name]["win_turn"]=solved[key]
        results[name]["first3"]=list(rec["library"][:3])
    return {"gid":gid,"results":results,"stages":history}

def reset_caches():
    base.reset_caches()

def smoke_parity():
    """Check reused native against frozen Oct-25 baseline on identical seeds."""
    path=Path("benchmark_results/dack_t1_hypergeo_n10000_report.raw.json.gz")
    assert path.is_file(),"frozen baseline raw benchmark unavailable"
    with gzip.open(path,"rt",encoding="utf8") as f:
        old=json.load(f)
    assert old["deck_hash"]==HASH and old["seed_base"]==base.SEED_BASE
    oldrows=old["rows"]
    for gid in (0,1,2,23,75):
        reset_caches()
        trial=simulate(gid,seed_override=base.SEED_BASE)
        native=trial["results"]["native"]
        reference=oldrows[gid]["native"]
        assert native["seat"]==reference["seat"],(gid,"seat")
        assert native["keep_n"]==reference["keep_n"],(gid,"keep_n")
        assert native["win_turn"]==reference["win_turn"],(gid,"win_turn")
        assert native["hand"]==reference["hand"],(gid,"hand")
    print("FROZEN_NATIVE_REPLAY_PARITY_PASS",flush=True)

def run(shard,games,path):
    audit()
    assert games==GAMES_PER_SHARD and 0<=shard<N//games
    dest=Path(path)
    dest.parent.mkdir(parents=True,exist_ok=True)
    checkpoint=dest.with_suffix("").with_suffix(".jsonl")
    start=shard*GAMES_PER_SHARD
    rows=[]
    if checkpoint.exists():
        rows=[json.loads(s) for s in checkpoint.read_text().splitlines() if s.strip()]
        assert all(row["gid"]==start+i for i,row in enumerate(rows))
    if dest.exists() and len(rows)==games:
        print("SHARD_ALREADY_COMPLETE",shard,flush=True);return
    started=time.time()
    with checkpoint.open("a",encoding="utf8") as f:
        for j in range(len(rows),games):
            gid=start+j
            reset_caches()
            rec=simulate(gid)
            assert rec["gid"]==gid
            assert all(rec["results"][p]["seed"]==SEED_BASE+gid*1000003 for p in POLICIES)
            assert len({rec["results"][p]["seat"] for p in POLICIES})==1
            f.write(json.dumps(rec,separators=(",",":"))+"\n")
            f.flush();os.fsync(f.fileno())
            rows.append(rec)
            print("MIDDLE_PAIRED",gid," ".join(f"{k}:{rec['results'][k]['win_turn']}({rec['results'][k]['keep_n']})" for k in POLICIES),round(time.time()-started,2),flush=True)
    out={"schema":SCHEMA,"shard":shard,"games":games,"seed_base":SEED_BASE,
         "beam":BEAM,"deck_hash":HASH,"policy_bumps":POLICIES,
         "rows":rows,"elapsed_sec":round(time.time()-started,2)}
    tmp=Path(str(dest)+".tmp")
    with tmp.open("wb") as raw:
        with gzip.GzipFile(filename="",mode="wb",fileobj=raw,mtime=0) as z:
            z.write(json.dumps(out,separators=(",",":")).encode())
        raw.flush();os.fsync(raw.fileno())
    os.replace(tmp,dest)
    print("SHARD_PASS",shard,games,round(time.time()-started,2),flush=True)

def wilson(k,n):
    return base.wilson(k,n)

def paired(a,b,t):
    ids=sorted(a)
    z=[int(0<a[i]["results"][b]["win_turn"]<=t)-
       int(0<a[i]["results"]["native"]["win_turn"]<=t) for i in ids]
    n=len(z);mu=sum(z)/n if n else 0
    se=math.sqrt(sum((v-mu)**2 for v in z)/((n-1)*n)) if n>1 else 0
    return {"delta_pp":round(100*mu,4),"gains":z.count(1),"losses":z.count(-1),
            "paired_95_ci_pp":[round(100*(mu-1.96*se),4),round(100*(mu+1.96*se),4)]}

def pool(path,out):
    audit()
    rows={}
    files=sorted(Path(path).rglob("middle_shard_*.json.gz"))
    for fn in files:
        with gzip.open(fn,"rt",encoding="utf8") as f:q=json.load(f)
        assert q["schema"]==SCHEMA and q["deck_hash"]==HASH
        assert q["seed_base"]==SEED_BASE and q["beam"]==BEAM
        assert q["policy_bumps"]==POLICIES
        assert q["games"]==GAMES_PER_SHARD
        assert len(q["rows"])==q["games"]
        for j,rec in enumerate(q["rows"]):
            gid=q["shard"]*GAMES_PER_SHARD+j
            assert rec["gid"]==gid and gid not in rows
            for name in POLICIES:
                r=rec["results"][name]
                assert r["game_id"]==gid and r["seed"]==SEED_BASE+gid*1000003
                assert r["win_turn"] in (0,1,2,3)
                assert r["keep_n"] in (1,2,3,4,5,6,7)
            assert len({rec["results"][name]["seat"] for name in POLICIES})==1
            rows[gid]=rec
    assert set(rows).issubset(set(range(N)))
    missing=set(range(N))-set(rows)
    k=len(rows)
    summary={"status":"PASS" if not missing else "INCOMPLETE","planned_n":N,
      "validated_n":k,"missing_ids_first50":sorted(missing)[:50],
      "missing_count":len(missing),"shards_found":len(files),
      "shards_expected":N//GAMES_PER_SHARD,"seed_base":SEED_BASE,
      "deck_hash":HASH,"beam":BEAM,"policies":POLICIES,
      "scope":"Goldfish T1/T2/T3 Dack casts, 99-card exact frozen deck, one free multiplayer London; optimistic engine and provisional old continuation thresholds, not full cEDH wins.",
      "design":"Three preselected increasing bumps to existing continuation thresholds, with native-T1-positive keeps protected. Shared pre-reveal hand evaluations across all four policies. Exploratory, not re-calibrated globally optimal mulligan policy.",
      "arms":{},"paired_vs_native":{},"t1_discordant_first40":{}}
    if k:
        for name in POLICIES:
            z=[rows[i]["results"][name] for i in sorted(rows)]
            c=collections.Counter(v["win_turn"] for v in z)
            turn1=c[1]
            summary["arms"][name]={
                "counts":{str(t):c[t] for t in range(4)},
                "T1_pct":round(100*turn1/k,4),
                "T1_95_ci":wilson(turn1,k),
                "T2_pct":round(100*(turn1+c[2])/k,4),
                "T3_pct":round(100*(turn1+c[2]+c[3])/k,4),
                "T2_plus_half_T3_exact_pct":round(100*(turn1+c[2]+0.5*c[3])/k,4),
                "mean_keep":round(sum(v["keep_n"] for v in z)/k,4),
                "keeps_by_n":dict(sorted(collections.Counter(v["keep_n"] for v in z).items())),
            }
        for name in POLICIES:
            if name=="native":continue
            summary["paired_vs_native"][name]={f"T{t}":paired(rows,name,t) for t in (1,2,3)}
            gains=[i for i in sorted(rows) if rows[i]["results"][name]["win_turn"]==1 and rows[i]["results"]["native"]["win_turn"]!=1]
            losses=[i for i in sorted(rows) if rows[i]["results"]["native"]["win_turn"]==1 and rows[i]["results"][name]["win_turn"]!=1]
            summary["t1_discordant_first40"][name]=[
              {"gid":i,"native_keep":rows[i]["results"]["native"]["keep_n"],
               "candidate_keep":rows[i]["results"][name]["keep_n"],
               "native_hand":rows[i]["results"]["native"]["hand"],
               "candidate_hand":rows[i]["results"][name]["hand"],
               "native_T1":rows[i]["results"]["native"]["win_turn"]==1}
              for i in (gains+losses)[:40]]
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(summary,indent=2)+"\n")
    print("POOLED",summary["status"],"n",k,"missing",len(missing),
          "arms",json.dumps(summary["arms"]),flush=True)
    assert not missing,("incomplete: see report",len(missing))

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",action="store_true")
    ap.add_argument("--parity",action="store_true")
    ap.add_argument("--shard",type=int,default=0)
    ap.add_argument("--games",type=int,default=GAMES_PER_SHARD)
    ap.add_argument("--out",default="shards/middle_shard_0.json.gz")
    ap.add_argument("--pool",action="store_true")
    ap.add_argument("--path",default="shards")
    a=ap.parse_args()
    if a.parity:smoke_parity()
    elif a.audit:audit()
    elif a.pool:pool(a.path,a.out)
    else:run(a.shard,a.games,a.out)
