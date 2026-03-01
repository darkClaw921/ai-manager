<p align="center">
  <h1 align="center">AI Lead Manager</h1>
  <p align="center">
    <strong>AI-агент для автоматической квалификации лидов через Telegram и веб-виджет</strong>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white" alt="Python 3.12">
    <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI">
    <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black" alt="React 19">
    <img src="https://img.shields.io/badge/Claude-API-cc785c?logo=anthropic&logoColor=white" alt="Claude API">
    <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" alt="Docker">
    <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL">
  </p>
</p>

---

## Что это?

**AI Lead Manager** — полноценная система, которая заменяет первичного менеджера по продажам. AI-агент на базе Claude ведёт диалог с потенциальными клиентами, квалифицирует их по настраиваемому скрипту, отвечает на вопросы с помощью RAG (база знаний FAQ + обработка возражений) и записывает на консультацию — всё без участия человека.

## Ключевые возможности

### AI-диалоги
- Многоэтапная квалификация лидов по настраиваемому скрипту (выявление потребностей, бюджет, сроки, ЛПР)
- RAG-поиск по базе знаний FAQ и шаблонам обработки возражений (Qdrant + sentence-transformers)
- Автоматический расчёт interest score (0–100) на основе пройденных этапов
- Tool use: запись на встречу, передача менеджеру, обновление данных лида

### Каналы коммуникации
- **Telegram Bot** — полноценный бот с webhook-интеграцией, inline-кнопками для записи
- **Web Widget** — встраиваемый чат-виджет (Preact) с WebSocket-подключением в реальном времени и REST-fallback

### Админ-панель
- Дашборд с аналитикой (графики по дням, по статусам, по каналам, воронка конверсии)
- Управление лидами с фильтрацией, поиском и детализацией
- Просмотр диалогов в формате чата с возможностью паузы, передачи и завершения
- Редактор квалификационных скриптов, FAQ и обработки возражений
- Управление каналами (Telegram, Web Widget) с тестированием подключения
- Система бронирования с настройками доступности менеджеров
- Системные настройки (AI-модель, приветствие, интеграции, уведомления)
- Управление пользователями с ролями (admin / manager)

### Интеграции
- **CRM** — отправка лидов через webhook (универсальная интеграция)
- **Google Sheets** — экспорт лидов и аналитики
- **Уведомления** — webhook + Telegram-уведомления о новых лидах, квалификации, записях
- **CSV-экспорт** — выгрузка данных из аналитики

### Фоновые задачи (Celery)
- Периодическая синхронизация FAQ и возражений с Qdrant (каждые 5 мин)
- Ежедневный расчёт аналитики с опциональным экспортом в Google Sheets
- Мониторинг «зависших» диалогов (старше 24ч) с уведомлениями

## Архитектура

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│  Telegram    │     │  Web Widget  │     │   Admin Panel    │
│  Bot :8443   │     │  :3001       │     │   :3000          │
└──────┬───────┘     └──────┬───────┘     └──────┬───────────┘
       │                    │                    │
       │     ┌──────────────┴────────────────────┘
       │     │
       ▼     ▼
┌──────────────────────────────────────────────────────────┐
│                    FastAPI Backend :8000                  │
│  ┌─────────┐  ┌───────────┐  ┌────────┐  ┌───────────┐  │
│  │   API   │  │    AI     │  │ Tools  │  │  Channels │  │
│  │ Routes  │  │  Engine   │  │Handler │  │  Adapters │  │
│  └─────────┘  └───────────┘  └────────┘  └───────────┘  │
│  ┌─────────┐  ┌───────────┐  ┌────────┐  ┌───────────┐  │
│  │Services │  │  RAG      │  │ Qualif.│  │Integration│  │
│  │  Layer  │  │ Pipeline  │  │  FSM   │  │   Layer   │  │
│  └─────────┘  └───────────┘  └────────┘  └───────────┘  │
└─────────┬──────────┬──────────────┬──────────────────────┘
          │          │              │
    ┌─────▼──┐  ┌────▼───┐  ┌──────▼──┐  ┌───────────┐
    │Postgres│  │ Qdrant │  │  Redis  │  │  Celery   │
    │  :5432 │  │  :6333 │  │  :6379  │  │  Worker   │
    └────────┘  └────────┘  └─────────┘  └───────────┘
```

## Tech Stack

| Слой | Технология |
|------|-----------|
| Backend API | Python 3.12, FastAPI, SQLAlchemy 2.x (async), Alembic |
| AI/LLM | Anthropic Claude API, sentence-transformers |
| Vector DB | Qdrant (cosine similarity, 384d) |
| Main DB | PostgreSQL 16 |
| Cache & Queue | Redis 7, Celery |
| Telegram Bot | python-telegram-bot (webhooks), httpx |
| Admin Panel | React 19, TypeScript, Vite, Ant Design, Recharts, Zustand |
| Web Widget | Preact, TypeScript, Vite, WebSocket |
| Infra | Docker Compose (8 сервисов) |

## Быстрый старт

### Требования

- Docker & Docker Compose
- Anthropic API ключ ([получить здесь](https://console.anthropic.com/))
- Telegram Bot Token (опционально, через [@BotFather](https://t.me/BotFather))

### Установка

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/your-repo/ai-manager.git
cd ai-manager

# 2. Скопируйте и настройте переменные окружения
cp .env.example .env

# 3. Заполните обязательные переменные в .env:
#    - ANTHROPIC_API_KEY=sk-ant-xxx
#    - JWT_SECRET_KEY=ваш-секретный-ключ
#    - TELEGRAM_BOT_TOKEN=xxx:yyy (если нужен Telegram)

# 4. Запустите все сервисы
docker compose up -d

# 5. Примените миграции БД
docker compose exec api alembic upgrade head

# 6. Создайте начальные данные (админ, настройки, скрипт квалификации)
docker compose exec api python -m app.db.seed
```

### Доступ

| Сервис | URL | Credentials |
|--------|-----|-------------|
| Admin Panel | http://localhost:3000 | admin@example.com / admin |
| API Docs (Swagger) | http://localhost:8000/docs | — |
| Health Check | http://localhost:8000/health | — |
| Widget (dev) | http://localhost:3001 | — |
| Qdrant Dashboard | http://localhost:6333/dashboard | — |

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://postgres:postgres@postgres:5432/ai_manager` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `QDRANT_HOST` | Qdrant server host | `qdrant` |
| `ANTHROPIC_API_KEY` | API ключ Anthropic | — (обязательно) |
| `JWT_SECRET_KEY` | Секрет для JWT токенов | `change-me-in-production` |
| `JWT_EXPIRATION_MINUTES` | Время жизни access token | `60` |
| `TELEGRAM_BOT_TOKEN` | Токен Telegram бота | — (опционально) |
| `CORS_ORIGINS` | Разрешённые origins | `["http://localhost:3000","http://localhost:3001"]` |
| `CELERY_BROKER_URL` | Redis для Celery | `redis://redis:6379/1` |
| `CRM_WEBHOOK_URL` | Webhook для CRM-интеграции | — (опционально) |
| `GOOGLE_SHEETS_CREDENTIALS` | JSON credentials для Google Sheets | — (опционально) |

## Встраивание виджета

Добавьте на сайт одну строку:

```html
<script src="http://localhost:3001/embed.js" data-channel-id="YOUR_CHANNEL_ID"></script>
```

Виджет появится в правом нижнем углу. `channel_id` можно получить в админ-панели в разделе Каналы.

## API

Полная документация API доступна по адресу `/docs` (Swagger UI) после запуска backend.

### Основные эндпоинты

```
POST   /api/v1/auth/login              # Авторизация
POST   /api/v1/auth/refresh             # Обновление токена

GET    /api/v1/leads                    # Список лидов (фильтры, пагинация)
GET    /api/v1/leads/{id}               # Детали лида
PUT    /api/v1/leads/{id}               # Обновление лида

GET    /api/v1/conversations            # Список диалогов
GET    /api/v1/conversations/{id}       # Детали диалога с сообщениями
PUT    /api/v1/conversations/{id}/status # Изменение статуса

CRUD   /api/v1/scripts/qualification    # Скрипты квалификации
CRUD   /api/v1/scripts/faq             # FAQ записи
CRUD   /api/v1/scripts/objections      # Обработка возражений

CRUD   /api/v1/channels                # Каналы коммуникации
CRUD   /api/v1/bookings                # Записи на консультации

GET    /api/v1/analytics/dashboard     # Дашборд
GET    /api/v1/analytics/leads         # Статистика лидов
GET    /api/v1/analytics/funnel        # Воронка конверсии
GET    /api/v1/analytics/export        # CSV экспорт

WS     /api/v1/widget/ws              # WebSocket для виджета
POST   /api/v1/widget/init            # Инициализация сессии виджета
POST   /api/v1/widget/messages        # REST fallback для сообщений
```

## Структура проекта

```
ai-manager/
├── backend/                 # FastAPI backend (Python 3.12)
│   ├── app/
│   │   ├── api/            # REST API endpoints
│   │   ├── ai/             # AI engine (LLM, RAG, qualification FSM, prompts)
│   │   ├── models/         # SQLAlchemy models (11 таблиц)
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic layer
│   │   ├── channels/       # Channel adapters (Telegram, WebWidget)
│   │   ├── integrations/   # CRM, Google Sheets, webhooks
│   │   ├── tasks/          # Celery background tasks
│   │   └── db/             # Database session, repository, seed
│   └── alembic/            # Database migrations
├── telegram-bot/            # Telegram bot service
│   └── bot/
│       ├── handlers/       # Command & message handlers
│       ├── api_client.py   # Backend API client
│       └── main.py         # Bot entry point (webhook mode)
├── admin/                   # Admin panel (React 19 + Ant Design)
│   └── src/
│       ├── pages/          # 10 страниц (Dashboard, Leads, Conversations...)
│       ├── api/            # Typed API client with JWT refresh
│       ├── store/          # Zustand auth store
│       └── components/     # Layout, ProtectedRoute
├── widget/                  # Chat widget (Preact)
│   └── src/
│       ├── Widget.tsx      # Chat UI component
│       ├── api.ts          # WebSocket + REST client
│       └── embed.js        # IIFE loader for iframe embedding
├── nginx/                   # Nginx reverse proxy
├── docker-compose.yml       # 8 сервисов
└── .env.example            # Шаблон переменных окружения
```

## База данных

11 таблиц:

- `admin_users` — Пользователи админ-панели (admin / manager)
- `channels` — Каналы коммуникации (Telegram, Web Widget)
- `leads` — Лиды с данными квалификации и interest score
- `conversations` — Диалоги, привязанные к лидам и каналам
- `messages` — Сообщения диалогов (user / assistant / system)
- `qualification_scripts` — Скрипты квалификации с этапами
- `faq_items` — FAQ для RAG-поиска
- `objection_scripts` — Шаблоны обработки возражений
- `bookings` — Записи на консультации
- `booking_settings` — Настройки доступности менеджеров
- `system_settings` — Системные настройки (key-value)

## Как это работает

```
Пользователь пишет в Telegram / виджет
         │
         ▼
   Channel Adapter (Telegram / WebWidget)
         │
         ▼
   ConversationEngine.process_message()
         │
         ├── 1. Сохраняет сообщение в БД
         ├── 2. ContextBuilder: история + RAG + квалификация
         ├── 3. Claude API (с tool_use loop, макс. 5 итераций)
         ├── 4. ToolHandler: запись, передача, обновление лида
         ├── 5. Обновляет этап квалификации + interest score
         └── 6. Сохраняет ответ, возвращает клиенту
```

### Этапы квалификации

```
INITIAL → NEEDS_DISCOVERY → BUDGET_CHECK → TIMELINE_CHECK
    → DECISION_MAKER → QUALIFIED → BOOKING_OFFERED
    → BOOKED → HANDED_OFF
```

Каждый этап добавляет до 25 баллов к interest score (макс. 100).


## Добавление админа
 docker compose exec api uv run -m app.db.create_admin \                                                                                                                                     
    --email admin@admin.ru --password admin --name "Admin" --role admin
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_manager \
    uv run -m app.db.create_admin


## TODO
удаление канала удаеляет также все его диалоги и лиды

## Лицензия

MIT
