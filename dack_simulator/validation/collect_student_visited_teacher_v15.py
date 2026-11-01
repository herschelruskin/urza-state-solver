"""v15 DAgger pilot: query v5 teacher at *student-visited* London states.

This addresses covariate shift: a student that mulligans differently from v5
visits sevens/depths underrepresented in teacher-visited-only training.
No normal gameplay uses teacher; this is expensive OFFLINE label collection.
Frozen v13 source student (.5 cutoff), not the tuned v13b.
"""
from __future__ import annotations
import argparse,gzip,json,hashlib,sys,time
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import dack_paired_counterfactual_v5_stable_chance_20261031 as teacher
import dack_mulligan_teacher_features_v13_20261031 as f
from dack_simulator.validation.collect_teacher_london_v13 import finalists

ref=teacher.reference
d=ref.d
PROTOCOL="dack_v15_student_v13_visited_v5_teacher_labels"
MODEL="models/dack_teacher_distill_v13_EXPERIMENTAL.json"

def sample_game(gid,variant,model):
    seed=int(ref.SPEC['seed_base'])+gid*ref.SEED_STRIDE
    seat,stages=ref.stage_slots(seed)
    slotmap=ref.SLOT_VARIANTS[variant]
    ref.sim.reset_caches()
    ref.sim.root.install(variant)
    ref.sim.m.set_trial_seed(seed)
    records=[]
    for stage,(keep_n,order) in enumerate(zip(ref.sim.STAGES,stages)):
        seven=tuple(slotmap[s] for s in order[:7])
        rest=tuple(slotmap[s] for s in order[7:])
        if len(rest)!=92:raise AssertionError('physical 99 violated')
        choices=finalists(seven,keep_n,rest)
        counts=Counter(rest)
        feats=[f.extract(seven,q['hand'],q['bottom'],counts,seat,keep_n,
                         stage,q['struct_rank'],i) for i,q in enumerate(choices)]
        scores=[f.score_head(model,'choice_trees',x) for x in feats]
        sidx=max(range(len(scores)),key=lambda i:scores[i])
        skvote=f.score_head(model,'keep_trees',feats[sidx])
        skeep=keep_n==1 or skvote>=model['keep_cutoff']
        # EXACT original teacher stage evaluator, no speculative student outcomes
        # and NO hand-future draw order passed to student.
        raw,ev,struct,hand,bottom,actual_rest,ignored,refined=(
            ref.batch.evaluate_keep(seven,keep_n,rest,seat))
        assert tuple(actual_rest)==rest
        native_cutoff=0. if keep_n==1 else ref.batch.FROZEN_CONTINUATION[keep_n-1]
        native=keep_n==1 or float(raw)>=native_cutoff
        threshold=native_cutoff + (
            0. if native and float(ev['t1'])>0 else
            ref.sim.ASSERTIVE_BUMPS.get(keep_n,0.)
        )
        tkeep=keep_n==1 or float(raw)>=threshold
        selected=(tuple(hand),tuple(bottom))
        matching=[i for i,q in enumerate(choices) if
                  (tuple(q['hand']),tuple(q['bottom']))==selected]
        assert matching,('teacher bottom not shortlisted',gid,stage)
        row={
            'type':'stage','game_id':gid,'group_id':f'{variant}:{gid}',
            'variant':variant,'stage':stage,'seat':seat,'keep_n':keep_n,
            'seven':list(seven),'unknown_counts':dict(sorted(counts.items())),
            'candidate_rows':choices,
            'teacher_chosen_candidate':matching[0],
            'teacher_keep':bool(tkeep),'teacher_raw':float(raw),
            'teacher_sampled_t1':float(ev['t1']),
            'teacher_threshold':float(threshold),'teacher_refined':bool(refined),
            'teacher_selected_hand':list(hand),'teacher_selected_bottom':list(bottom),
            'source_student_chosen_candidate':sidx,
            'source_student_keep':bool(skeep),
            'source_student_keep_vote':skvote,
            'source_student_choice_score':scores[sidx],
        }
        assert Counter(seven)+counts==Counter(ref.VARIANTS[variant])
        records.append(row)
        print('V15_STUDENT_STATE_TEACHER',gid,stage,
              {'student_keep':skeep,'teacher_keep':tkeep,
               'student_bottom':sidx,'teacher_bottom':matching[0]},flush=True)
        if skeep:break
    assert records[-1]['source_student_keep']
    return records

def generate(start,games,out,split='train',variant='one_key_34'):
    limit={'train':(67000,67999),'validation':(68000,68999)}
    if split not in limit:raise ValueError('invalid DAgger split')
    lo,hi=limit[split]
    if games<1 or not lo<=start<=start+games-1<=hi:
        raise ValueError('out-of-band DAgger game IDs')
    teacher.audit()
    modelpath=Path(MODEL)
    model=json.loads(modelpath.read_text())
    if model['deployed_policy_approved'] is not False:
        raise ValueError('frozen student unexpectedly approved')
    if model['source_manifest_sha256']!=ref.source_sha(ref.MANIFEST_PATH):
        raise ValueError('physical manifest mismatch')
    path=Path(out);path.parent.mkdir(exist_ok=True,parents=True)
    counters=Counter();before=time.monotonic()
    meta={'type':'metadata','schema':'dack_v13_v5_london_teacher_stages_v1',
          'split':split,'start':start,'games':games,'variant':variant,
          'teacher':'dack_stable_dice_strict_bounded_witness_v5',
          'sampling_protocol':PROTOCOL,'student_visited_stage_sampling':True,
          'student_policy_sha256':hashlib.sha256(modelpath.read_bytes()).hexdigest(),
          'source_manifest_sha256':ref.source_sha(ref.MANIFEST_PATH),
          'source_spec_sha256':ref.source_sha(ref.SPEC_PATH),
          'no_future_order_in_features':True,
          'not_representative_of_v5_visited_states':True,
          'no_actual_gameplay_outcome_labels':True}
    with gzip.open(path,'wt',encoding='utf8') as fp:
        fp.write(json.dumps(meta,separators=(',',':'))+'\n')
        for gid in range(start,start+games):
            records=sample_game(gid,variant,model)
            for row in records:
                fp.write(json.dumps(row,separators=(',',':'))+'\n')
                counters['stages']+=1;counters['candidates']+=len(row['candidate_rows'])
                counters['teacher_keep']+=int(row['teacher_keep'])
                counters['student_keep']+=int(row['source_student_keep'])
                counters['keep_mismatch']+=int(row['teacher_keep']!=row['source_student_keep'])
                counters['bottom_mismatch']+=int(
                    row['teacher_chosen_candidate']!=row['source_student_chosen_candidate'])
            counters['games']+=1
    print('V15_DAGGER_TEACHER_REAL_PASS',json.dumps({
        'split':split,'start':start,'games':games,
        'counts':dict(counters),'seconds':round(time.monotonic()-before,3)
    },sort_keys=True),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--split',choices=('train','validation'),default='train')
    p.add_argument('--start',type=int,default=67000)
    p.add_argument('--games',type=int,default=2)
    p.add_argument('--variant',default='one_key_34',choices=list(ref.VARIANTS))
    p.add_argument('--out',default='datasets/v15_student_teacher_67000.jsonl.gz')
    a=p.parse_args()
    generate(a.start,a.games,a.out,a.split,a.variant)
