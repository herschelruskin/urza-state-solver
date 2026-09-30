#!/usr/bin/env python3
import argparse, json, os
import dack_v075_current99 as old
import dack_current99_batch as b

BASE_DECK=tuple(old.CURRENT_DECK)

def utility(t):
    return 1.0 if t in (1,2) else 0.5 if t==3 else 0.0

def run_variant(game_id,fixed):
    # Restore old classification, then optionally apply Pearl fix.
    import importlib
    # The v0.75 wrapper recognizes Implements/Mind Stone and delegates to the
    # v0.73 wrapper, which omits Pearl.  Save a stable old classifier once.
    return None

# Capture old classifier before importing fix.
OLD_ARTIFACT=b.d.is_artifact_perm
import dack_v076_pearl_artifact_fix as fix
FIXED_ARTIFACT=b.d.is_artifact_perm

def simulate(game_id,classifier):
    b.d.is_artifact_perm=classifier
    b.d.DECK=list(BASE_DECK)
    b.v.clear_caches()
    return b.simulate_game(game_id)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--start",type=int,required=True)
    ap.add_argument("--games",type=int,default=4)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    assert fix.selftest()
    rows=[]
    for gid in range(a.start,a.start+a.games):
        oldr=simulate(gid,OLD_ARTIFACT)
        newr=simulate(gid,FIXED_ARTIFACT)
        rows.append({
          "game_id":gid,
          "old":{"win_turn":oldr["win_turn"],"keep_n":oldr["keep_n"],"utility":utility(oldr["win_turn"])},
          "fixed":{"win_turn":newr["win_turn"],"keep_n":newr["keep_n"],"utility":utility(newr["win_turn"])},
        })
        print(json.dumps({"game_id":gid,"old":oldr["win_turn"],"fixed":newr["win_turn"]}),flush=True)
    b.d.is_artifact_perm=FIXED_ARTIFACT
    os.makedirs(os.path.dirname(a.out) or ".",exist_ok=True)
    json.dump({"test":"pearl_artifact_identity_paired","start":a.start,"games":a.games,"rows":rows},open(a.out,"w"),indent=2)

if __name__=="__main__":
    main()
