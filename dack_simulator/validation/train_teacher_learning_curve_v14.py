"""Evaluate teacher imitation learning curves on distinct natural physical-game groups.

Fixed disjoint validation data for every training size. Never train on
imitation_test or full-game policy evaluation groups. Outcome probabilities
are NOT estimated here: metrics are teacher decision agreement only.
"""
from __future__ import annotations
import argparse,gzip,json,hashlib,random,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from dack_simulator.validation import train_teacher_distillation_v13 as tr

def main(trainfiles,valfiles,outdir):
    from sklearn.ensemble import RandomForestClassifier
    import numpy as np
    train,train_ids,sha=tr.read(trainfiles,'train')
    val,val_ids,vsha=tr.read(valfiles,'validation')
    assert sha==vsha and train_ids.isdisjoint(val_ids)
    assert len(train_ids)>=128 and len(val_ids)>=32
    # Make all training subsets nested, independently of file enumeration.
    old=sorted(i for i in train_ids if i<60016)
    fresh=sorted(i for i in train_ids if i>=60016)
    assert len(old)>=16
    chosen_order=old+fresh
    targets=[16,32,64,96,128,len(chosen_order)]
    report={'schema':'dack_v14_teacher_learning_curve',
            'status':'PASS','training_group_ids':[min(train_ids),max(train_ids)],
            'validation_group_ids':[min(val_ids),max(val_ids)],
            'no_overlap':True,'n_validation_groups':len(val_ids),
            'full_gameplay_outcomes_not_used':True,
            'models':[]}
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    for target in targets:
        subset=[r for r in train if r['game_id'] in set(chosen_order[:target])]
        group_count=len({r['game_id'] for r in subset})
        assert group_count==target,(group_count,target)
        cx,cy,cw,kx,ky,_=tr.transform(subset)
        assert set(cy)=={0,1} and set(ky)=={0,1}
        choice=RandomForestClassifier(
            n_estimators=64,max_depth=7,min_samples_leaf=2,
            max_features=.75,class_weight='balanced_subsample',
            random_state=1337,n_jobs=2)
        choice.fit(cx,cy,sample_weight=cw)
        keep=RandomForestClassifier(
            n_estimators=64,max_depth=7,min_samples_leaf=2,
            max_features=.75,class_weight='balanced_subsample',
            random_state=31337,n_jobs=2)
        keep.fit(kx,ky)
        import dack_mulligan_teacher_features_v13_20261031 as f
        model={
            'schema':f.EXPORT_SCHEMA,
            'model_purpose':'behavior_cloning_OF_original_v5_london_teacher_decisions',
            'feature_hash':f.feature_hash(),'feature_count':len(f.FEATURES),
            'source_manifest_sha256':sha,
            'source_teacher_version':'dack_stable_dice_strict_bounded_witness_v5',
            'choice_trees':tr.to_json_forest(choice),'keep_trees':tr.to_json_forest(keep),
            'keep_cutoff':.5,
            'training_groups':target,'validation_groups':len(val_ids),
            'training_stage_rows':len(subset),
            'validation_stage_rows':len(val),
            'teacher_outcomes_not_used_as_predictor_inputs':True,
            'teacher_probabilities_NOT_deployment_probabilities':True,
            'deployed_policy_approved':False,'diagnostic_only':True,
            'n_trees_per_head':64,'max_depth':7,
            'student_family':'same_frozen_v13_two_head_random_forest_no_hyperparameter_search',
            'training_game_ids':chosen_order[:target],
            'training_groups_have_natural_physical_seven_card_seats':True
        }
        label='v14_teacher_groups_'+str(target)
        path=outdir/(label+'.json')
        path.write_text(json.dumps(model,sort_keys=True,separators=(',',':'))+'\n')
        score=tr.evaluate(val,model)
        counts={k:v for k,v in score.items() if k!='per_stage_results'}
        record={'train_groups':target,'train_stage_rows':len(subset),
                'train_candidate_rows':len(cx),
                'validation':counts,
                'model_path':str(path),
                'model_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        report['models'].append(record)
        print('V14_TEACHER_LEARNING_CURVE_POINT',json.dumps(record),flush=True)
    scores=report['models']
    first=scores[0]['validation'];last=scores[-1]['validation']
    report['baseline_first_vs_final']={
        'first_choice_accuracy':first['candidate_top1_accuracy'],
        'last_choice_accuracy':last['candidate_top1_accuracy'],
        'first_keep_accuracy':first['keep_decision_accuracy_under_student_selected_bottom'],
        'last_keep_accuracy':last['keep_decision_accuracy_under_student_selected_bottom'],
        'first_joint_accuracy':first['joint_stage_accuracy'],
        'last_joint_accuracy':last['joint_stage_accuracy'],
        'first_teacher_keep_rate':first['teacher_keep_rate'],
        'last_student_keep_rate':last['student_keep_rate'],
        'first_student_keep_rate':first['student_keep_rate']
    }
    report['all_students_unapproved']=True
    Path('benchmark_results').mkdir(exist_ok=True)
    Path('benchmark_results/v14_teacher_learning_curve.json').write_text(
        json.dumps(report,sort_keys=True,indent=2)+'\n')
    print('V14_TEACHER_LEARNING_CURVE_PASS',json.dumps(report['baseline_first_vs_final']),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--train',nargs='+',required=True)
    p.add_argument('--validation',nargs='+',required=True)
    p.add_argument('--outdir',default='models/v14_curve')
    a=p.parse_args()
    main(a.train,a.validation,a.outdir)
