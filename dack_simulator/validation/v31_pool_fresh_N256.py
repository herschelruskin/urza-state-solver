#!/usr/bin/env python3
"""Pool exactly N256 fresh 104k games and paired bootstrap, no tuning."""
from __future__ import annotations
import collections,gzip,glob,json,random,math
from pathlib import Path

POLICIES=("v27_frozen","v31_action_regret")
def mcnemar(g,l):
    n=g+l
    if not n:return 1.
    # Exact two-sided binomial null, including small discordance.
    p=2.*sum(math.comb(n,k) for k in range(min(g,l)+1))/2**n
    return min(1.,p)

def main():
    paths=sorted(glob.glob("collected/v31_104k_*.json.gz"))
    assert len(paths)==64,len(paths)
    rows=[];models=None
    for f in paths:
        with gzip.open(f,"rt") as fp:d=json.load(fp)
        assert d["schema"]=="dack_v31_prospective_104k_matched_v27_v31"
        assert d["status"]=="PASS"
        assert d["n_physical_games"]==4
        assert d["same_seat_and_initial_physical_seven"] and d["strict_gameplay_beam"]==160
        assert d["no_prospective_training"]
        assert tuple(d["policies"])==POLICIES
        if models is None:models=d["source_sha256"]
        assert models==d["source_sha256"]
        rows+=d["rows"]
    rows.sort(key=lambda x:x["game_id"])
    assert [x["game_id"] for x in rows]==list(range(104000,104256))
    metrics={}
    for p in POLICIES:
        x=[r[p] for r in rows]
        metrics[p]={
           "n":len(x),
           "T1":sum(z["turn"]==1 for z in x),
           "T2":sum(0<z["turn"]<=2 for z in x),
           "T3":sum(0<z["turn"]<=3 for z in x),
           "mean_keep_n":sum(z["keep_n"] for z in x)/len(x),
           "simulation_seconds":round(sum(z["seconds"] for z in x),4)
        }
    rng=random.Random(310410)
    paired={}
    for turn in (1,2,3):
        diffs=[
          int(0<r["v31_action_regret"]["turn"]<=turn)-
          int(0<r["v27_frozen"]["turn"]<=turn)
          for r in rows
        ]
        n=len(diffs)
        boot=sorted(sum(diffs[rng.randrange(n)] for _ in range(n))/n*100.
                    for _ in range(10000))
        gains=diffs.count(1);losses=diffs.count(-1)
        paired[f"T{turn}"]={
           "difference_pp":100.*sum(diffs)/n,
           "gains":gains,"losses":losses,
           "paired_bootstrap_95ci_pp":[boot[249],boot[9749]],
           "exploratory_exact_mcnemar_p":mcnemar(gains,losses)
        }
    changes=collections.Counter()
    examples=[]
    for row in rows:
        a=row["v27_frozen"];b=row["v31_action_regret"]
        ha=a["history"];hb=b["history"]
        assert ha[0]["seven_slots"]==hb[0]["seven_slots"]
        if a["keep_n"]!=b["keep_n"]:
            changes["different_final_keep_depth"]+=1
        elif collections.Counter(a["hand"] if "hand" in a else ha[-1]["hand"])!=collections.Counter(b["hand"] if "hand" in b else hb[-1]["hand"]):
            changes["same_depth_different_final_kept_hand"]+=1
        else:changes["same_final_hand"]+=1
        idx=next((i for i,(x,y) in enumerate(zip(ha,hb)) if x["kept"]!=y["kept"] or x["bottom"]!=y["bottom"]),None)
        if idx is not None:changes["some_London_decision_change"]+=1
        if idx is not None:
            examples.append({"game_id":row["game_id"],"first_change_stage":idx,
                             "v27_keep_n":a["keep_n"],"v31_keep_n":b["keep_n"],
                             "v27_win_turn":a["turn"],"v31_win_turn":b["turn"],
                             "v27_bottom":ha[idx]["bottom"],"v31_bottom":hb[idx]["bottom"]})
    # Goldfish full-game T2 is primary; never promote on N256 alone.
    report={
      "schema":"dack_v31_prospective_104k_N256_frozen_v27_vs_regret_student",
      "status":"PASS","n_independent_physical_game_ids":256,
      "physical_ids":[104000,104255],
      "primary_outcome":"cumulative Dack deployment by T2",
      "goldfish_not_multiplayer_winrate":True,
      "all_games_independent_of_103k_model_and_99k_bottoming_audit":True,
      "no_prospective_train_or_model_selection":True,
      "model_approved":False,
      "model_sha256":models,
      "metrics":metrics,"paired_v31_minus_v27":paired,
      "speed_ratio_v27_over_v31":metrics["v27_frozen"]["simulation_seconds"]/max(1e-9,metrics["v31_action_regret"]["simulation_seconds"]),
      "decision_changes":dict(changes),
      "changed_decision_examples":examples[:40],
      "limitation":"Student bottom selector unchanged; v31 modifies only frozen v27's keep threshold using actual 103k Q advantage, but N256 alone cannot establish equivalence. This is not multiplayer cEDH win probability."
    }
    out=Path("benchmark_results/v31_prospective_104k_N256.json")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("DACK_V31_PROSPECTIVE_N256_REPORT_PASS",json.dumps({
       "n":256,"metrics":metrics,"paired":paired,"changes":dict(changes),
       "model_approved":False
    },sort_keys=True),flush=True)

if __name__=="__main__":main()
