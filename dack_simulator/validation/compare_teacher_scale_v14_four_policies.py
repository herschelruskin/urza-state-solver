"""New 66k physical-game paired v5 vs frozen v13, v14-128, v14-144.

All policies share same shuffled 99 physical slots by game ID and real
beam-160 gameplay. Each runs in a fresh Python process to prevent patches
and global cache leakage. Do not treat N16 as noninferiority.
"""
from __future__ import annotations
import argparse,gzip,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CHILD=(
    "import json,sys,time\n"
    "gid=int(sys.argv[1]);policy=sys.argv[2]\n"
    "if policy=='v5':\n"
    " import dack_paired_counterfactual_v5_stable_chance_20261031 as p\n"
    " p.audit();runner=p.reference\n"
    "else:\n"
    " import dack_paired_counterfactual_v13_teacher_distill_20261031 as p\n"
    " model={'v13_16':'models/dack_teacher_distill_v13_EXPERIMENTAL.json',"
    "'v14_128':'models/v14_curve/v14_teacher_groups_128.json',"
    "'v14_144':'models/v14_curve/v14_teacher_groups_144.json'}[policy]\n"
    " p.audit(model);runner=p.ref\n"
    " assert p.MODEL['deployed_policy_approved'] is False\n"
    "start=time.perf_counter();r=runner.game('one_key_34',gid)\n"
    "print('PHYSICAL_GAME',json.dumps({'turn':r['win_turn'],"
    "'keep_n':r['keep_n'],'seat':r['seat'],"
    "'history':r['history'],"
    "'seconds':round(time.perf_counter()-start,4)}),flush=True)\n"
)
POLICIES=('v5','v13_16','v14_128','v14_144')

def run_game(gid,policy):
    r=subprocess.run([sys.executable,'-c',CHILD,str(gid),policy],
                     cwd=ROOT,text=True,capture_output=True,timeout=1500)
    if r.returncode:
        print('TEACHER_SCALE_CHILD_FAILURE',gid,policy,r.stderr[-1800:],r.stdout[-1800:],flush=True)
        raise RuntimeError('policy test failed')
    answers=[s[len('PHYSICAL_GAME '):] for s in r.stdout.splitlines() if s.startswith('PHYSICAL_GAME ')]
    if len(answers)!=1:raise AssertionError('missing exact game label')
    return json.loads(answers[0])

def main(start,games,out):
    if games<1 or start<66000 or start+games>67000:
        raise ValueError('fresh 66k outer game seed band required')
    records=[]
    for gid in range(start,start+games):
        rec={'game_id':gid}
        for policy in POLICIES:rec[policy]=run_game(gid,policy)
        assert len({rec[p]['seat'] for p in POLICIES})==1
        records.append(rec)
        print('TEACHER_V14_QUAD_PAIRED_GAME',gid,
              {p:(rec[p]['turn'],rec[p]['keep_n'],rec[p]['seconds']) for p in POLICIES},
              flush=True)
    def metrics(policy):
        x=[r[policy] for r in records]
        return {'n':len(x),'T1':sum(v['turn']==1 for v in x),
                'T2':sum(v['turn'] in (1,2) for v in x),
                'T3':sum(v['turn'] in (1,2,3) for v in x),
                'mean_keep':sum(v['keep_n'] for v in x)/len(x),
                'seconds':round(sum(v['seconds'] for v in x),4)}
    results={p:metrics(p) for p in POLICIES}
    report={'schema':'dack_v14_teacher_learning_curve_four_policy_paired',
            'status':'PASS','game_ids':[start,start+games-1],
            'simulator_gameplay_beam':160,'same_physical_stage_seeds':True,
            'training_and_validation_ids_are_separate':True,
            'students_approved_for_production':False,'metrics':results,
            'rows':records,
            'warning':'Bounded goldfish deployment and small N; not multiplayer win rate or policy noninferiority.'}
    dest=Path(out);dest.parent.mkdir(exist_ok=True,parents=True)
    with gzip.open(dest,'wt') as fp:json.dump(report,fp)
    print('TEACHER_V14_QUAD_PAIRED_PASS',json.dumps({
        k:v for k,v in report.items() if k!='rows'},sort_keys=True),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--start',type=int,default=66000)
    p.add_argument('--games',type=int,default=2)
    p.add_argument('--out',default='shards/v14_four_policy_66000.json.gz')
    a=p.parse_args()
    main(a.start,a.games,a.out)
