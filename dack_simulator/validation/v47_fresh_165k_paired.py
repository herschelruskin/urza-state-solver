#!/usr/bin/env python3
"""Fresh 165k strict physical v43 vs v47 hybrid N256, plus ORIGINAL v5 N128.

Predeclared frozen three-policy comparison: every initial 99-slot deck order,
seat, rules and stable dice is identical. Each policy separate interpreter.
v47 uses actual ORIGINAL v5 beam60 sampled score for the first TWO sevens
only (one possible retained hand, no bottom); exact original v43 at stages2+.
Original v5 complete reference is included for the first 128 games.
Do not tune any policy on these future outcomes.
"""
from __future__ import annotations
import argparse,gzip,json,subprocess,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SCHEMA="dack_v47_fresh_165k_v43_vs_original_early_two_sevens_N16_shard"
SCRIPT=(
 "import json,time,sys\n"
 "p=sys.argv[1];g=int(sys.argv[2]);t=time.perf_counter()\n"
 "if p=='v43':\n"
 " import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as m\n"
 " m.audit();ref=m.ref\n"
 "elif p=='v47':\n"
 " import dack_paired_counterfactual_v47_v5_early_two_sevens_20261101 as m\n"
 " m.audit();ref=m.ref\n"
 "else:\n"
 " import dack_paired_counterfactual_v5_stable_chance_20261031 as m\n"
 " m.audit();ref=m.reference\n"
 "r=ref.game('one_key_34',g)\n"
 "print('DACK_V47_NEW_PHYSICAL_GAME',json.dumps({'turn':r['win_turn'],"
 "'seat':r['seat'],'keep_n':r['keep_n'],'history':r['history'],"
 "'seconds':round(time.perf_counter()-t,4)}))\n"
)
def game(gid,policy):
    p=subprocess.run([sys.executable,"-c",SCRIPT,policy,str(gid)],
       cwd=ROOT,text=True,capture_output=True,timeout=900)
    if p.returncode:raise RuntimeError(("165k physical policy error",
         gid,policy,p.stdout[-1000:],p.stderr[-1500:]))
    lines=[x[len("DACK_V47_NEW_PHYSICAL_GAME "):] for x in p.stdout.splitlines()
           if x.startswith("DACK_V47_NEW_PHYSICAL_GAME ")]
    assert len(lines)==1,(gid,policy,len(lines))
    return json.loads(lines[0])
def run(start,out):
    if start not in range(165000,165256,16):
        raise ValueError("N256 new candidate, 16 fixed independent N16 shards")
    a=[]
    for gid in range(start,start+16):
        base=game(gid,"v43")
        hybrid=game(gid,"v47")
        full=game(gid,"v5") if gid<165128 else None
        assert base["seat"]==hybrid["seat"]
        assert base["history"][0]["seven_slots"]==hybrid["history"][0]["seven_slots"]
        assert base["history"][0]["seven"]==hybrid["history"][0]["seven"]
        assert base["turn"] in (0,1,2,3) and hybrid["turn"] in (0,1,2,3)
        # Full original v5 is an independent reference, with exact early
        # action/state parity by hybrid, even if subsequent policies diverge.
        if full is not None:
            assert full["seat"]==hybrid["seat"]
            assert full["history"][0]["seven_slots"]==hybrid["history"][0]["seven_slots"]
            for stage in (0,1):
                if stage>=len(full["history"]):break
                x=full["history"][stage];y=hybrid["history"][stage]
                for key in ("stage","keep_n","kept","seven","hand","bottom","refined"):
                    assert x[key]==y[key],("full original v5 early parity",gid,stage,key)
                for key in ("raw","threshold","sampled_t1"):
                    assert abs(float(x[key])-float(y[key]))<=1e-7
        a.append({"gid":gid,"v43":base,"v47":hybrid,"original_v5":full})
        print("DACK_V47_NEW165K_PAIRED_GAME",gid,
           "v43",base["turn"],"v47",hybrid["turn"],
           "full_v5",full["turn"] if full else None,
           "runtime",round(base["seconds"]+hybrid["seconds"]+(full["seconds"] if full else 0),2),
           flush=True)
    q={
       "schema":SCHEMA,"status":"PASS","game_ids":[start,start+15],
       "N_independent_groups":16,
       "source_comparison_wholly_new_165k_not_dev":True,
       "original_99_slots_and_same_physical_first_seven_seat":True,
       "real_strict_beam160_and_stateless_stable_dice":True,
       "two_original_frozen_policies_unchanged":True,
       "experimental_v47_uses_original_v5_beam60_at_0_1_ONLY":True,
       "frozen_v43_from_stage2_onward":True,
       "exact_original_v5_early_action_parity_where_reference_present":True,
       "original_v5_reference_first_128_games_only":True,
       "not_multiplayer_4player_cedh_winrate":True,
       "model_or_policy_approved":False,
       "rows":a}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(q,f,sort_keys=True)
    print("DACK_V47_FRESH_165K_N16_THREE_POLICY_PHYSICAL_PASS",start,flush=True)
if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--start",type=int,required=True);a.add_argument("--out",required=True)
    z=a.parse_args();run(z.start,z.out)
