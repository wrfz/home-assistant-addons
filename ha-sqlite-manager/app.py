import re
import asyncio
import hashlib
import sqlite3
import json
import logging
from pathlib import Path
from aiohttp import web


class SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, bytes):
            try:
                return obj.decode("utf-8")
            except UnicodeDecodeError:
                return f"<binary {len(obj)} bytes>"
        return super().default(obj)

DB_PATH = Path("/config/home-assistant_v2.db")
STATIC_DIR = Path("/opt/static")
CONFIG_YAML = Path("/opt/config.yaml")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ha-sqlite-manager")


def read_app_version():
    try:
        m = re.search(r'^version:\s*"?([0-9.]+)', CONFIG_YAML.read_text(), re.MULTILINE)
        return m.group(1) if m else "unknown"
    except Exception:
        return "unknown"


APP_VERSION = read_app_version()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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


async def api_tables(request):
    log.info("Listing tables")
    conn = get_db()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    conn.close()
    log.info("Found %d tables", len(tables))
    return web.json_response([t["name"] for t in tables])


async def api_states(request):
    log.info("Listing entities with state counts")
    since = parse_int(request.query.get("since"), -1)
    conn = get_db()
    rows = conn.execute(
        """
        SELECT sm.metadata_id, sm.entity_id, COUNT(s.state_id) AS state_count,
               MAX(s.state_id) AS max_state_id
        FROM states_meta sm
        LEFT JOIN states s ON s.metadata_id = sm.metadata_id
        GROUP BY sm.metadata_id, sm.entity_id
        ORDER BY sm.entity_id
        """
    ).fetchall()
    data = [dict(r) for r in rows]
    if since >= 0:
        new_counts = {
            r["metadata_id"]: r["new_count"]
            for r in conn.execute(
                "SELECT metadata_id, COUNT(*) AS new_count "
                "FROM states WHERE state_id > ? GROUP BY metadata_id",
                (since,),
            ).fetchall()
        }
        for r in data:
            r["new_count"] = new_counts.get(r["metadata_id"], 0)
    conn.close()
    log.info("Found %d entities", len(data))
    return web.Response(
        text=json.dumps(data, cls=SafeEncoder),
        content_type="application/json",
    )


async def api_table(request):
    table_name = request.match_info["table_name"]
    page = parse_int(request.query.get("page"), 1)
    page_size = parse_int(request.query.get("page_size"), 100)
    sort = request.query.get("sort")
    sort_dir = request.query.get("dir", "asc")

    log.info(
        "Viewing table '%s' (page %d, page_size %d, sort=%s %s)",
        table_name, page, page_size, sort, sort_dir,
    )

    conn = get_db()

    valid = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    ).fetchone()
    if not valid:
        conn.close()
        log.warning("Table '%s' not found", table_name)
        return web.json_response({"error": "Table not found"}, status=404)

    table_cols = {r["name"] for r in conn.execute(f'PRAGMA table_info("{table_name}")')}
    order_clause = ""
    if sort in table_cols and sort_dir in ("asc", "desc"):
        order_clause = f' ORDER BY "{sort}" {sort_dir.upper()}'

    total_rows = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
    offset = (page - 1) * page_size

    cursor = conn.execute(
        f'SELECT * FROM "{table_name}"{order_clause} LIMIT ? OFFSET ?', (page_size, offset)
    )
    columns = [desc[0] for desc in cursor.description]
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    log.info("Table '%s': %d rows total, returning %d rows", table_name, total_rows, len(rows))

    data = {
        "table_name": table_name,
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


async def api_entity_states(request):
    entity_id = request.match_info["entity_id"]
    page = parse_int(request.query.get("page"), 1)
    page_size = parse_int(request.query.get("page_size"), 100)
    sort = request.query.get("sort", "last_updated_ts")
    sort_dir = request.query.get("dir", "desc")

    log.info(
        "GET /api/entity/%s/states (page=%d, page_size=%d, sort=%s %s)",
        entity_id, page, page_size, sort, sort_dir,
    )

    conn = get_db()

    meta = conn.execute(
        "SELECT metadata_id FROM states_meta WHERE entity_id = ?", (entity_id,)
    ).fetchone()
    if not meta:
        conn.close()
        log.warning("Entity '%s' not found in states_meta", entity_id)
        return web.json_response({"error": "Entity not found"}, status=404)

    metadata_id = meta["metadata_id"]
    log.info("Entity '%s' -> metadata_id=%d", entity_id, metadata_id)

    states_cols = {r["name"] for r in conn.execute("PRAGMA table_info(states)")}
    if sort not in states_cols:
        sort = "last_updated_ts"
    if sort_dir not in ("asc", "desc"):
        sort_dir = "desc"

    total_rows = conn.execute(
        "SELECT COUNT(*) FROM states WHERE metadata_id = ?", (metadata_id,)
    ).fetchone()[0]
    log.info("Entity '%s': %d states in total", entity_id, total_rows)

    offset = (page - 1) * page_size
    cursor = conn.execute(
        f'SELECT * FROM states WHERE metadata_id = ? '
        f'ORDER BY "{sort}" {sort_dir.upper()} LIMIT ? OFFSET ?',
        (metadata_id, page_size, offset),
    )
    columns = [desc[0] for desc in cursor.description]
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    log.info("Entity '%s': returning %d rows (page %d/%d)", entity_id, len(rows), page, total_pages)

    data = {
        "entity_id": entity_id,
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


async def api_statistics(request):
    log.info("Listing statistics entities with counts")
    since = parse_int(request.query.get("since"), -1)
    conn = get_db()
    rows = conn.execute(
        """
        SELECT sm.id AS metadata_id, sm.statistic_id, COUNT(s.id) AS stat_count,
               MAX(s.id) AS max_stat_id
        FROM statistics_meta sm
        LEFT JOIN statistics s ON s.metadata_id = sm.id
        GROUP BY sm.id, sm.statistic_id
        ORDER BY sm.statistic_id
        """
    ).fetchall()
    data = [dict(r) for r in rows]
    if since >= 0:
        new_counts = {
            r["metadata_id"]: r["new_count"]
            for r in conn.execute(
                "SELECT metadata_id, COUNT(*) AS new_count "
                "FROM statistics WHERE id > ? GROUP BY metadata_id",
                (since,),
            ).fetchall()
        }
        for r in data:
            r["new_count"] = new_counts.get(r["metadata_id"], 0)
    conn.close()
    log.info("Found %d statistics", len(data))
    return web.Response(
        text=json.dumps(data, cls=SafeEncoder),
        content_type="application/json",
    )


async def api_statistic_data(request):
    statistic_id = request.match_info["statistic_id"]
    page = parse_int(request.query.get("page"), 1)
    page_size = parse_int(request.query.get("page_size"), 100)
    sort = request.query.get("sort", "start_ts")
    sort_dir = request.query.get("dir", "desc")

    log.info(
        "Viewing data for statistic '%s' (page %d, page_size %d, sort=%s %s)",
        statistic_id, page, page_size, sort, sort_dir,
    )

    conn = get_db()
    meta = conn.execute(
        "SELECT id FROM statistics_meta WHERE statistic_id = ?", (statistic_id,)
    ).fetchone()
    if not meta:
        conn.close()
        log.warning("Statistic '%s' not found in statistics_meta", statistic_id)
        return web.json_response({"error": "Statistic not found"}, status=404)

    metadata_id = meta["id"]

    stat_cols = {r["name"] for r in conn.execute("PRAGMA table_info(statistics)")}
    if sort not in stat_cols:
        sort = "start_ts"
    if sort_dir not in ("asc", "desc"):
        sort_dir = "desc"

    total_rows = conn.execute(
        "SELECT COUNT(*) FROM statistics WHERE metadata_id = ?", (metadata_id,)
    ).fetchone()[0]
    offset = (page - 1) * page_size
    cursor = conn.execute(
        f'SELECT * FROM statistics WHERE metadata_id = ? '
        f'ORDER BY "{sort}" {sort_dir.upper()} LIMIT ? OFFSET ?',
        (metadata_id, page_size, offset),
    )
    columns = [desc[0] for desc in cursor.description]
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    log.info("Statistic '%s': returning %d rows (page %d/%d)", statistic_id, len(rows), page, total_pages)

    data = {
        "statistic_id": statistic_id,
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


async def api_event_types(request):
    log.info("Listing event types with counts")
    since = parse_int(request.query.get("since"), -1)
    conn = get_db()
    rows = conn.execute(
        """
        SELECT et.event_type_id, et.event_type, COUNT(e.event_id) AS event_count,
               MAX(e.event_id) AS max_event_id
        FROM event_types et
        LEFT JOIN events e ON e.event_type_id = et.event_type_id
        GROUP BY et.event_type_id, et.event_type
        ORDER BY et.event_type
        """
    ).fetchall()
    data = [dict(r) for r in rows]
    if since >= 0:
        new_counts = {
            r["event_type_id"]: r["new_count"]
            for r in conn.execute(
                "SELECT event_type_id, COUNT(*) AS new_count "
                "FROM events WHERE event_id > ? GROUP BY event_type_id",
                (since,),
            ).fetchall()
        }
        for r in data:
            r["new_count"] = new_counts.get(r["event_type_id"], 0)
    conn.close()
    log.info("Found %d event types", len(data))
    return web.Response(
        text=json.dumps(data, cls=SafeEncoder),
        content_type="application/json",
    )


async def api_event_type_data(request):
    event_type = request.match_info["event_type"]
    page = parse_int(request.query.get("page"), 1)
    page_size = parse_int(request.query.get("page_size"), 100)
    sort = request.query.get("sort", "time_fired_ts")
    sort_dir = request.query.get("dir", "desc")

    log.info(
        "Viewing events for type '%s' (page %d, page_size %d, sort=%s %s)",
        event_type, page, page_size, sort, sort_dir,
    )

    conn = get_db()
    meta = conn.execute(
        "SELECT event_type_id FROM event_types WHERE event_type = ?", (event_type,)
    ).fetchone()
    if not meta:
        conn.close()
        log.warning("Event type '%s' not found in event_types", event_type)
        return web.json_response({"error": "Event type not found"}, status=404)

    event_type_id = meta["event_type_id"]

    events_cols = {r["name"] for r in conn.execute("PRAGMA table_info(events)")}
    if sort not in events_cols:
        sort = "time_fired_ts"
    if sort_dir not in ("asc", "desc"):
        sort_dir = "desc"

    total_rows = conn.execute(
        "SELECT COUNT(*) FROM events WHERE event_type_id = ?", (event_type_id,)
    ).fetchone()[0]
    offset = (page - 1) * page_size
    cursor = conn.execute(
        f'SELECT * FROM events WHERE event_type_id = ? '
        f'ORDER BY "{sort}" {sort_dir.upper()} LIMIT ? OFFSET ?',
        (event_type_id, page_size, offset),
    )
    columns = [desc[0] for desc in cursor.description]
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    log.info("Event type '%s': returning %d rows (page %d/%d)", event_type, len(rows), page, total_pages)

    data = {
        "event_type": event_type,
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
WATCH_INTERVAL = 3


def max_id(conn, spec):
    kind = spec.get("kind")
    if kind == "entity":
        row = conn.execute(
            "SELECT MAX(state_id) AS m FROM states WHERE metadata_id = "
            "(SELECT metadata_id FROM states_meta WHERE entity_id = ?)",
            (spec.get("id"),),
        ).fetchone()
    elif kind == "statistic":
        row = conn.execute(
            "SELECT MAX(id) AS m FROM statistics WHERE metadata_id = "
            "(SELECT id FROM statistics_meta WHERE statistic_id = ?)",
            (spec.get("id"),),
        ).fetchone()
    elif kind == "event":
        row = conn.execute(
            "SELECT MAX(event_id) AS m FROM events WHERE event_type_id = "
            "(SELECT event_type_id FROM event_types WHERE event_type = ?)",
            (spec.get("id"),),
        ).fetchone()
    else:
        row = conn.execute(f'SELECT MAX(rowid) AS m FROM "{spec.get("table")}"').fetchone()
    return row["m"] if row and row["m"] is not None else 0


def page_signature(conn, spec):
    kind = spec.get("kind")
    table = spec.get("table")
    if kind == "entity":
        where, params = (
            " WHERE metadata_id = (SELECT metadata_id FROM states_meta WHERE entity_id = ?)",
            [spec.get("id")],
        )
    elif kind == "statistic":
        where, params = (
            " WHERE metadata_id = (SELECT id FROM statistics_meta WHERE statistic_id = ?)",
            [spec.get("id")],
        )
    elif kind == "event":
        where, params = (
            " WHERE event_type_id = (SELECT event_type_id FROM event_types WHERE event_type = ?)",
            [spec.get("id")],
        )
    elif kind == "table":
        where, params = "", []
    else:
        return None

    sort = spec.get("sort")
    sort_dir = spec.get("dir") or "asc"
    table_cols = {r["name"] for r in conn.execute(f'PRAGMA table_info("{table}")')}
    order_clause = ""
    if sort in table_cols and sort_dir in ("asc", "desc"):
        order_clause = f' ORDER BY "{sort}" {sort_dir.upper()}'

    page = parse_int(spec.get("page"), 1)
    page_size = parse_int(spec.get("page_size"), 100)
    total = conn.execute(
        f'SELECT COUNT(*) AS c FROM "{table}"{where}', params
    ).fetchone()["c"]
    offset = (page - 1) * page_size
    rows = conn.execute(
        f'SELECT * FROM "{table}"{where}{order_clause} LIMIT ? OFFSET ?',
        params + [page_size, offset],
    ).fetchall()
    payload = json.dumps([total] + [dict(r) for r in rows], cls=SafeEncoder, sort_keys=True)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def check_view_changed(conn, spec, state):
    is_stats = spec.get("kind") == "statistic" or spec.get("table") in STATS_TABLES
    mid = max_id(conn, spec)
    sig = page_signature(conn, spec) if is_stats else None
    changed = state["max_id"] is not None and mid != state["max_id"]
    if is_stats and state["sig"] is not None and sig != state["sig"]:
        changed = True
    state["max_id"] = mid
    state["sig"] = sig
    return changed


async def ws_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    ws["watch"] = None
    ws["state"] = {"max_id": None, "sig": None}
    request.app["watch_connections"].add(ws)
    log.info("WebSocket client connected (%d active)", len(request.app["watch_connections"]))
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    continue
                if data.get("type") == "watch":
                    view = data.get("view")
                    ws["watch"] = view
                    ws["state"] = {"max_id": None, "sig": None}
                    log.info("Watch view set: %s", view)
    finally:
        request.app["watch_connections"].discard(ws)
        log.info("WebSocket client disconnected (%d active)", len(request.app["watch_connections"]))
    return ws


async def watch_loop(app):
    while True:
        await asyncio.sleep(WATCH_INTERVAL)
        for ws in list(app["watch_connections"]):
            spec = ws.get("watch")
            if not spec:
                continue
            try:
                conn = get_db()
                try:
                    changed = check_view_changed(conn, spec, ws["state"])
                finally:
                    conn.close()
                if changed:
                    await ws.send_json({"type": "reload"})
            except Exception as e:
                log.warning("Watch check failed: %s", e)


async def start_watch_loop(app):
    app["watch_task"] = asyncio.get_running_loop().create_task(watch_loop(app))


@web.middleware
async def no_cache_middleware(request, handler):
    resp = await handler(request)
    resp.headers["Cache-Control"] = "no-store"
    return resp


def create_app():
    app = web.Application(middlewares=[no_cache_middleware])
    app["watch_connections"] = set()
    app.router.add_get("/", index)
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/api/tables", api_tables)
    app.router.add_get("/api/states", api_states)
    app.router.add_get("/api/table/{table_name}", api_table)
    app.router.add_get("/api/entity/{entity_id}/states", api_entity_states)
    app.router.add_get("/api/statistics", api_statistics)
    app.router.add_get("/api/statistic/{statistic_id}/data", api_statistic_data)
    app.router.add_get("/api/event-types", api_event_types)
    app.router.add_get("/api/event-type/{event_type}/data", api_event_type_data)
    app.on_startup.append(start_watch_loop)
    return app


if __name__ == "__main__":
    log.info("Starting HA SQLite Manager on port 8099")
    log.info("Database: %s (exists: %s)", DB_PATH, DB_PATH.exists())
    app = create_app()
    web.run_app(app, port=8099)
