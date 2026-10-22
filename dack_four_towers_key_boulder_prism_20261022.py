#!/usr/bin/env python3
"""Matched Dack baseline vs requested four Command Towers + 3 accelerator package.

User-requested EXACT hypothetical:
  - 4 Plains + 4 Command Tower (NOT singleton legal, and ONLY white in mono-white Dack)
  - Hardlight Containment, Lunarch Mantle, Basalt Monolith OUT
  + Pentad Prism, Voltaic Key, Giant's Boulder IN
Two actionable comparators:
  legal: instead of 4 Command Towers, use Command Tower, Mana Confluence,
         City of Brass, Gemstone Mine
  legal_combo_safe: same legal lands, but keep Lunarch Mantle's accessible
         Boonweaver sacrifice outlet, remove Tooth of Ramos instead.
All 4 arms keep same 34 lands and 99 cards; no banned mana crypt/lotus.
The shared Pentad Prism fix correctly allows removing 2 counters with NO tap.
Results measure T1/T2/T3 Dack CAST, NOT full Boonweaver combo success.
"""
from __future__ import annotations
import argparse, gzip, hashlib, json, math, time
from collections import Counter
from pathlib import Path
import dack_rainbow_prism_corrected_20261022 as imported

root=imported.root
d=imported.d
m=imported.m
CURRENT=imported.CURRENT
swap=imported.swap

# Base engine predates the user's new four-Command-Tower experiment. In a
# mono-white identity Command Tower is a white-only untapped land.
if "Command Tower" not in d.CARD_ID:
    cid=max(d.CARD_ID.values(),default=-1)+1
    d.CARD_ID["Command Tower"]=cid
    d.ID_CARD[cid]="Command Tower"
d.LANDS=frozenset(set(d.LANDS)|{"Command Tower"})
d.WHITE_LANDS=frozenset(set(d.WHITE_LANDS)|{"Command Tower"})
d.GUARANTEED_WHITE_LANDS=frozenset(set(d.GUARANTEED_WHITE_LANDS)|{"Command Tower"})
d.LAND_TUTOR_TARGETS=tuple(dict.fromkeys(tuple(d.LAND_TUTOR_TARGETS)+("Command Tower",)))

OUT_NONLAND=("Hardlight Containment","Lunarch Mantle","Basalt Monolith")
IN_NONLAND=("Pentad Prism","Voltaic Key","Giant's Boulder")
def replace_plains(deck,replacements):
    arr=list(deck)
    assert arr.count("Plains")>=len(replacements)
    for n in replacements:
        arr[arr.index("Plains")]=n
    return tuple(arr)
def replace_nonlands(deck,outs=OUT_NONLAND):
    arr=tuple(deck)
    for a,b in zip(outs,IN_NONLAND):
        arr=swap(arr,a,b)
    return arr

FOUR_TOWERS=replace_nonlands(replace_plains(CURRENT,["Command Tower"]*4))
LEGAL_LANDS=("Command Tower","Mana Confluence","City of Brass","Gemstone Mine")
LEGAL=replace_nonlands(replace_plains(CURRENT,LEGAL_LANDS))
SAFE_OUT=("Hardlight Containment","Tooth of Ramos","Basalt Monolith")
LEGAL_COMBO_SAFE=replace_nonlands(replace_plains(CURRENT,LEGAL_LANDS),SAFE_OUT)
VARIANTS={
 "current":CURRENT,
 "four_towers_hypothetical":FOUR_TOWERS,
 "legal_four_lands":LEGAL,
 "legal_preserve_mantle":LEGAL_COMBO_SAFE,
}
root.VARIANTS=VARIANTS
root.batch.build_deck=lambda variant:VARIANTS[variant]

def sha(deck):return hashlib.sha256("\n".join(deck).encode()).hexdigest()

def check_diff(label,from_cards,to_cards):
    assert Counter(VARIANTS[label])-Counter(CURRENT)==Counter(to_cards),label
    assert Counter(CURRENT)-Counter(VARIANTS[label])==Counter(from_cards),label

def audit():
    assert len(CURRENT)==99 and CURRENT.count("Plains")==10
    assert all(k not in CURRENT for k in IN_NONLAND+("Command Tower",))
    assert all(k in CURRENT for k in OUT_NONLAND+("Tooth of Ramos",))
    assert len(set(LEGAL))==len(LEGAL)
    check_diff("four_towers_hypothetical",["Plains"]*4+list(OUT_NONLAND),
               ["Command Tower"]*4+list(IN_NONLAND))
    check_diff("legal_four_lands",["Plains"]*4+list(OUT_NONLAND),
               list(LEGAL_LANDS)+list(IN_NONLAND))
    check_diff("legal_preserve_mantle",["Plains"]*4+list(SAFE_OUT),
               list(LEGAL_LANDS)+list(IN_NONLAND))
    for variant,deck in VARIANTS.items():
        assert len(deck)==99
        assert deck.count("Plains")== (10 if variant=="current" else 6)
        assert sum(card in d.LANDS or card in ("Emeria's Call","Razorgrass Ambush") for card in deck)==34,(variant,"land_count")
        assert root.COMBO.issubset(deck)
        assert deck.count("Bucknard's Everfull Purse")==1 and deck.count("Coalition Relic")==1
        assert not {"Mana Crypt","Jeweled Lotus"}.intersection(deck)
        assert variant=="four_towers_hypothetical" or len([x for x in Counter(deck).values() if x>1])==1
        root.install(variant)
        assert len(d.DECK)==99
        assert all(x in d.CARD_ID for x in d.DECK)
    assert FOUR_TOWERS.count("Command Tower")==4
    assert LEGAL.count("Command Tower")==1
    assert "Lunarch Mantle" in CURRENT and "Lunarch Mantle" not in FOUR_TOWERS and "Lunarch Mantle" in LEGAL_COMBO_SAFE
    # Commander Tower produces white, not sunburst-favorable off-color mana.
    state=d.State(1,("Pentad Prism",),(),(d.Perm("Command Tower",False,0,1),))
    outputs=d.tap_mana_actions(state)
    assert any(q.w==1 and q.any==0 for q in outputs), "Command Tower must make W"
    assert not any(q.any>0 for q in outputs), "Command Tower must NOT make off-color mana"
    # Prism repair is active and can release both mana units in one turn.
    s=d.State(1,(),(),(d.Perm("Pentad Prism",False,2,1),))
    first=[x for x in d.tap_mana_actions(s) if x.any==1 and x.battlefield[0].counters==1 and not x.battlefield[0].tapped]
    assert first
    second=[x for x in d.tap_mana_actions(first[0]) if x.any==2 and x.battlefield[0].counters==0]
    assert second
    # All additions are real actions, not merely deck-name membership.
    assert d.COSTS["Voltaic Key"]==(1,0,0)
    assert d.COSTS["Giant's Boulder"]==(1,0,0)
    assert d.COSTS["Pentad Prism"]==(2,0,0)
    assert root.batch.CONFIG["lambda"]==0.5
    print("DACK_FOUR_TOWERS_PACKAGE_AUDIT_PASS",
          json.dumps({v:sha(deck) for v,deck in VARIANTS.items()}),flush=True)

def run(shard,games,beam,out):
    rows=[];start=time.time()
    for i in range(games):
        gid=shard*games+i;rec={"gid":gid}
        for name in VARIANTS:
            root.install(name)
            d._WIN_CACHE.clear()
            rec[name]=root.simulate(name,gid,beam)
            print("PACKAGE_GAME",name,gid,rec[name]["win_turn"],rec[name]["keep_n"],flush=True)
        rows.append(rec)
    payload={"schema":"four_towers_package_paired_v1","shard":shard,"games":games,
             "beam":beam,"seed_base":root.batch.CONFIG["seed_base"],
             "deck_sha":{k:sha(v) for k,v in VARIANTS.items()},
             "rows":rows,"elapsed_sec":round(time.time()-start,2)}
    with gzip.open(out,"wt",encoding="utf8") as f:json.dump(payload,f,separators=(",",":"))
    print("DACK_FOUR_TOWERS_PACKAGE_SHARD_PASS",shard,games,round(time.time()-start,2),flush=True)

def pool(path,out,expected):
    files=sorted(Path(path).rglob("*.json.gz"))
    assert files
    data={};hashes=None;beams=set()
    for path in files:
        with gzip.open(path,"rt",encoding="utf8") as f:q=json.load(f)
        assert q["schema"]=="four_towers_package_paired_v1"
        assert len(q["rows"])==q["games"]
        if hashes is None:hashes=q["deck_sha"]
        assert hashes==q["deck_sha"]
        beams.add(q["beam"])
        for rec in q["rows"]:
            gid=rec["gid"];assert gid not in data
            for variant in VARIANTS:
                assert rec[variant]["game_id"]==gid
                assert rec[variant]["seed"]==q["seed_base"]+gid*1000003
            data[gid]=rec
    assert len(beams)==1
    assert set(data)==set(range(expected)),(len(data),expected)
    n=len(data)
    report={"status":"PASS","n_paired":n,"beam":list(beams)[0],"deck_sha":hashes,
      "scope":"Historical full-beam commander deployment goldfish only, no validation of post-Dack combo; 4 Command Tower variant is illegal singleton; free London EV is approximate and susceptible to mulligan sampling noise; inherited imperfect-information/oracle limits.",
      "swaps":{"nonlands":list(zip(OUT_NONLAND,IN_NONLAND)),
               "lands_hypothetical":"4 Plains => 4 Command Tower",
               "lands_legal":"4 Plains => Command Tower, Mana Confluence, City of Brass, Gemstone Mine",
               "combo_safe_caveat":"Protects Lunarch Mantle by removing Tooth of Ramos instead"}}
    for variant in VARIANTS:
        counts=Counter(data[i][variant]["win_turn"] for i in data)
        report[variant]={"counts":{str(x):counts[x] for x in range(4)},
            **{f"by_T{t}_pct":round(100*sum(counts[x] for x in range(1,t+1))/n,4) for t in (1,2,3)},
            "mean_keep":round(sum(data[i][variant]["keep_n"] for i in data)/n,4)}
    paired={}
    for variant in VARIANTS:
        if variant=="current":continue
        diffs={}
        for t in (1,2,3):
            z=[int(0<data[i][variant]["win_turn"]<=t)-int(0<data[i]["current"]["win_turn"]<=t) for i in data]
            gain=z.count(1);loss=z.count(-1);mu=(gain-loss)/n
            se=math.sqrt(sum((v-mu)**2 for v in z)/(n-1)/n) if n>1 else 0
            diffs["by_T"+str(t)]={"delta_pp":round(100*mu,4),"gains":gain,"losses":loss,
                 "paired_95pct_pp":[round(100*(mu-1.96*se),3),round(100*(mu+1.96*se),3)]}
        paired[variant+"_minus_current"]=diffs
    report["paired"]=paired
    Path(out).write_text(json.dumps(report,indent=2))
    print("DACK_FOUR_TOWERS_PACKAGE_POOL_PASS",json.dumps(report),flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",action="store_true")
    ap.add_argument("--shard",type=int,default=0)
    ap.add_argument("--games",type=int,default=8)
    ap.add_argument("--beam",type=int,default=160)
    ap.add_argument("--out",default="package.json.gz")
    ap.add_argument("--pool",action="store_true")
    ap.add_argument("--path",default="shards")
    ap.add_argument("--expected",type=int,default=64)
    a=ap.parse_args();audit()
    if a.audit:pass
    elif a.pool:pool(a.path,a.out,a.expected)
    else:run(a.shard,a.games,a.beam,a.out)
