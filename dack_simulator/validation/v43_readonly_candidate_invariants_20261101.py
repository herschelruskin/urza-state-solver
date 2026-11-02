#!/usr/bin/env python3
"""Read-only v43 structural/legal/information-boundary audit. No acceptance cohort."""
from __future__ import annotations
import argparse, hashlib, json, random, sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as v43
import dack_mulligan_teacher_features_v13_20261031 as f
from dack_simulator.validation.collect_teacher_london_v13 import finalists
ref=v43.ref
TEST_GIDS=tuple(range(162400,162412))
SCHEMA="dack_v43_v5_readonly_structural_candidate_info_boundary_audit_v1"

def one_candidate(q,c,i,stage,seat,kn,seven,pool):
    x=f.extract(seven,c["hand"],c["bottom"],pool,seat,kn,stage,c["struct_rank"],i)
    return float(v43.v27.original.estimator.predict(v43.v27.original.MODEL,x))

def audit():
    v43.audit()
    assert tuple(ref.sim.STAGES)==(7,7,6,5,4,3,2,1),ref.sim.STAGES
    variant="one_key_34"; deck=ref.SLOT_VARIANTS[variant]
    assert len(deck)==99 and len(ref.SLOTS)==99
    report={"schema":SCHEMA,"status":"PASS","gids":list(TEST_GIDS),"checks":Counter(),"by_stage":{},"illustrative_exclusions":[]}
    for gid in TEST_GIDS:
        seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(seed)
        assert seat in range(4) and len(orders)==8
        orig_state,orig_hist=v43.choose_keep(deck,seat,orders)
        assert orig_hist and orig_hist[-1]["kept"]
        assert Counter(orig_state.hand)+Counter(orig_state.library)==Counter(ref.VARIANTS[variant])
        assert len(orig_state.library)==99-len(orig_state.hand)
        assert orig_hist[0]["keep_n"]==orig_hist[1]["keep_n"]==7 if len(orig_hist)>1 else orig_hist[0]["keep_n"]==7
        assert tuple(orig_state.library[-len(orig_hist[-1]["bottom"]):])==tuple(orig_hist[-1]["bottom"]) if orig_hist[-1]["bottom"] else True
        permuted=[]
        for st,order in enumerate(orders):
            assert len(order)==99 and len(set(order))==99
            assert Counter(deck[s] for s in order)==Counter(ref.VARIANTS[variant])
            repl=list(order[7:]);random.Random(gid*33+st).shuffle(repl)
            permuted.append(tuple(order[:7])+tuple(repl))
        _newstate,newhist=v43.choose_keep(deck,seat,permuted)
        def decision_signature(h):
            return [(a["stage"],a["keep_n"],a["kept"],a["raw"],a["candidate_index"],
                     a["hand"],a["bottom"]) for a in h]
        assert decision_signature(orig_hist)==decision_signature(newhist),(gid,"future peeking")
        report["checks"]["hidden_92_reorder_no_decision_change"]+=1
        report["checks"]["full_99_restoration_every_stage"]+=len(orders)
        for stage,(kn,order) in enumerate(zip(ref.sim.STAGES,orders)):
            seven=tuple(deck[s] for s in order[:7])
            unknown=tuple(deck[s] for s in order[7:])
            pool=Counter(unknown)
            assert Counter(seven)+pool==Counter(ref.VARIANTS[variant])
            all_candidates=finalists(seven,kn,unknown,limit=99)
            restricted=finalists(seven,kn,unknown)
            assert all_candidates[:len(restricted)]==restricted
            assert len(all_candidates)==__import__("math").comb(7,7-kn)
            for c in all_candidates:
                assert len(c["hand"])==kn and len(c["bottom"])==7-kn
                assert Counter(c["hand"])+Counter(c["bottom"])==Counter(seven)
            scores=[one_candidate(None,c,i,stage,seat,kn,seven,pool) for i,c in enumerate(all_candidates)]
            index_all=max(range(len(scores)),key=lambda i:(scores[i],-i))
            index_top=max(range(len(restricted)),key=lambda i:(scores[i],-i))
            a=report["by_stage"].setdefault(str(stage),{"n":0,"all_count":len(all_candidates),"short_count":len(restricted),
                 "exclusion_Qmax_count":0,"max_delta_sum":0.,"max_delta":0.})
            a["n"]+=1
            delta=max(0.,scores[index_all]-scores[index_top])
            a["exclusion_Qmax_count"]+=int(index_all>=len(restricted) and delta>1e-9)
            a["max_delta_sum"]+=delta
            a["max_delta"]=max(a["max_delta"],delta)
            if delta>.02 and len(report["illustrative_exclusions"])<10:
                report["illustrative_exclusions"].append({
                    "gid":gid,"seat":seat,"stage":stage,"keep_n":kn,"seven":seven,
                    "top_q":scores[index_top],"top_hand":restricted[index_top]["hand"],
                    "top_bottom":restricted[index_top]["bottom"],
                    "outside_q":scores[index_all],"outside_hand":all_candidates[index_all]["hand"],
                    "outside_bottom":all_candidates[index_all]["bottom"],
                    "delta_q":delta,
                })
            if stage<len(orig_hist):
                h=orig_hist[stage]
                assert h["candidate_count"]==len(restricted)
                assert h["candidate_index"]==index_top
                assert h["hand"]==restricted[index_top]["hand"]
                assert h["bottom"]==restricted[index_top]["bottom"]
                assert abs(h["raw"]-scores[index_top])<0.00000006
                threshold=float(v43.v27.original.DP["seat_continuations"][str(seat)]["thresholds_by_london_stage"][stage])
                assert h["kept"]==(kn==1 or scores[index_top]>=threshold)
            report["checks"]["legal_all_bottom_candidates"]+=len(all_candidates)
            report["checks"]["candidate_max_and_threshold_parity"]+=int(stage<len(orig_hist))
        print("AUDIT_GID",gid,"stages_visited",len(orig_hist),flush=True)
    report["checks"]=dict(report["checks"])
    report["notes"]=[
       "All sampled ids are development-only, not acceptance sets.",
       "Q2-excluded-candidate comparison is predictive only; not physical outcome validation.",
       "Hidden order invariance checks policy only, not downstream tutor-gameplay boundary."
    ]
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);args=p.parse_args()
    r=audit()
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(r,indent=2,sort_keys=True)+"\n")
    print("DACK_V43_READONLY_INVARIANTS_PASS",json.dumps(r,sort_keys=True),flush=True)
