#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,math,os
from collections import Counter,defaultdict
from pathlib import Path

COMPAT_FIELDS=(
 'schema_version','experiment_id','experiment_type','comparison','engine_version','solver_sha256',
 'production_config_sha256','deck_sha256','runner_sha256','microtask_runner_sha256','beam','samples','seed_base')
PROV_FIELDS=('experiment_id','task_id','replicate','target_index','solver_sha256','production_config_sha256',
             'runner_sha256','microtask_runner_sha256','task_manifest_sha256')

def sha256_file(p:Path):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def fnum(x):return float(x) if x not in ('',None) else float('nan')
def mean(xs):return sum(xs)/len(xs) if xs else float('nan')
def sample_se(xs):
    n=len(xs)
    if n<2:return float('nan')
    mu=mean(xs);return math.sqrt(sum((x-mu)**2 for x in xs)/(n-1)/n)

def read_manifest(p):
    return json.loads(p.read_text(encoding='utf-8'))

def task_files(mp,m):
    td=mp.parent;outs=m.get('outputs') or {}
    try:
        cp=td/outs['contexts']['file'];tp=td/outs['trials']['file'];rp=td/outs['runner_manifest']['file']
    except Exception:raise ValueError(f'{m.get("task_id")}: missing outputs metadata')
    for label,p in [('contexts',cp),('trials',tp),('runner_manifest',rp)]:
        if not p.exists():raise ValueError(f'{m.get("task_id")}: missing {label} file')
        expected=(outs.get(label) or {}).get('sha256')
        if expected and sha256_file(p)!=expected:raise ValueError(f'{m.get("task_id")}: {label} SHA mismatch')
    return cp,tp,rp

def augmented_rows(csv_path,m,manifest_sha):
    with csv_path.open(newline='',encoding='utf-8') as f:
        r=csv.DictReader(f)
        fields=list(PROV_FIELDS)+list(r.fieldnames or [])
        for row in r:
            prov={
              'experiment_id':m['experiment_id'],'task_id':m['task_id'],'replicate':m['replicate'],
              'target_index':m['target_index'],'solver_sha256':m['solver_sha256'],
              'production_config_sha256':m['production_config_sha256'],'runner_sha256':m['runner_sha256'],
              'microtask_runner_sha256':m['microtask_runner_sha256'],'task_manifest_sha256':manifest_sha}
            yield fields,{**prov,**row}

def write_pooled(records,kind,out_path):
    seen=set();count=0;writer=None
    tmp=out_path.with_suffix(out_path.suffix+'.tmp')
    with tmp.open('w',newline='',encoding='utf-8') as fo:
        for mp,m,cp,tp in records:
            src=cp if kind=='contexts' else tp;manifest_sha=sha256_file(mp)
            for fields,row in augmented_rows(src,m,manifest_sha):
                if writer is None:writer=csv.DictWriter(fo,fieldnames=fields);writer.writeheader()
                key=(row['task_id'],row.get('context_id','')) if kind=='contexts' else \
                    (row['task_id'],row.get('context_id',''),row.get('future_index',''),row.get('seat_class',''))
                if key in seen:continue
                seen.add(key);writer.writerow(row);count+=1
    tmp.replace(out_path)
    return count

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--in-dir',required=True);ap.add_argument('--out-dir',required=True);args=ap.parse_args()
    inp=Path(args.in_dir);out=Path(args.out_dir);out.mkdir(parents=True,exist_ok=True)
    manifests=sorted(inp.rglob('task_manifest.json'))
    if not manifests:raise SystemExit('no task manifests found')
    status_counts=Counter();complete=[];compat=None
    for mp in manifests:
        m=read_manifest(mp);status_counts[m.get('status','missing')]+=1
        if m.get('status')!='complete':continue
        sig={k:m.get(k) for k in COMPAT_FIELDS}
        if compat is None:compat=sig
        elif sig!=compat:
            diffs={k:(compat.get(k),sig.get(k)) for k in COMPAT_FIELDS if compat.get(k)!=sig.get(k)}
            raise SystemExit(f'incompatible completed task {m.get("task_id")}: {diffs}')
        cp,tp,_=task_files(mp,m)
        with cp.open(newline='',encoding='utf-8') as f:
            if sum(1 for _ in csv.DictReader(f))!=1:raise SystemExit(f'{m.get("task_id")}: context row count != 1')
        complete.append((mp,m,cp,tp))
    if not complete:raise SystemExit('no complete compatible tasks to pool')
    ids=[m['task_id'] for _,m,_,_ in complete]
    if len(ids)!=len(set(ids)):raise SystemExit('duplicate complete task_id detected')

    nctx=write_pooled(complete,'contexts',out/'pooled_contexts.csv')
    ntr=write_pooled(complete,'trials',out/'pooled_trials.csv')

    groups=defaultdict(list);meta={}
    with (out/'pooled_contexts.csv').open(newline='',encoding='utf-8') as f:
        for row in csv.DictReader(f):
            c=row['target_card'];groups[c].append(row);meta[c]=(row['target_role'],row['target_group'])
    fields=['target_card','target_role','target_group','N','mean_delta_utility','se_delta_utility','ci95_lo','ci95_hi',
            'mean_delta_le2','mean_delta_le3','mean_delta_t1','mean_delta_t2','mean_delta_t3','positive_n','negative_n','tie_n',
            'mean_target_utility','mean_control_utility','mean_target_le2','mean_control_le2','mean_target_le3','mean_control_le3']
    rows=[]
    for c,rs in groups.items():
        du=[fnum(r['delta_utility']) for r in rs];se=sample_se(du);mu=mean(du)
        rows.append({'target_card':c,'target_role':meta[c][0],'target_group':meta[c][1],'N':len(rs),
          'mean_delta_utility':mu,'se_delta_utility':se,'ci95_lo':mu-1.96*se if math.isfinite(se) else '',
          'ci95_hi':mu+1.96*se if math.isfinite(se) else '',
          'mean_delta_le2':mean([fnum(r['delta_le2']) for r in rs]),'mean_delta_le3':mean([fnum(r['delta_le3']) for r in rs]),
          'mean_delta_t1':mean([fnum(r['delta_t1']) for r in rs]),'mean_delta_t2':mean([fnum(r['delta_t2']) for r in rs]),
          'mean_delta_t3':mean([fnum(r['delta_t3']) for r in rs]),'positive_n':sum(x>1e-12 for x in du),
          'negative_n':sum(x<-1e-12 for x in du),'tie_n':sum(abs(x)<=1e-12 for x in du),
          'mean_target_utility':mean([fnum(r['target_utility']) for r in rs]),'mean_control_utility':mean([fnum(r['control_utility']) for r in rs]),
          'mean_target_le2':mean([fnum(r['target_le2']) for r in rs]),'mean_control_le2':mean([fnum(r['control_le2']) for r in rs]),
          'mean_target_le3':mean([fnum(r['target_le3']) for r in rs]),'mean_control_le3':mean([fnum(r['control_le3']) for r in rs])})
    rows.sort(key=lambda r:r['mean_delta_utility'],reverse=True)
    with (out/'pooled_summary_by_card.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

    idx_fields=['task_id','target_index','target_card','replicate','status']+list(COMPAT_FIELDS[4:])+['task_manifest_sha256']
    with (out/'pooled_task_index.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=idx_fields);w.writeheader()
        for mp,m,_,_ in complete:
            row={k:m.get(k) for k in idx_fields if k!='task_manifest_sha256'};row['task_manifest_sha256']=sha256_file(mp);w.writerow(row)
    manifest={
      'schema_version':'DACK-atomic-pool-v1','complete_tasks':len(complete),'discovered_task_manifests':len(manifests),
      'status_counts':dict(status_counts),'pooled_context_rows':nctx,'pooled_trial_rows':ntr,'summary_cards':len(rows),
      'compatibility_signature':compat,'task_index_sha256':sha256_file(out/'pooled_task_index.csv'),
      'pooled_contexts_sha256':sha256_file(out/'pooled_contexts.csv'),'pooled_trials_sha256':sha256_file(out/'pooled_trials.csv')}
    tmp=out/'pool_manifest.json.tmp';tmp.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8');tmp.replace(out/'pool_manifest.json')
    print(json.dumps(manifest,indent=2,sort_keys=True))

if __name__=='__main__':main()
