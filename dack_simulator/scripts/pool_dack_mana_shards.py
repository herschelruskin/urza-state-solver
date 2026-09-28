#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,glob,json,math,os
from collections import defaultdict
from pathlib import Path

def fnum(x): return float(x) if x not in ('',None) else float('nan')
def mean(xs): return sum(xs)/len(xs) if xs else float('nan')
def sample_se(xs):
    n=len(xs)
    if n<2:return float('nan')
    mu=mean(xs);var=sum((x-mu)**2 for x in xs)/(n-1)
    return math.sqrt(var/n)

def concat_csv(paths,out):
    paths=list(paths)
    if not paths:return 0
    seen=set();n=0
    with open(out,'w',newline='',encoding='utf-8') as fo:
        w=None
        for p in paths:
            with open(p,newline='',encoding='utf-8') as fi:
                r=csv.DictReader(fi)
                if w is None:w=csv.DictWriter(fo,fieldnames=r.fieldnames);w.writeheader()
                for row in r:
                    key=(row.get('context_id'),row.get('target_card'),row.get('future_index',''),row.get('seat_class',''))
                    if key in seen:continue
                    seen.add(key);w.writerow(row);n+=1
    return n

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--in-dir',required=True);ap.add_argument('--out-dir',required=True);args=ap.parse_args()
    inp=Path(args.in_dir);out=Path(args.out_dir);out.mkdir(parents=True,exist_ok=True)
    ctx_files=sorted(inp.glob('shard_*_contexts.csv'));trial_files=sorted(inp.glob('shard_*_trials.csv'))
    nctx=concat_csv(ctx_files,out/'pooled_contexts.csv'); ntr=concat_csv(trial_files,out/'pooled_trials.csv')
    groups=defaultdict(list);meta={}
    with open(out/'pooled_contexts.csv',newline='',encoding='utf-8') as f:
        for row in csv.DictReader(f):
            c=row['target_card'];groups[c].append(row);meta[c]=(row['target_role'],row['target_group'])
    fields=['target_card','target_role','target_group','N','mean_delta_utility','se_delta_utility','ci95_lo','ci95_hi',
            'mean_delta_le2','mean_delta_le3','mean_delta_t1','mean_delta_t2','mean_delta_t3','positive_n','negative_n','tie_n',
            'mean_target_utility','mean_control_utility','mean_target_le2','mean_control_le2','mean_target_le3','mean_control_le3']
    rows=[]
    for c,rs in groups.items():
        du=[fnum(r['delta_utility']) for r in rs];se=sample_se(du);mu=mean(du)
        rows.append({
            'target_card':c,'target_role':meta[c][0],'target_group':meta[c][1],'N':len(rs),
            'mean_delta_utility':mu,'se_delta_utility':se,'ci95_lo':mu-1.96*se if math.isfinite(se) else '',
            'ci95_hi':mu+1.96*se if math.isfinite(se) else '',
            'mean_delta_le2':mean([fnum(r['delta_le2']) for r in rs]),'mean_delta_le3':mean([fnum(r['delta_le3']) for r in rs]),
            'mean_delta_t1':mean([fnum(r['delta_t1']) for r in rs]),'mean_delta_t2':mean([fnum(r['delta_t2']) for r in rs]),'mean_delta_t3':mean([fnum(r['delta_t3']) for r in rs]),
            'positive_n':sum(x>1e-12 for x in du),'negative_n':sum(x<-1e-12 for x in du),'tie_n':sum(abs(x)<=1e-12 for x in du),
            'mean_target_utility':mean([fnum(r['target_utility']) for r in rs]),'mean_control_utility':mean([fnum(r['control_utility']) for r in rs]),
            'mean_target_le2':mean([fnum(r['target_le2']) for r in rs]),'mean_control_le2':mean([fnum(r['control_le2']) for r in rs]),
            'mean_target_le3':mean([fnum(r['target_le3']) for r in rs]),'mean_control_le3':mean([fnum(r['control_le3']) for r in rs])})
    rows.sort(key=lambda r:r['mean_delta_utility'],reverse=True)
    with open(out/'pooled_summary_by_card.csv','w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    manifests=[]
    for p in sorted(inp.glob('shard_*_manifest.json')):
        manifests.append(json.load(open(p)))
    (out/'pool_manifest.json').write_text(json.dumps({'shards':len(manifests),'pooled_context_rows':nctx,'pooled_trial_rows':ntr,'source_manifests':manifests},indent=2),encoding='utf-8')
    print(json.dumps({'shards':len(manifests),'contexts':nctx,'trials':ntr,'summary_cards':len(rows),'out_dir':str(out)},indent=2))
if __name__=='__main__':main()
