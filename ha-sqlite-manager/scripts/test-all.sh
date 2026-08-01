#!/usr/bin/env bash
# Runs the full test suite:
#   - python compile check
#   - unit + endpoint tests (SQLite, no server needed)
#   - integration tests against real MySQL + PostgreSQL (containers are
#     auto-started if missing)
#
# Usage:
#   ./scripts/test-all.sh                # keeps containers running afterwards
#   ./scripts/test-all.sh --cleanup      # removes the containers afterwards
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env.sh"
ADDON_DIR="$(dirname "$SCRIPT_DIR")"

CLEANUP=0
if [ "${1:-}" = "--cleanup" ]; then
    CLEANUP=1
fi

cleanup() {
    "$SCRIPT_DIR/db-down.sh"
}
if [ "$CLEANUP" -eq 1 ]; then
    trap cleanup EXIT
fi

cd "$ADDON_DIR"

echo ">> ensuring python dependencies"
python3 -c 'import aiohttp, pymysql, psycopg, pytest, pytest_asyncio' 2>/dev/null \
    || pip install -q -r requirements-dev.txt

echo ">> ensuring dev databases"
"$SCRIPT_DIR/setup-db.sh"

echo ">> compile check"
python3 -m py_compile app.py db.py

echo ">> unit + endpoint tests"
python3 -m pytest -q

echo ">> integration tests (MySQL + PostgreSQL)"
python3 -m pytest tests/test_integration_db.py -v

echo ">> ALL TESTS PASSED"
