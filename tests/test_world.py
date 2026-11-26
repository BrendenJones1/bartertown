from pathlib import Path

import pytest
import yaml

from paperclip.config import load_config
from paperclip.world import (
    CATEGORIES,
    PAPERCLIP_ID,
    PREFERENCE_CHOICES,
    generate_world,
    load_anchors,
    load_catalog,
    rotate_seats,
)

ROOT = Path(__file__).resolve().parents[1]
CFG = load_config(ROOT / "config" / "tournament.yaml")
GAME = CFG.game
N = len(CFG.seats)


def _world(seed: int = 101):
    return generate_world(seed, GAME, N)


# --- catalog / anchors -------------------------------------------------------


def test_catalog_shape():
    items = load_catalog()
    assert 80 <= len(items) <= 120
    assert {i.category for i in items} == set(CATEGORIES)
    clip = next(i for i in items if i.id == PAPERCLIP_ID)
    assert clip.base_value == 1
    values = [i.base_value for i in items]
    assert min(values) == 1 and 1500 <= max(values) <= 2000


def test_anchors_include_spec_examples():
    anchors = {a.name.lower(): a.value for a in load_anchors()}
    assert anchors["a paperclip"] == 1
    assert anchors["a used bike"] == 40
    assert anchors["a used car"] == 500
    assert anchors["a small house"] == 2000


def _write_items(tmp_path, items) -> Path:
    p = tmp_path / "items.yaml"
    p.write_text(yaml.safe_dump({"items": items}))
    return p


def _raw_items() -> list[dict]:
    return yaml.safe_load((ROOT / "data" / "items.yaml").read_text())["items"]


def test_catalog_rejects_duplicate_ids(tmp_path):
    raw = _raw_items()
    raw.append(dict(raw[1]))
    with pytest.raises(ValueError, match="duplicate"):
        load_catalog(_write_items(tmp_path, raw))


def test_catalog_rejects_unknown_category(tmp_path):
    raw = _raw_items()
    raw[1]["category"] = "spaceships"
    with pytest.raises(ValueError, match="unknown category"):
        load_catalog(_write_items(tmp_path, raw))


def test_catalog_requires_paperclip(tmp_path):
    raw = [r for r in _raw_items() if r["id"] != PAPERCLIP_ID]
    with pytest.raises(ValueError, match="paperclip"):
        load_catalog(_write_items(tmp_path, raw))


# --- determinism -------------------------------------------------------------


def test_same_seed_identical_world():
    assert _world(101) == _world(101)


def test_different_seeds_differ():
    a, b = _world(101), _world(202)
    assert a.inventories != b.inventories
    assert a.preferences != b.preferences
    assert a.reserve != b.reserve
    assert a.trends != b.trends


# --- starting inventories ----------------------------------------------------


@pytest.mark.parametrize("seed", [1, 101, 202, 303])
def test_starting_hands(seed):
    w = _world(seed)
    assert len(w.inventories) == N
    for hand in w.inventories:
        assert len(hand) == GAME.starting_items_per_agent
        items = [w.items[i] for i in hand]
        assert sum(it.catalog_id == PAPERCLIP_ID for it in items) == 1
        assert all(it.base_value <= GAME.starting_value_ceiling for it in items)


def test_all_item_ids_unique_and_partitioned():
    w = _world()
    dealt = [i for hand in w.inventories for i in hand]
    assert len(dealt) == len(set(dealt))
    assert set(dealt).isdisjoint(w.reserve)
    assert set(dealt) | set(w.reserve) == set(w.items)
    # Every non-paperclip catalog item exists exactly once in the world.
    catalog_ids = [it.catalog_id for it in w.items.values() if it.catalog_id != PAPERCLIP_ID]
    assert sorted(catalog_ids) == sorted(c.id for c in load_catalog() if c.id != PAPERCLIP_ID)


def test_not_enough_low_end_items_raises():
    tiny = [c for c in load_catalog() if c.base_value <= 3]
    with pytest.raises(ValueError, match="need"):
        generate_world(1, GAME, N, catalog=tiny)


# --- preferences / trends ----------------------------------------------------


def test_preferences_cover_all_categories():
    for prefs in _world().preferences:
        assert set(prefs) == set(CATEGORIES)
        assert all(v in PREFERENCE_CHOICES for v in prefs.values())


def test_trend_schedule():
    w = _world()
    every = GAME.trend_shock_every
    assert [t.turn for t in w.trends] == list(range(every, GAME.turns + 1, every))
    for t in w.trends:
        assert t.category in CATEGORIES
        assert 0.5 <= t.multiplier <= 3.0
        assert t.category in t.headline
        assert str(t.multiplier) not in t.headline  # headline leaks no numbers


# --- seat rotation -----------------------------------------------------------


def test_rotation_zero_is_identity():
    assert rotate_seats(CFG.seats, 0) == CFG.seats


def test_rotation_shifts_models_k_seats():
    for k in range(N):
        rotated = rotate_seats(CFG.seats, k)
        for j, seat in enumerate(CFG.seats):
            assert rotated[(j + k) % N] == seat


def test_every_model_plays_every_hand_once():
    plays = {s.id: set() for s in CFG.seats}
    for k in range(N):
        for pos, seat in enumerate(rotate_seats(CFG.seats, k)):
            plays[seat.id].add(pos)
    assert all(p == set(range(N)) for p in plays.values())
