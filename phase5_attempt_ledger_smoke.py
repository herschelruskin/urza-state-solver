#!/usr/bin/env python3
"""Exact packed attempted-action ledger regression."""

from decision_observation import ActionIntent
from non_oracle_episode import (
    _fresh_actions_from_attempt_ledger,
    _record_attempt,
)


def action(action_id,equiv):
    return ActionIntent(
        action_id=action_id,
        kind="test_action",
        equivalence_key=equiv,
        label=action_id,
    )


def main():
    a=action("exec-a",("same",1))
    b=action("exec-b",("same",1))
    c=action("exec-c",("other",2))

    fresh,blob,mask,index=_fresh_actions_from_attempt_ledger((a,b,c),None)
    assert fresh==(a,b,c)
    assert mask==0
    assert len(index)==2  # a/b share one strategic equivalence class

    ledger=_record_attempt(a,blob,mask,index)
    fresh2,blob2,mask2,index2=_fresh_actions_from_attempt_ledger((c,b,a),ledger)
    assert blob2==blob
    assert mask2==ledger[1]
    assert fresh2==(c,)  # equivalent b is excluded after attempting a

    ledger2=_record_attempt(c,blob2,mask2,index2)
    fresh3,_,_,_=_fresh_actions_from_attempt_ledger((a,c,b),ledger2)
    assert fresh3==()

    d=action("exec-d",("new",3))
    try:
        _fresh_actions_from_attempt_ledger((a,b,c,d),ledger)
    except AssertionError:
        pass
    else:
        raise AssertionError("strategic action-set drift was silently remapped")

    print("packed attempt ledger preserves strategic equivalence classes: PASS")
    print("action ordering cannot change bit positions: PASS")
    print("same-cycle strategic action-set drift fails loudly: PASS")


if __name__=="__main__":
    main()
