#!/usr/bin/env python3
"""STRATIFIED offline London beam-label collector: natural + legal fast starts.

Physical slots are uniformly shuffled *conditional on a documented set of
preselected opening-hand cards*. All seven cards exist in the physical deck.
The 92 unknown cards remain a complete physical multiset, shuffled separately
for each hidden-future rollout. Never disclose future order to the learner.

Enrichment is intentionally biased. DO NOT claim pooled scores or
temperature calibration are representative for naturally distributed keeps.
Calibrate later on independently sampled policy-kept (or properly weighted)
distribution; use these labels initially for learning rare T1 signatures.
"""
from __future__ import annotations
from collections import Counter
import argparse
import gzip
import json
from pathlib import Path
import random
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

import dack_simulator.validation.generate_offline_london_labels_v8 as base

ref=base.ref
d=base.d
SCHEMA=base.SCHEMA
PROTOCOL="DACK-OFFLINE-STRATIFIED-V9"
# All choices are from the 99-card one-Key physical list. Spell names are
# concrete independent resources, NOT predictions of future draws.
FAST_CORES={
    "led_vault_tomb_white":("Lion's Eye Diamond","Mana Vault","Ancient Tomb","Plains"),
    "led_ring_tomb_white":("Lion's Eye Diamond","Sol Ring","Ancient Tomb","Plains"),
    "led_vault_ring_white":("Lion's Eye Diamond","Mana Vault","Sol Ring","Plains"),
    "led_grim_tomb_white":("Lion's Eye Diamond","Grim Monolith","Ancient Tomb","Plains"),
    "led_vault_city_white":("Lion's Eye Diamond","Mana Vault","City of Traitors","Plains"),
    "led_ring_city_white":("Lion's Eye Diamond","Sol Ring","City of Traitors","Plains"),
    "led_vault_tomb_key":("Lion's Eye Diamond","Mana Vault","Ancient Tomb","Voltaic Key","Plains"),
    "led_ring_vault_key":("Lion's Eye Diamond","Sol Ring","Mana Vault","Voltaic Key","Plains"),
    "gemstone_led_ring_white":("Gemstone Caverns","Lion's Eye Diamond","Sol Ring","Plains"),
    "led_mox_tomb_white":("Lion's Eye Diamond","Mox Diamond","Ancient Tomb","Plains"),
    "vault_ring_tomb_white":("Mana Vault","Sol Ring","Ancient Tomb","Plains"),
    "zero_rock_suite":("Mana Vault","Sol Ring","Chrome Mox","Plains"),
}
# Four natural states for each eight explicitly enriched states.
SCHEDULE=("natural","led_vault_tomb_white","led_ring_tomb_white",
          "natural","led_vault_ring_white","led_grim_tomb_white",
          "natural","led_vault_city_white","led_ring_city_white",
          "natural","led_vault_tomb_key","led_ring_vault_key",
          "natural","gemstone_led_ring_white","led_mox_tomb_white",
          "natural","vault_ring_tomb_white","zero_rock_suite")
# 6/18 natural, 12/18 enriched. Cycle known before any game outcomes.

def stratum_for(gid,split):
    lo,_=base.ALLOWED_SPLITS[split]
    return SCHEDULE[(int(gid)-lo)%len(SCHEDULE)]

def conditioned_opening(gid,variant,split):
    """Random physical 7 conditional on a FORCED CORE; never fake card copies."""
    if variant not in ref.VARIANTS:raise KeyError(variant)
    kind=stratum_for(gid,split)
    names=ref.SLOT_VARIANTS[variant]
    seed=int(ref.SPEC["seed_base"])+int(gid)*ref.SEED_STRIDE
    seat,orders=ref.stage_slots(seed)
    if kind=="natural":
        stage=(gid-base.ALLOWED_SPLITS[split][0])%len(ref.sim.STAGES)
        order=tuple(orders[stage])
        selected=()
    else:
        # Enriched examples focus on opening 7, where rare T1 lines can exist.
        stage=(gid-base.ALLOWED_SPLITS[split][0])%2
        rng=random.Random(base.seeded(PROTOCOL,gid,variant,"core"))
        core=FAST_CORES[kind]
        ids_by_name={}
        for slot in ref.SLOTS:
            ids_by_name.setdefault(names[slot],[]).append(slot)
        selected=[]
        for card in core:
            available=[s for s in ids_by_name[card] if s not in selected]
            if not available:raise ValueError(("forced card missing",card,variant))
            selected.append(rng.choice(available))
        rng.shuffle(selected)
        remaining=[s for s in ref.SLOTS if s not in selected]
        rng.shuffle(remaining)
        order=tuple(selected+remaining)
        selected=tuple(selected)
        if kind.startswith("gemstone") and seat==0:
            # Do NOT condition seat as a function of future outcomes; explicitly
            # record that this stratum forces nonstarting seats.
            seat=1+rng.randrange(3)
    seven=tuple(names[s] for s in order[:7])
    unknown=tuple(names[s] for s in order[7:])
    assert len(order)==len(set(order))==99
    assert len(seven)==7 and len(unknown)==92
    assert Counter(seven)+Counter(unknown)==Counter(ref.VARIANTS[variant])
    for card in FAST_CORES.get(kind,()):
        assert card in seven,(gid,kind,card,seven)
    return {
        "kind":kind,"stage":stage,"seat":seat,
        "keep_n":int(ref.sim.STAGES[stage]),
        "seven":seven,"unknown":unknown,
        "forced_core":FAST_CORES.get(kind,()),
        "seed_protocol":PROTOCOL,
        "sampled_order":order,
    }

def generate(start,games,out,variant="one_key_34",split="train",
             candidates=2,draws=4):
    lo,hi=base.ALLOWED_SPLITS[split]
    if start<lo or start+games-1>hi:raise ValueError("split ID range violated")
    if min(games,candidates,draws)<1:raise ValueError("positive sizes")
    base.teacher.audit()
    ref.sim.root.install(variant)
    output=Path(out);output.parent.mkdir(parents=True,exist_ok=True)
    counts=Counter()
    begin=time.monotonic()
    meta={
        "type":"metadata","schema":SCHEMA,"split":split,"start":start,
        "games":games,"variant":variant,"rules":base.LABEL_RULES,
        "beam":160,"max_turn":3,
        "draws_per_choice":draws,"choice_count_max":candidates,
        "source_physical_sha256":ref.source_sha(ref.MANIFEST_PATH),
        "source_spec_sha256":ref.source_sha(ref.SPEC_PATH),
        "sampling_protocol":PROTOCOL,
        "sampling_schedule":SCHEDULE,
        "sampling_conditional_fast_core":True,
        "raw_sample_probabilities_biased":True,
        "not_population_representative":True,
        "future_library_order_not_in_features":True,
        "grouped_by_game_id":True,
        "strata_count_predeclared":len(SCHEDULE),
        "warning":"NOT an unbiased model calibration or naturally dealt policy test"}
    with gzip.open(output,"wt",encoding="utf8") as fp:
        fp.write(json.dumps(meta,separators=(",",":"))+"\n")
        for gid in range(start,start+games):
            case=conditioned_opening(gid,variant,split)
            choices=base.candidates(case["seven"],case["keep_n"],
                                    case["unknown"],case["seat"],candidates)
            for ci,(hand,bottom,struct) in enumerate(choices):
                for j in range(draws):
                    # Crucially, the visible-seven conditioning is independent
                    # of future outcome and of these hidden-library draws.
                    random_key=(PROTOCOL,gid,variant,case["kind"],
                                case["stage"],ci,j)
                    lib=list(case["unknown"])
                    random.Random(base.seeded(*random_key,"hidden")).shuffle(lib)
                    complete=tuple(lib)+tuple(bottom)
                    ref.sim.reset_caches()
                    ref.sim.root.install(variant)
                    ref.sim.m.set_trial_seed(base.seeded(*random_key,"dice"))
                    turn=int(d._win_turn_from_unknown_order(
                        hand,complete,case["seat"],beam=160,max_turn=3) or 0)
                    assert turn in (0,1,2,3)
                    row={
                        "type":"label","game_id":gid,"group_id":f"{variant}:{gid}",
                        "variant":variant,"scenario_stage":case["stage"],
                        "keep_n":case["keep_n"],"seat":case["seat"],
                        "seven":list(case["seven"]),"hand":list(hand),
                        "bottom":list(bottom),
                        "unknown_counts":dict(sorted(Counter(case["unknown"]).items())),
                        "structural_score":list(struct) if isinstance(struct,tuple) else struct,
                        "candidate_index":ci,"future_index":j,"label_turn":turn,
                        "selection_stratum":case["kind"],
                        "selection_forced_core":list(case["forced_core"]),
                        "selection_protocol":PROTOCOL,
                    }
                    fp.write(json.dumps(row,separators=(",",":"))+"\n")
                    counts[f"T{turn}"]+=1;counts["labels"]+=1
                    counts["stratum:"+case["kind"]]+=1
                    if counts["labels"]%8==0:
                        print("STRATIFIED_LABEL_PROGRESS",gid,
                              dict((k,counts[f"T{k}"]) for k in range(4)),
                              round(time.monotonic()-begin,2),flush=True)
            counts["scenarios"]+=1
    print("STRATIFIED_REAL_LABELS_PASS",json.dumps({
        "split":split,"start":start,"games":games,"variant":variant,
        "counts":dict(counts),"elapsed_seconds":round(time.monotonic()-begin,3),
        "warning":"strata are intentional nonrepresentative oversamples"
    },sort_keys=True),flush=True)
    return counts

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--split",choices=("train","calibration"),default="train")
    p.add_argument("--start",type=int,default=20200)
    p.add_argument("--games",type=int,default=4)
    p.add_argument("--variant",choices=list(ref.VARIANTS),default="one_key_34")
    p.add_argument("--candidates",type=int,default=2)
    p.add_argument("--draws",type=int,default=4)
    p.add_argument("--out",default="datasets/dack_stratified_train_v9.jsonl.gz")
    a=p.parse_args()
    generate(a.start,a.games,a.out,a.variant,a.split,a.candidates,a.draws)
