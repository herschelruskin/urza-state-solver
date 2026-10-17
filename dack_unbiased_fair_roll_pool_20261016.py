#!/usr/bin/env python3
"""Pool outcome-blind d4 and T1-boundary nonclairvoyance sensitivity experiment."""
import argparse,glob,gzip,json,math
from collections import Counter
from pathlib import Path

BUCK_SHA="f130ff4c9c0fbc888525070877fe820caba03e836e0be66ec60ea3410e950068"
CURRENT_SHA="3a10a02e1aae070645129fa85ed94240f1ae9d5447e3711f7621f92064d9f129"
MODES=("control_current","fair_d4","strict_current","strict_buck")
HASHES={"control_current":CURRENT_SHA,"strict_current":CURRENT_SHA,
        "fair_d4":BUCK_SHA,"strict_buck":BUCK_SHA}
SEED_BASE=7604096001

def load(mode,dir_path,n,beam):
    files=sorted(glob.glob(f"{dir_path}/**/{mode}_shard_*.json.gz",recursive=True))
    assert files,(mode,"missing artifacts")
    out={}
    for path in files:
        with gzip.open(path,"rt") as f:q=json.load(f)
        assert q["schema"]=="dack_unbiased_v1"
        assert q["mode"]==mode and q["deck_sha256"]==HASHES[mode]
        assert q["beam"]==beam and q["seed_base"]==SEED_BASE
        assert len(q["rows"])==q["games"]
        for i,row in enumerate(q["rows"]):
            gid=int(row["game_id"])
            assert gid==q["shard"]*q["games"]+i
            assert 0<=row["win_T2"]<=1 and 0<=row["expected_prob_T2"]<=1
            assert gid not in out,(mode,gid,"duplicate")
            out[gid]=row
    assert set(out)==set(range(n)),(mode,"missing IDs",len(out),n)
    return out,len(files)

def paired(a,b):
    assert set(a)==set(b)
    ids=sorted(a)
    n=len(ids)
    vals=[a[i]["win_T2"]-b[i]["win_T2"] for i in ids]
    mean=sum(vals)/n
    se=math.sqrt(sum((x-mean)**2 for x in vals)/(n-1)/n)
    wins=sum(x>0 for x in vals);loses=sum(x<0 for x in vals)
    dis=wins+loses
    pmcn=min(1.,2*sum(math.comb(dis,j) for j in range(min(wins,loses)+1))/(2**dis)) if dis else 1.
    return {"delta_pp":round(100*mean,4),
            "paired_normal_95pct_pp":[round(100*(mean-1.96*se),3),
                                       round(100*(mean+1.96*se),3)],
            "buck_only":wins,"current_only":loses,
            "discordant":dis,"mcnemar_exact_two_sided_p":round(pmcn,8)}

def aggregate(rows):
    n=len(rows)
    wins=sum(q["win_T2"] for q in rows.values())
    nroll=sum(q["rolled"] is not None for q in rows.values())
    rolls=Counter(q["rolled"] for q in rows.values() if q["rolled"] is not None)
    return {"n":n,"T2_count":wins,"T2_pct":round(100*wins/n,4),
            "mean_keep":round(sum(q["keep_n"] for q in rows.values())/n,4),
            "Purse_commitment_games":nroll,
            "d4_distribution_when_committed":{str(i):rolls[i] for i in (1,2,3,4)},
            "mean_precommit_expected_T2_pct":round(100*sum(q["expected_prob_T2"] for q in rows.values())/n,4),
            "mean_pre_roll_choices_evaluated":round(sum(q["choices_evaluated"] for q in rows.values())/n,4)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dir",default="shards")
    ap.add_argument("--games",type=int,default=512)
    ap.add_argument("--beam",type=int,default=120)
    ap.add_argument("--out",default="dack_unbiased_fair_roll_pooled_20261016.json")
    a=ap.parse_args()
    variants={}
    for mode in MODES:
        rows,files=load(mode,a.dir,a.games,a.beam)
        variants[mode]={"summary":aggregate(rows),"shards":files,
                        "deck_sha256":HASHES[mode],"rows":rows}
    out={
        "status":"PASS",
        "n_per_arm":a.games,"beam":a.beam,
        "design":"Matched-seed World Map versus Bucknard trial, independently sampled d4 with commitment before revealing die, plus restricted T1-pass no-future-draw sensitivity",
        "variants":{name:{k:v for k,v in entry.items() if k!="rows"} for name,entry in variants.items()},
        "paired":{
            "blind_d4_vs_current":paired(variants["fair_d4"]["rows"],variants["control_current"]["rows"]),
            "strict_buck_vs_strict_current":paired(variants["strict_buck"]["rows"],variants["strict_current"]["rows"]),
            "blind_d4_vs_strict_buck":paired(variants["fair_d4"]["rows"],variants["strict_buck"]["rows"]),
            "current_multi_frontier_vs_strict_current":paired(variants["control_current"]["rows"],variants["strict_current"]["rows"])},
        "integrity":{
            "fair_d4_rolled_count":variants["fair_d4"]["summary"]["Purse_commitment_games"],
            "shuffles_game_seeded_not_global_multiset_seed":True,
            "known_random_cards_absent":["Component Pouch"],
            "deck_hashes_verified":True},
        "limits":[
            "Goldfish Dack-cast proxy, not interactive win probability",
            "Search still has access to sampled library ordering during in-turn card-selection and tutor/draw action comparisons",
            "Fair d4 candidate solver uses top 8 per turn and beam 120 rather than exhaustive optimal policy",
            "Strict comparison commits one heuristic-best T1 pass line before T2 draw; deliberately conservative",
            "Strict comparison suppresses T1 Bucknard activation; do not equate its absolute percentages with optimum",
            "One d4 sampled per committed Bucknard activation, not after pre-roll beam selection",
            "Game-seeded shuffle is independent across games but repeated same-multiset shuffles in same game use same order",
            "Mulligans evaluated using neutral die and inherited provisional continuation thresholds",
            "Monte Carlo uncertainty remains, particularly if few games use Bucknard"
        ]}
    Path(a.out).write_text(json.dumps(out,indent=2)+"\n")
    print("DACK_UNBIASED_FAIR_ROLL_POOL_PASS",json.dumps(out),flush=True)

if __name__=="__main__":main()
