# Home Assistant DB Manager

View, browse and manage the Home Assistant database directly from the web UI:
a single-page app that shows all database tables with pagination, sorting,
filtering, live updates and usage statistics.

Works with **SQLite**, **MySQL** and **PostgreSQL**.

![Add-on category](https://img.shields.io/badge/category-database-informational)
![Version](https://img.shields.io/badge/version-2026.8.3-blue)
![Python](https://img.shields.io/badge/python-3.14-blue)

## Features

- **Full database access**: browse every table of the Home Assistant recorder
  database (`states`, `statistics`, `events`, ... and all meta tables).
- **Paginated table view** with column sorting and server-side filtering.
- **Usage views** ("Top Usage"): `states_meta`, `statistics_meta` and
  `event_types` with per-entity row counts and a **"new" counter** that shows
  how many rows arrived since your last visit.
- **Incremental count views**: count columns are served from in-memory
  counters that are prewarmed at startup, so navigation stays fast even on
  databases with millions of rows (deltas are fetched via a rowid range scan
  and aggregated in Python).
- **Live updates**: tables refresh automatically over a WebSocket connection,
  synchronized across multiple clients (configurable interval, default 3 s).
- **Clean New**: resets the "new" baselines of all count views.
- **Hide columns** individually or hide all empty columns; hidden columns are
  excluded from the SQL queries, so hiding columns actually speeds up large
  tables.
- **Column info tooltips**: every column header shows a description of the
  column, including computed (virtual) columns.
- **Theme-aware**: follows the Home Assistant theme; human-readable dates,
  sizes and colors for virtual columns.
- **Performance diagnostics**: every request logs per-phase timings and every
  SQL query logs its duration (with a `debug` log level for details).

## Installation

1. Add this repository to Home Assistant:
   `Settings → Add-ons → Add-on Store → ⋮ → Repositories`
   → add `https://github.com/wrfz/home-assistant-addons`.
2. Find **Home Assistant DB Manager** in the store and install it.
3. Configure the `log_level` option if desired (`info` / `debug`).
4. Start the add-on and open the web UI.

The add-on auto-detects the recorder database:

1. The `HA_DB_URL` environment variable (see below), else
2. the `recorder.db_url` from your `configuration.yaml`, else
3. the default SQLite file at `/config/home-assistant_v2.db`.

### Using an external database

To point the add-on at a MySQL or PostgreSQL recorder database, set
`recorder.db_url` in your Home Assistant `configuration.yaml`; the add-on
picks it up automatically:

```yaml
recorder:
  db_url: mysql://user:password@host:3306/homeassistant
```

Alternatively, set the `HA_DB_URL` environment variable (this is also how the
add-on is run in development). Supported schemes: `sqlite:///...`,
`mysql://...` / `mariadb://...` / `mysql+pymysql://...`,
`postgresql://...` / `postgres://...` / `postgresql+psycopg://...`.

## Configuration

The add-on configuration is minimal:

| Option      | Values       | Description                                   |
| ----------- | ------------ | --------------------------------------------- |
| `log_level` | `info`, `debug` | `debug` logs every SQL query with its duration. |

Persistent settings (live-update interval, hidden columns) are stored per
instance and editable in the web UI.

## Usage

- **Table list**: all tables with estimated row counts; click one to open it.
- **Filters**: click a value in a count column to see only the rows belonging
  to that entity/event type.
- **New column**: shows rows added since the baseline; use **Clean New** to
  reset the baseline.
- **Sorting**: click a column header; click again to toggle direction.

## Development

Run the app locally against a SQLite demo database:

```bash
./scripts/run-local.sh          # uses scripts/demo.db (created on demand)
```

Or against an existing database:

```bash
HA_DB_URL=sqlite:///path/to/db.db ./scripts/run-local.sh
```

The web UI is served at <http://localhost:8099>.

### Tests

```bash
python3 -m pytest
```

For the MySQL/PostgreSQL integration tests, start the containers first:

```bash
./scripts/setup-db.sh   # starts pg-test and mysql-test containers
```

## License

Apache-2.0
