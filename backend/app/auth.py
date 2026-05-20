from datetime import datetime, timezone, timedelta
import uuid
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models.user import User
from app.services.redis_jwt_sessions import validate_jwt_session

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(login: str, role: str) -> tuple[str, str]:
    """JWT + jti для привязки сессии в Redis."""
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": login, "role": role, "exp": expire, "jti": jti}
    token = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return token, jti


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> User:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        login = payload.get("sub")
        if not login:
            raise HTTPException(status_code=401, detail="Неверный токен")
        jti = payload.get("jti")
        if (settings.redis_url or "").strip():
            if not jti:
                raise HTTPException(status_code=401, detail="Токен без идентификатора сессии")
            if not await validate_jwt_session(jti, login):
                raise HTTPException(status_code=401, detail="Сессия недействительна или завершена")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Неверный или истёкший токен")
    result = await db.execute(select(User).where(User.login == login))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return user
