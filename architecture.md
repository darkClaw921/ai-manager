# AI Lead Manager -- Architecture

## Overview

AI-agent that replaces a primary sales manager for lead qualification via Telegram and web widget channels. Built with FastAPI + PostgreSQL + Qdrant + Redis + Anthropic Claude.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python 3.12 + FastAPI |
| ORM | SQLAlchemy 2.x (async) + Alembic |
| Main DB | PostgreSQL 16 |
| Vector DB | Qdrant |
| Cache/Queue | Redis 7 |
| AI/LLM | Anthropic Claude API, OpenAI API, OpenRouter API |
| Embeddings | sentence-transformers |
| Telegram Bot | Direct Telegram Bot API via httpx (multi-bot, no separate service) |
| Admin Frontend | React 19 + TypeScript + Vite + Ant Design |
| Web Widget | Preact + Vite + TypeScript |
| Background Tasks | Celery + Redis |
| Containerization | Docker Compose |

## Project Structure

```
ai-manager/
├── docker-compose.yml          # All 7 services orchestration (no separate telegram-bot)
├── .env.example                # Environment variables template
├── architecture.md             # This file
├── backend/
│   ├── Dockerfile              # Python 3.12-slim + uv
│   ├── .dockerignore
│   ├── pyproject.toml          # Dependencies and tooling config (includes openai, gspread, google-auth)
│   ├── alembic.ini             # Alembic configuration
│   ├── alembic/
│   │   ├── env.py              # Async migration runner
│   │   ├── script.py.mako      # Migration template
│   │   └── versions/
│   │       ├── 2026_02_25_0001_initial_schema.py  # All 11 tables
│   │       ├── 2026_02_26_0002_keywords_array_to_jsonb.py  # faq_items.keywords text[] -> JSONB
│   │       ├── 2026_02_26_0003_add_channel_script_fk.py  # channels.qualification_script_id FK
│   │       ├── 2026_02_28_0004_add_manager_id_to_conversations.py  # conversations.manager_id FK
│   │       ├── 2026_02_28_0005_add_owner_id_to_resources.py  # owner_id FK to channels, scripts, system_settings
│   │       └── 2026_02_28_0006_add_script_binding_and_score_config.py  # qualification_script_id FK to faq_items/objection_scripts, score_config to qualification_scripts
│   └── app/
│       ├── __init__.py
│       ├── main.py             # FastAPI app factory, lifespan (polling/webhook init per channel), CORS, /health
│       ├── config.py           # Pydantic Settings (all env vars)
│       ├── dependencies.py     # FastAPI DI: get_db(), get_current_user(), require_admin(), get_effective_owner_id(), EffectiveOwnerId type alias
│       ├── middleware.py       # RequestLoggingMiddleware: request_id, timing, structlog contextvars
│       ├── logging_config.py   # setup_logging(): structlog + stdlib, JSON (prod) / console (dev)
│       ├── rate_limit.py       # slowapi Limiter (Redis backend), rate_limit_exceeded_handler (429)
│       ├── api/
│       │   ├── __init__.py
│       │   ├── router.py       # API router aggregator (prefix /api/v1)
│       │   ├── auth.py         # POST /auth/login, POST /auth/refresh (JWT), POST /auth/register (public, rate-limited 3/min, creates manager + BookingSettings + default SystemSettings)
│       │   ├── leads.py        # GET/PUT/DELETE /leads (filters, pagination, owner_id scoping via Channel JOIN)
│       │   ├── conversations.py # GET /conversations, GET /conversations/{id}, PUT /conversations/{id}/status (with transition validation + system messages), POST /conversations/{id}/messages (manager sends message to client), DELETE /conversations/{id} — all with owner_id scoping via Channel JOIN
│       │   ├── scripts.py      # CRUD qualification scripts, FAQ, objections + Qdrant sync + bulk text import via LLM parse — all with owner_id scoping
│       │   ├── channels.py     # CRUD channels (webhook/polling mode switching, script_id validation, owner_id scoping) + POST /channels/{id}/test
│       │   ├── bookings.py     # CRUD bookings + GET/PUT /bookings/settings — owner_id scoping via Lead→Channel JOIN
│       │   ├── settings.py     # GET/PUT /settings (bulk system settings, per-manager fallback), get_settings_for_owner() helper
│       │   ├── users.py        # CRUD admin_users (admin-only), auto-manages BookingSettings for manager role
│       │   ├── analytics.py    # GET /analytics/dashboard, /leads, /funnel, /export — all with owner_id scoping
│       │   ├── managers.py     # GET /managers (list with stats, admin-only), GET /managers/{id}/stats (detailed stats, admin-only)
│       │   ├── webhooks.py     # POST /webhooks/telegram/{channel_id}/init, /message, /update — thin wrappers delegating to TelegramUpdateHandler
│       │   ├── ws_manager.py   # ConnectionManager singleton: WebSocket connection registry
│       │   └── widget.py       # WebSocket + REST endpoints for chat widget
│       ├── models/
│       │   ├── __init__.py     # Re-exports all models
│       │   ├── base.py         # Base (DeclarativeBase), UUIDMixin, TimestampMixin
│       │   ├── user.py         # AdminUser, UserRole enum, channels relationship
│       │   ├── channel.py      # Channel (with qualification_script_id FK, owner_id FK + relationships), ChannelType enum
│       │   ├── lead.py         # Lead, LeadStatus enum
│       │   ├── conversation.py # Conversation (with manager_id FK + relationship), Message, ConversationStatus/MessageRole/MessageType enums
│       │   ├── script.py       # QualificationScript (with owner_id FK, score_config JSON, faq_items/objection_scripts relationships), FAQItem (with owner_id FK, qualification_script_id FK), ObjectionScript (with owner_id FK, qualification_script_id FK)
│       │   ├── booking.py      # Booking, BookingSettings, BookingStatus/BookingMode enums
│       │   └── settings.py     # SystemSettings (key-value JSONB, owner_id FK, UNIQUE(key, owner_id))
│       ├── db/
│       │   ├── __init__.py
│       │   ├── session.py      # Async engine, sessionmaker, get_db_session()
│       │   ├── seed.py         # Initial admin, system settings, qualification script
│       │   ├── create_admin.py # CLI script: create admin/manager user (interactive or --email/--password/--name/--role args)
│       │   └── repository.py   # BaseRepository[T]: generic async CRUD (get, get_multi, create, update, delete)
│       ├── schemas/
│       │   ├── __init__.py     # Re-exports all schemas
│       │   ├── common.py       # PaginationParams, PaginatedResponse[T] (generic)
│       │   ├── auth.py         # LoginRequest, TokenResponse, RefreshRequest, RegisterRequest, RegisterResponse
│       │   ├── user.py         # UserCreate, UserUpdate, UserResponse
│       │   ├── lead.py         # LeadResponse, LeadUpdateRequest, LeadFilter
│       │   ├── conversation.py # ConversationResponse, ConversationDetailResponse (with manager_id/name), MessageResponse (with metadata_), ConversationStatusUpdate, SendManagerMessageRequest/Response
│       │   ├── script.py       # QualificationScript/FAQItem/ObjectionScript Create/Update/Response
│       │   ├── channel.py      # ChannelCreate (with qualification_script_id), ChannelUpdate, ChannelResponse (with script_name)
│       │   ├── booking.py      # BookingCreate/Update/Response, BookingSettingsUpdate/Response
│       │   ├── manager.py      # ManagerWithStats, ManagerDetailStats
│       │   ├── settings.py     # SystemSettingsResponse, SystemSettingsUpdate
│       │   ├── analytics.py    # DashboardResponse, LeadStatsResponse, FunnelResponse, FunnelStage
│       │   └── messages.py     # IncomingMessageSchema, OutgoingMessageSchema
│       ├── services/
│       │   ├── __init__.py     # Re-exports all services (AnalyticsService, ConversationService, LeadService, auth functions)
│       │   ├── auth_service.py # verify_password, create_access/refresh_token, authenticate_user, decode_token
│       │   ├── conversation_service.py  # ConversationService: get_or_create, messages, status, list
│       │   ├── lead_service.py          # LeadService: get_or_create, update, qualification, list
│       │   ├── analytics_service.py     # AnalyticsService: dashboard, lead_stats, funnel, qualification_breakdown (Redis cache) — all methods accept owner_id for scoping via Channel JOIN
│       │   ├── telegram_webhook_service.py # TelegramWebhookService: setWebhook, deleteWebhook, getUpdates, getMe, answerCallbackQuery
│       │   ├── telegram_update_handler.py # TelegramUpdateHandler: routes Telegram Updates; build_engine(db) with per-owner LLM; AI gate for HANDED_OFF
│       │   └── telegram_polling_service.py # TelegramPollingService: manages per-channel asyncio long-polling tasks (start_polling, stop_polling, stop_all, _polling_loop with backoff)
│       ├── ai/
│       │   ├── __init__.py     # Re-exports all AI engine classes
│       │   ├── base_client.py  # BaseLLMClient ABC, MessageResponse dataclass (shared by all providers)
│       │   ├── llm_client.py   # AnthropicClient (BaseLLMClient): AsyncAnthropic wrapper, tenacity retry; LLMClient alias
│       │   ├── openai_client.py # OpenAIClient (BaseLLMClient): AsyncOpenAI wrapper with format conversion
│       │   ├── openrouter_client.py # OpenRouterClient (OpenAIClient): OpenRouter via OpenAI SDK, custom base_url
│       │   ├── format_converter.py  # Anthropic <-> OpenAI format converters (tools, messages, responses)
│       │   ├── client_factory.py    # create_llm_client(db, owner_id): factory with per-owner API key support
│       │   ├── embeddings.py   # EmbeddingsManager: sentence-transformers, lazy load, thread pool
│       │   ├── rag.py          # RAGPipeline: FAQ/objection search via Qdrant with owner_id + script_id filtering
│       │   ├── qdrant_init.py  # ensure_collections, sync_faq/objections_to_qdrant (stores owner_id + script_id in payload)
│       │   ├── qualification.py # QualificationStage enum, QualificationStateMachine, STAGE_LABELS, compute_score_breakdown()
│       │   ├── prompts.py      # System/stage/RAG/greeting prompt templates (Russian)
│       │   ├── tools.py        # Tool definitions (Anthropic format), ToolHandler (with _score_history tracking), ToolResult, ToolContext
│       │   ├── context_builder.py # ContextBuilder: assembles LLMContext (with owner_id, script_id, score_config) from DB+RAG+qualification
│       │   └── engine.py       # ConversationEngine: orchestrator with per-owner LLM client via db_session
│       ├── channels/
│       │   ├── __init__.py     # Re-exports AbstractChannelAdapter, IncomingMessage, WebWidgetAdapter
│       │   ├── base.py         # AbstractChannelAdapter ABC, IncomingMessage dataclass
│       │   ├── telegram.py     # TelegramAdapter: send_message, process_incoming, send_booking_prompt via HTTP API
│       │   └── web_widget.py   # WebWidgetAdapter: WebSocket-based channel adapter
│       ├── integrations/
│       │   ├── __init__.py     # Re-exports: BaseCRMIntegration, WebhookCRM, MockCRM, GoogleSheetsExporter, WebhookNotifier
│       │   ├── crm.py          # BaseCRMIntegration ABC, WebhookCRM, MockCRM, get_crm_integration() factory
│       │   ├── google_sheets.py # GoogleSheetsExporter: gspread service account, export_leads(), export_analytics()
│       │   └── webhook_notifier.py # WebhookNotifier: HTTP webhook + Telegram chat notifications (fire-and-forget)
│       └── tasks/
│           ├── __init__.py     # Package docstring
│           ├── celery_app.py   # Celery app config, Redis broker/backend, Beat schedule (qdrant sync, daily analytics, stale conversations)
│           ├── crm_sync.py     # sync_lead_to_crm task: sync lead data to CRM via webhook
│           ├── qdrant_sync.py  # sync_faq_collection, sync_objections_collection, sync_single_faq tasks
│           └── analytics.py    # calculate_daily_analytics, check_stale_conversations tasks
│   └── tests/
│       ├── conftest.py         # Shared pytest fixtures: test_engine (SQLite+StaticPool), factory fixtures, app/client HTTP fixtures
│       ├── test_ai/
│       │   ├── test_qualification.py # QualificationStateMachine unit tests (55 tests)
│       │   └── test_prompts.py       # Prompt building unit tests
│       ├── test_services/
│       │   ├── test_lead_service.py         # LeadService integration tests (30 tests)
│       │   └── test_conversation_service.py # ConversationService integration tests
│       └── test_api/
│           ├── test_auth.py    # Auth endpoint tests: login, refresh (6 tests)
│           ├── test_leads.py   # Leads CRUD endpoint tests (13 tests)
│           └── test_widget.py  # Widget history + WebSocket endpoint tests (7 tests)
├── telegram-bot/
│   ├── Dockerfile              # Python 3.12-slim + uv, port 8443, CMD python -m bot.main
│   ├── .dockerignore
│   ├── pyproject.toml          # python-telegram-bot[webhooks], httpx, pydantic-settings, structlog
│   └── bot/
│       ├── __init__.py
│       ├── config.py           # BotSettings(BaseSettings), get_bot_settings()
│       ├── api_client.py       # BackendAPIClient: init_conversation, send_message, get_conversation_status
│       ├── main.py             # Application builder, webhook mode, handler registration
│       └── handlers/
│           ├── __init__.py
│           ├── start.py        # /start command handler
│           ├── conversation.py # Text message handler, booking callback handler
│           └── fallback.py     # Non-text message fallback
├── admin/
│   ├── Dockerfile              # Multi-stage: node:20-alpine build + nginx:alpine serve
│   ├── nginx.conf              # Gzip, /api proxy to api:8000, SPA fallback, cache headers, port 3000
│   ├── .dockerignore
│   ├── package.json            # React 19, antd, react-router-dom, @tanstack/react-query, axios, zustand, recharts, dayjs, framer-motion
│   ├── vite.config.ts          # Proxy /api->:8000, alias @/->src/, seoPlugin (generates sitemap.xml + robots.txt at build time, replaces %VITE_APP_URL% in HTML)
│   ├── tsconfig.json           # References: tsconfig.app.json, tsconfig.node.json
│   ├── tsconfig.app.json       # React JSX, strict, ES2020, path alias @/
│   ├── tsconfig.node.json      # For vite.config.ts
│   ├── index.html              # Entry point for Vite, SEO meta tags (OG, Twitter Cards, JSON-LD SoftwareApplication + FAQPage), %VITE_APP_URL% placeholders replaced at build time
│   └── public/
│       └── vite.svg             # Favicon
│   └── src/
│       ├── main.tsx            # ReactDOM.createRoot, StrictMode
│       ├── App.tsx             # BrowserRouter, ConfigProvider (ruRU, blue theme), QueryClientProvider, all routes; LandingOrDashboard component at / (landing for guests, /dashboard redirect for auth users)
│       ├── vite-env.d.ts       # Vite type reference
│       ├── api/
│       │   ├── client.ts       # Axios instance with JWT + impersonation interceptor (request: Bearer token + X-Impersonate-Manager-Id, response: 401 refresh, 403/500 notifications)
│       │   └── index.ts        # All typed API functions: authAPI (login, refresh, register), leadsAPI, conversationsAPI, scriptsAPI, channelsAPI, bookingsAPI, settingsAPI, usersAPI, managersAPI (getAll, getStats), analyticsAPI
│       ├── store/
│       │   ├── authStore.ts    # Zustand + persist: token, refreshToken, user, isAuthenticated; login, logout, refreshAccessToken
│       │   ├── themeStore.ts   # Zustand + persist: isDark, toggleTheme; dark/light theme switching with localStorage
│       │   ├── impersonationStore.ts  # Zustand + persist (sessionStorage): impersonatedManagerId, impersonatedManagerName, isImpersonating; startImpersonation, stopImpersonation
│       │   └── onboardingStore.ts  # Zustand + persist (localStorage): currentStep, completedByUser (per userId); setStep, nextStep, prevStep, completeOnboarding, isCompleted
│       ├── hooks/
│       │   └── useAuth.ts      # Auth hook: user, isAuthenticated, isLoading, logout; redirects to /login if not authenticated
│       ├── components/
│       │   ├── ProtectedRoute.tsx  # Navigate to / (landing) if not authenticated
│       │   ├── ImpersonationBanner.tsx  # Warning banner when admin impersonates a manager; shows name + exit button
│       │   ├── MainLayout.tsx      # Ant Design Layout: collapsible Sider (10 menu items with adminOnly/managerOnly flags), ImpersonationBanner, Header, Content (Outlet); auto-redirects new managers to /onboarding
│       │   └── landing/
│       │       └── AnimatedSection.tsx  # Reusable framer-motion wrapper: fade-in-up on viewport enter, delay prop, once:true
│       ├── pages/
│       │   ├── LandingPage.tsx         # SEO-optimized landing (route /): Hero, Stats, Testimonials (3), Features (6), How it works (4), Lead Preview, FAQ (6 items), CTA, semantic HTML
│       │   ├── LoginPage.tsx           # Centered Card + Form (email, password), validation, error notifications
│       │   ├── OnboardingPage.tsx       # Manager onboarding page (6 steps): welcome, qualification script, knowledge base, channel, AI settings, done; vertical Steps sidebar, navigates to relevant pages; auto-redirect on first login
│       │   ├── DashboardPage.tsx       # Statistic cards, LineChart (leads/day), BarChart (by status), PieChart (by channel), funnel chart, recent tables
│       │   ├── LeadsPage.tsx           # Table with filters (status, date, search), qualification_stage_label column, Drawer with fresh data fetch (useQuery), Steps qualification progress, score breakdown Table, score history Timeline, delete with Popconfirm, Progress for interest_score
│       │   ├── ConversationsPage.tsx   # Table with filters (status, date, lead_id from URL), delete with Popconfirm, lead_id Tag indicator, click to navigate to detail
│       │   ├── ConversationDetailPage.tsx  # Chat view (user=blue right, assistant=grey left, system=gold center), sidebar info, action buttons (pause/handoff/complete), 5s auto-refresh
│       │   ├── ScriptsPage.tsx         # 3 Tabs: Qualification (Collapse with stage cards + score weights section with InputNumber per stage + Save button calling updateScoreConfig, visual Form.List editor with Segmented visual/JSON mode toggle + score_config in modal, AI generate modal), FAQ (Table + CRUD Modal with qualification_script_id Select + Qdrant sync + bulk text import modal with script Select + filter Select by script), Objections (Table + CRUD Modal with qualification_script_id Select + Qdrant sync + bulk text import modal with script Select + filter Select by script)
│       │   ├── ChannelsPage.tsx        # Card layout, dynamic form (Telegram: bot_token + bot_mode selector; WebWidget: origins + theme), mode Tag on cards (Webhook blue / Long Polling orange), qualification script Select (allowClear, loads via useQuery), purple Tag with script name on cards, Switch toggle, embed code copy, test connection
│       │   ├── BookingsPage.tsx        # 2 Tabs: Bookings list (Table + confirm/cancel), Settings (per-manager form: days, hours, slot, timezone, mode)
│       │   ├── SettingsPage.tsx        # Collapse sections: AI, Greeting (preview), Integrations, Notifications; save/undo with unsaved indicator
│       │   ├── UsersPage.tsx           # Table, create/edit Modal (email, password, full_name, role), admin-only, cannot delete self
│       │   ├── ManagersPage.tsx       # Admin-only table of managers with stats (channels/leads/conversations counts), impersonation button per row
│       │   └── RegisterPage.tsx       # Public registration form (name, email, password, confirm), auto-login on success, link to login
│       └── types/
│           └── index.ts        # All TypeScript interfaces: AdminUser, Lead, Conversation, Message, Channel, QualificationScript (with score_config), FAQItem (with qualification_script_id), ObjectionScript (with qualification_script_id), Booking, BookingSettings, SystemSetting, PaginatedResponse, TokenResponse, DashboardData, LeadStats, FunnelData, ManagerWithStats, ManagerDetailStats, RegisterRequest
└── widget/
    ├── Dockerfile              # Multi-stage: node:20-alpine build + nginx:alpine serve
    ├── nginx.conf              # Gzip, SPA fallback, CORS, cache headers
    ├── package.json            # Preact, @preact/signals, Vite, TypeScript
    ├── tsconfig.json           # Preact JSX, ES2015 target
    ├── vite.config.ts          # Preact preset, multi-entry (widget + embed)
    ├── index.html              # Dev/build entry point
    ├── embed.js                # IIFE loader: creates iframe with widget on host pages
    └── src/
        ├── main.tsx            # Bootstrap: reads channel_id from URL, creates ChatAPI, renders Widget
        ├── Widget.tsx          # Chat UI: bubble button, message list, input, typing indicator
        ├── api.ts              # ChatAPI: WebSocket + REST client with reconnection
        └── styles.css          # Widget styles with CSS variables, animations, mobile responsive
```

## Docker Services

| Service | Image | Port | Description |
|---------|-------|------|-------------|
| postgres | postgres:16 | 5432 | Main database, volume: pg_data |
| qdrant | qdrant/qdrant:latest | 6333 | Vector DB for FAQ/objection RAG |
| redis | redis:7-alpine | 6379 | Cache, sessions, Celery broker |
| api | backend/Dockerfile | 8000 | FastAPI backend |
| worker | backend/Dockerfile | - | Celery worker (same image as api) |
| ~~telegram-bot~~ | ~~removed~~ | — | Telegram handled directly by api service via webhook |
| admin | admin/Dockerfile | 3000 | Admin SPA (React + Ant Design, nginx) |
| widget | widget/Dockerfile | 3001 | Chat widget (nginx), depends on api |

## Database Schema (11 tables)

- **admin_users** -- Admin/manager accounts (email, password_hash, role, is_active)
- **channels** -- Communication channels (type: telegram/web_widget, config JSONB)
- **leads** -- Leads with qualification data (status, interest_score, qualification_data JSONB)
- **conversations** -- Conversations linked to leads and channels (status, started_at, ended_at, manager_id FK to admin_users)
- **messages** -- Chat messages (role, content, message_type, metadata JSONB)
- **qualification_scripts** -- Qualification scripts with stages (JSONB array)
- **faq_items** -- FAQ entries for RAG (question, answer, keywords array)
- **objection_scripts** -- Objection handling patterns (pattern, response_template)
- **bookings** -- Consultation bookings (lead_id, manager_id, scheduled_at, status)
- **booking_settings** -- Manager availability config (available_days/hours JSONB, booking_mode)
- **system_settings** -- Key-value system settings (JSONB value)

## Interest Score (Механизм расчёта)

Interest Score — числовое значение 0–100, отражающее степень квалификации лида. Хранится в поле `leads.interest_score`.

### Расчёт

Реализован в `QualificationStateMachine.calculate_interest_score()` ([backend/app/ai/qualification.py](backend/app/ai/qualification.py)). Работает по принципу суммирования весов пройденных квалификационных этапов. Поддерживает два режима:

**Режим по умолчанию** (когда `score_config` не задан):

| Этап | Вес |
|------|-----|
| `needs_discovery` | 25 |
| `budget_check` | 25 |
| `timeline_check` | 25 |
| `decision_maker` | 25 |

**Кастомный режим** (когда в `QualificationScript.score_config` заданы пользовательские веса): используются веса из `score_config` (формат `{"stage_id": weight}`).

Этап считается пройденным, если его ключ присутствует в словаре `qualification_data` лида. Итоговый балл = сумма весов пройденных этапов, ограничен `min(score, 100)`.

### Жизненный цикл обновления

1. **Инициализация (score = 0)**: При создании лида (`LeadService.get_or_create_lead()`) и при старте первого диалога (`ConversationEngine.start_conversation()`) — score устанавливается в 0.

2. **Продвижение через LLM tool_use**: LLM вызывает инструмент `advance_qualification` (определён в [backend/app/ai/tools.py](backend/app/ai/tools.py)), когда считает, что собрана ключевая информация текущего этапа. Обработчик `_advance_qualification()`:
   - Фиксирует `current_stage_value` и `score_before` ДО вызова advance.
   - Вызывает `QualificationStateMachine.advance(collected_data)` — записывает данные в `qualification_data` и переключает этап на следующий по `TRANSITIONS`.
   - Вызывает `calculate_interest_score()` — пересчитывает балл на основе обновлённого `qualification_data`.
   - Вычисляет `score_delta` и сохраняет запись в `_score_history` внутри `qualification_data` (stage, score_added, total_score, info).
   - Возвращает новый этап и балл в ответе инструмента.

3. **Персистенция после каждого сообщения**: В `ConversationEngine.process_message()` ([backend/app/ai/engine.py](backend/app/ai/engine.py)) после завершения tool_use loop:
   - Вызывается `qualification_sm.calculate_interest_score()` — финальный пересчёт.
   - Результат сохраняется через `LeadService.update_qualification(lead_id, stage, data, score)` ([backend/app/services/lead_service.py](backend/app/services/lead_service.py)), который записывает `qualification_stage`, `qualification_data` и `interest_score` в таблицу `leads`.

4. **Авто-обновление статуса лида**: `LeadService.update_qualification()` дополнительно обновляет `lead.status` в зависимости от этапа:
   - `needs_discovery` / `budget_check` / `timeline_check` / `decision_maker` → `LeadStatus.QUALIFYING` (если был `NEW`)
   - `qualified` / `booking_offer` → `LeadStatus.QUALIFIED`

### Пример прогрессии

```
initial (0) → needs_discovery (25) → budget_check (50) → timeline_check (75) → decision_maker (100) → qualified (100)
```

### Отображение

- **Admin Panel** ([admin/src/pages/LeadsPage.tsx](admin/src/pages/LeadsPage.tsx)): Progress bar в таблице лидов, qualification_stage_label колонка. Drawer загружает свежие данные (GET /leads/{id}), показывает Steps прогресс квалификации, таблицу разбивки оценки, Timeline историю score.
- **Dashboard** ([admin/src/pages/DashboardPage.tsx](admin/src/pages/DashboardPage.tsx)): avg score в карточке статистики.
- **API**: Возвращается в `EngineResponse.interest_score` и в `LeadResponse.interest_score`.

## Key Files Detail

### [backend/app/config.py](backend/app/config.py)
`Settings(BaseSettings)` class with `get_settings()` cached factory. Groups: Database, Redis, Qdrant, JWT, Telegram (WEBHOOK_BASE_URL), CORS, Celery, Integrations. **API-ключи LLM не хранятся в env** — пользователи задают их через админ-панель, ключи хранятся в БД (system_settings).

### [backend/app/main.py](backend/app/main.py)
`create_app()` factory. Lifespan checks DB/Redis/Qdrant on startup, initializes Qdrant collections via `ensure_collections()`, creates `TelegramPollingService` (stored in `app.state.polling_service`), and for each active Telegram channel routes by `config.bot_mode`: `polling` channels start long-polling via `polling_service.start_polling()`, `webhook` channels register via `TelegramWebhookService.set_webhook()` (requires `WEBHOOK_BASE_URL`). On shutdown: `polling_service.stop_all()` then `engine.dispose()`. CORS middleware. GET /health endpoint. Includes `/api/v1` router.

### [backend/app/db/session.py](backend/app/db/session.py)
`create_async_engine` with asyncpg. `async_session_factory` (expire_on_commit=False). `get_db_session()` async context manager with auto-commit/rollback.

### [backend/app/dependencies.py](backend/app/dependencies.py)
`get_db()` -- FastAPI Depends yielding async session with commit/rollback. `get_current_user()` -- extracts JWT from Authorization header, validates token, returns AdminUser. `require_admin()` -- wraps get_current_user with role check for admin-only endpoints.

### [backend/app/models/base.py](backend/app/models/base.py)
`Base(AsyncAttrs, DeclarativeBase)`. `UUIDMixin` (uuid4 PK). `TimestampMixin` (created_at server_default, updated_at onupdate).

### [backend/app/db/seed.py](backend/app/db/seed.py)
Idempotent seed: admin@example.com (bcrypt), 9 system settings (incl. 3 empty API key placeholders: `anthropic_api_key`, `openai_api_key`, `openrouter_api_key`), default qualification script with 4 stages (NEEDS_DISCOVERY, BUDGET_CHECK, TIMELINE_CHECK, DECISION_MAKER). Run: `python -m app.db.seed`.

### [backend/app/tasks/celery_app.py](backend/app/tasks/celery_app.py)
Celery app with Redis broker and result backend. Includes 3 task modules (crm_sync, qdrant_sync, analytics). Beat schedule: FAQ/objections Qdrant sync every 5 minutes, daily analytics at 00:00 UTC, stale conversation check every hour. Autodiscover from `app.tasks`.

### [backend/app/tasks/crm_sync.py](backend/app/tasks/crm_sync.py)
`sync_lead_to_crm(lead_id)` -- loads lead from DB, sends to CRM via `get_crm_integration()`, updates lead metadata with sync result. Retry: 3 attempts, 60s delay.

### [backend/app/tasks/qdrant_sync.py](backend/app/tasks/qdrant_sync.py)
`sync_faq_collection()` -- full resync of FAQ items from PostgreSQL to Qdrant. `sync_objections_collection()` -- full resync of objections. `sync_single_faq(faq_id)` -- upsert or remove a single FAQ item (real-time update). All use `asyncio.run()` for async-to-sync bridge.

### [backend/app/tasks/analytics.py](backend/app/tasks/analytics.py)
`calculate_daily_analytics()` -- daily stats calculation (leads, qualified, bookings, avg score) with optional Google Sheets export. `check_stale_conversations()` -- finds active conversations older than 24h, sends webhook notifications.

### [backend/app/integrations/crm.py](backend/app/integrations/crm.py)
`BaseCRMIntegration` ABC with `sync_lead()`, `update_lead()`, `check_connection()`. `WebhookCRM` -- sends JSON payloads to a webhook URL with retry (3 attempts). `MockCRM` -- logs all calls, always succeeds. `get_crm_integration(webhook_url)` factory selects implementation.

### [backend/app/integrations/google_sheets.py](backend/app/integrations/google_sheets.py)
`GoogleSheetsExporter` -- exports leads and analytics to Google Sheets via gspread service account. `export_leads(leads_data)` appends rows to "Лиды" worksheet. `export_analytics(data)` appends row to "Аналитика" worksheet. Lazy client init, auto-creates worksheets. Gracefully skips when credentials are absent.

### [backend/app/integrations/webhook_notifier.py](backend/app/integrations/webhook_notifier.py)
`WebhookNotifier` -- fire-and-forget notifications via HTTP webhook and Telegram Bot API. Methods: `notify_new_lead()`, `notify_qualified_lead()`, `notify_booking()`, `notify_handoff()`. Each sends JSON to webhook URL and HTML message to Telegram chat. Configurable enabled_events filter. Errors logged, never block.

### [backend/app/services/analytics_service.py](backend/app/services/analytics_service.py)
`AnalyticsService(db, redis_client)` -- analytics queries with optional Redis caching (60s TTL). `get_dashboard(period)` -- summary stats. `get_lead_stats(period)` -- by day/status/channel with channel name resolution. `get_conversion_funnel()` -- stages with percentages. `get_avg_response_time()`. `get_qualification_breakdown()` -- by qualification stage.

### [backend/app/services/telegram_webhook_service.py](backend/app/services/telegram_webhook_service.py)
`TelegramWebhookService` -- manages Telegram Bot API interactions via httpx (timeout 45s). Methods: `set_webhook(bot_token, webhook_url, secret_token)`, `delete_webhook(bot_token)`, `get_updates(bot_token, offset, timeout, limit, allowed_updates)` (long-polling), `get_me(bot_token)` (validate token), `answer_callback_query(bot_token, callback_query_id, text)`. Static method: `generate_webhook_secret()` (secrets.token_urlsafe). Used by channels API, webhooks, and polling service.

### [backend/app/services/telegram_update_handler.py](backend/app/services/telegram_update_handler.py)
`TelegramUpdateHandler` -- stateless handler that routes a raw Telegram Update dict to the appropriate processing method. Public method: `handle_update(channel, update, db)` -- creates a TelegramAdapter, dispatches to `_handle_start`, `_handle_text_message`, or `_handle_callback_query`, closes the adapter in `finally`. Module-level function: `build_engine(db)` -- async factory that wires ConversationEngine with db_session for per-owner LLM client creation; shared by the handler and legacy webhook endpoints.

### [backend/app/services/telegram_polling_service.py](backend/app/services/telegram_polling_service.py)
`TelegramPollingService` -- manages per-channel asyncio long-polling tasks. One instance per application (stored in `app.state.polling_service`). Methods: `start_polling(channel_id, bot_token)` -- cancels existing task if any, deletes webhook, creates asyncio.Task with `_polling_loop`; `stop_polling(channel_id)` -- cancels and awaits task; `stop_all()` -- stops all active polling tasks (used during shutdown). Internal: `_polling_loop(channel_id, bot_token)` -- infinite loop using `TelegramWebhookService.get_updates()` with 30s long-poll, exponential backoff on errors (5s to 60s cap), periodic channel `is_active` check every 10 iterations; `_process_update(channel_id, update)` -- opens per-update DB session and delegates to `TelegramUpdateHandler.handle_update()`.

### [backend/alembic/env.py](backend/alembic/env.py)
Async migration runner using `async_engine_from_config`. Imports all models for autogenerate metadata.

### [backend/app/db/repository.py](backend/app/db/repository.py)
`BaseRepository[T]` -- generic async CRUD. Methods: `get(id)`, `get_multi(offset, limit, filters, order_by)`, `count(filters)`, `create(**kwargs)`, `update(entity, **kwargs)`, `delete(entity)`. Used by service layer.

### [backend/app/services/auth_service.py](backend/app/services/auth_service.py)
Authentication service. `verify_password(plain, hashed)` -- bcrypt. `create_access_token(user_id, role)` -- JWT with configurable expiry. `create_refresh_token(user_id)` -- JWT with 7-day expiry. `decode_token(token)` -- validates JWT, returns payload or None. `authenticate_user(db, email, password)` -- looks up active user, verifies password. `get_user_by_id(db, user_id)` -- gets active user.

### [backend/app/services/conversation_service.py](backend/app/services/conversation_service.py)
`ConversationService` -- business logic for conversations and messages. Methods: `get_or_create_conversation`, `get_conversation`, `get_messages`, `add_message`, `update_status`, `list_conversations`. Uses `BaseRepository`. `PaginatedResult` dataclass.

### [backend/app/services/lead_service.py](backend/app/services/lead_service.py)
`LeadService` -- business logic for leads. Methods: `get_or_create_lead` (channel_id + external_id), `get_lead`, `update_lead`, `update_qualification` (stage + data + score with auto-status), `list_leads`.

### [backend/app/api/auth.py](backend/app/api/auth.py)
POST `/auth/login` -- authenticates user, returns access_token + refresh_token + user. POST `/auth/refresh` -- validates refresh token, issues new token pair.

### [backend/app/api/leads.py](backend/app/api/leads.py)
GET `/leads` -- list with filters (status, channel_id, date_from, date_to, search) + server-side pagination (lightweight, includes `qualification_stage_label` but no breakdown). GET `/leads/{id}` -- single lead with full `score_breakdown`, `qualification_script_name`, `qualification_stage_label`. PUT `/leads/{id}` -- update. DELETE `/leads/{id}`. `_lead_response(lead, script, include_breakdown)` helper populates channel info, stage labels, and optional score breakdown from qualification script.

### [backend/app/api/conversations.py](backend/app/api/conversations.py)
GET `/conversations` -- list with filters + pagination (includes manager_name). GET `/conversations/{id}` -- detail with all messages (selectinload including manager). PUT `/conversations/{id}/status` -- update status with `ALLOWED_TRANSITIONS` validation (active->paused/completed/handed_off, paused->active/completed, handed_off->active/completed, completed is terminal); on handoff sets `manager_id` + system message "Менеджер {name} взял диалог"; on return to active clears `manager_id`/`ended_at` + system message "Менеджер вернул диалог боту". POST `/conversations/{id}/messages` -- manager sends message to client: validates status==HANDED_OFF, saves with `role=assistant` + `metadata_={sender: "manager", manager_id, manager_name}`, delivers via TelegramAdapter or WebWidgetAdapter. DELETE `/conversations/{id}` -- deletes conversation and all its messages.

### [backend/app/api/scripts.py](backend/app/api/scripts.py)
CRUD for qualification_scripts (GET/POST/PUT/DELETE `/scripts/qualification`). CRUD for faq_items (GET/POST/PUT/DELETE `/scripts/faq`). CRUD for objection_scripts (GET/POST/PUT/DELETE `/scripts/objections`). GET `/scripts/faq` and GET `/scripts/objections` support optional `script_id` query parameter for filtering by qualification_script_id. PUT `/scripts/qualification/{script_id}/score-config` -- updates score weights with stage_id validation against script stages (422 for invalid stage_ids or negative weights, 404 for missing scripts). POST `/scripts/faq/sync` and `/scripts/objections/sync` -- re-sync to Qdrant. POST `/scripts/faq/parse` and `/scripts/objections/parse` -- bulk text import via LLM: accepts BulkTextImport(text, qualification_script_id), sends to LLM via create_llm_client() with parsing prompt, strips markdown code fences, creates records in DB with optional qualification_script_id binding, returns created items. POST `/scripts/qualification/generate` -- generates a full qualification script from a business description via LLM: accepts BulkTextImport(text), sends to LLM with a Russian prompt instructing JSON object output (name, description, stages array), creates QualificationScript in DB, returns QualificationScriptResponse. Error handling: 422 for invalid JSON, 502 for LLM errors. Helper functions: `_extract_json_array()`, `_extract_json_object()`.

### [backend/app/api/channels.py](backend/app/api/channels.py)
CRUD for channels (GET/POST/PUT/DELETE `/channels`) with dual-mode Telegram support (webhook/polling). On create: `_validate_script_id()` checks script exists, then `_setup_telegram_channel()` starts polling or registers webhook based on `config.bot_mode`. On update: validates script_id, detects mode/token/active changes, tears down old mode via `_teardown_telegram_channel()` then sets up new mode. On delete: tears down active mode. POST `/channels/{id}/test` -- calls Telegram `getMe` API to validate bot token. Helper functions: `_register_telegram_webhook()`, `_deregister_telegram_webhook()`, `_setup_telegram_channel()`, `_teardown_telegram_channel()`, `_channel_response()` (populates qualification_script_name from relationship), `_validate_script_id()` (404 if script not found). Uses `request.app.state.polling_service` for polling management.

### [backend/app/api/bookings.py](backend/app/api/bookings.py)
CRUD for bookings with filters (status, manager_id, date_from, date_to). GET `/bookings/settings` -- loads all active managers, auto-creates missing BookingSettings, returns settings with `manager_name` from AdminUser.full_name. PUT `/bookings/settings/{id}` -- update individual booking settings.

### [backend/app/api/settings.py](backend/app/api/settings.py)
GET `/settings` -- all system settings (secret keys masked: last 4 chars visible). PUT `/settings` -- bulk update (key-value pairs); masked secret values are skipped to prevent overwriting. `SECRET_SETTING_KEYS` set defines which keys are treated as secrets (`anthropic_api_key`, `openai_api_key`, `openrouter_api_key`). Helper functions: `mask_secret_value()`, `is_masked_value()`, `_build_masked_response()`.

### [backend/app/api/users.py](backend/app/api/users.py)
CRUD for admin_users (admin-only via require_admin dependency). Password hashing on create/update. Cannot delete self. Auto-manages BookingSettings: creates on user creation with MANAGER role, handles role changes (creates/deletes BookingSettings), deletes BookingSettings before user deletion.

### [backend/app/api/analytics.py](backend/app/api/analytics.py)
GET `/analytics/dashboard?period=7d` -- summary via AnalyticsService (total/today/week/month leads, active conversations, qualification rate, bookings, avg score). GET `/analytics/leads?days=30` -- leads by day, by status, by channel. GET `/analytics/funnel` -- conversion funnel (new -> qualifying -> qualified -> booked -> handed_off). GET `/analytics/export` -- CSV export of all leads (StreamingResponse).

### [backend/app/schemas/common.py](backend/app/schemas/common.py)
`PaginationParams(page, page_size)`. `PaginatedResponse[T]` -- generic paginated wrapper (items, total, page, pages).

### [backend/app/schemas/auth.py](backend/app/schemas/auth.py)
`LoginRequest(email: EmailStr, password)`. `TokenResponse(access_token, refresh_token, token_type, user: UserResponse)`. `RefreshRequest(refresh_token)`.

### [backend/app/schemas/user.py](backend/app/schemas/user.py)
`UserResponse` (no password_hash, from_attributes). `UserCreate(email, password, full_name, role, is_active)`. `UserUpdate` (all optional).

### [backend/app/schemas/lead.py](backend/app/schemas/lead.py)
`ScoreBreakdownItem` (stage_id, stage_label, weight, completed, collected_info). `LeadResponse` (includes `channel_name`, `channel_type`, `score_breakdown`, `qualification_script_name`, `qualification_stage_label` optional fields), `LeadUpdateRequest`, `LeadFilter`.

### [backend/app/schemas/conversation.py](backend/app/schemas/conversation.py)
`ConversationResponse` (with manager_id, manager_name), `ConversationDetailResponse` (with messages, manager_id, manager_name), `MessageResponse` (with metadata_), `ConversationStatusUpdate`, `ConversationFilter`, `SendManagerMessageRequest(text)`, `SendManagerMessageResponse(id, content, created_at)`.

### [backend/app/schemas/script.py](backend/app/schemas/script.py)
Create/Update/Response for QualificationScript (includes `score_config: dict[str, int] | None`), FAQItem (includes `qualification_script_id: uuid.UUID | None`), ObjectionScript (includes `qualification_script_id: uuid.UUID | None`). `BulkTextImport(text, qualification_script_id)` -- request body for bulk text import endpoints. `ScoreConfigUpdate(score_config: dict[str, int])` -- request body for updating qualification script score weights.

### [backend/app/schemas/channel.py](backend/app/schemas/channel.py)
`ChannelCreate` (with optional qualification_script_id), `ChannelUpdate` (with optional qualification_script_id), `ChannelResponse` (with qualification_script_id and qualification_script_name).

### [backend/app/schemas/booking.py](backend/app/schemas/booking.py)
`BookingCreate/Update/Response`, `BookingSettingsUpdate/Response`. `BookingSettingsResponse` includes `manager_name: str | None` field populated by the API endpoint.

### [backend/app/schemas/settings.py](backend/app/schemas/settings.py)
`SystemSettingsResponse`, `SystemSettingsUpdate(settings: dict)`.

### [backend/app/schemas/analytics.py](backend/app/schemas/analytics.py)
`DashboardResponse`, `LeadsByDay`, `LeadStatsResponse`, `FunnelStage`, `FunnelResponse`.

### [backend/app/ai/base_client.py](backend/app/ai/base_client.py)
`BaseLLMClient` -- abstract base class for all LLM providers. Defines `send_message()` and `close()` interface. `MessageResponse` dataclass with `.text`, `.tool_calls`, `.has_tool_use` properties (shared by all providers).

### [backend/app/ai/llm_client.py](backend/app/ai/llm_client.py)
`AnthropicClient(BaseLLMClient)` -- wrapper around `anthropic.AsyncAnthropic`. `send_message(messages, system, tools, tool_choice)` with tenacity retry (3 attempts, exponential backoff on RateLimitError/InternalServerError/APIConnectionError). Returns `MessageResponse`. `LLMClient` alias for backward compatibility.

### [backend/app/ai/openai_client.py](backend/app/ai/openai_client.py)
`OpenAIClient(BaseLLMClient)` -- wrapper around `openai.AsyncOpenAI`. Converts Anthropic-style messages/tools to OpenAI format via `format_converter`. Tenacity retry on OpenAI error types. Returns normalized `MessageResponse`.

### [backend/app/ai/openrouter_client.py](backend/app/ai/openrouter_client.py)
`OpenRouterClient(OpenAIClient)` -- extends OpenAIClient with `base_url="https://openrouter.ai/api/v1"` and optional HTTP-Referer/X-Title headers.

### [backend/app/ai/format_converter.py](backend/app/ai/format_converter.py)
Stateless format converters: `anthropic_tools_to_openai()`, `anthropic_messages_to_openai()` (handles system prompt, tool_result blocks, tool_use blocks, is_error flag), `openai_response_to_message_response()` (normalizes stop_reason, tool_calls, usage).

### [backend/app/ai/client_factory.py](backend/app/ai/client_factory.py)
`create_llm_client(db, owner_id=None)` -- async factory reading `llm_provider`, `ai_model`, and API keys exclusively from DB (system_settings). API-ключи LLM не берутся из env — только из БД, пользователи задают их через админ-панель. Supports per-manager settings via owner_id: per-owner DB → global DB (owner_id IS NULL). `get_setting_value(db, key, default, owner_id)` -- per-owner with global fallback. Returns `BaseLLMClient` instance (AnthropicClient, OpenAIClient, or OpenRouterClient).

### [backend/app/ai/embeddings.py](backend/app/ai/embeddings.py)
`EmbeddingsManager` -- sentence-transformers model loader. Default model: `paraphrase-multilingual-MiniLM-L12-v2` (384d). Lazy loading + singleton caching. `embed_text(str)` and `embed_batch(list[str])` run via `asyncio.to_thread` to avoid blocking the event loop.

### [backend/app/ai/rag.py](backend/app/ai/rag.py)
`RAGPipeline` -- Qdrant-based retrieval with per-owner and per-script filtering. `search_faq(query, limit, owner_id, script_id)`, `search_objections(query, limit, owner_id, script_id)`, `get_relevant_context(query, owner_id=None, script_id=None)`. Uses `AsyncQdrantClient.search()` with cosine similarity, score threshold 0.7. `_build_search_filter(owner_id, script_id)` -- builds Qdrant Filter: `must` for owner_id, `should` for script_id (matching specific script OR empty string for global entries). Returns `FAQResult`, `ObjectionResult`, `RAGContext` dataclasses.

### [backend/app/ai/qdrant_init.py](backend/app/ai/qdrant_init.py)
`ensure_collections()` -- idempotent creation of `faq_knowledge` and `objections_knowledge` Qdrant collections (384d, cosine). Called in FastAPI lifespan. `sync_faq_to_qdrant(db, qdrant, embeddings)` and `sync_objections_to_qdrant(db, qdrant, embeddings)` -- bulk upsert from PostgreSQL to Qdrant, includes `owner_id` and `script_id` (from `qualification_script_id`) in each point's payload. `sync_all()` -- combines both.

### [backend/app/ai/qualification.py](backend/app/ai/qualification.py)
`QualificationStage` enum (9 stages: INITIAL through HANDED_OFF). `STAGE_LABELS: dict[str, str]` -- Russian labels for all 9 stages. `compute_score_breakdown(qualification_data, score_config)` -- pure function returning per-stage breakdown (stage_id, stage_label, weight, completed, collected_info); uses `_score_history` from qualification_data for collected_info lookup. `QualificationStateMachine` -- manages stage transitions. Constructor accepts optional `score_config: dict[str, int] | None` for custom stage weights. Methods: `get_current_prompt()`, `get_expected_info()`, `can_advance()`, `advance(collected_data)`, `calculate_interest_score()` (0-100; uses `score_config` if provided, otherwise falls back to default `STAGE_WEIGHTS` of 25 pts per qualifying stage). `TRANSITIONS` dict validates state changes.

### [backend/app/ai/prompts.py](backend/app/ai/prompts.py)
All prompt templates in Russian. `SYSTEM_PROMPT` (role + rules including advance_qualification usage rule, includes `{current_datetime}` placeholder as first line), `QUALIFICATION_STAGE_PROMPTS` (per-stage instructions; needs_discovery/budget_check/timeline_check/decision_maker stages include advance_qualification reminders), `RAG_CONTEXT_TEMPLATE`, `GREETING_TEMPLATE`, `HANDOFF_PROMPT`. Helper functions: `build_lead_info()`, `build_stage_instructions()`, `build_rag_context()`, `build_greeting()`.

### [backend/app/ai/tools.py](backend/app/ai/tools.py)
`TOOLS_LIST` -- 4 tool definitions in Anthropic format: `book_appointment` (creates Booking), `transfer_to_manager` (changes conversation status to handed_off), `update_lead_info` (updates lead fields), `advance_qualification` (advances qualification stage via QualificationStateMachine.advance(), tracks score history in `_score_history` within qualification_data, returns new stage and interest score). `ToolHandler` class routes calls to handlers. `_advance_qualification()` captures current_stage and score_before before advance, computes delta, appends `{stage, score_added, total_score, info}` to `_score_history`. `ToolResult` dataclass. `ToolContext` dataclass (db_session, lead_id, conversation_id, qualification_sm).

### [backend/app/ai/context_builder.py](backend/app/ai/context_builder.py)
`ContextBuilder` -- assembles `LLMContext` (with `owner_id`) for each conversation turn. `build_context(conversation_id, new_message)`: loads conversation + lead from DB, determines `owner_id` via `_get_channel_owner_id(channel_id)`, loads message history (per-owner setting), loads qualification script via `_load_script_for_channel(channel_id)`, gets RAG context from Qdrant (filtered by owner_id and script_id), builds QualificationStateMachine (with score_config from script), assembles system prompt, detects manager messages, formats messages for Anthropic API. `_get_channel_owner_id(channel_id)` -- returns channel.owner_id. `_get_history_limit(owner_id)` -- per-owner with global fallback. `_load_script_for_channel(channel_id)`: loads Channel, if `qualification_script_id` is set loads that script, otherwise falls back to `_load_active_script()`. `LLMContext` dataclass includes `owner_id` field. Module-level: `MONTHS_RU` / `WEEKDAYS_RU` dicts, `format_datetime_ru()`.

### [backend/app/ai/engine.py](backend/app/ai/engine.py)
`ConversationEngine` -- main orchestrator with per-owner LLM client support. Constructor accepts optional `db_session` for dynamic LLM client creation. `_get_llm_client(owner_id)` -- creates per-owner LLM client via `create_llm_client(db, owner_id)` when db_session is available, falls back to pre-built client. `process_message(conversation_id, user_message)` pipeline: save user msg, build context (determines owner_id), create per-owner LLM client, LLM call with tool_use loop (max 5 iterations), update qualification, save response, return `EngineResponse`. `start_conversation(lead_id, channel_id)` -- creates conversation with greeting. `EngineResponse` dataclass (text, actions, qualification_stage, interest_score).

### [backend/app/channels/base.py](backend/app/channels/base.py)
`AbstractChannelAdapter` -- ABC with 3 abstract methods: `send_message(external_id, text, **kwargs)`, `process_incoming(raw_data) -> IncomingMessage`, `send_booking_prompt(external_id, available_slots)`. `IncomingMessage` dataclass with external_id, text, channel_type, metadata, timestamp.

### [backend/app/channels/telegram.py](backend/app/channels/telegram.py)
`TelegramAdapter(AbstractChannelAdapter)` -- sends messages via Telegram Bot HTTP API (httpx). `send_message(external_id, text, parse_mode=HTML, reply_markup)`, `process_incoming(raw_data)` parses Telegram Update dict into IncomingMessage, `send_booking_prompt(external_id, slots)` sends inline keyboard with time slots. `_api_request(method, payload)` -- internal POST to `api.telegram.org/bot{token}/{method}`.

### [backend/app/channels/web_widget.py](backend/app/channels/web_widget.py)
`WebWidgetAdapter(AbstractChannelAdapter)` -- implements all abstract methods using ConnectionManager for WebSocket delivery. Extra method: `send_typing(external_id)`. Formats messages as JSON: `{type, text, data, timestamp}`. Logs undelivered messages for offline sessions.

### [backend/app/schemas/messages.py](backend/app/schemas/messages.py)
Pydantic schemas for channel messages. `IncomingMessageSchema` (external_id, text, channel_type, metadata, timestamp). `OutgoingMessageSchema` (text, message_type, data, qualification_stage, interest_score).

### [backend/app/api/ws_manager.py](backend/app/api/ws_manager.py)
`ConnectionManager` -- singleton managing active WebSocket connections. Methods: `connect(session_id, websocket)` (accepts + replaces old connection), `disconnect(session_id)`, `send_message(session_id, data)` (JSON, auto-removes broken connections), `send_typing(session_id)`, `is_connected(session_id)`. `manager` -- module-level singleton instance.

### [backend/app/api/widget.py](backend/app/api/widget.py)
Widget API endpoints registered at `/api/v1/widget`. WebSocket endpoint: `GET /ws?channel_id=UUID&session_id=UUID` -- real-time message processing via ConversationEngine. REST fallback: `POST /init` (creates lead + conversation, returns session_id + greeting), `POST /messages` (send message, get AI response), `GET /history/{session_id}` (conversation history). Helper `_build_engine(db)` assembles ConversationEngine with db_session for per-owner LLM client creation.

### [backend/app/api/webhooks.py](backend/app/api/webhooks.py)
Webhook endpoints for Telegram. `POST /webhooks/telegram/{channel_id}/update` -- receives raw Telegram Update JSON directly from Telegram API, validates `X-Telegram-Bot-Api-Secret-Token` header, delegates processing to `TelegramUpdateHandler.handle_update()`. Legacy endpoints: `POST /webhooks/telegram/{channel_id}/init`, `POST /webhooks/telegram/{channel_id}` (for backward compat) -- use `build_engine()` from `telegram_update_handler`. `GET /webhooks/telegram/conversations/{conversation_id}/status` -- returns conversation status. Helper: `_get_active_channel(db, channel_id)` -- validates channel existence and type.

### [telegram-bot/bot/config.py](telegram-bot/bot/config.py)
`BotSettings(BaseSettings)` with fields: TELEGRAM_BOT_TOKEN, WEBHOOK_URL, WEBHOOK_SECRET, BACKEND_API_URL (default http://api:8000), TELEGRAM_CHANNEL_ID, LOG_LEVEL. `get_bot_settings()` with @lru_cache.

### [telegram-bot/bot/api_client.py](telegram-bot/bot/api_client.py)
`BackendAPIClient` -- httpx.AsyncClient wrapper for backend API. `init_conversation(channel_id, external_id, name)` POST to /init endpoint. `send_message(channel_id, external_id, text)` POST to webhook endpoint. `get_conversation_status(conversation_id)` GET. Retry logic: 3 attempts on network errors (ConnectError, ReadTimeout, WriteTimeout). Timeout: 30s.

### [telegram-bot/bot/main.py](telegram-bot/bot/main.py)
Entry point. `main()` builds Application via ApplicationBuilder with token and webhook config (port 8443, /webhook path, secret_token). Registers handlers: CommandHandler(/start), CallbackQueryHandler(book: pattern), MessageHandler(TEXT), MessageHandler(non-TEXT fallback). `post_init` creates BackendAPIClient in bot_data. `post_shutdown` closes httpx client.

### [telegram-bot/bot/handlers/start.py](telegram-bot/bot/handlers/start.py)
`start_handler(update, context)` -- calls api_client.init_conversation(), stores conversation_id in context.user_data, sends greeting.

### [telegram-bot/bot/handlers/conversation.py](telegram-bot/bot/handlers/conversation.py)
`message_handler(update, context)` -- sends user text to api_client.send_message(), relays AI response, handles actions (booking inline keyboard, transfer notification). `booking_callback_handler(update, context)` -- handles inline keyboard button presses (book:{date}:{time}), sends booking selection to AI. `_build_booking_keyboard(slots)` -- creates InlineKeyboardMarkup.

### [telegram-bot/bot/handlers/fallback.py](telegram-bot/bot/handlers/fallback.py)
`fallback_handler(update, context)` -- responds to non-text messages with a polite explanation.

### [admin/src/App.tsx](admin/src/App.tsx)
Root component. BrowserRouter with Routes: / (LandingOrDashboard — shows LandingPage for guests, redirects to /dashboard for authenticated users), /landing (redirect to /), /login (LoginPage), /register (RegisterPage, lazy), protected routes (ProtectedRoute -> MainLayout -> child routes: dashboard, leads, conversations, conversations/:id, scripts, channels, bookings, settings, users, managers, onboarding). `LandingOrDashboard` component checks `useAuthStore.isAuthenticated`. ConfigProvider with ruRU locale and blue theme (dark/light via useThemeStore). QueryClientProvider wrapping everything. Catch-all `*` redirects to `/`.

### [admin/src/api/client.ts](admin/src/api/client.ts)
Axios instance (baseURL: /api/v1, timeout: 30s). Request interceptor adds Bearer token from localStorage and X-Impersonate-Manager-Id header when impersonation is active (via useImpersonationStore.getState()). Response interceptor handles 401 (refresh token flow with queue for concurrent requests), 403 (notification), 500 (notification). On refresh failure, clears tokens and redirects to /login.

### [admin/src/api/index.ts](admin/src/api/index.ts)
Typed API functions grouped by domain: authAPI (login, refresh, register), leadsAPI (getLeads, getLead, updateLead, deleteLead), conversationsAPI (getConversations, getConversation, updateStatus, deleteConversation), scriptsAPI (CRUD for qualification/FAQ/objections + syncFAQ/syncObjections + parseFAQ(text, qualificationScriptId?)/parseObjections(text, qualificationScriptId?) for bulk text import with optional script binding + generateScript for LLM-generated qualification scripts + updateScoreConfig(scriptId, scoreConfig) for saving stage weights), channelsAPI (CRUD + testChannel), bookingsAPI (CRUD + getSettings/updateSettings), settingsAPI (getSettings, updateSettings), usersAPI (CRUD), managersAPI (getAll, getStats), analyticsAPI (getDashboard with period param, getLeadStats, getConversionFunnel, exportCSV as blob).

### [admin/src/store/authStore.ts](admin/src/store/authStore.ts)
Zustand store with persist middleware. State: token, refreshToken, user (AdminUser), isAuthenticated. Actions: login (calls API, stores tokens in localStorage and state), logout (clears everything), refreshAccessToken, setUser.

### [admin/src/store/themeStore.ts](admin/src/store/themeStore.ts)
Zustand store with persist middleware (localStorage key: `theme-storage`). State: isDark (boolean, default false). Action: toggleTheme(). Used in App.tsx to switch ConfigProvider algorithm (darkAlgorithm/defaultAlgorithm) and in MainLayout for theme toggle button.

### [admin/src/store/impersonationStore.ts](admin/src/store/impersonationStore.ts)
Zustand store with persist middleware (sessionStorage key: `impersonation-storage`). State: impersonatedManagerId (string|null), impersonatedManagerName (string|null), isImpersonating (boolean). Actions: startImpersonation(id, name) sets id/name/true, stopImpersonation() resets all to null/false. Used by axios interceptor (X-Impersonate-Manager-Id header), ImpersonationBanner, and MainLayout (admin-only menu filtering).

### [admin/src/store/onboardingStore.ts](admin/src/store/onboardingStore.ts)
Zustand store with persist middleware (localStorage key: `onboarding-storage`). State: currentStep (number, 0-5), completedByUser (Record<string, boolean> keyed by userId). Actions: setStep(n), nextStep(), prevStep(), completeOnboarding(userId), isCompleted(userId), resetForUser(userId). Both `completedByUser` and `currentStep` are persisted. Used by OnboardingPage and MainLayout (auto-redirect logic).

### [admin/src/components/ImpersonationBanner.tsx](admin/src/components/ImpersonationBanner.tsx)
Ant Design Alert component (type=warning, banner mode). Renders only when isImpersonating is true. Shows manager name and "Выйти из режима просмотра" button. Exit action calls stopImpersonation() and navigates to /managers.

### [admin/src/components/MainLayout.tsx](admin/src/components/MainLayout.tsx)
Ant Design Layout with fixed Sider (10 menu items with icons, adminOnly and managerOnly flags, collapsible, responsive breakpoint), ImpersonationBanner above Header, Header (collapse toggle + theme toggle sun/moon button + user dropdown with role display and logout), Content (Outlet for nested routes). Menu items filtered by role and impersonation state: admin-only items (Users, Managers) hidden for managers and during admin impersonation; "Обучение" item (managerOnly) visible only for managers. Auto-redirects new managers from /dashboard to /onboarding if onboarding not completed. Dark theme support via useThemeStore and theme tokens.

### [admin/src/components/landing/AnimatedSection.tsx](admin/src/components/landing/AnimatedSection.tsx)
Reusable framer-motion animation wrapper. Props: children, delay (default 0), className, style. Uses `motion.div` with `initial={{ opacity: 0, y: 50 }}`, `whileInView={{ opacity: 1, y: 0 }}`, `transition={{ duration: 0.6, delay }}`, `viewport={{ once: true }}`. Used in LandingPage for scroll-triggered fade-in-up animations with stagger effect via delay prop.

### [admin/src/pages/LandingPage.tsx](admin/src/pages/LandingPage.tsx)
SEO-optimized public landing page (route `/`) with 8 sections and semantic HTML (`<main>`, `aria-label`, proper heading hierarchy). Hero: animated badge, keyword-rich H1 "AI-менеджер квалифицирует лидов на автопилоте", trust text "Бесплатно. Без карты.", chat mockup. Stats: 4 key metrics (24/7, <5 min, 100%, 3+ LLM). Testimonials: 3 blockquote cards with names/roles/companies. Features: 6 cards (AI-qualification, Telegram bots, Scripts/FAQ, Analytics, Bookings, Integrations) in bento grid. How it works: 4 steps with numbered badges. Lead Preview: interactive card mockup with score bar and qualification stages. FAQ: 6 items in CSS accordion (matches JSON-LD FAQPage schema in index.html). CTA: with trust line. Footer: semantic nav with `<a href>` links for SEO crawling.

### [admin/src/pages/OnboardingPage.tsx](admin/src/pages/OnboardingPage.tsx)
Manager onboarding page with 6 interactive steps. Layout: vertical Steps sidebar (Col md=7) + content Card (Col md=17). Steps: 0-Welcome (system overview), 1-Qualification Script (stages, weights, AI generation), 2-Knowledge Base (FAQ, objections, import), 3-Channel (Telegram/Web Widget setup), 4-AI Settings (LLM provider, API key, greeting), 5-Done (summary + redirect to dashboard). Each step has large icon (colorPrimary), title, description, "Как это работает" Card (colorFillAlter), and action button navigating to relevant page. Footer: "Пропустить обучение" / "Назад" / "Далее" / "Завершить". On complete/skip: marks onboarding as completed in onboardingStore and navigates to /dashboard. Uses theme tokens for dark mode support.

### [admin/src/pages/DashboardPage.tsx](admin/src/pages/DashboardPage.tsx)
Period filter (7d/30d/90d Radio.Group) and CSV export button in header. 6+ Statistic cards (total/today/week/month leads, active conversations, qualification rate, bookings, avg score). 4 Recharts with Legend: LineChart (leads per day), BarChart (by status), PieChart (by channel), horizontal BarChart (funnel). Recent leads table (10 rows) and conversations table (5 rows). Auto-refresh 60s. CSV download via blob URL.

### [admin/src/pages/LeadsPage.tsx](admin/src/pages/LeadsPage.tsx)
Filters: status Select, DatePicker RangePicker, Input.Search. Ant Design Table with server-side pagination (status Tag, qualification_stage_label column with responsive:['md'], interest_score Progress bar, date formatted). Click row opens Drawer that fetches fresh lead data via useQuery (GET /leads/{id}) with Spin loading overlay. Drawer shows: Descriptions (ID, name, email, phone, company, status Tag, Progress bar, qualification_stage_label, qualification_script_name, source, channel info, created_at), vertical Steps component for qualification progress (finish/process/wait states with weight% and collected_info), score breakdown Table (stage_label, weight%, CheckCircle/MinusCircle status, collected_info), Timeline for _score_history (stage label, score delta, cumulative score, info). stageLabels constant maps stage_id to Russian labels. Delete with Popconfirm. "Диалоги" button navigates to ConversationsPage with lead_id filter.

### [admin/src/pages/ConversationsPage.tsx](admin/src/pages/ConversationsPage.tsx)
Filters: status Select, DatePicker RangePicker, lead_id from URL search params (useSearchParams). Table with pagination. Closable Tag shows active lead_id filter (truncated UUID). Delete button with Popconfirm (stopPropagation to avoid row click navigation). Click row navigates to /conversations/:id.

### [admin/src/pages/ConversationDetailPage.tsx](admin/src/pages/ConversationDetailPage.tsx)
Chat view with message bubbles: user messages (blue, right-aligned), assistant (grey, left-aligned), manager messages (light blue with border, left-aligned, label "Менеджер (имя)"), system (gold tag, centered). Manager messages distinguished by `metadata_.sender === 'manager'`. Each bubble shows role label and timestamp. Sidebar Card with lead/channel/status/manager info. Action buttons: active -> Pause/Handoff/Complete; paused -> Resume; handed_off -> "Вернуть боту"/Complete. Message input (TextArea + Send button) visible when status=handed_off; Enter sends, Shift+Enter newline. Auto-refresh 3s for active and handed_off conversations. Auto-scroll to latest message.

### [admin/src/pages/ScriptsPage.tsx](admin/src/pages/ScriptsPage.tsx)
3 Ant Design Tabs. Qualification: Collapse panels showing stages + "Оценка интереса" section (InputNumber per stage with weight %, "Сохранить веса" button calling updateScoreConfig via scriptsAPI.updateScoreConfig). Create/edit Modal with Segmented toggle (visual/JSON mode). Visual mode: Form.List with Card per stage (stage_id Select, question_prompt TextArea, expected_info Input, follow_ups comma-separated Input, next_stage Select), up/down/delete buttons per card, "Добавить этап" dashed button, dynamic score_config section (InputNumber per stage). JSON mode: TextArea with monospace font. Bidirectional data sync on mode switch. Submit includes score_config. "Сгенерировать через AI" button opens Modal. FAQ: Table with filter Select by qualification script (filterScriptId state, script_id in query params), CRUD Modal with qualification_script_id Select, Sync to Qdrant button, "Импорт текстом" Modal with script Select + TextArea (parseFAQ with qualificationScriptId). Objections: analogous to FAQ -- filter Select, qualification_script_id in create/edit form, script Select in import modal (parseObjections with qualificationScriptId).

### [admin/src/pages/ChannelsPage.tsx](admin/src/pages/ChannelsPage.tsx)
Card layout per channel (type icon, name, active Switch, create date). Mode Tag on Telegram cards: blue "Webhook" or orange "Long Polling" based on config.bot_mode. Purple Tag with qualification script name when assigned. Create/edit Modal with dynamic form: Telegram (bot_token, bot_mode selector with webhook/polling options), Web Widget (allowed_origins, theme_color picker), qualification script Select (allowClear, placeholder "Глобальный активный скрипт", loads scripts list via useQuery). Embed code copy button for web_widget channels. Test connection button. CRUD operations.

### [admin/src/pages/BookingsPage.tsx](admin/src/pages/BookingsPage.tsx)
2 Tabs. Bookings list: Table with status/date filters, confirm/cancel action buttons. Booking Settings: per-manager Card form with Checkbox.Group (weekdays), TimePicker.RangePicker (hours), slot duration Select, timezone Select, booking mode Select, booking link Input.

### [admin/src/pages/SettingsPage.tsx](admin/src/pages/SettingsPage.tsx)
Collapse sections: AI (provider Select, model Select, 3 API key Input.Password fields with active provider Badge, max messages InputNumber, timeout InputNumber), Greeting (TextArea + preview Card), Integrations (CRM webhook, Google Sheets credentials, notification webhook), Notifications (email, telegram chat ID, event Checkbox.Group). Save all / undo buttons with unsaved changes Badge indicator.

### [admin/src/pages/UsersPage.tsx](admin/src/pages/UsersPage.tsx)
Table with role Tag, active Tag, create date. Create/edit Modal (email, password, full_name, role Select). Admin-only access. Cannot delete current user. Password optional on edit.

### [admin/src/pages/ManagersPage.tsx](admin/src/pages/ManagersPage.tsx)
Admin-only page. Ant Design Table listing managers with columns: full_name, email, channels_count, leads_count, conversations_count, is_active status Tag (green/red). "Войти как менеджер" button per row calls startImpersonation from impersonationStore + navigates to /dashboard. Data loaded via managersAPI.getAll() with useEffect/useState. Loading and error states handled with Alert.

### [admin/src/pages/RegisterPage.tsx](admin/src/pages/RegisterPage.tsx)
Public registration page. Ant Design Form with fields: full_name, email, password, confirm_password (with cross-field validation). Submit calls authAPI.register(), saves tokens to localStorage and authStore, redirects to /dashboard. Handles 409 duplicate email error. Link to /login at bottom. Styled like LoginPage (centered Card with shadow).

### [admin/src/types/index.ts](admin/src/types/index.ts)
All TypeScript interfaces: AdminUser, ScoreBreakdownItem (stage_id, stage_label, weight, completed, collected_info), Lead (includes score_breakdown, qualification_script_name, qualification_stage_label), LeadStatus, Conversation, ConversationStatus, ConversationDetail, Message, MessageRole, Channel (includes qualification_script_id, qualification_script_name), ChannelType, QualificationScript (includes score_config: Record<string, number> | null), FAQItem (includes qualification_script_id: string | null), ObjectionScript (includes qualification_script_id: string | null), Booking, BookingStatus, BookingMode, BookingSettings, SystemSetting, PaginatedResponse<T>, TokenResponse, DashboardData, LeadStats, LeadsByDay, FunnelStage, FunnelData, ManagerWithStats, ManagerDetailStats, RegisterRequest.

### [widget/embed.js](widget/embed.js)
IIFE loader script for embedding widget on external sites. Reads `data-channel-id` from `<script>` tag. Creates fixed-position iframe (bottom-right, 400x600px, z-index 999999). Handles postMessage commands: `widget:resize`, `widget:close`, `widget:open`, `widget:minimize`, `widget:maximize`.

### [widget/src/api.ts](widget/src/api.ts)
`ChatAPI` class -- WebSocket client with REST fallback. Constructor takes channelId and apiUrl. WebSocket: `connect()`, `disconnect()`, `sendMessage(text)`. Reconnection: exponential backoff 1s-30s, max 10 attempts. REST fallback: `initSession()`, `sendMessageREST(text)`, `getHistory()`. Session ID persisted in localStorage. Callbacks: `onMessage`, `onTyping`, `onStatusChange`.

### [widget/src/Widget.tsx](widget/src/Widget.tsx)
Preact functional component. States: messages[], inputText, isOpen, isTyping, isConnected. UI: chat bubble button (SVG icon), expandable chat window with header (connection status dot, close button), scrollable message list (user bubbles right, assistant bubbles left), typing indicator (3 animated dots), text input + send button. Auto-scroll, focus on open, Enter key support, postMessage to parent iframe.

### [widget/src/main.tsx](widget/src/main.tsx)
Entry point. Reads `channel_id` and optional `api_url` from URL query params. Creates `ChatAPI` instance. Renders `Widget` component into `#widget-root`.

### [widget/vite.config.ts](widget/vite.config.ts)
Vite config with `@preact/preset-vite` plugin. Build target: es2015. Multi-entry: widget (index.html) + embed (embed.js). Output: named files, chunked, hashed assets.

### [widget/nginx.conf](widget/nginx.conf)
nginx config for widget serving on port 3001. Gzip compression, SPA fallback (try_files), static asset caching (30d), embed.js no-cache, CORS headers (Allow-Origin: *), X-Frame-Options: ALLOWALL for iframe embedding.

### [backend/app/middleware.py](backend/app/middleware.py)
`RequestLoggingMiddleware(BaseHTTPMiddleware)` -- assigns a unique `request_id` (UUID4) to every request, binds it to structlog contextvars so all logs within the request scope include it. Logs `request_started` and `request_completed` (or `request_failed`) with method, path, status_code, duration_ms. Adds `X-Request-ID` response header for client-side tracing.

### [backend/app/logging_config.py](backend/app/logging_config.py)
`setup_logging()` -- configures structlog and stdlib logging. Uses `ConsoleRenderer` in development (DEBUG + TTY) and `JSONRenderer` with callsite parameters (filename, func_name, lineno) in production. Integrates stdlib logging (uvicorn, sqlalchemy) via `ProcessorFormatter`. Quietens noisy loggers: `uvicorn.access` → WARNING, `sqlalchemy.engine` → DEBUG in debug mode / WARNING in production, `httpx/httpcore` → WARNING.

### [backend/app/rate_limit.py](backend/app/rate_limit.py)
`create_limiter()` -- builds `slowapi.Limiter` with Redis backend (`storage_uri=REDIS_URL`), default limit `100/minute` per IP, `headers_enabled=False`. `limiter` module-level singleton used via `@limiter.limit(...)` decorators. `rate_limit_exceeded_handler` -- custom 429 JSON response with `detail`, `retry_after`, `Retry-After` header, structured logging.

### [backend/tests/conftest.py](backend/tests/conftest.py)
Shared pytest fixtures for all tests. `test_engine` -- SQLite in-memory with `StaticPool` (single shared connection). `TestSessionLocal` -- `async_sessionmaker` for test DB. Fixtures: `db_session` (creates/drops tables per test), `channel_factory`, `lead_factory`, `conversation_factory`, `message_factory`, `admin_user_factory`. `app` fixture -- sets test env vars (`JWT_SECRET_KEY=test-secret-key`, `DATABASE_URL=sqlite+aiosqlite:///:memory:`, etc.), calls `get_settings.cache_clear()` and `limiter.reset()`, creates FastAPI test app with `get_db` dependency override. `client` fixture -- `httpx.AsyncClient` with `ASGITransport`.

### [backend/tests/test_api/test_leads.py](backend/tests/test_api/test_leads.py)
Integration tests for leads CRUD API (13 tests). `_make_token(user_id)` helper creates JWT signed with `test-secret-key`. Tests cover: list (unauthorized, empty, with leads, pagination, status filter), get (success, 404, unauthorized), update (name, status, 404), delete (success, 404). Classes: `TestLeadsListEndpoint`, `TestLeadsGetEndpoint`, `TestLeadsUpdateEndpoint`, `TestLeadsDeleteEndpoint`.

### [backend/tests/test_api/test_widget.py](backend/tests/test_api/test_widget.py)
Integration tests for widget API (7 tests). `TestWidgetHistory` (5 async tests) -- history endpoint with various scenarios (unknown session, messages present, completed conversation, field verification, empty conversation). `TestWidgetWebSocket` (2 sync tests using `starlette.testclient.TestClient`) -- WebSocket connect/disconnect with mocked engine, ignores non-message types. `_make_test_app()` helper creates isolated FastAPI app for sync WebSocket tests.
