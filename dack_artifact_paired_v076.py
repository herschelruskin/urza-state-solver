#!/usr/bin/env python3
import argparse, hashlib, json, os
import dack_v076_creature_sequences as v
import dack_current99_batch_v076 as b
from dataclasses import replace

d=v.d
GENERIC="Generic 2C Rock"

# Exact abstract benchmark: {2} artifact, enters untapped, T: add C.
if GENERIC not in d.CARD_ID:
    nid=max(d.CARD_ID.values(),default=-1)+1
    d.CARD_ID[GENERIC]=nid; d.ID_CARD[nid]=GENERIC
d.COSTS[GENERIC]=(2,0,0)
d.RAMP_PROTECTED=frozenset(set(d.RAMP_PROTECTED)|{GENERIC})
d.MOONSILVER_MANA_ARTIFACTS=frozenset(set(d.MOONSILVER_MANA_ARTIFACTS)|{GENERIC})

_old_art=d.is_artifact_perm
def is_artifact_perm(name):
    return name==GENERIC or _old_art(name)
d.is_artifact_perm=is_artifact_perm

_old_tap=d.tap_mana_actions
def tap_mana_actions(s):
    out=list(_old_tap(s))
    for i,p in enumerate(s.battlefield):
        if d.effective_name(p)==GENERIC and not p.tapped:
            bf=list(s.battlefield); bf[i]=replace(p,tapped=True)
            out.append(replace(s,battlefield=tuple(bf),c=s.c+1))
    seen=set(); z=[]
    for q in out:
        k=d.key(q)
        if k not in seen: seen.add(k); z.append(q)
    return z
d.tap_mana_actions=tap_mana_actions

# Score the abstract benchmark exactly like an untapped reusable one-mana rock so beam
# selection does not penalize it merely because it lacks a printed card name.
_old_score=d.score
def score(s):
    z=_old_score(s)
    for p in s.battlefield:
        if d.effective_name(p)==GENERIC and not p.tapped:
            z+=24
    # Remove the extra battlefield-bank heuristic mismatch conservatively only for
    # on-board Generic Rock. The exact comparison still comes from legal search actions.
    return z
d.score=score

# Mycosynth Gardens may legally copy the benchmark at MV2.
_old_v03=d.v03_actions
def v03_actions(s):
    out=list(_old_v03(s))
    if any(x.name=="The Mycosynth Gardens" and not x.tapped and not x.aux for x in s.battlefield):
        if any(d.effective_name(x)==GENERIC for x in s.battlefield):
            for paid in d.pay_options(s,2):
                gi=next((j for j,x in enumerate(paid.battlefield)
                         if x.name=="The Mycosynth Gardens" and not x.tapped and not x.aux),None)
                if gi is None: continue
                if not any(d.effective_name(x)==GENERIC for j,x in enumerate(paid.battlefield) if j!=gi):
                    continue
                bf=list(paid.battlefield); bf[gi]=replace(bf[gi],tapped=True,aux="COPY:"+GENERIC)
                out.append(replace(paid,battlefield=tuple(bf)))
    seen=set(); z=[]
    for q in out:
        k=d.key(q)
        if k not in seen: seen.add(k); z.append(q)
    return z
d.v03_actions=v03_actions

BASE_DECK=tuple(v.CURRENT_DECK)
BASE_HASH=hashlib.sha256("\n".join(BASE_DECK).encode()).hexdigest()

GROUPS={
 "twos":[
   "Liquimetal Torque","Pearl Medallion","Mind Stone","Prismatic Lens","Implements of Sacrifice"
 ],
 "threes":[
   "Tooth of Ramos","Coalition Relic","Everflowing Chalice","Jeweled Amulet","Moonsilver Key","Expedition Map"
 ],
}

def variant_names(group):
    out=["baseline"]
    for card in GROUPS[group]:
        out += [card+" -> Generic Rock", card+" -> Snow Plains"]
    return out

def deck_for(name):
    if name=="baseline": return list(BASE_DECK)
    if " -> Generic Rock" in name:
        target=name.split(" -> Generic Rock")[0]; repl=GENERIC
    elif " -> Snow Plains" in name:
        target=name.split(" -> Snow Plains")[0]; repl="Snow-Covered Plains"
    else: raise ValueError(name)
    deck=list(BASE_DECK)
    deck[deck.index(target)]=repl
    assert len(deck)==99
    return deck

def utility(t):
    return 1.0 if t in (1,2) else 0.5 if t==3 else 0.0

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--group",choices=sorted(GROUPS),required=True)
    ap.add_argument("--start",type=int,required=True)
    ap.add_argument("--games",type=int,default=4)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    assert v.selftest()
    rows=[]
    for gid in range(a.start,a.start+a.games):
        vr={}
        for name in variant_names(a.group):
            d.DECK=deck_for(name)
            row=b.simulate_game(gid)
            vr[name]={"win_turn":row["win_turn"],"keep_n":row["keep_n"],
                      "seat":row["seat"],"utility":utility(row["win_turn"])}
        rows.append({"game_id":gid,"variants":vr})
        print(json.dumps({"group":a.group,"game_id":gid,
                          "wins":{k:x["win_turn"] for k,x in vr.items()}}),flush=True)
    d.DECK=list(BASE_DECK)
    payload={"test":"artifact_benchmark_paired_v076","group":a.group,
             "base_deck_sha256":BASE_HASH,"policy_signature":b.CONFIG,
             "generic_benchmark":"{2} artifact, untapped, T: add {C}",
             "targets":GROUPS[a.group],"start":a.start,"games":a.games,"rows":rows}
    os.makedirs(os.path.dirname(a.out) or ".",exist_ok=True)
    json.dump(payload,open(a.out,"w"),indent=2)
    print(json.dumps({"status":"complete","group":a.group,"games":a.games}),flush=True)

if __name__=="__main__": main()
