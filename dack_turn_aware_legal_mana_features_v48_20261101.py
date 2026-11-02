#!/usr/bin/env python3
"""Read-only, observable turn-aware resource witness features for Dack v43.

This is a LEGALITY-FIRST SUBSET of the installed full physical rules engine.
Positive no-draw witnesses use genuine engine actions/payments. Bounded search
is NOT exhaustive: a negative means not found within beam/depth, not impossible.

Unseen top decks / rearrangements / fetches / tutor-to-hand / tutors-to-board
are deliberately EXCLUDED from the strict no-draw mana witness. All branches
must preserve library tuple EXACTLY. Tutors are a separate observable category
and later research axis, not silently counted as guaranteed usable mana.
No source hand's physical hidden order is consulted by any output feature.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import replace
from pathlib import Path
import hashlib,json,sys,time
ROOT=Path(__file__).resolve().parent
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import dack_paired_counterfactual_v43_v27_max_Q2_20261101 as v43
from dack_simulator.validation.collect_teacher_london_v13 import finalists
ref=v43.ref
d=ref.d
SCHEMA="dack_v48_turn_aware_strict_no_future_draw_legality_witness_v1"
RULES="actual_runtime_v43_inherited_mana_payments_gemstone_exile_guard"
MAX_DEP=10;BEAM=48
# Source-skill positions must remain separate, in particular Workshop artifact
# restrictions, Cavern Dack-white restrictions and Untaidake legend restrictions.
RESOURCE_KEYS=("w","c","any","restricted_legend","restricted_artifact",
               "restricted_dack_white","treasures","spawn")
SPECIAL=("Lion's Eye Diamond","Mox Diamond","Mox Opal","Chrome Mox","Lotus Petal",
 "Gemstone Caverns","Ancient Tomb","City of Traitors","Mishra's Workshop",
 "Untaidake, the Cloud Keeper","Cavern of Souls","Sol Ring","Mana Vault",
 "Grim Monolith","Basalt Monolith","Moonsilver Key","Voltaic Key",
 "The Mycosynth Gardens","Scroll Rack","Brainstone","Enlightened Tutor",
 "Tezzeret, Cruel Captain")
def visible_seed(seven,keep_n,stage,seat):
    # Stable identifier for reproducibility; not any hidden92 order.
    return hashlib.sha256(json.dumps([sorted(seven),keep_n,stage,seat],
                  separators=(",",":")).encode()).hexdigest()[:20]
def mana_budget(s):
    """Within ONE legal state, maximize generic after paying exactly W W.

    Artifact-only mana cannot pay a nonartifact commander. Legend-only mana
    can pay generic. Cavern's special Dack-only mana can pay W or generic.
    """
    white=s.w+s.any+s.restricted_dack_white
    total=s.w+s.c+s.any+s.restricted_legend+s.restricted_dack_white
    generic_left=(total-2) if white>=2 else -1
    reduction=int(any(d.effective_name(p)=="Pearl Medallion" for p in s.battlefield))
    exact_cast=bool(d.can_cast_dack(s))
    return {"white_pips_possible":min(2,white),
            "available_white_mana":white,"generic_after_WW":generic_left,
            "total_commander_usable":total,
            "artifact_only_unusable":s.restricted_artifact,
            "commander_generic_cost":4-reduction,
            "can_cast":exact_cast}
def resources(s):
    return {k:int(getattr(s,k)) for k in RESOURCE_KEYS}
def _actions(s):
    if d.city_trigger_pending(s):
        funcs=(d.tap_mana_actions,d.utility_actions,d.nasty_mana_actions,d.resolve_city_trigger_actions)
    else:
        funcs=(d.play_land_actions,d.tap_mana_actions,d.utility_actions,
               d.special_actions,d.v03_actions,d.nasty_mana_actions,d.cast_actions)
    for fun in funcs:
        for q in fun(s):
            # Necessary condition: no card was drawn, looked at and manipulated,
            # tutored, shuffled or moved from the unseen 92-card library.
            # This makes our witness conservative with respect to tutor lines.
            if q.library!=s.library:continue
            yield q
def _rank(s):
    b=mana_budget(s)
    # Resource and persistence score, not a probability or model label.
    # Same-state joint coverage matters more than independent mana maxima.
    joint=3*b["white_pips_possible"]+min(7,max(-1,b["generic_after_WW"]))
    reusable=sum(not p.tapped for p in s.battlefield)
    return (int(b["can_cast"])*10000+joint*20+
            min(14,b["total_commander_usable"])*3+4*reusable+
            min(8,len(s.battlefield)))
def search_main(states,beam=BEAM,depth=MAX_DEP):
    curr=list(states);seen={d.key(s) for s in curr};passes={}
    wins=[];max_white=0;max_generic=-1;max_commander=0
    best_joint=None
    expanded=0;considered=0
    for iteration in range(depth+1):
        nxt=[]
        for s in curr:
            expanded+=1
            b=mana_budget(s)
            max_white=max(max_white,b["available_white_mana"])
            max_generic=max(max_generic,b["generic_after_WW"])
            max_commander=max(max_commander,b["total_commander_usable"])
            if best_joint is None or (b["white_pips_possible"],max(-1,b["generic_after_WW"]))>(best_joint[0],best_joint[1]):
                best_joint=(b["white_pips_possible"],b["generic_after_WW"],s)
            if b["can_cast"] and not d.city_trigger_pending(s):wins.append(s)
            if not d.city_trigger_pending(s):
                k=d.key(s)
                if k not in passes or _rank(s)>_rank(passes[k]):passes[k]=s
            if iteration==depth:continue
            for q in _actions(s):
                considered+=1
                k=d.key(q)
                if k in seen:continue
                seen.add(k);nxt.append(q)
        if not nxt:break
        nxt.sort(key=_rank,reverse=True)
        # Exact original state-key de-dup; no speculative 'mana dominance'.
        curr=nxt[:beam]
    if best_joint is None:
        raise AssertionError("empty frontier")
    pass_states=sorted(passes.values(),key=_rank,reverse=True)[:beam]
    white,generic,example=best_joint
    witness=next((s for s in wins if d.can_cast_dack(s)),None)
    return {"cast_witness":witness,"pass_states":pass_states,
       "max_white":max_white,"max_generic_after_WW":max_generic,
       "max_commander_usable":max_commander,
       "best_joint_white":white,"best_joint_generic_after_WW":generic,
       "best_joint_state":example,
       "expanded_states":expanded,"considered_actions":considered,
       "beam":beam,"depth":depth}
def _advance_turn_no_draw(s):
    q=d.untap_and_begin(replace(s,turn=2))
    q=d.add_opponent_cycle_resources(q)
    out=[]
    for uq in d.mana_vault_upkeep_options(q):
        # No unknown library cards are drawn at the start of T2.
        uq=d.saga_advance(uq);uq=d.begin_first_main(uq)
        if uq.library==s.library:out.append(uq)
    return out
def analyze(seven,unknown,seat,keep_n=7,stage=0,bottom=(),beam=BEAM,depth=MAX_DEP):
    seven=tuple(seven);unknown=tuple(unknown);bottom=tuple(bottom)
    assert len(seven)==7 and len(unknown)==92
    assert len(bottom)==7-keep_n
    keep=Counter(seven)-Counter(bottom)
    assert sum(keep.values())==keep_n and all(x>=0 for x in keep.values())
    hand=tuple(sorted(keep.elements()))
    # Convert hidden order to a **canonical multiset**, and append known
    # bottom cards. The feature cannot see the actual order by construction.
    library=tuple(sorted(unknown))+tuple(sorted(bottom))
    if len(hand)+len(library)!=99:raise AssertionError("physical reconstruction")
    allcards=Counter(ref.SLOT_VARIANTS["one_key_34"].values())
    assert Counter(hand)+Counter(library)==allcards
    assert ref.sim.STAGES[stage]==keep_n
    begin=d.State(1,hand,library)
    pre=d._pregame_states(begin,seat)
    assert pre and all(z.library==library for z in pre)
    a=search_main(pre,beam=beam,depth=depth)
    # Resource witness 'yes' is proved by the installed can_cast_dack gate
    # in a trace reachable via installed physical engine actions.
    second=[]
    for p in a["pass_states"]:
        second+=_advance_turn_no_draw(p)
    if not second:
        second=[d.begin_first_main(d.untap_and_begin(replace(s,turn=2))) for s in a["pass_states"]]
    b=search_main(second,beam=beam,depth=depth)
    w1=a["cast_witness"];w2=b["cast_witness"]
    q1=mana_budget(a["best_joint_state"])
    q2=mana_budget(b["best_joint_state"])
    out={"schema":SCHEMA,"visible_seed":visible_seed(seven,keep_n,stage,seat),
      "seat":int(seat),"keep_n":keep_n,"stage":stage,
      "hand":list(hand),"bottom":list(bottom),
      "mana_witness_T1_no_draw":bool(w1),
      "mana_witness_T2_no_draw":bool(w1 or w2),
      "T1":{"white_max":a["max_white"],
         "generic_after_WW_max":a["max_generic_after_WW"],
         "total_commander_usable_max":a["max_commander_usable"],
         "joint_white":q1["white_pips_possible"],
         "joint_generic_after_WW":q1["generic_after_WW"],
         "artifact_restricted_in_joint":q1["artifact_only_unusable"],
         "states":a["expanded_states"],"actions":a["considered_actions"]},
      "T2":{"white_max":b["max_white"],
         "generic_after_WW_max":b["max_generic_after_WW"],
         "total_commander_usable_max":b["max_commander_usable"],
         "joint_white":q2["white_pips_possible"],
         "joint_generic_after_WW":q2["generic_after_WW"],
         "artifact_restricted_in_joint":q2["artifact_only_unusable"],
         "states":b["expanded_states"],"actions":b["considered_actions"]},
      "tutor_dependency_not_included_in_witness":True,
      "no_future_draw_card_was_used":True,
      "bounded_search_negative_is_not_impossibility_proof":True,
      "physical_rule_source":RULES,"beam":beam,"depth":depth}
    for which,s in (("T1",w1),("T2",w2)):
        if s is not None:
            assert d.can_cast_dack(s)
            assert s.library==library,"witness cannot have looked at unseen cards"
            out[which+"_witness"]={"resources":resources(s),
              "battlefield":[{"name":p.name,"tapped":p.tapped,"aux":p.aux}
                             for p in s.battlefield],
              "unspent_mana_total":mana_budget(s)["total_commander_usable"],
              "white_coverage":mana_budget(s)["white_pips_possible"],
              "generic_after_WW":mana_budget(s)["generic_after_WW"]}
    return out
def smoke():
    v43.audit()
    deck=ref.SLOT_VARIANTS["one_key_34"]
    cases=[
     ["Plains","Plains","Ancient Tomb","Sol Ring","Mox Diamond","Mana Vault","Enlightened Tutor"],
     ["Mishra's Workshop","Plains","Sol Ring","Mana Vault","Mox Opal","Plains","Chrome Mox"],
     ["Cavern of Souls","City of Traitors","Mana Vault","Chrome Mox","Silence","Plains","Sol Ring"],
     ["Gemstone Caverns","Mox Diamond","Ancient Tomb","Sol Ring","Plains","Plains","Enlightened Tutor"],
    ]
    rows=[]
    for seat,seven in enumerate(cases):
        assert not (Counter(seven)-Counter(deck.values()))
        rem=list(deck.values())
        for c in seven:rem.remove(c)
        before=time.perf_counter()
        p=analyze(seven,rem,seat,beam=24,depth=8)
        q=analyze(seven,list(reversed(rem)),seat,beam=24,depth=8)
        for t in ("mana_witness_T1_no_draw","mana_witness_T2_no_draw","T1","T2"):
            assert p[t]==q[t],(seat,t,p[t],q[t])
        rows.append({"seat":seat,"T1":p["mana_witness_T1_no_draw"],
            "T2":p["mana_witness_T2_no_draw"],"t1_budget":p["T1"],
            "t2_budget":p["T2"],"seconds":round(time.perf_counter()-before,3)})
    # A state with 3 mana reserved for artifact spells cannot satisfy
    # an otherwise short commander cast.
    library=tuple(sorted(d.COMBO_CREATURES))
    bad=d.State(1,(),library,w=1,c=1,restricted_artifact=8)
    assert not mana_budget(bad)["can_cast"]
    assert mana_budget(bad)["artifact_only_unusable"]==8
    bad2=d.State(1,(),library,w=1,c=3,restricted_legend=2)
    assert not mana_budget(bad2)["can_cast"]
    good=d.State(1,(),library,w=1,c=3,restricted_dack_white=2)
    assert mana_budget(good)["can_cast"]
    return {"status":"PASS","schema":SCHEMA,"cases":rows,
       "hidden92_reversal_invariant":True,"positive_cast_uses_actual_gate":True,
       "mana_restricted_pool_cases_checked":True}
if __name__=="__main__":
    print("DACK_V48_MANA_WITNESS_SMOKE_PASS",json.dumps(smoke(),sort_keys=True),flush=True)
