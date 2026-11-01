#!/usr/bin/env python3
"""Isolated neutral-bottom metamorphic test against unchanged strict goldfish.

Three proposed "blank" cards are exchanged between final kept hand and the
London bottom, preserving EVERY ramp card, tutor, actual unseen 92-card order,
seat, and combo pieces. Compares original state-keyed dice to a diagnostic
counterfactual-coupled chance key where only these three cards are aliases.
This is a *chance-coupling diagnostic*, NOT new validated rules.
"""
from __future__ import annotations
import argparse, collections, gzip, hashlib, json, random, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import dack_paired_counterfactual_v5_stable_chance_20261031 as teacher
import dack_mulligan_stateless_roll_v1_20261031 as dice

ref=teacher.reference
BLANKS=("Void Mirror","Charitable Levy","Touch the Spirit Realm")
SAMPLES=12
SCENARIOS={
    "bucknard_key":{
        "core":("Bucknard's Everfull Purse","Plains","Sol Ring","Voltaic Key"),
        "mechanism":"Bucknard chance, no initial Mox; proposed neutral fillers",
    },
    "mana_vault_tutor":{
        "core":("Ancient Tomb","Mana Vault","Plains","Enlightened Tutor"),
        "mechanism":"Deterministic acceleration and a tutor, no initial Mox",
    },
    "mox_opal_exception":{
        "core":("Mox Opal","Plains","Sol Ring","Mana Vault"),
        "mechanism":"Void Mirror may supply artifact count / metalcraft",
    },
    "chrome_mox_exception":{
        "core":("Chrome Mox","Plains","Sol Ring","Mana Vault"),
        "mechanism":"Void Mirror colorless vs white imprint candidates",
    },
}
def stable_seed(*args):
    return int.from_bytes(hashlib.sha256(
        json.dumps(("DACK_V29_NEUTRAL_BOTTOM_READONLY",*args),
             separators=(",",":")).encode()).digest()[:8],"big")

def normalized_roll(state,card,sides,salt=0):
    # Research-only common random numbers. Not allowed to enter approved solver.
    pairs=[]
    for name,value in dice.canonical_state_for_chance(state):
        if name in {"hand","library","grave","exile"}:
            value=tuple("__FILLER__" if x in BLANKS else x for x in value)
            if name in {"hand","grave","exile"}:
                value=tuple(sorted(value))
        pairs.append((name,value))
    payload=json.dumps(
        (int(dice.buck.TRIAL_SEED),str(card),int(sides),int(salt),tuple(pairs)),
        ensure_ascii=False,separators=(",",":")).encode()
    return 1+int.from_bytes(hashlib.sha256(payload).digest()[:8],"big")%int(sides)

def one(scenario,start,samples,out):
    if scenario not in SCENARIOS or not 101000<=start<101100 or samples!=SAMPLES:
        raise ValueError("v29 fixed diagnostic: named scenario and 101k IDs / twelve futures")
    assert 101000<=start and start+samples<=101100
    a=teacher.audit()
    assert a["status"]=="PASS"
    assert dice.buck._roll is dice.stable_roll
    core=SCENARIOS[scenario]["core"]
    seven=core+BLANKS
    assert len(seven)==7 and len(set(seven))==7
    pool=collections.Counter(ref.VARIANTS["one_key_34"])
    pool.subtract(seven)
    assert not any(n<0 for n in pool.values())
    unknown=tuple(x for x,n in sorted(pool.items()) for _ in range(n))
    assert len(unknown)==92
    ids=range(start,start+samples)
    rows=[]
    try:
      for gid in ids:
        gseed=stable_seed("test_game",scenario,gid)
        seat=random.Random(gseed).randrange(4)
        rem=list(unknown)
        random.Random(stable_seed("unseen",gid)).shuffle(rem)
        outcomes={}
        for mode in ("original_full_state_dice","coupled_filler_dice"):
          dice.buck._roll=dice.stable_roll if mode=="original_full_state_dice" else normalized_roll
          group=[]
          for keep_blank in BLANKS:
            hand=ref.d.sort_hand(core+(keep_blank,))
            bottom=tuple(x for x in BLANKS if x!=keep_blank)
            assert len(hand)==5 and len(bottom)==2
            assert collections.Counter(hand+bottom+tuple(rem))==collections.Counter(ref.VARIANTS["one_key_34"])
            ref.sim.reset_caches()
            ref.sim.root.install("one_key_34")
            ref.sim.m.set_trial_seed(gseed)
            t0=time.monotonic()
            turn=int(ref.d._win_turn_from_unknown_order(
                tuple(hand),tuple(rem)+bottom,seat,beam=160,max_turn=3) or 0)
            group.append({
                "keep_blank":keep_blank,
                "bottom":bottom,
                "turn":turn,
                "seconds":round(time.monotonic()-t0,4),
            })
          outcomes[mode]=group
        rows.append({
          "game_id":gid,"seat":seat,
          "original_dice_turns":[x["turn"] for x in outcomes["original_full_state_dice"]],
          "coupled_dice_turns":[x["turn"] for x in outcomes["coupled_filler_dice"]],
          "alternatives":outcomes,
          "original_all_same_turn":len(set(x["turn"] for x in outcomes["original_full_state_dice"]))==1,
          "coupled_all_same_turn":len(set(x["turn"] for x in outcomes["coupled_filler_dice"]))==1,
        })
        print("DACK_V29_METAMORPHIC_GAME",scenario,gid,seat,rows[-1]["original_dice_turns"],
              rows[-1]["coupled_dice_turns"],flush=True)
    finally:
      dice.buck._roll=dice.stable_roll
    report={
      "schema":"dack_v29_neutral_bottom_candidate_chance_coupling",
      "status":"PASS",
      "scenario":scenario,"description":SCENARIOS[scenario]["mechanism"],
      "fixed_visible_core":core,"three_filler_candidates":BLANKS,
      "game_ids":[start,start+samples-1],
      "n_games":samples,
      "unknown_92_identical_across_bottoms":True,
      "all_three_candidates_preserve_core_mana_and_tutors":True,
      "normalizer_scope":"chance_roll_hash_only__not_card_rules_or_gameplay",
      "diagnostic_mode_NOT_approved":True,
      "original_dice_all_equal_n":sum(r["original_all_same_turn"] for r in rows),
      "coupled_dice_all_equal_n":sum(r["coupled_all_same_turn"] for r in rows),
      "original_dice_turn_disagreement_n":sum(not r["original_all_same_turn"] for r in rows),
      "coupled_dice_turn_disagreement_n":sum(not r["coupled_all_same_turn"] for r in rows),
      "results":rows,
      "interpretation_guard":"Different turns under original keyed chance do not establish actual strategy difference; correlated chance is a diagnostic, not an approved engine replacement. Remaining difference can be due to real card roles or beam-search heuristics."
    }
    path=Path(out);path.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path,"wt") as f:json.dump(report,f,sort_keys=True)
    print("DACK_V29_NEUTRAL_BOTTOM_SCENARIO_PASS",scenario,report["original_dice_turn_disagreement_n"],
          report["coupled_dice_turn_disagreement_n"],flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--scenario",choices=tuple(SCENARIOS),required=True)
    p.add_argument("--start",type=int,default=101000)
    p.add_argument("--samples",type=int,default=SAMPLES)
    p.add_argument("--out",required=True)
    x=p.parse_args();one(x.scenario,x.start,x.samples,x.out)
