#!/usr/bin/env python3
"""One-time guarded migration for explicit Markov-safe in-game RNG.

Run from the repository root on branch ``rng-state-migration``:

    py -3 tools/apply_rng_state_migration.py

The script intentionally fails if the finalized Oracle source no longer matches
its audited anchors.  It edits only:

- urza_solver.py
- solver_architecture.py
- architecture_smoke.py

After successful validation, commit those three modified files and remove this
one-time applicator.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def patch_urza() -> None:
    path = ROOT / "urza_solver.py"
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "from functools import lru_cache\n",
        "from functools import lru_cache\nfrom solver_architecture import RandomStreams, canonical_markov_state_key, stable_digest\n",
        "architecture RNG import",
    )

    text = replace_once(
        text,
        '    win_family: str = ""\n    trace: Tuple[str,...] = ()\n',
        '    win_family: str = ""\n    # Root seed selecting the deterministic game-randomness tape.  This is true\n    # simulator state, never policy-visible information.\n    rng_root_seed: int = 0\n    trace: Tuple[str,...] = ()\n',
        "State rng_root_seed field",
    )

    old_shuffle = '''def shuffled_library(s:State,salt:str)->Tuple[str,...]:\n    lib=list(s.library)\n    h=hashlib.sha256((salt+'|'+str(s.turn)+'|'+str(len(s.trace))+'|'+repr(lib)).encode()).digest()\n    rng=random.Random(int.from_bytes(h[:8],'big'))\n    rng.shuffle(lib)\n    return tuple(lib)\n'''
    new_shuffle = '''def shuffled_library(s:State,salt:str)->Tuple[str,...]:\n    \"\"\"Return a reproducible shuffle without consulting trajectory history.\n\n    The root seed selects an immutable game-randomness tape.  The event coordinate\n    is derived from the action salt plus the canonical Markov state, which excludes\n    trace/provenance fields but retains every future-legality distinction.\n\n    Consequences:\n    - identical Markov state + action + root seed -> identical shuffle;\n    - different root seeds sample different deterministic worlds;\n    - adding/removing trace text cannot change a game outcome;\n    - policy/Monte-Carlo RNG usage cannot perturb the actual game stream.\n    \"\"\"\n    lib=list(s.library)\n    state_fingerprint=stable_digest(canonical_markov_state_key(s))\n    event_id=(\"shuffle\",salt,state_fingerprint)\n    rng=RandomStreams(s.rng_root_seed).game_rng(event_id)\n    rng.shuffle(lib)\n    return tuple(lib)\n'''
    text = replace_once(text, old_shuffle, new_shuffle, "shuffled_library migration")

    text = replace_once(
        text,
        '''def search_hand(deck_order:List[str], keep_n:int, bottom:List[str], max_turn=7,\n                beam=2500, max_actions_per_turn=60, caverns_live=True,\n                progress_tag:str="", progress_seconds:float=0.0, graph_stats=None)->Tuple[Optional[int],str,Tuple[str,...],int]:\n    hand,lib=london_opening_zones(deck_order,keep_n,bottom)\n    s=State(turn=1,library=lib,hand=tuple(hand),battlefield=(),trace=("--- Turn 1 ---",))\n''',
        '''def search_hand(deck_order:List[str], keep_n:int, bottom:List[str], max_turn=7,\n                beam=2500, max_actions_per_turn=60, caverns_live=True,\n                progress_tag:str="", progress_seconds:float=0.0, graph_stats=None,\n                rng_root_seed:int=0)->Tuple[Optional[int],str,Tuple[str,...],int]:\n    hand,lib=london_opening_zones(deck_order,keep_n,bottom)\n    s=State(turn=1,library=lib,hand=tuple(hand),battlefield=(),rng_root_seed=rng_root_seed,trace=("--- Turn 1 ---",))\n''',
        "search_hand root seed",
    )

    text = replace_once(
        text,
        '''                progress_seconds=progress_seconds,\n                graph_stats=hand_graph\n            )\n''',
        '''                progress_seconds=progress_seconds,\n                graph_stats=hand_graph,\n                rng_root_seed=seed\n            )\n''',
        "production search_hand seed propagation",
    )

    text = replace_once(
        text,
        '''def profile_single_hand(deck_order:List[str], max_turn:int=3, beam:int=300,\n                        max_actions_per_turn:int=60, caverns_live:bool=True,\n                        print_every_depth:int=1):\n''',
        '''def profile_single_hand(deck_order:List[str], max_turn:int=3, beam:int=300,\n                        max_actions_per_turn:int=60, caverns_live:bool=True,\n                        print_every_depth:int=1, rng_root_seed:int=0):\n''',
        "profile_single_hand signature",
    )
    text = replace_once(
        text,
        '''    s=State(turn=1,library=lib,hand=tuple(hand),battlefield=(),trace=("--- Turn 1 ---",))\n    if caverns_live and "Gemstone Caverns" in s.hand:\n''',
        '''    s=State(turn=1,library=lib,hand=tuple(hand),battlefield=(),rng_root_seed=rng_root_seed,trace=("--- Turn 1 ---",))\n    if caverns_live and "Gemstone Caverns" in s.hand:\n''',
        "profile_single_hand State seed",
    )
    text = replace_once(
        text,
        '''        d,max_turn=max_turn,beam=beam,\n        max_actions_per_turn=depth,caverns_live=True\n    )\n''',
        '''        d,max_turn=max_turn,beam=beam,\n        max_actions_per_turn=depth,caverns_live=True,rng_root_seed=seed\n    )\n''',
        "profile_seed propagation",
    )

    text = replace_once(
        text,
        '''def profile_search_hand(deck_order:List[str], keep_n:int, bottom:List[str], max_turn=7,\n                        beam=300, max_actions_per_turn=60, caverns_live=True,\n                        candidate_tag="candidate"):\n''',
        '''def profile_search_hand(deck_order:List[str], keep_n:int, bottom:List[str], max_turn=7,\n                        beam=300, max_actions_per_turn=60, caverns_live=True,\n                        candidate_tag="candidate", rng_root_seed:int=0):\n''',
        "profile_search_hand signature",
    )
    text = replace_once(
        text,
        '''    s=State(turn=1,library=lib,hand=tuple(hand),battlefield=(),trace=("--- Turn 1 ---",))\n\n    if "Gemstone Caverns" in s.hand and caverns_live and len(s.hand)>1:\n''',
        '''    s=State(turn=1,library=lib,hand=tuple(hand),battlefield=(),rng_root_seed=rng_root_seed,trace=("--- Turn 1 ---",))\n\n    if "Gemstone Caverns" in s.hand and caverns_live and len(s.hand)>1:\n''',
        "profile_search_hand State seed",
    )
    text = replace_once(
        text,
        '''                max_actions_per_turn=depth,caverns_live=caverns_live,\n                candidate_tag=tag\n            )\n''',
        '''                max_actions_per_turn=depth,caverns_live=caverns_live,\n                candidate_tag=tag,rng_root_seed=seed\n            )\n''',
        "profile oracle seed propagation",
    )

    path.write_text(text, encoding="utf-8")


def patch_architecture() -> None:
    path = ROOT / "solver_architecture.py"
    text = path.read_text(encoding="utf-8")

    text = replace_once(text, 'RNG_SCHEME_VERSION = "urza-rng-v2"', 'RNG_SCHEME_VERSION = "urza-rng-v3-keyed-state"', "RNG version")
    text = replace_once(text, 'STATE_KEY_VERSION = "urza-state-key-v2"', 'STATE_KEY_VERSION = "urza-state-key-v3"', "state-key version")

    old = '''def canonical_true_state_key(state: Any) -> Tuple[Any, ...]:\n    \"\"\"Conservative exact transposition/replay key.\n\n    Every State dataclass field is included.  Ordered hidden library contents are\n    included exactly.  Hand and battlefield ordering are canonicalized because\n    tuple insertion order in those zones is not strategic identity.\n\n    The current Oracle still has history-dependent deterministic shuffles, so\n    `trace` remains part of this *true* exact key. A future narrower DP strategic\n    key should only drop history after shuffle randomness is fully migrated to\n    explicit RandomStreams.\n    \"\"\"\n    if not is_dataclass(state):\n        return stable_key(state)\n\n    values: Dict[str, Any] = {}\n    for f in fields(state):\n        value = getattr(state, f.name)\n        if f.name == "hand":\n            value = tuple(sorted(value))\n        elif f.name == "battlefield":\n            value = _canonical_battlefield(value)\n        values[f.name] = value\n    return stable_key(values)\n'''
    new = '''def _canonical_state_values(state: Any, *, exclude: frozenset[str] = frozenset()) -> Dict[str, Any]:\n    if not is_dataclass(state):\n        raise TypeError("canonical state projection requires a dataclass state")\n    values: Dict[str, Any] = {}\n    for f in fields(state):\n        if f.name in exclude:\n            continue\n        value = getattr(state, f.name)\n        if f.name == "hand":\n            value = tuple(sorted(value))\n        elif f.name == "battlefield":\n            value = _canonical_battlefield(value)\n        elif f.name in {"graveyard", "exile", "interaction_seen"}:\n            value = tuple(sorted(value))\n        values[f.name] = value\n    return values\n\n\ndef canonical_true_state_key(state: Any) -> Tuple[Any, ...]:\n    \"\"\"Conservative replay/debug key including trajectory provenance.\"\"\"\n    if not is_dataclass(state):\n        return stable_key(state)\n    return stable_key(_canonical_state_values(state))\n\n\ndef canonical_markov_state_key(state: Any) -> Tuple[Any, ...]:\n    \"\"\"Canonical future-relevant true state for Markov transitions.\n\n    `trace`, `interaction_seen`, and `urza_cast_turn` are reporting/provenance\n    history rather than rules state.  They must not influence future shuffles or\n    transposition identity.  Hidden library order, the explicit RNG root seed,\n    pending phases, mana, exact permanent grants/refund credits, commander state,\n    and all other dataclass fields remain represented.\n    \"\"\"\n    if not is_dataclass(state):\n        return stable_key(state)\n    return stable_key(\n        _canonical_state_values(\n            state,\n            exclude=frozenset({"trace", "interaction_seen", "urza_cast_turn"}),\n        )\n    )\n'''
    text = replace_once(text, old, new, "canonical Markov state key")
    path.write_text(text, encoding="utf-8")


def patch_architecture_smoke() -> None:
    path = ROOT / "architecture_smoke.py"
    text = path.read_text(encoding="utf-8")

    text = replace_once(text, "from urza_solver import Perm, State\n", "from urza_solver import Perm, State, shuffled_library\n", "smoke shuffled_library import")
    text = replace_once(
        text,
        "    canonical_true_state_key,\n",
        "    canonical_markov_state_key,\n    canonical_true_state_key,\n",
        "smoke markov key import",
    )
    text = replace_once(
        text,
        '''        battlefield=(Perm("Grinding Station"),),\n    )\n''',
        '''        battlefield=(Perm("Grinding Station"),),\n        rng_root_seed=20260822,\n    )\n''',
        "smoke base root seed",
    )

    anchor = '''def test_policy_view_tracks_future_legality_without_hidden_future():\n'''
    inserted = '''def test_markov_key_drops_reporting_history_but_keeps_rng_world():\n    state = base_state()\n    key = canonical_markov_state_key(state)\n    assert key == canonical_markov_state_key(\n        replace(\n            state,\n            trace=("different route", "same physical state"),\n            interaction_seen=("Swan Song",),\n            urza_cast_turn=1,\n        )\n    )\n    assert key != canonical_markov_state_key(replace(state, rng_root_seed=20260823))\n    assert key != canonical_markov_state_key(replace(state, remora_upkeep_pending=True))\n    assert key != canonical_markov_state_key(\n        replace(\n            state,\n            battlefield=(replace(state.battlefield[0], knack_granted=True),),\n        )\n    )\n\n\ndef test_in_game_shuffle_is_trace_independent_and_seeded():\n    cards=tuple(f"C{i}" for i in range(12))\n    state=replace(base_state(),library=cards,trace=("short",))\n    same_physical=replace(\n        state,\n        trace=("a", "much", "longer", "trajectory", "history"),\n        interaction_seen=("Force of Will",),\n        urza_cast_turn=1,\n    )\n    a=shuffled_library(state,"rng-smoke")\n    b=shuffled_library(same_physical,"rng-smoke")\n    assert a==b, "trace/reporting history changed the actual shuffle"\n    assert a==shuffled_library(state,"rng-smoke"), "same seeded event was not reproducible"\n\n    other_seed=replace(state,rng_root_seed=20260823)\n    assert RandomStreams(state.rng_root_seed).seed_for(\n        "game", ("shuffle","rng-smoke",stable_digest(canonical_markov_state_key(state)))\n    ) != RandomStreams(other_seed.rng_root_seed).seed_for(\n        "game", ("shuffle","rng-smoke",stable_digest(canonical_markov_state_key(other_seed)))\n    )\n\n\n'''
    text = replace_once(text, anchor, inserted + anchor, "insert RNG/Markov smokes")

    text = replace_once(
        text,
        '''        test_exact_key_tracks_final_oracle_state_fields,\n        test_policy_view_tracks_future_legality_without_hidden_future,\n''',
        '''        test_exact_key_tracks_final_oracle_state_fields,\n        test_markov_key_drops_reporting_history_but_keeps_rng_world,\n        test_in_game_shuffle_is_trace_independent_and_seeded,\n        test_policy_view_tracks_future_legality_without_hidden_future,\n''',
        "register RNG/Markov smokes",
    )

    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_urza()
    patch_architecture()
    patch_architecture_smoke()
    print("RNG STATE MIGRATION APPLIED")
    print("Modified: urza_solver.py, solver_architecture.py, architecture_smoke.py")
    print("Next: run architecture_smoke.py and the finalized Oracle smoke suite.")


if __name__ == "__main__":
    main()
