#!/usr/bin/env python3
"""Same-seed drift audit across N10000 reference and N128 protected-aura run.

Run INSIDE protected-aura experiment's full import environment. It confirms
the 99-card current deck, Assertive policy, rules beam, individual kept hand,
ordered next 3 cards, seed, seat, keep size and turn against archived trial.
"""
import collections
import gzip
import hashlib
import json
from pathlib import Path

import dack_assertive_protected_auras_cutsearch_n128_20261027 as study
import dack_active_mulligan_policy as sim

ROOT=Path("benchmark_results")
REF=ROOT/"dack_assertive_heldout_n10000_report.raw.json.gz"
PROTECTED=ROOT/"dack_assertive_protected_auras_cutsearch_n128_report.raw.json.gz"
REF_REPORT=ROOT/"dack_assertive_heldout_n10000_report.json"
PROTECTED_REPORT=ROOT/"dack_assertive_protected_auras_cutsearch_n128_report.json"

def read_gz(path):
    assert path.is_file(),path
    with gzip.open(path,"rt",encoding="utf8") as f:return json.load(f)

def main():
    study.audit()
    assert sim.ACTIVE_POLICY=="assertive"==study.POLICY
    assert sim.GAMEPLAY_BEAM==study.BEAM==160
    assert sim.deck_hash(study.CURRENT)==sim.FROZEN_DECK_HASH
    assert sim.FROZEN_DECK_HASH=="a1c8e05dc3f9e1bcfbfbe2f7773ea4a5e62222d3440dd2f7417fd7f2f058c422"
    archive=read_gz(REF)
    assert archive["deck_hash"]==sim.FROZEN_DECK_HASH
    assert len(archive["rows"])==10000
    assert archive["seed_base"]==sim.DEFAULT_SEED_BASE

    # Critically, import all prior screen modules BEFORE same-seed reference
    # parity. This detects unexpected shared-global simulator monkeypatches.
    sim.configure_variants({"current":study.CURRENT})
    ids=(0,1,8,23,75)
    for i in ids:
        sim.reset_caches()
        out=sim.simulate("current",i,policy="assertive",
                         seed_base=sim.DEFAULT_SEED_BASE,beam=160)
        old=archive["rows"][i]["results"]["assertive"]
        for k in ("seed","seat","keep_n","hand","first3","win_turn"):
            assert out[k]==old[k],("N10000_DRIFT",i,k,out[k],old[k])
        print("ORIGINAL_HELDOUT_REPLAY_PASS",i,
              out["win_turn"],out["keep_n"],flush=True)

    n128=read_gz(PROTECTED)
    p=json.loads(PROTECTED_REPORT.read_text())
    ref=json.loads(REF_REPORT.read_text())
    assert p["status"]=="PASS" and p["n"]==128
    assert ref["status"]=="PASS"
    assert n128["seed_base"]==study.SEED_BASE
    assert len(n128["rows"])==128
    assert p["hashes"]["current"]==ref["deck_hash"]==sim.FROZEN_DECK_HASH
    assert p["beam"]==ref["beam"]==160
    assert p["policy"]=="assertive"
    sim.configure_variants(study.VARIANTS)
    for i in (0,1,8,23,75,127):
        sim.reset_caches()
        out=sim.simulate("current",i,policy="assertive",
                         seed_base=study.SEED_BASE,beam=160)
        old=n128["rows"][i]["arms"]["current"]
        for k in ("seed","seat","keep_n"):
            assert out[k]==old[k],("PROTECTED_DRIFT",i,k,out[k],old[k])
        assert out["win_turn"]==old["turn"],("PROTECTED_DRIFT",i,
                                             out["win_turn"],old["turn"])
        print("PROTECTED_BASELINE_REPLAY_PASS",i,
              out["win_turn"],out["keep_n"],flush=True)

    stats=collections.defaultdict(lambda:collections.Counter())
    counts=collections.Counter()
    for row in n128["rows"]:
        a=row["arms"]["current"]
        t=a["turn"];seat=a["seat"];keep=a["keep_n"]
        counts[t]+=1
        z=stats[seat]
        z["n"]+=1
        z["by_T1"]+=int(t==1)
        z["by_T2"]+=int(t in (1,2))
        z["by_T3"]+=int(t in (1,2,3))
        z["total_keep"]+=keep
    assert counts=={0:34,1:7,2:47,3:40},counts
    audit={"status":"PASS",
       "explanation":"The 10000-game policy, baseline deck, and protected screen use identical source rules, and selected original/protected game IDs replay exactly.",
       "source_baseline_hash":sim.FROZEN_DECK_HASH,
       "beam":160,"policy":"assertive",
       "reference":{"N":10000,"by_T2":ref["arms"]["assertive"]["T2_pct"],
                     "by_T3":ref["arms"]["assertive"]["T3_pct"]},
       "protected":{"N":128,"by_T2":p["arms"]["current"]["T2_pct"],
                    "by_T3":p["arms"]["current"]["T3_pct"],
                    "counts":dict(counts),"mean_keep":p["arms"]["current"]["mean_keep"]},
       "reference_replayed_ids":list(ids),
       "protected_replayed_ids":[0,1,8,23,75,127],
       "protected_seat_breakdown":{str(seat):dict(v) for seat,v in stats.items()},
       "limitation":"Only selected game IDs are exactly replayed; no proof of absence of every simulator flaw. The N128 screen's unusually low T3 is a statistical outlier worth rechecking with larger fresh seeds."}
    path=ROOT/"dack_assertive_baseline_drift_audit_20261027.json"
    path.write_text(json.dumps(audit,indent=2)+"\n")
    print("ASSERTIVE_BASELINE_DRIFT_AUDIT_PASS",json.dumps(audit),flush=True)

if __name__=="__main__":main()
