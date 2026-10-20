#!/usr/bin/env python3
"""Unbiased Gemstone Caverns pregame decision audit for Dack.

For each retained London hand (same game seeds and policy as Realistic v6),
enumerate EVERY legal pregame action BEFORE T1 draw. Compare inherited
static heuristic's pregame selection with a visible-information metric:
  * whether Gemstone is actually available in a non-starting seat
  * legal exile targets and loss of hand resources
  * bankable / white capacity after the pregame action
This is diagnostic, not a new winrate estimate or automatic policy fix.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,random
from collections import Counter
import dack_realistic_v6_stratified_reward_20261019 as v6
root=v6.root;d=v6.d;m=v6.m;fair=v6.fair;v2=v6.v2;v1=v6.v1

def game(variant,gid):
    root.install(variant)
    seed=v2.SEED_BASE+gid*1000003
    m.set_trial_seed(seed)
    rng=random.Random(seed)
    seat=rng.randrange(4)
    fair.overridden_roll(2)
    st,keep_n,_=root.choose_hand_with_free(rng,seat)
    candidates=d._pregame_states(st,seat)
    chosen,reported=fair.choose_pregame(st,seat)
    assert len(candidates)==reported and chosen in candidates
    return {"game_id":gid,"seat":seat,"keep_n":keep_n,
      "gemstone_in_kept_hand":"Gemstone Caverns" in st.hand,
      "pregame_options":len(candidates),
      "chosen_score":d.score(chosen),
      "static_chose_deploy":any(q.name=="Gemstone Caverns" for q in chosen.battlefield),
      "legal_exile_choices":[list(q.exile) for q in candidates if q.exile!=st.exile],
      "opening_hand":list(st.hand) if len(candidates)>1 else []}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--variant",choices=("current","buck_worldmap"),default="current")
    ap.add_argument("--shard",type=int,default=0)
    ap.add_argument("--games",type=int,default=12)
    ap.add_argument("--out",default="gemstone_pregame_audit.json.gz")
    a=ap.parse_args()
    assert a.shard>=0 and a.games>0
    v6.audit()
    rows=[]
    for j in range(a.games):
        gid=a.shard*a.games+j
        rows.append(game(a.variant,gid))
        print("GEMSTONE_PREGAME_GAME",a.variant,gid,
              rows[-1]["pregame_options"],flush=True)
    obj={"schema":"dack_gemstone_pregame_census","variant":a.variant,
       "shard":a.shard,"games":a.games,
       "seed_base":v2.SEED_BASE,
       "deck_sha256":hashlib.sha256("\n".join(v2.trial.VARIANTS[a.variant]).encode()).hexdigest(),
       "count_eligible":sum(q["pregame_options"]>1 for q in rows),
       "count_static_deploy":sum(q["static_chose_deploy"] for q in rows),
       "rows":rows}
    with gzip.open(a.out,"wt",encoding="utf8") as f:
        json.dump(obj,f,separators=(",",":"))
    print("GEMSTONE_PREGAME_CENSUS_PASS",a.variant,a.games,obj["count_eligible"],flush=True)
if __name__=="__main__":main()
