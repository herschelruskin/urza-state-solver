#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,math,sqlite3
from collections import defaultdict
from pathlib import Path


def read_csv(p):
    with p.open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))
def mean(xs): return sum(xs)/len(xs) if xs else float('nan')
def se(xs):
    if len(xs)<2:return float('nan')
    m=mean(xs);return math.sqrt(sum((x-m)**2 for x in xs)/(len(xs)-1)/len(xs))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--experiment-dir',required=True);ap.add_argument('--out-dir',required=True);args=ap.parse_args()
    root=Path(args.experiment_dir);out=Path(args.out_dir);out.mkdir(parents=True,exist_ok=True)
    manifests=[];contexts=[];trials=[];seen=set();fingerprints=set()
    for mp in sorted((root/'tasks').glob('*/task_manifest.json')):
        m=json.loads(mp.read_text())
        if m.get('status')!='complete':continue
        task=m['task_id'];td=mp.parent
        cp=next(iter(td.glob('shard_*_contexts.csv')),None);tp=next(iter(td.glob('shard_*_trials.csv')),None)
        if not cp or not tp:continue
        cr=read_csv(cp);tr=read_csv(tp)
        if len(cr)!=1:continue
        key=(m['experiment_id'],m['solver_sha256'],m['deck_sha256'],m['beam'],m['samples'],m['seed_base'])
        fingerprints.add(key)
        if task in seen:continue
        seen.add(task);manifests.append(m)
        for r in cr:r.update({'experiment_id':m['experiment_id'],'task_id':task,'replicate':m['replicate'],'solver_sha256':m['solver_sha256'],'deck_sha256':m['deck_sha256']});contexts.append(r)
        for r in tr:r.update({'experiment_id':m['experiment_id'],'task_id':task,'replicate':m['replicate'],'solver_sha256':m['solver_sha256'],'deck_sha256':m['deck_sha256']});trials.append(r)
    if len(fingerprints)>1: raise SystemExit(f'incompatible fingerprints found: {len(fingerprints)}; pool experiments/configs separately')
    def write(name,rows):
        p=out/name
        if not rows:return
        fields=list(rows[0])
        with p.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    write('contexts.csv',contexts);write('trials.csv',trials)
    groups=defaultdict(list)
    for r in contexts:groups[r['target_card']].append(r)
    summary=[]
    for card,rs in groups.items():
        du=[float(r['delta_utility']) for r in rs];d2=[float(r['delta_le2']) for r in rs];d3=[float(r['delta_le3']) for r in rs]
        e=se(du);mu=mean(du)
        summary.append({'target_card':card,'N':len(rs),'mean_delta_utility':mu,'se_delta_utility':e,
                        'ci95_lo':mu-1.96*e if math.isfinite(e) else '','ci95_hi':mu+1.96*e if math.isfinite(e) else '',
                        'mean_delta_le2':mean(d2),'mean_delta_le3':mean(d3),'positive_n':sum(x>1e-12 for x in du),
                        'negative_n':sum(x<-1e-12 for x in du),'tie_n':sum(abs(x)<=1e-12 for x in du)})
    summary.sort(key=lambda r:r['mean_delta_utility'],reverse=True);write('summary_by_card.csv',summary)
    # SQLite mirror for mining across many experiments later.
    db=sqlite3.connect(out/'dack_data_lake.sqlite')
    for table,rows in [('contexts',contexts),('trials',trials),('summary_by_card',summary),('tasks',manifests)]:
        db.execute(f'DROP TABLE IF EXISTS {table}')
        if not rows:continue
        fields=list(rows[0]);db.execute('CREATE TABLE '+table+' ('+', '.join('"'+f+'" TEXT' for f in fields)+')')
        db.executemany('INSERT INTO '+table+' VALUES ('+','.join('?' for _ in fields)+')',[[str(r.get(f,'')) for f in fields] for r in rows])
    db.commit();db.close()
    (out/'pool_manifest.json').write_text(json.dumps({'complete_tasks':len(manifests),'context_rows':len(contexts),'trial_rows':len(trials),'fingerprint_count':len(fingerprints),'fingerprints':[list(x) for x in fingerprints]},indent=2),encoding='utf-8')
    print(json.dumps({'complete_tasks':len(manifests),'contexts':len(contexts),'trials':len(trials),'cards':len(summary),'out':str(out)},indent=2))
if __name__=='__main__':main()