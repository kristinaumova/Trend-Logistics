"""
Скрипт сидирования тестовых данных: поставки для дашборда и истории ML.
Запуск из папки backend: python seed_data.py
"""
import asyncio
import random
import sys
from datetime import datetime, timedelta

# Добавляем путь к app
sys.path.insert(0, ".")

from sqlalchemy import select, func
import os

from app.auth import hash_password
from app.db import AsyncSessionLocal, init_db
from app.models.shipment import Shipment, ShipmentStatus
from app.models.user import User


async def seed():
    await init_db()
    async with AsyncSessionLocal() as db:
        # Пользователь по умолчанию, если нет ни одного
        user_count = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
        if user_count == 0:
            pwd = (os.environ.get("ADMIN_PASSWORD") or "").strip()
            if not pwd:
                raise SystemExit("Задайте ADMIN_PASSWORD в окружении")
            u = User(
                login="admin",
                password_hash=hash_password(pwd),
                role="admin",
            )
            db.add(u)
            await db.flush()
            print("Создан пользователь admin")
        r = await db.execute(select(func.count()).select_from(Shipment))
        if (r.scalar() or 0) > 0:
            await db.commit()
            return
        routes = [
            ("Москва", "Санкт-Петербург"),
            ("Москва", "Казань"),
            ("Санкт-Петербург", "Москва"),
            ("Новосибирск", "Москва"),
            ("Екатеринбург", "Самара"),
            ("Казань", "Нижний Новгород"),
        ]
        transport_types = ["truck", "rail", "truck", "truck", "sea", "air"]
        products = ["Генеральные грузы", "Контейнеры", "Скоропортящиеся", "Оборудование", "Промышленные детали"]
        for i in range(50):
            origin, dest = random.choice(routes)
            planned = datetime.utcnow() - timedelta(days=random.randint(0, 30))
            actual = planned + timedelta(days=random.uniform(3, 12)) if random.random() > 0.3 else None
            status = (
                ShipmentStatus.DELIVERED
                if actual
                else (ShipmentStatus.IN_TRANSIT if random.random() > 0.5 else ShipmentStatus.PENDING)
            )
            s = Shipment(
                route_origin=origin,
                route_destination=dest,
                transport_type=random.choice(transport_types),
                product_type=random.choice(products),
                weight_kg=random.uniform(100, 5000),
                volume_m3=round(random.uniform(1, 20), 1) if random.random() > 0.3 else None,
                priority=random.choice(["low", "normal", "high"]),
                status=status,
                planned_delivery_at=planned,
                actual_delivery_at=actual,
            )
            db.add(s)
        await db.commit()
        print("Добавлено 50 тестовых поставок.")
    return


if __name__ == "__main__":
    asyncio.run(seed())
