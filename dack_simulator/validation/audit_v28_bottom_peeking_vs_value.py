#!/usr/bin/env python3
"""Audit v5 London bottom information and independent future generalization.

v5's action must be independent of *actual* hidden-library order. Evaluate its
chosen bottom, structural top3 and frozen v14 choice on completely independent
fresh common hidden 92-card permutations. Teacher's own hand-specific seeded
rollout samples are never used as held-out outcomes or predictor fields.

Audit cohort 99k; read-only diagnostic, NEVER train on these groups.
"""
from __future__ import annotations
import argparse,collections,gzip,hashlib,json,random,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import dack_paired_counterfactual_v5_stable_chance_20261031 as teacher
from dack_simulator.validation.collect_teacher_london_v13 import finalists
import dack_mulligan_teacher_features_v13_20261031 as features

ref=teacher.reference
PROTOCOL="DACK_V28_INDEPENDENT_HIDDEN_ORDER_INVARIANCE_AND_REAL_FUTURES"
STUDENT_PATH=Path("models/v14_curve/v14_teacher_groups_128.json")

def seed(*parts):
    payload=json.dumps((PROTOCOL,*parts),separators=(",",":")).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8],"big")

def selected_index(options,hand,bottom):
    selected=(tuple(hand),tuple(bottom))
    exact=[i for i,v in enumerate(options)
           if (tuple(v["hand"]),tuple(v["bottom"]))==selected]
    assert exact,("v5 choice outside same complete structural finalist set",hand,bottom)
    return exact[0]

def verify_order_invariance(gid,seat,stage,kn,seven,rest,expected_hand,expected_bottom,expected_u):
    # IMPORTANT: only permute *unknown* card order, retaining all 92
    # unseen card identities and the 7 visible hand cards.
    x=list(rest)
    random.Random(seed(gid,stage,"permute_unknown_suffix")).shuffle(x)
    assert collections.Counter(x)==collections.Counter(rest)
    assert len(x)==92 and (x!=list(rest) or len(set(x))==1)
    original=[]
    for unknown in (list(rest),x):
        ref.sim.reset_caches()
        ref.sim.root.install("one_key_34")
        game_seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
        ref.sim.m.set_trial_seed(game_seed)
        raw,ev,struct,hand,bottom,rem,ignored,refined=ref.batch.evaluate_keep(
            seven,kn,unknown,seat)
        original.append((float(raw),tuple(hand),tuple(bottom),tuple(sorted(rem)),bool(refined)))
    assert original[0]==original[1],(
        "V5 ACTUAL UNKNOWN ORDER AFFECTS BOTTOM/UTILITY",gid,stage,original)
    assert original[0][1]==tuple(expected_hand)
    assert original[0][2]==tuple(expected_bottom)
    assert abs(original[0][0]-expected_u)<1e-9
    return True

def student_index(model,seven,kn,unknown,seat,stage,options):
    pool=collections.Counter(unknown)
    scored=[]
    for i,c in enumerate(options):
        x=features.extract(seven,c["hand"],c["bottom"],pool,seat,kn,stage,
                           c["struct_rank"],i)
        vote=features.score_head(model,"choice_trees",x)
        scored.append((vote,-i))
    return max(range(len(scored)),key=lambda i:scored[i])

def choose_option_ids(options,teacher_index,student_ix):
    # Limited to a predeclared independent alternative set; never select
    # using held-out futures. Wider structural pool v5 can target 12.
    ids=list(dict.fromkeys([0,1,2,student_ix,teacher_index]))
    return [i for i in ids if 0<=i<len(options)]

def one(gid,samples,student_model):
    game_seed=int(ref.SPEC["seed_base"])+gid*ref.SEED_STRIDE
    seat,orders=ref.stage_slots(game_seed)
    deck=ref.SLOT_VARIANTS["one_key_34"]
    ref.sim.reset_caches();ref.sim.root.install("one_key_34")
    ref.sim.m.set_trial_seed(game_seed)
    state,history=ref.choose_keep(deck,seat,orders)
    assert history and history[-1]["kept"]
    stage_info=history[-1]
    stage=stage_info["stage"]
    kn=stage_info["keep_n"]
    seven=tuple(stage_info["seven"])
    rest=tuple(deck[x] for x in orders[stage][7:])
    assert len(rest)==92 and collections.Counter(seven)+collections.Counter(rest)==collections.Counter(ref.VARIANTS["one_key_34"])
    assert tuple(state.hand)==tuple(stage_info["hand"])
    if kn==7:
        return {"game_id":gid,"status":"no_bottom_at_keep7",
                "kept_stage":stage,"keep_n":kn,"seat":seat}
    originals=finalists(seven,kn,rest)
    t_idx=selected_index(originals,stage_info["hand"],stage_info["bottom"])
    s_idx=student_index(student_model,seven,kn,rest,seat,stage,originals)
    # Check exact v5 reference without disclosing hidden top cards to evaluator.
    verify_order_invariance(gid,seat,stage,kn,seven,rest,
        stage_info["hand"],stage_info["bottom"],float(stage_info["raw"]))
    candidates=choose_option_ids(originals,t_idx,s_idx)
    names=tuple(sorted(rest))
    result={i:collections.Counter() for i in candidates}
    for j in range(samples):
        # Identical unseen 92-name permutation and identical stable dice seed
        # for every candidate in one group, separate from the deterministic
        # original v5 teacher candidate-specific future sampler.
        unknown=list(names)
        random.Random(seed("heldout_lib",gid,stage,j)).shuffle(unknown)
        trial=seed("heldout_dice",gid,stage,j)
        for i in candidates:
            c=originals[i]
            hand=tuple(c["hand"]);bottom=tuple(c["bottom"])
            ref.sim.reset_caches();ref.sim.root.install("one_key_34")
            ref.sim.m.set_trial_seed(trial)
            turn=int(ref.d._win_turn_from_unknown_order(
                hand,tuple(unknown)+bottom,seat,beam=160,max_turn=3) or 0)
            assert turn in (0,1,2,3)
            result[i][turn]+=1
    rows=[]
    for i in candidates:
        z=result[i]
        rows.append({
          "candidate_index":i,
          "structural_rank":originals[i]["struct_rank"],
          "bottom":originals[i]["bottom"],
          "hand":originals[i]["hand"],
          "is_v5_choice":i==t_idx,
          "is_frozen_v14_choice":i==s_idx,
          "is_structural_first":i==0,
          "heldout_by_T1":z[1]/samples,
          "heldout_by_T2":(z[1]+z[2])/samples,
          "heldout_by_T3":(z[1]+z[2]+z[3])/samples,
          "heldout_blended_utility":(z[1]+z[2]+0.5*z[3])/samples,
        })
    return {
       "game_id":gid,"status":"audited",
       "seat":seat,"kept_stage":stage,"keep_n":kn,
       "visible_seven":seven,
       "candidate_count":len(originals),
       "v5_candidate_index":t_idx,
       "v14_candidate_index":s_idx,
       "selected_v5_outside_structural_top3":t_idx>2,
       "v5_changes_bottom_vs_v14":t_idx!=s_idx,
       "actual_unknown_order_permutation_invariance_verified":True,
       "sampled_independent_futures_per_candidate":samples,
       "independent_same_future_for_all_candidates":True,
       "candidate_results":rows,
       "no_actual_topdeck_as_decision_feature":True,
       "teacher_model_used_original_seeded_futures_not_heldout":True,
    }

def main(start,games,samples,out):
    if not 99000<=start or games!=4 or start+games>99064 or samples!=16:
        raise ValueError("v28 frozen: 99k IDs 4-game shards, 16 heldout futures")
    a=teacher.audit();assert a["status"]=="PASS"
    model=json.loads(STUDENT_PATH.read_text())
    assert model["deployed_policy_approved"] is False
    count=collections.Counter();rows=[]
    for gid in range(start,start+games):
        record=one(gid,samples,model)
        rows.append(record);count[record["status"]]+=1
        print("V28_BOTTOM_REAL_AUDIT_GAME",gid,record["status"],
              record.get("keep_n"),record.get("v5_candidate_index"),
              dict(count),flush=True)
    meta={
      "schema":"dack_v28_v5_bottom_order_independence_and_unseen_value",
      "status":"PASS","game_ids":[start,start+games-1],
      "n_games":games,
      "n_independent_heldout_futures_per_candidate":samples,
      "v5_rule_version":teacher.VERSION,
      "v14_model_sha256":hashlib.sha256(STUDENT_PATH.read_bytes()).hexdigest(),
      "strict_beam160_outcome":True,
      "teacher_actual_hidden_order_invariance":True,
      "teacher_and_labels_disjoint_rollout_seeds":True,
      "99k_audit_only_must_not_fit_policy":True,
      "no_teacher_candidate_or_outcome_features_in_student_choice":True,
      "rows":rows,
    }
    dest=Path(out);dest.parent.mkdir(exist_ok=True,parents=True)
    with gzip.open(dest,"wt") as f:json.dump(meta,f,sort_keys=True)
    print("DACK_V28_HIDDEN_DECK_ORDER_AUDIT_PASS",dict(count),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--games",type=int,default=4)
    p.add_argument("--samples",type=int,default=16)
    p.add_argument("--out",required=True)
    x=p.parse_args()
    main(x.start,x.games,x.samples,x.out)
