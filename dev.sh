#!/bin/bash
set -e

# ── AI Lead Manager — Development ──────────────────────────────────────────
# Все сервисы в Docker с hot-reload:
#   - Backend: uvicorn --reload + volume mounts
#   - Admin:   vite dev server + volume mounts
#   - Widget:  vite dev server + volume mounts
#   - Infra:   PostgreSQL, Qdrant, Redis
#
# Команды:
#   ./dev.sh              — запустить все сервисы
#   ./dev.sh build        — пересобрать образы и запустить
#   ./dev.sh down         — остановить все сервисы
#   ./dev.sh logs [svc]   — логи (все или конкретный сервис)
#   ./dev.sh ps           — статус сервисов
#   ./dev.sh restart svc  — перезапустить сервис
#   ./dev.sh db-migrate   — Alembic миграции
#   ./dev.sh db-seed      — seed данных
#   ./dev.sh shell        — bash в api контейнере
# ────────────────────────────────────────────────────────────────────────────

cd "$(dirname "$0")"

# docker-compose.yml + docker-compose.override.yml (auto)
DC="docker compose"

if [ ! -f .env ]; then
    echo "Файл .env не найден. Копирую из .env.example..."
    cp .env.example .env
    echo "Отредактируйте .env и перезапустите."
    exit 1
fi

case "${1:-up}" in
    up)
        $DC up -d
        echo ""
        echo "Dev-окружение запущено:"
        echo "  API:     http://localhost:8000"
        echo "  Admin:   http://localhost:3000"
        echo "  Widget:  http://localhost:3001"
        echo "  PgSQL:   localhost:5432"
        echo "  Qdrant:  http://localhost:6333"
        echo "  Redis:   localhost:6379"
        ;;
    build)
        $DC up -d --build
        echo "Образы пересобраны, сервисы запущены."
        ;;
    down)
        $DC down
        ;;
    logs)
        shift; $DC logs -f "$@"
        ;;
    ps)
        $DC ps
        ;;
    restart)
        shift; $DC restart "$@"
        ;;
    db-migrate)
        $DC exec api alembic upgrade head
        ;;
    db-seed)
        $DC exec api python -m app.db.seed
        ;;
    shell)
        $DC exec api bash
        ;;
    *)
        echo "Неизвестная команда: $1"
        echo "Команды: up, build, down, logs, ps, restart, db-migrate, db-seed, shell"
        exit 1
        ;;
esac
