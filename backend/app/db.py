from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
)
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Миграция SQLite: колонка volume_m3 (старые файлы БД)
        for ddl in (
            "ALTER TABLE shipments ADD COLUMN volume_m3 REAL",
            "ALTER TABLE shipments ADD COLUMN transit_started_at DATETIME",
        ):
            if "sqlite" in settings.database_url:
                try:
                    await conn.execute(text(ddl))
                except Exception:
                    pass
        if "postgresql" in settings.database_url:
            try:
                await conn.execute(
                    text(
                        "ALTER TABLE shipments ADD COLUMN IF NOT EXISTS transit_started_at "
                        "TIMESTAMP WITH TIME ZONE"
                    )
                )
            except Exception:
                pass
            for col in ("route_origin", "route_destination"):
                try:
                    await conn.execute(
                        text(f"ALTER TABLE shipments ALTER COLUMN {col} TYPE VARCHAR(512)")
                    )
                except Exception:
                    pass
            try:
                await conn.execute(
                    text(
                        "UPDATE shipments SET transit_started_at = created_at "
                        "WHERE status = 'delivered' AND transit_started_at IS NULL"
                    )
                )
            except Exception:
                pass
        if "sqlite" in settings.database_url:
            try:
                await conn.execute(
                    text(
                        "UPDATE shipments SET transit_started_at = created_at "
                        "WHERE status = 'delivered' AND transit_started_at IS NULL"
                    )
                )
            except Exception:
                pass
