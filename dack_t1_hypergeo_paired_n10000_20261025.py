#!/usr/bin/env python3
"""Paired, checkpointed Dack T1 deployment audit against an ~8% claim.

Frozen: Oct-25 exact-99 Boonweaver 'current' deck and corrected Prism rules.
Policies: native lambda=0.5 free multiplayer London; T1-greedy continuation.
T1-greedy chooses among legal London bottoms by estimated T1 chance, keeps if
that estimate is positive, otherwise takes the next legal mulligan. It is NOT
a proven globally optimal T1 policy. Both policies reveal the same independent
game seed, seat, and per-mulligan shuffled hands, never future draw order.

These are goldfish Dack CAST outcomes conditional on combo eligibility, not
fully validated combo completions or multiplayer game wins.
"""
from __future__ import annotations
import argparse, collections, gc, gzip, hashlib, itertools, json, math, os, random, time
from pathlib import Path
import dack_broad_finalists_heldout_n256_20261025 as prior

root=prior.broad.root
d=prior.broad.d
m=prior.broad.m
batch=root.batch
DECK=tuple(prior.DECKS["current"])
HASH=hashlib.sha256("\n".join(DECK).encode()).hexdigest()
EXPECTED_HASH="a1c8e05dc3f9e1bcfbfbe2f7773ea4a5e62222d3440dd2f7417fd7f2f058c422"
SEED_BASE=20261025111008
SCHEMA="dack_t1_hypergeo_paired_v1"
GAMES_PER_SHARD=40
BEAM=160
STAGES=(7,7,6,5,4,3,2,1)
root.VARIANTS={"current":DECK}
batch.build_deck=lambda name:DECK
batch.CONFIG["seed_base"]=SEED_BASE

def audit():
    assert HASH==EXPECTED_HASH,(HASH,EXPECTED_HASH)
    assert len(DECK)==99 and root.COMBO.issubset(DECK)
    assert DECK.count("Plains")==10 and DECK.count("World Map")==1
    assert DECK.count("Bucknard's Everfull Purse")==1
    assert not {"Mana Crypt","Jeweled Lotus"}.intersection(DECK)
    assert len([x for x in DECK if x!="Plains"])==len(set(x for x in DECK if x!="Plains"))
    assert batch.CONFIG["lambda"]==0.5
    assert callable(d.keep_weighted_ev_seat)
    root.install("current")
    assert tuple(d.DECK)==DECK
    assert d.COSTS["Pentad Prism"]==(2,0,0)
    s=d.State(1,(),(),(d.Perm("Pentad Prism",False,2,1),))
    q=[v for v in d.tap_mana_actions(s) if v.any==1 and not v.battlefield[0].tapped and v.battlefield[0].counters==1]
    assert q and any(v.any==2 for v in d.tap_mana_actions(q[0]))
    print("T1_AUDIT_OK",json.dumps({"hash":HASH,"seed_base":SEED_BASE,"game_beam":BEAM,"games_per_shard":GAMES_PER_SHARD}),flush=True)

def t1_bottom(seven,keep_n,rest,seat):
    ranked=[]
    for inds in itertools.combinations(range(7),7-keep_n):
        iset=set(inds)
        hand=d.sort_hand(tuple(seven[j] for j in range(7) if j not in iset))
        bottom=tuple(seven[j] for j in inds)
        struct=sum(d.bottom_priority(x,seven) for x in bottom)
        ranked.append(((struct,-sum(x in d.COMBO_CREATURES for x in hand),
                         -sum(x in d.AURAS for x in hand)),hand,bottom))
    ranked.sort(key=lambda x:x[0],reverse=True)
    winner=None
    for struct,hand,bottom in ranked[:12]:
        # Independent seeded samples of unseen cards; actual ordered rest is NOT
        # consulted when deciding to keep. Same 60-beam/8-sample budget as native.
        ev=d.keep_weighted_ev_seat(hand,tuple(rest),seat=int(seat),beam=60,
                                    samples=8,bottom=bottom,t3_weight=0)
        rank=(ev["t1"],ev["le2"]+0.5*ev["t3"],struct)
        if winner is None or rank>winner[0]:
            winner=(rank,hand,bottom,ev)
    assert winner is not None
    rank,hand,bottom,ev=winner
    return hand,bottom,ev

def greedy_game(gid):
    root.install("current")
    seed=SEED_BASE+int(gid)*1000003
    m.set_trial_seed(seed)
    rng=random.Random(seed)
    seat=rng.randrange(4)
    audit_log=[]
    for stage,keep_n in enumerate(STAGES):
        cards=list(d.DECK);rng.shuffle(cards)
        seven,rest=cards[:7],cards[7:]
        hand,bottom,ev=t1_bottom(seven,keep_n,rest,seat)
        keep=(ev["t1"]>0 or keep_n==1)
        audit_log.append({"stage":stage,"keep_n":keep_n,"t1_est":round(ev["t1"],5),
                          "le2_est":round(ev["le2"],5),"kept":keep})
        if keep:
            d._WIN_CACHE.clear()
            win=d._win_turn_from_unknown_order(hand,tuple(rest)+tuple(bottom),
                                                 seat,beam=BEAM,max_turn=3)
            return {"game_id":gid,"seed":seed,"seat":seat,"keep_n":keep_n,
                    "win_turn":int(win or 0),"hand":list(hand),
                    "first3":list((tuple(rest)+tuple(bottom))[:3]),
                    "audit":audit_log}
    raise AssertionError("London terminal keep unreachable")

def native_game(gid):
    root.install("current")
    capture={}
    orig=root.choose_hand_with_free
    def observe(rng,seat):
        state,keep_n,log=orig(rng,seat)
        capture["hand"]=list(state.hand)
        capture["first3"]=list(state.library[:3])
        return state,keep_n,log
    root.choose_hand_with_free=observe
    try:
        rec=root.simulate("current",gid,BEAM)
    finally:
        root.choose_hand_with_free=orig
    assert rec["seed"]==SEED_BASE+gid*1000003
    return {**rec,**capture}

def reset_caches():
    d.clear_v073_mulligan_cache()
    if hasattr(d,"_WEIGHTED_SEAT_CACHE"):d._WEIGHTED_SEAT_CACHE.clear()
    if hasattr(d,"_KEEP_SEAT_CACHE"):d._KEEP_SEAT_CACHE.clear()
    if hasattr(d,"_WIN_CACHE"):d._WIN_CACHE.clear()
    gc.collect()

def run(shard,games,out):
    audit()
    assert shard>=0 and games==GAMES_PER_SHARD
    start=shard*GAMES_PER_SHARD
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    progress=dest.with_suffix("").with_suffix(".jsonl")
    rows=[]
    if progress.exists():
        rows=[json.loads(s) for s in progress.read_text().splitlines() if s.strip()]
        assert all(row["gid"]==start+i for i,row in enumerate(rows)),"checkpoint IDs inconsistent"
    if dest.exists() and len(rows)==games:
        print("SHARD_ALREADY_FINISHED",shard,flush=True)
        return
    began=time.time()
    with progress.open("a",encoding="utf8") as f:
        for offset in range(len(rows),games):
            gid=start+offset
            reset_caches()
            native=native_game(gid)
            reset_caches()
            greedy=greedy_game(gid)
            assert native["game_id"]==greedy["game_id"]==gid
            assert native["seed"]==greedy["seed"]==SEED_BASE+gid*1000003
            assert native["seat"]==greedy["seat"]
            row={"gid":gid,"native":native,"t1_greedy":greedy}
            f.write(json.dumps(row,separators=(",",":"))+"\n")
            f.flush();os.fsync(f.fileno())
            rows.append(row)
            print("T1_PAIRED",gid,native["win_turn"],greedy["win_turn"],
                  native["keep_n"],greedy["keep_n"],"elapsed",round(time.time()-began,1),flush=True)
    payload={"schema":SCHEMA,"shard":shard,"games":games,"start_id":start,
             "game_beam":BEAM,"seed_base":SEED_BASE,"deck_hash":HASH,
             "rows":rows,"elapsed_sec":round(time.time()-began,2)}
    tmp=dest.with_suffix(dest.suffix+".tmp")
    with tmp.open("wb") as raw:
        with gzip.GzipFile(filename="",mode="wb",fileobj=raw,mtime=0) as z:
            z.write(json.dumps(payload,separators=(",",":")).encode())
        raw.flush();os.fsync(raw.fileno())
    os.replace(tmp,dest)
    print("SHARD_COMPLETE",shard,len(rows),round(time.time()-began,1),flush=True)

def wilson(k,n):
    if not n:return [None,None]
    z=1.96;p=k/n
    c=(p+z*z/(2*n))/(1+z*z/n)
    h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return [round((c-h)*100,4),round((c+h)*100,4)]

def pool(path,expected,out):
    audit()
    files=sorted(Path(path).rglob("t1shard_*.json.gz"))
    rows={}
    for fn in files:
        with gzip.open(fn,"rt",encoding="utf8") as f:q=json.load(f)
        assert q["schema"]==SCHEMA and q["deck_hash"]==HASH
        assert q["seed_base"]==SEED_BASE and q["game_beam"]==BEAM
        assert q["games"]==GAMES_PER_SHARD
        assert len(q["rows"])==q["games"]
        for j,rec in enumerate(q["rows"]):
            gid=q["shard"]*GAMES_PER_SHARD+j
            assert rec["gid"]==gid and gid not in rows,("duplicate or wrong",gid,str(fn))
            assert rec["native"]["seed"]==rec["t1_greedy"]["seed"]==SEED_BASE+gid*1000003
            assert rec["native"]["seat"]==rec["t1_greedy"]["seat"]
            rows[gid]=rec
    assert expected==10000
    missing=sorted(set(range(expected))-set(rows))
    if any(gid<0 or gid>=expected for gid in rows):raise AssertionError("unexpected game IDs")
    ids=sorted(rows);n=len(ids)
    out_data={"status":"PASS" if not missing else "INCOMPLETE",
              "planned_n":expected,"validated_n":n,
              "shards_found":len(files),"shards_planned":expected//GAMES_PER_SHARD,
              "missing_game_ids_first_100":missing[:100],"missing_game_count":len(missing),
              "schema":SCHEMA,"seed_base":SEED_BASE,"game_beam":BEAM,
              "deck_hash":HASH,"policy_native":"lambda=0.5 free London, frozen thresholds",
              "policy_t1_greedy":"maximize sampled t1 across top 12 legal bottom options; keep when any T1 estimate positive; else free London mulligan through keep 1",
              "scope":"optimistic goldfish Dack cast conditional on Boonweaver combo library, not validated combo completion or multiplayer win",
              "arms":{},"paired_T1":{},"t1_discordant_first_100":[]}
    for k in ("native","t1_greedy"):
        c=collections.Counter(rows[i][k]["win_turn"] for i in ids)
        win1=c[1];win2=win1+c[2];win3=win2+c[3]
        out_data["arms"][k]={"counts":{str(j):c[j] for j in range(4)},
           "T1_pct":round(100*win1/n,4) if n else None,
           "T1_95_wilson_pct":wilson(win1,n),
           "T2_pct":round(100*win2/n,4) if n else None,
           "T3_pct":round(100*win3/n,4) if n else None,
           "mean_keep_size":round(sum(rows[i][k]["keep_n"] for i in ids)/n,4) if n else None}
    gains=[i for i in ids if rows[i]["t1_greedy"]["win_turn"]==1 and rows[i]["native"]["win_turn"]!=1]
    losses=[i for i in ids if rows[i]["native"]["win_turn"]==1 and rows[i]["t1_greedy"]["win_turn"]!=1]
    delta=(len(gains)-len(losses))/n if n else 0
    e=[int(rows[i]["t1_greedy"]["win_turn"]==1)-int(rows[i]["native"]["win_turn"]==1) for i in ids]
    se=math.sqrt(sum((v-delta)**2 for v in e)/(n-1)/n) if n>1 else 0
    out_data["paired_T1"]={"gains":len(gains),"losses":len(losses),
        "delta_pp":round(100*delta,4),
        "normal_95_ci_pp":[round(100*(delta-1.96*se),4),round(100*(delta+1.96*se),4)],
        "changed_keep_size":sum(rows[i]["native"]["keep_n"]!=rows[i]["t1_greedy"]["keep_n"] for i in gains+losses)}
    out_data["t1_discordant_first_100"]=[
        {"gid":i,"native_hand":rows[i]["native"].get("hand"),
         "greedy_hand":rows[i]["t1_greedy"].get("hand"),
         "native_keep_n":rows[i]["native"]["keep_n"],
         "greedy_keep_n":rows[i]["t1_greedy"]["keep_n"],
         "native_T1":rows[i]["native"]["win_turn"]==1,
         "greedy_T1":rows[i]["t1_greedy"]["win_turn"]==1} for i in (gains+losses)[:100]]
    report=Path(out);report.write_text(json.dumps(out_data,indent=2)+"\n")
    raw_path=report.with_suffix(".raw.json.gz")
    with gzip.open(raw_path,"wt",encoding="utf8") as f:
        json.dump({"schema":SCHEMA,"deck_hash":HASH,"seed_base":SEED_BASE,
                   "rows":[rows[i] for i in ids]},f,separators=(",",":"))
    print("POOL",out_data["status"],"games",n,"missing",len(missing),
          "T1",out_data["arms"],"paired",out_data["paired_T1"],flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--audit",action="store_true")
    parser.add_argument("--shard",type=int,default=0)
    parser.add_argument("--games",type=int,default=GAMES_PER_SHARD)
    parser.add_argument("--out",default="shards/t1shard_000.json.gz")
    parser.add_argument("--pool",action="store_true")
    parser.add_argument("--path",default="shards")
    parser.add_argument("--expected",type=int,default=10000)
    opts=parser.parse_args()
    if opts.audit:audit()
    elif opts.pool:pool(opts.path,opts.expected,opts.out)
    else:run(opts.shard,opts.games,opts.out)
