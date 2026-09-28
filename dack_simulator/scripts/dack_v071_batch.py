#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,subprocess,sys,time
from pathlib import Path

HERE=Path(__file__).resolve().parent
MICRO=HERE/'dack_v071_microtask.py'

def atomic_csv(path,rows):
    fields=['experiment_id','replicate','target_index','task_id','status','seconds','returncode','message']
    tmp=path.with_suffix('.tmp')
    with tmp.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    tmp.replace(path)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--experiment-id',required=True)
    ap.add_argument('--out-dir',required=True)
    ap.add_argument('--replicate-start',type=int,required=True)
    ap.add_argument('--replicate-stop',type=int,required=True)
    ap.add_argument('--target-start',type=int,default=0)
    ap.add_argument('--target-stop',type=int,default=60)
    ap.add_argument('--beam',type=int,default=240)
    ap.add_argument('--samples',type=int,default=1)
    ap.add_argument('--seed-base',type=int,default=71024001)
    ap.add_argument('--timeout',type=float,default=45.0)
    ap.add_argument('--max-tasks',type=int,default=20,help='hard cap per invocation')
    args=ap.parse_args()
    out=Path(args.out_dir);out.mkdir(parents=True,exist_ok=True)
    rows=[];attempted=0
    registry=out/'batch_registry.csv'
    for rep in range(args.replicate_start,args.replicate_stop):
      for ti in range(args.target_start,min(args.target_stop,60)):
        if attempted>=args.max_tasks: break
        task_id=f'{args.experiment_id}__r{rep:06d}__t{ti:02d}'
        task_manifest=out/'tasks'/task_id/'task_manifest.json'
        if task_manifest.exists():
            try:
                prior=json.loads(task_manifest.read_text())
                if prior.get('status')=='complete':
                    continue
            except Exception:
                pass
        cmd=[sys.executable,str(MICRO),'--experiment-id',args.experiment_id,'--target-index',str(ti),'--replicate',str(rep),
             '--out-dir',str(out),'--beam',str(args.beam),'--samples',str(args.samples),'--seed-base',str(args.seed_base),'--timeout',str(args.timeout)]
        t=time.time();q=subprocess.run(cmd,text=True,capture_output=True);sec=time.time()-t
        status='unknown';msg=(q.stdout or q.stderr)[-1200:].replace('\n',' | ')
        try:
            last=[x for x in (q.stdout or '').splitlines() if x.strip()][-1]
            status=json.loads(last).get('status','unknown')
        except Exception: status='failed' if q.returncode else 'unknown'
        rec={'experiment_id':args.experiment_id,'replicate':rep,'target_index':ti,'task_id':task_id,'status':status,
             'seconds':round(sec,3),'returncode':q.returncode,'message':msg}
        rows.append(rec);atomic_csv(registry,rows);print(json.dumps(rec),flush=True);attempted+=1
      if attempted>=args.max_tasks: break
    print(json.dumps({'attempted':attempted,'status_counts':{s:sum(r['status']==s for r in rows) for s in sorted(set(r['status'] for r in rows))}},indent=2))

if __name__=='__main__':main()