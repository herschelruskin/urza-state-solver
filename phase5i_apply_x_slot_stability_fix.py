#!/usr/bin/env python3
"""One-time source patch for stable Reshape/Whir permanent commitments.

Public PermanentSlot descriptors intentionally encode observable state. They are
valid for choosing a permanent, but mutable fields such as tapped/refund-credit
must not be used to re-identify that permanent after paying costs. Resolve the
committed battlefield indices before any cost mutation, then carry those stable
indices through payment.
"""

from pathlib import Path


def replace_once(path, old, new):
    p=Path(path)
    text=p.read_text(encoding="utf-8")
    if new in text:
        print(f"{path}: already patched")
        return
    if old not in text:
        raise SystemExit(f"{path}: patch anchor missing")
    p.write_text(text.replace(old,new,1),encoding="utf-8")
    print(f"{path}: patched")


# Phase-1 Reshape: identify sacrifice before pay() can mutate public fields.
replace_once(
    "x_artifact_search_adapter.py",
    '''    slot = _slot_from_parameter(tuple(params["sacrifice"]))\n\n    paid = solver.pay(state, generic, 2)\n    if paid is None:\n        raise ValueError("Reshape mana cost could not be paid")\n''',
    '''    slot = _slot_from_parameter(tuple(params["sacrifice"]))\n    # The additional-cost permanent is chosen before costs are paid.  Its\n    # observable slot fields may change while paying mana (for example a\n    # producer refund credit can be consumed), but pay() never reorders or\n    # removes battlefield permanents.  Resolve identity now and carry the\n    # stable battlefield index through payment.\n    index = _slot_index(state, slot)\n\n    paid = solver.pay(state, generic, 2)\n    if paid is None:\n        raise ValueError("Reshape mana cost could not be paid")\n'''
)
replace_once(
    "x_artifact_search_adapter.py",
    '''    index = _slot_index(paid, slot)\n    paid = solver.remove_perm(paid, index)\n''',
    '''    paid = solver.remove_perm(paid, index)\n'''
)

# Phase-1 Whir: resolve all slots before tapping the first one.  Otherwise two
# identical untapped artifacts change occurrence numbering after the first tap.
replace_once(
    "x_artifact_search_adapter.py",
    '''    paid = solver.pay(state, 0, 3)\n    if paid is None:\n        raise ValueError("Whir colored cost could not be paid")\n    for slot in slots:\n        index = _slot_index(paid, slot)\n        if paid.battlefield[index].tapped or not solver.is_artifact_perm(\n            paid.battlefield[index]\n        ):\n            raise ValueError("committed improvise object is no longer legal")\n        paid = solver.update_perm(paid, index, tapped=True)\n''',
    '''    paid = solver.pay(state, 0, 3)\n    if paid is None:\n        raise ValueError("Whir colored cost could not be paid")\n    # Resolve the complete committed improvise set before mutating any member.\n    # This keeps duplicate public slots stable when tapping one would otherwise\n    # renumber the remaining identical untapped objects.\n    indices = tuple(_slot_index(paid, slot) for slot in slots)\n    for index in indices:\n        if paid.battlefield[index].tapped or not solver.is_artifact_perm(\n            paid.battlefield[index]\n        ):\n            raise ValueError("committed improvise object is no longer legal")\n        paid = solver.update_perm(paid, index, tapped=True)\n'''
)

# Typed Phase-2 Reshape mirrors the same commitment semantics.
replace_once(
    "non_oracle_x_artifact_tutor_runtime.py",
    '''        slot = _slot_from_parameter(tuple(params["sacrifice"]))\n        index = _slot_index(paid, slot)\n        if not solver.is_artifact_perm(paid.battlefield[index]):\n''',
    '''        slot = _slot_from_parameter(tuple(params["sacrifice"]))\n        # Recover the committed source from the pre-payment state.  pay() can\n        # mutate public permanent annotations but preserves battlefield order.\n        index = _slot_index(state, slot)\n        if not solver.is_artifact_perm(paid.battlefield[index]):\n'''
)

# Typed Phase-2 Whir mirrors the duplicate-slot fix.
replace_once(
    "non_oracle_x_artifact_tutor_runtime.py",
    '''        for raw in tuple(params["improvise"]):\n            slot = _slot_from_parameter(tuple(raw))\n            index = _slot_index(paid, slot)\n            if paid.battlefield[index].tapped or not solver.is_artifact_perm(paid.battlefield[index]):\n                raise ValueError("committed Whir improvise permanent is no longer legal")\n            paid = solver.update_perm(paid, index, tapped=True)\n''',
    '''        slots = tuple(\n            _slot_from_parameter(tuple(raw))\n            for raw in tuple(params["improvise"])\n        )\n        indices = tuple(_slot_index(paid, slot) for slot in slots)\n        for index in indices:\n            if paid.battlefield[index].tapped or not solver.is_artifact_perm(paid.battlefield[index]):\n                raise ValueError("committed Whir improvise permanent is no longer legal")\n            paid = solver.update_perm(paid, index, tapped=True)\n'''
)

# Phase-1 regressions.
p=Path("x_artifact_search_adapter_smoke.py")
text=p.read_text(encoding="utf-8")
if "test_reshape_sacrifice_identity_survives_payment_annotation_change" not in text:
    anchor='''def test_reshape_search_cannot_retroactively_raise_x_for_hidden_target():\n'''
    test='''def test_reshape_sacrifice_identity_survives_payment_annotation_change():\n    state = solver.State(\n        turn=2,\n        library=("Mana Vault", "Tail"),\n        hand=(RESHAPE,),\n        battlefield=(\n            solver.Perm(\n                "Grinding Station", tapped=True, producer_urza_ready=True\n            ),\n        ),\n        blue=2,\n        colorless=0,\n        rng_root_seed=20260822,\n    )\n    info = InformationState()\n    cast = choose_reshape_cast(\n        reshape_cast_request(state, info, horizon=6), 0, "Grinding Station"\n    )\n    envelope, _, _ = resolve_reshape_cast(state, cast)\n    assert not any(p.name == "Grinding Station" for p in envelope.true_state.battlefield)\n    print("Reshape sacrifice survives payment-side annotation change: PASS")\n\n\n'''
    if anchor not in text: raise SystemExit("adapter smoke Reshape anchor missing")
    text=text.replace(anchor,test+anchor,1)
if "test_whir_duplicate_improvise_slots_survive_first_tap" not in text:
    anchor='''def test_whir_exposes_distinct_public_payment_plans_without_hidden_target():\n'''
    test='''def test_whir_duplicate_improvise_slots_survive_first_tap():\n    state = solver.State(\n        turn=2,\n        library=("Grim Monolith", "Tail"),\n        hand=(WHIR,),\n        battlefield=(clue(), clue()),\n        blue=3,\n        colorless=0,\n        rng_root_seed=20260822,\n    )\n    request = whir_cast_request(state, InformationState(), horizon=6)\n    cast = choose_whir_cast(\n        request, 2, improvise_names=("Clue", "Clue"), floating_generic=0\n    )\n    envelope, _, _ = resolve_whir_cast(state, cast)\n    assert len(envelope.true_state.battlefield) == 2\n    assert all(p.tapped for p in envelope.true_state.battlefield)\n    print("Whir duplicate improvise slots remain addressable: PASS")\n\n\n'''
    if anchor not in text: raise SystemExit("adapter smoke Whir anchor missing")
    text=text.replace(anchor,test+anchor,1)
text=text.replace(
    '''        test_reshape_x_and_sacrifice_are_committed_before_search,\n        test_reshape_search_cannot_retroactively_raise_x_for_hidden_target,\n''',
    '''        test_reshape_x_and_sacrifice_are_committed_before_search,\n        test_reshape_sacrifice_identity_survives_payment_annotation_change,\n        test_reshape_search_cannot_retroactively_raise_x_for_hidden_target,\n'''
)
text=text.replace(
    '''        test_whir_improvise_plan_is_committed_before_search,\n        test_whir_exposes_distinct_public_payment_plans_without_hidden_target,\n''',
    '''        test_whir_improvise_plan_is_committed_before_search,\n        test_whir_duplicate_improvise_slots_survive_first_tap,\n        test_whir_exposes_distinct_public_payment_plans_without_hidden_target,\n'''
)
p.write_text(text,encoding="utf-8")

# Typed runtime regressions exercise the same two failure modes through the real
# Phase-2 action bridge.
p=Path("x_artifact_tutor_runtime_smoke.py")
text=p.read_text(encoding="utf-8")
if "test_runtime_reshape_sacrifice_survives_payment_annotation_change" not in text:
    anchor='''def test_reshape_prized_statue_dies_trigger_is_above_spell():\n'''
    test='''def test_runtime_reshape_sacrifice_survives_payment_annotation_change():\n    runtime = make_runtime_state(solver.State(\n        turn=3,\n        library=("Mana Vault", "Island"),\n        hand=("Reshape",),\n        battlefield=(\n            solver.Perm(\n                "Grinding Station", tapped=True, producer_urza_ready=True\n            ),\n        ),\n        blue=2,\n        colorless=0,\n    ))\n    action = next(\n        a for a in x_actions(runtime, "Reshape", 0)\n        if dict(a.parameters).get("sacrifice_name") == "Grinding Station"\n    )\n    runtime = apply_main_action(runtime, action)\n    assert not any(p.name == "Grinding Station" for p in runtime.true_state.battlefield)\n    assert runtime.stack.top().kind == "x_artifact_reshape_spell"\n\n\n'''
    if anchor not in text: raise SystemExit("runtime smoke Reshape anchor missing")
    text=text.replace(anchor,test+anchor,1)
if "test_runtime_whir_duplicate_improvise_slots_survive_first_tap" not in text:
    anchor='''def test_base_policy_chooses_revealed_artifact_not_fail_to_find():\n'''
    test='''def test_runtime_whir_duplicate_improvise_slots_survive_first_tap():\n    runtime = make_runtime_state(solver.State(\n        turn=3,\n        library=("Grim Monolith", "Island"),\n        hand=("Whir of Invention",),\n        battlefield=(\n            solver.Perm("Clue", mode="clue"),\n            solver.Perm("Clue", mode="clue"),\n        ),\n        blue=3,\n        colorless=0,\n    ))\n    action = next(\n        a for a in x_actions(runtime, "Whir of Invention", 2)\n        if len(dict(dict(a.parameters)["cast_parameters"])["improvise"]) == 2\n    )\n    runtime = apply_main_action(runtime, action)\n    assert len(runtime.true_state.battlefield) == 2\n    assert all(p.tapped for p in runtime.true_state.battlefield)\n    assert runtime.stack.top().kind == "x_artifact_whir_spell"\n\n\n'''
    if anchor not in text: raise SystemExit("runtime smoke Whir anchor missing")
    text=text.replace(anchor,test+anchor,1)
text=text.replace(
    '''        test_cast_commit_actions_are_hidden_future_invariant,\n        test_reshape_prized_statue_dies_trigger_is_above_spell,\n''',
    '''        test_cast_commit_actions_are_hidden_future_invariant,\n        test_runtime_reshape_sacrifice_survives_payment_annotation_change,\n        test_reshape_prized_statue_dies_trigger_is_above_spell,\n'''
)
text=text.replace(
    '''        test_whir_commits_x_and_improvise_before_search,\n        test_base_policy_chooses_revealed_artifact_not_fail_to_find,\n''',
    '''        test_whir_commits_x_and_improvise_before_search,\n        test_runtime_whir_duplicate_improvise_slots_survive_first_tap,\n        test_base_policy_chooses_revealed_artifact_not_fail_to_find,\n'''
)
p.write_text(text,encoding="utf-8")

print("X-slot stability source patch complete")
