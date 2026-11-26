"""Pydantic models for ``config/*.yaml`` (CLAUDE.md §2, §8)."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

NUM_SEATS = 8


class ConfigError(ValueError):
    """Raised when a config file is missing, malformed, or fails validation."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TournamentSettings(_Strict):
    run_id: str = Field(min_length=1)
    seeds: list[int] = Field(min_length=1)
    rotate_seats: bool = True

    @model_validator(mode="after")
    def _unique_seeds(self) -> "TournamentSettings":
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError(f"tournament.seeds must be unique, got {self.seeds}")
        return self


class GameSettings(_Strict):
    turns: int = Field(gt=0)
    starting_items_per_agent: int = Field(ge=1)  # includes the paperclip
    starting_value_ceiling: float = Field(gt=0)
    auction_items_per_turn: int = Field(ge=0)
    trade_rounds_per_turn: int = Field(ge=0)
    trend_shock_every: int = Field(gt=0)
    craft_value_cap: float = Field(gt=0)
    history_window: int = Field(gt=0)
    agent_temperature: float = Field(ge=0, le=2)


class Seat(_Strict):
    id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    model: str = Field(min_length=1)


class PanelJudge(_Strict):
    family: str = Field(min_length=1)
    model: str = Field(min_length=1)


class JudgeSettings(_Strict):
    temperature: float = Field(default=0, ge=0, le=2)
    normalizer: str = Field(min_length=1)
    panel: list[PanelJudge] = Field(min_length=2)

    @model_validator(mode="after")
    def _one_judge_per_family(self) -> "JudgeSettings":
        families = [j.family for j in self.panel]
        dupes = sorted({f for f in families if families.count(f) > 1})
        if dupes:
            raise ValueError(f"judges.panel must have one judge per family; duplicated: {dupes}")
        return self


class Config(_Strict):
    tournament: TournamentSettings
    game: GameSettings
    seats: list[Seat]
    judges: JudgeSettings

    @model_validator(mode="after")
    def _check_seats(self) -> "Config":
        if len(self.seats) != NUM_SEATS:
            raise ValueError(f"seats must have exactly {NUM_SEATS} entries, got {len(self.seats)}")
        ids = [s.id for s in self.seats]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"seat ids must be unique; duplicated: {dupes}")
        panel_families = {j.family for j in self.judges.panel}
        missing = sorted({s.family for s in self.seats} - panel_families)
        if missing:
            raise ValueError(
                f"seat families {missing} have no judge in judges.panel "
                f"(panel families: {sorted(panel_families)})"
            )
        return self

    @property
    def families(self) -> list[str]:
        """Distinct seat families in seat order."""
        return list(dict.fromkeys(s.family for s in self.seats))


def load_config(path: str | Path) -> Config:
    """Load and validate a config YAML file. Raises ``ConfigError`` with a clear message."""
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text())
    except OSError as e:
        raise ConfigError(f"cannot read config {path}: {e}") from e
    except yaml.YAMLError as e:
        raise ConfigError(f"invalid YAML in {path}: {e}") from e
    if not isinstance(raw, dict):
        raise ConfigError(f"config {path} must be a YAML mapping, got {type(raw).__name__}")
    try:
        return Config.model_validate(raw)
    except ValidationError as e:
        raise ConfigError(f"invalid config {path}:\n{e}") from e
