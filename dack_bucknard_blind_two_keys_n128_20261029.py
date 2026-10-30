#!/usr/bin/env python3
"""Blind pre-roll d4 Bucknard audit on REAL Boulder + Voltaic/Manifold deck.

The normal seeded goldfish knows a Bucknard result during beam expansion
and might choose an activation path exploiting the realized outcome.
This separate diagnostic removes that advantage: it does NOT roll before
committing to activating Bucknard, choosing key untaps, and paying costs.
It measures T2 EXPECTED success across all uniform independent d4 outcomes
for the committed activation(s), allowing post-roll play to adapt normally.

For each hand, run the assertive one-free London mulligan using NEUTRAL
fixed-2 Bucknard during mulligan evaluation (not a realized sample). Search
turns 1 and 2 WITHOUT resolving any Bucknard activation; retain K best
pre-roll opportunities per turn. Evaluate the same paid activation choice
over independent d4 outcomes and pick the highest expected chance.

Correctly covers ordinary 1-d4 activation, a Voltaic OR Manifold 2-d4
activation costing 3 generic, and both Keys 3-d4 activation costing 5.
This is a limited top-K imperfect-information policy, NOT globally optimal,
and old beam search still uses known library order. The roll is NOT
available to the prefix/keep choice. It is NOT a fixed two-Treasure test.

Matched comparator decks replace Bucknard with Tooth of Ramos,
Implements of Sacrifice, or Candelabra of Tawnos, all otherwise holding
both Keys. Comparators use same seed IDs and original search, which
still has the original future draw/oracle approximation but no Buck die.
Every arm protects all Auras + Gleaming Splendor from exile.
"""
from __future__ import annotations
import argparse,collections,gzip,hashlib,itertools,json,math,os,random
from pathlib import Path
from dataclasses import replace
import dack_manifold_second_key_stack_20261029 as second
import dack_actual_current_boulder_20261028 as live

sim=second.sim;d=sim.d;buck=second.buck
N=128
GAMES_PER_SHARD=4
SEED_BASE=9914291031034001
POLICY="assertive"
BEAM=96
CANDIDATES_PER_TURN=3
SCHEMA="dack_bucknard_two_keys_blind_expectation_n128_v1"
PURSE="Bucknard's Everfull Purse"
BASE0=tuple(live.ACTUAL_CURRENT_99)

def cut(deck,old,new):
    arr=list(deck);assert old in arr and new not in arr
    arr[arr.index(old)]=new
    return tuple(arr)

KEYS=cut(cut(BASE0,"Tooth of Ramos","Voltaic Key"),
         "Implements of Sacrifice","Manifold Key")
VARIANTS={
    "bucknard":KEYS,
    "without_buck_tooth":cut(KEYS,PURSE,"Tooth of Ramos"),
    "without_buck_implements":cut(KEYS,PURSE,"Implements of Sacrifice"),
    "without_buck_candelabra":cut(KEYS,PURSE,"Candelabra of Tawnos"),
}
sim.configure_variants(VARIANTS)
ORIG_UTILITY=d.utility_actions
ORIG_ROLL=buck._roll
def forced_dice(rolls):
    def roller(s,card,sides,salt=0):
        if card!=PURSE:
            return ORIG_ROLL(s,card,sides,salt)
        assert sides==4
        ix=2 if salt>=20000 else (1 if salt>=10000 else 0)
        if ix>=len(rolls):ix=0
        return rolls[ix]
    buck._roll=roller

def source_leaves(s,q):
    before=sum(d.effective_name(p)==PURSE for p in s.battlefield)
    after=sum(d.effective_name(p)==PURSE for p in q.battlefield)
    return before>after and q.treasures>s.treasures

def find_pre_states(hand,ordered_library,seat):
    candidates={1:{},2:{}}
    def no_purse_activation(s):
        all_acts=ORIG_UTILITY(s)
        if s.turn<=2 and any(d.effective_name(p)==PURSE and not p.tapped for p in s.battlefield):
            candidates[s.turn][d.key(s)]=s
        return [q for q in all_acts if not source_leaves(s,q)]
    d.utility_actions=no_purse_activation
    try:
        starts=d._pregame_states(d.State(1,hand,tuple(ordered_library)),seat)
        states=starts
        for turn in (1,2):
            nxt=[]
            if turn==1:nxt=[d.draw(s,1) for s in states]
            else:
                for s in states:
                    q=d.untap_and_begin(replace(s,turn=turn))
                    q=d.add_opponent_cycle_resources(q)
                    for u in d.mana_vault_upkeep_options(q):
                        nxt.append(d.begin_first_main(d.saga_advance(d.draw(u,1))))
            wins,front=d.search_turn_frontier_many(
                nxt,beam=BEAM,depth=22 if turn==1 else 24)
            if wins:return True,[],{str(k):len(v) for k,v in candidates.items()}
            if turn==1:
                front.sort(key=d.score,reverse=True)
                states=front[:BEAM]
    finally:
        d.utility_actions=ORIG_UTILITY
    ranked=[]
    for turn,states in candidates.items():
        ranked+=sorted(states.values(),key=d.score,reverse=True)[:CANDIDATES_PER_TURN]
    return False,ranked,{str(k):len(v) for k,v in candidates.items()}

def activation_templates(s):
    forced_dice((1,1,1))
    outs=[q for q in ORIG_UTILITY(s) if source_leaves(s,q)]
    uniq={}
    for q in outs:
        ndice=q.treasures-s.treasures
        assert ndice in (1,2,3),(ndice,s.turn)
        uniq[(d.key(q),ndice)]=(q,ndice)
    return list(uniq.values())

def post_roll_t2(s,rolls,ndice):
    assert ndice==len(rolls)
    forced_dice(rolls)
    q=replace(s,treasures=s.treasures+sum(rolls)-ndice)
    if d.can_cast_dack(q):return True
    d._WIN_CACHE.clear()
    wins,fr=d.search_turn_frontier_many([q],beam=BEAM,depth=24)
    if wins:return True
    if q.turn==2:return False
    fr.sort(key=d.score,reverse=True)
    next_states=[]
    for t in fr[:BEAM]:
        t=d.untap_and_begin(replace(t,turn=2))
        t=d.add_opponent_cycle_resources(t)
        for u in d.mana_vault_upkeep_options(t):
            next_states.append(d.begin_first_main(d.saga_advance(d.draw(u,1))))
    if not next_states:return False
    wins,_=d.search_turn_frontier_many(next_states,beam=BEAM,depth=24)
    return bool(wins)

def blind_bucknard(gid):
    sim.root.install("bucknard")
    seed=SEED_BASE+gid*1000003
    buck.set_trial_seed(seed)
    rng=random.Random(seed)
    seat=rng.randrange(4)
    forced_dice((2,2,2))
    d._WIN_CACHE.clear()
    state,keep_n,_=sim.choose_hand_with_free(rng,seat,policy=POLICY)
    immediate,candidates,counts=find_pre_states(state.hand,state.library,seat)
    if immediate:
        return {"gid":gid,"p2":1.0,"keep_n":keep_n,
                "candidates":counts,"evaluated":0,"chosen_dice":0}
    best=0.0;bestdice=0;evaluated=0
    for st in candidates:
        for action,ndice in activation_templates(st):
            evaluated+=1
            # Enumerate ALL independent uniform d4 rolls (4/16/64),
            # never conditional on a known outcome when choosing action.
            cases=itertools.product((1,2,3,4),repeat=ndice)
            hits=sum(int(post_roll_t2(action,rs,ndice)) for rs in cases)
            chance=hits/(4**ndice)
            if chance>best:best=chance;bestdice=ndice
            if best==1.0:break
        if best==1.0:break
    forced_dice((2,2,2))
    return {"gid":gid,"p2":best,"keep_n":keep_n,
            "candidates":counts,"evaluated":evaluated,"chosen_dice":bestdice}

def no_buck(gid,name):
    sim.reset_caches()
    # This arm contains no Purse, therefore no d4 decision leakage.
    buck._roll=ORIG_ROLL
    rec=sim.simulate(name,gid,policy=POLICY,seed_base=SEED_BASE,beam=160)
    return {"gid":gid,"p2":float(0<rec["win_turn"]<=2),
            "t1":int(rec["win_turn"]==1),
            "t3":int(0<rec["win_turn"]<=3),
            "keep_n":rec["keep_n"]}

def audit():
    assert second.witness()["status"]=="PASS"
    assert N==32*GAMES_PER_SHARD and len(VARIANTS)==4
    assert POLICY==sim.ACTIVE_POLICY
    assert "Giant's Boulder" in KEYS and "World Map" not in KEYS
    assert {"Voltaic Key","Manifold Key",PURSE,"Gleaming Splendor"}.issubset(KEYS)
    assert "Tooth of Ramos" not in KEYS and "Implements of Sacrifice" not in KEYS
    assert all(len(v)==99 for v in VARIANTS.values())
    assert all(sim.root.COMBO.issubset(v) for v in VARIANTS.values())
    assert all("Gleaming Splendor" in v for v in VARIANTS.values())
    assert all("Voltaic Key" in v and "Manifold Key" in v for v in VARIANTS.values())
    assert len({sim.deck_hash(v) for v in VARIANTS.values()})==4
    assert all(PURSE not in v for k,v in VARIANTS.items() if k!="bucknard")
    forced_dice((1,2,3))
    st=d.State(1,(),tuple(sim.root.COMBO),
        (d.Perm(PURSE),d.Perm("Voltaic Key"),d.Perm("Manifold Key")),c=5)
    actions=activation_templates(st)
    assert set(n for _,n in actions)=={1,2,3},set(n for _,n in actions)
    assert any(n==3 and q.treasures==3 for q,n in actions)
    assert any(n==2 and q.treasures==2 for q,n in actions)
    assert any(n==1 and q.treasures==1 for q,n in actions)
    forced_dice((1,2,3))
    assert any(q.treasures==6 for q in ORIG_UTILITY(st) if source_leaves(st,q))
    assert not d.chrome_mox_allowed("Gleaming Splendor")
    forced_dice((2,2,2))
    sim.configure_variants(VARIANTS)
    print("BUCK_BLIND_N128_AUDIT_PASS",json.dumps({
        "n":N,"seed":SEED_BASE,"beam_blind":BEAM,
        "beam_comparator":160,
        "max_candidates_per_turn":CANDIDATES_PER_TURN,
        "blind_roll_distribution":"EXACT independent 1..4^ndice uniform average",
        "protected_non_aura":"Gleaming Splendor",
        "hashes":{k:sim.deck_hash(v) for k,v in VARIANTS.items()}}),flush=True)

def smoke():
    audit()
    for name in VARIANTS:
        if name=="bucknard":
            result=blind_bucknard(88749)
        else:result=no_buck(88749,name)
        assert 0<=result["p2"]<=1
        print("BUCK_BLIND_SMOKE_PASS",name,result["p2"],flush=True)

def run(shard,games,out):
    audit()
    assert 0<=shard<32 and games==GAMES_PER_SHARD
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    checkpoint=Path(str(dest).replace(".json.gz",".jsonl"))
    rows=[]
    if checkpoint.exists():
        rows=[json.loads(s) for s in checkpoint.read_text().splitlines() if s]
        assert all(s["gid"]==shard*games+i for i,s in enumerate(rows))
    if dest.exists() and len(rows)==games:return
    with checkpoint.open("a",encoding="utf8") as fp:
        for i in range(len(rows),games):
            gid=shard*games+i
            arms={"bucknard":blind_bucknard(gid)}
            for name in VARIANTS:
                if name!="bucknard":arms[name]=no_buck(gid,name)
            assert set(arms)==set(VARIANTS)
            rows.append({"gid":gid,"arms":arms})
            fp.write(json.dumps(rows[-1],separators=(",",":"))+"\n")
            fp.flush();os.fsync(fp.fileno())
            print("BUCK_BLIND_MATCHED_GAME",gid,[(k,round(v["p2"],3)) for k,v in arms.items()],flush=True)
    with gzip.open(dest,"wt",encoding="utf8") as f:
        json.dump({"schema":SCHEMA,"shard":shard,"seed_base":SEED_BASE,"rows":rows,
                   "hashes":{k:sim.deck_hash(v) for k,v in VARIANTS.items()}},f)
    print("BUCK_BLIND_SHARD_COMPLETE",shard,len(rows),flush=True)

def pool(folder,out):
    audit()
    files=sorted(Path(folder).rglob("buck_blind_shard_*.json.gz"))
    assert len(files)==32,len(files)
    got={}
    for f in files:
        with gzip.open(f,"rt") as z:record=json.load(z)
        assert record["schema"]==SCHEMA and record["seed_base"]==SEED_BASE
        assert record["hashes"]=={k:sim.deck_hash(v) for k,v in VARIANTS.items()}
        assert len(record["rows"])==GAMES_PER_SHARD
        for i,row in enumerate(record["rows"]):
            gid=record["shard"]*GAMES_PER_SHARD+i
            assert row["gid"]==gid and gid not in got and set(row["arms"])==set(VARIANTS)
            got[gid]=row
    assert set(got)==set(range(N))
    rows=[got[i] for i in range(N)]
    result={"schema":SCHEMA,"status":"PASS","n":N,
            "shards_found":len(files),"seed_base":SEED_BASE,
            "beam_blind":BEAM,"beam_comparators":160,
            "baseline":"two Keys with Bucknard, no Tooth/Implements",
            "assumptions":"Blind pre-roll action choice maximizing exact averaged d4 outcome, top 3 eligible candidate states per turn; four-face or 16/64 independent combinations for multiple activations. Postroll adaptation allowed. Neutral2 heuristic used for mulligan decisions. Search is approximate and may see future draws, so not a verified fully imperfect-information win rate.",
            "arms":{},"paired_vs_bucknard":{},
            "max_candidates_per_turn":CANDIDATES_PER_TURN,
            "roll_policy":"NO realized d4 available when choosing pre-activation line",
            "protected_splendor_and_auras":True}
    for name in VARIANTS:
        vals=[q["arms"][name]["p2"] for q in rows]
        result["arms"][name]={"mean_probability_T2_pct":round(100*sum(vals)/N,4),
            "p2_probabilistic_success_mass":round(sum(vals),4),
            "mean_keep_n":round(sum(q["arms"][name]["keep_n"] for q in rows)/N,4),
            "deck_hash":sim.deck_hash(VARIANTS[name])}
        if name!="bucknard":
            dd=[q["arms"]["bucknard"]["p2"]-q["arms"][name]["p2"] for q in rows]
            mu=sum(dd)/N
            se=math.sqrt(sum((x-mu)**2 for x in dd)/(N*(N-1)))
            result["paired_vs_bucknard"][name]={
                "bucknard_minus_comparator_T2_pp":round(100*mu,4),
                "paired_95_ci_pp":[round(100*(mu-1.96*se),4),round(100*(mu+1.96*se),4)],
                "note":"Comparators use full unrestricted deterministic search (no random Bucknard); Bucknard uses approximate top-K blind policy"}
    Path(out).write_text(json.dumps(result,indent=2)+"\n")
    with gzip.open(str(out).replace(".json",".raw.json.gz"),"wt",encoding="utf8") as fp:json.dump({"schema":SCHEMA,"rows":rows},fp)
    print("BUCK_BLIND_N128_FINAL_PASS",json.dumps({
        "arms":result["arms"],"paired":result["paired_vs_bucknard"]}),flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",action="store_true")
    ap.add_argument("--smoke",action="store_true")
    ap.add_argument("--pool",action="store_true")
    ap.add_argument("--shard",type=int,default=0)
    ap.add_argument("--games",type=int,default=GAMES_PER_SHARD)
    ap.add_argument("--path",default="shards")
    ap.add_argument("--out",default="shards/buck_blind_shard_0.json.gz")
    a=ap.parse_args()
    if a.audit:audit()
    elif a.smoke:smoke()
    elif a.pool:pool(a.path,a.out)
    else:run(a.shard,a.games,a.out)
