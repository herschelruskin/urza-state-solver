#!/usr/bin/env python3
"""Planned controlled-swap coverage of the two independent Assertive screens.

No experimental outcomes are inferred. Lists exactly which cards are varied
in 1-for-1 matched configurations vs held constant in both screens.
"""
from __future__ import annotations
import collections, csv, json
from pathlib import Path
import dack_assertive_ramp_land_key_screen_n256_20261026 as core
import dack_assertive_flexslots_33to36_n128_20261026 as flex

MANIFEST="dack_assertive_ramp_tracker_manifest.json"
SOURCES=(("core20",core.VARIANTS),("flex41",flex.VARIANTS))

def main(outdir="ramp_leaderboard"):
    manifest=json.loads(Path(MANIFEST).read_text())
    log=[]
    counts=collections.Counter()
    involved=collections.defaultdict(set)
    for suite,variants in SOURCES:
        names=list(variants)
        assert "current" in variants
        for i,a in enumerate(names):
            for b in names[i+1:]:
                old=collections.Counter(variants[a])-collections.Counter(variants[b])
                new=collections.Counter(variants[b])-collections.Counter(variants[a])
                if sum(old.values())!=1 or sum(new.values())!=1:continue
                o=next(iter(old)); n=next(iter(new))
                log.append({"suite":suite,"from":a,"to":b,"removed":o,"added":n})
                counts[o]+=1;counts[n]+=1
                involved[o].add(suite);involved[n].add(suite)
    catalog=[]
    for item in manifest["tracked_cards"]:
        name=item["card"]
        catalog.append({
         "card":name,"role":item["role"],
         "planned_direct_swap_contexts":counts[name],
         "suites":",".join(sorted(involved[name])),
         "status":"PLANNED_DIRECT_EVIDENCE" if counts[name] else "NOT_DIRECTLY_VARIED",
         "notes":item["notes"]})
    catalog.sort(key=lambda x:(-x["planned_direct_swap_contexts"],x["card"]))
    dest=Path(outdir);dest.mkdir(parents=True,exist_ok=True)
    for name,fields,records in (
       ("planned_direct_swap_coverage.csv",list(catalog[0]),catalog),
       ("planned_one_card_contrasts.csv",list(log[0]),log)):
        with (dest/name).open("w",newline="",encoding="utf8") as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(records)
    r={"schema":"dack_assertive_planned_comparison_coverage_v1",
       "sources":{name:len(variants) for name,variants in SOURCES},
       "total_one_card_contrasts":len(log),
       "unique_tracked_cards_directly_varied":sum(x["planned_direct_swap_contexts"]>0 for x in catalog),
       "unique_tracked_cards_not_directly_varied":sum(x["planned_direct_swap_contexts"]==0 for x in catalog),
       "note":"Counts represent PLANNED pairwise comparisons. No turn results or actual piece power are implied.",
       "coverage":catalog}
    (dest/"planned_direct_swap_coverage.json").write_text(json.dumps(r,indent=2)+"\n")
    lines=["# Planned Assertive ramp comparisons (not performance rankings)","",
       f"{len(log)} distinct one-card pair contexts across the two screens, "
       f"covering {r['unique_tracked_cards_directly_varied']}/{len(catalog)} tracked pieces.","",
       "| Card | Category | Direct contexts | Status |",
       "|---|---|---:|---|"]
    for x in catalog:
        lines.append(f"| {x['card']} | {x['role']} | {x['planned_direct_swap_contexts']} | {x['status']} |")
    lines+=["","Cards with no direct comparison need a targeted held-constant-vs-replaced trial later. "
            "They are **not** the worst cards; they are simply unmeasured by these variant screens.",""]
    (dest/"planned_direct_swap_coverage.md").write_text("\n".join(lines)+"\n")
    print("DIRECT_SWAP_COVERAGE_PASS",json.dumps({
      "contexts":len(log),
      "tracked_covered":r["unique_tracked_cards_directly_varied"],
      "tracked_missing":r["unique_tracked_cards_not_directly_varied"],
      "top":catalog[:6],
      "missing": [x["card"] for x in catalog if x["planned_direct_swap_contexts"]==0]}),flush=True)

if __name__=="__main__":
    main()
