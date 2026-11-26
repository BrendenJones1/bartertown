import random
import subprocess
import sys

import pytest

from paperclip.rng import derive_seed, rng_for


def _draw(r: random.Random) -> list[float]:
    return [r.random() for _ in range(5)]


def test_same_seed_and_purpose_is_deterministic():
    assert _draw(rng_for(101, "world")) == _draw(rng_for(101, "world"))


def test_purposes_are_separated():
    assert _draw(rng_for(101, "world")) != _draw(rng_for(101, "auction"))


def test_seeds_are_separated():
    assert _draw(rng_for(101, "world")) != _draw(rng_for(202, "world"))


def test_returns_independent_instances():
    a = rng_for(1, "x")
    a.random()
    b = rng_for(1, "x")
    assert b.random() == rng_for(1, "x").random()


def test_does_not_touch_global_random():
    random.seed(0)
    expected = random.random()
    random.seed(0)
    rng_for(5, "p").random()
    assert random.random() == expected


def test_stable_across_processes():
    # Guards against accidental use of hash(), which varies with PYTHONHASHSEED.
    code = "from paperclip.rng import derive_seed; print(derive_seed(101, 'world'))"
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        env={"PYTHONHASHSEED": "12345"},
    )
    assert int(out.stdout) == derive_seed(101, "world")


def test_known_value_pinned():
    # Pin the derivation so a change to it is a deliberate, visible decision.
    assert rng_for(0, "test").randint(0, 10**9) == 337935674


@pytest.mark.parametrize("bad", ["", None])
def test_rejects_bad_purpose(bad):
    with pytest.raises(ValueError):
        rng_for(1, bad)


def test_rejects_non_int_seed():
    with pytest.raises(TypeError):
        rng_for("1", "x")  # type: ignore[arg-type]
