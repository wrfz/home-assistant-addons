# Changelog

## 0.38.0

- Support for MySQL and PostgreSQL recorder databases (in addition to SQLite).
  The database is auto-detected from Home Assistant's `recorder.db_url` in
  `configuration.yaml` (overridable via the `HA_DB_URL` env var).
- Added test suite (pytest + GitHub Actions CI with Postgres/MySQL services).
- Added dev scripts in `scripts/`: `setup-db.sh`, `test-all.sh [--cleanup]`,
  `db-down.sh`, `env.sh` — start containers, apply schema and run all tests
  without setting any env vars manually.
- Watch interval setting now persisted in `/data/settings.json`.

## 0.37.0

- Settings page: configurable live-update interval (stored server-side) and
  live client/view counters.

## 0.36.0

- Multi-client WebSocket synchronization (deduplicated server-side watches).
- `new` count column in usage views uses global `since` baseline.

## 0.35.0

- Human/raw timestamp toggle, locale-aware formatting.

## 0.34.0

- Sortable table columns, live reload via WebSocket.

## 0.33.0

- Top usage views for states, statistics and events.

## 0.1.0

- Initial release
- View all database tables
- Paginated table view
