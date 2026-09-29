#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,importlib.util,json,subprocess,sys,time
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
RUNNER=HERE/'dack_v072_sharded_mana_screen.py'
SOLVER=ROOT/'src'/'dack_t3_solver_v0_72_frontier_dominance.py'
ENGINE_CONFIG=ROOT/'config'/'v072_production_engine.json'


def sha256_file(p:Path):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()


def load_config():
    cfg=json.loads(ENGINE_CONFIG.read_text(encoding='utf-8'))
    if cfg.get('engine_version')!='v0.72' or cfg.get('engine_status')!='production_frozen':
        raise SystemExit('production engine config is not frozen v0.72')
    actual=sha256_file(SOLVER)
    if actual!=cfg.get('solver_sha256'):
        raise SystemExit(f'solver SHA mismatch: config={cfg.get("solver_sha256")} actual={actual}')
    return cfg

CFG=load_config()


def load_runner():
    spec=importlib.util.spec_from_file_location('dack_v072_runner_manifest',RUNNER)
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
    return mod
R=load_runner()


def deck_sha():
    return hashlib.sha256(('\n'.join(R.m.DECK)+'\n').encode()).hexdigest()


def row_count(p:Path):
    if not p.exists(): return 0
    try:
        with p.open(newline='',encoding='utf-8') as f:return sum(1 for _ in csv.DictReader(f))
    except Exception:return 0


def atomic_json(path:Path,obj):
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    tmp.replace(path)


def identity_view(d):
    keys=(
      'schema_version','experiment_id','task_id','experiment_type','comparison',
      'target_index','target_card','control_card','replicate','shard_id','beam','samples','seed_base',
      'engine_version','solver_file','solver_sha256','production_config_file','production_config_sha256',
      'deck_sha256','deck_size','runner_file','runner_sha256','microtask_runner_file','microtask_runner_sha256')
    return {k:d.get(k) for k in keys}


def verify_complete_outputs(old,tdir,cp,tp,rp):
    if row_count(cp)!=1 or row_count(tp)<1 or not rp.exists():return False,'missing/invalid completed output rows'
    outs=old.get('outputs') or {}
    for label,p in [('contexts',cp),('trials',tp),('runner_manifest',rp)]:
        rec=outs.get(label) or {}
        expected=rec.get('sha256')
        if expected and sha256_file(p)!=expected:return False,f'{label} SHA mismatch'
    return True,''


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--experiment-id',required=True)
    ap.add_argument('--target-index',type=int,required=True)
    ap.add_argument('--replicate',type=int,required=True)
    ap.add_argument('--out-dir',required=True)
    ap.add_argument('--beam',type=int,default=int(CFG['production_beam']))
    ap.add_argument('--samples',type=int,default=1)
    ap.add_argument('--seed-base',type=int,default=72024001)
    ap.add_argument('--timeout',type=float,default=45.0)
    ap.add_argument('--python',default=sys.executable)
    args=ap.parse_args()

    if args.beam!=int(CFG['production_beam']):
        raise SystemExit(f'production runner requires beam={CFG["production_beam"]}; got {args.beam}')
    if not 0 <= args.target_index < len(R.TARGETS):raise SystemExit('target index out of range')
    target=R.TARGETS[args.target_index]
    task_id=f'{args.experiment_id}__r{args.replicate:06d}__t{args.target_index:02d}'
    out=Path(args.out_dir);tasks=out/'tasks';tasks.mkdir(parents=True,exist_ok=True)
    tdir=tasks/task_id;tdir.mkdir(parents=True,exist_ok=True)
    shard_id=720000000 + args.replicate*100 + args.target_index
    cp=tdir/f'shard_{shard_id}_contexts.csv';tp=tdir/f'shard_{shard_id}_trials.csv';rp=tdir/f'shard_{shard_id}_manifest.json'
    mp=tdir/'task_manifest.json'

    base={
      'schema_version':'DACK-data-lake-v2','experiment_id':args.experiment_id,'task_id':task_id,
      'experiment_type':'conditional_forced_opening_slot','comparison':'target_vs_Plains',
      'target_index':args.target_index,'target_card':target,'control_card':'Plains','replicate':args.replicate,
      'shard_id':shard_id,'beam':args.beam,'samples':args.samples,'seed_base':args.seed_base,
      'engine_version':CFG['engine_version'],'solver_file':SOLVER.name,'solver_sha256':sha256_file(SOLVER),
      'production_config_file':ENGINE_CONFIG.name,'production_config_sha256':sha256_file(ENGINE_CONFIG),
      'deck_sha256':deck_sha(),'deck_size':len(R.m.DECK),
      'runner_file':RUNNER.name,'runner_sha256':sha256_file(RUNNER),
      'microtask_runner_file':Path(__file__).name,'microtask_runner_sha256':sha256_file(Path(__file__).resolve()),
      'status':'started','started_unix':time.time()
    }

    if mp.exists():
        try:old=json.loads(mp.read_text(encoding='utf-8'))
        except Exception as e:raise SystemExit(f'existing task manifest unreadable: {e}')
        if identity_view(old)!=identity_view(base):
            raise SystemExit('existing task identity/provenance conflicts with requested task; refusing overwrite')
        if old.get('status')=='complete':
            ok,msg=verify_complete_outputs(old,tdir,cp,tp,rp)
            if not ok:raise SystemExit(f'completed task integrity failure: {msg}')
            print(json.dumps({'status':'complete_existing','task_id':task_id,'target':target,
                              'context_rows':1,'trial_rows':row_count(tp),'task_manifest_sha256':sha256_file(mp)},sort_keys=True))
            return

    # Only incomplete same-identity tasks may be cleaned/restarted.
    for p in (cp,tp,rp):
        if p.exists():p.unlink()
    atomic_json(mp,base)
    cmd=[args.python,str(RUNNER),'--shard-id',str(shard_id),'--contexts-per-target','1','--samples',str(args.samples),
         '--beam',str(args.beam),'--seed-base',str(args.seed_base),'--out-dir',str(tdir),'--target',target,'--progress','1']
    t=time.time();err='';rc=None
    try:
        q=subprocess.run(cmd,text=True,capture_output=True,timeout=args.timeout)
        rc=q.returncode;err=(q.stderr or q.stdout)[-1200:]
        ok=(rc==0 and row_count(cp)==1 and row_count(tp)>=1 and rp.exists())
        status='complete' if ok else 'failed'
    except subprocess.TimeoutExpired:
        status='timeout';rc='timeout';err=f'timed out after {args.timeout}s'

    base.update({'status':status,'elapsed_seconds':round(time.time()-t,4),'returncode':rc,'message':err,
                 'context_rows':row_count(cp),'trial_rows':row_count(tp),'finished_unix':time.time()})
    if status=='complete':
        runner_manifest=json.loads(rp.read_text(encoding='utf-8'))
        if runner_manifest.get('solver_sha256')!=base['solver_sha256']:
            raise SystemExit('runner manifest solver SHA mismatch')
        if int(runner_manifest.get('beam',-1))!=args.beam or int(runner_manifest.get('seed_base',-1))!=args.seed_base:
            raise SystemExit('runner manifest beam/seed mismatch')
        base['outputs']={
          'contexts':{'file':cp.name,'sha256':sha256_file(cp),'rows':row_count(cp)},
          'trials':{'file':tp.name,'sha256':sha256_file(tp),'rows':row_count(tp)},
          'runner_manifest':{'file':rp.name,'sha256':sha256_file(rp)}
        }
    atomic_json(mp,base)
    print(json.dumps(base,sort_keys=True))
    if status!='complete':raise SystemExit(2)

if __name__=='__main__':main()
