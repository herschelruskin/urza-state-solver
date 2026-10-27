#!/usr/bin/env python3
"""Evidence-grounded Dack ramp-piece leaderboard under Assertive mulligans.

Consumes verified complete reports AND raw paired rows of either/both frozen
Assertive screening runs. Derives legal one-for-one replacements between any
two arm decks from variant 'in'/'out' multiset differences. Measures T1/T2/T3
paired differences and exact weighted score, with within-screen CIs. Scores
individual cards only from such matched single-card contrasts. Multi-swap
packages are tracked, never causally assigned to each ingredient.

Screens are exploratory, multiple correlated contrasts; leaderboard tiers
are provisional until independent confirmatory replication. Baseline core
cards that never varied are NOT_TESTED, never mislabelled "worst".
"""
from __future__ import annotations
import argparse, collections, csv, gzip, json, math, statistics
from pathlib import Path

MANIFEST="dack_assertive_ramp_tracker_manifest.json"
ANCHORS=("current","full_prism_voltaic_boulder","full_preserve_mantle",
         "full_basalt_over_boulder","full_double_keys")
RAMP_ROLES={"core_mana","core_land","ramp_flex","untapper","tutor_flex",
            "land","rainbow_land","combo_flex"}

def read_json(p):
    path=Path(p)
    with (gzip.open(path,"rt",encoding="utf8") if path.suffix==".gz" else path.open("rt",encoding="utf8")) as f:
        return json.load(f)

def summaries(manifest, args):
    provided={"core20":(args.core20_report,args.core20_raw),
              "flex41":(args.flex41_report,args.flex41_raw)}
    result=[]
    for meta in manifest["input_suites"]:
        name=meta["id"]
        sr,raw=provided[name]
        if not sr and not raw:continue
        if not sr or not raw:raise ValueError(f"{name}: must provide BOTH verified summary and raw")
        result.append((meta,read_json(sr),read_json(raw)))
    return result

def reconstruct_card_decks(summary,baseline):
    base=collections.Counter(baseline)
    decks={}
    for name,info in summary["arms"].items():
        x=base-collections.Counter(info["out"])
        # Validate every removed card really was present, including multiples.
        for card,needed in collections.Counter(info["out"]).items():
            assert base[card]>=needed,(name,card,"invalid removal")
        x+=collections.Counter(info["in"])
        assert sum(x.values())==99,(name,sum(x.values()))
        decks[name]=x
    assert decks["current"]==base,"current is not the frozen 99"
    return decks

def assert_source(meta,report,raw):
    assert report["status"]=="PASS",meta["id"]
    assert report["policy"]==raw.get("policy",report["policy"])=="assertive"
    assert report["validated_n"]==meta["n"]
    assert report["missing_count"]==0 and report["shards_found"]==meta["n"]//(4 if meta["id"]=="core20" else 2)
    assert len(report["arms"])==meta["arms"]
    assert raw["seed_base"]==report["seed_base"]
    assert raw["schema"]==report["schema"]
    assert len(raw["rows"])==meta["n"]
    expected_hash=report.get("deck_hashes",report.get("hashes"))
    assert expected_hash==raw.get("deck_hashes",raw.get("hashes"))
    assert len(expected_hash)==meta["arms"]
    seen=set()
    for row in raw["rows"]:
        gid=row["gid"]
        assert gid not in seen and 0<=gid<meta["n"],(meta["id"],gid)
        seen.add(gid)
        assert set(row["arms"])==set(report["arms"]),gid
        assert len({rec["seat"] for rec in row["arms"].values()})==1
        for k,rec in row["arms"].items():
            assert rec["seed"]==report["seed_base"]+gid*1000003
            assert rec["turn"] in (0,1,2,3)
    assert len(seen)==meta["n"]
    for k,info in report["arms"].items():
        c=collections.Counter(row["arms"][k]["turn"] for row in raw["rows"])
        assert all(info["counts"][str(i)]==c[i] for i in range(4)),(meta["id"],k)
    return expected_hash

def utility(turn):
    return 0.0 if turn==0 else (0.5 if turn==3 else 1.0)

def metric(t,turn):
    return 1 if 0<turn<=t else 0

def stat(diffs):
    n=len(diffs)
    avg=sum(diffs)/n
    se=math.sqrt(sum((d-avg)**2 for d in diffs)/(n*(n-1))) if n>1 else 0
    return {"delta_pp":round(100*avg,4),
            "ci_low_pp":round(100*(avg-1.96*se),4),
            "ci_high_pp":round(100*(avg+1.96*se),4),
            "gains":sum(x>0 for x in diffs),
            "losses":sum(x<0 for x in diffs)}

def make_pairs(meta,report,raw,decks):
    names=sorted(decks,key=lambda s:(ANCHORS.index(s) if s in ANCHORS else len(ANCHORS),s))
    rows=sorted(raw["rows"],key=lambda row:row["gid"])
    output=[]
    for i,before in enumerate(names):
        for after in names[i+1:]:
            out=decks[before]-decks[after]
            new=decks[after]-decks[before]
            if sum(out.values())!=1 or sum(new.values())!=1:continue
            removed=next(iter(out))
            added=next(iter(new))
            assert removed!=added
            trials=[]
            for t in (1,2,3):
                vals=[metric(t,row["arms"][after]["turn"])-metric(t,row["arms"][before]["turn"]) for row in rows]
                trials.append(stat(vals))
            w=stat([utility(row["arms"][after]["turn"])-utility(row["arms"][before]["turn"]) for row in rows])
            output.append({"suite":meta["id"],"n":len(rows),
                           "from":before,"to":after,"removed":removed,"added":added,
                           "T1":trials[0],"T2":trials[1],"T3":trials[2],
                           "weighted":w,
                           "from_T2_pct":report["arms"][before]["T2_pct"],
                           "to_T2_pct":report["arms"][after]["T2_pct"]})
    return output

def card_ranking(manifest,comparisons):
    result=[]
    tracked=manifest["tracked_cards"]
    for item in tracked:
        name=item["card"]
        exposures=[]
        for pair in comparisons:
            sign=(1 if pair["added"]==name else -1 if pair["removed"]==name else 0)
            if not sign:continue
            def switched(m):
                s=pair[m]
                return {"delta_pp":round(s["delta_pp"]*sign,4),
                        "low_pp":s["ci_low_pp"] if sign>0 else round(-s["ci_high_pp"],4),
                        "high_pp":s["ci_high_pp"] if sign>0 else round(-s["ci_low_pp"],4)}
            exposures.append({"suite":pair["suite"],"from":pair["from"],"to":pair["to"],
                              "against":pair["removed"] if sign>0 else pair["added"],
                              "n":pair["n"],"T1":switched("T1"),"T2":switched("T2"),
                              "T3":switched("T3"),"weighted":switched("weighted")})
        t2=[x["T2"]["delta_pp"] for x in exposures]
        t1=[x["T1"]["delta_pp"] for x in exposures]
        t3=[x["T3"]["delta_pp"] for x in exposures]
        if not t2: status="NOT_TESTED"
        elif min(t2)>0:status="CONSISTENTLY_POSITIVE_DIRECTION"
        elif max(t2)<0:status="CONSISTENTLY_NEGATIVE_DIRECTION"
        else:status="MIXED_OR_ZERO"
        if exposures:
            med=statistics.median(t2)
            data={"median_T2_delta_pp":round(med,4),
                  "min_T2_delta_pp":min(t2),"max_T2_delta_pp":max(t2),
                  "median_T1_delta_pp":round(statistics.median(t1),4),
                  "median_T3_delta_pp":round(statistics.median(t3),4),
                  "ci_excludes_zero_positive":sum(x["T2"]["low_pp"]>0 for x in exposures),
                  "ci_excludes_zero_negative":sum(x["T2"]["high_pp"]<0 for x in exposures),
                  "direct_contexts":len(exposures),
                  "suites":sorted(set(x["suite"] for x in exposures))}
        else:
            data={"median_T2_delta_pp":None,"min_T2_delta_pp":None,
                  "max_T2_delta_pp":None,"median_T1_delta_pp":None,
                  "median_T3_delta_pp":None,
                  "ci_excludes_zero_positive":0,"ci_excludes_zero_negative":0,
                  "direct_contexts":0,"suites":[]}
        result.append({**item,"status":status,**data,"evidence":exposures})
    return sorted(result,key=lambda x:(x["median_T2_delta_pp"] is None,
           -(x["median_T2_delta_pp"] if x["median_T2_delta_pp"] is not None else -999),
            -x["direct_contexts"],x["card"]))

def fmt(v):
    return "—" if v is None else f"{v:+.2f}"

def markdown(report):
    manifest=report["manifest"]
    done=report["sources"]
    out=["# Dack Assertive — Ramp and Flex-Slot Evidence Tracker","",
      f"**Status:** {report['status']}. **Objective:** fastest T1/T2 Dack cast, secondary T3 reliability. "
      "This is an *optimistic goldfish cast proxy*, not confirmed full-combo or multiplayer win rate.","",
      "## Sources",""]
    for s in manifest["input_suites"]:
        mark="COMPLETE" if s["id"] in done else "AWAITING VERIFIED POOL"
        out.append(f"- **{s['id']}** — {s['arms']} deck variants, {s['n']} paired seeds; "
                   f"{mark}; [GitHub run](https://github.com/herschelruskin/urza-state-solver/actions/runs/{s['run_id']})")
    out+=["","## Direct-swap card leaderboard (conditional effects)","",
           "A card appears here only when there is a controlled comparison where one card replaces exactly one other card. "
           "A positive number means the card improved **T2** relative to its stated replacement in those contexts. "
           "Effects from different contexts reuse games and **must not be treated as independent**. "
           "The median is a descriptive sorting key, not a causal global value or valid pooled confidence interval.","",
           "| Card | Class | Matched contexts | Median ΔT2 (pp) | Range (pp) | Direction |",
           "|---|---|---:|---:|---:|---|"]
    for c in report["cards"]:
        r="—" if c["direct_contexts"]==0 else f"{fmt(c['min_T2_delta_pp'])} to {fmt(c['max_T2_delta_pp'])}"
        out.append(f"| {c['card']} | {c['role']} | {c['direct_contexts']} | "
                   f"{fmt(c['median_T2_delta_pp'])} | {r} | {c['status']} |")
    out+=["","## Strongest one-card replacement results (exploratory)",""]
    pairs=sorted(report["direct_pairs"],key=lambda r:r["T2"]["delta_pp"],reverse=True)
    out+=["| Test | Swap | Δ by T2 (pp) | Paired 95% CI (pp) | Δ by T3 (pp) |",
           "|---|---|---:|---:|---:|"]
    for p in pairs[:12]+list(reversed(pairs[-8:])):
        effect=p["T2"]
        out.append(f"| {p['suite']}: {p['from']} → {p['to']} | "
                   f"{p['removed']} → {p['added']} | {fmt(effect['delta_pp'])} | "
                   f"{fmt(effect['ci_low_pp'])} to {fmt(effect['ci_high_pp'])} | "
                   f"{fmt(p['T3']['delta_pp'])} |")
    if not pairs:out.append("| No complete screen data yet | — | — | — | — |")
    out+=["","## Interpretation / safeguards","",
       "- **NOT_TESTED does not mean bad.** It usually means the piece was held constant. Sol Ring, Mana Vault, LED and similar essentials aren't ranked from deck-level correlations.",
       "- **A card's value depends on the replaced slot and neighbors.** Pentad Prism with rainbow lands can differ from Prism in a white-heavy list.",
       "- **Lunarch Mantle and World Map are not fungible ramp only.** A cast-only test does not price downstream Boonweaver combo functionality, tutoring, or protection.",
       "- **Multiple testing warning:** dozens of overlapping contrasts at n=128/256 are discovery signals, not proof; shortlist top few and confirm on fresh n≥1,024 paired seeds.",
       "- **Do not merge seeds across suites as if they were paired.** Each 20- or 41-arm run has its own matched-randomness comparison space.",""]
    return "\n".join(out)+"\n"

def write_csv(path,headers,rows):
    with Path(path).open("w",newline="",encoding="utf8") as f:
        w=csv.DictWriter(f,fieldnames=headers,extrasaction="ignore")
        w.writeheader()
        for row in rows:w.writerow(row)

def main(args):
    manifest=read_json(args.manifest)
    assert manifest["schema"]=="dack_assertive_ramp_piece_tracking_v1"
    inputs=summaries(manifest,args)
    sources={}
    pairs=[]
    deckbase=None
    if inputs:
        # Identical frozen exact-99 provenance with complete case-sensitive card names.
        import dack_active_mulligan_policy as sim
        deckbase=sim.FROZEN_DECK
    for meta,rep,raw in inputs:
        assert_source(meta,rep,raw)
        decks=reconstruct_card_decks(rep,deckbase)
        pairs.extend(make_pairs(meta,rep,raw,decks))
        sources[meta["id"]]={"n":meta["n"],"arms":meta["arms"],
                              "one_card_contrasts":len([p for p in pairs if p["suite"]==meta["id"]]),
                              "seed_base":rep["seed_base"],"policy":rep["policy"]}
    cardrows=card_ranking(manifest,pairs)
    status="COMPLETE_TWO_SCREENS" if len(sources)==2 else "ONE_SCREEN_COMPLETE" if sources else "AWAITING_SCREEN_RESULTS"
    summary={"schema":"dack_assertive_ramp_piece_ranking_v1","status":status,
             "manifest":manifest,"sources":sources,"direct_pairs":pairs,"cards":cardrows,
             "note":"Cards ordered by descriptive median signed T2 effect across overlapping one-card replacements, NOT a causal global strength ranking; independent held-out confirmation needed."}
    dest=Path(args.outdir);dest.mkdir(parents=True,exist_ok=True)
    (dest/"ramp_piece_leaderboard.json").write_text(json.dumps(summary,indent=2)+"\n")
    (dest/"ramp_piece_leaderboard.md").write_text(markdown(summary))
    simple=[]
    for c in cardrows:
        simple.append({k:v for k,v in c.items() if k!="evidence"})
    write_csv(dest/"ramp_piece_leaderboard.csv",
       ["card","role","status","direct_contexts","median_T2_delta_pp",
        "min_T2_delta_pp","max_T2_delta_pp","median_T1_delta_pp",
        "median_T3_delta_pp","ci_excludes_zero_positive",
        "ci_excludes_zero_negative","notes"],simple)
    flattened=[]
    for p in pairs:
        row={k:p[k] for k in ("suite","n","from","to","removed","added")}
        for t in ("T1","T2","T3","weighted"):
            for m in ("delta_pp","ci_low_pp","ci_high_pp","gains","losses"):
                row[f"{t}_{m}"]=p[t][m]
        flattened.append(row)
    fields=list(flattened[0]) if flattened else (
        ["suite","n","from","to","removed","added"]+
        [f"{t}_{m}" for t in ("T1","T2","T3","weighted") for m in ("delta_pp","ci_low_pp","ci_high_pp","gains","losses")])
    write_csv(dest/"one_card_matched_swaps.csv",fields,flattened)
    print("RAMP_LEADERBOARD",status,
          "sources",list(sources),"direct_swaps",len(pairs),
          "cards_with_evidence",sum(c["direct_contexts"]>0 for c in cardrows),
          "top5",[(c["card"],c["median_T2_delta_pp"],c["direct_contexts"])
                  for c in cardrows if c["direct_contexts"]][:5],
          flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest",default=MANIFEST)
    ap.add_argument("--outdir",default="ramp_leaderboard")
    ap.add_argument("--core20-report")
    ap.add_argument("--core20-raw")
    ap.add_argument("--flex41-report")
    ap.add_argument("--flex41-raw")
    main(ap.parse_args())
