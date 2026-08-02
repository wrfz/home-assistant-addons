#!/usr/bin/env bash
# Run the addon locally against a SQLite DB (e.g. scripts/demo.db).
#
# Usage:
#   ./scripts/run-local.sh                 # uses scripts/demo.db (created on demand)
#   HA_DB_URL=sqlite:///path/to/db.db ./scripts/run-local.sh
#
# The web UI is served at http://localhost:8099
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ADDON_DIR="$(dirname "$SCRIPT_DIR")"

export HA_STATIC_DIR="${HA_STATIC_DIR:-$ADDON_DIR/static}"
export HA_CONFIG_YAML="${HA_CONFIG_YAML:-$ADDON_DIR/config.yaml}"
export HA_SQLITE_SETTINGS_FILE="${HA_SQLITE_SETTINGS_FILE:-$ADDON_DIR/scripts/settings.json}"

if [ -z "${HA_DB_URL:-}" ]; then
    DEMO_DB="${DEMO_DB:-$ADDON_DIR/scripts/demo.db}"
    if [ ! -f "$DEMO_DB" ]; then
        echo ">> demo DB not found, creating $DEMO_DB"
        python3 "$SCRIPT_DIR/make-demo-db.py" "$DEMO_DB"
    fi
    export HA_DB_URL="sqlite:///$DEMO_DB"
fi

echo ">> DB: $HA_DB_URL"
exec python3 "$ADDON_DIR/app.py"
