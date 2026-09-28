#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,importlib.util,json,os,subprocess,sys,time
from pathlib import Path

HERE=Path(__file__).resolve().parent
RUNNER=HERE/'dack_v068_sharded_mana_screen.py'
SOLVER=HERE.parent/'src'/'dack_t3_solver_v0_68_color_canonicalization.py'


def load_runner():
    spec=importlib.util.spec_from_file_location('dack_v068_runner_manifest',RUNNER)
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
    return mod
R=load_runner()


def sha256_file(p:Path):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()


def deck_sha():
    return hashlib.sha256(('\n'.join(R.m.DECK)+'\n').encode()).hexdigest()


def row_count(p:Path):
    if not p.exists(): return 0
    try:
        with p.open(newline='',encoding='utf-8') as f:return sum(1 for _ in csv.DictReader(f))
    except Exception:return 0


def atomic_json(path:Path,obj):
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,indent=2,sort_keys=True),encoding='utf-8')
    tmp.replace(path)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--experiment-id',required=True)
    ap.add_argument('--target-index',type=int,required=True)
    ap.add_argument('--replicate',type=int,required=True)
    ap.add_argument('--out-dir',required=True)
    ap.add_argument('--beam',type=int,default=240)
    ap.add_argument('--samples',type=int,default=1)
    ap.add_argument('--seed-base',type=int,default=71024001)
    ap.add_argument('--timeout',type=float,default=45.0)
    ap.add_argument('--python',default=sys.executable)
    args=ap.parse_args()
    if not 0 <= args.target_index < len(R.TARGETS): raise SystemExit('target index out of range')
    target=R.TARGETS[args.target_index]
    task_id=f'{args.experiment_id}__r{args.replicate:06d}__t{args.target_index:02d}'
    out=Path(args.out_dir);tasks=out/'tasks';tasks.mkdir(parents=True,exist_ok=True)
    tdir=tasks/task_id;tdir.mkdir(parents=True,exist_ok=True)
    # Unique integer shard id; replicate and target index are collision-free while target count <100.
    shard_id=710000000 + args.replicate*100 + args.target_index
    cp=tdir/f'shard_{shard_id}_contexts.csv';tp=tdir/f'shard_{shard_id}_trials.csv';rp=tdir/f'shard_{shard_id}_manifest.json'
    mp=tdir/'task_manifest.json'
    base={
      'schema_version':'DACK-data-lake-v1','experiment_id':args.experiment_id,'task_id':task_id,
      'experiment_type':'conditional_forced_opening_slot','comparison':'target_vs_Plains',
      'target_index':args.target_index,'target_card':target,'control_card':'Plains','replicate':args.replicate,
      'shard_id':shard_id,'beam':args.beam,'samples':args.samples,'seed_base':args.seed_base,
      'solver_file':SOLVER.name,'solver_sha256':sha256_file(SOLVER),'deck_sha256':deck_sha(),
      'deck_size':len(R.m.DECK),'runner_file':RUNNER.name,'runner_sha256':sha256_file(RUNNER),
      'status':'started','started_unix':time.time()
    }
    # Resume exact completed microtask.
    if mp.exists():
        try:
            old=json.loads(mp.read_text())
            if old.get('status')=='complete' and row_count(cp)==1 and rp.exists():
                print(json.dumps({'status':'complete_existing','task_id':task_id,'target':target,'context_rows':1,'trial_rows':row_count(tp)}));return
        except Exception:pass
    # Clean only this atomic task's incomplete runner outputs.
    for p in (cp,tp,rp):
        if p.exists():p.unlink()
    atomic_json(mp,base)
    cmd=[args.python,str(RUNNER),'--shard-id',str(shard_id),'--contexts-per-target','1','--samples',str(args.samples),
         '--beam',str(args.beam),'--seed-base',str(args.seed_base),'--out-dir',str(tdir),'--target',target,'--progress','1']
    t=time.time();err='';rc=None
    try:
        q=subprocess.run(cmd,text=True,capture_output=True,timeout=args.timeout)
        rc=q.returncode;err=(q.stderr or q.stdout)[-1000:]
        ok=(rc==0 and row_count(cp)==1 and rp.exists())
        status='complete' if ok else 'failed'
    except subprocess.TimeoutExpired:
        status='timeout';rc='timeout';err=f'timed out after {args.timeout}s'
    base.update({'status':status,'elapsed_seconds':round(time.time()-t,4),'returncode':rc,'message':err,
                 'context_rows':row_count(cp),'trial_rows':row_count(tp),'finished_unix':time.time()})
    atomic_json(mp,base)
    print(json.dumps(base,sort_keys=True))
    if status!='complete': raise SystemExit(2)

if __name__=='__main__':main()