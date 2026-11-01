"""Paired fresh-seed full-game research test of frozen v13 teacher imitation vs v5."""
from __future__ import annotations
import argparse,gzip,json,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CHILD=(
  "import sys,json,time\n"
  "gid=int(sys.argv[1]);name=sys.argv[2]\n"
  "if name=='v5':\n"
  " import dack_paired_counterfactual_v5_stable_chance_20261031 as m\n"
  " m.audit();runner=m.reference\n"
  "else:\n"
  " import dack_paired_counterfactual_v13_teacher_distill_20261031 as m\n"
  " m.audit();runner=m.ref\n"
  "t=time.monotonic();r=runner.game('one_key_34',gid)\n"
  "print('GAME_RECORD',json.dumps({'win_turn':r['win_turn'],"
  "'keep_n':r['keep_n'],'history':r['history'],"
  "'seat':r['seat'],'first3':r['first3'],"
  "'seconds':round(time.monotonic()-t,4)}),flush=True)\n"
)

def run(gid,name):
    r=subprocess.run([sys.executable,"-c",CHILD,str(gid),name],cwd=ROOT,
                     capture_output=True,text=True,timeout=1500)
    if r.returncode:raise RuntimeError((name,gid,r.stdout[-1600:],r.stderr[-1600:]))
    results=[x[len("GAME_RECORD "):] for x in r.stdout.splitlines()
             if x.startswith("GAME_RECORD ")]
    if len(results)!=1:raise ValueError((name,gid,results))
    return json.loads(results[0])

def main(start,games,out):
    if not 64000<=start or start+games>65000 or games<1:
        raise ValueError("only reserved 64k full-game policy IDs allowed")
    paired=[]
    for gid in range(start,start+games):
        a=run(gid,"v5");b=run(gid,"student")
        assert a["seat"]==b["seat"]
        paired.append({"game_id":gid,"v5":a,"student":b})
        print("V13_TEACHER_DISTILL_PAIR",gid,a["win_turn"],b["win_turn"],
              a["seconds"],b["seconds"],flush=True)
    def metrics(name):
        o=[p[name] for p in paired]
        return {
           "n":len(o),"T1":sum(x["win_turn"]==1 for x in o),
           "T2":sum(x["win_turn"] in (1,2) for x in o),
           "T3":sum(x["win_turn"] in (1,2,3) for x in o),
           "mean_keep":sum(x["keep_n"] for x in o)/len(o),
           "seconds":round(sum(x["seconds"] for x in o),4)}
    a=metrics("v5");b=metrics("student")
    differences=[int(p["student"]["win_turn"] in (1,2))-
                 int(p["v5"]["win_turn"] in (1,2)) for p in paired]
    result={"status":"PASS","schema":"dack_v13_teacher_distill_paired_research",
            "game_ids":[start,start+games-1],
            "rules":"strict_stable_dice_same_physical_stage_slots",
            "student_model_approved":False,
            "v5":a,"distilled":b,
            "speed_ratio":a["seconds"]/max(.001,b["seconds"]),
            "T2_gains":differences.count(1),"T2_losses":differences.count(-1),
            "warning":"Tiny first experiment, only bounded goldfish deployment, not real multiplayer wins.",
            "rows":paired}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt") as f:json.dump(result,f)
    print("V13_DISTILLED_PAIRED_PASS",json.dumps(
        {k:v for k,v in result.items() if k!="rows"}),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",type=int,default=64000)
    p.add_argument("--games",type=int,default=1)
    p.add_argument("--out",default="shards/v13_pair_64000.json.gz")
    a=p.parse_args()
    main(a.start,a.games,a.out)
