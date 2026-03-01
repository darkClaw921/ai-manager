#!/bin/bash
set -e

# ── AI Lead Manager — Production ───────────────────────────────────────────
# Production-сервисы в Docker:
#   - Backend: gunicorn + 4 uvicorn workers
#   - Nginx reverse proxy (80/443)
#   - Celery worker + beat
#   - Resource limits, log rotation
#   - DEBUG=false, LOG_LEVEL=WARNING
#
# Команды:
#   ./prod.sh              — запустить все сервисы
#   ./prod.sh build        — пересобрать и запустить
#   ./prod.sh down         — остановить
#   ./prod.sh logs [svc]   — логи
#   ./prod.sh ps           — статус
#   ./prod.sh restart svc  — перезапустить сервис
#   ./prod.sh db-migrate   — Alembic миграции
#   ./prod.sh db-backup    — дамп PostgreSQL
#   ./prod.sh update       — обновить без даунтайма
# ────────────────────────────────────────────────────────────────────────────

cd "$(dirname "$0")"

DC="docker compose -f docker-compose.prod.yml"

if [ ! -f .env ]; then
    echo "ОШИБКА: .env не найден. Скопируйте .env.example и заполните production-значения."
    exit 1
fi

if grep -q "change-me-in-production" .env 2>/dev/null; then
    echo "ОШИБКА: JWT_SECRET_KEY содержит значение по умолчанию. Замените в .env."
    exit 1
fi

case "${1:-up}" in
    up)
        $DC up -d
        echo ""
        echo "Production запущен:"
        echo "  Nginx: http://localhost (80/443)"
        ;;
    build)
        $DC up -d --build
        ;;
    down)
        $DC down
        ;;
    logs)
        shift; $DC logs -f --tail=100 "$@"
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
    db-backup)
        BACKUP="backup_$(date +%Y%m%d_%H%M%S).sql"
        $DC exec postgres pg_dump -U "${POSTGRES_USER:-postgres}" "${POSTGRES_DB:-ai_manager}" > "$BACKUP"
        echo "Дамп сохранён: $BACKUP"
        ;;
    update)
        echo "1/3 Сборка образов..."
        $DC build
        echo "2/3 Миграции..."
        $DC up -d api
        $DC exec api alembic upgrade head
        echo "3/3 Перезапуск..."
        $DC up -d
        echo "Обновление завершено."
        ;;
    *)
        echo "Неизвестная команда: $1"
        echo "Команды: up, build, down, logs, ps, restart, db-migrate, db-backup, update"
        exit 1
        ;;
esac
