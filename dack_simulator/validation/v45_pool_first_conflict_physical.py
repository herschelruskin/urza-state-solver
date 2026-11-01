#!/usr/bin/env python3
"""Pool selected actual v5-v43 first KEEP conflicts, real physical K32/C64.

Resample 44 independent source deal groups, K32 futures per deal and ONE
shared C64 full99 lottery per seat-stage cell. All first-conflict source
games are retrospective, not unselected population observations.
"""
import argparse,glob,gzip,json,random
from pathlib import Path
from collections import Counter,defaultdict

SCHEMA="dack_v45_physical_first_conflict_K32_C64_v43_downstream_1"
def by(t,h):return int(0<int(t)<=h)

def run(ks,cs,out):
    kp=sorted(glob.glob(ks));cp=sorted(glob.glob(cs))
    assert len(kp)==8 and len(cp)==20,(len(kp),len(cp))
    cases={};C={};digest=None
    for file in kp:
        with gzip.open(file,"rt") as f:d=json.load(f)
        assert d["schema"]==SCHEMA and d["status"]=="PASS" and d["kind"]=="K"
        assert d["true_v43_downstream_selftest"] and d["blind_unknown92_and_real_beam160"]
        assert d["source_historical_N44_not_fresh_population"]
        assert d["K_futures"]==32
        if digest is None:digest=d["source_sha256"]
        assert digest==d["source_sha256"]
        for r in d["rows"]:
            assert r["gid"] not in cases and r["stage"] in range(5)
            assert len(r["turns"])==32
            cases[r["gid"]]=r
    assert len(cases)==44
    for file in cp:
        with gzip.open(file,"rt") as f:d=json.load(f)
        assert d["schema"]==SCHEMA and d["status"]=="PASS" and d["kind"]=="C"
        assert d["true_v43_downstream_selftest"]
        assert d["all_99_cards_restored_for_each_later_london_stage"]
        assert d["full99_future_not_influenced_by_original_seven"]
        assert d["source_sha256"]==digest
        key=(int(d["seat"]),int(d["stage"]))
        assert key not in C and key[0] in range(4) and key[1] in range(5)
        C[key]=d["turns"]
        assert len(C[key]) in (0,64)
    assert len(C)==20
    for r in cases.values():
        assert len(C[(r["seat"],r["stage"])])==64
    def summarize(rs):
        if not rs:return None
        result={"N_source_selected_first_conflicts":len(rs),
           "v5_first_KEEP":sum(r["v5_first_keeps"] for r in rs),
           "v43_first_KEEP":sum(not r["v5_first_keeps"] for r in rs)}
        for h in (1,2,3):
            values=[]
            for r in rs:
                k=sum(by(t,h) for t in r["turns"])/32
                c=sum(by(t,h) for t in C[(r["seat"],r["stage"])])/64
                values.append((1 if r["v5_first_keeps"] else -1)*(k-c))
            result[f"physical_one_step_v5_minus_v43_T{h}_pp"]=100*sum(values)/len(values)
            result[f"positive_T{h}_per_state"]=sum(v>0 for v in values)
            result[f"negative_T{h}_per_state"]=sum(v<0 for v in values)
        return result
    rr=list(cases.values())
    main=summarize(rr)
    grouped={str(s):summarize([r for r in rr if r["stage"]==s]) for s in range(5)}
    dirs={x:summarize([r for r in rr if r["v5_first_keeps"]==q])
        for x,q in [("v5_keeps_v43_mulls",True),("v43_keeps_v5_mulls",False)]}
    rng=random.Random(451510)
    B=2000
    draws={h:[] for h in (1,2,3)}
    gids=sorted(cases)
    for _ in range(B):
        Cboot={}
        for cell,turns in C.items():
            if not turns:continue
            sub=[turns[rng.randrange(64)] for i in range(64)]
            Cboot[cell]={h:sum(by(t,h) for t in sub)/64 for h in (1,2,3)}
        delta={h:0. for h in (1,2,3)}
        for _ in range(44):
            r=cases[gids[rng.randrange(44)]]
            future=[r["turns"][rng.randrange(32)] for i in range(32)]
            sign=1 if r["v5_first_keeps"] else -1
            for h in (1,2,3):
                k=sum(by(t,h) for t in future)/32
                delta[h]+=sign*(k-Cboot[(r["seat"],r["stage"])][h])
        for h in (1,2,3):draws[h].append(100*delta[h]/44)
    CI={}
    for h in (1,2,3):
        a=sorted(draws[h])
        CI[f"T{h}"]=[a[49],a[1949]]
    outdata={
      "schema":"dack_v45_real_selected_v5_v43_first_decision_44_game_K_C_physical",
      "status":"PASS","selected_outer_source_games":44,
      "K_physical_futures_per_group":32,
      "C_physical_futures_per_used_seat_stage_cell":64,
      "K_real_games":44*32,
      "C_real_games":sum(len(v) for v in C.values()),
      "independent_C_cells":sum(bool(v) for v in C.values()),
      "exact_v43_downstream_full99_parity":True,
      "selected_151k_source_ALREADY_CONSUMED":True,
      "physical_rollouts_new_after_source_selection":True,
      "conditional_one_step_v43_future_not_original_v5_future":True,
      "not_population_winrate_and_not_policy_approval":True,
      "source_sha256":digest,
      "selected_physical_action_advantage":main,
      "by_first_disagreement_stage":grouped,
      "by_direction":dirs,
      "two_source_group_K_C_bootstrap_95ci_pp":CI,
    }
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(outdata,indent=2,sort_keys=True)+"\n")
    print("DACK_V45_SELECTED_FIRST_CONFLICT_REAL_PHYSICAL_K_C_PASS",
          json.dumps({"overall":main,"by_stage":grouped,"by_direction":dirs,"CI":CI},sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--K",required=True);p.add_argument("--C",required=True);p.add_argument("--out",required=True)
    q=p.parse_args();run(q.K,q.C,q.out)
