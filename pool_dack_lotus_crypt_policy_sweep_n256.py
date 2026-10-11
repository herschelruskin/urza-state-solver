#!/usr/bin/env python3
"""Pool 256 paired real-engine policy-sweep games, with paired CIs."""
import argparse,glob,gzip,json,math,collections,pathlib
ARMS=("frozen","deeper_005","deeper_010","lotus_tutor","lotus_tutor_deeper_005")
def result(rows):
    n=len(rows);by=collections.Counter(q["win_turn"] for q in rows)
    return {"n":n,"T1_pct":100*by[1]/n,
            "leT2_pct":100*(by[1]+by[2])/n,
            "leT3_pct":100*(by[1]+by[2]+by[3])/n,
            "mean_keep_n":sum(q["keep_n"] for q in rows)/n,
            "lotus_kept":sum("Jeweled Lotus" in q["kept_hand"] for q in rows),
            "crypt_kept":sum("Mana Crypt" in q["kept_hand"] for q in rows),
            "both_kept":sum(
                "Jeweled Lotus" in q["kept_hand"] and "Mana Crypt" in q["kept_hand"]
                for q in rows)}
def paired(a,b,condition):
    da=[int(condition(y))-int(condition(x)) for x,y in zip(a,b)]
    n=len(da);mu=sum(da)/n
    var=sum((x-mu)**2 for x in da)/(n-1)
    sd=1.96*math.sqrt(var/n)
    return {"delta_pp":mu*100,"ci95_pp":[(mu-sd)*100,(mu+sd)*100],
            "better":da.count(1),"worse":da.count(-1)}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--glob",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--expected",type=int,default=256)
    args=p.parse_args()
    paths=glob.glob(args.glob)
    assert paths
    allrows={a:[] for a in ARMS};hashes=set()
    for path in paths:
        with gzip.open(path,"rt") as f:v=json.load(f)
        assert v["schema"]=="dack_policy_sweep_n256_v1"
        hashes.add(v["deck_sha256"])
        for a in ARMS:allrows[a]+=v["arms"][a]
    assert len(hashes)==1
    for a,rows in allrows.items():
        rows.sort(key=lambda q:q["id"])
        assert len(rows)==args.expected,(a,len(rows))
        assert [r["id"] for r in rows]==list(range(args.expected))
    for i in range(args.expected):
        assert len({allrows[a][i]["seed"] for a in ARMS})==1
        assert len({allrows[a][i]["seat"] for a in ARMS})==1
    metrics={"T1":lambda q:q["win_turn"]==1,
             "leT2":lambda q:q["win_turn"] in (1,2),
             "leT3":lambda q:q["win_turn"] in (1,2,3)}
    summary={a:result(rows) for a,rows in allrows.items()}
    deltas={a:{name:paired(allrows["frozen"],allrows[a],fn)
               for name,fn in metrics.items()}
            for a in ARMS if a!="frozen"}
    obj={"engine":"v0.77-real","n":args.expected,
         "deck_sha256":next(iter(hashes)),"summary":summary,
         "paired_vs_frozen":deltas}
    pathlib.Path(args.out).parent.mkdir(parents=True,exist_ok=True)
    pathlib.Path(args.out).write_text(json.dumps(obj,indent=2)+"\n")
    print("POOLED_N256_POLICY_SWEEP_PASS")
    print(json.dumps(obj),flush=True)
if __name__=="__main__": main()
