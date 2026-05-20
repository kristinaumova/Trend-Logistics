# Что сделать перед пушем в GitHub, чтобы заработал автодеплой

## 1. Репозиторий на GitHub

- Создай репозиторий (если ещё нет).
- Подключи локальный проект: `git remote add origin https://github.com/<user>/<repo>.git`
- Ветка для деплоя — **main** или **master** (воркфлоу запускается при пуше в эти ветки).

## 2. Секреты репозитория

В GitHub: **Settings → Secrets and variables → Actions → New repository secret.**

Добавь секреты:

| Секрет | Обязательный | Описание |
|--------|----------------|----------|
| `DEPLOY_HOST` | ✅ Да | IP или домен сервера (например `123.45.67.89` или `server.example.com`) |
| `DEPLOY_USER` | ✅ Да | Пользователь SSH (например `deploy` или `root`) |
| `DEPLOY_SSH_KEY` | ✅ Да | **Приватный** SSH-ключ (содержимое файла `id_rsa` целиком, включая `-----BEGIN ... -----`) |
| `DEPLOY_PATH` | Нет | Каталог **git-репозитория** на сервере (по умолчанию `/opt/trend_logistics`). При первом деплое выполняется `git clone`, далее — `git fetch` + checkout коммита из пуша |
| `DEPLOY_PORT` | Нет | Порт SSH, если не 22 |
| `JWT_SECRET` | Рекомендуется | Секрет для JWT (длинная случайная строка для продакшена) |
| `ADMIN_PASSWORD` | ✅ Да | Пароль `admin` (приложение + Grafana). **Не коммитить**, только секрет Actions / `.env` на сервере |
| `APP_DOMAIN` | Нет | Домен для HTTPS (по умолчанию `trend-logistics.ru`) |
| `ACME_EMAIL` | Рекомендуется | Email для Let's Encrypt (уведомления об истечении сертификата) |
| `MONITORING_URL` | Нет | Ссылка «Мониторинг» в SPA (по умолчанию `/grafana/`) |

**Как получить приватный ключ для `DEPLOY_SSH_KEY`:**  
На своей машине: `cat ~/.ssh/id_rsa` (или другой ключ). Скопируй весь вывод, включая первую и последнюю строки, и вставь в секрет.

## 3. Сервер

- **Docker** и **Compose V2** на сервере. Проверка:
  ```bash
  docker compose version
  ```
  Если `apt install docker-compose-plugin` пишет **Unable to locate package** — на сервере нет репозитория Docker CE. Установите плагин **вручную** (подходит для Ubuntu/Debian):
  ```bash
  # Важно: файл называется docker-compose-linux-aarch64 (НЕ arm64) или docker-compose-linux-x86_64
  ARCH="$(uname -m)"
  case "$ARCH" in
    x86_64|amd64) COMPOSE_ARCH="x86_64" ;;
    aarch64|arm64) COMPOSE_ARCH="aarch64" ;;
    *) echo "Неподдерживаемая архитектура: $ARCH"; exit 1 ;;
  esac
  sudo mkdir -p /usr/local/lib/docker/cli-plugins
  sudo curl -fL \
    "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-${COMPOSE_ARCH}" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
  docker compose version
  ```
  Если **404** — сначала диагностика на сервере:
  ```bash
  uname -m
  curl -fL -o /dev/null -w "HTTP %{http_code}\n" \
    "https://github.com/docker/compose/releases/download/v5.1.3/docker-compose-linux-x86_64"
  ```
  (для ARM замени на `docker-compose-linux-aarch64`; **не** `arm64` в имени файла).

  Скрипт из репозитория (после `git clone` или из каталога деплоя):
  ```bash
  chmod +x scripts/install-docker-compose.sh
  ./scripts/install-docker-compose.sh
  ```

  **Запасной вариант** — старый бинарь `docker-compose` v1 (в workflow тоже подхватится, если нет V2):
  ```bash
  sudo curl -fL "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-Linux-x86_64" \
    -o /usr/local/bin/docker-compose
  sudo chmod +x /usr/local/bin/docker-compose
  docker-compose version
  ```
  (для ARM: `docker-compose-Linux-aarch64` или `docker-compose-linux-aarch64` — проверьте HTTP-кодом `curl -w "%{http_code}"`).

  Если GitHub с сервера недоступен (всегда 404/000) — скачайте бинарь на свой ПК и перенесите через `scp` в `/usr/local/lib/docker/cli-plugins/docker-compose`, затем `chmod +x`.
  Должно вывести версию Compose V2. После этого деплой из GitHub Actions снова запустите.

  **Через apt** (только если подключён [официальный репозиторий Docker](https://docs.docker.com/engine/install/ubuntu/)):
  ```bash
  sudo apt-get update
  sudo apt-get install -y docker-compose-plugin
  docker compose version
  ```
  Старый `docker-compose` 1.29 + Docker 24+ при `up` может давать **`KeyError: 'ContainerConfig'`** — лучше именно **Compose V2** (`docker compose` с пробелом).
- По SSH можно зайти под пользователем `DEPLOY_USER` с ключом, который соответствует публичному ключу, добавленному в `~/.ssh/authorized_keys` на сервере.
- На сервере должны быть **git** и **Docker**. Каталог `DEPLOY_PATH` создастся при первом деплое (`git clone`); родительский каталог должен быть доступен на запись, например:
  ```bash
  sudo mkdir -p /opt
  sudo chown $USER:$USER /opt
  ```
- Репозиторий на GitHub должен быть доступен для чтения токеном Actions (для **приватного** репо это работает из коробки; для **публичного** — тоже).
- Альтернатива без токена в URL: один раз вручную на сервере `git clone git@github.com:<user>/<repo>.git $DEPLOY_PATH` (deploy key в GitHub), тогда в workflow можно не менять remote — достаточно `git fetch` / `git pull` (при необходимости поправь скрипт под SSH-remote).

## 4. После первого пуша

- Зайди в **Actions** в репозитории — должен запуститься workflow **Build and Deploy**.
- Если деплой не нужен (сервер ещё не готов), можно не добавлять секреты `DEPLOY_*` — тогда шаг деплоя упадёт с ошибкой. Чтобы воркфлоу не падал, когда деплой не настроен, можно временно отключить запуск по пушу (оставить только `workflow_dispatch`) в `.github/workflows/deploy.yml`.

## 5. Краткий чеклист

- [ ] Репозиторий на GitHub создан, remote добавлен
- [ ] Секреты добавлены: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`
- [ ] На сервере установлены Docker и Docker Compose
- [ ] SSH-вход по ключу под `DEPLOY_USER` работает
- [ ] Каталог деплоя создан и доступен для записи (если используешь не домашнюю папку)
- [ ] (Рекомендуется) Задан `JWT_SECRET` для продакшена
- [ ] Задан `ADMIN_PASSWORD` (сложный пароль, только в секретах)
- [ ] DNS: **A-запись** `trend-logistics.ru` → IP сервера (и открыты порты **80**, **443**)
- [ ] (Рекомендуется) Секрет `ACME_EMAIL` для Let's Encrypt
- [ ] Пуш в ветку `main` или `master`

После этого при каждом пуше в эту ветку на сервере в `DEPLOY_PATH` обновляется код через **git** (без SCP и без `/tmp` на runner) и перезапускается `docker compose up -d`.

## Стек в Docker (PostgreSQL, Redis, ClickHouse, Prometheus, Grafana)

В `docker-compose.yml` по умолчанию поднимаются:

- **PostgreSQL** — основная OLTP-БД приложения (`DATABASE_URL` задаётся в compose).
- **Redis** — сессии JWT (`jti`) и кэш ответов external_data по маршруту.
- **ClickHouse** — события прогнозов (`forecast_events`), логин/пароль **`trend`/`trend`** (как в `docker-compose.yml`).
- **Prometheus** — сбор метрик с `GET http://backend:8000/metrics` (только `127.0.0.1:9090` на хосте).
- **Grafana** — дашборды (снаружи: `https://trend-logistics.ru/grafana/`).
- **Caddy** — HTTPS и авто-сертификаты Let's Encrypt для `APP_DOMAIN` (порты **80** / **443**).

Сайт в продакшене: **https://trend-logistics.ru** (не `:3000`). Локальная отладка на сервере: `http://127.0.0.1:3000` (`APP_PUBLISH_PORT`).

Локальная разработка **без** Docker: в `.env` можно оставить `DATABASE_URL=sqlite+...` и не задавать `REDIS_URL` / `CLICKHOUSE_HOST` — тогда работают прежние облегчённые режимы.

### Версия Python для локального `pip install`

Образ backend в Docker — **Python 3.11**. Для установки зависимостей на машине разработчика используйте **Python 3.11 или 3.12** (виртуальное окружение). На **Python 3.14** сборка `asyncpg`, `greenlet`, `pydantic-core` из текущего `requirements.txt` может завершаться ошибкой; в этом случае ориентируйтесь на Docker или смените интерпретатор.

## Пайплайн зелёный, а фронт на сервере старый

Частые причины:

1. **Кэш Docker при `docker compose build`** — слой с `COPY frontend/` иногда не пересобирается так, как ожидаешь; в этом репозитории в workflow после деплоя фронт собирается с **`build --no-cache frontend`**, остальные сервисы — с обычным кэшем.
2. **Кэш браузера по `index.html`** — для SPA без заголовков nginx отдаёт старую оболочку со ссылками на старые JS-чанки. В `frontend/nginx.conf` для `/index.html` задано **no-cache**; после смены конфига нужен ещё один деплой или пересборка образа `frontend`.
3. **Смотришь не тот URL** — в продакшене открывай **https://trend-logistics.ru**, а не IP:3000 (порт 3000 только на localhost для отладки).
4. **Проверка на сервере вручную:**  
   `cd $DEPLOY_PATH && docker compose images` — время создания образа `frontend` должно обновиться после пуша.  
   `docker compose exec frontend cat /usr/share/nginx/html/index.html | head` — внутри контейнера должны быть актуальные имена файлов из `assets/`.

## 6. HTTPS (Caddy) не поднимается / нет сертификата

1. **DNS:** `dig +short trend-logistics.ru` должен вернуть IP сервера.
2. **Фаервол:** открыты входящие **80** и **443** (`sudo ufw allow 80,443/tcp` при ufw).
3. **Порты:** на сервере ничто другое не слушает 80/443 (`sudo ss -tlnp | grep -E ':80|:443'`).
4. Логи Caddy: `docker compose logs caddy --tail 80`.
5. В `.env` на сервере (или в секретах Actions): `APP_DOMAIN=trend-logistics.ru`, `ACME_EMAIL=ваш@email.ru`, `GRAFANA_ROOT_URL=https://trend-logistics.ru/grafana/`.
6. После смены DNS подождите 5–15 минут и перезапустите: `docker compose up -d --force-recreate caddy`.

## 7. ClickHouse: `Authentication failed` / `password is incorrect`

На образе ClickHouse 24 при **первом** запуске в volume может сохраниться **случайный пароль** пользователя `default`, а backend подключается с другими учётными данными.

**Исправление (один раз на сервере):** сбросить только volume ClickHouse и поднять стек заново (PostgreSQL/Redis не трогаются):

```bash
cd /opt/trend_logistics   # DEPLOY_PATH
docker compose down
docker volume ls | grep ch_data
docker volume rm ИМЯ_ПРОЕКТА_ch_data   # например trend_logistics_ch_data
git pull   # или дождись деплоя с обновлённым compose (user trend / password trend)
docker compose up -d --build
```

После пуша в репозиторий в compose заданы **`CLICKHOUSE_USER=trend`**, **`CLICKHOUSE_PASSWORD=trend`** для ClickHouse и backend. Backend при ошибке CH **не падает** при старте, но аналитика в CH не пишется, пока volume не пересоздан.

## 8. Ошибка **502 Bad Gateway** в браузере

Схема в `docker-compose.yml`: контейнер **frontend** подключён к сети как `network_mode: service:backend` — у nginx и uvicorn **один** сетевой стек. Запросы к API идут на **`http://127.0.0.1:8000`** внутри этого стека (не через имя `backend` в DNS).

1. Логи: `docker-compose logs backend` и `docker-compose logs frontend`.
2. С хоста (порт из `PORT`, по умолчанию 3000): `curl -s http://127.0.0.1:3000/healthz` не сработает для API — healthz на бэкенде внутри контейнера. Проверка: `docker-compose exec backend curl -sf http://127.0.0.1:8000/healthz` — должен быть `{"status":"ok"}`.
3. Если exec падает — backend не слушает 8000 (смотри traceback в `logs backend`).
4. После смены compose **обязательно** пересобери образы: `docker-compose build --no-cache frontend backend && docker-compose up -d`.

## 9. Ошибка деплоя **`KeyError: 'ContainerConfig'`** (docker-compose)

Типично для **docker-compose 1.29.x** и **Docker Engine 24+**: при пересоздании контейнера ломается разбор метаданных образа.

**Что сделать на сервере (лучший вариант):** установить Compose V2 как плагин Docker:

```bash
sudo apt-get update
sudo apt-get install -y docker-compose-plugin
docker compose version
```

Дальше используй **`docker compose`** (с пробелом) вместо **`docker-compose`**.

**Без смены пакета:** перед `up` полностью останавливай стек (так делает GitHub Actions в этом репозитории):

```bash
cd /opt/trend_logistics   # твой DEPLOY_PATH
docker-compose down --remove-orphans
docker-compose build
docker-compose up -d
```
