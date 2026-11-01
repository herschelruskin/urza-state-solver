"""Actual conditional T1/T2/T3 futures for exact teacher-kept London hands.

Distinct from teacher imitation labels. These are real 160-beam goldfish
deployment outcomes on fresh, independent 92-card hidden-library orders,
given a hand selected by the frozen v5 London reference. The hidden sampled
order is never exposed to the probability learner.

The independent unit is the physical game group, not one of its futures.
Do not report labels conditioned on v5 keeps as overall natural game win rate.
"""
from __future__ import annotations
import argparse,gzip,json,random,hashlib,sys,time
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import dack_paired_counterfactual_v5_stable_chance_20261031 as teacher

ref=teacher.reference
d=ref.d
SCHEMA="dack_v14_exact_teacher_kept_real_future_labels_v1"

def seeded(*args):
    b=json.dumps([SCHEMA,*args],sort_keys=True,separators=(',',':'))
    return int.from_bytes(hashlib.sha256(b.encode()).digest()[:8],'big')

def label(path,out,draws=4):
    if draws<1:raise ValueError('invalid independent draw count')
    with gzip.open(path,'rt') as f:
        header=json.loads(next(f));stages=[json.loads(line) for line in f]
    assert header['teacher']=='dack_stable_dice_strict_bounded_witness_v5'
    assert len(stages)>0
    assert stages[-1]['teacher_keep']
    assert sum(bool(x['teacher_keep']) for x in stages)==1
    choice=stages[-1]
    gid=int(choice['game_id']);variant=header['variant']
    assert variant in ref.VARIANTS
    hand=tuple(choice['teacher_selected_hand'])
    bottom=tuple(choice['teacher_selected_bottom'])
    unknown=choice['unknown_counts']
    assert len(hand)+len(bottom)==7
    assert sum(unknown.values())==92
    assert Counter(hand)+Counter(bottom)+Counter(unknown)==Counter(ref.VARIANTS[variant])
    assert header['source_manifest_sha256']==ref.source_sha(ref.MANIFEST_PATH)
    teacher.audit()
    rows=[];counts=Counter();t0=time.monotonic()
    for j in range(draws):
        lib=list(c for card,n in sorted(unknown.items()) for c in [card]*n)
        random.Random(seeded(gid,variant,j,'physical_unknown')).shuffle(lib)
        ref.sim.reset_caches()
        ref.sim.root.install(variant)
        ref.sim.m.set_trial_seed(seeded(gid,variant,j,'stable_dice'))
        outcome=int(d._win_turn_from_unknown_order(
            hand,tuple(lib)+bottom,choice['seat'],beam=160,max_turn=3) or 0)
        assert outcome in (0,1,2,3)
        counts[outcome]+=1
        rows.append({
            'type':'label','schema':SCHEMA,
            'game_id':gid,'group_id':f'{variant}:{gid}',
            'variant':variant,'seat':choice['seat'],
            'keep_n':choice['keep_n'],'stage':choice['stage'],
            'hand':list(hand),'bottom':list(bottom),
            'seven':choice['seven'],'unknown_counts':unknown,
            'future_index':j,'label_turn':outcome,
            'selection_protocol':'exact_v5_real_policy_kept',
        })
    meta={'type':'metadata','schema':SCHEMA,
          'source_teacher':'dack_stable_dice_strict_bounded_witness_v5',
          'group_id':f'{variant}:{gid}',
          'game_id':gid,'draws':draws,'split':header['split'],
          'source_physical_sha256':header['source_manifest_sha256'],
          'selection_protocol':'exact_v5_real_policy_kept',
          'actual_gameplay_beam':160,
          'physical_future_independently_shuffled':True,
          'model_input_never_contains_future_order':True,
          'not_population_unconditional_deck_win_probability':True}
    dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(dest,'wt') as f:
        f.write(json.dumps(meta,separators=(',',':'))+'\n')
        for row in rows:f.write(json.dumps(row,separators=(',',':'))+'\n')
    print('V14_TEACHER_KEPT_REAL_FUTURES_PASS',json.dumps({
       'gid':gid,'n_futures':draws,
       'outcomes':{str(i):counts[i] for i in range(4)},
       'seconds':round(time.monotonic()-t0,3)
    }),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--teacher-stage-file',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--draws',type=int,default=4)
    a=p.parse_args()
    label(a.teacher_stage_file,a.out,a.draws)
