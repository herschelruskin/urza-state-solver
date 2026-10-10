#!/usr/bin/env python3
"""Pool matched full-engine DACK Jeweled Lotus/Mana Crypt 1024-game shards."""
import argparse, csv, glob, gzip, json, math
from collections import Counter
from pathlib import Path
from dack_lotus_crypt_n1024 import VARIANTS

def summarize(rows):
    n=len(rows); c=Counter(r[4] for r in rows)
    return dict(n=n,T1=100*c[1]/n,T2_exact=100*c[2]/n,
                T3_exact=100*c[3]/n,leT2=100*(c[1]+c[2])/n,
                leT3=100*(c[1]+c[2]+c[3])/n,fail=100*c[0]/n,
                mean_keep=sum(r[3] for r in rows)/n)

def paired_delta(rows_a,rows_b,metric):
    def success(row):
        t=row[4]
        return t==1 if metric=="T1" else (
            t in (1,2) if metric=="leT2" else t in (1,2,3))
    diffs=[int(success(b))-int(success(a)) for a,b in zip(rows_a,rows_b)]
    n=len(diffs); avg=sum(diffs)/n
    var=sum((v-avg)**2 for v in diffs)/(n-1)
    half=1.96*math.sqrt(var/n)*100
    return dict(delta_pp=100*avg,ci95_low_pp=100*avg-half,
                ci95_high_pp=100*avg+half,
                better=sum(x==1 for x in diffs),
                worse=sum(x==-1 for x in diffs))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--glob",required=True)
    ap.add_argument("--expected",type=int,default=1024)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    paths=sorted(glob.glob(a.glob))
    assert paths, "missing result shards"
    allrows={v:[] for v in VARIANTS}; shas={}
    meta=None
    for path in paths:
        with gzip.open(path,"rt") as f: obj=json.load(f)
        assert obj["schema"]=="dack_paired_lotus_crypt_n1024_v1"
        if meta is None: meta=obj["config"]
        else: assert meta==obj["config"]
        for v in VARIANTS:
            item=obj["variants"][v]
            if v in shas: assert shas[v]==item["deck_sha256"]
            shas[v]=item["deck_sha256"]
            allrows[v].extend(item["rows"])
    for v in VARIANTS:
        rows=sorted(allrows[v],key=lambda x:x[0])
        assert len(rows)==a.expected,(v,len(rows),a.expected)
        assert [x[0] for x in rows]==list(range(a.expected))
        allrows[v]=rows
    for i in range(a.expected):
        assert len({allrows[v][i][1] for v in VARIANTS})==1
        assert len({allrows[v][i][2] for v in VARIANTS})==1
    summary={v:summarize(allrows[v]) for v in VARIANTS}
    paired={}
    for a1,b1 in (("A_baseline","B_jeweled_lotus"),
                  ("B_jeweled_lotus","C_lotus_mana_crypt"),
                  ("A_baseline","C_lotus_mana_crypt")):
        paired[a1+"_to_"+b1]={metric:paired_delta(allrows[a1],allrows[b1],metric)
                              for metric in ("T1","leT2","leT3")}
    obj={"n":a.expected,"engine":meta["engine"],"policy":meta["policy"],
         "config":meta,"deck_sha256":shas,"summary":summary,"paired":paired,
         "baseline_T1_sanity":"pass" if 2.5<=summary["A_baseline"]["T1"]<=7 else "FLAG_REVIEW"}
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    Path(a.out).write_text(json.dumps(obj,indent=2)+"\n")
    csvpath=str(Path(a.out).with_suffix(".csv"))
    with open(csvpath,"w",newline="") as f:
        w=csv.writer(f);w.writerow(["variant","N","T1","T2_exact","leT2","T3_exact","leT3","fail","mean_keep"])
        for v in VARIANTS:
            s=summary[v]
            w.writerow([v,s["n"],s["T1"],s["T2_exact"],s["leT2"],s["T3_exact"],s["leT3"],s["fail"],s["mean_keep"]])
    print(json.dumps({"summary":summary,"paired":paired,"baseline_T1_sanity":obj["baseline_T1_sanity"]}),flush=True)

if __name__=="__main__":main()
