#!/usr/bin/env python3
"""v33: fresh-future counterfactual bottom replay, matched at same London stage.

Precommitted source is ALL 110k N256 games where v5 and v27 kept at the
same London stage but with different final hands (56 groups in preliminary
read-only census). Neither the original 110k win turns nor any future
orders enter a decision. 8 *independent* physical unknown shuffles per
arm in each of two untuned splits. Strict immutable stable-dice beam160.
Each group shares draws and dice seed across arms to reduce variance.
No v5 search calls are needed; archive already records both actual decisions.
NOT a prospective full-game policy comparison; 110k is the selection cohort.
"""
from __future__ import annotations
import argparse
from collections import Counter
import gzip
import glob
import hashlib
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import dack_paired_counterfactual_v5_stable_chance_20261031 as v5

ref = v5.reference
PROTO = "DACK_V33_SAME_STAGE_DIFFERENT_BOTTOM_FRESH_FUTURES_20261101"
SPLITS = ("calibration", "untouched_validation")
FUTURES_PER_SPLIT = 8
N_BLOCKS = 8
GROUPS_PER_BLOCK = 7
BEAM = 160


def seed(*parts):
    s = json.dumps((PROTO, *parts), separators=(",",":")).encode()
    return int.from_bytes(hashlib.sha256(s).digest()[:8], "big")


def selected_groups():
    files = sorted(glob.glob(str(ROOT / "benchmark_results/v32_110k_shards/v32_110k_*.json.gz")))
    assert len(files) == 64, ("need entire frozen 110k cohort",len(files))
    rows = []
    sha = None
    for file in files:
        with gzip.open(file, "rt") as f:
            doc = json.load(f)
        assert doc["schema"] == "dack_v32_prospective_110k_three_policy_strict"
        assert doc["status"] == "PASS" and doc["actual_gameplay_beam"] == 160
        assert doc["test_cohort_never_in_training_or_threshold_calibration"]
        assert doc["same_physical_first_seven_and_seat"]
        if sha is None:
            sha = doc["source_sha256"]
        assert sha == doc["source_sha256"]
        rows.extend(doc["rows"])
    rows.sort(key=lambda r:r["game_id"])
    assert [r["game_id"] for r in rows] == list(range(110000,110256))
    selected = []
    for row in rows:
        a,b = row["v5"],row["v27_frozen"]
        if a["keep_n"] != b["keep_n"]:
            continue
        if Counter(a["history"][-1]["hand"]) == Counter(b["history"][-1]["hand"]):
            continue
        selected.append(row)
    assert len(selected) == 56, ("disagreement group census changed",len(selected))
    return selected,sha


def audit_one(row):
    gid = int(row["game_id"])
    seat, orders = ref.stage_slots(int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE)
    a,b = row["v5"],row["v27_frozen"]
    assert seat == a["seat"] == b["seat"]
    assert a["keep_n"] == b["keep_n"]
    sa = a["history"][-1]; sb = b["history"][-1]
    assert sa["kept"] and sb["kept"] and sa["stage"] == sb["stage"]
    stage = int(sa["stage"])
    assert int(ref.sim.STAGES[stage]) == a["keep_n"]
    order = orders[stage]
    deck = ref.SLOT_VARIANTS["one_key_34"]
    seven = tuple(deck[s] for s in order[:7])
    unknown = tuple(deck[s] for s in order[7:])
    assert len(unknown) == 92
    assert tuple(sa["seven"]) == seven and tuple(sb["seven"]) == seven
    assert tuple(sa["seven_slots"]) == tuple(order[:7])
    assert tuple(sb["seven_slots"]) == tuple(order[:7])
    choices = {}
    for name,h in (("v5",sa),("v27_frozen",sb)):
        hand,bottom = tuple(h["hand"]),tuple(h["bottom"])
        assert len(hand) == a["keep_n"] and len(bottom) == 7-len(hand)
        assert Counter(hand)+Counter(bottom) == Counter(seven)
        choices[name] = (hand,bottom)
    assert Counter(choices["v5"][0]) != Counter(choices["v27_frozen"][0])
    return gid,seat,stage,unknown,choices


def run_block(block,out):
    if not 0 <= block < N_BLOCKS:
        raise ValueError("v33 block must be 0..7")
    report = v5.audit()
    assert report["status"] == "PASS"
    assert ref.SPEC["beam"] == BEAM and len(ref.SLOTS) == 99
    rows,sha = selected_groups()
    subset = rows[block*GROUPS_PER_BLOCK:(block+1)*GROUPS_PER_BLOCK]
    assert len(subset) == GROUPS_PER_BLOCK
    output = []
    t0 = time.monotonic()
    for row in subset:
        gid,seat,stage,unknown,choices = audit_one(row)
        splits = {}
        for split in SPLITS:
            trials = []
            for j in range(FUTURES_PER_SPLIT):
                shuffled = list(unknown)
                random.Random(seed("hidden_92_permutation",gid,split,j)).shuffle(shuffled)
                actual = {}
                for name in ("v5","v27_frozen"):
                    hand,bottom = choices[name]
                    ref.sim.reset_caches()
                    ref.sim.root.install("one_key_34")
                    ref.sim.m.set_trial_seed(seed("blind_effects",gid,split,j))
                    turn = int(ref.d._win_turn_from_unknown_order(
                        hand,tuple(shuffled)+bottom,seat,beam=BEAM,max_turn=3) or 0)
                    assert turn in (0,1,2,3)
                    actual[name] = turn
                trials.append(actual)
            splits[split] = trials
        output.append({
            "game_id":gid,"seat":seat,"stage":stage,"keep_n":row["v5"]["keep_n"],
            "v5_bottom":list(choices["v5"][1]),
            "v27_bottom":list(choices["v27_frozen"][1]),
            "splits":splits,
        })
        print("DACK_V33_REPLAY_GROUP",gid,"stage",stage,"elapsed_s",
              round(time.monotonic()-t0,2),flush=True)
    doc={
        "schema":"dack_v33_same_stage_bottom_fresh_futures",
        "status":"PASS","block":block,
        "selection_ids":[110000,110255],
        "selection_criterion":"ALL same keep stage different kept hand v5 versus frozen v27",
        "selection_uses_original_win_turn":False,
        "source_shas":sha,"actual_beam":BEAM,
        "futures_per_split":FUTURES_PER_SPLIT,
        "same_unknown_shuffle_and_dice_seed_between_arms":True,
        "independent_split_futures":True,
        "mulligan_policy_not_run":True,
        "only_actual_archived_bottom_decisions":True,
        "no_engine_or_model_changes":True,
        "policy_approved":False,
        "rows":output,
    }
    dest = Path(out)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(dest,"wt") as f:
        json.dump(doc,f,sort_keys=True)
    print("DACK_V33_REPLAY_BLOCK_PASS",block,len(output),
          round(time.monotonic()-t0,2),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--block",type=int,required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    run_block(a.block,a.out)
