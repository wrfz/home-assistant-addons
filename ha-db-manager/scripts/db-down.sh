#!/usr/bin/env bash
# Removes the dev MySQL + PostgreSQL containers.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env.sh"

echo ">> removing $DEV_PG_CONTAINER and $DEV_MYSQL_CONTAINER"
docker rm -f "$DEV_PG_CONTAINER" "$DEV_MYSQL_CONTAINER" >/dev/null 2>&1 || true
echo ">> done"
