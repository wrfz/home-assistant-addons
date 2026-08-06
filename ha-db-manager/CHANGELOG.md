# Changelog

All notable changes to the Home Assistant DB Manager add-on.

## 2026.8.3

- **Count views much faster**: count columns (states, statistics, events) use
  incremental in-memory counters that are prewarmed at startup, so page
  navigation only reads the rows that changed since the last visit.
- Snapshot queries use separate `MAX`/`MIN` statements (milliseconds instead of
  a full table scan) and deltas are aggregated in Python from a plain rowid
  range fetch, avoiding slow `GROUP BY` index scans.
- Purged rows are detected immediately: when the minimum row id moves up, the
  counter is rebuilt and the baseline is reset.

## 2026.8.2

- **Column info**: every column header now shows an "i" tooltip with a
  description of the column, including the computed (virtual) columns.
- **Frontend rewritten on lit-html**: the table view renders via diffing,
  which makes live updates and page flips faster, renders values XSS-safe
  and uses real event handlers instead of inline `onclick` strings.
- **Binary values** (BLOBs) are displayed as human-readable sizes.
- **Hidden columns are now excluded from the SQL queries**, not just hidden in
  the UI, so hiding columns actually speeds up large tables.
- **Empty-column detection fixed**: a column is only reported as "empty" when
  it really has no usable value (NULL or empty).
- **Performance diagnostics**: every request logs per-phase timings and every
  SQL query logs its duration.
- New **`log_level` configuration option** (`info` / `debug`).

## 2026.8.1

- **Version scheme switched to YYYY.M.P** (calendar-based versioning).

## 0.44.0

- **Hide individual columns** via the "x" in the table header.

## 0.43.0

- **Page support for top-usage views** (states, statistics, events).
- **Sorting for the "new" column** in top-usage views.
- Top-usage views and the full table list **merged into one navigation**.
- Fixed invisible "new" column when a page is opened.
- Meta table moved to the top of the list; meta tables reordered.
- **Sort flickering fixed.**
- **Filtered views show the readable value in the title** (e.g. "States of
  sensor.xyz") instead of a raw ID.
- Wrong filtering after pressing "Back" fixed.
- "Max" column removed.
- **Virtual columns colorized** (e.g. `state_count`, `event_count`, `new`).
- **Live mode is the default**; column order changed.
- Unnecessary links in meta tables removed.
- **"New" counters for states, statistics and events computed in the
  backend**, with "Clean New" to reset the baseline.
- Scripts to run the app locally without Home Assistant.

## 0.42.0

- Fixed CSS/JS URLs after the template split.

## 0.41.0

- Internal release (version bump only).

## 0.40.0

- Internal refactor: table view code shared between states, statistics and
  events; `index.html` split into separate templates.

## 0.39.0

- New **statistics short-term** view.
- Add-on folder renamed to `ha-db-manager`.
- Bump to Python 3.14.

## 0.38.0

- Support for **MySQL and PostgreSQL** recorder databases (in addition to
  SQLite), auto-detected from Home Assistant's `recorder.db_url`
  (overridable via `HA_DB_URL`).

## 0.37.0

- Configurable **live-update interval**; number of registered listeners is
  shown.

## 0.36.0

- **Live updates synchronized across multiple clients** (deduplicated
  server-side watches).

## 0.35.0

- "New values" column fixed.

## 0.34.0

- Debug panel made resizable.

## 0.33.0

- Logging for the "new entries" column.

## 0.32.0

- **Count updates shown** in top-usage tables.

## 0.31.0

- Slider jump fixed when live update is on.

## 0.30.0

- **Live update**: tables refresh automatically over a WebSocket connection.

## 0.29.0

- **Refresh button** for manual reload.

## 0.28.0

- **Column sorting for all tables.**
- Changed display format for year values.

## 0.27.0

- **Settings page** added.

## 0.26.0

- **Human-readable date/time values** in tables.

## 0.25.0

- Frontend for the Statistics and Events usage views.

## 0.24.0

- **Top Usage views for Statistics and Events.**

## 0.23.0

- Debug panel toggled by clicking.

## 0.22.0

- Version added to the `index.html` URL to force the browser to reload the
  site after updates.

## 0.21.0

- More server logging.

## 0.20.0

- Browser caching disabled.

## 0.19.0

- **Debug panel** added.

## 0.18.0

- Server logging added.

## 0.17.0

- Theme is only updated while the Home Assistant DevTools tab is open (fix).

## 0.16.0

- Theme update.

## 0.15.0

- Configurable **theme update interval**.

## 0.14.0

- **Theme usage**: the add-on follows the Home Assistant theme.

## 0.13.0

- Page index fix.

## 0.12.0

- Invalid page index fix.

## 0.11.0

- Internal release (version bump only).

## 0.10.0

- Server-side logging.

## 0.9.0

- **Progress animation** while data is loading.
- Clicking an `entity_id` in the usage view **jumps to its states**.

## 0.8.0

- New **"Top Usage: States"** view.
- Top-usage columns are **sortable**.

## 0.7.0

- Fixed JSON serialization for tables containing binary data.

## 0.6.0

- **Rewritten as a single-page app** with a JSON API and server logging.

## 0.5.0

- Template refinements.

## 0.4.0

- **Ingress path support** (add-on runs behind the Home Assistant ingress).

## 0.3.0

- Add-on configuration refinements.

## 0.2.0

- Add-on configuration updated (supported architectures, repository URL).

## 0.1.0

- Initial release
- View all database tables
- Paginated table view
