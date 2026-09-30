"""Speed-only Thought Vessel patch for paired land->2-drop tests.
Oracle: {2} Artifact; no maximum hand size; T: Add C.
The hand-size ability is irrelevant to the turn-3 Dack objective.
"""
from dataclasses import replace
import dack_v075_current99 as v

d=v.d
NAME="Thought Vessel"

if NAME not in d.CARD_ID:
    nid=max(d.CARD_ID.values(),default=-1)+1
    d.CARD_ID[NAME]=nid
    d.ID_CARD[nid]=NAME

d.COSTS[NAME]=(2,0,0)
d.RAMP_PROTECTED=frozenset(set(d.RAMP_PROTECTED)|{NAME})
d.MOONSILVER_MANA_ARTIFACTS=frozenset(set(d.MOONSILVER_MANA_ARTIFACTS)|{NAME})

_prev_artifact=d.is_artifact_perm
def is_artifact_perm(name):
    return name==NAME or _prev_artifact(name)
d.is_artifact_perm=is_artifact_perm

_prev_tap=d.tap_mana_actions
def tap_mana_actions(s):
    out=list(_prev_tap(s))
    for i,p in enumerate(s.battlefield):
        if d.effective_name(p)==NAME and not p.tapped:
            bf=list(s.battlefield); bf[i]=replace(p,tapped=True)
            out.append(replace(s,battlefield=tuple(bf),c=s.c+1))
    return _dedupe(out)
d.tap_mana_actions=tap_mana_actions

_prev_v03=d.v03_actions
def v03_actions(s):
    out=list(_prev_v03(s))
    if any(x.name=="The Mycosynth Gardens" and not x.tapped and not x.aux for x in s.battlefield):
        if any(d.effective_name(x)==NAME for x in s.battlefield):
            for paid in d.pay_options(s,2):
                gi=next((j for j,x in enumerate(paid.battlefield)
                         if x.name=="The Mycosynth Gardens" and not x.tapped and not x.aux),None)
                if gi is None: continue
                if not any(d.effective_name(x)==NAME for j,x in enumerate(paid.battlefield) if j!=gi):
                    continue
                bf=list(paid.battlefield)
                bf[gi]=replace(bf[gi],tapped=True,aux="COPY:"+NAME)
                out.append(replace(paid,battlefield=tuple(bf)))
    return _dedupe(out)
d.v03_actions=v03_actions

_prev_score=d.score
def score(s):
    z=_prev_score(s)
    for p in s.battlefield:
        if d.effective_name(p)==NAME and not p.tapped:
            z+=24
    return z
d.score=score

def _dedupe(states):
    seen=set(); out=[]
    for q in states:
        k=d.key(q)
        if k not in seen:
            seen.add(k); out.append(q)
    return out

def clear_caches():
    v.clear_caches()

def selftest():
    from dataclasses import replace
    assert d.COSTS[NAME]==(2,0,0)
    assert d.is_artifact_perm(NAME)
    assert NAME in d.MOONSILVER_MANA_ARTIFACTS
    s=d.State(1,(),(),(d.Perm(NAME),))
    outs=d.tap_mana_actions(s)
    assert any(q.c==1 and any(x.name==NAME and x.tapped for x in q.battlefield) for q in outs)
    s=d.State(1,(),(),(d.Perm("The Mycosynth Gardens"),d.Perm(NAME)),c=2)
    assert any(any(x.aux=="COPY:"+NAME for x in q.battlefield) for q in d.v03_actions(s))
    return True
