#!/usr/bin/env python3
"""Pool exact N=4096 DACK shards and emit win/mulligan/card-appearance analytics."""
import argparse, csv, glob, json, math
from collections import Counter, defaultdict
import dack_v076_current99_20261002 as v

d=v.d

def wilson(k,n,z=1.959963984540054):
    if not n: return [0.0,0.0]
    p=k/n
    den=1+z*z/n
    ctr=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [ctr-half,ctr+half]

def pct(x): return 100.0*x

def rate_block(k,n):
    return {"count":int(k),"n":int(n),"rate":k/n if n else None,"pct":pct(k/n) if n else None,
            "ci95":wilson(k,n) if n else None}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--glob",required=True)
    ap.add_argument("--expected-games",type=int,default=4096)
    ap.add_argument("--json-out",required=True)
    ap.add_argument("--games-csv",required=True)
    ap.add_argument("--cards-csv",required=True)
    ap.add_argument("--mulligan-csv",required=True)
    a=ap.parse_args()

    files=sorted(glob.glob(a.glob))
    if not files:
        raise SystemExit("no shards found")

    rows=[]; sig=None; shard_times=[]
    seen_ids=set()
    for fp in files:
        with open(fp,encoding="utf-8") as f:
            p=json.load(f)
        if sig is None: sig=p["compatibility_signature"]
        if p["compatibility_signature"]!=sig:
            raise SystemExit(f"incompatible shard: {fp}")
        shard_times.append(float(p.get("elapsed_seconds",0.0)))
        for r in p["rows"]:
            gid=int(r["game_id"])
            if gid in seen_ids:
                raise SystemExit(f"duplicate game_id {gid}")
            seen_ids.add(gid); rows.append(r)
    rows.sort(key=lambda r:int(r["game_id"]))
    n=len(rows)
    if n!=a.expected_games:
        raise SystemExit(f"expected {a.expected_games} games, got {n}")

    c=Counter(int(r["win_turn"]) for r in rows)
    t1=c[1]; t2=c[2]; t3=c[3]; fail=c[0]
    le2=t1+t2; le3=t1+t2+t3

    keep_counts=Counter(int(r["keep_n"]) for r in rows)
    seat_counts=Counter(int(r["seat"]) for r in rows)
    mean_keep=sum(int(r["keep_n"]) for r in rows)/n
    sorted_keeps=sorted(int(r["keep_n"]) for r in rows)
    median_keep=(sorted_keeps[(n-1)//2]+sorted_keeps[n//2])/2

    # Exact outcome by London keep size.
    mulligan_strata=[]
    for k in range(7,0,-1):
        rr=[r for r in rows if int(r["keep_n"])==k]
        nk=len(rr)
        cc=Counter(int(r["win_turn"]) for r in rr)
        mulligan_strata.append({
            "keep_n":k,"mulligans":7-k,"n":nk,"share":nk/n,
            "T1":cc[1]/nk if nk else None,
            "T2_exact":cc[2]/nk if nk else None,
            "le_T2":(cc[1]+cc[2])/nk if nk else None,
            "T3_exact":cc[3]/nk if nk else None,
            "le_T3":(cc[1]+cc[2]+cc[3])/nk if nk else None,
            "fail_T3":cc[0]/nk if nk else None,
        })

    # Seat strata (useful check that actual-seat-before-mulligans is functioning).
    seat_strata=[]
    for seat in range(4):
        rr=[r for r in rows if int(r["seat"])==seat]
        ns=len(rr); cc=Counter(int(r["win_turn"]) for r in rr)
        seat_strata.append({
            "seat":seat,"n":ns,
            "T1":cc[1]/ns if ns else None,
            "le_T2":(cc[1]+cc[2])/ns if ns else None,
            "le_T3":(cc[1]+cc[2]+cc[3])/ns if ns else None,
        })

    # Kept-hand card appearance analytics. This is associative, not a causal ablation estimate.
    deck_counts=Counter(d.DECK)
    card_stats=[]
    global_le3=le3/n
    for card in sorted(deck_counts):
        present_all=present_wins=copy_all=copy_wins=0
        exact_present={1:0,2:0,3:0}
        exact_copy={1:0,2:0,3:0}
        le2_present=0
        for r in rows:
            hc=Counter(r["kept_hand"])
            copies=hc.get(card,0)
            if not copies: continue
            present_all+=1; copy_all+=copies
            wt=int(r["win_turn"])
            if wt>0:
                present_wins+=1; copy_wins+=copies
            if wt in (1,2,3):
                exact_present[wt]+=1; exact_copy[wt]+=copies
            if wt in (1,2): le2_present+=1
        wr=(present_wins/present_all) if present_all else None
        card_stats.append({
            "card":card,
            "copies_in_deck":deck_counts[card],
            "kept_game_presence_all":present_all,
            "kept_copy_appearances_all":copy_all,
            "winning_kept_game_presence":present_wins,
            "winning_kept_copy_appearances":copy_wins,
            "T1_winning_hand_presence":exact_present[1],
            "T2_winning_hand_presence":exact_present[2],
            "T3_winning_hand_presence":exact_present[3],
            "T1_winning_copy_appearances":exact_copy[1],
            "T2_winning_copy_appearances":exact_copy[2],
            "T3_winning_copy_appearances":exact_copy[3],
            "le_T2_when_kept":le2_present/present_all if present_all else None,
            "le_T3_when_kept":wr,
            "le_T3_lift_pp_vs_global":(wr-global_le3)*100 if wr is not None else None,
            "win_presence_share_of_all_wins":present_wins/le3 if le3 else None,
        })

    # Raw user-requested ranking: number of appearances in winning kept hands.
    raw_rank=sorted(card_stats,key=lambda x:(x["winning_kept_copy_appearances"],
                                             x["winning_kept_game_presence"]),reverse=True)
    for i,x in enumerate(raw_rank,1): x["raw_win_appearance_rank"]=i

    # Normalized best/worst: only cards seen in >=100 final kept hands to suppress tiny denominators.
    stable=[x for x in card_stats if x["kept_game_presence_all"]>=100]
    norm_rank=sorted(stable,key=lambda x:x["le_T3_when_kept"],reverse=True)
    for i,x in enumerate(norm_rank,1): x["normalized_le_T3_rank"]=i
    rank_by_card={x["card"]:x.get("raw_win_appearance_rank") for x in raw_rank}
    norm_by_card={x["card"]:x.get("normalized_le_T3_rank") for x in norm_rank}
    for x in card_stats:
        x["raw_win_appearance_rank"]=rank_by_card.get(x["card"])
        x["normalized_le_T3_rank"]=norm_by_card.get(x["card"])

    summary={
        "compatibility_signature":sig,
        "n":n,
        "shards":len(files),
        "summary":{
            "T1":rate_block(t1,n),
            "T2_exact":rate_block(t2,n),
            "le_T2":rate_block(le2,n),
            "T3_exact":rate_block(t3,n),
            "le_T3":rate_block(le3,n),
            "fail_T3":rate_block(fail,n),
        },
        "utility_lambda_0_5":(le2+0.5*t3)/n,
        "mulligans":{
            "mean_keep":mean_keep,
            "median_keep":median_keep,
            "keep_counts":{str(k):keep_counts[k] for k in range(7,0,-1)},
            "keep_percent":{str(k):100*keep_counts[k]/n for k in range(7,0,-1)},
            "strata":mulligan_strata,
        },
        "seat_counts":{str(k):seat_counts[k] for k in range(4)},
        "seat_strata":seat_strata,
        "card_analytics":{
            "definition":"Appearances are in the final London kept hand after bottoming. Raw winning appearances answer frequency; normalized le_T3_when_kept is associative and is not a card-ablation causal effect.",
            "stable_normalized_min_kept_presence":100,
            "raw_top_20":[{
                "card":x["card"],
                "winning_kept_copy_appearances":x["winning_kept_copy_appearances"],
                "winning_kept_game_presence":x["winning_kept_game_presence"],
                "kept_game_presence_all":x["kept_game_presence_all"],
                "le_T3_when_kept":x["le_T3_when_kept"],
                "lift_pp":x["le_T3_lift_pp_vs_global"],
            } for x in raw_rank[:20]],
            "normalized_best_15":[{
                "card":x["card"],"kept_n":x["kept_game_presence_all"],
                "le_T3_when_kept":x["le_T3_when_kept"],
                "lift_pp":x["le_T3_lift_pp_vs_global"],
                "winning_presence":x["winning_kept_game_presence"],
            } for x in norm_rank[:15]],
            "normalized_worst_15":[{
                "card":x["card"],"kept_n":x["kept_game_presence_all"],
                "le_T3_when_kept":x["le_T3_when_kept"],
                "lift_pp":x["le_T3_lift_pp_vs_global"],
                "winning_presence":x["winning_kept_game_presence"],
            } for x in list(reversed(norm_rank))[:15]],
        },
        "runtime":{
            "sum_shard_seconds":sum(shard_times),
            "mean_shard_seconds":sum(shard_times)/len(shard_times),
            "max_shard_seconds":max(shard_times),
        },
    }

    with open(a.json_out,"w",encoding="utf-8") as f:
        json.dump(summary,f,indent=2)

    with open(a.games_csv,"w",newline="",encoding="utf-8") as f:
        fields=["game_id","seed","seat","keep_n","mulligans","keep_utility","win_turn",
                "kept_hand","bottomed_cards"]
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for r in rows:
            w.writerow({
                **{k:r[k] for k in fields if k not in {"kept_hand","bottomed_cards"}},
                "kept_hand":" | ".join(r["kept_hand"]),
                "bottomed_cards":" | ".join(r["bottomed_cards"]),
            })

    card_fields=[
        "raw_win_appearance_rank","normalized_le_T3_rank","card","copies_in_deck",
        "kept_game_presence_all","kept_copy_appearances_all",
        "winning_kept_game_presence","winning_kept_copy_appearances",
        "T1_winning_hand_presence","T2_winning_hand_presence","T3_winning_hand_presence",
        "T1_winning_copy_appearances","T2_winning_copy_appearances","T3_winning_copy_appearances",
        "le_T2_when_kept","le_T3_when_kept","le_T3_lift_pp_vs_global",
        "win_presence_share_of_all_wins"
    ]
    with open(a.cards_csv,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=card_fields); w.writeheader()
        w.writerows(sorted(card_stats,key=lambda x:x["raw_win_appearance_rank"]))

    with open(a.mulligan_csv,"w",newline="",encoding="utf-8") as f:
        fields=["keep_n","mulligans","n","share","T1","T2_exact","le_T2","T3_exact","le_T3","fail_T3"]
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(mulligan_strata)

    print(json.dumps({
        "status":"complete","games":n,"shards":len(files),
        "T1":t1/n,"le_T2":le2/n,"le_T3":le3/n,
        "mean_keep":mean_keep
    },indent=2))

if __name__=="__main__":
    main()
