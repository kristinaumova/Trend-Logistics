from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, hash_password
from app.db import get_db
from app.models.user import User
from app.schemas.user_admin import UserCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])


async def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Только для администратора")
    return user


@router.get("", response_model=list[UserOut])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
):
    r = await db.execute(select(User).order_by(User.id))
    return list(r.scalars().all())


@router.post("", response_model=UserOut)
async def create_user(
    body: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
):
    exists = await db.execute(select(User).where(User.login == body.login))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Пользователь с таким логином уже есть")
    u = User(login=body.login, password_hash=hash_password(body.password), role=body.role)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить себя")
    r = await db.execute(select(User).where(User.id == user_id))
    u = r.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="Не найден")
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()
    return {"ok": True}
