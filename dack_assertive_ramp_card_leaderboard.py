#!/usr/bin/env python3
"""Versioned Dack ramp-piece evidence ledger, Assertive policy.

--bootstrap creates a truthful pending-data inventory from the 20- and 41-arm
screens and the independently validated historical Standard-policy evidence.

--screen20-report / --screen20-raw and --flex41-report / --flex41-raw
incrementally add validated Assertive results without ever cross-comparing
different seeds, policies, decks, or non-matched trial arms.

Direct one-card substitutions are analyzed within a single paired trial.
The card 'screening signal' is the sample-size-weighted mean across observed
direct contrasts, NOT a causal marginal card effect or a confirmatory CI.
Repeated contrasts share arms/games; their point estimates are correlated.
Only new held-out trials can confirm speculative winners.
"""
from __future__ import annotations
import argparse, collections, gzip, json, math, statistics
from pathlib import Path

import dack_assertive_ramp_land_key_screen_n256_20261026 as screen20
import dack_assertive_flexslots_33to36_n128_20261026 as flex41
from dack_active_mulligan_policy import deck_hash

EVIDENCE_SCHEMA="dack_assertive_ramp_card_evidence_20261026_v1"
TRIALS=(
    {"name":"screen20","module":screen20,"n":256,
     "default_report":"benchmark_results/dack_assertive_ramp_land_key_screen_n256_report.json",
     "default_raw":"benchmark_results/dack_assertive_ramp_land_key_screen_n256_report.raw.json.gz",
     "source_run":"https://github.com/herschelruskin/urza-state-solver/actions/runs/40444150025"},
    {"name":"flex41","module":flex41,"n":128,
     "default_report":"benchmark_results/dack_assertive_flexslots_33to36_n128_report.json",
     "default_raw":"benchmark_results/dack_assertive_flexslots_33to36_n128_report.raw.json.gz",
     "source_run":"https://github.com/herschelruskin/urza-state-solver/actions/runs/40445020227"},
)
# Only these are presently being tested with one-for-one substitutions.
RAMP_ROLES={
    "Mana Vault":"fast positive-mana rock",
    "Sol Ring":"fast positive-mana rock",
    "Grim Monolith":"fast positive-mana rock",
    "Basalt Monolith":"three-mana rock / untap engine",
    "Lotus Petal":"burst mana",
    "Lion's Eye Diamond":"burst mana",
    "Mox Diamond":"fast colored mana",
    "Chrome Mox":"fast colored mana",
    "Mox Opal":"fast colored mana",
    "Jeweled Amulet":"slow mana storage",
    "Everflowing Chalice":"scalable ramp",
    "Coalition Relic":"slow fixing/charge ramp",
    "Arcane Signet":"colored ramp",
    "Fellwar Stone":"colored ramp",
    "Mind Stone":"two-mana rock",
    "The Mind Stone":"two-mana rock",
    "Tooth of Ramos":"three-mana storage artifact",
    "Implements of Sacrifice":"burst conversion",
    "Pentad Prism":"sunburst burst mana",
    "Giant's Boulder":"small artifact ramp",
    "Voltaic Key":"artifact untapper",
    "Manifold Key":"artifact untapper",
    "Candelabra of Tawnos":"land untapper",
    "Moonsilver Key":"mana-artifact tutor",
    "World Map":"land/tutor utility",
    "Lunarch Mantle":"combo sacrifice outlet / flex slot",
    "Hardlight Containment":"combo-affecting flex slot",
    "Plains":"basic land / slot baseline",
    "Command Tower":"white-only commander land",
    "Mana Confluence":"rainbow source",
    "City of Brass":"rainbow source",
    "Gemstone Mine":"rainbow source",
    "Ancient Tomb":"positive mana land",
    "City of Traitors":"positive mana land",
    "Crystal Vein":"burst land",
    "Mishra's Workshop":"artifact-only mana land",
    "Gemstone Caverns":"conditional acceleration",
}
MONITORED=set(RAMP_ROLES)
ANCHORS=("Sol Ring","Mana Vault","Grim Monolith","Lion's Eye Diamond",
         "Chrome Mox","Mox Diamond","Mox Opal","Lotus Petal","Ancient Tomb",
         "City of Traitors","Crystal Vein","Mishra's Workshop",
         "Moonsilver Key","Coalition Relic","Everflowing Chalice","Jeweled Amulet",
         "Arcane Signet","Fellwar Stone","Mind Stone","The Mind Stone",
         "Tooth of Ramos","Implements of Sacrifice","World Map")

def readgz(path):
    with gzip.open(path,"rt",encoding="utf8") as f:return json.load(f)

def load_trial(config,report_path,raw_path):
    if not report_path and not raw_path:return None
    assert report_path and raw_path, "provide both summary and raw evidence"
    summary=json.loads(Path(report_path).read_text())
    raw=readgz(raw_path)
    m=config["module"]
    assert summary["status"]=="PASS",summary.get("status")
    assert summary["validated_n"]==config["n"] and summary["missing_count"]==0
    assert summary["policy"]=="assertive"
    assert summary["beam"]==160
    assert raw["schema"]==summary["schema"]==m.SCHEMA
    assert raw["seed_base"]==summary["seed_base"]==m.SEED_BASE
    if config["name"]=="screen20":hashes=summary["deck_hashes"]
    else:hashes=summary["hashes"]
    assert hashes=={name:deck_hash(deck) for name,deck in m.VARIANTS.items()}
    rows=raw["rows"]
    assert len(rows)==config["n"]
    assert set(x["gid"] for x in rows)==set(range(config["n"]))
    assert len({x["gid"] for x in rows})==len(rows)
    rows=sorted(rows,key=lambda x:x["gid"])
    for r in rows:
        assert set(r["arms"])==set(m.VARIANTS)
        assert len({z["seed"] for z in r["arms"].values()})==1
        assert len({z["seat"] for z in r["arms"].values()})==1
        assert next(iter(r["arms"].values()))["seed"]==m.SEED_BASE+r["gid"]*1000003
    return {"config":config,"summary":summary,"rows":rows,"hashes":hashes}

def diff(a,b):
    ca,cb=collections.Counter(a),collections.Counter(b)
    removed=list((ca-cb).elements())
    added=list((cb-ca).elements())
    return removed,added

def one_slot_contrasts(trial):
    mod=trial["config"]["module"]
    rows=trial["rows"];n=len(rows)
    all_decks=mod.VARIANTS
    names=list(all_decks)
    records=[]
    for i,name_a in enumerate(names):
        for name_b in names[i+1:]:
            out,into=diff(all_decks[name_a],all_decks[name_b])
            if len(out)!=1 or len(into)!=1:continue
            old,new=out[0],into[0]
            if old not in MONITORED and new not in MONITORED:continue
            metrics={}
            for turn in (1,2,3):
                z=[int(0<r["arms"][name_b]["turn"]<=turn)-
                   int(0<r["arms"][name_a]["turn"]<=turn) for r in rows]
                mean=sum(z)/n
                se=math.sqrt(sum((x-mean)**2 for x in z)/(n*(n-1))) if n>1 else 0
                metrics[f"T{turn}"]={"delta_pp":round(100*mean,4),
                    "paired_95_ci_pp":[round(100*(mean-1.96*se),4),
                                       round(100*(mean+1.96*se),4)],
                    "improvements":z.count(1),"regressions":z.count(-1)}
            # One-for-one matched comparison, oriented 'new card' vs 'old card'.
            records.append({"trial":trial["config"]["name"],"n":n,
                "old_card":old,"new_card":new,
                "from_arm":name_a,"to_arm":name_b,
                "background_land_count_from":mod.nominal(all_decks[name_a]) if hasattr(mod,"nominal")
                   else sum(q in mod.sim.d.LANDS or q in ("Emeria's Call","Razorgrass Ambush") for q in all_decks[name_a]),
                "background_land_count_to":mod.nominal(all_decks[name_b]) if hasattr(mod,"nominal")
                   else sum(q in mod.sim.d.LANDS or q in ("Emeria's Call","Razorgrass Ambush") for q in all_decks[name_b]),
                "metrics":metrics})
    return records

def rank_cards(comparisons):
    grouped=collections.defaultdict(list)
    for c in comparisons:
        if c["old_card"] in MONITORED:
            grouped[c["old_card"]].append({"delta":-c["metrics"]["T2"]["delta_pp"],
                "n":c["n"],"comp":c,"direction":"old"})
        if c["new_card"] in MONITORED:
            grouped[c["new_card"]].append({"delta":c["metrics"]["T2"]["delta_pp"],
                "n":c["n"],"comp":c,"direction":"new"})
    ranked=[]
    for card,recs in grouped.items():
        # All scores are heuristics. Multiple comparisons within a given
        # trial share games and hands, so this is NOT a pooled independent CI.
        total=sum(v["n"] for v in recs)
        score=sum(v["delta"]*v["n"] for v in recs)/total
        ranked.append({
            "card":card,"role":RAMP_ROLES[card],
            "exploratory_context_weighted_T2_pp":round(score,4),
            "matched_single_card_contexts":len(recs),
            "distinct_trial_sets":len({v["comp"]["trial"] for v in recs}),
            "positive_contexts":sum(v["delta"]>0 for v in recs),
            "negative_contexts":sum(v["delta"]<0 for v in recs),
            "zero_contexts":sum(v["delta"]==0 for v in recs),
            "backgrounds":sorted({x for v in recs for x in (v["comp"]["from_arm"],v["comp"]["to_arm"])}),
            "status":"EXPLORATORY_NOT_CONFIRMATORY"})
    return sorted(ranked,key=lambda x:(-x["exploratory_context_weighted_T2_pp"],
                    -x["matched_single_card_contexts"],x["card"]))

def prior_reference():
    d=json.loads(Path("benchmark_results/dack_broad_finalists_heldout_n256.json").read_text())
    assert d["status"]=="PASS" and d["n_paired"]==256
    old=json.loads(Path("benchmark_results/dack_no_basalt_key_candelabra_n128.json").read_text())
    assert old["status"]=="PASS" and old["n_paired"]==128
    return {
      "standard_policy_only_not_poolable_into_assertive":{
        "n256_independent_heldout":{
            "trial":"dack_broad_finalists_heldout_n256",
            "winner_by_T2":"double_key",
            "current_T2_pct":d["variants"]["current"]["by_T2_pct"],
            "double_key_T2_pct":d["variants"]["double_key"]["by_T2_pct"],
            "double_key_paired_T2_pp":d["paired_vs_current"]["double_key"]["T2"],
            "note":"The historical double-Key package's 95% T2 CI crosses zero; not evidence that each individual Key is better."},
        "n128_voltaic_vs_candelabra":{
            "trial":"dack_no_basalt_key_candelabra_n128",
            "voltaic_T2_pct":old["voltaic_key"]["by_T2_pct"],
            "candelabra_T2_pct":old["candelabra"]["by_T2_pct"],
            "paired_T2":old["paired"]["candelabra_minus_voltaic_key"]["by_T2"],
            "note":"Historical Standard policy, different fixed 34-land deck; CI crosses zero."}}}

def build(inputs):
    trials=[]
    for config in TRIALS:
        report,raw=inputs[config["name"]]
        t=load_trial(config,report,raw)
        if t:trials.append(t)
    cards={}
    for m in (screen20,flex41):
        for name,deck in m.VARIANTS.items():
            for card in MONITORED:
                if card in deck:
                    card_rec=cards.setdefault(card,{"card":card,"role":RAMP_ROLES[card],
                        "variant_memberships":0,"screening_status":"UNRANKED_UNTIL_MATCHED_RESULTS"})
                    card_rec["variant_memberships"]+=1
    comparisons=[]
    for t in trials:comparisons.extend(one_slot_contrasts(t))
    ranks=rank_cards(comparisons)
    for row in ranks:
        cards[row["card"]]["screening_status"]="EXPLORATORY_DIRECT_COMPARISON_AVAILABLE"
    return {"schema":EVIDENCE_SCHEMA,"active_policy":"assertive","promotion_source_n":10000,
       "screen_status":{
         config["name"]:{"source_run":config["source_run"],
                         "expected_n":config["n"],
                         "variant_count":len(config["module"].VARIANTS),
                         "status":"VALIDATED" if any(t["config"]["name"]==config["name"] for t in trials) else "WAITING_FOR_POOLED_RESULT"}
         for config in TRIALS},
       "comparison_rules":{
         "primary_endpoint":"cumulative T2 Dack-cast rate, paired same seeds",
         "secondary_endpoints":["T1","T3","land count","combo dependency flags"],
         "valid_contrast":"one-for-one direct card substitution on otherwise identical 99-card backgrounds within one validated matched trial",
         "do_not":"Do not infer a card's marginal independent value from multi-card packages, do not pool different policies, or mistake repeated contrasts for independent confirmation",
         "effect_status":"Exploratory; correlated re-use of games, multiple comparisons, provisional leaderboard; independent held-out confirmation required."},
       "fixed_anchor_cards_needing_future_dedicated_trials":[x for x in ANCHORS if x not in {c["card"] for c in ranks}],
       "tracked_ramp_inventory":sorted(cards.values(),key=lambda x:x["card"]),
       "single_swap_comparison_count":len(comparisons),
       "single_swap_head_to_heads":sorted(comparisons,key=lambda x:-x["metrics"]["T2"]["delta_pp"]),
       "exploratory_card_ranking":ranks,
       "historical_context":prior_reference()}

def markdown(report):
    s=["# Dack Assertive ramp-piece leaderboard",
       "","**Primary metric:** probability of Dack cast by T2 under the promoted Assertive London policy, with T1 and T3 tracked as checks.",
       "",
       "> All results are optimistic full-beam goldfish Dack-cast rates, not verified complete combo lines or multiplayer wins. Small-sample rankings are exploratory and susceptible to winner's curse.",
       "","## Live evidence status",""]
    for name,q in report["screen_status"].items():
        s.append(f"- **{name}**: {q['status']}, {q['variant_count']} decks × {q['expected_n']} matched game IDs — {q['source_run']}")
    s+=["","## Ramp-card ranking (only controlled single-card comparisons)",""]
    ranked=report["exploratory_card_ranking"]
    if ranked:
        s+=["| Rank | Card | Observed context-weighted T2 signal (pp) | Matched contexts | Trial sets | Positive / negative contexts |",
            "|---:|---|---:|---:|---:|---:|"]
        for i,r in enumerate(ranked,1):
            s.append(f"| {i} | {r['card']} | {r['exploratory_context_weighted_T2_pp']:+.2f} | {r['matched_single_card_contexts']} | {r['distinct_trial_sets']} | {r['positive_contexts']} / {r['negative_contexts']} |")
        s+=["","**Interpretation:** The score averages results across the *observed replacement options and deck backgrounds*, not the intrinsic value of a card. Contexts share hands and games; the displayed score has **no valid pooled confidence interval**. Strong claims require a held-out card comparison."]
    else:
        s+=["**Pending.** Neither Assertive screen has pooled yet; no empirical Assertive card ranking is available. The 61 planned arm labels and existing historical controls are indexed in the JSON."]
    s+=["","## Leading one-slot head-to-head comparisons",""]
    comp=report["single_swap_head_to_heads"]
    if comp:
        s+=["| New card over old | Background | Δ T2 (pp) | Paired 95% CI (pp) | n |",
            "|---|---|---:|---|---:|"]
        for x in comp[:30]:
            ci=x["metrics"]["T2"]["paired_95_ci_pp"]
            s.append(f"| {x['new_card']} over {x['old_card']} | {x['trial']}: {x['from_arm']} → {x['to_arm']} | {x['metrics']['T2']['delta_pp']:+.2f} | {ci[0]:+.2f} to {ci[1]:+.2f} | {x['n']} |")
    s+=["","## Historical controls — Standard mulligans only",""]
    h=report["historical_context"]["standard_policy_only_not_poolable_into_assertive"]
    a=h["n256_independent_heldout"];b=h["n128_voltaic_vs_candelabra"]
    s.append(f"- The old 256-game held-out six-arm screen had **double-Key** at {a['double_key_T2_pct']:.2f}% by T2 versus {a['current_T2_pct']:.2f}% for the baseline; paired difference {a['double_key_paired_T2_pp']['delta_pp']:+.2f} pp with 95% CI {a['double_key_paired_T2_pp']['paired_95_ci_pp']}. The interval crosses zero.")
    s.append(f"- The old 128-game Key vs Candelabra direct swap had Voltaic Key at {b['voltaic_T2_pct']:.2f}% by T2 and Candelabra at {b['candelabra_T2_pct']:.2f}%; also not a settled ranking.")
    s+=["","## What's not ranked yet",""]
    s.append("Some powerful rocks are present in every test deck and consequently have no controlled 'card absent' comparator in these screens. Their omission from the rankings **does not mean they are weak**. Dedicated same-slot replacement tests are needed for: "+", ".join(report["fixed_anchor_cards_needing_future_dedicated_trials"])+".")
    s+=["","**Promotion rule:** No deck cut is decided by this leaderboard. Identify repeatable T2-leading combinations, separately verify full combo functionality and multiplayer constraints, then run independent held-out paired tests."]
    return "\n".join(s)+"\n"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--screen20-report")
    ap.add_argument("--screen20-raw")
    ap.add_argument("--flex41-report")
    ap.add_argument("--flex41-raw")
    ap.add_argument("--out",default="benchmark_results/dack_assertive_ramp_card_tracker.json")
    ap.add_argument("--md",default="DACK_ASSERTIVE_RAMP_CARD_LEADERBOARD.md")
    a=ap.parse_args()
    choices={
      "screen20":(a.screen20_report,a.screen20_raw),
      "flex41":(a.flex41_report,a.flex41_raw)}
    r=build(choices)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,indent=2)+"\n")
    Path(a.md).write_text(markdown(r))
    print("RAMP_CARD_LEDGER",json.dumps({
        "screen_status":{k:v["status"] for k,v in r["screen_status"].items()},
        "card_inventory":len(r["tracked_ramp_inventory"]),
        "matched_head_to_heads":r["single_swap_comparison_count"],
        "ranked_cards":len(r["exploratory_card_ranking"]),
        "top_cards":r["exploratory_card_ranking"][:8]}),flush=True)

if __name__=="__main__":
    main()
