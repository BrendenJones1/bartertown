"""World generation from a seed (CLAUDE.md §3, §4).

Everything random about a game except LLM sampling is fixed here from ``seed``: starting
inventories, private preferences, auction drip order (reserve pool order), and the trend
schedule. Each concern uses its own ``rng_for(seed, purpose)`` stream so they stay independent.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from paperclip.config import GameSettings, Seat
from paperclip.rng import rng_for

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ITEMS_PATH = ROOT / "data" / "items.yaml"
DEFAULT_ANCHORS_PATH = ROOT / "data" / "anchors.yaml"

CATEGORIES: tuple[str, ...] = (
    "office",
    "kitchen",
    "music",
    "tech",
    "sports",
    "collectible",
    "furniture",
    "fashion",
    "vehicle",
    "experience",
)
PAPERCLIP_ID = "paperclip"

# Private preference multipliers are drawn per category from this fixed menu.
PREFERENCE_CHOICES: tuple[float, ...] = (0.5, 0.75, 1.0, 1.5, 2.0)
TREND_MIN, TREND_MAX = 0.5, 3.0

_HEADLINE_UP = "TRENDING: {cat} items are suddenly all the rage!"
_HEADLINE_DOWN = "SLUMP: interest in {cat} items is fading fast."


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CatalogItem(_Strict):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: str
    base_value: float = Field(gt=0)
    description: str = Field(min_length=1)

    @model_validator(mode="after")
    def _known_category(self) -> "CatalogItem":
        if self.category not in CATEGORIES:
            raise ValueError(f"item {self.id!r}: unknown category {self.category!r}")
        return self


class Anchor(_Strict):
    name: str = Field(min_length=1)
    value: float = Field(gt=0)


def _load_yaml_list(path: Path, key: str) -> list:
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict) or not isinstance(raw.get(key), list):
        raise ValueError(f"{path}: expected a mapping with a {key!r} list")
    return raw[key]


def load_catalog(path: str | Path = DEFAULT_ITEMS_PATH) -> list[CatalogItem]:
    """Load and validate the item catalog. Requires unique ids and a paperclip of value 1."""
    try:
        items = [CatalogItem.model_validate(r) for r in _load_yaml_list(Path(path), "items")]
    except ValidationError as e:
        raise ValueError(f"invalid item catalog {path}:\n{e}") from e
    ids = [i.id for i in items]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"duplicate item ids in {path}: {dupes}")
    clip = next((i for i in items if i.id == PAPERCLIP_ID), None)
    if clip is None or clip.base_value != 1:
        raise ValueError(f"{path}: catalog must contain {PAPERCLIP_ID!r} with base_value 1")
    return items


def load_anchors(path: str | Path = DEFAULT_ANCHORS_PATH) -> list[Anchor]:
    """Load the judge anchor list (CLAUDE.md §7)."""
    try:
        return [Anchor.model_validate(r) for r in _load_yaml_list(Path(path), "anchors")]
    except ValidationError as e:
        raise ValueError(f"invalid anchors {path}:\n{e}") from e


@dataclass(frozen=True)
class Item:
    """A concrete item instance in a game. ``id`` is unique within the world."""

    id: str
    catalog_id: str
    name: str
    category: str
    base_value: float
    description: str


@dataclass(frozen=True)
class TrendShock:
    turn: int  # 1-indexed turn on which the shock fires
    category: str
    multiplier: float
    headline: str


@dataclass(frozen=True)
class World:
    """Initial state of a game. Seat-indexed fields refer to seat positions, not models."""

    seed: int
    items: dict[str, Item]  # every item instance: dealt + reserve
    inventories: tuple[tuple[str, ...], ...]  # per seat, item ids
    preferences: tuple[dict[str, float], ...]  # per seat, category -> multiplier
    reserve: tuple[str, ...]  # item ids, in seeded auction drip order
    trends: tuple[TrendShock, ...]


def _instance(c: CatalogItem, item_id: str | None = None) -> Item:
    return Item(
        id=item_id or c.id,
        catalog_id=c.id,
        name=c.name,
        category=c.category,
        base_value=c.base_value,
        description=c.description,
    )


def _headline(category: str, multiplier: float) -> str:
    template = _HEADLINE_UP if multiplier >= 1 else _HEADLINE_DOWN
    return template.format(cat=category)


def generate_trends(seed: int, game: GameSettings) -> tuple[TrendShock, ...]:
    """One shock every ``trend_shock_every`` turns: turns every, 2*every, ... <= turns."""
    rng = rng_for(seed, "trends")
    shocks = []
    for turn in range(game.trend_shock_every, game.turns + 1, game.trend_shock_every):
        category = rng.choice(CATEGORIES)
        multiplier = round(rng.uniform(TREND_MIN, TREND_MAX), 2)
        shocks.append(TrendShock(turn, category, multiplier, _headline(category, multiplier)))
    return tuple(shocks)


def generate_preferences(seed: int, num_seats: int) -> tuple[dict[str, float], ...]:
    rng = rng_for(seed, "preferences")
    return tuple(
        {cat: rng.choice(PREFERENCE_CHOICES) for cat in CATEGORIES} for _ in range(num_seats)
    )


def generate_world(
    seed: int,
    game: GameSettings,
    num_seats: int,
    catalog: list[CatalogItem] | None = None,
) -> World:
    """Build the full initial world for ``seed``. Deterministic in ``(seed, game, catalog)``."""
    catalog = load_catalog() if catalog is None else catalog
    by_id = {c.id: c for c in catalog}
    if PAPERCLIP_ID not in by_id:
        raise ValueError(f"catalog must contain {PAPERCLIP_ID!r}")

    extra = game.starting_items_per_agent - 1
    low_end = sorted(
        (
            c
            for c in catalog
            if c.id != PAPERCLIP_ID and c.base_value <= game.starting_value_ceiling
        ),
        key=lambda c: c.id,
    )
    needed = extra * num_seats
    if len(low_end) < needed:
        raise ValueError(
            f"need {needed} catalog items with base_value <= {game.starting_value_ceiling} "
            f"to deal {extra} per seat to {num_seats} seats; catalog has {len(low_end)}"
        )

    deal_rng = rng_for(seed, "deal")
    dealt = deal_rng.sample(low_end, needed)

    items: dict[str, Item] = {}
    inventories = []
    for seat in range(num_seats):
        clip = _instance(by_id[PAPERCLIP_ID], f"{PAPERCLIP_ID}-{seat + 1}")
        hand = [clip] + [_instance(c) for c in dealt[seat * extra : (seat + 1) * extra]]
        for it in hand:
            items[it.id] = it
        inventories.append(tuple(it.id for it in hand))

    # Reserve: every undealt catalog item except the paperclip, in seeded drip order.
    dealt_ids = {c.id for c in dealt}
    reserve_items = [
        _instance(c)
        for c in sorted(catalog, key=lambda c: c.id)
        if c.id != PAPERCLIP_ID and c.id not in dealt_ids
    ]
    rng_for(seed, "reserve").shuffle(reserve_items)
    for it in reserve_items:
        items[it.id] = it

    return World(
        seed=seed,
        items=items,
        inventories=tuple(inventories),
        preferences=generate_preferences(seed, num_seats),
        reserve=tuple(it.id for it in reserve_items),
        trends=generate_trends(seed, game),
    )


def rotate_seats(seats: list[Seat], k: int) -> list[Seat]:
    """Seat assignment for rotation ``k`` (CLAUDE.md §2).

    Hands stay fixed to seat positions; every model moves ``k`` seats over, so the model
    originally at seat ``j`` plays seat ``(j + k) % n``. Result is indexed by seat position.
    """
    n = len(seats)
    return [seats[(i - k) % n] for i in range(n)]
