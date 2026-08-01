#!/usr/bin/env bash
# Starts local MySQL + PostgreSQL dev containers and applies the HA recorder
# schema + seed data. Idempotent: reuses already-running containers.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env.sh"
ADDON_DIR="$(dirname "$SCRIPT_DIR")"

start_if_needed() {
    local name="$1"
    shift
    if docker inspect "$name" >/dev/null 2>&1; then
        if [ "$(docker inspect -f '{{.State.Running}}' "$name")" = "true" ]; then
            echo ">> $name already running"
        else
            echo ">> starting $name"
            docker start "$name" >/dev/null
        fi
    else
        echo ">> creating $name"
        docker run -d --name "$name" "$@" >/dev/null
    fi
}

start_if_needed "$DEV_PG_CONTAINER" \
    -e POSTGRES_PASSWORD="$DEV_DB_PASSWORD" \
    -e POSTGRES_DB=hass \
    -p "$DEV_PG_PORT":5432 \
    postgres:16-alpine

start_if_needed "$DEV_MYSQL_CONTAINER" \
    -e MYSQL_ROOT_PASSWORD="$DEV_DB_PASSWORD" \
    -e MYSQL_DATABASE=hass \
    -p "$DEV_MYSQL_PORT":3306 \
    mysql:8

echo ">> waiting for databases to become ready..."
pg_ok=0
my_ok=0
for _ in $(seq 1 60); do
    docker exec "$DEV_PG_CONTAINER" pg_isready -U postgres >/dev/null 2>&1 && pg_ok=1
    docker exec "$DEV_MYSQL_CONTAINER" mysqladmin ping -h 127.0.0.1 -p"$DEV_DB_PASSWORD" >/dev/null 2>&1 && my_ok=1
    if [ "$pg_ok" -eq 1 ] && [ "$my_ok" -eq 1 ]; then
        break
    fi
    sleep 2
done

if [ "$pg_ok" -ne 1 ] || [ "$my_ok" -ne 1 ]; then
    echo "ERROR: databases did not become ready in time" >&2
    exit 1
fi

echo ">> applying schema + seed data"
docker exec -i "$DEV_MYSQL_CONTAINER" mysql -h 127.0.0.1 -u root -p"$DEV_DB_PASSWORD" hass \
    < "$ADDON_DIR/tests/schema.mysql.sql" 2>/dev/null
docker exec -i "$DEV_PG_CONTAINER" psql -U postgres -d hass -f - \
    < "$ADDON_DIR/tests/schema.postgres.sql" >/dev/null

echo ">> ready:"
echo "   postgres: postgresql://postgres:<pwd>@localhost:${DEV_PG_PORT}/hass"
echo "   mysql:    mysql://root:<pwd>@localhost:${DEV_MYSQL_PORT}/hass?charset=utf8mb4"
