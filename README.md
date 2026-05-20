# Trend Logistics

Программный комплекс для **интервального прогнозирования сроков поставки** с учётом внешних факторов (погода, трафик, геополитика). Соответствует курсовой работе по проектированию ИС для предсказания сроков поставки.

## Возможности

- **Авторизация**: JWT, вход по логину/паролю; учётная запись `admin` (пароль задаётся в `ADMIN_PASSWORD`, не отображается в интерфейсе).
- **REST API**: поставки (CRUD, фильтры), запрос прогноза по ID поставки, внешние факторы по маршруту (все эндпоинты защищены).
- **Интервальный прогноз**: квантильная регрессия (Gradient Boosting) даёт интервал «min–max» дней и медиану; прогноз **привязан к времени маршрута** (OSRM + проверка разумности, при сбое — оценка по расстоянию и виду транспорта). На карточке разделены **время в пути по маршруту (ч)** и **календарный срок с учётом факторов (дн.)**.
- **Внешние факторы**: отдельный сервис `external_data_service` — мок или живые API (Open-Meteo для погоды без ключа, заглушки для трафика/геополитики). Основной бэкенд вызывает его по HTTP; при недоступности — встроенный мок.
- **Мониторинг**: вынесен на отдельный ресурс — в шапке ссылка «Мониторинг» (URL задаётся через `MONITORING_URL`, например Grafana).
- **Веб-интерфейс**: дашборд поставок, детальная карточка с прогнозом, разделы Аналитика и Настройки.

## Стек

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2 (async), SQLite (или PostgreSQL через `DATABASE_URL`), scikit-learn (квантильная регрессия).
- **Frontend**: React 18, Vite, React Router.
- **БД**: SQLite по умолчанию (файл `trend_logistics.db` в каталоге backend).

## Запуск локально

### 1. Backend

```bash
cd trend_logistics/backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Создание таблиц и тестовые данные
python seed_data.py
# Запуск API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API: <http://127.0.0.1:8000>  

**Документация API (продакшен):**
- **Swagger UI**: <http://127.0.0.1:8000/docs>
- **ReDoc**: <http://127.0.0.1:8000/redoc>
- **OpenAPI 3.0 (JSON)**: <http://127.0.0.1:8000/openapi.json> — для генерации клиентов и импорта в Postman/Insomnia

### 2. Frontend

```bash
cd trend_logistics/frontend
npm install
npm run dev
```

Интерфейс: <http://127.0.0.1:3000> (проксирует `/api` на бэкенд). Вход: логин **admin**, пароль из `.env` (`ADMIN_PASSWORD`).

### 3. Сидирование данных (если таблицы пустые)

Из каталога `backend`:

```bash
python seed_data.py
```

Будет создано 50 тестовых поставок с разными маршрутами и статусами.

## Основные эндпоинты

| Метод | Путь | Описание |
|--------|------|----------|
| GET | `/shipments` | Список поставок (фильтры: `status`, `transport_type`, `skip`, `limit`) |
| GET | `/shipments/{id}` | Поставка по ID |
| POST | `/shipments` | Создание поставки (JSON body) |
| POST | `/forecasts` | Расчёт прогноза (body: `{"shipment_id": 1}`) |
| GET | `/forecasts/by-shipment/{id}` | Последний прогноз по поставке |
| GET | `/factors/for-route` | Внешние факторы (query: `route_origin`, `route_destination`) |
| POST | `/auth/login` | Вход (body: `{"login","password"}`), возвращает JWT |
| GET | `/auth/me` | Текущий пользователь (заголовок `Authorization: Bearer <token>`) |
| GET | `/config/public` | Публичный конфиг (например `monitoring_url` для фронта) |
| GET | `/route` | Маршрут между городами: расстояние, время, координаты для карты (OSRM) |

**Карта и маршрут:** на странице деталей поставки отображается карта на базе [OpenLayers](https://openlayers.org/) с нейтральными тайлами CartoDB (без политической символики). Маршрут по автодорогам считается движком [OSRM](https://project-osrm.org/) (без ключа). Геокодинг городов — по встроенному справочнику (Москва, СПб, Новосибирск, Омск, Казань и др.). Расстояние и базовое время в карточках берутся из этого расчёта.

## Сервис внешних данных (external_data_service)

Отдельный микросервис, который отдаёт погоду, трафик и геополитику по маршруту.

**Как это работает:**
1. При расчёте прогноза или при запросе «факторы по маршруту» основной backend вызывает **external_data_client.get_all_factors(origin, destination)**.
2. Если в конфиге задан **EXTERNAL_DATA_SERVICE_URL** (в Docker это `http://external_data:8001`), клиент делает HTTP-запрос **GET /factors?route_origin=...&route_destination=...** к сервису external_data.
3. Сервис external_data в ответ отдаёт JSON: `{ "weather": {...}, "traffic": {...}, "geopolitics": {...} }`. Режим данных задаётся переменными окружения: по умолчанию **mock** (случайные значения), при **EXTERNAL_DATA_USE_LIVE_WEATHER=true** погода берётся из Open-Meteo.
4. Если сервис недоступен или URL не задан, backend использует **встроенный мок** (класс ExternalFactorsService) — приложение продолжает работать без внешнего сервиса.

- **Режимы**: `mock` (случайные данные) или `live` (реальные API).
- **Погода (live)**: [Open-Meteo](https://open-meteo.com) — бесплатно, без ключа; города из справочника (Москва, СПб, Казань и др.).
- **Трафик / геополитика**: пока мок; в коде есть заглушки для подключения своих API.

Запуск отдельно (для разработки):

```bash
cd external_data_service
pip install -r requirements.txt
# С живой погодой:
EXTERNAL_DATA_USE_LIVE_WEATHER=true uvicorn main:app --reload --port 8001
```

Эндпоинты: `GET /weather`, `GET /traffic`, `GET /geopolitics`, `GET /factors?route_origin=...&route_destination=...`, `GET /health`. Документация: `http://localhost:8001/docs`.

В Docker Compose сервис поднимается автоматически; бэкенд обращается к нему по `http://external_data:8001`. Переменные в `.env`: `EXTERNAL_DATA_USE_LIVE_WEATHER`, `EXTERNAL_DATA_USE_LIVE_TRAFFIC`, `EXTERNAL_DATA_USE_LIVE_GEOPOLITICS`.


## Структура проекта


```
trend_logistics/
├── backend/                 # Основной API (поставки, прогнозы, авторизация)
│   ├── app/
│   │   ├── api/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/        # + external_data_client (вызов external_data_service)
│   │   └── ...
│   └── requirements.txt
├── external_data_service/   # Сервис погоды/трафика/геополитики (мок или live API)
│   ├── main.py
│   ├── config.py
│   ├── geocode.py           # Города → координаты для Open-Meteo
│   ├── providers/           # weather, traffic, geopolitics
│   └── requirements.txt
├── frontend/
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
├── Dockerfile.external_data
└── README.md
```

## Docker Compose

Запуск бэкенда и фронта (nginx) одной командой:

```bash
cp .env.example .env
# Отредактируйте .env: JWT_SECRET, MONITORING_URL, при необходимости EXTERNAL_DATA_USE_LIVE_WEATHER=true
docker compose up -d --build
```

Продакшен (домен **trend-logistics.ru**): **Caddy** на портах 80/443, авто-сертификаты Let's Encrypt. Сайт: **https://trend-logistics.ru**, Grafana: **https://trend-logistics.ru/grafana/**.

Локально на сервере (без HTTPS): <http://127.0.0.1:3000> (`APP_PUBLISH_PORT`). В `.env` задайте `APP_DOMAIN`, `ACME_EMAIL`, `JWT_SECRET` (см. `.env.example`).

## GitHub Actions: деплой на сервер

При пуше в `main`/`master` выполняется деплой по SSH: **git clone / git pull** в `DEPLOY_PATH`, затем `docker compose build` и `up`.

**Перед первым пушем** нужно настроить секреты и сервер — см. **[docs/DEPLOY_SETUP.md](docs/DEPLOY_SETUP.md)**.

**Секреты репозитория (Settings → Secrets and variables → Actions):**

- `DEPLOY_HOST` — хост сервера
- `DEPLOY_USER` — пользователь SSH
- `DEPLOY_SSH_KEY` — приватный ключ SSH (содержимое)
- `DEPLOY_PATH` — каталог git-репозитория на сервере (например `/opt/trend_logistics`)
- `DEPLOY_PORT` — (опционально) порт SSH, по умолчанию 22
- `JWT_SECRET` — секрет для JWT (обязательно в продакшене)
- `ADMIN_PASSWORD` — пароль `admin` для приложения и Grafana (обязательно)
- `APP_DOMAIN` — (опционально) домен HTTPS, по умолчанию `trend-logistics.ru`
- `ACME_EMAIL` — email для Let's Encrypt
- `MONITORING_URL` — (опционально) ссылка «Мониторинг» (по умолчанию `/grafana/`)

На сервере должны быть установлены **git**, Docker и Docker Compose.

## Лицензия

Учебный проект (курсовая работа).
