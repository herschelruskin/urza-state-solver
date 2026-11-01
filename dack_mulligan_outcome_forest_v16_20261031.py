"""Pure-Python four-class conditional outcome forest, v16 research only.

Model label 0 = not deploy by turn 3, 1 = T1, 2 = T2, 3 = T3.
Probability is conditional on a particular London-kept hand and the
physical unseen-card MULTISET, *not* the unconditional deck win rate.
"""
from __future__ import annotations
import hashlib,json,math
import dack_mulligan_teacher_features_v13_20261031 as f

SCHEMA='dack_v16_teacher_kept_conditional_outcome_forest'

def predict(model,visible_features):
    if model.get('schema')!=SCHEMA or model.get('feature_hash')!=f.feature_hash():
        raise ValueError('incompatible outcome model')
    if model.get('classes')!=[0,1,2,3]:
        raise ValueError('missing four outcome classes')
    if len(visible_features)!=len(f.FEATURES):
        raise ValueError('feature count mismatch')
    scores=[0.,0.,0.,0.]
    for t in model['trees']:
        i=0;depth=0
        while t['left'][i]>=0:
            j=int(t['feature'][i])
            i=t['left'][i] if visible_features[j]<=t['threshold'][i] else t['right'][i]
            depth+=1
            if depth>30:raise ValueError('invalid decision tree')
        p=t['probabilities'][i]
        for k in range(4):scores[k]+=p[k]
    n=len(model['trees'])
    if n<1:raise ValueError('empty forest')
    p=[max(0.,s/n) for s in scores]
    total=sum(p)
    if total<=0:raise ValueError('invalid probabilities')
    p=[x/total for x in p]
    assert len(p)==4 and abs(sum(p)-1.)<1e-8
    return p

def deployment_summary(probabilities):
    p=probabilities
    return {'P_T1':p[1],'P_by_T2':p[1]+p[2],
            'P_by_T3':1.-p[0],
            'utility_T2_plus_half_T3':p[1]+p[2]+.5*p[3]}

def selftest():
    zeros=[[0.25]*4]
    dummy={'schema':SCHEMA,'feature_hash':f.feature_hash(),
           'classes':[0,1,2,3],
           'trees':[{'left':[-1],'right':[-1],'feature':[-2],
                     'threshold':[-2.],'probabilities':zeros}]}
    p=predict(dummy,[0.]*len(f.FEATURES))
    assert p==[.25]*4
    assert deployment_summary(p)['P_by_T2']==.5
    return {'status':'PASS','features':len(f.FEATURES),
            'no_future_order_inputs':True,'no_runtime_sklearn':True}

if __name__=='__main__':
    print(json.dumps(selftest(),indent=2))
