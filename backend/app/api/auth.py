from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, get_current_user, verify_password
from app.config import settings
from app.db import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.services.redis_jwt_sessions import delete_jwt_session, save_jwt_session

router = APIRouter(prefix="/auth", tags=["auth"])
_logout_security = HTTPBearer(auto_error=False)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.login == data.login))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    token, jti = create_access_token(user.login, user.role)
    ttl = int(settings.jwt_expire_minutes * 60)
    await save_jwt_session(jti, user.login, ttl)
    return TokenResponse(
        access_token=token,
        id=user.id,
        login=user.login,
        role=user.role,
    )


@router.post("/logout")
async def logout(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_logout_security)],
):
    """Завершение сессии: удаление jti из Redis (если Redis включён)."""
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Требуется токен")
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Неверный токен")
    jti = payload.get("jti")
    if jti:
        await delete_jwt_session(jti)
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
async def me(user: Annotated[User, Depends(get_current_user)]):
    return user
