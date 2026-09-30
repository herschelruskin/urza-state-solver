"""v0.76: classify Pearl Medallion correctly as an artifact.

No Oracle behavior changes beyond artifact identity.  Pearl's cost-reduction
effect and mana cost were already modeled in v0.75.
"""
import dack_v075_current99 as v

d=v.d
_prev_artifact=d.is_artifact_perm

def is_artifact_perm(name):
    return name=="Pearl Medallion" or _prev_artifact(name)

d.is_artifact_perm=is_artifact_perm

def clear_caches():
    v.clear_caches()

def selftest():
    assert v.selftest()
    assert d.is_artifact_perm("Pearl Medallion")

    # Pearl now counts toward metalcraft.
    s=d.State(1,(),(),(
        d.Perm("Pearl Medallion"),
        d.Perm("Sol Ring"),
        d.Perm("Mox Opal"),
    ))
    assert d.metalcraft(s), "Pearl must count for Mox Opal metalcraft"

    # Artifact-only mana can pay for Pearl.
    s=d.State(1,("Pearl Medallion",),(),restricted_artifact=2)
    assert any(any(x.name=="Pearl Medallion" for x in q.battlefield)
               for q in d._cast_actions_ranked(s,0)), "Workshop-style artifact mana must cast Pearl"

    # Pearl entering is another artifact for Tezzeret's +1 trigger.
    s=d.State(1,("Pearl Medallion",),(),(
        d.Perm("Tezzeret, Cruel Captain",loyalty=4),
    ),c=2)
    outs=d._cast_actions_ranked(s,0)
    assert any(any(x.name=="Tezzeret, Cruel Captain" and x.loyalty==5
                       for x in q.battlefield)
               for q in outs), "Pearl ETB must trigger Tezzeret"
    return True

if __name__=="__main__":
    print("selftest:", "PASS" if selftest() else "FAIL")
