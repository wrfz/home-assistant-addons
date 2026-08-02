import re
import os
import asyncio
import hashlib
import json
import logging
from pathlib import Path
from aiohttp import web

import db


class SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, bytes):
            try:
                return obj.decode("utf-8")
            except UnicodeDecodeError:
                return f"<binary {len(obj)} bytes>"
        return super().default(obj)

STATIC_DIR = Path(os.environ.get("HA_STATIC_DIR", "/opt/static"))
CONFIG_YAML = Path(os.environ.get("HA_CONFIG_YAML", "/opt/config.yaml"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ha-db-manager")


def read_app_version():
    try:
        m = re.search(r'^version:\s*"?([0-9.]+)', CONFIG_YAML.read_text(), re.MULTILINE)
        return m.group(1) if m else "unknown"
    except Exception:
        return "unknown"


APP_VERSION = read_app_version()


def get_db():
    return db.get_connection()


def parse_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def index(request):
    version = request.query.get("v")
    if version != APP_VERSION:
        log.info("Redirecting to versioned URL (v=%s, was=%s)", APP_VERSION, version)
        return web.HTTPFound(f"?v={APP_VERSION}")
    log.info("Serving index page (app version %s)", APP_VERSION)
    html = (STATIC_DIR / "index.html").read_text().replace("__APP_VERSION__", APP_VERSION)
    resp = web.Response(text=html, content_type="text/html")
    resp.headers["X-Addon-Version"] = APP_VERSION
    return resp


async def static_file(request):
    name = request.match_info["name"]
    path = (STATIC_DIR / name).resolve()
    if STATIC_DIR.resolve() not in path.parents or not path.is_file():
        raise web.HTTPNotFound()
    text = path.read_text()
    if name == "app.js":
        text = text.replace("__APP_VERSION__", APP_VERSION)
    content_type = "application/javascript" if name.endswith(".js") else "text/css"
    resp = web.Response(text=text, content_type=content_type)
    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp


async def api_tables(request):
    log.info("Listing tables")
    conn = get_db()
    tables = db.list_tables(conn)
    conn.close()
    usage_names = list(USAGE_SPECS.keys())
    tables = usage_names + [name for name in tables if name not in usage_names]
    data = [
        {
            "name": name,
            "label": USAGE_SPECS[name].get("label") if name in USAGE_SPECS else None,
            "counts": name in USAGE_SPECS,
            "default_sort": USAGE_SPECS[name].get("default_sort") if name in USAGE_SPECS else None,
            "links": _view_links(name),
            "virtual_cols": _virtual_cols(name),
        }
        for name in tables
    ]
    log.info("Found %d tables", len(data))
    return web.json_response(data)


def query_paged(conn, table, where, params, page, page_size, sort, sort_dir, default_sort):
    """Run a paged SELECT * against a table with an optional WHERE clause.

    Returns (columns, rows, total_pages, total_rows). Sort column and direction
    are validated against the table's columns; invalid values fall back to
    default_sort (None means no ordering). Raises KeyError if the table does not
    exist.
    """
    table_cols = db.table_columns(conn, table)
    if not table_cols:
        raise KeyError(table)
    if sort not in table_cols:
        sort = default_sort
    if sort_dir not in ("asc", "desc"):
        sort_dir = "desc"
    order_clause = ""
    if sort:
        order_clause = f' ORDER BY {db.quote(sort)} {sort_dir.upper()}'
    total_rows = db.execute(
        conn, f'SELECT COUNT(*) AS c FROM {db.quote(table)}{where}', params
    ).fetchone()["c"]
    offset = (page - 1) * page_size
    res = db.execute(
        conn,
        f'SELECT * FROM {db.quote(table)}{where}{order_clause} LIMIT ? OFFSET ?',
        params + [page_size, offset],
    )
    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    return res.columns, res.fetchall(), total_pages, total_rows


RELATIONS = [
    {"parent": "states_meta", "parent_col": "metadata_id", "child": "states", "child_col": "metadata_id"},
    {"parent": "state_attributes", "parent_col": "attributes_id", "child": "states", "child_col": "attributes_id"},
    {"parent": "statistics_meta", "parent_col": "id", "child": "statistics", "child_col": "metadata_id"},
    {"parent": "statistics_meta", "parent_col": "id", "child": "statistics_short_term", "child_col": "metadata_id"},
    {"parent": "event_types", "parent_col": "event_type_id", "child": "events", "child_col": "event_type_id"},
    {"parent": "event_data", "parent_col": "data_id", "child": "events", "child_col": "data_id"},
]


USAGE_SPECS = {
    "states_meta": {
        "label": "States",
        "base": "SELECT sm.metadata_id, sm.entity_id FROM states_meta sm",
        "counts": [
            {"table": "states", "pk": "state_id", "group": "metadata_id",
             "count": "state_count"},
        ],
        "sorts": ["metadata_id", "entity_id", "state_count"],
        "default_sort": "entity_id",
        "filter_cols": ["metadata_id", "entity_id"],
        "links": {
            "entity_id": {"target": "states", "filter_col": "metadata_id", "value_col": "metadata_id"},
        },
    },
    "statistics_meta": {
        "label": "Statistics",
        "base": "SELECT sm.id AS metadata_id, sm.statistic_id FROM statistics_meta sm",
        "counts": [
            {"table": "statistics", "pk": "id", "group": "metadata_id",
             "count": "stat_count"},
            {"table": "statistics_short_term", "pk": "id", "group": "metadata_id",
             "count": "short_stat_count"},
        ],
        "sorts": ["metadata_id", "statistic_id", "stat_count", "short_stat_count"],
        "default_sort": "statistic_id",
        "filter_cols": ["metadata_id", "statistic_id"],
        "links": {
            "statistic_id": {"target": "statistics", "filter_col": "metadata_id", "value_col": "metadata_id"},
            "metadata_id": {"target": "statistics", "filter_col": "metadata_id", "value_col": "metadata_id"},
            "short_stat_count": {"target": "statistics_short_term", "filter_col": "metadata_id", "value_col": "metadata_id"},
        },
    },
    "event_types": {
        "label": "Events",
        "base": "SELECT et.event_type_id, et.event_type FROM event_types et",
        "counts": [
            {"table": "events", "pk": "event_id", "group": "event_type_id",
             "count": "event_count"},
        ],
        "sorts": ["event_type_id", "event_type", "event_count"],
        "default_sort": "event_type",
        "filter_cols": ["event_type_id", "event_type"],
        "links": {
            "event_type": {"target": "events", "filter_col": "event_type_id", "value_col": "event_type_id"},
            "event_type_id": {"target": "events", "filter_col": "event_type_id", "value_col": "event_type_id"},
        },
    },
}


def _view_links(table):
    """Map a view's columns to navigation targets (parent/child tables)."""
    links = {}
    if table in USAGE_SPECS:
        links.update(USAGE_SPECS[table].get("links", {}))
    for rel in RELATIONS:
        if rel["parent"] == table:
            links.setdefault(rel["parent_col"], {
                "target": rel["child"], "filter_col": rel["child_col"], "value_col": rel["parent_col"],
            })
        if rel["child"] == table:
            links.setdefault(rel["child_col"], {
                "target": rel["parent"], "filter_col": rel["parent_col"], "value_col": rel["child_col"],
            })
    return links


def _virtual_cols(table):
    """Columns of a count view that are computed, not part of the base table."""
    spec = USAGE_SPECS.get(table)
    if not spec:
        return []
    return [c["count"] for c in spec["counts"]] + ["new_count"]


def _count_view_base(spec, since, filter_col=None, filter_value=None):
    """Build the base SELECT of a count view (meta table + aggregated counts).

    Returns (sql, params). Each count table is pre-aggregated and joined to avoid
    cross products. The `new_count` column is always emitted; when `since >= 0`
    it counts rows added after `since` (per group), otherwise it is 0 for every
    row (nothing is new relative to the current baseline). When
    `filter_col`/`filter_value` are given the meta rows are restricted to
    matching values (used when navigating from a child table's foreign key back
    to its meta row).
    """
    selects = ["t.*"]
    joins = [f"FROM ({spec['base']}) t"]
    params = []
    where = ""
    if filter_col and filter_value is not None:
        where = f" WHERE t.{db.quote(filter_col)} = ?"
    for i, c in enumerate(spec["counts"]):
        alias = f"c{i}"
        selects.append(f"COALESCE({alias}.{c['count']}, 0) AS {c['count']}")
        joins.append(
            f"LEFT JOIN (SELECT {c['group']}, COUNT(*) AS {c['count']} "
            f"FROM {db.quote(c['table'])} GROUP BY {c['group']}) {alias} "
            f"ON {alias}.{c['group']} = t.{c['group']}"
        )
    if since >= 0:
        c = spec["counts"][0]
        selects.append("COALESCE(nc.new_count, 0) AS new_count")
        joins.append(
            f"LEFT JOIN (SELECT {c['group']} AS g, COUNT(*) AS new_count "
            f"FROM {db.quote(c['table'])} "
            f"WHERE {db.quote(c['pk'])} > ? GROUP BY {c['group']}) nc "
            f"ON nc.g = t.{c['group']}"
        )
        params.append(since)
    else:
        selects.append("0 AS new_count")
    if where:
        params.append(filter_value)
    return f"SELECT {', '.join(selects)} " + " ".join(joins) + where, params


def count_view_paged(conn, spec, page, page_size, sort, sort_dir, since,
                     filter_col=None, filter_value=None):
    """Run a paged count view for a meta table (see USAGE_SPECS).

    Returns (columns, rows, total_pages, total_rows, baseline) where baseline is
    the global max of the first count table's primary key (the frontend `since`
    anchor for the `new` column). The `new_count` column is always present (0 for
    every row when `since < 0`) and sortable. When `filter_col`/`filter_value`
    are given the meta rows are restricted to matching values.
    """
    sorts = list(spec["sorts"]) + ["new_count"]
    if sort not in sorts:
        sort = spec["default_sort"]
    if sort_dir not in ("asc", "desc"):
        sort_dir = "desc"
    base, base_params = _count_view_base(spec, since, filter_col, filter_value)
    total_rows = db.execute(
        conn, f"SELECT COUNT(*) AS c FROM ({base}) AS t", base_params
    ).fetchone()["c"]
    offset = (page - 1) * page_size
    res = db.execute(
        conn,
        f"SELECT * FROM ({base}) AS t "
        f"ORDER BY {db.quote(sort)} {sort_dir.upper()} LIMIT ? OFFSET ?",
        base_params + [page_size, offset],
    )
    columns = list(res.columns)
    rows = res.fetchall()
    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    first = spec["counts"][0]
    row = db.execute(
        conn,
        f"SELECT MAX({db.quote(first['pk'])}) AS m FROM {db.quote(first['table'])}",
    ).fetchone()
    baseline = row["m"] if row and row["m"] is not None else 0
    return columns, rows, total_pages, total_rows, baseline


async def api_table(request):
    table_name = request.match_info["table_name"]
    page = parse_int(request.query.get("page"), 1)
    page_size = parse_int(request.query.get("page_size"), 100)
    counts = request.query.get("counts") == "1"
    filter_col = request.query.get("filter_col")
    filter_value = request.query.get("filter_value")
    sort = request.query.get("sort")
    sort_dir = request.query.get("dir")
    if sort_dir is None:
        sort_dir = "desc" if filter_col and filter_value is not None else "asc"
    since = parse_int(request.query.get("since"), -1)

    log.info(
        "Viewing table '%s' (page %d, page_size %d, sort=%s %s, counts=%s, "
        "filter_col=%s, filter_value=%s)",
        table_name, page, page_size, sort, sort_dir, counts, filter_col, filter_value,
    )

    if table_name not in db.list_tables(get_db()):
        log.warning("Table '%s' not found", table_name)
        return web.json_response({"error": "Table not found"}, status=404)

    if counts:
        spec = USAGE_SPECS.get(table_name)
        if spec is None:
            return web.json_response({"error": "No count view for this table"}, status=404)
        if filter_col and filter_col not in spec["filter_cols"]:
            return web.json_response({"error": "Invalid filter column"}, status=400)
        conn = get_db()
        try:
            columns, rows, total_pages, total_rows, baseline = count_view_paged(
                conn, spec, page, page_size, sort or spec["default_sort"], sort_dir, since,
                filter_col, filter_value,
            )
        finally:
            conn.close()
        data = {
            "table_name": table_name,
            "counts": True,
            "columns": columns,
            "rows": rows,
            "page": page,
            "page_size": page_size,
            "total_rows": total_rows,
            "total_pages": total_pages,
            "global_baseline": baseline,
        }
        log.info("Count view '%s': %d rows total, returning %d rows", table_name, total_rows, len(rows))
        return web.Response(
            text=json.dumps(data, cls=SafeEncoder),
            content_type="application/json",
        )

    conn = get_db()
    try:
        table_cols = db.table_columns(conn, table_name)
    except Exception:
        conn.close()
        return web.json_response({"error": "Table not found"}, status=404)
    try:
        if filter_col and filter_value is not None:
            if filter_col not in table_cols:
                return web.json_response({"error": "Invalid filter column"}, status=400)
            columns, rows, total_pages, total_rows = query_paged(
                conn, table_name,
                f" WHERE {db.quote(filter_col)} = ?", [filter_value],
                page, page_size, sort, sort_dir, DETAIL_DEFAULT_SORTS.get(table_name),
            )
        else:
            columns, rows, total_pages, total_rows = query_paged(
                conn, table_name, "", [], page, page_size, sort, sort_dir, None
            )
    except KeyError:
        conn.close()
        log.warning("Table '%s' not found", table_name)
        return web.json_response({"error": "Table not found"}, status=404)
    finally:
        conn.close()

    log.info("Table '%s': %d rows total, returning %d rows", table_name, total_rows, len(rows))

    data = {
        "table_name": table_name,
        "counts": False,
        "columns": columns,
        "rows": rows,
        "page": page,
        "page_size": page_size,
        "total_rows": total_rows,
        "total_pages": total_pages,
    }
    return web.Response(
        text=json.dumps(data, cls=SafeEncoder),
        content_type="application/json",
    )


STATS_TABLES = {"statistics", "statistics_short_term"}

DETAIL_DEFAULT_SORTS = {
    "states": "last_updated_ts",
    "statistics": "start_ts",
    "statistics_short_term": "start_ts",
    "events": "time_fired_ts",
}


def max_id(conn, spec):
    table = spec.get("table")
    if spec.get("counts") and table in USAGE_SPECS:
        first = USAGE_SPECS[table]["counts"][0]
        filter_col = spec.get("filter_col")
        filter_value = spec.get("filter_value")
        if filter_col and filter_value is not None:
            row = db.execute(
                conn,
                f'SELECT MAX({db.quote(first["pk"])}) AS m FROM {db.quote(first["table"])} '
                f'WHERE {db.quote(filter_col)} = ?',
                (filter_value,),
            ).fetchone()
            return row["m"] if row and row["m"] is not None else 0
        row = db.execute(
            conn,
            f'SELECT MAX({db.quote(first["pk"])}) AS m FROM {db.quote(first["table"])}',
        ).fetchone()
        return row["m"] if row and row["m"] is not None else 0
    return db.max_row_id(conn, table)


def page_signature(conn, spec):
    table = spec.get("table")
    page = parse_int(spec.get("page"), 1)
    page_size = parse_int(spec.get("page_size"), 100)
    sort = spec.get("sort")
    sort_dir = spec.get("dir") or "asc"
    if spec.get("counts") and table in USAGE_SPECS:
        columns, rows, total_pages, total_rows, baseline = count_view_paged(
            conn, USAGE_SPECS[table], page, page_size,
            sort or USAGE_SPECS[table]["default_sort"], sort_dir,
            parse_int(spec.get("since"), -1),
            spec.get("filter_col"), spec.get("filter_value"),
        )
        payload = json.dumps([total_rows] + [dict(r) for r in rows], cls=SafeEncoder, sort_keys=True)
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    filter_col = spec.get("filter_col")
    filter_value = spec.get("filter_value")
    where = ""
    params = []
    if filter_col and filter_value is not None:
        where = f" WHERE {db.quote(filter_col)} = ?"
        params = [filter_value]
    table_cols = db.table_columns(conn, table)
    order_clause = ""
    if sort in table_cols and sort_dir in ("asc", "desc"):
        order_clause = f' ORDER BY {db.quote(sort)} {sort_dir.upper()}'

    total = db.execute(
        conn, f'SELECT COUNT(*) AS c FROM {db.quote(table)}{where}', params
    ).fetchone()["c"]
    offset = (page - 1) * page_size
    rows = db.execute(
        conn,
        f'SELECT * FROM {db.quote(table)}{where}{order_clause} LIMIT ? OFFSET ?',
        params + [page_size, offset],
    ).fetchall()
    payload = json.dumps([total] + [dict(r) for r in rows], cls=SafeEncoder, sort_keys=True)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def check_view_changed(conn, spec, state):
    is_stats = spec.get("counts") or spec.get("table") in STATS_TABLES
    mid = max_id(conn, spec)
    sig = page_signature(conn, spec) if is_stats else None
    if mid is None:
        state["max_id"] = None
        state["sig"] = sig
        return False
    changed = state["max_id"] is not None and mid != state["max_id"]
    if is_stats and state["sig"] is not None and sig != state["sig"]:
        changed = True
    state["max_id"] = mid
    state["sig"] = sig
    return changed


def view_key(view):
    return json.dumps(view, sort_keys=True)


async def ws_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    ws["watch_key"] = None
    request.app["state"]["watch_connections"].add(ws)
    log.info("WebSocket client connected (%d active)", len(request.app["state"]["watch_connections"]))
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    continue
                if data.get("type") == "watch":
                    view = data.get("view")
                    old = ws.get("watch_key")
                    if old and old in request.app["state"]["watches"]:
                        request.app["state"]["watches"][old]["connections"].discard(ws)
                        if not request.app["state"]["watches"][old]["connections"]:
                            del request.app["state"]["watches"][old]
                    ws["watch_key"] = None
                    if view:
                        key = view_key(view)
                        watch = request.app["state"]["watches"].setdefault(
                            key,
                            {"state": {"max_id": None, "sig": None}, "connections": set(), "spec": view},
                        )
                        watch["connections"].add(ws)
                        ws["watch_key"] = key
                    log.info("Watch view set: %s", view)
    finally:
        request.app["state"]["watch_connections"].discard(ws)
        key = ws.get("watch_key")
        if key and key in request.app["state"]["watches"]:
            request.app["state"]["watches"][key]["connections"].discard(ws)
            if not request.app["state"]["watches"][key]["connections"]:
                del request.app["state"]["watches"][key]
        log.info("WebSocket client disconnected (%d active)", len(request.app["state"]["watch_connections"]))
    return ws


async def watch_loop(app):
    while True:
        interval = app["state"]["watch_interval"]
        await asyncio.sleep(interval)
        for key, watch in list(app["state"]["watches"].items()):
            if not watch["connections"]:
                continue
            try:
                conn = get_db()
                try:
                    changed = check_view_changed(conn, watch["spec"], watch["state"])
                finally:
                    conn.close()
                if changed:
                    for ws in list(watch["connections"]):
                        await ws.send_json({"type": "reload"})
            except Exception as e:
                log.warning("Watch check failed: %s", e)


def settings_payload(app):
    return {
        "watch_interval": app["state"]["watch_interval"],
        "clients": len(app["state"].get("watch_connections", set())),
        "views": len(app["state"].get("watches", {})),
    }


def _settings_file():
    return os.environ.get("HA_SQLITE_SETTINGS_FILE", "/data/settings.json")


def load_settings(app):
    try:
        with open(_settings_file(), "r") as f:
            data = json.load(f)
        interval = parse_int(data.get("watch_interval"), None)
        if interval and 1 <= interval <= 60:
            app["state"]["watch_interval"] = interval
            log.info("Loaded watch interval %d s from %s", interval, _settings_file())
    except FileNotFoundError:
        pass
    except Exception as e:
        log.warning("Could not load settings from %s: %s", _settings_file(), e)


def save_settings(app):
    try:
        with open(_settings_file(), "w") as f:
            json.dump({"watch_interval": app["state"]["watch_interval"]}, f)
    except Exception as e:
        log.warning("Could not save settings to %s: %s", _settings_file(), e)


async def api_get_settings(request):
    return web.json_response(settings_payload(request.app))


async def api_set_settings(request):
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    interval = parse_int(body.get("watch_interval"), None)
    if interval is None or interval < 1 or interval > 60:
        return web.json_response(
            {"error": "watch_interval must be between 1 and 60 seconds"}, status=400
        )
    request.app["state"]["watch_interval"] = interval
    save_settings(request.app)
    log.info("Watch interval set to %d s", interval)
    return web.json_response(settings_payload(request.app))


async def start_watch_loop(app):
    app["watch_task"] = asyncio.get_running_loop().create_task(watch_loop(app))


@web.middleware
async def no_cache_middleware(request, handler):
    resp = await handler(request)
    if not request.path.startswith("/static/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


def create_app():
    app = web.Application(middlewares=[no_cache_middleware])
    app["state"] = {
        "watch_interval": 3,
        "watch_connections": set(),
        "watches": {},
    }
    load_settings(app)
    app.router.add_get("/", index)
    app.router.add_get("/static/{name}", static_file)
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/api/settings", api_get_settings)
    app.router.add_post("/api/settings", api_set_settings)
    app.router.add_get("/api/tables", api_tables)
    app.router.add_get("/api/table/{table_name}", api_table)
    if not os.environ.get("HA_DISABLE_WATCH_LOOP"):
        app.on_startup.append(start_watch_loop)
    return app


if __name__ == "__main__":
    backend = db.get_backend()
    log.info("Starting Home Assistant DB Manager on port 8099")
    log.info("Database backend: %s (%s)", backend.kind, backend.display_name())
    app = create_app()
    web.run_app(app, port=8099)
