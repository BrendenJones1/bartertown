"""Seeded RNG helper (CLAUDE.md §8: all randomness via explicit, purpose-derived RNGs)."""

import hashlib
import random


def derive_seed(seed: int, purpose: str) -> int:
    """Stable 64-bit integer derived from ``(seed, purpose)``.

    Uses SHA-256 rather than ``hash()`` so results do not depend on PYTHONHASHSEED.
    """
    digest = hashlib.sha256(f"{seed}\x00{purpose}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def rng_for(seed: int, purpose: str) -> random.Random:
    """Return a fresh ``random.Random`` seeded from ``(seed, purpose)``.

    The same pair always yields the same stream; different purposes yield independent streams.
    """
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise TypeError(f"seed must be an int, got {type(seed).__name__}")
    if not isinstance(purpose, str) or not purpose:
        raise ValueError("purpose must be a non-empty string")
    return random.Random(derive_seed(seed, purpose))
