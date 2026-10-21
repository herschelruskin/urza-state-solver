#!/usr/bin/env python3
"""Recalibrate free multiplayer London continuation thresholds for Dack.

Independent sampled opening seven-card hands per keep depth and seat class.
All sampled keep decisions use v10's hidden-order-blind bottom estimator.
The calibrated value is the expected optimal next-hand value in the same
utility scale; it is *not* the old stale fixed cutoff.

Free London sequence is 7, 7, 6, 5, 4, 3, 2, 1.
Compute V1=E(U1), then Vn=E(max(Un,V[n-1])) for n=2..7.
First seven uses V7 (another free seven), second seven uses V6,
and subsequent keep n uses V[n-1]. This accounts for the free mulligan.

Known limitation: U_n itself comes from the inherited approximate T2/T3
continuation estimator, not a fully corrected Realistic Beam rollout. The
calibration is self-consistent within that estimator, not proven optimal.
"""
from __future__ import annotations
import argparse,hashlib,json,random,time,gzip
from pathlib import Path
import dack_v11_pre_reveal_barrier_20261020 as v11
v2=v11.v2;root=v11.root;d=v11.d;m=v11.m
batch=v11.v10.root.batch
SEED=915324116

def sample_one(variant,seat_class,keep_n,index):
    root.install(variant)
    seat=0 if seat_class=="first" else 2
    material=f"{SEED}|calibrate|{variant}|{seat_class}|{keep_n}|{index}"
    seed=int.from_bytes(hashlib.sha256(material.encode()).digest()[:8],"big")
    rng=random.Random(seed)
    cards=list(d.DECK)
    rng.shuffle(cards)
    seven,rest=cards[:7],cards[7:]
    m.set_trial_seed(seed)
    raw,ev,struct,hand,bottom,unknown,_,refined=\
       batch.evaluate_keep(seven,keep_n,rest,seat)
    assert len(hand)==keep_n and len(bottom)==7-keep_n
    assert sorted(tuple(hand)+tuple(bottom))==sorted(seven)
    assert sorted(tuple(unknown)+tuple(bottom)+tuple(hand))==sorted(d.DECK)
    return {"sample":index,"utility":round(float(raw),7),
            "le2":round(float(ev["le2"]),7),
            "t3_exact":round(float(ev["t3"]),7),
            "refined":bool(refined),
            "hand":list(hand),"bottom":list(bottom)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--variant",choices=("current","buck_worldmap"),required=True)
    p.add_argument("--seat-class",choices=("first","later"),required=True)
    p.add_argument("--keep-n",type=int,choices=range(1,8),required=True)
    p.add_argument("--samples",type=int,default=24)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    assert a.samples>=8
    v11.audit()
    root.install(a.variant)
    records=[];start=time.time()
    for i in range(a.samples):
        v=sample_one(a.variant,a.seat_class,a.keep_n,i)
        records.append(v)
        if (i+1)%8==0:
            print("LONDON_CALIBRATION_SAMPLES",a.variant,a.seat_class,
                  a.keep_n,i+1,flush=True)
    doc={"schema":"dack_v12_london_calibration_samples",
         "variant":a.variant,"seat_class":a.seat_class,
         "keep_n":a.keep_n,"n":a.samples,
         "engine":"v10 blind-library sampled bottom EV, λ=.5",
         "deck_sha256":hashlib.sha256("\n".join(v2.trial.VARIANTS[a.variant]).encode()).hexdigest(),
         "elapsed":round(time.time()-start,2),
         "samples":records}
    Path(a.out).write_text(json.dumps(doc,indent=2)+"\n")
    print("DACK_V12_INDEPENDENT_MULLIGAN_SAMPLE_PASS",
          a.variant,a.seat_class,a.keep_n,a.samples,flush=True)
if __name__=="__main__":main()
