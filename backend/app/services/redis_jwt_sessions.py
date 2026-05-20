"""Хранение активных JWT-сессий в Redis (как в описании ВКР)."""
from __future__ import annotations

from app.redis_client import get_redis


async def save_jwt_session(jti: str, login: str, ttl_seconds: int) -> None:
    r = await get_redis()
    if r is None:
        return
    await r.setex(f"jwt:sess:{jti}", ttl_seconds, login)


async def validate_jwt_session(jti: str, login: str) -> bool:
    r = await get_redis()
    if r is None:
        return True
    got = await r.get(f"jwt:sess:{jti}")
    return got == login


async def delete_jwt_session(jti: str) -> None:
    r = await get_redis()
    if r is None:
        return
    await r.delete(f"jwt:sess:{jti}")
