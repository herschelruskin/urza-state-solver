#!/usr/bin/env python3
"""Dack flicker current-100 T1-T3 DEPLOYMENT-only engine fork.

Forks validated v0.77 and patches the minimum new mechanics required for the
2026-10-12 creature-flicker non-Boonweaver list. Never interprets a Dack cast
as an automatically completed win. Opponent response and combo-pile resolution
are deliberately NOT modeled in this phase.

The older v0.77 calibration/mulligan source remains unmodified.
"""
from __future__ import annotations
from dataclasses import replace
from itertools import combinations
from pathlib import Path
import random

import dack_v077_full_deck_accel as engine

d = engine.d
ROOT = Path(__file__).resolve().parent
DECK_FILE = ROOT / "dack_flicker_current100_20261012.txt"
CREATURES = frozenset({
    "Abdel Adrian, Gorion's Ward", "Bronzebeak Foragers",
    "Felidar Guardian", "Fiend Hunter", "Flickerwisp",
    "Radiant Solar", "Restoration Angel", "Wispweaver Angel",
})
MDFC = frozenset({"Emeria's Call", "Razorgrass Ambush"})
# All policy-eligible white spells, including white creatures except Radiant Solar.
WHITE_IMPRINTS = frozenset({
    "Abdel Adrian, Gorion's Ward", "Abeyance", "Bilbo's Gambit",
    "Blind Obedience", "Bronzebeak Foragers", "Calamity's Wake",
    "Charitable Levy", "Deafening Silence", "Emeria's Call",
    "Enlightened Tutor", "Felidar Guardian", "Fiend Hunter",
    "Flickerwisp", "Gleaming Splendor", "March of Otherworldly Light",
    "Orim's Chant", "Paladin Class", "Path to Exile", "Razorgrass Ambush",
    "Restoration Angel", "Scout's Warning", "Seam Rip", "Silence",
    "Smothering Tithe", "Static Prison", "Sunscour", "Swords to Plowshares",
    "Touch the Spirit Realm", "Vanquish the Horde", "Wispweaver Angel",
})
assert len(WHITE_IMPRINTS) == 30
NEW_LANDS = frozenset({"Blast Zone", "Emergence Zone", "Fomori Vault", "Petrified Hamlet"})
NEW_ARTIFACTS = frozenset({
    "Mirage Mirror", "Rings of Brighthearth", "Smothering Tithe",  # Tithe removed from artifact classification below
    "Staff of Compleation", "The One Ring", "Throne of Eldraine", "Mind Stone",
})
NEW_ARTIFACTS -= {"Smothering Tithe"}
# Spells the goldfish is allowed to cast as real battlefield permanents.
PERMANENT_COSTS = {
    "Blind Obedience": (1,1,0), "Mirage Mirror": (3,0,0),
    "Rings of Brighthearth": (3,0,0), "Smothering Tithe": (3,1,0),
    "Staff of Compleation": (3,0,0), "The One Ring": (4,0,0),
    "Throne of Eldraine": (5,0,0), "Mind Stone": (2,0,0),
    "Charitable Levy": (1,1,0), "Disruptor Flute": (2,0,0),
}
# Sorcery speed spells with modeled effects are NOT inserted into COSTS:
# legacy default would incorrectly put a sorcery onto the battlefield.
BATTLEFRONT_COST = (3,1,0)
# Oracle {X} counts as 0 when Battlefront checks mana value.
# These are the noncreature/nonland permanents with costs <=3.
ELIGIBLE_BATTLEFRONT = {
    "Arcane Signet", "Basalt Monolith", "Blind Obedience", "Chrome Mox",
    "Cursed Totem", "Deafening Silence", "Defense Grid", "Disruptor Flute",
    "Charitable Levy",
    "Fellwar Stone", "Gleaming Splendor", "Grim Monolith", "Jeweled Amulet",
    "Lion's Eye Diamond", "Lotus Petal", "Manifold Key", "Mind Stone",
    "Mirage Mirror", "Moonsilver Key", "Mox Diamond", "Mox Opal",
    "Paladin Class", "Portable Hole", "Prismatic Lens", "Rings of Brighthearth",
    "Sol Ring", "Static Prison", "Staff of Compleation", "Tezzeret, Cruel Captain",
    "The Mind Stone", "Thorn of Amethyst", "Touch the Spirit Realm",
    "Trinisphere", "Vexing Bauble", "Void Mirror", "Voltaic Key",
}
# These two are eligible at MV0, but Battlefront puts them in with X=0.
ELIGIBLE_BATTLEFRONT.add("Everflowing Chalice")
# Verify individually against installed costs, not just a hard-coded count.

def load_deck():
    cards = []
    commander = None
    for row in DECK_FILE.read_text(encoding="utf8").splitlines():
        if not row.strip():
            continue
        n, name = row.split(" ", 1)
        if name == d.COMMANDER:
            assert int(n) == 1
            commander = name
        else:
            cards.extend([name] * int(n))
    assert commander == d.COMMANDER, commander
    assert len(cards) == 99, len(cards)
    assert len(set(cards)) == 87, len(set(cards))
    assert all(cards.count(c) == 1 for c in CREATURES)
    assert cards.count("Plains") == 13
    return tuple(cards)

BASE_DECK = load_deck()
d.DECK = list(BASE_DECK)
# Disable old Boonweaver 'all creatures in library' gate, hard-mulligan penalty,
# LED hand-contamination restriction and forced library-repair target.
# This test measures CAST availability, not whether the new flicker combo wins.
d.COMBO_CREATURES = frozenset()
d.AURAS = frozenset()
# Provisional NEW combo failure: both these key creatures must be in hand.
# One in hand alone does not invalidate the new flicker pile.
COMBO_HAND_BLOCK_PAIR = frozenset({"Abdel Adrian, Gorion's Ward", "Radiant Solar"})
def combo_hand_blocked(s):
    return COMBO_HAND_BLOCK_PAIR.issubset(set(s.hand))
d.chrome_mox_allowed = lambda card: card in WHITE_IMPRINTS
d.LANDS = frozenset(set(d.LANDS) | NEW_LANDS)
d.COSTS.update(PERMANENT_COSTS)
# Only battlefield permanents count toward Metalcraft.
_artifact_original = d.is_artifact_perm
def is_artifact_perm(card):
    return card in NEW_ARTIFACTS or _artifact_original(card)
d.is_artifact_perm = is_artifact_perm
# Need exactly 99 cards registered in cache identities, including creature pitches.
for card in set(BASE_DECK) | {"United Battlefront"}:
    if card not in d.CARD_ID:
        idx = max(d.CARD_ID.values(), default=-1)+1
        d.CARD_ID[card] = idx
        d.ID_CARD[idx] = card

d.RAMP_PROTECTED = frozenset(set(d.RAMP_PROTECTED) | {
    "The One Ring", "Throne of Eldraine", "Staff of Compleation",
    "Rings of Brighthearth", "Mirage Mirror", "Smothering Tithe",
    "Charitable Levy", "Disruptor Flute", "United Battlefront",
})
d.MOONSILVER_MANA_ARTIFACTS = frozenset(set(d.MOONSILVER_MANA_ARTIFACTS) | {"Throne of Eldraine", "Staff of Compleation"})

# One-purpose life ledger for Staff activations. The older deployment solver's
# State has no life field. Distinguishable sentinel entries in State.exile
# represent the paid life; they are not real exiled MTG cards.
STAFF_LIFE2="__STAFF_PAID_LIFE_2__"
STAFF_LIFE4="__STAFF_PAID_LIFE_4__"
def staff_life_spent(s):
    return 2*s.exile.count(STAFF_LIFE2)+4*s.exile.count(STAFF_LIFE4)
def staff_can_pay(s,amt):
    return staff_life_spent(s)+amt<40
_previous_key=d.key
def key(s):
    return (_previous_key(s),staff_life_spent(s))
d.key=key

# Dack is a creature and is NOT taxed by Thorn of Amethyst.
# The inherited v0.74 oracle-corrected cast evaluator already excludes Thorn.
_previous_can_cast = d.can_cast_dack
def can_cast_dack(s):
    # A true creature-combo restriction, separate from the mana calculation.
    # This deliberately does NOT require all eight creatures in the library.
    if combo_hand_blocked(s): return False
    if any(p.name == "Thorn of Amethyst" for p in s.battlefield):
        s = replace(s, battlefield=tuple(p for p in s.battlefield if p.name != "Thorn of Amethyst"))
    return _previous_can_cast(s)
d.can_cast_dack = can_cast_dack
# London bottom preference: do not keep both bridge pieces stranded in hand.
_previous_bottom_priority=d.bottom_priority
def bottom_priority(card,seven):
    if COMBO_HAND_BLOCK_PAIR.issubset(set(seven)) and card in COMBO_HAND_BLOCK_PAIR:
        return max(80,_previous_bottom_priority(card,seven))
    return _previous_bottom_priority(card,seven)
d.bottom_priority=bottom_priority

# The inherited oracle-audited engine already handles BOTH Thorn and
# Charitable Levy tax on noncreature spells; never apply those taxes twice.
_previous_cast = d.cast_actions
def _legacy_cast_thorn_correct(s):
    return _previous_cast(s)

# Register actual land output (these 4 lands are not in the legacy tap table).
_original_tap = d.tap_mana_actions
def tap_mana_actions(s):
    # A Mycosynth Gardens COPY of Chrome Mox does not copy its exiled
    # imprinted card; it therefore cannot produce mana.
    out = []
    for q in _original_tap(s):
        fake = any(
            p.name=="The Mycosynth Gardens" and p.aux=="COPY:Chrome Mox"
            and not p.tapped and i<len(q.battlefield)
            and q.battlefield[i].tapped
            for i,p in enumerate(s.battlefield))
        if not fake:out.append(q)
    for i,p in enumerate(s.battlefield):
        if p.tapped:
            continue
        n = d.effective_name(p)
        if n in NEW_LANDS:
            bf = list(s.battlefield)
            bf[i] = replace(p,tapped=True)
            out.append(replace(s,battlefield=tuple(bf),c=s.c+1))
        elif n == "Throne of Eldraine":
            bf = list(s.battlefield); bf[i] = replace(p,tapped=True)
            # The four white mana is restricted to casting monowhite spells.
            # For this phase it is only used to pay for Dack.
            out.append(replace(s,battlefield=tuple(bf),
                               restricted_dack_white=s.restricted_dack_white+4))
        elif n == "Staff of Compleation" and staff_can_pay(s,2):
            bf = list(s.battlefield); bf[i] = replace(p,tapped=True)
            # Pay 2 life and tap: one white (optimally chosen in mono-white).
            out.append(replace(s,battlefield=tuple(bf),w=s.w+1,
                               exile=s.exile+(STAFF_LIFE2,)))
    return d._dedupe(out) if hasattr(d,"_dedupe") else engine._dedupe(out)
d.tap_mana_actions = tap_mana_actions

# Draw/untap engine actions. Card draws use the actual library order.
# Do not model the later expensive Mind Stone harness activation in T1-3.
_original_special = d.special_actions
def special_actions(s):
    out = list(_original_special(s))
    for i,p in enumerate(s.battlefield):
        if p.tapped:
            continue
        n=d.effective_name(p)
        if n=="The One Ring":
            bf=list(s.battlefield)
            burden=p.counters+1
            bf[i]=replace(p,tapped=True,counters=burden)
            out.append(d.draw(replace(s,battlefield=tuple(bf)),burden))
            # Copy Ring's activated ability with Rings for {2}. The copy
            # resolves first (draw after counter n+1), then the original
            # (draw after counter n+2): 2*n+3 cards in total.
            if any(d.effective_name(x)=="Rings of Brighthearth" for x in s.battlefield):
                for paid in d.pay_options(s,2):
                    bb=list(paid.battlefield)
                    bb[i]=replace(bb[i],tapped=True,counters=p.counters+2)
                    out.append(d.draw(replace(paid,battlefield=tuple(bb)),2*p.counters+3))
        elif n=="Staff of Compleation" and staff_can_pay(s,4):
            bf=list(s.battlefield);bf[i]=replace(p,tapped=True)
            out.append(d.draw(replace(s,battlefield=tuple(bf),
                                      exile=s.exile+(STAFF_LIFE4,)),1))
            # Copy draw activation for {2} without paying life twice.
            if any(d.effective_name(x)=="Rings of Brighthearth" for x in s.battlefield):
                for paid in d.pay_options(s,2):
                    bb=list(paid.battlefield);bb[i]=replace(bb[i],tapped=True)
                    out.append(d.draw(replace(paid,battlefield=tuple(bb),
                                      exile=paid.exile+(STAFF_LIFE4,)),2))
        elif n=="Throne of Eldraine":
            # Cost is 3 mana of the chosen color, NOT its own restricted 4W.
            for paid in d.pay_options(s,3,0,0):
                used=(s.w-paid.w)+(s.any-paid.any)
                if used!=3: continue
                bf=list(paid.battlefield);bf[i]=replace(bf[i],tapped=True)
                out.append(d.draw(replace(paid,battlefield=tuple(bf)),2))
                # Copy Throne's draw-two ability if another two generic mana
                # is available; Rings-copy payment is not restricted by Throne.
                if any(d.effective_name(x)=="Rings of Brighthearth" for x in s.battlefield):
                    for copied in d.pay_options(paid,2):
                        bb=list(copied.battlefield);bb[i]=replace(bb[i],tapped=True)
                        out.append(d.draw(replace(copied,battlefield=tuple(bb)),4))
    # Mind Stone's ordinary {1},tap,sacrifice-to-draw is already modeled
    # by the inherited utility_actions. Only add the Rings copied ability
    # here, avoiding duplicate search branches for normal activations.
    if any(d.effective_name(x)=="Rings of Brighthearth" for x in s.battlefield):
        for i,p in enumerate(s.battlefield):
            if d.effective_name(p)!="Mind Stone" or p.tapped:continue
            for pcopy in d.pay_options(s,3):
                bb=list(pcopy.battlefield);src=bb.pop(i)
                out.append(d.draw(replace(pcopy,battlefield=tuple(bb),
                           grave=pcopy.grave+(src.name,)),2))
    # Gleaming Splendor: {2}{W}, target ourselves and one opponent, draw one.
    # Opponent's card is not modeled as a resource on OUR turn.
    if any(d.effective_name(x)=="Gleaming Splendor" for x in s.battlefield):
        tithe=any(d.effective_name(x)=="Smothering Tithe" for x in s.battlefield)
        for paid in d.pay_options(s,2,1):
            # Choose self + one opponent: their draw grants us one Tithe
            # Treasure if Tithe is present under the established no-pay policy.
            out.append(replace(d.draw(paid,1),
                      treasures=paid.treasures+(1 if tithe else 0)))
            if any(d.effective_name(x)=="Rings of Brighthearth" for x in s.battlefield):
                for copied in d.pay_options(paid,2):
                    # The same opponent draws twice in our turn: one
                    # Splendor trigger, plus two Tithe draws if present.
                    out.append(replace(d.draw(copied,2),
                                  treasures=copied.treasures+1+(2 if tithe else 0)))
    # Staff: {5} to untap; non-mana ability can be used multiple times.
    for i,p in enumerate(s.battlefield):
        if d.effective_name(p)!="Staff of Compleation" or not p.tapped:continue
        for paid in d.pay_options(s,5):
            bf=list(paid.battlefield);bf[i]=replace(bf[i],tapped=False)
            out.append(replace(paid,battlefield=tuple(bf)))
    # Rings + Basalt: pay {3} to untap Basalt, copy for {2}; tap
    # Basalt between the two untap resolutions. Requires {2} external
    # resources before starting, but then produces unlimited colorless.
    if (s.c < 12 and
        any(d.effective_name(p)=="Rings of Brighthearth" for p in s.battlefield)
        and any(d.effective_name(p)=="Basalt Monolith" and not p.tapped for p in s.battlefield)):
        for paid in d.pay_options(s,2):
            # Cap the infinite-colorless representation at 12C, avoiding
            # arbitrarily many distinct mana-pool states in bounded search.
            out.append(replace(paid,c=12))
    # Fomori Vault: {3}, T, discard; see X cards (our artifact count),
    # choose one, randomly bottom the others. No card-count gain.
    for fi,f in enumerate(s.battlefield):
        if f.name!="Fomori Vault" or f.tapped or not s.hand:
            continue
        X=sum(d.is_artifact_perm(d.effective_name(x)) for x in s.battlefield)+s.treasures
        if X<1:continue
        for paid in d.pay_options(s,3):
            # The Vault itself must remain untapped after paying the
            # activation cost; it cannot finance its own {3} then tap again.
            if paid.battlefield[fi].tapped:continue
            top=paid.library[:X]
            if not top:continue
            for discard in sorted(set(paid.hand)):
                hh=list(paid.hand);hh.remove(discard)
                for take in sorted(set(top)):
                    remaining=list(top);remaining.remove(take)
                    rnd=random.Random(d._stable_seed(tuple(remaining)+tuple(paid.library[X:]),0xF0A0))
                    rnd.shuffle(remaining)
                    bf=list(paid.battlefield);bf[fi]=replace(bf[fi],tapped=True)
                    out.append(replace(paid,hand=d.sort_hand(hh+[take]),
                            grave=paid.grave+(discard,),battlefield=tuple(bf),
                            library=tuple(paid.library[X:])+tuple(remaining)))
    # Mirage Mirror copying a nonlegendary mana source until end of turn.
    for i,p in enumerate(s.battlefield):
        if p.name!="Mirage Mirror" or p.aux or p.tapped:
            continue
        for ti,t in enumerate(s.battlefield):
            if i==ti:continue
            target=d.effective_name(t)
            if target not in {"Ancient Tomb","City of Traitors","Crystal Vein",
                              "Sol Ring","Mana Vault","Grim Monolith","Basalt Monolith",
                              "Arcane Signet","Fellwar Stone","Mox Diamond",
                              "Mind Stone"}:
                continue
            for paid in d.pay_options(s,2):
                bf=list(paid.battlefield)
                bf[i]=replace(bf[i],aux="COPY:"+target)
                out.append(replace(paid,battlefield=tuple(bf)))
    return engine._dedupe(out)
d.special_actions=special_actions

_old_untap = d.untap_and_begin
def untap_and_begin(s):
    # Copy expiration occurs at the END of the previous turn, before the
    # normal untap step. Otherwise a Mirror copied into Mana Vault/Monolith
    # erroneously skips untapping forever.
    s=replace(s,battlefield=tuple(replace(p,aux="") if p.name=="Mirage Mirror" and
        p.aux.startswith("COPY:") else p for p in s.battlefield))
    return _old_untap(s)
d.untap_and_begin=untap_and_begin

# Rings can copy Voltaic Key's ability for {2}: the original untaps
# another artifact while the copy untaps the tapped Key itself.
# This converts finite colorless into repeatable untaps, including colored
# rocks and The One Ring. Manifold Key cannot target itself.
_base_utility=d.utility_actions
def utility_actions(s):
    out=list(_base_utility(s))
    if any(d.effective_name(p)=="Rings of Brighthearth" for p in s.battlefield):
        for ki,key in enumerate(s.battlefield):
            if key.name!="Voltaic Key" or key.tapped:continue
            for ti,target in enumerate(s.battlefield):
                if ti==ki or not target.tapped or not d.is_artifact_perm(d.effective_name(target)):
                    continue
                for paid in d.pay_options(s,3):
                    bf=list(paid.battlefield)
                    bf[ki]=replace(bf[ki],tapped=False)
                    bf[ti]=replace(bf[ti],tapped=False)
                    out.append(replace(paid,battlefield=tuple(bf)))
    return engine._dedupe(out)
d.utility_actions=utility_actions

# Four-player goldfish assumption, explicitly requested: when Tithe survives
# across a complete opponent cycle, add exactly three Treasures (one per opponent).
# Preserve the inherited independent Gleaming Splendor assumption (+1 per cycle).
# No Treasures are produced immediately upon casting Tithe.
_base_opponent_cycle = d.add_opponent_cycle_resources
TITHE_TREASURES_PER_CYCLE = 3
def add_opponent_cycle_resources(s):
    had_tithe = any(d.effective_name(p) == "Smothering Tithe" for p in s.battlefield)
    q = _base_opponent_cycle(s)
    if had_tithe:
        q = replace(q, treasures=q.treasures + TITHE_TREASURES_PER_CYCLE)
    return q
d.add_opponent_cycle_resources = add_opponent_cycle_resources

def _front_hit(s,card):
    """Resolve Battlefront putting a card onto battlefield without casting."""
    if card=="Chrome Mox":
        outputs=[]
        for imprint in sorted(set(s.hand) & WHITE_IMPRINTS):
            hand=list(s.hand);hand.remove(imprint)
            bf=d.artifact_enters_bf(s.battlefield,d.Perm(card,False,0,s.turn))
            outputs.append(replace(s,hand=d.sort_hand(hand),exile=s.exile+(imprint,),battlefield=bf))
        # The inherited Chrome Mox mana method assumes an imprinted white
        # spell. Until un-imprinted Mox is represented as a distinct artifact
        # state, omit this non-mana Battlefront hit instead of falsely granting W.
        return outputs
    if card=="Mox Diamond":
        outputs=[]
        for land in sorted(set(s.hand)&set(d.LANDS)):
            hand=list(s.hand);hand.remove(land)
            bf=d.artifact_enters_bf(s.battlefield,d.Perm(card,False,0,s.turn))
            outputs.append(replace(s,hand=d.sort_hand(hand),grave=s.grave+(land,),battlefield=bf))
        return outputs
    bf=d.artifact_enters_bf(s.battlefield,d.Perm(card,False,0,s.turn,
                       loyalty=4 if card=="Tezzeret, Cruel Captain" else 0))
    return [replace(s,battlefield=bf)]

def battlefront_actions(s):
    if "United Battlefront" not in s.hand:
        return []
    if not d.stax_allows(s,"United Battlefront",is_artifact=False):
        return []
    cost_g,cost_w,_ = BATTLEFRONT_COST
    if any(p.name=="Thorn of Amethyst" for p in s.battlefield):
        cost_g+=1
    if any(p.name=="Trinisphere" for p in s.battlefield):
        cost_g=max(cost_g,3-cost_w)
    if any(p.name=="Charitable Levy" for p in s.battlefield):
        cost_g+=1
    results=[]
    for paid in d.pay_options(s,cost_g,cost_w):
        if not d.payment_stax_ok(s,paid):continue
        hand=list(paid.hand); hand.remove("United Battlefront")
        base=replace(paid,hand=d.sort_hand(hand),grave=paid.grave+("United Battlefront",),
                     spells=paid.spells+1,nonartifact_spells=paid.nonartifact_spells+1,
                     noncreature_spells=paid.noncreature_spells+1)
        window=base.library[:7]
        tail=base.library[7:]
        hit_ids=[j for j,name in enumerate(window) if name in ELIGIBLE_BATTLEFRONT]
        # All 0/1/2 candidate choices, including putting nothing into play.
        for k in range(min(2,len(hit_ids))+1):
            for selected in combinations(hit_ids,k):
                chosen=[window[j] for j in selected]
                rest=[window[j] for j in range(len(window)) if j not in selected]
                # Opponent doesn't control bottom order; deterministic shuffle
                # is intentionally keyed from this library state.
                rng=random.Random(d._stable_seed(tuple(rest)+tuple(tail),0xB477))
                rng.shuffle(rest)
                states=[replace(base,library=tuple(tail)+tuple(rest))]
                for name in chosen:
                    states=[next_state for z in states for next_state in _front_hit(z,name)]
                results.extend(states)
    return engine._dedupe(results)

# The inherited v0.74-v0.77 spell engine already applies Levy tax,
# counter accumulation, draw, and Plains-to-battlefield. Do not duplicate.
# Only genuinely new sorcery/cantrip branches are added here.
def _cast_cantrip_actions(s):
    costs={"Scout's Warning":(0,1),"Abeyance":(1,1)}
    out=[]
    levy=any(d.effective_name(p)=="Charitable Levy" for p in s.battlefield)
    thorn=any(d.effective_name(p)=="Thorn of Amethyst" for p in s.battlefield)
    trini=any(d.effective_name(p)=="Trinisphere" for p in s.battlefield)
    for card,(g,w) in costs.items():
        if card not in s.hand or not d.stax_allows(s,card):continue
        if thorn:g+=1
        if levy:g+=1
        if trini:g=max(g,3-w)
        for paid in d.pay_options(s,g,w):
            if not d.payment_stax_ok(s,paid):continue
            h=list(paid.hand);h.remove(card)
            q=d.draw(replace(paid,hand=d.sort_hand(h),
                       grave=paid.grave+(card,),spells=paid.spells+1,
                       noncreature_spells=paid.noncreature_spells+1,
                       nonartifact_spells=paid.nonartifact_spells+1),1)
            # Levy triggered by casting the cantrip: its trigger resolves
            # before the spell, but both draws are represented in net state.
            if levy:
                q=_apply_new_noncreature_levy_trigger(s,q)
            out.append(q)
    return out

def _apply_new_noncreature_levy_trigger(s,q):
    ix=next((i for i,x in enumerate(q.battlefield)
             if d.effective_name(x)=="Charitable Levy"),None)
    if ix is None:return q
    bf=list(q.battlefield)
    counter=bf[ix].counters+1
    if counter<3:
        bf[ix]=replace(bf[ix],counters=counter)
        return replace(q,battlefield=tuple(bf))
    bf.pop(ix)
    q=d.draw(replace(q,battlefield=tuple(bf),
                     grave=q.grave+("Charitable Levy",)),1)
    if "Plains" in q.library:
        lib=list(q.library);lib.remove("Plains")
        return replace(q,library=d.shuffled_unknown(lib),
                   battlefield=q.battlefield+(d.Perm("Plains",True,0,s.turn),))
    return q

def cast_actions(s):
    raw=list(_previous_cast(s))
    # Battlefront itself is a noncreature spell and triggers Levy.
    for z in battlefront_actions(s):
        raw.append(_apply_new_noncreature_levy_trigger(s,z)
                   if any(p.name=="Charitable Levy" for p in s.battlefield) else z)
    raw.extend(_cast_cantrip_actions(s))
    return engine._dedupe(raw)
d.cast_actions = cast_actions

def build_deck(variant="baseline"):
    cards=list(BASE_DECK)
    if variant=="baseline":
        pass
    elif variant=="battlefront_over_prismatic":
        cards[cards.index("Prismatic Lens")]="United Battlefront"
    elif variant=="battlefront_over_amulet":
        cards[cards.index("Jeweled Amulet")]="United Battlefront"
    else:
        raise ValueError(variant)
    assert len(cards)==99
    return tuple(cards)

def install(variant="baseline"):
    deck=build_deck(variant)
    engine.set_deck(deck)
    return deck

def selftest():
    assert len(BASE_DECK)==99
    assert "Radiant Solar" not in WHITE_IMPRINTS
    assert not combo_hand_blocked(d.State(1,("Abdel Adrian, Gorion's Ward",),()))
    assert not combo_hand_blocked(d.State(1,("Radiant Solar",),()))
    assert combo_hand_blocked(d.State(1,("Abdel Adrian, Gorion's Ward","Radiant Solar"),()))
    assert not can_cast_dack(d.State(1,("Abdel Adrian, Gorion's Ward","Radiant Solar"),(),w=2,c=4))
    assert can_cast_dack(d.State(1,("Abdel Adrian, Gorion's Ward",),(),w=2,c=4))
    assert all(c in WHITE_IMPRINTS for c in CREATURES if c!="Radiant Solar")
    assert all(c in WHITE_IMPRINTS for c in MDFC)
    assert not d.chrome_mox_allowed("Ancient Den")
    assert not d.chrome_mox_allowed("The One Ring")
    assert not d.chrome_mox_allowed("Radiant Solar")
    assert all(d.chrome_mox_allowed(c) for c in WHITE_IMPRINTS)
    # 3 generic + 1 white = exactly FOUR total mana. White is mandatory.
    assert BATTLEFRONT_COST==(3,1,0)
    assert sum(BATTLEFRONT_COST)==4
    bf_top=("Sol Ring","Arcane Signet","Plains","Felidar Guardian",
            "The One Ring","Prismatic Lens","Blind Obedience")
    assert not battlefront_actions(d.State(1,("United Battlefront",),bf_top,w=1,c=2))
    assert not battlefront_actions(d.State(1,("United Battlefront",),bf_top,w=0,c=4))
    assert battlefront_actions(d.State(1,("United Battlefront",),bf_top,w=1,c=3))
    # Battlefront costs five total under Levy, not four.
    tax=(d.Perm("Charitable Levy"),)
    assert not battlefront_actions(d.State(1,("United Battlefront",),bf_top,
                                             battlefield=tax,w=1,c=3))
    assert battlefront_actions(d.State(1,("United Battlefront",),bf_top,
                                         battlefield=tax,w=1,c=4))
    # Tithe creates no mana on entry: only an opponent cycle adds the modeled 3.
    no_tithe=d.State(1,(),(),treasures=1)
    tithe=replace(no_tithe,battlefield=(d.Perm("Smothering Tithe"),))
    assert add_opponent_cycle_resources(no_tithe).treasures==1
    assert tithe.treasures==1
    assert add_opponent_cycle_resources(tithe).treasures==4
    both=replace(tithe,battlefield=(d.Perm("Smothering Tithe"),d.Perm("Gleaming Splendor")))
    assert add_opponent_cycle_resources(both).treasures==5
    assert "The One Ring" not in ELIGIBLE_BATTLEFRONT
    assert "Throne of Eldraine" not in ELIGIBLE_BATTLEFRONT
    assert all(c not in ELIGIBLE_BATTLEFRONT for c in CREATURES)
    assert d.is_artifact_perm("The One Ring")
    assert not d.is_artifact_perm("Smothering Tithe")
    assert all(c in d.CARD_ID for c in BASE_DECK)
    assert all(c in d.LANDS for c in NEW_LANDS)
    # Chrome Mox can imprint flicker creatures, but not Radiant Solar.
    ss=d.State(1,("Chrome Mox","Felidar Guardian","Radiant Solar"),())
    casts=[q for q in d.cast_actions(ss) if any(x.name=="Chrome Mox" for x in q.battlefield)]
    assert any("Felidar Guardian" in q.exile for q in casts)
    assert all("Radiant Solar" not in q.exile for q in casts)
    # Thorn taxes artifact spells, including Sol Ring, by one generic mana.
    ss=d.State(1,("Sol Ring",),(),battlefield=(d.Perm("Thorn of Amethyst"),),c=1)
    assert not any(any(x.name=="Sol Ring" for x in q.battlefield) for q in d.cast_actions(ss))
    # Rings + Basalt cannot supply colorless without two extra mana.
    ss=d.State(1,(),(),battlefield=(d.Perm("Rings of Brighthearth"),d.Perm("Basalt Monolith")))
    assert not any(q.c==12 for q in d.special_actions(ss))
    ss=replace(ss,c=2)
    assert any(q.c==12 for q in d.special_actions(ss))
    # Creature commander must not be taxed by Thorn.
    s=d.State(1,(),(),battlefield=(d.Perm("Thorn of Amethyst"),),w=2,c=4)
    assert d.can_cast_dack(s)
    # Throne's mana can cast Dack but cannot be converted into ordinary W.
    s=d.State(2,(),(),battlefield=(d.Perm("Throne of Eldraine"),),c=2)
    x=[q for q in d.tap_mana_actions(s) if q.restricted_dack_white==4]
    assert x and all(q.w==0 for q in x)
    # Staff is a zero-mana activation with a life payment, not a {1} tax.
    s=d.State(2,(),(),battlefield=(d.Perm("Staff of Compleation"),))
    assert any(q.w==1 for q in d.tap_mana_actions(s))
    # Draw engines must be reached from their actual cast-in-hand
    # actions, not just work when pre-seeded onto the battlefield.
    ring_start=d.State(1,("The One Ring",),("Mana Vault","Plains"),
                       c=4)
    ring_casts=[q for q in d.cast_actions(ring_start)
                if any(p.name=="The One Ring" for p in q.battlefield)]
    assert ring_casts, "The One Ring cannot be cast from hand"
    assert any("Mana Vault" in z.hand
        for q in ring_casts for z in d.special_actions(q)), (
        "The One Ring cast -> tap -> actual draw path missing")
    throne_start=d.State(2,("Throne of Eldraine",),("Sol Ring","Mana Vault"),
                        c=5)
    throne_casts=[q for q in d.cast_actions(throne_start)
                  if any(p.name=="Throne of Eldraine" for p in q.battlefield)]
    assert throne_casts, "Throne of Eldraine cannot be cast from hand"
    assert any(z.restricted_dack_white==4 for q in throne_casts
        for z in d.tap_mana_actions(q)), (
        "Throne of Eldraine cast -> four restricted white missing")
    throne_draw_start=d.State(2,(),("Sol Ring","Mana Vault"),
                        battlefield=(d.Perm("Throne of Eldraine"),),w=3)
    assert any(len(z.hand)==2 for z in d.special_actions(throne_draw_start)), (
        "Throne of Eldraine three-white -> draw-two path missing")
    # The One Ring places burden counter BEFORE drawing.
    s=d.State(2,(),("Plains","Sol Ring"),battlefield=(d.Perm("The One Ring"),))
    q=[z for z in d.special_actions(s) if z.hand==("Plains",)]
    assert q and any(z.battlefield[0].counters==1 for z in q)
    # Every mana-producer card in the frozen deck must have a behavior
    # that can generate mana in a suitable witness state.
    representative={"Ancient Den","Ancient Tomb","Arcane Signet",
        "Basalt Monolith","Blast Zone","Cavern of Souls","Chrome Mox",
        "City of Traitors","Command Beacon","Crystal Vein",
        "Eiganjo, Seat of the Empire","Emergence Zone","Fellwar Stone",
        "Fomori Vault","Gemstone Caverns","Great Hall of the Citadel",
        "Grim Monolith","Jeweled Amulet","Mana Vault","Mind Stone",
        "Mishra's Workshop","Mox Diamond","Petrified Hamlet",
        "Plains","Prismatic Lens","Remote Farm","Ruins of Trokair",
        "Sol Ring","Staff of Compleation","Talon Gates of Madara",
        "The Mind Stone","The Mycosynth Gardens","Throne of Eldraine",
        "Urza's Cave","Urza's Saga"}
    assert representative <= set(BASE_DECK)
    for mana_name in representative - {"Jeweled Amulet"}:
        witness=d.State(2,(),(),battlefield=(d.Perm(mana_name,False,
                     2 if mana_name=="Remote Farm" else 1),))
        assert any(z.w+z.c+z.any+z.restricted_artifact+
                   z.restricted_legend+z.restricted_dack_white > 0
                   for z in d.tap_mana_actions(witness)),mana_name
    # Conditional acceleration: these require specific supporting permanents.
    s=d.State(1,(),(),battlefield=(d.Perm("Lotus Petal"),))
    assert any(q.w>=1 and "Lotus Petal" in q.grave for q in d.tap_mana_actions(s))
    s=d.State(1,(),(),battlefield=(d.Perm("Lion's Eye Diamond"),))
    assert any(q.w>=3 for q in d.tap_mana_actions(s))
    s=d.State(1,(),(),battlefield=(d.Perm("Mox Opal"),d.Perm("Sol Ring"),d.Perm("Arcane Signet")))
    assert any(q.w+q.any>=1 for q in d.tap_mana_actions(s))
    s=d.State(1,(),(),battlefield=(d.Perm("Krark-Clan Ironworks"),d.Perm("Sol Ring")))
    assert any(q.c>=2 and "Sol Ring" in q.grave for q in d.utility_actions(s))
    s=d.State(1,(),(),battlefield=(d.Perm("Jeweled Amulet",False,1,aux="W"),))
    assert any(q.w>=1 for q in d.tap_mana_actions(s))
    # Throne's draw ability requires three WHITE, never three colorless.
    s=d.State(2,(),("Plains","Sol Ring"),battlefield=(d.Perm("Throne of Eldraine"),),c=3)
    assert not any(len(q.hand)>0 for q in d.special_actions(s))
    s=replace(s,c=0,w=3)
    assert any(len(q.hand)==2 for q in d.special_actions(s))
    # Staff can pay 4 life to draw at most nine times in 40-life goldfish.
    assert staff_can_pay(d.State(1,(),(),exile=(STAFF_LIFE4,)*8),4)
    assert not staff_can_pay(d.State(1,(),(),exile=(STAFF_LIFE4,)*9),4)
    assert not staff_can_pay(d.State(1,(),(),exile=(STAFF_LIFE4,)*9),2*2)
    # Staff draws one card and taps; it does not require mana for that mode.
    s=d.State(1,(),("Mana Vault",),battlefield=(d.Perm("Staff of Compleation"),))
    assert any("Mana Vault" in q.hand and q.battlefield[0].tapped
               for q in d.special_actions(s))
    # Fomori Vault converts a card and 3 mana into top-X selection.
    ss=d.State(2,("Plains",),("Mana Vault","Arcane Signet","Sol Ring"),
        battlefield=(d.Perm("Fomori Vault"),d.Perm("Mind Stone")),c=3)
    assert any("Mana Vault" in q.hand and "Plains" in q.grave
        for q in d.special_actions(ss))
    # Rings can copy Ring to draw three on a zero-burden activation.
    ss=d.State(2,(),("Plains","Sol Ring","Mana Vault"),
        battlefield=(d.Perm("Rings of Brighthearth"),d.Perm("The One Ring")),c=2)
    assert any(q.battlefield[1].counters==2 and len(q.hand)==3
        for q in d.special_actions(ss))
    # Vault cannot spend its own mana to pay {3} then activate.
    sf=d.State(2,("Plains",),("Mana Vault","Arcane Signet"),
        battlefield=(d.Perm("Fomori Vault"),d.Perm("Sol Ring")),c=2)
    assert not any("Mana Vault" in q.hand for q in d.special_actions(sf))
    # A Gardens copy of Chrome Mox has no imprinted card, so cannot add W.
    copied=d.State(1,(),(),battlefield=(d.Perm("The Mycosynth Gardens",aux="COPY:Chrome Mox"),))
    assert not any(q.w>0 for q in d.tap_mana_actions(copied))
    # Mirage Mirror resumes ordinary untapping after copied Monolith text expires.
    sm=d.State(1,(),(),battlefield=(d.Perm("Mirage Mirror",True,aux="COPY:Mana Vault"),))
    sn=d.untap_and_begin(sm)
    assert sn.battlefield[0].aux=="" and not sn.battlefield[0].tapped
    # Battlefront Chrome Mox with no eligible imprint is NEVER a white source.
    so=d.State(1,(),())
    assert _front_hit(so,"Chrome Mox")==[]
    # Rings/Voltaic untaps itself (as well as the selected tapped rock).
    ss=d.State(2,(),(),battlefield=(d.Perm("Rings of Brighthearth"),
        d.Perm("Voltaic Key"),d.Perm("Arcane Signet",True)),c=3)
    assert any(not q.battlefield[1].tapped and not q.battlefield[2].tapped
        for q in d.utility_actions(ss))
    # Mind Stone sac-for-draw comes from the already-correct inherited
    # utility engine; do not model it twice in special_actions.
    s=d.State(1,(),("Plains",),battlefield=(d.Perm("Mind Stone"),),c=1)
    assert any("Plains" in q.hand and "Mind Stone" in q.grave
               and not q.battlefield for q in d.utility_actions(s))
    # Gleaming Splendor is real draw, not merely passive Treasures.
    s=d.State(1,(),("Plains",),battlefield=(d.Perm("Gleaming Splendor"),),w=1,c=2)
    assert any("Plains" in q.hand for q in d.special_actions(s))
    # Gleaming plus Tithe: our activated self/opponent draw makes a
    # Treasure for the opponent draw in addition to passive cycles.
    sb=d.State(2,(),("Plains",),battlefield=(
        d.Perm("Gleaming Splendor"),d.Perm("Smothering Tithe")),w=1,c=2)
    assert any("Plains" in z.hand and z.treasures==1 for z in d.special_actions(sb))
    # Untap Staff costs FIVE generic, never five life.
    s=d.State(1,(),(),battlefield=(d.Perm("Staff of Compleation",True),),c=5)
    assert any(not q.battlefield[0].tapped and q.c==0 for q in d.special_actions(s))
    # Inherited Levy handles costs/triggers once, not twice.
    s=d.State(1,("Sol Ring",),("Plains","Arcane Signet"),
              battlefield=(d.Perm("Charitable Levy",False,2),),c=2)
    assert any("Charitable Levy" in q.grave and "Plains" in q.hand
               for q in d.cast_actions(s))
    # Test at exactly the threshold to catch accidental double spell taxes.
    ss=d.State(1,("Sol Ring",),(),battlefield=(d.Perm("Thorn of Amethyst"),),c=2)
    assert any(p.name=="Sol Ring" for q in d.cast_actions(ss) for p in q.battlefield)
    # Two real cantrips: Scout's Warning W, Abeyance 1W.
    ss=d.State(1,("Scout's Warning",),("Mana Vault",),w=1)
    assert any("Mana Vault" in q.hand for q in d.cast_actions(ss))
    ss=d.State(1,("Abeyance",),("Plains",),w=1,c=1)
    assert any("Plains" in q.hand for q in d.cast_actions(ss))
    # Battlefront 3W can hit two eligible permanents directly into play.
    s=d.State(2,("United Battlefront",),
        ("Sol Ring","Arcane Signet","Plains","Felidar Guardian","The One Ring","Prismatic Lens","Blind Obedience"),
        w=1,c=3)
    targets=[z for z in d.battlefront_actions(s)] if hasattr(d,"battlefront_actions") else battlefront_actions(s)
    assert targets and any({"Sol Ring","Arcane Signet"} <=
        {p.name for p in z.battlefield} for z in targets)
    assert any("Felidar Guardian" in z.library for z in targets)
    return True

if __name__=="__main__":
    import argparse
    a=argparse.ArgumentParser()
    a.add_argument("--audit",action="store_true")
    a.add_argument("--variant",default="baseline")
    opts=a.parse_args()
    install(opts.variant)
    assert selftest()
    print("DACK_FLICKER_V078_FOCUSED_AUDIT_PASS",opts.variant,flush=True)
