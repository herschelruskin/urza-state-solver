#!/usr/bin/env python3
"""Boonweaver v0.77 paired Serum Powder/Planar Atlas screen (no banned cards).

Uses the exact October 10 A_baseline deck as an AST literal; imports only v0.77.
Adds the multiplayer free seven and rules-correct Serum Powder (bottom first).
Output is a transparent N-game heuristic-policy screen, not optimal-play proof.
"""
from __future__ import annotations
import argparse, ast, hashlib, itertools, json, random, time
from collections import Counter
from dataclasses import replace
from pathlib import Path
import dack_full_deck_accel_n512_batch as batch

m=batch.m
d=m.d
source=ast.parse(Path("dack_lotus_crypt_n1024.py").read_text())
raw=next(ast.literal_eval(node.value) for node in source.body
         if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="BASE_TEXT" for t in node.targets))
BASE=tuple(card for line in raw.splitlines()
           for count,card in [line.split(" ",1)] for _ in range(int(count)))
assert len(BASE)==99 and BASE.count("Snow-Covered Plains")==13
assert "Mana Crypt" not in BASE and "Jeweled Lotus" not in BASE
assert BASE.count("Implements of Sacrifice")==1
PROTECTED=frozenset({
    "Boonweaver Giant","Preston, the Vanisher","Roaming Throne",
    "Bound by Moonsilver","Floating Shield","Gift of Immortality",
    "Hardlight Containment","Idolized","Lunarch Mantle","Mantle of the Ancients",
    "Minimus Containment","Pentarch Ward","Sheltered by Ghosts","Super State",
})
assert len(PROTECTED)==14 and PROTECTED.issubset(BASE)
VARIANTS=("baseline","serum_powder","planar_atlas")

def build_deck(name):
    assert name in VARIANTS
    cards=list(BASE)
    if name!="baseline":
        cards[cards.index("Implements of Sacrifice")]={
            "serum_powder":"Serum Powder","planar_atlas":"Planar Atlas"
        }[name]
    assert len(cards)==99
    return tuple(cards)

for name in ("Serum Powder","Planar Atlas"):
    if name not in d.CARD_ID:
        cid=max(d.CARD_ID.values())+1
        d.CARD_ID[name]=cid;d.ID_CARD[cid]=name
d.COSTS.update({"Serum Powder":(3,0,0),"Planar Atlas":(2,0,0)})
old_is_artifact=d.is_artifact_perm
def is_artifact(name):
    return name in {"Serum Powder","Planar Atlas"} or old_is_artifact(name)
d.is_artifact_perm=is_artifact
d.RAMP_PROTECTED=frozenset(set(d.RAMP_PROTECTED)|{"Serum Powder","Planar Atlas"})
d.MOONSILVER_MANA_ARTIFACTS=frozenset(set(d.MOONSILVER_MANA_ARTIFACTS)|{"Serum Powder","Planar Atlas"})
d.AURAS=frozenset(set(d.AURAS)|PROTECTED.difference(d.COMBO_CREATURES))

_old_tap=d.tap_mana_actions
def tap_mana_actions(s):
    out=list(_old_tap(s))
    for i,p in enumerate(s.battlefield):
        if p.tapped or d.effective_name(p.name if False else p) not in {"Serum Powder","Planar Atlas"}:
            continue
        bf=list(s.battlefield); bf[i]=replace(p,tapped=True)
        out.append(replace(s,battlefield=tuple(bf),c=s.c+1))
    return m._dedupe(out)
d.tap_mana_actions=tap_mana_actions

_old_cast=d.cast_actions
TRIAL_SEED=0
def stable_shuffle(items,salt):
    vals=list(items)
    dig=hashlib.sha256((str(TRIAL_SEED)+"|"+repr(salt)).encode()).digest()
    random.Random(int.from_bytes(dig[:8],"big")).shuffle(vals)
    return vals

def atlas_states(pre,post):
    if sum(x.name=="Planar Atlas" for x in post.battlefield)<=sum(x.name=="Planar Atlas" for x in pre.battlefield):
        return [post]
    if not any(x.name=="Planar Atlas" and not x.tapped for x in post.battlefield):
        return [post]
    bf=list(post.battlefield)
    ai=next(i for i,p in enumerate(bf) if p.name=="Planar Atlas" and not p.tapped)
    bf[ai]=replace(bf[ai],tapped=True)
    base=replace(post,battlefield=tuple(bf))
    top=base.library[:4]; tail=base.library[4:]
    # May decline to look; if looking, may reveal 0 or 1 eligible land card.
    # Revealing 0 bottoms the four looked-at cards in random order.
    choices=[None]+list(dict.fromkeys(x for x in top if x in d.LANDS))
    out=[base]
    for pick in choices:
        chosen=[] if pick is None else [pick]
        remaining=list(top)
        if pick is not None:remaining.remove(pick)
        bot=stable_shuffle(remaining,(pre.turn,pre.hand,pre.library[:4],pick,"ATLAS"))
        out.append(replace(base,library=tuple(chosen)+tuple(tail)+tuple(bot)))
    return out

def cast_actions(s):
    out=[]
    for q in _old_cast(s):
        out.extend(atlas_states(s,q))
    return m._dedupe(out)
d.cast_actions=cast_actions

_old_score=d.score
def score(s):
    value=_old_score(s)
    for p in s.battlefield:
        if not p.tapped and d.effective_name(p) in {"Serum Powder","Planar Atlas"}:
            value+=22
    return value
d.score=score

# Exact same deck/seed mapping, plus a free initial Commander mulligan.
# Existing frozen continuation values are used at the 7,6,...,1 decisions.
C=batch.FROZEN_CONTINUATION
CFG=batch.CONFIG.copy()
CFG["gameplay_beam"]=int(CFG["gameplay_beam"])
CFG["mulligan_eval_beam"]=int(CFG["mulligan_eval_beam"])

def screen_normal(seven,keep_n,rest,seat):
    return batch.evaluate_keep(seven,keep_n,rest,seat)

def best_powder_bottom(seven,keep_n):
    """Choose a legal London bottoming set before Powder's exile.

    Every protected creature/Aura must be on the bottom; it may never be exiled.
    Higher-value nonprotected fast mana is preferentially preserved when slots remain.
    """
    if "Serum Powder" not in seven:return None
    count=7-keep_n
    inds=tuple(range(7))
    premiums={"Lion's Eye Diamond","Mana Vault","Sol Ring","Ancient Tomb",
              "Mox Diamond","Mox Opal","Chrome Mox","Lotus Petal",
              "Mishra's Workshop","City of Traitors","Grim Monolith"}
    viable=[]
    for b in itertools.combinations(inds,count):
        bs=set(b)
        hand=tuple(seven[i] for i in inds if i not in bs)
        bottom=tuple(seven[i] for i in b)
        if "Serum Powder" not in hand or any(x in PROTECTED for x in hand):
            continue
        score=(sum(x in PROTECTED for x in bottom)*100
               +sum(x in premiums for x in bottom)*10
               +sum(x in d.LANDS for x in bottom)*2)
        viable.append((score,hand,bottom))
    return max(viable,key=lambda x:x[0]) if viable else None

def eval_powder_redraw(hand,rest,bottom,seat):
    # Exact color/resource evaluator, but a reduced screening sample.
    ev=d.keep_weighted_ev_seat(
        d.sort_hand(hand),tuple(rest),seat=seat,
        beam=CFG["mulligan_eval_beam"],samples=CFG["screen_samples"],
        bottom=bottom,t3_weight=CFG["lambda"])
    return float(ev["utility"])

def choose_hand(rng,seat,variant):
    pool=list(d.DECK)
    game_exile=[]
    audit=[]; free_available=True
    keep_n=7; seen_stage=0; powders=0
    while True:
        seen_stage+=1
        rng.shuffle(pool)
        seven=list(pool[:7]); rest=list(pool[7:])
        raw,ev,struct,normal_hand,normal_bottom,unknown,_,refined=screen_normal(seven,keep_n,rest,seat)
        # A first mulligan in 4-player EDH is free; for the first seven
        # compare against a second seven's opportunity value, conservatively
        # using the same calibrated C6 threshold used for that second seven.
        threshold=0.0 if keep_n==1 else float(C[keep_n-1])
        rec={"stage":seen_stage,"keep_n":keep_n,"raw":float(raw),"threshold":threshold,
             "powder_safe":False,"powder_used":False}
        if keep_n==1 or float(raw)>=threshold:
            audit.append(rec)
            lib=tuple(unknown)+tuple(normal_bottom)
            return d.State(1,tuple(normal_hand),lib,exile=tuple(game_exile)),keep_n,powders,audit
        if variant=="serum_powder":
            candidate=best_powder_bottom(seven,keep_n)
            if candidate is not None:
                rec["powder_safe"]=True
                _,to_exile,bottom=candidate
                # The Powder hand is already the post-London-bottom hand:
                # exile it, draw the *same number* of cards from the
                # library remaining after the seven-card mulligan draw.
                assert "Serum Powder" in to_exile
                assert not PROTECTED.intersection(to_exile)
                n=len(to_exile)
                replacement=tuple(rest[:n])
                undrawn=tuple(rest[n:])
                future=undrawn+tuple(bottom)
                powder_raw=eval_powder_redraw(replacement,undrawn,bottom,seat)
                rec["powder_utility"]=powder_raw
                rec["powder_used"]=True
                powders+=1
                game_exile.extend(to_exile)
                assert not PROTECTED.intersection(game_exile)
                if powder_raw>=threshold or keep_n==1:
                    rec["powder_kept"]=True
                    audit.append(rec)
                    return d.State(1,d.sort_hand(replacement),future,
                                   exile=tuple(game_exile)),keep_n,powders,audit
                # Otherwise take a normal mulligan with exiled cards gone.
                rec["powder_kept"]=False
                pool=list(replacement)+list(future)
                assert len(pool)+len(game_exile)==99
                audit.append(rec)
                if free_available:
                    free_available=False
                else:
                    keep_n-=1
                assert keep_n>=1
                continue
        audit.append(rec)
        if free_available:
            free_available=False
        else:
            keep_n-=1
        assert keep_n>=1

def simulate(name,gid,screen_beam=None,game_beam=None):
    deck=build_deck(name);m.set_deck(deck)
    seed=CFG["seed_base"]+int(gid)*1000003
    global TRIAL_SEED
    TRIAL_SEED=seed; m.set_trial_seed(seed)
    rng=random.Random(seed)
    seat=rng.randrange(4)
    s,k,np,audit=choose_hand(rng,seat,name)
    if game_beam is None:game_beam=CFG["gameplay_beam"]
    win=d._win_turn_from_unknown_order(s.hand,s.library,seat,
                beam=game_beam,max_turn=3)
    # If our mulligans exiled anything we cannot shuffle it back in.
    assert not PROTECTED.intersection(s.exile)
    return {"id":gid,"variant":name,"seat":seat,"keep":k,"powders":np,
            "powder_safe":sum(x["powder_safe"] for x in audit),
            "powder_used":sum(x["powder_used"] for x in audit),
            "turn":int(win or 0),"exiled":list(s.exile),
            "audit":audit}

def selftest():
    assert m.selftest()
    for name in VARIANTS:assert len(build_deck(name))==99
    assert all("Mana Crypt" not in build_deck(x) and "Jeweled Lotus" not in build_deck(x) for x in VARIANTS)
    assert best_powder_bottom(["Serum Powder","Boonweaver Giant","Sol Ring","Ancient Tomb",
              "Snow-Covered Plains","Mana Vault","Manifold Key"],7) is None
    assert best_powder_bottom(["Serum Powder","Boonweaver Giant","Sol Ring","Ancient Tomb",
              "Snow-Covered Plains","Mana Vault","Manifold Key"],6) is not None
    # Three-mana Serum Powder taps for a colorless when untapped.
    x=d.State(1,(),tuple(PROTECTED),(d.Perm("Serum Powder"),))
    assert any(q.c==1 for q in d.tap_mana_actions(x))
    # Atlas enters tapped; can't produce mana until a later untap.
    x=d.State(1,("Planar Atlas",),("Snow-Covered Plains","Sol Ring",
        "Ancient Tomb","Preston, the Vanisher","Roaming Throne"),c=2)
    results=d.cast_actions(x)
    assert any(any(p.name=="Planar Atlas" and p.tapped for p in q.battlefield) for q in results)
    assert any(q.library[0]=="Snow-Covered Plains" for q in results)
    assert not any(q.c>=1 for q in d.tap_mana_actions(d.State(1,(),(),
                (d.Perm("Planar Atlas",tapped=True),))))
    print("AUDIT_PASS exact-99, 14 protected, banned excluded, atlas-etb, powder-bottom",flush=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--n",type=int,default=8)
    parser.add_argument("--start",type=int,default=0)
    parser.add_argument("--beam",type=int,default=240)
    parser.add_argument("--screen-beam",type=int,default=60)
    parser.add_argument("--out",default="powder_atlas_result.json")
    args=parser.parse_args()
    CFG["gameplay_beam"]=args.beam
    CFG["mulligan_eval_beam"]=args.screen_beam
    selftest()
    results={name:[] for name in VARIANTS}
    begin=time.time()
    for gid in range(args.start,args.start+args.n):
        for name in VARIANTS:
            row=simulate(name,gid,game_beam=args.beam)
            results[name].append(row)
            print(json.dumps({"game":gid,"variant":name,"turn":row["turn"],
                    "keep":row["keep"],"powders":row["powders"]}),flush=True)
    summary={}
    for name,rows in results.items():
        c=Counter(r["turn"] for r in rows)
        summary[name]={"n":len(rows),"T1":c[1],"T2":c[2],"T3":c[3],
                       "T1T2":c[1]+c[2],"T1T2T3":c[1]+c[2]+c[3],
                       "powder_activations":sum(r["powders"] for r in rows),
                       "powder_safes":sum(r["powder_safe"] for r in rows),
                       "mean_keep":sum(r["keep"] for r in rows)/len(rows)}
    payload={"method":"v0.77 multiplayer free London + heuristic legal Serum Powder",
             "replacement":"Implements of Sacrifice",
             "config":CFG,"summary":summary,
             "rows":results,"elapsed":time.time()-begin}
    Path(args.out).write_text(json.dumps(payload,indent=2))
    print("FINAL_SUMMARY "+json.dumps(summary),flush=True)

if __name__=="__main__":main()
