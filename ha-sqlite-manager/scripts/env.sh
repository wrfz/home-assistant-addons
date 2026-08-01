#!/usr/bin/env bash
# Shared dev defaults for the test scripts.
# Override any value by exporting it before calling a script,
# e.g.:  DEV_DB_PASSWORD=foo ./scripts/setup-db.sh
export DEV_PG_CONTAINER="${DEV_PG_CONTAINER:-pg-test}"
export DEV_MYSQL_CONTAINER="${DEV_MYSQL_CONTAINER:-mysql-test}"
export DEV_DB_PASSWORD="${DEV_DB_PASSWORD:-secret}"
export DEV_PG_PORT="${DEV_PG_PORT:-5433}"
export DEV_MYSQL_PORT="${DEV_MYSQL_PORT:-3307}"
export HA_TEST_MYSQL_URL="mysql://root:${DEV_DB_PASSWORD}@localhost:${DEV_MYSQL_PORT}/hass?charset=utf8mb4"
export HA_TEST_PG_URL="postgresql://postgres:${DEV_DB_PASSWORD}@localhost:${DEV_PG_PORT}/hass"
