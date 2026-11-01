"""v16 fixed nonlinear outcome model vs constant conditional-rate baseline.

Train on 144 independent natural v5-policy-kept seven-card hands, four
independent beam-160 futures each. Evaluate on 40 disjoint v5-kept hands
with four independent futures each. Repeat futures from one game are
clustered, never treated as independent opening hands in uncertainty.

This is NOT unbiased policy performance across physical games. It only
estimates deployment probabilities conditional on the original v5 keeping.
No teacher choice labels or realized future order enter predictors.
"""
from __future__ import annotations
import argparse,gzip,json,hashlib,math,random,sys
from pathlib import Path
from collections import Counter,defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import dack_mulligan_teacher_features_v13_20261031 as features
import dack_mulligan_outcome_forest_v16_20261031 as runtime
from dack_simulator.validation.collect_teacher_london_v13 import finalists

def read(paths,split):
    rows=[];groups=set()
    for p in paths:
        with gzip.open(p,'rt') as f:
            meta=json.loads(next(f))
            assert meta['schema']==runtime.SCHEMA.replace(
                'dack_v16_teacher_kept_conditional_outcome_forest',
                'dack_v14_exact_teacher_kept_real_future_labels_v1')
            assert meta['split']==split
            assert meta['selection_protocol']=='exact_v5_real_policy_kept'
            recs=[json.loads(x) for x in f]
        if len(recs)!=4 or [x['future_index'] for x in recs]!=[0,1,2,3]:
            raise ValueError('expected exactly four independent futures')
        gid=recs[0]['game_id'];groups.add(gid)
        for rec in recs:
            assert rec['group_id']==recs[0]['group_id']
            assert sum(rec['unknown_counts'].values())==92
            if rec['label_turn'] not in (0,1,2,3):raise ValueError('bad class')
            rows.append(rec)
    if not rows:raise ValueError('no outcomes')
    return rows,groups

def featurize(rows):
    cache={};xs=[];ys=[];groups=[]
    for r in rows:
        gid=r['group_id']
        if gid not in cache:
            seven=tuple(r['seven']);kn=int(r['keep_n'])
            unknown=r['unknown_counts']
            rest=tuple(card for card,n in sorted(unknown.items()) for _ in range(n))
            candidates=finalists(seven,kn,rest)
            match=[(i,c) for i,c in enumerate(candidates) if
                   Counter(c['hand'])==Counter(r['hand']) and
                   tuple(c['bottom'])==tuple(r['bottom'])]
            if not match:raise AssertionError(('reference choice absent',gid))
            i,c=match[0]
            cache[gid]=features.extract(seven,r['hand'],r['bottom'],unknown,
                r['seat'],kn,r['stage'],c['struct_rank'],i)
        xs.append(cache[gid]);ys.append(int(r['label_turn']));groups.append(gid)
    return xs,ys,groups

def export(model):
    trees=[]
    for est in model.estimators_:
        t=est.tree_
        x=t.value[:,0,:]
        tprob=(x/x.sum(axis=1,keepdims=True)).tolist()
        trees.append({'left':t.children_left.tolist(),
                      'right':t.children_right.tolist(),
                      'feature':t.feature.tolist(),
                      'threshold':t.threshold.tolist(),
                      'probabilities':tprob})
    return trees

def evaluate(preds,labels):
    n=len(labels)
    prior_metrics={
        'multiclass_brier':sum(sum((p[k]-(int(y==k)))**2 for k in range(4))
                                for p,y in zip(preds,labels))/n,
        'multiclass_logloss':-sum(math.log(max(1e-9,p[y]))
                                   for p,y in zip(preds,labels))/n,
    }
    for name,key,t in [('T1',[1],lambda y:y==1),
                       ('T2_cumulative',[1,2],lambda y:y in (1,2)),
                       ('T3_cumulative',[1,2,3],lambda y:y in (1,2,3))]:
        prior_metrics[name]={
            'predicted':sum(sum(p[k] for k in key) for p in preds)/n,
            'observed':sum(t(y) for y in labels)/n
        }
    return prior_metrics

def train(trainfiles,valfiles,modelout,reportout):
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    tr,tgroups=read(trainfiles,'train')
    va,vgroups=read(valfiles,'validation')
    assert len(tgroups)==144 and len(vgroups)==40 and not (tgroups&vgroups)
    assert len(tr)==576 and len(va)==160
    X,y,ids=featurize(tr)
    V,w,vids=featurize(va)
    assert set(y)==set(w)=={0,1,2,3}
    forest=RandomForestClassifier(
        n_estimators=96,max_depth=6,min_samples_leaf=8,
        max_features=.5,random_state=20261031,n_jobs=2)
    forest.fit(np.asarray(X),np.asarray(y))
    model={
        'schema':runtime.SCHEMA,
        'feature_hash':features.feature_hash(),
        'source_policy':'dack_stable_dice_strict_bounded_witness_v5',
        'classes':[0,1,2,3],'trees':export(forest),
        'training_unique_game_groups':len(tgroups),
        'calibration_unique_game_groups':len(vgroups),
        'training_rollouts':len(tr),'validation_rollouts':len(va),
        'trained_only_on_v5_policy_kept_hands':True,
        'not_an_unconditional_deck_win_probability':True,
        'validation_not_used_for_training_or_hyperparameter_search':True,
        'actual_gameplay_beam':160,
        'deployed_policy_approved':False,
        'diagnostic_only':True,
        'no_future_draw_order_in_features':True,
    }
    for i in range(min(10,len(V))):
        a=runtime.predict(model,V[i])
        b=forest.predict_proba(np.asarray([V[i]]))[0].tolist()
        if any(abs(q-z)>1e-9 for q,z in zip(a,b)):
            raise AssertionError('pure Python model export prediction differs from sklearn')
    pforest=[runtime.predict(model,x) for x in V]
    prior=[y.count(k)/len(y) for k in range(4)]
    pbaseline=[prior]*len(w)
    full=evaluate(pforest,w);base=evaluate(pbaseline,w)
    group_rows=defaultdict(list)
    for i,g in enumerate(vids):group_rows[g].append(i)
    gids=sorted(group_rows)
    rng=random.Random(161616)
    samples=[]
    for i in range(300):
        indices=[j for g in [gids[rng.randrange(len(gids))] for _ in gids]
                 for j in group_rows[g]]
        full_brier=evaluate([pforest[j] for j in indices],[w[j] for j in indices])['multiclass_brier']
        base_brier=evaluate([pbaseline[j] for j in indices],[w[j] for j in indices])['multiclass_brier']
        samples.append(full_brier-base_brier)
    samples.sort()
    report={
        'schema':'dack_v16_conditional_four_class_outcome_diagnostic',
        'status':'PASS','distinct_train_hands':len(tgroups),
        'distinct_validation_hands':len(vgroups),
        'outcome_labels_train':len(tr),'outcome_labels_validation':len(va),
        'training_class_counts':{str(k):y.count(k) for k in range(4)},
        'validation_class_counts':{str(k):w.count(k) for k in range(4)},
        'validation_results':{'trained_nonlinear_forest':full,'constant_class_rate_baseline':base},
        'Brier_forest_minus_constant':full['multiclass_brier']-base['multiclass_brier'],
        'group_bootstrap_95ci_Brier_difference':[samples[int(len(samples)*.025)],
            samples[int(len(samples)*.975)]],
        'model_approved':False,
        'warning':'Only 40 held-separate validation hands; this is conditional on v5 keeps, not full-game policy win rate and not safe to deploy on other-selected hands.'
    }
    a=Path(modelout);a.parent.mkdir(parents=True,exist_ok=True)
    a.write_text(json.dumps(model,sort_keys=True,separators=(',',':'))+'\n')
    b=Path(reportout);b.parent.mkdir(parents=True,exist_ok=True)
    b.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print('V16_V5_SELECTED_CONDITIONAL_OUTCOME_MODEL_PASS',json.dumps(report),flush=True)

if __name__=='__main__':
    import glob
    p=argparse.ArgumentParser()
    p.add_argument('--root',default='datasets/true_v5_kept_futures_v14')
    p.add_argument('--model',default='models/dack_v16_conditional_outcomes_EXPERIMENTAL.json')
    p.add_argument('--report',default='benchmark_results/v16_true_outcome_forest_diagnostic.json')
    a=p.parse_args()
    paths=list(Path(a.root).glob('outcome_*.jsonl.gz'))
    trainfiles=[str(p) for p in paths if 60000<=int(p.stem.split('.')[0].split('_')[-1])<60144]
    valfiles=[str(p) for p in paths if 61000<=int(p.stem.split('.')[0].split('_')[-1])<61040]
    train(sorted(trainfiles),sorted(valfiles),a.model,a.report)
