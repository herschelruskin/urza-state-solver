#!/usr/bin/env python3
"""Process-isolated DACK v0.68 mana-screen sweep.

Each target/context is executed in its own child process. A pathological beam search can
therefore time out without losing completed cards or corrupting the sweep. Re-running the
same sweep is resumable: complete one-row shards are skipped; empty/partial shards are
removed and retried with the same deterministic shard id/seed.
"""
from __future__ import annotations
import argparse,csv,importlib.util,json,os,subprocess,sys,time
from pathlib import Path

HERE=Path(__file__).resolve().parent
RUNNER=HERE/'dack_v068_sharded_mana_screen.py'

def load_runner():
    spec=importlib.util.spec_from_file_location('dack_v068_runner_manifest',RUNNER)
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
    return m
R=load_runner()

def row_count(path:Path):
    if not path.exists(): return 0
    try:
        with path.open(newline='',encoding='utf-8') as f:return sum(1 for _ in csv.DictReader(f))
    except Exception:return 0

def shard_id_for(sweep_id,target_index):
    # 680000 + sweep*100 + canonical target index. 60 targets fit safely in each sweep block.
    return 680000 + int(sweep_id)*100 + int(target_index)

def save_status(path, rows):
    fields=['sweep_id','target_index','target_card','shard_id','status','seconds','context_rows','trial_rows','returncode','message']
    tmp=path.with_suffix('.tmp')
    with tmp.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    tmp.replace(path)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--sweep-id',type=int,required=True)
    ap.add_argument('--out-dir',required=True)
    ap.add_argument('--target-start',type=int,default=0)
    ap.add_argument('--target-stop',type=int,default=None)
    ap.add_argument('--beam',type=int,default=240)
    ap.add_argument('--samples',type=int,default=4)
    ap.add_argument('--seed-base',type=int,default=680240)
    ap.add_argument('--timeout',type=float,default=45.0,help='seconds per target/context child process')
    ap.add_argument('--python',default=sys.executable)
    args=ap.parse_args()
    out=Path(args.out_dir);out.mkdir(parents=True,exist_ok=True)
    stop=len(R.TARGETS) if args.target_stop is None else min(args.target_stop,len(R.TARGETS))
    inds=list(range(max(0,args.target_start),stop))
    status_path=out/f'sweep_{args.sweep_id:04d}_status.csv'
    existing={}
    if status_path.exists():
        with status_path.open(newline='',encoding='utf-8') as f:
            existing={int(r['target_index']):r for r in csv.DictReader(f)}
    rows=[]
    for idx in inds:
        card=R.TARGETS[idx]; sid=shard_id_for(args.sweep_id,idx)
        cp=out/f'shard_{sid:04d}_contexts.csv';tp=out/f'shard_{sid:04d}_trials.csv';mp=out/f'shard_{sid:04d}_manifest.json'
        nc=row_count(cp);nt=row_count(tp)
        if nc==1 and mp.exists():
            rec={'sweep_id':args.sweep_id,'target_index':idx,'target_card':card,'shard_id':sid,'status':'complete_existing',
                 'seconds':0,'context_rows':nc,'trial_rows':nt,'returncode':0,'message':'resumed existing complete shard'}
            rows.append(rec);save_status(status_path,rows);print(json.dumps(rec),flush=True);continue
        # Empty/partial one-context shard cannot contain a complete context. Remove and retry deterministically.
        for p in (cp,tp,mp):
            if p.exists():p.unlink()
        cmd=[args.python,str(RUNNER),'--shard-id',str(sid),'--contexts-per-target','1','--samples',str(args.samples),
             '--beam',str(args.beam),'--seed-base',str(args.seed_base),'--out-dir',str(out),'--target',card,'--progress','1']
        t=time.time();status='failed';msg='';rc=''
        try:
            p=subprocess.run(cmd,text=True,capture_output=True,timeout=args.timeout)
            rc=p.returncode;status='complete' if p.returncode==0 and row_count(cp)==1 and mp.exists() else 'failed'
            msg=(p.stderr or p.stdout)[-500:].replace('\n',' | ')
        except subprocess.TimeoutExpired as e:
            status='timeout';rc='timeout';msg=f'timed out after {args.timeout}s'
        sec=time.time()-t;nc=row_count(cp);nt=row_count(tp)
        rec={'sweep_id':args.sweep_id,'target_index':idx,'target_card':card,'shard_id':sid,'status':status,
             'seconds':round(sec,3),'context_rows':nc,'trial_rows':nt,'returncode':rc,'message':msg}
        rows.append(rec);save_status(status_path,rows);print(json.dumps(rec),flush=True)
    summary={k:sum(r['status']==k for r in rows) for k in sorted(set(r['status'] for r in rows))}
    print(json.dumps({'sweep_id':args.sweep_id,'targets_attempted':len(rows),'status_counts':summary,'status_csv':str(status_path)},indent=2))
if __name__=='__main__':main()
