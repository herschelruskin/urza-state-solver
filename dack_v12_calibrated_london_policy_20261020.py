#!/usr/bin/env python3
"""Apply independently calibrated free-London thresholds to v11 Realistic Beam.

A/B with v11 frozen old continuation choices on same physical RNG seeds.
The only requested change is keep/continue decision thresholds. Exactly the
same bottoming evaluator and actual turn search are used for both policies.
"""
import argparse,gzip,hashlib,json,random,time
from collections import Counter
from pathlib import Path
import dack_v11_pre_reveal_barrier_20261020 as v11
v10=v11.v10;v2=v11.v2;root=v11.root;d=v11.d;m=v11.m
batch=root.batch
ORIG_CHOOSE=root.choose_hand_with_free
CALIBRATION=None
STAGES=(7,7,6,5,4,3,2,1)
MULL_LOG=[]

def load_calibration(path):
    global CALIBRATION
    q=json.loads(Path(path).read_text())
    assert q["status"]=="PASS"
    assert "variants" in q
    CALIBRATION=q
    return q

def threshold(variant,seat,stage):
    assert CALIBRATION is not None
    cls="first" if seat==0 else "later"
    data=CALIBRATION["variants"][variant]["seat_classes"][cls]
    n=STAGES[stage]
    if n==1:return -1.
    if stage==0:return float(data["first_free_seven_threshold"])
    if stage==1:return float(data["second_seven_threshold"])
    return float(data["normal_keep_n_threshold"][str(n)])

def chooser(rng,seat):
    variant=getattr(chooser,"variant")
    expected=CALIBRATION["variants"][variant]["deck_sha256"]
    actual=hashlib.sha256("\n".join(v2.trial.VARIANTS[variant]).encode()).hexdigest()
    assert expected==actual,("deck changed; recalibrate London policy",variant)
    audit=[]
    for i,n in enumerate(STAGES):
        cards=list(d.DECK);rng.shuffle(cards)
        seven,rest=cards[:7],cards[7:]
        raw,ev,struct,hand,bottom,unknown,_,refined=\
            batch.evaluate_keep(seven,n,rest,seat)
        cutoff=threshold(variant,seat,i)
        keep=(n==1 or raw>=cutoff)
        row={"stage":i,"keep_n":n,
             "utility":round(float(raw),6),
             "threshold":round(cutoff,6),"accept":keep,
             "refined":bool(refined)}
        audit.append(row)
        if keep:
            MULL_LOG.extend(audit)
            return d.State(1,tuple(hand),tuple(unknown)+tuple(bottom)),n,audit
    raise AssertionError("terminal keep_n=1 must accept")

def audit():
    v11.audit()
    assert STAGES==(7,7,6,5,4,3,2,1)
    assert len(set(STAGES))==7
    print("DACK_V12_FREE_LONDON_STAGE_POLICY_PASS",flush=True)

def simulate(variant,gid,calibrated):
    root.install(variant)
    MULL_LOG.clear()
    chooser.variant=variant
    if calibrated:
        root.choose_hand_with_free=chooser
    else:
        root.choose_hand_with_free=ORIG_CHOOSE
    try:
        rec=v11.simulate(variant,gid)
    finally:
        root.choose_hand_with_free=ORIG_CHOOSE
    return {"game_id":gid,"win_turn":rec["win_turn"],"keep_n":rec["keep_n"],
        "seat":rec["seat"],"rolls":rec["rolls"],"turn_audit":rec["turn_audit"],
        "stages":list(MULL_LOG) if calibrated else []}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",action="store_true")
    p.add_argument("--variant",choices=("current","buck_worldmap"),default="current")
    p.add_argument("--policy",choices=("frozen","calibrated"),default="calibrated")
    p.add_argument("--calibration",default="dack_v12_thresholds.json")
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--games",type=int,default=2)
    p.add_argument("--out",default="dack_v12_mulligan.json.gz")
    a=p.parse_args()
    audit()
    if a.audit:return
    load_calibration(a.calibration)
    rows=[];start=time.time()
    for j in range(a.games):
        gid=a.shard*a.games+j
        q=simulate(a.variant,gid,a.policy=="calibrated")
        rows.append(q)
        print("DACK_V12_MULLIGAN_GAME",a.variant,a.policy,gid,
              q["win_turn"],q["keep_n"],flush=True)
    result={
      "schema":"dack_v12_mulligan_policy_trial","variant":a.variant,
      "policy":a.policy,"shard":a.shard,"games":a.games,
      "deck_sha256":hashlib.sha256("\n".join(v2.trial.VARIANTS[a.variant]).encode()).hexdigest(),
      "seed_base":v2.SEED_BASE,
      "counts":{str(k):v for k,v in Counter(x["win_turn"] for x in rows).items()},
      "elapsed_seconds":round(time.time()-start,2),"rows":rows}
    with gzip.open(a.out,"wt",encoding="utf8") as f:json.dump(result,f,separators=(",",":"))
    print("DACK_V12_MULLIGAN_SHARD_PASS",a.variant,a.policy,a.games,flush=True)
if __name__=="__main__":main()
