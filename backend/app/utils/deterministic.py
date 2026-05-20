"""Детерминированные «случайные» величины по строке маршрута (без смены при каждом запросе)."""
import hashlib
import struct
from typing import Callable


def route_seed(route_origin: str, route_destination: str, salt: str = "") -> int:
    a = (route_origin or "").strip().lower().replace("ё", "е")
    b = (route_destination or "").strip().lower().replace("ё", "е")
    raw = f"{salt}|{a}|{b}".encode("utf-8")
    return struct.unpack(">Q", hashlib.sha256(raw).digest()[:8])[0]


def seeded_float(seed: int, idx: int, lo: float, hi: float) -> float:
    h = hashlib.sha256(f"{seed}:{idx}".encode()).digest()
    u = struct.unpack(">I", h[:4])[0] / 2**32
    return lo + u * (hi - lo)


def seeded_choice(seed: int, idx: int, choices: list[str]) -> str:
    if not choices:
        return ""
    h = hashlib.sha256(f"{seed}:{idx}".encode()).digest()
    u = struct.unpack(">I", h[:4])[0]
    return choices[u % len(choices)]
