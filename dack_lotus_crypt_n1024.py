#!/usr/bin/env python3
"""Paired 1024-game Jeweled Lotus/Mana Crypt comparison on production DACK v0.77.

Uses the existing engine and stable lambda=.5 London evaluator, gameplay beam 240.
Card effects are appended to the live engine; no proxy simulation is used.
"""
import argparse
from collections import Counter
from dataclasses import replace
import gzip, hashlib, json
import dack_full_deck_accel_n512_batch as batch

m=batch.m
d=m.d
BASE_TEXT="1 Ancient Den\n1 Ancient Tomb\n1 Arcane Signet\n1 Basalt Monolith\n1 Blast Zone\n1 Boonweaver Giant\n1 Bound by Moonsilver\n1 Brainstone\n1 Bucknard's Everfull Purse\n1 Campfire\n1 Candelabra of Tawnos\n1 Cavern of Souls\n1 Charitable Levy\n1 Chrome Mox\n1 City of Traitors\n1 Coalition Relic\n1 Command Beacon\n1 Crystal Vein\n1 Deafening Silence\n1 Defense Grid\n1 Disruptor Flute\n1 Eiganjo, Seat of the Empire\n1 Eldrazi Confluence\n1 Emeria's Call\n1 Enlightened Tutor\n1 Erode\n1 Everflowing Chalice\n1 Expedition Map\n1 Fellwar Stone\n1 Floating Shield\n1 Gemstone Caverns\n1 Gift of Immortality\n1 Gleaming Splendor\n1 Great Hall of the Citadel\n1 Grim Monolith\n1 Hardlight Containment\n1 Homeward Path\n1 Idolized\n1 Implements of Sacrifice\n1 Inventors' Fair\n1 Jeweled Amulet\n1 Krark-Clan Ironworks\n1 Lion's Eye Diamond\n1 Lotus Petal\n1 Lunarch Mantle\n1 Mana Vault\n1 Manifold Key\n1 Mantle of the Ancients\n1 March of Otherworldly Light\n1 Mind Stone\n1 Minimus Containment\n1 Mishra's Workshop\n1 Moonsilver Key\n1 Mox Diamond\n1 Mox Opal\n1 Orim's Chant\n1 Paladin Class\n1 Pentarch Ward\n1 Petrified Hamlet\n1 Portable Hole\n1 Preston, the Vanisher\n1 Prismatic Lens\n1 Razorgrass Ambush\n1 Remote Farm\n1 Roaming Throne\n1 Ruins of Trokair\n1 Scroll Rack\n1 Sheltered by Ghosts\n1 Silence\n13 Snow-Covered Plains\n1 Sol Ring\n1 Static Prison\n1 Super State\n1 Talon Gates of Madara\n1 Tezzeret, Cruel Captain\n1 The Mind Stone\n1 The Mycosynth Gardens\n1 Thorn of Amethyst\n1 Tooth of Ramos\n1 Touch the Spirit Realm\n1 Trinisphere\n1 Untaidake, the Cloud Keeper\n1 Unwanted Remake\n1 Urza's Cave\n1 Urza's Saga\n1 Vexing Bauble\n1 Void Mirror"
BASE_DECK=tuple(card for line in BASE_TEXT.splitlines()
                for n,card in [line.split(" ",1)]
                for _ in range(int(n)))
assert len(BASE_DECK)==99 and BASE_DECK.count("Snow-Covered Plains")==13
assert len(set(BASE_DECK))==87
VARIANTS=("A_baseline","B_jeweled_lotus","C_lotus_mana_crypt")

def build_deck(variant):
    assert variant in VARIANTS
    deck=list(BASE_DECK)
    snow=[i for i,x in enumerate(deck) if x=="Snow-Covered Plains"]
    if variant in ("B_jeweled_lotus","C_lotus_mana_crypt"):
        deck[snow[0]]="Jeweled Lotus"
    if variant=="C_lotus_mana_crypt":
        deck[snow[1]]="Mana Crypt"
    assert len(deck)==99
    return tuple(deck)

# Preserve production card identities, classifications and mulligan ranking.
for c in set(BASE_DECK)|{"Jeweled Lotus","Mana Crypt"}:
    if c not in d.CARD_ID:
        cid=max(d.CARD_ID.values(),default=-1)+1
        d.CARD_ID[c]=cid
        d.ID_CARD[cid]=c
d.COSTS.update({"Jeweled Lotus":(0,0,0),"Mana Crypt":(0,0,0)})
_prev_is_artifact=d.is_artifact_perm
def _is_artifact(n):
    return n in {"Jeweled Lotus","Mana Crypt"} or _prev_is_artifact(n)
d.is_artifact_perm=_is_artifact
d.MOONSILVER_MANA_ARTIFACTS=frozenset(
    set(d.MOONSILVER_MANA_ARTIFACTS)|{"Jeweled Lotus","Mana Crypt"})
d.RAMP_PROTECTED=frozenset(
    set(d.RAMP_PROTECTED)|{"Jeweled Lotus","Mana Crypt"})
d.AURAS=frozenset(set(d.AURAS)|{
    "Hardlight Containment","Lunarch Mantle","Pentarch Ward","Minimus Containment"
})

_original_tap=d.tap_mana_actions
def tap_mana_actions(s):
    out=list(_original_tap(s))
    for i,p in enumerate(s.battlefield):
        if p.tapped: continue
        n=d.effective_name(p)
        if n=="Mana Crypt":
            bf=list(s.battlefield)
            bf[i]=replace(p,tapped=True)
            out.append(replace(s,battlefield=tuple(bf),c=s.c+2))
        elif n=="Jeweled Lotus":
            # Three WHITE mana, restricted to commander casting. This separate
            # existing Dack-only pool may cover both WW and generic for Dack.
            bf=list(s.battlefield)
            bf.pop(i)
            out.append(replace(s,battlefield=tuple(bf),
                               restricted_dack_white=s.restricted_dack_white+3,
                               grave=s.grave+(p.name,)))
    return m._dedupe(out)
d.tap_mana_actions=tap_mana_actions

# Gardens can copy either zero-MV artifact. The Gardens becomes tapped and
# therefore cannot immediately produce mana without a legitimate untap.
_original_v03=d.v03_actions
def v03_actions(s):
    out=list(_original_v03(s))
    if any(p.name=="The Mycosynth Gardens" and not p.tapped and not p.aux
           for p in s.battlefield):
        for target in set(d.effective_name(p) for p in s.battlefield):
            if target not in {"Mana Crypt","Jeweled Lotus"}: continue
            gi=next((i for i,p in enumerate(s.battlefield)
                    if p.name=="The Mycosynth Gardens" and not p.tapped
                       and not p.aux),None)
            if gi is None: continue
            bf=list(s.battlefield)
            bf[gi]=replace(bf[gi],tapped=True,aux="COPY:"+target)
            out.append(replace(s,battlefield=tuple(bf)))
    return m._dedupe(out)
d.v03_actions=v03_actions

_original_score=d.score
def score(s):
    x=_original_score(s)
    for p in s.battlefield:
        if p.tapped: continue
        if d.effective_name(p)=="Mana Crypt": x+=48
        if d.effective_name(p)=="Jeweled Lotus": x+=72
    return x
d.score=score

# Exactly the same production sampler/continuation table and game ID mapping.
batch.build_deck=build_deck
batch.VARIANTS={v:{"kind":"exact_plains_replacement",
                    "replace":([] if v=="A_baseline" else
                    [("Snow-Covered Plains","Jeweled Lotus")] if v=="B_jeweled_lotus" else
                    [("Snow-Covered Plains","Jeweled Lotus"),
                     ("Snow-Covered Plains","Mana Crypt")])}
                for v in VARIANTS}

def validate():
    assert m.selftest()
    m.set_deck(BASE_DECK)
    assert len(d.DECK)==99
    lib=tuple(d.COMBO_CREATURES)
    # Exact Mana Crypt {T}:CC; no white production.
    s=d.State(1,(),lib,(d.Perm("Mana Crypt"),))
    a=[q for q in d.tap_mana_actions(s) if q.c==2]
    assert a and a[0].w==0 and a[0].battlefield[0].tapped
    # Lotus three commander-restricted W; cannot be paid on ordinary spells.
    s=d.State(1,(),lib,(d.Perm("Jeweled Lotus"),),c=3)
    a=[q for q in d.tap_mana_actions(s)
       if q.restricted_dack_white==3]
    assert a and d.can_cast_dack(a[0])
    assert a[0].w==0 and a[0].any==0
    assert not d.pay_options(a[0],1,white=1)  # not normal spell mana
    assert not d.can_cast_dack(d.State(1,(),lib,
                                      (d.Perm("Jeweled Lotus"),),c=2))
    # 3 Lotus mana + 2 Crypt + untapped W land is a legal T1.
    s=d.State(1,("Jeweled Lotus","Mana Crypt","Snow-Covered Plains"),lib)
    q=d.search_turn(s,beam=400,depth=16)
    assert d.can_cast_dack(q),"T1 Lotus+Crypt+Plains line pruned"
    # A tapped Crypt cannot make mana, but Keys may legally untap it.
    s=d.State(1,(),lib,(d.Perm("Mana Crypt",True),))
    assert not any(q.c>=2 for q in d.tap_mana_actions(s))
    # Gardens copy is tapped upon copying, no immediate mana.
    s=d.State(1,(),lib,(d.Perm("The Mycosynth Gardens"),
                        d.Perm("Mana Crypt")))
    outs=d.v03_actions(s)
    assert any(any(p.aux=="COPY:Mana Crypt" and p.tapped
                   for p in q.battlefield) for q in outs)
    print("LOTUS_CRYPT_AUDIT_PASS",flush=True)

def run(shard,games,outpath):
    rows={v:[] for v in VARIANTS}
    for k in range(games):
        gid=shard*games+k
        for v in VARIANTS:
            r=batch.simulate_game(v,gid)
            rows[v].append([
                r["game_id"],r["seed"],r["seat"],r["keep_n"],r["win_turn"]])
        print(json.dumps({"shard":shard,"done":k+1,"gid":gid}),flush=True)
    obj={"schema":"dack_paired_lotus_crypt_n1024_v1",
         "engine":batch.CONFIG["engine"],
         "policy":batch.CONFIG["policy"],
         "config":batch.CONFIG,
         "shard":shard,"games":games,
         "variants":{v:{"deck_sha256":batch.deck_sha(build_deck(v)),
                         "rows":rows[v]} for v in VARIANTS},
         "columns":["game_id","seed","seat","keep_n","win_turn"]}
    with gzip.open(outpath,"wt",encoding="utf8") as f:
        json.dump(obj,f,separators=(",",":"))
    print("SHARD_PASS",shard,flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",action="store_true")
    ap.add_argument("--shard",type=int,default=0)
    ap.add_argument("--games",type=int,default=16)
    ap.add_argument("--out",default="dack_lotus_crypt_shard.json.gz")
    a=ap.parse_args()
    validate()
    if not a.audit:run(a.shard,a.games,a.out)
