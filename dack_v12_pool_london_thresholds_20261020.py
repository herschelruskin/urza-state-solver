#!/usr/bin/env python3
"""Pool independent sampled utility distributions into dynamic London thresholds."""
import argparse,glob,json,math
from pathlib import Path

def compute(files):
    grouped={}
    for f in files:
        q=json.loads(Path(f).read_text())
        assert q["schema"]=="dack_v12_london_calibration_samples"
        k=(q["variant"],q["seat_class"],q["keep_n"])
        assert k not in grouped
        assert q["n"]==len(q["samples"])
        vals=[s["utility"] for s in q["samples"]]
        assert all(0<=x<=1.5 for x in vals)
        grouped[k]=(vals,q["deck_sha256"])
    out={"status":"PASS","model":"free London sequence 7/7/6/5/4/3/2/1; E(max(U_n, continuation))",
         "variants":{},"limitations":[
          "Utility values are inherited optimistic continuation estimates",
          "Small independent-hand calibration samples may produce noisy threshold estimates",
          "Per-deck and per-seat-class thresholds must be recomputed after deck change",
          "Known-top/Scroll Rack repairs do not yet apply within the mulligan evaluator"]}
    for variant in ("current","buck_worldmap"):
        sha={grouped[(variant,seat,n)][1] for seat in ("first","later") for n in range(1,8)}
        assert len(sha)==1
        out["variants"][variant]={"deck_sha256":sha.pop(),"seat_classes":{}}
        for seat in ("first","later"):
            v={};summary={}
            for n in range(1,8):
                vals=grouped[(variant,seat,n)][0]
                if n==1:
                    v[n]=sum(vals)/len(vals)
                else:
                    v[n]=sum(max(x,v[n-1]) for x in vals)/len(vals)
                summary[str(n)]={"n":len(vals),"utility_mean":sum(vals)/len(vals),
                  "continue_to_lower_depth_value":v.get(n-1),
                  "optimal_value_at_depth":v[n],
                  "utility_standard_error":math.sqrt(sum((x-sum(vals)/len(vals))**2 for x in vals)/(len(vals)*(len(vals)-1)))}
            assert all(v[n]>=v[n-1] for n in range(2,8))
            out["variants"][variant]["seat_classes"][seat]={
              "dynamic_V_by_depth":{str(n):v[n] for n in range(1,8)},
              "first_free_seven_threshold":v[7],
              "second_seven_threshold":v[6],
              "normal_keep_n_threshold":{str(n):v[n-1] for n in range(2,8)},
              "sample_summary":summary}
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--samples",default="calibration")
    p.add_argument("--out",default="dack_v12_thresholds.json")
    a=p.parse_args()
    files=glob.glob(a.samples+"/**/*.json",recursive=True)
    assert len(files)==28,(len(files),files[:3])
    out=compute(files)
    Path(a.out).write_text(json.dumps(out,indent=2)+"\n")
    print("DACK_V12_FREE_LONDON_DYNAMIC_THRESHOLDS_PASS",json.dumps({
      v:{seat:{"first7":q["first_free_seven_threshold"],
                 "second7":q["second_seven_threshold"]}
         for seat,q in dat["seat_classes"].items()}
      for v,dat in out["variants"].items()}),flush=True)

if __name__=="__main__":main()
