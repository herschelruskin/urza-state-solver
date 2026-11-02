#!/usr/bin/env python3
"""Research-only selective strict physical K-value fallback for v43 early sevens.

The baseline and DP-only candidate remain frozen. At London stages 0/1 only,
trigger limited strict legal six-future goldfish samples on OBSERVABLE unusual
mana/tutor/card combinations near the decision threshold.

Crucial: never use the actual future shuffle/order, outer-game seed, or T2
outcome in deciding whether to sample or the sampled policy action. The
outcome simulator's original game chance seed MUST be restored after all
internal hypothetical samples. Sampled T2 is shrunk towards frozen v27 Q2.
No additional model trained or teacher labels used.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import hashlib,json,random
import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as v43
import dack_mulligan_teacher_features_v13_20261031 as features
from dack_simulator.validation.collect_teacher_london_v13 import finalists
ref=v43.ref
POLICY="dack_v43_DP_with_selective_observable_early_seven_strict_futures_RESEARCH"
DP_PATH=Path("models/dack_v43_model_only_policy_consistent_DP_163700_N1024_RESEARCH.json")
PROTO="DACK_V43_6_PHYSICAL_SAMPLED_VISIBLE_SEVEN_SEED_V1"
FUTURES=6;PRIOR=8.0;MARGIN=0.18;CHANGE_MARGIN=0.06;DISAGREEMENT=0.12
ENABLED=True
OUTER_SEED=None
STATS=Counter()

def stable_seed(*items):
    blob=json.dumps((PROTO,*items),sort_keys=True,separators=(",",":"))
    return int.from_bytes(hashlib.sha256(blob.encode()).digest()[:8],"big")

def risk_patterns(seven):
    s=set(seven);out=[]
    pairs={
      "gemstone_moxdiamond":("Gemstone Caverns","Mox Diamond"),
      "gemstone_enlightened":("Gemstone Caverns","Enlightened Tutor"),
      "mono_grim_workshop":("Grim Monolith","Mishra's Workshop"),
      "grim_gardens":("Grim Monolith","The Mycosynth Gardens"),
      "grim_moonsilver":("Grim Monolith","Moonsilver Key"),
      "led_brainstone":("Lion's Eye Diamond","Brainstone"),
      "led_scroll":("Lion's Eye Diamond","Scroll Rack"),
      "led_gardens":("Lion's Eye Diamond","The Mycosynth Gardens"),
      "vault_key":("Mana Vault","Voltaic Key"),
      "vault_enlightened":("Mana Vault","Enlightened Tutor"),
      "tomb_enlightened":("Ancient Tomb","Enlightened Tutor"),
      "tomb_sol":("Ancient Tomb","Sol Ring"),
      "chrome_diamond":("Chrome Mox","Mox Diamond"),
      "sol_city":("Sol Ring","City of Traitors"),
      "sol_led":("Sol Ring","Lion's Eye Diamond"),
    }
    for label,cs in pairs.items():
        if all(c in s for c in cs):out.append(label)
    return out

def independent_physical_keep(seven,unknown,seat,stage,q):
    """Futures condition only on observed seven and remaining *multiset*.

    The actual ordered unseen92 never enters the choice of order, seed, or
    game state. Root and original chance seed are restored even on failure.
    """
    assert OUTER_SEED is not None,"external caller must provide trial seed for restoration"
    assert len(seven)==7 and len(unknown)==92
    visible=tuple(sorted(seven))
    pool=tuple(sorted(Counter(unknown).items()))
    unseen=[card for card,count in pool for _ in range(count)]
    assert len(unseen)==92
    wins=[];turns=[]
    try:
        for future in range(FUTURES):
            sampled=unseen.copy()
            random.Random(stable_seed("future_order",visible,pool,seat,stage,future)).shuffle(sampled)
            ref.sim.reset_caches()
            ref.sim.root.install("one_key_34")
            ref.sim.m.set_trial_seed(stable_seed("game_chance",visible,pool,seat,stage,future))
            ref.d._WIN_CACHE.clear()
            turn=ref.d._win_turn_from_unknown_order(tuple(seven),tuple(sampled),seat,beam=160,max_turn=2)
            turn=int(turn or 0)
            assert turn in (0,1,2)
            turns.append(turn)
            wins.append(int(0<turn<=2))
    finally:
        ref.sim.reset_caches()
        ref.sim.root.install("one_key_34")
        ref.sim.m.set_trial_seed(int(OUTER_SEED))
        ref.d._WIN_CACHE.clear()
    adjusted=(sum(wins)+PRIOR*q)/(FUTURES+PRIOR)
    return adjusted,turns

def install(enabled=True):
    global ENABLED
    v43.audit()
    tab=json.loads(DP_PATH.read_text())
    assert tab["source_groups"]==[163700,164723] and tab["stage_keep_counts"]==list(ref.sim.STAGES)
    for seat,record in tab["seats"].items():
        thresholds=record["thresholds_by_london_stage"]
        assert len(thresholds)==8 and thresholds[-1]==-1
        ref_dp=v43.v27.original.DP["seat_continuations"][seat]["thresholds_by_london_stage"]
        ref_dp[:]=list(thresholds)
    ENABLED=bool(enabled)
    ref.choose_keep=choose_keep
    ref.MULLIGAN_POLICY_NAME=POLICY if enabled else "v43_DP_only_no_fallback_internal_PARITY"
    ref.MULLIGAN_SAMPLER_NAME="6_blind_physical_future_samples_only_on_observable_risky_early_sevens" if enabled else "none"
    return True

def choose_keep(deck_slots,seat,orders):
    assert deck_slots==ref.SLOT_VARIANTS["one_key_34"] and len(orders)==8
    thresholds=v43.v27.original.DP["seat_continuations"][str(seat)]["thresholds_by_london_stage"]
    hist=[];did_sample=False
    for stage,(kn,order) in enumerate(zip(ref.sim.STAGES,orders)):
        seven=tuple(deck_slots[s] for s in order[:7])
        unknown=tuple(deck_slots[s] for s in order[7:])
        assert len(seven)==7 and len(unknown)==92
        pool=Counter(unknown)
        pred=[]
        for i,c in enumerate(finalists(seven,kn,unknown)):
            x=features.extract(seven,c["hand"],c["bottom"],pool,seat,kn,stage,c["struct_rank"],i)
            q=float(v43.v27.original.estimator.predict(v43.v27.original.MODEL,x))
            pred.append((q,-i,c))
        q,neg,selected=max(pred,key=lambda a:(a[0],a[1]))
        threshold=float(thresholds[stage])
        raw_keep=(kn==1 or q>=threshold)
        kept=raw_keep;sampled_turns=[];adjusted=q
        risk=risk_patterns(seven) if stage in (0,1) else []
        trigger=bool(ENABLED and not did_sample and stage in (0,1)
                     and risk and abs(q-threshold)<=MARGIN)
        if trigger:
            STATS["fallback_invoked"]+=1;did_sample=True
            adjusted,sampled_turns=independent_physical_keep(seven,unknown,seat,stage,q)
            # Conservative intervention: one-step K evidence must flip
            # the Q2-vs-continuation decision with a healthy margin, while
            # substantially disagreeing with model's prediction.
            new_keep=adjusted>=threshold
            if (new_keep!=raw_keep and abs(adjusted-threshold)>=CHANGE_MARGIN
                    and abs(adjusted-q)>=DISAGREEMENT):
                kept=new_keep
                STATS["fallback_changed_keep"]+=1
        hand=tuple(selected["hand"]);bottom=tuple(selected["bottom"])
        assert Counter(hand)+Counter(bottom)==Counter(seven)
        hist.append({
          "stage":stage,"keep_n":kn,"kept":bool(kept),"raw":round(q,7),
          "threshold":round(threshold,7),"refined":False,"sampled_t1":None,
          "candidate_index":-neg,"candidate_count":len(pred),
          "seven_slots":list(order[:7]),"seven":list(seven),
          "hand":list(hand),"bottom":list(bottom),
          "hand_slots":ref.selected_slots(order[:7],seven,hand),
          "bottom_slots":ref.selected_slots(order[:7],seven,bottom),
          "fallback_trigger":trigger,"fallback_risk_patterns":risk,
          "fallback_samples":sampled_turns,
          "fallback_adjusted_Q2":round(adjusted,7) if trigger else None,
          "fallback_action_changed":kept!=raw_keep,"policy":POLICY
        })
        STATS["visited"]+=1
        if kept:
            return ref.d.State(1,hand,unknown+bottom),hist
    raise AssertionError("London terminal must keep")

def selftest():
    install(enabled=False)
    deck=ref.SLOT_VARIANTS["one_key_34"]
    for gid in range(167900,167908):
        seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        seat,orders=ref.stage_slots(seed)
        baseline,ha=v43.choose_keep(deck,seat,orders)
        candidate,hb=choose_keep(deck,seat,orders)
        assert baseline.hand==candidate.hand and baseline.library==candidate.library,(gid,"state parity")
        assert len(ha)==len(hb),(gid,"history length")
        for a,b in zip(ha,hb):
            for key in ("stage","keep_n","kept","raw","threshold",
                        "candidate_index","candidate_count","hand","bottom"):
                assert a[key]==b[key],(gid,key,a[key],b[key])
    install(enabled=True)
    assert risk_patterns(("Gemstone Caverns","Mox Diamond","Plains","Plains",
      "Sol Ring","Brainstone","Lunarch Mantle"))
    assert not risk_patterns(("Plains",)*7)
    return {"status":"PASS","n_no_fallback_exact_full_history_parity":8,
        "futures":FUTURES,"prior":PRIOR,"margin":MARGIN,
        "change_margin":CHANGE_MARGIN,"disagreement":DISAGREEMENT,
        "policy":POLICY}
if __name__=="__main__":
    print("V43_HYBRID_SELECTIVE_SMOKE_PASS",json.dumps(selftest(),sort_keys=True),flush=True)
