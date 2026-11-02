#!/usr/bin/env python3
"""Read-only Gemstone Caverns legal pregame-exile enumeration/strict physical audit.

Original physics remains frozen. Temporary monkeypatch is scoped only to
counterfactual trials, then restored; never used for any benchmark acceptance.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import replace
from pathlib import Path
import hashlib,json,random,sys,time
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as v43
import dack_boonweaver_aura_exile_guard_20261029 as guard
ref=v43.ref;d=ref.d
PROTO="DACK_V43_GEMSTONE_EXILE_GUARD_PHYSICAL_V1"
N=24
GID_RANGE=range(162600,163600)
def seed(*x):
    return int.from_bytes(hashlib.sha256(json.dumps((PROTO,*x)).encode()).digest()[:8],"big")
def all_legal_pregames(s,seat):
    out=list(ORIGINAL(s,seat))
    if seat==0 or "Gemstone Caverns" not in s.hand:return out
    for card in sorted(set(s.hand)):
        if card=="Gemstone Caverns" or card in d.COMBO_CREATURES or card in guard.PROTECTED_EXILE:continue
        h=list(s.hand);h.remove("Gemstone Caverns");h.remove(card)
        q=replace(s,hand=d.sort_hand(h),
            battlefield=s.battlefield+(d.Perm("Gemstone Caverns",False,1,0),),
            exile=s.exile+(card,))
        if q not in out:out.append(q)
    return out
ORIGINAL=None

def run_case(gid,stage,seat,seven,hidden):
    trial=[]
    for j in range(N):
        future=list(hidden);random.Random(seed(gid,stage,j,"unseen")).shuffle(future)
        turns={}
        for arm in ("original","exhaustive"):
            ref.sim.reset_caches();ref.sim.root.install("one_key_34")
            ref.sim.m.set_trial_seed(seed(gid,stage,j,"chance"))
            d._WIN_CACHE.clear()
            d._pregame_states=ORIGINAL if arm=="original" else all_legal_pregames
            try:
                t=d._win_turn_from_unknown_order(tuple(d.sort_hand(seven)),tuple(future),seat,beam=160,max_turn=3)
            finally:
                d._pregame_states=ORIGINAL
            turns[arm]=int(t or 0)
        trial.append(turns)
    og=[r["original"] for r in trial];new=[r["exhaustive"] for r in trial]
    return {"gid":gid,"stage":stage,"seat":seat,"seven":list(seven),
            "baseline_exile":d.gemstone_exile_choice(seven),"hidden_count":len(hidden),
            "original_turns":og,"full_legal_turns":new,
            "baseline_T1":sum(t==1 for t in og),"full_T1":sum(t==1 for t in new),
            "baseline_T2":sum(t in (1,2) for t in og),"full_T2":sum(t in (1,2) for t in new),
            "baseline_T3":sum(t in (1,2,3) for t in og),"full_T3":sum(t in (1,2,3) for t in new),
            "new_only_T2":sum(b in (1,2) and a not in (1,2) for a,b in zip(og,new)),
            "old_only_T2":sum(a in (1,2) and b not in (1,2) for a,b in zip(og,new))}

def main():
    global ORIGINAL
    v43.audit()
    ORIGINAL=d._pregame_states
    sentinel=d.State(1,tuple(d.sort_hand(("Gemstone Caverns","Lunarch Mantle","Sol Ring","Plains"))),
       tuple(sorted(d.COMBO_CREATURES)))
    old=ORIGINAL(sentinel,2);full=all_legal_pregames(sentinel,2)
    assert len(old)>=3 and old==full,("inherited pregame patch must enumerate all legal safe exiles",old,full)
    assert any("Plains" in x.exile for x in full)
    assert any("Sol Ring" in x.exile for x in full)
    assert all("Lunarch Mantle" not in x.exile for x in full)
    print("GEMSTONE_GUARD_ALL_LEGAL_EXILES_PRESENT_PASS",len(old),len(full),flush=True)
    # Unseen future-selection prohibited: choose first four qualifying hypothetical
    # seven-card stages based solely on visible seven and seat.
    cases=[];deck=ref.SLOT_VARIANTS["one_key_34"]
    for gid in GID_RANGE:
        base=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(base)
        if seat==0:continue
        for st in (0,1):
            order=orders[st];seven=tuple(deck[s] for s in order[:7])
            if "Gemstone Caverns" not in seven:continue
            if not set(seven).intersection(guard.PROTECTED_EXILE):continue
            if not any(c not in guard.PROTECTED_EXILE and c not in d.COMBO_CREATURES and c!="Gemstone Caverns" for c in seven):continue
            s=d.State(1,tuple(d.sort_hand(seven)),())
            if len(ORIGINAL(s,seat))<2:continue
            cases.append((gid,st,seat,seven,tuple(deck[s] for s in order[7:])))
            break
        if len(cases)==4:break
    assert len(cases)==4,("qualifying states absent",len(cases))
    r=[];t0=time.monotonic()
    for gid,st,seat,seven,hidden in cases:
        z=run_case(gid,st,seat,seven,hidden);r.append(z)
        print("GEMSTONE_PHYSICAL_CASE",gid,st,seat,z["baseline_T2"],z["full_T2"],flush=True)
    result={"schema":"dack_v43_gemstone_exile_legal_completeness_conditional_physical_v1",
      "status":"PASS","legal_exile_full_enumeration_confirmed":True,
      "original_exile_action_count_in_witness":len(old),
      "complete_exile_action_count_in_witness":len(full),
      "selected_source_ids":[x[0] for x in cases],
      "selection":"first four from development 162600..163599 with seat>0, Gemstone+protected Aura and safe exile; visible-only",
      "physical_futures_per_state_per_arm":N,
      "strict_beam160":True,"no_future_order_used_to_select_cases":True,
      "same_hidden_92_and_chance_per_arm":True,
      "original_engine_restored_after_each_trial":True,
      "not_policy_benchmark":True,"elapsed_seconds":time.monotonic()-t0,
      "cases":r}
    dest=ROOT/"benchmark_results/v43_new_gemstone_exile_legal_action_physical_dev.json"
    dest.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("DACK_V43_GEMSTONE_PHYSICAL_PASS",json.dumps({
        "cases":len(r),"T2_original":sum(x["baseline_T2"] for x in r),
        "T2_full_legal":sum(x["full_T2"] for x in r),
        "new_only_T2":sum(x["new_only_T2"] for x in r),
        "old_only_T2":sum(x["old_only_T2"] for x in r)},sort_keys=True),flush=True)

if __name__=="__main__":main()
