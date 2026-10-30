#!/usr/bin/env python3
"""Revised non-clairvoyant Bucknard N128 screen on the ONE-KEY Boulder deck.

All decks keep Voltaic Key instead of Tooth of Ramos, and no Manifold Key.
One experiment isolates incremental Bucknard value over Candelabra while
retaining Implements. A second head-to-head compares Bucknard vs Implements
with a common Candelabra shell.

Bucknard action/cost/Key untap is committed BEFORE resolving a fair d4.
The optimal candidate is selected by the average of ALL 4 or 16 outcomes;
post-roll tactical adjustments may depend on the actual result, as legal.
Include conditional success by first die face to quantify roll-one failures.
The original global beam's deterministic in-state roll can cause clairvoyance;
report its naive result separately as a potentially optimistic diagnostic.

This is an approximate top-six eligible-state, beam128 pre-roll policy.
The no-Bucknard control uses the full beam160 engine (asymmetry explicitly
noted). Neutral fixed-2 only controls mulligan decisions; it is not a
fixed-2 result.
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
SEED_BASE=9914301030034001
POLICY="assertive"
BEAM=128
CANDIDATES_PER_TURN=6
SCHEMA="dack_bucknard_onekey_blind_d4_expected_n128_v2"
PURSE="Bucknard's Everfull Purse"
BASE0=tuple(live.ACTUAL_CURRENT_99)

def cut(deck,old,new):
    arr=list(deck);assert old in arr and new not in arr
    arr[arr.index(old)]=new
    return tuple(arr)

ONE_KEY=cut(BASE0,"Tooth of Ramos","Voltaic Key")
BUCK_WITH_CANDELABRA=cut(ONE_KEY,"Implements of Sacrifice","Candelabra of Tawnos")
VARIANTS={
    "buck_with_implements":ONE_KEY,
    "buck_with_candelabra":BUCK_WITH_CANDELABRA,
    "implements_with_candelabra":cut(BUCK_WITH_CANDELABRA,PURSE,"Implements of Sacrifice"),
    "implements_without_buck_tooth":cut(ONE_KEY,PURSE,"Tooth of Ramos"),
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

def blind_bucknard(gid,variant):
    assert variant.startswith("buck_") and variant in VARIANTS
    sim.root.install(variant)
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
                "candidates":counts,"evaluated":0,"chosen_dice":0,
                "first_roll_success":[1.,1.,1.,1.],"had_candidate":False}
    best=0.0;bestdice=0;evaluated=0
    first_roll_success=[0.,0.,0.,0.]
    for st in candidates:
        for action,ndice in activation_templates(st):
            evaluated+=1
            assert ndice in (1,2)
            # Enumerate fair uniform d4 outcomes, never choose based
            # on the eventual outcome. Record underroll sensitivity.
            hits=[0,0,0,0]
            for rs in itertools.product((1,2,3,4),repeat=ndice):
                hits[rs[0]-1]+=int(post_roll_t2(action,rs,ndice))
            by_first=[c/(4**(ndice-1)) for c in hits]
            chance=sum(by_first)/4
            if chance>best:
                best=chance;bestdice=ndice;first_roll_success=by_first
            if best==1.0:break
        if best==1.0:break
    forced_dice((2,2,2))
    return {"gid":gid,"p2":best,"keep_n":keep_n,
            "candidates":counts,"evaluated":evaluated,"chosen_dice":bestdice,
            "first_roll_success":first_roll_success,"had_candidate":bool(candidates)}

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
    assert "Giant's Boulder" in ONE_KEY and "World Map" not in ONE_KEY
    assert {"Voltaic Key",PURSE,"Gleaming Splendor","Implements of Sacrifice"}.issubset(ONE_KEY)
    assert "Tooth of Ramos" not in ONE_KEY and "Manifold Key" not in ONE_KEY
    assert all(len(v)==99 for v in VARIANTS.values())
    assert all(sim.root.COMBO.issubset(v) for v in VARIANTS.values())
    assert all("Gleaming Splendor" in v for v in VARIANTS.values())
    assert all("Voltaic Key" in v and "Manifold Key" not in v for v in VARIANTS.values())
    assert len({sim.deck_hash(v) for v in VARIANTS.values()})==4
    assert all(PURSE not in v for k,v in VARIANTS.items() if not k.startswith("buck_"))
    assert "Implements of Sacrifice" in VARIANTS["implements_with_candelabra"]
    assert "Implements of Sacrifice" not in VARIANTS["buck_with_candelabra"]
    assert "Candelabra of Tawnos" in VARIANTS["implements_with_candelabra"]
    assert "Candelabra of Tawnos" in VARIANTS["buck_with_candelabra"]
    forced_dice((1,2,3))
    st=d.State(1,(),tuple(sim.root.COMBO),
        (d.Perm(PURSE),d.Perm("Voltaic Key")),c=3)
    actions=activation_templates(st)
    assert set(n for _,n in actions)=={1,2},set(n for _,n in actions)
    assert any(n==2 and q.treasures==2 for q,n in actions)
    assert any(n==1 and q.treasures==1 for q,n in actions)
    assert any(q.treasures==3 for q in ORIG_UTILITY(st) if source_leaves(st,q))
    assert not d.chrome_mox_allowed("Gleaming Splendor")
    forced_dice((2,2,2))
    sim.configure_variants(VARIANTS)
    print("BUCK_BLIND_N128_AUDIT_PASS",json.dumps({
        "n":N,"seed":SEED_BASE,"beam_blind":BEAM,
        "beam_comparator":160,
        "max_candidates_per_turn":CANDIDATES_PER_TURN,
        "one_key_only":True,
        "blind_roll_distribution":"EXACT independent 1..4^ndice uniform average",
        "protected_non_aura":"Gleaming Splendor",
        "hashes":{k:sim.deck_hash(v) for k,v in VARIANTS.items()}}),flush=True)

def smoke():
    audit()
    for name in VARIANTS:
        if name.startswith("buck_"):
            result=blind_bucknard(88749,name)
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
            arms={}
            for name in VARIANTS:
                if name.startswith("buck_"):arms[name]=blind_bucknard(gid,name)
                else:arms[name]=no_buck(gid,name)
            # Standard known-roll seeded search is a diagnostic, NOT our
            # blind outcome. It may select prescient roll-dependent lines.
            sim.reset_caches()
            naive=sim.simulate("buck_with_implements",gid,
                               policy=POLICY,seed_base=SEED_BASE,beam=160)
            oracle_t2=int(0<naive["win_turn"]<=2)
            assert set(arms)==set(VARIANTS)
            rows.append({"gid":gid,"arms":arms,"oracle_t2":oracle_t2})
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
            "baseline":"ONE Voltaic Key replacing Tooth; Implements retained in current; no Manifold",
            "assumptions":"Two one-Key Bucknard arms, blind pre-roll action choice maximizing averaged 4 or 16 d4 outcomes, top six eligible candidate states per turn; postroll adaptation allowed. Neutral 2 only during mulligan. Full no-Buck comparator beam160 has asymmetric search budget; no-Buck head-to-head remains descriptive. Future draws known by old engine.",
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
        if name.startswith("buck_"):
            chosen=[q["arms"][name] for q in rows if q["arms"][name]["chosen_dice"]>0]
            available=[q["arms"][name] for q in rows if q["arms"][name]["had_candidate"]]
            result["arms"][name].update({
                "games_with_any_pre_roll_candidate":len(available),
                "games_choosing_positive_value_activation":len(chosen),
                "chosen_dice_histogram":dict(collections.Counter(x["chosen_dice"] for x in chosen)),
                "conditional_first_d4_success_pct_given_chosen_activation":[
                    round(100*sum(x["first_roll_success"][i] for x in chosen)/len(chosen),3)
                    if chosen else None for i in range(4)],
                "mean_pre_roll_candidates_evaluated":round(
                    sum(q["arms"][name]["evaluated"] for q in rows)/N,3)})
    result["naive_seeded_known_roll_onekey_T2_pct"]=round(
        100*sum(q["oracle_t2"] for q in rows)/N,4)
    # Exact paired contrasts on matched game seeds.
    for a,b,label in [
        ("buck_with_implements","implements_with_candelabra","buck_and_implements_vs_implements_and_candelabra"),
        ("buck_with_candelabra","implements_with_candelabra","buck_vs_implements_common_candelabra"),
        ("buck_with_implements","implements_without_buck_tooth","buck_vs_tooth_keep_implements"),
        ("buck_with_implements","buck_with_candelabra","implements_vs_candelabra_keep_buck")]:
        dd=[q["arms"][a]["p2"]-q["arms"][b]["p2"] for q in rows]
        mu=sum(dd)/N
        se=math.sqrt(sum((x-mu)**2 for x in dd)/(N*(N-1)))
        result["paired_vs_bucknard"][label]={
            "difference_T2_pp":round(100*mu,4),
            "paired_95_ci_pp":[round(100*(mu-1.96*se),4),round(100*(mu+1.96*se),4)],
            "a":a,"b":b,
            "warning":"Buck uses limited blind policy, comparator uses full beam160; exploratory"}
    Path(out).write_text(json.dumps(result,indent=2)+"\n")
    with gzip.open(str(out).replace(".json",".raw.json.gz"),"wt",encoding="utf8") as fp:json.dump({"schema":SCHEMA,"rows":rows},fp)
    print("BUCK_BLIND_N128_FINAL_PASS",json.dumps({
        "arms":result["arms"],"paired":result["paired_vs_bucknard"],
        "naive_seeded_roll":result["naive_seeded_known_roll_onekey_T2_pct"]}),flush=True)

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
