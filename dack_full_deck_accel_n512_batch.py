#!/usr/bin/env python3
"""N=512 natural full-deck acceleration revalidation runner.

Each variant is position-preserving relative to the frozen v0.76 current 99 and uses
the exact same game_id -> seed -> seat mapping as the completed N=4096 baseline.
Only the variant deck is simulated; the pooler reuses baseline games 0..511.
"""
import argparse, hashlib, json, random, time
from collections import Counter
import dack_v077_full_deck_accel as m

d=m.d

FROZEN_CONTINUATION={
    0:0.0,1:0.06171875,2:0.19234,3:0.31419,4:0.42268,5:0.51025,6:0.55603,
}
CONFIG={
    "engine":"v0.77-full-deck-accel-20261003",
    "policy":"stable_lambda_0.5_frozen_continuation",
    "lambda":0.5,"min_keep":1,"actual_seat_before_mulligans":True,
    "mulligan_eval_beam":60,"screen_samples":8,"refine_samples":16,
    "refine_margin":0.125,"bottom_finalists":12,
    "gameplay_beam":240,"max_turn":3,"seed_base":7604096001,
    "continuation":FROZEN_CONTINUATION,
}

CURRENT=tuple(m.BASE_CURRENT_DECK)
G=m.GENERIC_A

# kind:
# current_vs_generic => variant replaces a current card with Generic; card value = current - variant.
# prospect_vs_current => variant replaces the named current slot with prospect; value = variant - current.
# package_vs_current => multi-card exact replacement; value = variant - current.
VARIANTS={
    # Current cards from the supplied acceleration tables.
    "current__Tooth_of_Ramos_vs_Generic":{"kind":"current_vs_generic","replace":[("Tooth of Ramos",G)]},
    "current__Coalition_Relic_vs_Generic":{"kind":"current_vs_generic","replace":[("Coalition Relic",G)]},
    "current__Prismatic_Lens_vs_Generic":{"kind":"current_vs_generic","replace":[("Prismatic Lens",G)]},
    "current__Pearl_Medallion_vs_Generic":{"kind":"current_vs_generic","replace":[("Pearl Medallion",G)]},
    "current__Liquimetal_Torque_vs_Generic":{"kind":"current_vs_generic","replace":[("Liquimetal Torque",G)]},
    "current__Mind_Stone_vs_Generic":{"kind":"current_vs_generic","replace":[("Mind Stone",G)]},
    "current__Giants_Boulder_vs_Generic":{"kind":"current_vs_generic","replace":[("Giant's Boulder",G)]},
    "current__Moonsilver_Key_vs_Generic":{"kind":"current_vs_generic","replace":[("Moonsilver Key",G)]},
    "current__Candelabra_vs_Generic":{"kind":"current_vs_generic","replace":[("Candelabra of Tawnos",G)]},
    "current__Implements_vs_Generic":{"kind":"current_vs_generic","replace":[("Implements of Sacrifice",G)]},
    "current__Jeweled_Amulet_vs_Generic":{"kind":"current_vs_generic","replace":[("Jeweled Amulet",G)]},
    "current__Basalt_Monolith_vs_Generic":{"kind":"current_vs_generic","replace":[("Basalt Monolith",G)]},
    "current__The_Mind_Stone_vs_Generic":{"kind":"current_vs_generic","replace":[("The Mind Stone",G)]},
    "current__Everflowing_Chalice_vs_Generic":{"kind":"current_vs_generic","replace":[("Everflowing Chalice",G)]},

    # Prospects / historical cards. Anchor choices preserve the real current shell and, where
    # available, the corrected later comparison slot from the supplied table.
    "prospect__Helm_over_Implements":{"kind":"prospect_vs_current","replace":[("Implements of Sacrifice","Helm of Awakening")]},
    "prospect__KCI_over_Pearl":{"kind":"prospect_vs_current","replace":[("Pearl Medallion","Krark-Clan Ironworks")]},
    "prospect__Inspiring_Statuary_over_Implements":{"kind":"prospect_vs_current","replace":[("Implements of Sacrifice","Inspiring Statuary")]},
    "prospect__Marble_Diamond_over_Implements":{"kind":"prospect_vs_current","replace":[("Implements of Sacrifice","Marble Diamond")]},
    "prospect__Sonic_Screwdriver_over_Implements":{"kind":"prospect_vs_current","replace":[("Implements of Sacrifice","Sonic Screwdriver")]},
    "prospect__Urzas_Incubator_over_Implements":{"kind":"prospect_vs_current","replace":[("Implements of Sacrifice","Urza's Incubator")]},
    "prospect__Worn_Powerstone_over_Implements":{"kind":"prospect_vs_current","replace":[("Implements of Sacrifice","Worn Powerstone")]},
    "prospect__Chromatic_Lantern_over_Implements":{"kind":"prospect_vs_current","replace":[("Implements of Sacrifice","Chromatic Lantern")]},
    "prospect__Honor_Worn_Shaku_over_Implements":{"kind":"prospect_vs_current","replace":[("Implements of Sacrifice","Honor-Worn Shaku")]},
    "prospect__Component_Pouch_over_Implements":{"kind":"prospect_vs_current","replace":[("Implements of Sacrifice","Component Pouch")]},
    "prospect__Oketras_Monument_over_Implements":{"kind":"prospect_vs_current","replace":[("Implements of Sacrifice","Oketra's Monument")]},
    "prospect__Cloud_Key_over_Implements":{"kind":"prospect_vs_current","replace":[("Implements of Sacrifice","Cloud Key")]},
    "prospect__Pentad_Prism_over_Implements":{"kind":"prospect_vs_current","replace":[("Implements of Sacrifice","Pentad Prism")]},
    "prospect__Thran_Dynamo_over_Implements":{"kind":"prospect_vs_current","replace":[("Implements of Sacrifice","Thran Dynamo")]},
    "prospect__Extraplanar_Lens_over_Implements":{"kind":"prospect_vs_current","replace":[("Implements of Sacrifice","Extraplanar Lens")]},
    "prospect__Bucknard_over_Liquimetal":{"kind":"prospect_vs_current","replace":[("Liquimetal Torque","Bucknard's Everfull Purse")]},
    "prospect__Kozileks_Command_over_Implements":{"kind":"prospect_vs_current","replace":[("Implements of Sacrifice","Kozilek's Command")]},

    # Manifold Key already has a completed paired N=4096 full-deck test against Boulder and is
    # intentionally not recomputed here. Packages from the supplied tables are included.
    "package__KCI_Bucknard_over_Pearl_Liquimetal":{"kind":"package_vs_current","replace":[
        ("Pearl Medallion","Krark-Clan Ironworks"),("Liquimetal Torque","Bucknard's Everfull Purse")
    ]},
    "package__Two_Keys_over_Boulder_Candelabra":{"kind":"package_vs_current","replace":[
        ("Giant's Boulder","Manifold Key"),("Candelabra of Tawnos","Voltaic Key")
    ]},

    # Provisional four-card package and one-pair reversion ablations.
    "package__Final4_Buck_KCI_Manifold_Voltaic":{"kind":"package_vs_current","replace":[
        ("Liquimetal Torque","Bucknard's Everfull Purse"),("Pearl Medallion","Krark-Clan Ironworks"),
        ("Giant's Boulder","Manifold Key"),("Candelabra of Tawnos","Voltaic Key")
    ]},
    "ablate__Final4_revert_Buck_to_Liquimetal":{"kind":"package_vs_current","replace":[
        ("Pearl Medallion","Krark-Clan Ironworks"),("Giant's Boulder","Manifold Key"),
        ("Candelabra of Tawnos","Voltaic Key")
    ]},
    "ablate__Final4_revert_KCI_to_Pearl":{"kind":"package_vs_current","replace":[
        ("Liquimetal Torque","Bucknard's Everfull Purse"),("Giant's Boulder","Manifold Key"),
        ("Candelabra of Tawnos","Voltaic Key")
    ]},
    "ablate__Final4_revert_Manifold_to_Boulder":{"kind":"package_vs_current","replace":[
        ("Liquimetal Torque","Bucknard's Everfull Purse"),("Pearl Medallion","Krark-Clan Ironworks"),
        ("Candelabra of Tawnos","Voltaic Key")
    ]},
    "ablate__Final4_revert_Voltaic_to_Candelabra":{"kind":"package_vs_current","replace":[
        ("Liquimetal Torque","Bucknard's Everfull Purse"),("Pearl Medallion","Krark-Clan Ironworks"),
        ("Giant's Boulder","Manifold Key")
    ]},
}

def build_deck(variant):
    spec=VARIANTS[variant]
    deck=list(CURRENT)
    for old,new in spec["replace"]:
        if deck.count(old)!=1:
            raise AssertionError((variant,old,deck.count(old)))
        idx=deck.index(old); deck[idx]=new
    assert len(deck)==99
    return tuple(deck)

def deck_sha(deck):
    return hashlib.sha256("\n".join(deck).encode()).hexdigest()

def evaluate_keep(seven,keep_n,rest,seat):
    raw,ev,struct,hand,bottom,unknown=d.dack_bottom_weighted_ev_seat(
        seven,keep_n,rest,seat=seat,beam=CONFIG["mulligan_eval_beam"],
        samples=CONFIG["screen_samples"],t3_weight=CONFIG["lambda"],
        finalists_n=CONFIG["bottom_finalists"])
    threshold=0.0 if keep_n==CONFIG["min_keep"] else FROZEN_CONTINUATION[keep_n-1]
    refined=False
    if keep_n>CONFIG["min_keep"] and abs(float(raw)-float(threshold))<=CONFIG["refine_margin"]:
        raw,ev,struct,hand,bottom,unknown=d.dack_bottom_weighted_ev_seat(
            seven,keep_n,rest,seat=seat,beam=CONFIG["mulligan_eval_beam"],
            samples=CONFIG["refine_samples"],t3_weight=CONFIG["lambda"],
            finalists_n=CONFIG["bottom_finalists"])
        refined=True
    return raw,ev,struct,hand,bottom,unknown,threshold,refined

def choose_hand(rng,seat):
    audit=[]
    for keep_n in range(7,CONFIG["min_keep"]-1,-1):
        deck=list(d.DECK); rng.shuffle(deck)
        seven,rest=deck[:7],deck[7:]
        raw,ev,struct,hand,bottom,unknown,threshold,refined=evaluate_keep(seven,keep_n,rest,seat)
        audit.append({"keep_n":int(keep_n),"utility":float(raw),"threshold":float(threshold),
                      "le2_est":float(ev["le2"]),"t3_exact_est":float(ev["t3"]),
                      "le3_est":float(ev["le3"]),"refined":bool(refined)})
        if keep_n==CONFIG["min_keep"] or float(raw)>=float(threshold):
            return d.State(1,hand,tuple(unknown)+tuple(bottom)),keep_n,float(raw),tuple(hand),tuple(bottom),audit
    raise RuntimeError("no terminal London keep")

def simulate_game(variant,game_id):
    deck=build_deck(variant)
    m.set_deck(deck)
    seed=CONFIG["seed_base"]+int(game_id)*1000003
    m.set_trial_seed(seed)
    rng=random.Random(seed)
    seat=rng.randrange(4)
    state,keep_n,keep_u,kept,bottom,audit=choose_hand(rng,seat)
    win=d._win_turn_from_unknown_order(state.hand,state.library,seat,
        beam=CONFIG["gameplay_beam"],max_turn=CONFIG["max_turn"])
    return {"game_id":int(game_id),"seed":int(seed),"seat":int(seat),
            "keep_n":int(keep_n),"mulligans":int(7-keep_n),"keep_utility":float(keep_u),
            "win_turn":int(win) if win else 0,"kept_hand":list(kept),
            "bottomed_cards":list(bottom),"mulligan_audit":audit}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--variant",required=True,choices=sorted(VARIANTS))
    ap.add_argument("--shard",type=int,required=True)
    ap.add_argument("--games",type=int,default=32)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    assert m.selftest()
    deck=build_deck(a.variant)
    start=time.time(); rows=[]
    for i in range(a.games):
        gid=a.shard*a.games+i
        row=simulate_game(a.variant,gid); rows.append(row)
        print(json.dumps({"variant":a.variant,"shard":a.shard,"done":i+1,
                          "game_id":gid,"win_turn":row["win_turn"],"keep_n":row["keep_n"]}),flush=True)
    c=Counter(r["win_turn"] for r in rows)
    payload={
        "compatibility_signature":{**CONFIG,"variant":a.variant,"kind":VARIANTS[a.variant]["kind"],
            "replace":VARIANTS[a.variant]["replace"],"deck_sha256":deck_sha(deck),
            "baseline_deck_sha256":deck_sha(CURRENT)},
        "variant":a.variant,"shard":a.shard,"games":a.games,
        "elapsed_seconds":time.time()-start,
        "counts":{str(k):int(v) for k,v in sorted(c.items())},"rows":rows,
    }
    with open(a.out,"w",encoding="utf-8") as f: json.dump(payload,f,indent=2)
    print(json.dumps({"status":"complete","variant":a.variant,"counts":payload["counts"],
                      "elapsed_seconds":payload["elapsed_seconds"]}),flush=True)

if __name__=="__main__":
    main()
