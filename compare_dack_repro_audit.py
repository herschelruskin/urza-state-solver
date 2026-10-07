#!/usr/bin/env python3
import argparse,glob,gzip,json,os
from collections import defaultdict

VARS=(
    "ablate__Final4_revert_Voltaic_to_Candelabra",
    "package__Core3_plus_Incubator_over_Prismatic",
    "package__Core3_plus_Lantern_over_Everflowing",
    "package__Core3_plus_Sonic_over_Everflowing",
)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--ind-glob",required=True)
    ap.add_argument("--bun-glob",required=True)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()

    ind=defaultdict(dict)
    for fp in glob.glob(a.ind_glob):
        with open(fp,encoding="utf-8") as f:p=json.load(f)
        v=p["variant"]
        for r in p["rows"]:
            gid=int(r[0]); ind[v][gid]=[int(r[1]),int(r[2]),int(r[3])]

    bun=defaultdict(dict)
    for fp in glob.glob(a.bun_glob):
        with gzip.open(fp,"rb") as f:p=json.loads(f.read())
        for v,z in p["variants"].items():
            for r in z["rows"]:
                gid=int(r[0]); bun[v][gid]=[int(r[2]),int(r[3]),int(r[4])]

    result={"schema":"dack_repro_audit_v1","variants":{},"exact_match":True}
    for v in VARS:
        gids=sorted(set(ind[v])|set(bun[v]))
        diffs=[]
        for gid in gids:
            if ind[v].get(gid)!=bun[v].get(gid):
                diffs.append({"game_id":gid,"independent":ind[v].get(gid),"bundled":bun[v].get(gid)})
        result["variants"][v]={"n_independent":len(ind[v]),"n_bundled":len(bun[v]),
                               "n_differences":len(diffs),"differences":diffs[:50]}
        if diffs or len(ind[v])!=len(bun[v]): result["exact_match"]=False
    with open(a.out,"w",encoding="utf-8") as f:json.dump(result,f,indent=2)
    print(json.dumps({"exact_match":result["exact_match"],
                      "diff_counts":{v:result["variants"][v]["n_differences"] for v in VARS}}))
    if not result["exact_match"]:
        raise SystemExit(2)

if __name__=="__main__":
    main()
