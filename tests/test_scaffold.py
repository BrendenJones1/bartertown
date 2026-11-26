from pathlib import Path

import yaml

import paperclip

ROOT = Path(__file__).resolve().parents[1]


def test_package_imports():
    assert paperclip.__version__


def test_tournament_config_has_eight_seats_and_unique_ids():
    cfg = yaml.safe_load((ROOT / "config" / "tournament.yaml").read_text())
    seats = cfg["seats"]
    assert len(seats) == 8
    assert len({s["id"] for s in seats}) == 8


def test_dev_config_has_eight_seats():
    cfg = yaml.safe_load((ROOT / "config" / "dev.yaml").read_text())
    assert len(cfg["seats"]) == 8
