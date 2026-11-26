from pathlib import Path

import pytest
import yaml

from paperclip.config import Config, ConfigError, load_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", ["tournament.yaml", "dev.yaml"])
def test_shipped_configs_load(name):
    cfg = load_config(ROOT / "config" / name)
    assert isinstance(cfg, Config)
    assert len(cfg.seats) == 8
    assert cfg.tournament.seeds


def test_tournament_values():
    cfg = load_config(ROOT / "config" / "tournament.yaml")
    assert cfg.tournament.seeds == [101, 202, 303]
    assert cfg.tournament.rotate_seats is True
    assert cfg.game.craft_value_cap == 1.5
    assert cfg.families == ["anthropic", "openai", "google", "xai", "deepseek"]


def _raw() -> dict:
    return yaml.safe_load((ROOT / "config" / "dev.yaml").read_text())


def _write(tmp_path, raw) -> Path:
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(raw))
    return p


def _assert_invalid(tmp_path, raw, needle):
    with pytest.raises(ConfigError, match=needle):
        load_config(_write(tmp_path, raw))


def test_wrong_seat_count(tmp_path):
    raw = _raw()
    raw["seats"] = raw["seats"][:7]
    _assert_invalid(tmp_path, raw, "exactly 8")


def test_duplicate_seat_ids(tmp_path):
    raw = _raw()
    raw["seats"][1]["id"] = raw["seats"][0]["id"]
    _assert_invalid(tmp_path, raw, "unique")


def test_missing_family(tmp_path):
    raw = _raw()
    del raw["seats"][0]["family"]
    _assert_invalid(tmp_path, raw, "family")


def test_seat_family_without_judge(tmp_path):
    raw = _raw()
    raw["seats"][0]["family"] = "nobody"
    _assert_invalid(tmp_path, raw, "no judge")


def test_duplicate_panel_family(tmp_path):
    raw = _raw()
    raw["judges"]["panel"].append({"family": "f1", "model": "x/y"})
    _assert_invalid(tmp_path, raw, "one judge per family")


def test_missing_section(tmp_path):
    raw = _raw()
    del raw["game"]
    _assert_invalid(tmp_path, raw, "game")


def test_unknown_key_rejected(tmp_path):
    raw = _raw()
    raw["game"]["turnz"] = 5
    _assert_invalid(tmp_path, raw, "turnz")


def test_bad_value_rejected(tmp_path):
    raw = _raw()
    raw["game"]["turns"] = 0
    _assert_invalid(tmp_path, raw, "turns")


def test_duplicate_seeds(tmp_path):
    raw = _raw()
    raw["tournament"]["seeds"] = [1, 1]
    _assert_invalid(tmp_path, raw, "unique")


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="cannot read"):
        load_config(tmp_path / "nope.yaml")


def test_invalid_yaml(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("seats: [unclosed")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load_config(p)


def test_non_mapping(tmp_path):
    p = tmp_path / "list.yaml"
    p.write_text("- a\n- b\n")
    with pytest.raises(ConfigError, match="mapping"):
        load_config(p)
