#!/usr/bin/env python3
"""v31: Actual counterfactual Q(KEEP) vs Q(MULL) under a frozen continuation policy.

For a dealt visible seven at each selected London stage, evaluate:
 KEEP: same v14-128 candidate bottom, physically shuffle unknown 92 and
       deploy unchanged strict stable-dice beam160;
 MULL: restore all 99 physical slots, reshuffle future London stages, and
       follow the FROZEN v27 T2-only DP policy from the NEXT stage onwards,
       then deploy unchanged strict stable-dice beam160.

All actions are ex-ante decisions. Neither model nor selected bottom sees
any sampled future; Qs are outcome LABELS only. Both arms get a common
game/stage/future trial seed and seat. Games within a stage share seven/seat
and differ only in fresh future randomness. There is no exact bottom
imitation loss. It estimates *one-step action advantage with downstream
frozen v27*, not an optimal-policy value or cEDH multiplayer winrate.

Do not fit on validation/test groups. No changes to v5/v14/v27.
"""
from __future__ import annotations
import argparse,collections,gzip,hashlib,json,random,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import dack_paired_counterfactual_v27_T2_only_DP_20261101 as frozen
import dack_paired_counterfactual_v22_all_stage_real_keep_DP_20261101 as controller
import dack_mulligan_teacher_features_v13_20261031 as feats
import dack_mulligan_keep_value_v22_20261101 as estimator
from dack_simulator.validation.collect_teacher_london_v13 import finalists

ref=controller.ref
d=ref.d
PROTO="DACK_V31_ONE_STEP_Q_KEEP_MULL_UNSEEN_LONDON_ROLLOUT_V1"
SPLITS={"train":(103000,103047),"validation":(103048,103063),
        "test":(103064,103079)}
STAGES=(0,1,3,5)
N_FUTURES=6
BEAM=160

def stable_seed(*args):
    data=json.dumps((PROTO,*args),separators=(",",":")).encode()
    return int.from_bytes(hashlib.sha256(data).digest()[:8],"big")

def choose_candidate(seven,unknown,seat,stage):
    kn=int(ref.sim.STAGES[stage]);pool=collections.Counter(unknown)
    scored=[]
    for ix,c in enumerate(finalists(seven,kn,unknown)):
        x=feats.extract(seven,c["hand"],c["bottom"],pool,seat,kn,
                        stage,c["struct_rank"],ix)
        vote=feats.score_head(controller.old.MODEL,"choice_trees",x)
        scored.append((vote,-ix,c,x))
    assert scored
    score,minus_idx,c,features=max(scored,key=lambda x:(x[0],x[1]))
    return c,features,-minus_idx

def future_orders(gid,stage,j):
    """Actual fresh 99-slot reshuffles for EACH later London stage."""
    orders=[]
    for future_stage in range(stage+1,len(ref.sim.STAGES)):
        x=list(ref.SLOTS)
        random.Random(stable_seed("later_london_shuffle",gid,stage,j,future_stage)).shuffle(x)
        orders.append(tuple(x))
    return orders

def choose_mull_continuation(deck,seat,starting_stage,orders):
    """Exactly the frozen v27 seat thresholds and v14 bottoms, after forced MULL."""
    assert len(orders)==len(ref.sim.STAGES)-starting_stage
    thresholds=controller.DP["seat_continuations"][str(seat)]["thresholds_by_london_stage"]
    history=[]
    for s,order in zip(range(starting_stage,len(ref.sim.STAGES)),orders):
        kn=int(ref.sim.STAGES[s])
        seven=tuple(deck[slot] for slot in order[:7])
        unknown=tuple(deck[slot] for slot in order[7:])
        c,x,idx=choose_candidate(seven,unknown,seat,s)
        u=estimator.predict(controller.MODEL,x)
        threshold=float(thresholds[s])
        keep=(kn==1 or u>=threshold)
        history.append({"stage":s,"keep_n":kn,"kept":keep,
                        "candidate_index":idx,"prediction":u,"threshold":threshold})
        if keep:
            hand=tuple(c["hand"]);bottom=tuple(c["bottom"])
            assert collections.Counter(hand)+collections.Counter(bottom)==collections.Counter(seven)
            assert len(unknown)==92
            return d.State(1,hand,unknown+bottom),history
    raise AssertionError("final one card must keep")

def audit():
    r=frozen.audit()
    assert r["status"]=="PASS"
    assert controller.MODEL["T3_reward_is_exactly_zero"]
    assert controller.DP["model_approved"] is False
    assert controller.old.MODEL["deployed_policy_approved"] is False
    assert tuple(ref.sim.STAGES)==(7,7,6,5,4,3,2,1)
    assert ref.SPEC["beam"]==160
    assert 0 not in {int(x) for x in SPLITS["train"]}
    return r

def one_game(gid):
    game_seed=int(ref.SPEC["seed_base"])+int(gid)*ref.SEED_STRIDE
    seat,orders=ref.stage_slots(game_seed)
    deck=ref.SLOT_VARIANTS["one_key_34"]
    rows=[]
    for s in STAGES:
        kn=int(ref.sim.STAGES[s])
        order=orders[s]
        seven=tuple(deck[slot] for slot in order[:7])
        hidden=tuple(deck[slot] for slot in order[7:])
        assert len(seven)==7 and len(hidden)==92
        c,x,ix=choose_candidate(seven,hidden,seat,s)
        hand=tuple(c["hand"]);bottom=tuple(c["bottom"])
        assert len(hand)==kn
        # Frozen v27 already predicted the keep action; only use as a
        # comparator, not as a training label or hidden future.
        pred=estimator.predict(controller.MODEL,x)
        threshold=float(controller.DP["seat_continuations"][str(seat)]["thresholds_by_london_stage"][s])
        old_keep=pred>=threshold
        labels=[]
        for j in range(N_FUTURES):
            seed=stable_seed("gameplay_roll_seed",gid,s,j)
            sh=list(hidden)
            random.Random(stable_seed("keep_hidden_shuffle",gid,s,j)).shuffle(sh)
            assert collections.Counter(sh)==collections.Counter(hidden)
            ref.sim.reset_caches()
            ref.sim.root.install("one_key_34")
            ref.sim.m.set_trial_seed(seed)
            k=int(d._win_turn_from_unknown_order(
                hand,tuple(sh)+bottom,seat,beam=BEAM,max_turn=3) or 0)
            # MULL restores deck's seven cards and reshuffles physically;
            # there is NO difference in card inventory or deck identity.
            after=future_orders(gid,s,j)
            state,history=choose_mull_continuation(deck,seat,s+1,after)
            ref.sim.reset_caches()
            ref.sim.root.install("one_key_34")
            ref.sim.m.set_trial_seed(seed)
            m=int(d._win_turn_from_unknown_order(
                state.hand,state.library,seat,beam=BEAM,max_turn=3) or 0)
            assert k in (0,1,2,3) and m in (0,1,2,3)
            labels.append({"future_index":j,
                           "keep_turn":k,"mull_turn":m,
                           "mull_london_keep_stage":history[-1]["stage"]})
        kt=sum(0<t["keep_turn"]<=2 for t in labels)/N_FUTURES
        mt=sum(0<t["mull_turn"]<=2 for t in labels)/N_FUTURES
        k3=sum(0<t["keep_turn"]<=3 for t in labels)/N_FUTURES
        m3=sum(0<t["mull_turn"]<=3 for t in labels)/N_FUTURES
        rows.append({
            "game_id":gid,"seat":seat,"stage":s,"keep_n":kn,
            "seven":list(seven),"hand":list(hand),"bottom":list(bottom),
            "unknown_counts":dict(sorted(collections.Counter(hidden).items())),
            "struct_rank":c["struct_rank"],"candidate_index":ix,
            "features":x,"original_v27_predicted_keep_T2":pred,
            "original_v27_continuation_T2":threshold,
            "original_v27_action_keep":bool(old_keep),
            "rollouts":labels,
            "empirical_Q_keep_T2":kt,"empirical_Q_mull_T2":mt,
            "empirical_advantage_keep_minus_mull_T2":kt-mt,
            "empirical_Q_keep_T3":k3,"empirical_Q_mull_T3":m3,
            "empirical_advantage_keep_minus_mull_T3":k3-m3,
            "outcome_label_is_not_policy_feature":True,
            "bottom_imitation_not_a_target":True,
        })
    return rows

def run(start,games,split,out):
    if split not in SPLITS or games!=4 or N_FUTURES!=6:
        raise ValueError("frozen v31 four-physical-game shard/six paired future protocol")
    a,z=SPLITS[split]
    if not (a<=start and start+games-1<=z):
        raise ValueError("no cross-split or non-103k game IDs permitted")
    audit()
    t0=time.monotonic()
    rows=[]
    for gid in range(start,start+games):
        r=one_game(gid);rows.extend(r)
        print("V31_Q_ACTION_GAME",gid,
              [(x["stage"],round(x["empirical_advantage_keep_minus_mull_T2"],3))
               for x in r],
              round(time.monotonic()-t0,2),flush=True)
    sha=hashlib.sha256(Path("models/dack_v27_expanded_T2_only_value_EXPERIMENTAL.json").read_bytes()).hexdigest()
    dp_sha=hashlib.sha256(Path("models/dack_v27_T2_only_continuations_EXPERIMENTAL.json").read_bytes()).hexdigest()
    outdoc={
      "schema":"dack_v31_actual_two_action_regret_103k",
      "status":"PASS","split":split,"game_ids":[start,start+games-1],
      "physical_groups":games,"stages":STAGES,
      "futures_per_arm":N_FUTURES,
      "actual_beam":BEAM,
      "frozen_v27_model_sha256":sha,"frozen_v27_dp_sha256":dp_sha,
      "v5_v14_v27_code_unchanged":True,
      "no_96k_97k_98k_99k_outcome_training":True,
      "T2_is_primary":True,
      "forced_keep_vs_forced_mull_labels":True,
      "mull_restores_full_99_and_resamples_each_later_london_stage":True,
      "same_seat_and_gameplay_roll_seed_between_arms":True,
      "futures_conditional_on_visible_stage_hand":True,
      "shared_hash_seed_does_not_guarantee_identical_future_information_sets":True,
      "no_hidden_order_in_model_inputs":True,
      "downstream_mull_uses_frozen_v27_policy_only":True,
      "outcomes":rows
    }
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(dest,"wt") as f:json.dump(outdoc,f,sort_keys=True)
    print("V31_ACTION_COUNTERFACTUAL_SHARD_PASS",split,start,len(rows),
          round(time.monotonic()-t0,2),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--split",required=True,choices=tuple(SPLITS))
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--games",type=int,default=4)
    p.add_argument("--out",required=True)
    a=p.parse_args();run(a.start,a.games,a.split,a.out)
